"""
PCF (Policy Control Function) log parser.
Extracts policy control, bandwidth enforcement, and QoS metrics.
"""

import re
from typing import Dict, Optional
from pathlib import Path

from parsers.base_parser import Open5GSLogParser, ParsedEvent


class PCFParser(Open5GSLogParser):
    """
    Parse Open5GS PCF logs for policy control KPIs.
    
    Key metrics:
    - Policy decision requests/responses
    - QoS policy provisioning (5QI, ARP, MBR)
    - Bandwidth enforcement
    - Charging policy application
    - PCC rule activation/deactivation
    """
    
    def __init__(self, year: int = 2026):
        super().__init__('pcf', year)
        
        self.event_patterns = {
            'policy_decision_request': re.compile(
                r'Policy Authorization.*Request',
                re.IGNORECASE
            ),
            'policy_decision_response': re.compile(
                r'Policy Authorization.*Response',
                re.IGNORECASE
            ),
            'pcc_rule_creation': re.compile(
                r'PCC Rule.*Create',
                re.IGNORECASE
            ),
            'pcc_rule_removal': re.compile(
                r'PCC Rule.*Remove',
                re.IGNORECASE
            ),
            'qos_policy_provision': re.compile(
                r'QoS.*5QI\[(\d+)\].*ARP\[(\d+)\]',
                re.IGNORECASE
            ),
            'bandwidth_enforcement': re.compile(
                r'MBR\[UL:([^\]]+),DL:([^\]]+)\]',
                re.IGNORECASE
            ),
            'charging_policy': re.compile(
                r'Charging.*(?:Online|Offline)',
                re.IGNORECASE
            ),
            'session_binding': re.compile(
                r'Session Binding',
                re.IGNORECASE
            ),
        }
    
    def _classify_event(self, message: str, data: Dict) -> str:
        """Classify PCF event type"""
        for event_type, pattern in self.event_patterns.items():
            if pattern.search(message):
                return event_type
        
        if 'n7' in message.lower() or 'n5' in message.lower():
            return 'pcf_interface_message'
        elif 'policy' in message.lower():
            return 'policy_management'
        
        return 'pcf_other'
    
    def _enrich_event(self, event_type: str, data: Dict, message: str) -> Dict:
        """Enrich with PCF-specific data"""
        
        if event_type == 'policy_decision_response':
            # Extract policy decision result
            result_match = re.search(r'Result\[(\w+)\]', message)
            if result_match:
                data['decision_result'] = result_match.group(1)
        
        elif event_type == 'qos_policy_provision':
            match = self.event_patterns['qos_policy_provision'].search(message)
            if match:
                data['5qi'] = int(match.group(1))
                data['arp'] = int(match.group(2))
            
            # Extract MBR values
            mbr_match = self.event_patterns['bandwidth_enforcement'].search(message)
            if mbr_match:
                data['mbr_ul'] = mbr_match.group(1)
                data['mbr_dl'] = mbr_match.group(2)
            
            # Extract GBR values if present
            gbr_match = re.search(r'GBR\[UL:([^\]]+),DL:([^\]]+)\]', message)
            if gbr_match:
                data['gbr_ul'] = gbr_match.group(1)
                data['gbr_dl'] = gbr_match.group(2)
        
        elif event_type == 'pcc_rule_creation':
            # Extract PCC rule ID
            rule_match = re.search(r'PCC Rule ID\[([^\]]+)\]', message)
            if rule_match:
                data['pcc_rule_id'] = rule_match.group(1)
            
            # Extract rule name
            name_match = re.search(r'PCC Rule Name\[([^\]]+)\]', message)
            if name_match:
                data['pcc_rule_name'] = name_match.group(1)
        
        elif event_type == 'charging_policy':
            if 'online' in message.lower():
                data['charging_type'] = 'online'
            elif 'offline' in message.lower():
                data['charging_type'] = 'offline'
        
        elif event_type == 'session_binding':
            # Extract binding information
            binding_match = re.search(r'Binding\[([^\]]+)\]', message)
            if binding_match:
                data['binding_type'] = binding_match.group(1)
        
        # Extract DNN if present
        dnn_match = re.search(r'DNN\[([^\]]+)\]', message)
        if dnn_match:
            data['dnn'] = dnn_match.group(1)
        
        # Extract S-NSSAI if present
        snssai_match = re.search(r'S-NSSAI\[([^\]]+)\]', message)
        if snssai_match:
            data['s_nssai'] = snssai_match.group(1)
        
        return data
    
    def to_kpi_event(self, event: ParsedEvent) -> Optional[Dict]:
        """Convert PCF event to KPI metric"""
        
        if event.event_type == 'policy_decision_response':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'pcf_policy_decision',
                'imsi': event.structured_data.get('imsi'),
                'decision_result': event.structured_data.get('decision_result'),
                'dnn': event.structured_data.get('dnn'),
                's_nssai': event.structured_data.get('s_nssai')
            }
        
        elif event.event_type == 'qos_policy_provision':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'pcf_qos_provisioned',
                'imsi': event.structured_data.get('imsi'),
                '5qi': event.structured_data.get('5qi'),
                'arp': event.structured_data.get('arp'),
                'mbr_ul': event.structured_data.get('mbr_ul'),
                'mbr_dl': event.structured_data.get('mbr_dl'),
                'gbr_ul': event.structured_data.get('gbr_ul'),
                'gbr_dl': event.structured_data.get('gbr_dl')
            }
        
        elif event.event_type == 'pcc_rule_creation':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'pcf_pcc_rule_created',
                'pcc_rule_id': event.structured_data.get('pcc_rule_id'),
                'pcc_rule_name': event.structured_data.get('pcc_rule_name'),
                'imsi': event.structured_data.get('imsi')
            }
        
        elif event.event_type == 'charging_policy':
            return {
                'timestamp': event.timestamp.isoformat(),
                'gnb_id': 'unknown',
                'metric_type': 'pcf_charging_policy',
                'charging_type': event.structured_data.get('charging_type'),
                'imsi': event.structured_data.get('imsi'),
                'dnn': event.structured_data.get('dnn')
            }
        
        return None
