"""
UPF (User Plane Function) log parser.
Extracts user plane metrics: throughput, latency, packet loss, session stats.
"""

import re
from typing import Dict, Optional, Iterator
from pathlib import Path
from datetime import datetime

from parsers.base_parser import Open5GSLogParser, ParsedEvent


class UPFParser(Open5GSLogParser):
    """
    Parse Open5GS UPF logs for user plane KPIs.
    
    Key metrics:
    - Session establishment/teardown
    - Data volume (UL/DL bytes)
    - Throughput estimates
    - Packet forwarding stats
    - QoS enforcement (QER)
    """
    
    def __init__(self, year: int = 2026):
        super().__init__('upf', year)
        
        # UPF-specific event patterns
        self.event_patterns = {
            'session_establishment': re.compile(
                r'UE F-SEID\[.*\] APN\[([^\]]+)\] PDN-Type\[([^\]]+)\]',
                re.IGNORECASE
            ),
            'session_deletion': re.compile(
                r'UE F-SEID.* removed',
                re.IGNORECASE
            ),
            'data_forwarding': re.compile(
                r'gtp5g.* (\d+) bytes',
                re.IGNORECASE
            ),
            'pdr_setup': re.compile(
                r'PDR-ID\[(\d+)\] .* (CREATE|UPDATE|REMOVE)',
                re.IGNORECASE
            ),
            'qer_enforcement': re.compile(
                r'QER-ID\[(\d+)\] .* (GATE|RATE)',
                re.IGNORECASE
            ),
            'buffering': re.compile(
                r'Buffer.* (\d+) packets',
                re.IGNORECASE
            ),
        }
    
    def _classify_event(self, message: str, data: Dict) -> str:
        """Classify UPF event type"""
        for event_type, pattern in self.event_patterns.items():
            if pattern.search(message):
                return event_type
        
        # Generic classification
        if 'gtp5g' in message.lower():
            return 'gtp_tunnel'
        elif 'pfcp' in message.lower():
            return 'pfcp_message'
        elif 'session' in message.lower():
            return 'session_management'
        
        return 'other'
    
    def _enrich_event(self, event_type: str, data: Dict, message: str) -> Dict:
        """Enrich with UPF-specific data"""
        
        if event_type == 'session_establishment':
            # Extract APN/DNN and PDN type
            match = self.event_patterns['session_establishment'].search(message)
            if match:
                data['dnn'] = match.group(1)
                data['pdn_type'] = match.group(2)
            
            # Extract IP allocation
            ip_match = re.search(r'IPv4\[([0-9.]+)\]', message)
            if ip_match:
                data['ue_ip'] = ip_match.group(1)
            
            # Extract SEID for session tracking
            seid_match = re.search(r'F-SEID\[CP:([^\]]+),UP:([^\]]+)\]', message)
            if seid_match:
                data['cp_seid'] = seid_match.group(1)
                data['up_seid'] = seid_match.group(2)
        
        elif event_type == 'data_forwarding':
            # Extract direction and volume
            if 'gtp5g' in message:
                if 'recv' in message.lower() or 'ul' in message.lower():
                    data['direction'] = 'uplink'
                elif 'send' in message.lower() or 'dl' in message.lower():
                    data['direction'] = 'downlink'
                
                # Extract bytes
                bytes_match = re.search(r'(\d+) bytes', message)
                if bytes_match:
                    data['bytes'] = int(bytes_match.group(1))
        
        elif event_type == 'qer_enforcement':
            # Extract QoS parameters
            gate_match = re.search(r'GATE\[([^\]]+)\]', message)
            if gate_match:
                data['gate_status'] = gate_match.group(1)
            
            rate_match = re.search(r'MBR\[UL:([^\]]+),DL:([^\]]+)\]', message)
            if rate_match:
                data['mbr_ul'] = rate_match.group(1)
                data['mbr_dl'] = rate_match.group(2)
        
        return data
    
    def to_kpi_event(self, event: ParsedEvent) -> Optional[Dict]:
        """Convert UPF event to KPI metric"""
        
        if event.event_type == 'data_forwarding' and 'bytes' in event.structured_data:
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': self._infer_gnb_from_seid(event.structured_data),
                'metric_type': 'upf_data_volume',
                'direction': event.structured_data.get('direction', 'unknown'),
                'bytes': event.structured_data['bytes'],
                'ue_ip': event.structured_data.get('ue_ip'),
                'seid': event.structured_data.get('up_seid'),
                'dnn': event.structured_data.get('dnn', 'default')
            }
        
        elif event.event_type == 'session_establishment':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',  # Will be resolved from AMF logs
                'metric_type': 'upf_session_established',
                'ue_ip': event.structured_data.get('ue_ip'),
                'dnn': event.structured_data.get('dnn'),
                'pdn_type': event.structured_data.get('pdn_type'),
                'seid': event.structured_data.get('up_seid')
            }
        
        elif event.event_type == 'qer_enforcement':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'upf_qos_enforcement',
                'qer_id': event.structured_data.get('qer_id'),
                'gate_status': event.structured_data.get('gate_status'),
                'mbr_ul': event.structured_data.get('mbr_ul'),
                'mbr_dl': event.structured_data.get('mbr_dl')
            }
        
        return None
    
    def _infer_gnb_from_seid(self, data: Dict) -> str:
        """Infer gNB from SEID (would need correlation with AMF logs)"""
        seid = data.get('up_seid', '')
        # SEID often contains gNB identifier bits
        # This is a placeholder - real implementation needs correlation
        return f"gNB_{seid[-4:]}" if len(seid) > 4 else "gNB_unknown"
    
    def calculate_throughput_metrics(self, 
                                       events: Iterator[ParsedEvent],
                                       window_seconds: int = 60) -> Iterator[Dict]:
        """
        Calculate throughput metrics from data volume events.
        """
        from collections import defaultdict
        
        buckets = defaultdict(lambda: {
            'ul_bytes': 0,
            'dl_bytes': 0,
            'sessions': set(),
            'start_time': None,
            'end_time': None
        })
        
        for event in events:
            if event.event_type != 'data_forwarding':
                continue
            
            # Round to window
            window_key = event.timestamp.replace(
                second=(event.timestamp.second // window_seconds) * window_seconds,
                microsecond=0
            )
            
            bucket = buckets[window_key]
            
            if bucket['start_time'] is None:
                bucket['start_time'] = event.timestamp
            bucket['end_time'] = event.timestamp
            
            direction = event.structured_data.get('direction', 'unknown')
            bytes_count = event.structured_data.get('bytes', 0)
            
            if direction == 'uplink':
                bucket['ul_bytes'] += bytes_count
            elif direction == 'downlink':
                bucket['dl_bytes'] += bytes_count
            
            # Track unique sessions
            seid = event.structured_data.get('up_seid')
            if seid:
                bucket['sessions'].add(seid)
        
        # Yield throughput metrics
        for timestamp, bucket in sorted(buckets.items()):
            duration = (bucket['end_time'] - bucket['start_time']).total_seconds()
            if duration <= 0:
                duration = window_seconds
            
            yield {
                'timestamp': timestamp.isoformat(),
                'window_seconds': window_seconds,
                'ul_mbps': (bucket['ul_bytes'] * 8) / (duration * 1_000_000),
                'dl_mbps': (bucket['dl_bytes'] * 8) / (duration * 1_000_000),
                'total_mbps': ((bucket['ul_bytes'] + bucket['dl_bytes']) * 8) / (duration * 1_000_000),
                'active_sessions': len(bucket['sessions']),
                'ul_bytes': bucket['ul_bytes'],
                'dl_bytes': bucket['dl_bytes']
            }


def parse_upf_log(file_path: Path, year: int = 2026) -> Iterator[Dict]:
    """
    Convenience function to parse UPF log and yield KPI events.
    """
    parser = UPFParser(year)
    
    for event in parser.parse_file(file_path):
        kpi = parser.to_kpi_event(event)
        if kpi:
            yield kpi
