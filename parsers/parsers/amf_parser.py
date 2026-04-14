"""
AMF (Access and Mobility Management Function) log parser.
Extracts mobility events, registration stats, and UE context.
"""

import re
from typing import Dict, Optional, Iterator
from pathlib import Path

from parsers.base_parser import Open5GSLogParser, ParsedEvent


class AMFParser(Open5GSLogParser):
    """
    Parse Open5GS AMF logs for mobility and access metrics.
    
    Key metrics:
    - UE registrations (initial, mobility, periodic)
    - Authentication attempts/success/failure
    - Handover events
    - UE context management
    - NAS message statistics
    """
    
    def __init__(self, year: int = 2026):
        super().__init__('amf', year)
        
        self.event_patterns = {
            'initial_registration': re.compile(
                r'Initial registration',
                re.IGNORECASE
            ),
            'mobility_registration': re.compile(
                r'Mobility registration',
                re.IGNORECASE
            ),
            'periodic_registration': re.compile(
                r'Periodic registration',
                re.IGNORECASE
            ),
            'registration_accept': re.compile(
                r'Registration accept',
                re.IGNORECASE
            ),
            'registration_reject': re.compile(
                r'Registration reject.*cause\[(\d+)\]',
                re.IGNORECASE
            ),
            'authentication_success': re.compile(
                r'Authentication success',
                re.IGNORECASE
            ),
            'authentication_failure': re.compile(
                r'Authentication failure.*cause\[(\d+)\]',
                re.IGNORECASE
            ),
            'ue_context_release': re.compile(
                r'UE Context Release.*cause\[([^\]]+)\]',
                re.IGNORECASE
            ),
            'ng_setup': re.compile(
                r'gNB-NG-Setup.*gNB-ID\[([^\]]+)\]',
                re.IGNORECASE
            ),
            'handover_preparation': re.compile(
                r'Handover preparation',
                re.IGNORECASE
            ),
            'handover_execution': re.compile(
                r'Handover execution',
                re.IGNORECASE
            ),
            'handover_complete': re.compile(
                r'Handover complete',
                re.IGNORECASE
            ),
        }
    
    def _classify_event(self, message: str, data: Dict) -> str:
        """Classify AMF event type"""
        for event_type, pattern in self.event_patterns.items():
            if pattern.search(message):
                return event_type
        
        if 'ngap' in message.lower():
            return 'ngap_message'
        elif 'nas' in message.lower():
            return 'nas_message'
        
        return 'amf_other'
    
    def _enrich_event(self, event_type: str, data: Dict, message: str) -> Dict:
        """Enrich with AMF-specific data"""
        
        if 'registration' in event_type:
            # Extract registration type and UE identity
            reg_type = 'unknown'
            if 'initial' in event_type:
                reg_type = 'initial'
            elif 'mobility' in event_type:
                reg_type = 'mobility'
            elif 'periodic' in event_type:
                reg_type = 'periodic'
            
            data['registration_type'] = reg_type
            
            # Extract 5GS registration type
            reg_type_match = re.search(r'Registration Type\[(\d+)\]', message)
            if reg_type_match:
                data['5gs_registration_type'] = int(reg_type_match.group(1))
        
        elif event_type == 'registration_reject':
            match = self.event_patterns['registration_reject'].search(message)
            if match:
                data['reject_cause'] = int(match.group(1))
        
        elif event_type == 'ng_setup':
            match = self.event_patterns['ng_setup'].search(message)
            if match:
                data['gnb_id'] = match.group(1)
            
            # Extract gNB name if present
            gnb_name_match = re.search(r'gNB-Name\[([^\]]+)\]', message)
            if gnb_name_match:
                data['gnb_name'] = gnb_name_match.group(1)
            
            # Extract PLMN
            plmn_match = re.search(r'PLMN-ID\[([^\]]+)\]', message)
            if plmn_match:
                data['plmn'] = plmn_match.group(1)
        
        elif 'handover' in event_type:
            # Extract handover type
            if 'intra' in message.lower():
                data['handover_type'] = 'intra_amf'
            elif 'inter' in message.lower():
                data['handover_type'] = 'inter_amf'
            
            # Extract target
            target_match = re.search(r'TargetID\[([^\]]+)\]', message)
            if target_match:
                data['target_id'] = target_match.group(1)
        
        elif event_type == 'ue_context_release':
            match = self.event_patterns['ue_context_release'].search(message)
            if match:
                data['release_cause'] = match.group(1)
        
        # Extract UE counts
        ue_count_match = re.search(r'Number of AMF-UEs is now (\d+)', message)
        if ue_count_match:
            data['amf_ue_count'] = int(ue_count_match.group(1))
        
        gnb_ue_count_match = re.search(r'Number of gNB-UEs is now (\d+)', message)
        if gnb_ue_count_match:
            data['gnb_ue_count'] = int(gnb_ue_count_match.group(1))
        
        return data
    
    def to_kpi_event(self, event: ParsedEvent) -> Optional[Dict]:
        """Convert AMF event to KPI metric"""
        
        # Registration events
        if 'registration' in event.event_type:
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': event.structured_data.get('gnb_id', 'unknown'),
                'cell_id': 'unknown',  # Would need from RRC
                'metric_type': f"amf_{event.event_type}",
                'imsi': event.structured_data.get('imsi') or event.structured_data.get('supi'),
                'registration_type': event.structured_data.get('registration_type'),
                'success': 'accept' in event.event_type or 'success' in event.event_type,
                'reject_cause': event.structured_data.get('reject_cause'),
                '5gs_registration_type': event.structured_data.get('5gs_registration_type')
            }
        
        # gNB setup events
        elif event.event_type == 'ng_setup':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': event.structured_data.get('gnb_id'),
                'gnb_name': event.structured_data.get('gnb_name'),
                'plmn': event.structured_data.get('plmn'),
                'metric_type': 'amf_gnb_setup',
                'amf_ue_count': event.structured_data.get('amf_ue_count'),
                'gnb_ue_count': event.structured_data.get('gnb_ue_count')
            }
        
        # Handover events
        elif 'handover' in event.event_type:
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',  # Source gNB
                'metric_type': f"amf_{event.event_type}",
                'handover_type': event.structured_data.get('handover_type', 'unknown'),
                'target_id': event.structured_data.get('target_id'),
                'imsi': event.structured_data.get('imsi')
            }
        
        # UE context release
        elif event.event_type == 'ue_context_release':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': event.structured_data.get('gnb_id', 'unknown'),
                'metric_type': 'amf_ue_context_release',
                'release_cause': event.structured_data.get('release_cause'),
                'imsi': event.structured_data.get('imsi'),
                'amf_ue_count': event.structured_data.get('amf_ue_count')
            }
        
        # UE count updates (for load metrics)
        elif 'amf_ue_count' in event.structured_data:
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'aggregate',
                'metric_type': 'amf_ue_count',
                'amf_ue_count': event.structured_data['amf_ue_count'],
                'gnb_ue_count': event.structured_data.get('gnb_ue_count')
            }
        
        return None
    
    def calculate_registration_stats(self, 
                                      events: Iterator[ParsedEvent],
                                      window_minutes: int = 5) -> Iterator[Dict]:
        """
        Calculate registration success/failure rates.
        """
        from collections import defaultdict
        
        buckets = defaultdict(lambda: {
            'attempts': 0,
            'accepted': 0,
            'rejected': 0,
            'failures_by_cause': defaultdict(int),
            'unique_ues': set()
        })
        
        for event in events:
            if 'registration' not in event.event_type:
                continue
            
            window_key = event.timestamp.replace(second=0, microsecond=0)
            window_key = window_key.replace(minute=(window_key.minute // window_minutes) * window_minutes)
            
            bucket = buckets[window_key]
            
            bucket['attempts'] += 1
            
            if 'accept' in event.event_type:
                bucket['accepted'] += 1
            elif 'reject' in event.event_type:
                bucket['rejected'] += 1
                cause = event.structured_data.get('reject_cause', 'unknown')
                bucket['failures_by_cause'][cause] += 1
            
            imsi = event.structured_data.get('imsi')
            if imsi:
                bucket['unique_ues'].add(imsi)
        
        for timestamp, bucket in sorted(buckets.items()):
            total = bucket['attempts']
            yield {
                'timestamp': timestamp.isoformat(),
                'window_minutes': window_minutes,
                'registration_attempts': bucket['attempts'],
                'registration_accepted': bucket['accepted'],
                'registration_rejected': bucket['rejected'],
                'success_rate': bucket['accepted'] / total if total > 0 else 0,
                'unique_ues': len(bucket['unique_ues']),
                'rejection_causes': dict(bucket['failures_by_cause'])
            }
