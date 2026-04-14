"""
Base infrastructure for parsing Open5GS logs.
Provides common parsing, timestamp handling, and event extraction.
"""

import re
import gzip
import logging
from datetime import datetime
from typing import Dict, List, Optional, Iterator, Any, Callable
from dataclasses import dataclass
from pathlib import Path
import json
import hashlib


logger = logging.getLogger(__name__)


@dataclass
class ParsedEvent:
    """Standardized event from any NF log"""
    timestamp: datetime
    nf_type: str           # AMF, SMF, UPF, etc.
    event_type: str        # registration, session_establishment, etc.
    severity: str          # DEBUG, INFO, WARN, ERROR, FATAL
    message: str           # Raw message
    structured_data: Dict[str, Any]  # Extracted key-value pairs
    raw_line: str          # Original log line
    source_file: str
    line_number: int


class Open5GSLogParser:
    """
    Base parser for Open5GS log files.
    
    Open5GS log format:
    [TIMESTAMP] [NF] [PID] [SEVERITY] [COMPONENT] message...
    
    Example:
    03/27 14:32:15.284: [amf] INFO: [Added] Number of AMF-UEs is now 1 (../src/amf/context.c:141)
    """
    
    # Open5GS timestamp format: MM/DD HH:MM:SS.mmm
    TIMESTAMP_PATTERN = re.compile(
        r'^(\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}):\s+'
        r'\[(\w+)\]\s+(\w+):\s+(.*)$'
    )
    
    # Severity levels
    SEVERITIES = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
    
    # NF types in Open5GS
    NF_TYPES = [
        'amf', 'ausf', 'bsf', 'hss', 'mme', 'nrf', 'nssf',
        'pcf', 'pcrf', 'scp', 'sgwc', 'sgwu', 'smf',
        'udm', 'udr', 'upf'
    ]
    
    def __init__(self, nf_type: str, year: int = 2026):
        """
        Initialize parser for specific NF.
        
        Args:
            nf_type: One of Open5GS NF types
            year: Year for timestamp (logs don't include year)
        """
        self.nf_type = nf_type.lower()
        self.year = year
        
        # Event-specific parsers
        self.event_parsers: Dict[str, Callable] = {}
        
        # Metrics aggregation
        self.metrics_buffer: List[Dict] = []
        self.buffer_size = 1000
    
    def parse_file(self, file_path: Path) -> Iterator[ParsedEvent]:
        """
        Parse entire log file, yielding structured events.
        
        Supports .log and .log.gz files.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        # Handle compressed files
        if file_path.suffix == '.gz':
            open_fn = gzip.open
            mode = 'rt'
        else:
            open_fn = open
            mode = 'r'
        
        line_num = 0
        
        with open_fn(file_path, mode, encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_num += 1
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    event = self._parse_line(line, file_path.name, line_num)
                    if event:
                        yield event
                except Exception as e:
                    logger.debug(f"Parse error at {file_path}:{line_num}: {e}")
                    continue
    
    def _parse_line(self, line: str, source_file: str, line_num: int) -> Optional[ParsedEvent]:
        """Parse single log line"""
        match = self.TIMESTAMP_PATTERN.match(line)
        
        if not match:
            # Continuation of previous line or malformed
            return None
        
        timestamp_str, nf, severity, message = match.groups()
        
        # Skip if NF doesn't match (shouldn't happen with separate files)
        if nf.lower() != self.nf_type:
            return None
        
        # Parse timestamp
        timestamp = self._parse_timestamp(timestamp_str)
        
        # Extract structured data
        structured_data = self._extract_structured_data(message)
        
        # Determine event type
        event_type = self._classify_event(message, structured_data)
        
        # NF-specific enrichment
        structured_data = self._enrich_event(event_type, structured_data, message)
        
        return ParsedEvent(
            timestamp=timestamp,
            nf_type=self.nf_type.upper(),
            event_type=event_type,
            severity=severity.upper(),
            message=message,
            structured_data=structured_data,
            raw_line=line,
            source_file=source_file,
            line_number=line_num
        )
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse Open5GS timestamp format"""
        # Format: "03/27 14:32:15.284"
        try:
            dt = datetime.strptime(f"{self.year}/{ts_str}", "%Y/%m/%d %H:%M:%S.%f")
            return dt
        except ValueError:
            # Fallback
            return datetime.now()
    
    def _extract_structured_data(self, message: str) -> Dict[str, Any]:
        """Extract key-value pairs from message"""
        data = {}
        
        # Common patterns
        patterns = {
            'imsi': r'imsi-(\d+)',
            'supi': r'supi-imsi-(\d+)',
            'guti': r'guti-\[([^\]]+)\]',
            'amf_ue_ngap_id': r'AMF_UE_NGAP_ID\[(\d+)\]',
            'ran_ue_ngap_id': r'RAN_UE_NGAP_ID\[(\d+)\]',
            'suci': r'suci-\[([^\]]+)\]',
            'pei': r'pei-([^\s]+)',
            'dnn': r'DNN\[([^\]]+)\]',
            's_nssai': r'S-NSSAI\[([^\]]+)\]',
            'ip_address': r'IPv?4?\[?([0-9.]+)\]?',
            'port': r'Port\[?(\d+)\]?',
            'seid': r'SEID\[?(0[xX][0-9a-fA-F]+)\]?',
            'teid': r'TEID\[?(0[xX][0-9a-fA-F]+)\]?',
            'pdr_id': r'PDR-ID\[?(\d+)\]?',
            'far_id': r'FAR-ID\[?(\d+)\]?',
            'qer_id': r'QER-ID\[?(\d+)\]?',
            'urr_id': r'URR-ID\[?(\d+)\]?',
            'bar_id': r'BAR-ID\[?(\d+)\]?',
        }
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                data[key] = matches[0] if len(matches) == 1 else matches
        
        # Extract numbers
        number_patterns = [
            (r'Number of \w+ is now (\d+)', 'count'),
            (r'(\d+) bytes', 'bytes'),
            (r'(\d+) packets', 'packets'),
            (r'(\d+\.?\d*) Mbps', 'mbps'),
            (r'(\d+\.?\d*) ms', 'latency_ms'),
        ]
        
        for pattern, key in number_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    data[key] = float(match.group(1)) if '.' in match.group(1) else int(match.group(1))
                except ValueError:
                    data[key] = match.group(1)
        
        return data
    
    def _classify_event(self, message: str, data: Dict) -> str:
        """Classify message into event type"""
        # Override in subclasses
        return "unknown"
    
    def _enrich_event(self, event_type: str, data: Dict, message: str) -> Dict:
        """NF-specific enrichment"""
        return data
    
    def register_event_parser(self, event_type: str, parser: Callable):
        """Register custom parser for event type"""
        self.event_parsers[event_type] = parser
    
    def to_kpi_event(self, parsed_event: ParsedEvent) -> Optional[Dict]:
        """
        Convert parsed event to platform KPI event.
        Override in NF-specific parsers.
        """
        return None


class MetricsAggregator:
    """
    Aggregate metrics from log events for time-series storage.
    """
    
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.buckets: Dict[str, Dict] = {}
    
    def add_event(self, event: ParsedEvent):
        """Add event to appropriate time bucket"""
        bucket_key = event.timestamp.strftime("%Y-%m-%d %H:%M")
        
        if bucket_key not in self.buckets:
            self.buckets[bucket_key] = {
                'timestamp': event.timestamp.replace(second=0, microsecond=0),
                'nf_type': event.nf_type,
                'events': [],
                'counters': {}
            }
        
        self.buckets[bucket_key]['events'].append(event)
        
        # Update counters
        counter_key = f"{event.event_type}_{event.severity}"
        self.buckets[bucket_key]['counters'][counter_key] = \
            self.buckets[bucket_key]['counters'].get(counter_key, 0) + 1
    
    def get_metrics(self) -> Iterator[Dict]:
        """Yield aggregated metrics"""
        for bucket in sorted(self.buckets.values(), key=lambda x: x['timestamp']):
            yield self._compute_metrics(bucket)
    
    def _compute_metrics(self, bucket: Dict) -> Dict:
        """Compute aggregate metrics from bucket"""
        events = bucket['events']
        
        return {
            'timestamp': bucket['timestamp'].isoformat(),
            'nf_type': bucket['nf_type'],
            'total_events': len(events),
            'event_breakdown': bucket['counters'],
            'unique_ues': len(set(
                e.structured_data.get('imsi') or e.structured_data.get('supi')
                for e in events
                if 'imsi' in e.structured_data or 'supi' in e.structured_data
            )),
            'error_rate': sum(
                1 for e in events if e.severity in ['ERROR', 'FATAL']
            ) / len(events) if events else 0
        }
    
    def clear_old_buckets(self, keep_minutes: int = 5):
        """Clear buckets older than specified minutes"""
        cutoff = datetime.utcnow().replace(second=0, microsecond=0)
        cutoff = cutoff.replace(minute=(cutoff.minute - keep_minutes) % 60)
        
        old_keys = [
            k for k, v in self.buckets.items()
            if v['timestamp'] < cutoff
        ]
        
        for k in old_keys:
            del self.buckets[k]
