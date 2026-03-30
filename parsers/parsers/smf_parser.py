"""
SMF (Session Management Function) log parser.
Extracts session management, QoS, and charging metrics.
"""

import re
from typing import Dict, Optional
from pathlib import Path

from parsers.base_parser import Open5GSLogParser, ParsedEvent


class SMFParser(Open5GSLogParser):
    """
    Parse Open5GS SMF logs for session management KPIs.
    
    Key metrics:
    - PDU session establishment/modification/release
    - QoS flow management (5QI, GFBR, MFBR)
    - IP address allocation
    - UPF selection and association
    - Charging data records (CDR)
    """
    
    def __init__(self, year: int = 2026):
        super().__init__('smf', year)
        
        self.event_patterns = {
            'pdu_session_establishment': re.compile(
                r'Create SM Context',
                re.IGNORECASE
            ),
            'pdu_session_modification': re.compile(
                r'Update SM Context.*Modifying',
                re.IGNORECASE
            ),
            'pdu_session_release': re.compile(
                r'Release SM Context',
                re.IGNORECASE
            ),
            'qos_flow_setup': re.compile(
                r'QoS Flow.*5QI\[(\d+)\]',
                re.IGNORECASE
            ),
            'upf_association': re.compile(
                r'UPF associated.*IPv4\[([^\]]+)\]',
                re.IGNORECASE
            ),
            'ip_allocation': re.compile(
                r'UE IPv4\[([^\]]+)\]',
                re.IGNORECASE
            ),
            'n4_session_setup': re.compile(
                r'PFCP Session Establishment',
                re.IGNORECASE
            ),
            'charging_record': re.compile(
                r'Charging Data.*URR-ID',
                re.IGNORECASE
            ),
        }
    
    def _classify_event(self, message: str, data: Dict) -> str:
        """Classify SMF event type"""
        for event_type, pattern in self.event_patterns.items():
            if pattern.search(message):
                return event_type
        
        if 'pfcp' in message.lower():
            return 'pfcp_message'
        elif 'n11' in message.lower():
            return 'n11_message'
        elif 'n4' in message.lower():
            return 'n4_message'
        
        return 'smf_other'
    
    def _enrich_event(self, event_type: str, data: Dict, message: str) -> Dict:
        """Enrich with SMF-specific data"""
        
        if event_type == 'pdu_session_establishment':
            # Extract DNN and S-NSSAI
            dnn_match = re.search(r'DNN\[([^\]]+)\]', message)
            if dnn_match:
                data['dnn'] = dnn_match.group(1)
            
            snssai_match = re.search(r'S-NSSAI\[([^\]]+)\]', message)
            if snssai_match:
                data['s_nssai'] = snssai_match.group(1)
            
            # Extract PDU session type
            type_match = re.search(r'PDU Session Type\[([^\]]+)\]', message)
            if type_match:
                data['pdu_session_type'] = type_match.group(1)
        
        elif event_type == 'qos_flow_setup':
            match = self.event_patterns['qos_flow_setup'].search(message)
            if match:
                data['5qi'] = int(match.group(1))
            
            # Extract GFBR/MFBR
            gfbr_match = re.search(r'GFBR\[UL:([^\]]+),DL:([^\]]+)\]', message)
            if gfbr_match:
                data['gfbr_ul'] = gfbr_match.group(1)
                data['gfbr_dl'] = gfbr_match.group(2)
            
            mfbr_match = re.search(r'MFBR\[UL:([^\]]+),DL:([^\]]+)\]', message)
            if mfbr_match:
                data['mfbr_ul'] = mfbr_match.group(1)
                data['mfbr_dl'] = mfbr_match.group(2)
        
        elif event_type == 'upf_association':
            match = self.event_patterns['upf_association'].search(message)
            if match:
                data['upf_ip'] = match.group(1)
            
            # Extract UPF name/ID
            upf_name_match = re.search(r'UPF\[([^\]]+)\]', message)
            if upf_name_match:
                data['upf_name'] = upf_name_match.group(1)
        
        elif event_type == 'ip_allocation':
            match = self.event_patterns['ip_allocation'].search(message)
            if match:
                data['allocated_ip'] = match.group(1)
        
        elif event_type == 'charging_record':
            # Extract usage data
            ul_match = re.search(r'UL\[(\d+)\s*([KMGT]?)B\]', message)
            dl_match = re.search(r'DL\[(\d+)\s*([KMGT]?)B\]', message)
            
            if ul_match:
                data['usage_ul_bytes'] = self._parse_data_size(
                    int(ul_match.group(1)), ul_match.group(2)
                )
            if dl_match:
                data['usage_dl_bytes'] = self._parse_data_size(
                    int(dl_match.group(1)), dl_match.group(2)
                )
        
        # Extract SM context counts
        sm_count_match = re.search(r'SM contexts is now (\d+)', message)
        if sm_count_match:
            data['sm_context_count'] = int(sm_count_match.group(1))
        
        return data
    
    @staticmethod
    def _parse_data_size(value: int, unit: str) -> int:
        """Convert KB/MB/GB to bytes"""
        multipliers = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
        return value * multipliers.get(unit, 1)
    
    def to_kpi_event(self, event: ParsedEvent) -> Optional[Dict]:
        """Convert SMF event to KPI metric"""
        
        if event.event_type == 'pdu_session_establishment':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': event.structured_data.get('gnb_id', 'unknown'),
                'metric_type': 'smf_pdu_session_established',
                'imsi': event.structured_data.get('imsi'),
                'dnn': event.structured_data.get('dnn'),
                's_nssai': event.structured_data.get('s_nssai'),
                'pdu_session_type': event.structured_data.get('pdu_session_type'),
                'allocated_ip': event.structured_data.get('allocated_ip'),
                'sm_context_count': event.structured_data.get('sm_context_count')
            }
        
        elif event.event_type == 'qos_flow_setup':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'smf_qos_flow_established',
                'imsi': event.structured_data.get('imsi'),
                '5qi': event.structured_data.get('5qi'),
                'gfbr_ul': event.structured_data.get('gfbr_ul'),
                'gfbr_dl': event.structured_data.get('gfbr_dl'),
                'dnn': event.structured_data.get('dnn')
            }
        
        elif event.event_type == 'upf_association':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'smf_upf_associated',
                'upf_name': event.structured_data.get('upf_name'),
                'upf_ip': event.structured_data.get('upf_ip')
            }
        
        elif event.event_type == 'charging_record':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'smf_charging_data',
                'imsi': event.structured_data.get('imsi'),
                'usage_ul_bytes': event.structured_data.get('usage_ul_bytes'),
                'usage_dl_bytes': event.structured_data.get('usage_dl_bytes'),
                'urr_id': event.structured_data.get('urr_id')
            }
        
        elif 'sm_context_count' in event.structured_data:
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'aggregate',
                'metric_type': 'smf_context_count',
                'sm_context_count': event.structured_data['sm_context_count']
            }
        
        return None
