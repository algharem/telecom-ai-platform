"""
Real Open5GS Log Parser
Extracts KPI metrics from actual Open5GS network function logs (AMF, SMF, UPF, etc.)

Since these logs don't contain direct gNB or throughput information,
this parser derives KPIs from available session and event data:
- gNB ID: Derived from cell ID or mapped from default config
- Throughput: Generated based on session activity rate
- Latency: Estimated from event processing timestamps
- Packet Loss: Estimated from reject/failure events
"""

import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class SessionEvent:
    """Represents a parsed session event from logs"""
    timestamp: datetime
    event_type: str  # 'session_start', 'session_end', 'auth_failure', 'attach_failure'
    imsi: Optional[str]
    ue_id: Optional[str]
    cell_id: Optional[str]  # e.g., 0x19b01
    apn: Optional[str]
    nf_type: str  # 'amf', 'smf', 'upf', 'nrf'
    raw_line: str


class Open5GSRealLogParser:
    """
    Parse actual Open5GS logs and convert to gNB-level KPI metrics.
    
    Handles: AMF, SMF, UPF, NRF, HSS, AUSF logs
    Extracts: Session activity, authentication events, attachment failures
    Derives: gNB metrics with synthetic throughput/latency/packet_loss
    """
    
    def __init__(self):
        self.session_events: List[SessionEvent] = []
        self.cell_to_gnb_map: Dict[str, str] = self._build_cell_to_gnb_map()
        self.session_counters = defaultdict(lambda: {
            'total_sessions': 0,
            'successful_sessions': 0,
            'failed_sessions': 0,
            'auth_failures': 0,
            'attach_failures': 0,
            'session_end_count': 0,
            'timestamps': []
        })
    
    def _build_cell_to_gnb_map(self) -> Dict[str, str]:
        """Map cell IDs from logs to gNB identifiers"""
        return {
            '0x19b01': 'gNB-001',  # From mme.log CellID
            '0x19b02': 'gNB-002',
            '0x19b03': 'gNB-003',
            '0x19b04': 'gNB-004',
            '0x19b05': 'gNB-005',
        }
    
    def parse_line(self, line: str, nf_type: str, log_date: str) -> Optional[SessionEvent]:
        """
        Parse a single log line and extract session event.
        
        Args:
            line: Raw log line
            nf_type: Network function type (amf, smf, upf, nrf, hss)
            log_date: Date from filename (YYYY-MM-DD format)
        
        Returns:
            SessionEvent or None if no match
        """
        try:
            # Extract timestamp from line
            timestamp = self._extract_timestamp(line, log_date)
            if not timestamp:
                return None
            
            # Parse by network function type
            if nf_type == 'mme' or nf_type == 'amf':
                return self._parse_amf_line(line, timestamp, nf_type)
            elif nf_type == 'smf':
                return self._parse_smf_line(line, timestamp)
            elif nf_type == 'upf':
                return self._parse_upf_line(line, timestamp)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing line: {e}")
            return None
    
    def _extract_timestamp(self, line: str, log_date: str) -> Optional[datetime]:
        """Extract timestamp from log line"""
        # Pattern: HH:MM:SS.mmm
        pattern = r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})'
        match = re.search(pattern, line)
        
        if not match:
            return None
        
        try:
            h, m, s, ms = match.groups()
            date_part = datetime.strptime(log_date, '%Y-%m-%d')
            return datetime(
                date_part.year, date_part.month, date_part.day,
                int(h), int(m), int(s), int(ms) * 1000
            )
        except:
            return None
    
    def _parse_amf_line(self, line: str, timestamp: datetime, nf_type: str) -> Optional[SessionEvent]:
        """Parse AMF/MME log lines for attach/registration events"""
        
        # Extract IMSI if present (15 digits in brackets)
        imsi_match = re.search(r'\[(\d{15})\]', line)
        imsi = imsi_match.group(1) if imsi_match else None
        
        # Extract cell ID (CellID[0xXXXXX] or similar variants)
        cell_match = re.search(r'CellID\[([^\]]+)\]', line)
        cell_id = cell_match.group(1) if cell_match else None
        
        # Extract ENB_UE_S1AP_ID or MME_UE_S1AP_ID
        ue_id_match = re.search(r'(?:ENB_UE_S1AP_ID|MME_UE_S1AP_ID)\[(\d+)\]', line)
        ue_id = ue_id_match.group(1) if ue_id_match else None
        
        # Classify event type - be more flexible with pattern matching
        event_type = None
        
        # Session start patterns
        if any(x in line for x in ['Attach', 'attach', 'registration', 'Registration', 'initiated', 'create']):
            event_type = 'session_start'
        # Session end patterns
        elif any(x in line for x in ['Released', 'released', 'Remove', 'remove', 'deleted', 'Deleted', 'end']):
            event_type = 'session_end'
        # Auth/failure patterns
        elif any(x in line for x in ['reject', 'Reject', 'failure', 'Failure', 'failed', 'Failed', 'error', 'Error']):
            if 'attach' in line.lower():
                event_type = 'attach_failure'
            else:
                event_type = 'auth_failure'
        else:
            return None
        
        return SessionEvent(
            timestamp=timestamp,
            event_type=event_type,
            imsi=imsi,
            ue_id=ue_id,
            cell_id=cell_id,
            apn=None,
            nf_type=nf_type,
            raw_line=line
        )
    
    def _parse_smf_line(self, line: str, timestamp: datetime) -> Optional[SessionEvent]:
        """Parse SMF log lines for session and data events"""
        
        # Extract IMSI (15 digits)
        imsi_match = re.search(r'(?:IMSI|imsi)\[?(\d{15})\]?', line)
        imsi = imsi_match.group(1) if imsi_match else None
        
        # Extract APN (any identifier in brackets after APN)
        apn_match = re.search(r'APN\[([^\]]+)\]', line)
        apn = apn_match.group(1) if apn_match else None
        
        # Classify event - be more flexible
        event_type = None
        
        if any(x in line for x in ['Added', 'added', 'create', 'Create', 'session', 'Session']):
            event_type = 'session_start'
        elif any(x in line for x in ['Removed', 'removed', 'Released', 'released', 'delete', 'Delete']):
            event_type = 'session_end'
        else:
            return None
        
        return SessionEvent(
            timestamp=timestamp,
            event_type=event_type,
            imsi=imsi,
            ue_id=None,
            cell_id=None,
            apn=apn,
            nf_type='smf',
            raw_line=line
        )
    
    def _parse_upf_line(self, line: str, timestamp: datetime) -> Optional[SessionEvent]:
        """Parse UPF log lines for packet data events"""
        
        # UPF logs are less structured; look for session events
        if 'session' in line.lower():
            if 'created' in line.lower() or 'start' in line.lower():
                event_type = 'session_start'
            elif 'removed' in line.lower() or 'end' in line.lower():
                event_type = 'session_end'
            else:
                return None
            
            return SessionEvent(
                timestamp=timestamp,
                event_type=event_type,
                imsi=None,
                ue_id=None,
                cell_id=None,
                apn=None,
                nf_type='upf',
                raw_line=line
            )
        
        return None
    
    def process_file(self, filepath: Path, nf_type: str) -> List[SessionEvent]:
        """Process entire log file and extract events"""
        events = []
        
        # Extract date from filename or use today
        try:
            # Assuming format like: amf.log or amf-2023-06-10.log
            if '-' in filepath.stem:
                log_date = filepath.stem.split('-')[-3:]
                log_date_str = '-'.join(log_date)
            else:
                log_date_str = datetime.now().strftime('%Y-%m-%d')
        except:
            log_date_str = datetime.now().strftime('%Y-%m-%d')
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    event = self.parse_line(line, nf_type, log_date_str)
                    if event:
                        events.append(event)
                        self.session_events.append(event)
        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")
        
        return events
    
    def aggregate_to_gnb_kpi(self, events: List[SessionEvent], window_seconds: int = 60) -> Dict:
        """
        Aggregate session events into gNB-level KPI metrics.
        
        Returns dict mapping gNB ID to KPI metrics:
        {
            'gNB-001': {
                'timestamp': datetime,
                'prb_usage': float (0-100),
                'throughput': float (Mbps),
                'latency': float (ms),
                'packet_loss': float (%),
                'registration_success_rate': float (%)
            }
        }
        """
        
        # Group events by gNB and time window
        gnb_metrics = {}
        
        for event in events:
            # Determine gNB ID
            gnb_id = 'gNB-001'  # Default
            if event.cell_id:
                gnb_id = self.cell_to_gnb_map.get(event.cell_id, 'gNB-001')
            
            if gnb_id not in self.session_counters:
                self.session_counters[gnb_id] = {
                    'total_sessions': 0,
                    'successful_sessions': 0,
                    'failed_sessions': 0,
                    'auth_failures': 0,
                    'attach_failures': 0,
                    'session_end_count': 0,
                    'timestamps': []
                }
            
            counters = self.session_counters[gnb_id]
            
            # Update counters based on event type
            if event.event_type == 'session_start':
                counters['total_sessions'] += 1
                counters['successful_sessions'] += 1
            elif event.event_type == 'session_end':
                counters['session_end_count'] += 1
            elif event.event_type == 'auth_failure':
                counters['auth_failures'] += 1
                counters['failed_sessions'] += 1
            elif event.event_type == 'attach_failure':
                counters['attach_failures'] += 1
                counters['failed_sessions'] += 1
            
            counters['timestamps'].append(event.timestamp)
        
        # Calculate KPI metrics for each gNB
        for gnb_id, counters in self.session_counters.items():
            total = counters['total_sessions']
            failed = counters['failed_sessions']
            
            # Registration success rate (%)
            reg_success_rate = 100 * (total - failed) / max(total, 1)
            
            # Derive other metrics from event statistics
            # These are synthetic but based on real activity patterns
            
            # PRB usage: correlate with session count (higher sessions = higher PRB usage)
            prb_usage = min(100, 20 + (total % 80))
            
            # Throughput: estimate from session count and successful completions
            # Average 5 Mbps per session
            throughput = counters['successful_sessions'] * 5
            
            # Latency: based on auth failures (more failures = longer latency)
            latency = 20 + (counters['auth_failures'] * 2)
            
            # Packet loss: from failed sessions
            packet_loss = 100 * failed / max(total, 1)
            
            gnb_metrics[gnb_id] = {
                'gnb_id': gnb_id,
                'timestamp': datetime.utcnow().isoformat(),
                'prb_usage': round(prb_usage, 2),
                'throughput': round(throughput, 2),
                'latency': round(min(latency, 100), 2),  # Cap latency at 100ms
                'packet_loss': round(packet_loss, 2),
                'registration_success_rate': round(reg_success_rate, 2),
                'source': 'logs',
                # Debug info
                'session_count': total,
                'success_count': counters['successful_sessions'],
                'fail_count': failed,
                'auth_failures': counters['auth_failures'],
                'attach_failures': counters['attach_failures'],
            }
        
        return gnb_metrics


def parse_open5gs_logs(log_dir: Path) -> List[Dict]:
    """
    Main entry point: Parse all Open5GS logs in a directory and return KPI records.
    
    Args:
        log_dir: Path to directory containing amf.log, smf.log, upf.log, etc.
    
    Returns:
        List of gNB KPI metric dictionaries
    """
    
    # Validate directory exists
    if not isinstance(log_dir, Path):
        log_dir = Path(log_dir)
    
    logger.info(f"[PARSER] Starting log parsing from: {log_dir}")
    logger.info(f"[PARSER] Directory exists: {log_dir.exists()}")
    
    if not log_dir.exists():
        logger.warning(f"[PARSER] Log directory does not exist: {log_dir}")
        return []
    
    if not log_dir.is_dir():
        logger.warning(f"[PARSER] Path is not a directory: {log_dir}")
        return []
    
    parser = Open5GSRealLogParser()
    all_events = []
    files_processed = 0
    
    # NF log file patterns
    nf_types = {
        'amf*.log': 'amf',
        'mme*.log': 'mme',
        'smf*.log': 'smf',
        'upf*.log': 'upf',
        'nrf*.log': 'nrf',
        'hss*.log': 'hss',
        'ausf*.log': 'ausf',
    }
    
    # List all files in directory for debugging
    try:
        all_files = list(log_dir.glob('*.log'))
        logger.info(f"[PARSER] Found {len(all_files)} .log files in {log_dir}")
        for f in all_files[:5]:  # Log first 5 files
            logger.info(f"[PARSER]   - {f.name}")
    except Exception as e:
        logger.error(f"[PARSER] Error listing directory: {e}")
    
    # Process each log file
    for pattern, nf_type in nf_types.items():
        try:
            matching_files = list(log_dir.glob(pattern))
            logger.info(f"[PARSER] Pattern '{pattern}': found {len(matching_files)} files")
            
            for filepath in matching_files:
                logger.info(f"[PARSER] Parsing {filepath.name} as {nf_type}")
                try:
                    events = parser.process_file(filepath, nf_type)
                    all_events.extend(events)
                    files_processed += 1
                    logger.info(f"[PARSER] Extracted {len(events)} events from {filepath.name}")
                except Exception as e:
                    logger.error(f"[PARSER] Error processing {filepath}: {e}")
        except Exception as e:
            logger.error(f"[PARSER] Error globbing pattern {pattern}: {e}")
    
    logger.info(f"[PARSER] Total events extracted: {len(all_events)} from {files_processed} files")
    
    # Aggregate to gNB KPI metrics
    kpi_metrics = parser.aggregate_to_gnb_kpi(all_events)
    logger.info(f"[PARSER] Generated {len(kpi_metrics)} gNB KPI records")
    
    # Log generated gNB metrics
    for gnb_id, metrics in kpi_metrics.items():
        logger.info(f"[PARSER] {gnb_id}: throughput={metrics['throughput']} Mbps, "
                   f"latency={metrics['latency']} ms, prb={metrics['prb_usage']}%")
    
    return list(kpi_metrics.values())
