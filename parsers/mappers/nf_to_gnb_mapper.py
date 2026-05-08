"""
NF-specific metrics mappers - convert NF metrics to gNB KPI metrics.

Each NF parser extracts different metrics. These mappers standardize
and route those metrics to the gNB aggregator using a common interface.
"""

from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from abc import ABC, abstractmethod
import logging
import re

logger = logging.getLogger(__name__)


class NFMetricsMapper(ABC):
    """Base class for NF-specific metric mappers"""
    
    @abstractmethod
    def extract_gnb_id(self, parsed_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract gNB ID from parsed NF event data.
        
        Returns:
            gNB identifier (e.g., "gNB_001") or None
        """
        pass
    
    @abstractmethod
    def map_metrics(
        self,
        gnb_id: str,
        parsed_data: Dict[str, Any],
        timestamp: datetime
    ) -> Tuple[str, str, float]:
        """
        Extract and map NF metrics to standard gNB metrics.
        
        Returns:
            Tuple of (metric_name, nf_type, value)
            Examples:
            - ("registration_latency", "amf", 45.2)
            - ("throughput", "upf", 350.5)
        """
        pass


class AMFMetricsMapper(NFMetricsMapper):
    """
    Maps AMF (Access and Mobility Function) metrics to gNB KPIs.
    
    AMF handles:
    - UE registration and deregistration
    - Authentication
    - Mobility management
    
    Key metrics:
    - Registration attempts/success rate
    - Authentication latency
    - Number of registered UEs
    """
    
    # Pattern to extract gNB ID from logs
    GNBID_PATTERN = re.compile(r'gNB[_-]?(\d{3,5})', re.IGNORECASE)
    
    def extract_gnb_id(self, parsed_data: Dict[str, Any]) -> Optional[str]:
        """Extract gNB ID from AMF event"""
        # Try multiple sources
        if 'gnb_id' in parsed_data:
            return parsed_data['gnb_id']
        
        if 'message' in parsed_data:
            match = self.GNBID_PATTERN.search(str(parsed_data['message']))
            if match:
                return f"gNB_{match.group(1)}"
        
        # Fallback: try to extract from GUTI or RAN_UE_NGAP_ID
        if 'guti' in parsed_data:
            # GUTI format includes gNB info
            parts = str(parsed_data['guti']).split('-')
            if len(parts) >= 2:
                return f"gNB_{parts[1]}"
        
        return None
    
    def map_metrics(
        self,
        gnb_id: str,
        parsed_data: Dict[str, Any],
        timestamp: datetime
    ) -> list:
        """
        Map AMF metrics.
        Can yield multiple metrics from single event.
        
        Returns:
            List of (metric_name, nf_type, value) tuples
        """
        metrics = []
        message = str(parsed_data.get('message', ''))
        severity = parsed_data.get('severity', 'INFO').upper()
        
        # Registration events
        if 'added' in message.lower() and 'ues' in message.lower():
            # "Number of AMF-UEs is now X"
            try:
                count = int(parsed_data.get('count', 0))
                metrics.append(('registration_attempts', 'amf', float(count)))
            except (ValueError, TypeError):
                pass
        
        elif 'removed' in message.lower() and 'ues' in message.lower():
            # UE deregistration (failure)
            metrics.append(('registration_attempts', 'amf', 1.0))
            if severity in ['ERROR', 'WARN']:
                metrics.append(('registration_successes', 'amf', 0.0))
            else:
                metrics.append(('registration_successes', 'amf', 1.0))
        
        elif 'registration' in message.lower() and 'accept' in message.lower():
            # Successful registration
            metrics.append(('registration_attempts', 'amf', 1.0))
            metrics.append(('registration_successes', 'amf', 1.0))
            
            # Extract latency if available
            if 'latency_ms' in parsed_data:
                try:
                    latency = float(parsed_data['latency_ms'])
                    metrics.append(('registration_latency', 'amf', latency))
                except (ValueError, TypeError):
                    pass
        
        elif 'registration' in message.lower() and ('reject' in message.lower() or 'fail' in message.lower()):
            # Failed registration
            metrics.append(('registration_attempts', 'amf', 1.0))
            metrics.append(('registration_successes', 'amf', 0.0))
        
        # Authentication events
        elif 'authentication' in message.lower():
            if 'success' in message.lower():
                metrics.append(('authentication_success', 'amf', 1.0))
            elif 'fail' in message.lower() or 'reject' in message.lower():
                metrics.append(('authentication_success', 'amf', 0.0))
            
            # Extract latency
            if 'latency_ms' in parsed_data:
                try:
                    latency = float(parsed_data['latency_ms'])
                    metrics.append(('registration_latency', 'amf', latency))
                except (ValueError, TypeError):
                    pass
        
        return metrics


class UPFMetricsMapper(NFMetricsMapper):
    """
    Maps UPF (User Plane Function) metrics to gNB KPIs.
    
    UPF handles:
    - Packet forwarding and routing
    - QoS enforcement
    - Traffic measurement
    
    Key metrics:
    - Throughput (Mbps)
    - Latency (ms)
    - Packet loss (%)
    - Active sessions
    """
    
    GNBID_PATTERN = re.compile(r'gNB[_-]?(\d{3,5})', re.IGNORECASE)
    
    def extract_gnb_id(self, parsed_data: Dict[str, Any]) -> Optional[str]:
        """Extract gNB ID from UPF event"""
        if 'gnb_id' in parsed_data:
            return parsed_data['gnb_id']
        
        if 'message' in parsed_data:
            match = self.GNBID_PATTERN.search(str(parsed_data['message']))
            if match:
                return f"gNB_{match.group(1)}"
        
        # UPF might track sessions per gNB - try teid or seid
        if 'seid' in parsed_data or 'teid' in parsed_data:
            # Simplified extraction - would need actual gNB context
            return None
        
        return None
    
    def map_metrics(
        self,
        gnb_id: str,
        parsed_data: Dict[str, Any],
        timestamp: datetime
    ) -> list:
        """Map UPF metrics"""
        metrics = []
        message = str(parsed_data.get('message', ''))
        
        # Throughput metrics
        if 'mbps' in parsed_data or 'throughput' in message.lower():
            try:
                throughput = float(parsed_data.get('mbps', 0))
                metrics.append(('throughput', 'upf', throughput))
            except (ValueError, TypeError):
                pass
        
        # Latency metrics
        if 'latency_ms' in parsed_data or 'latency' in message.lower():
            try:
                latency = float(parsed_data.get('latency_ms', 0))
                metrics.append(('latency', 'upf', latency))
            except (ValueError, TypeError):
                pass
        
        # Packet loss metrics
        if 'packet_loss' in message.lower() or 'dropped' in message.lower():
            try:
                # Extract packet loss percentage
                packet_loss = float(parsed_data.get('packet_loss', 0.0))
                metrics.append(('packet_loss', 'upf', packet_loss))
            except (ValueError, TypeError):
                pass
        
        # Session establishment (throughput indicator)
        if 'session' in message.lower() and 'establish' in message.lower():
            if 'success' in message.lower():
                metrics.append(('session_success', 'upf', 1.0))
            elif 'fail' in message.lower():
                metrics.append(('session_success', 'upf', 0.0))
        
        return metrics


class NRFMetricsMapper(NFMetricsMapper):
    """
    Maps NRF (Network Repository Function) metrics to gNB KPIs.
    
    NRF handles:
    - Service discovery
    - NF registration and deregistration
    
    Key metrics:
    - Service availability
    - NF health status
    """
    
    GNBID_PATTERN = re.compile(r'gNB[_-]?(\d{3,5})', re.IGNORECASE)
    
    def extract_gnb_id(self, parsed_data: Dict[str, Any]) -> Optional[str]:
        """Extract gNB ID from NRF event"""
        if 'gnb_id' in parsed_data:
            return parsed_data['gnb_id']
        
        if 'message' in parsed_data:
            match = self.GNBID_PATTERN.search(str(parsed_data['message']))
            if match:
                return f"gNB_{match.group(1)}"
        
        return None
    
    def map_metrics(
        self,
        gnb_id: str,
        parsed_data: Dict[str, Any],
        timestamp: datetime
    ) -> list:
        """Map NRF metrics"""
        metrics = []
        message = str(parsed_data.get('message', '')).lower()
        severity = parsed_data.get('severity', 'INFO').upper()
        
        # Service availability based on NF health
        if 'registered' in message:
            # NF registered = available
            metrics.append(('service_availability', 'nrf', 100.0))
        elif 'deregistered' in message or 'heartbeat' in message:
            if severity in ['ERROR', 'WARN']:
                # NF failed heartbeat = not available
                metrics.append(('service_availability', 'nrf', 0.0))
            else:
                # Normal deregistration
                metrics.append(('service_availability', 'nrf', 100.0))
        elif severity == 'ERROR':
            # Error in NRF = reduced availability
            metrics.append(('service_availability', 'nrf', 50.0))
        
        return metrics


class AUSFMetricsMapper(NFMetricsMapper):
    """
    Maps AUSF (Authentication Server Function) metrics to gNB KPIs.
    
    AUSF handles:
    - 5G authentication (AUSF for 3GPP, NEF for external)
    - UE authentication status
    
    Key metrics:
    - Authentication success rate
    - Authentication latency
    """
    
    GNBID_PATTERN = re.compile(r'gNB[_-]?(\d{3,5})', re.IGNORECASE)
    
    def extract_gnb_id(self, parsed_data: Dict[str, Any]) -> Optional[str]:
        """Extract gNB ID from AUSF event"""
        if 'gnb_id' in parsed_data:
            return parsed_data['gnb_id']
        
        if 'message' in parsed_data:
            match = self.GNBID_PATTERN.search(str(parsed_data['message']))
            if match:
                return f"gNB_{match.group(1)}"
        
        return None
    
    def map_metrics(
        self,
        gnb_id: str,
        parsed_data: Dict[str, Any],
        timestamp: datetime
    ) -> list:
        """Map AUSF metrics"""
        metrics = []
        message = str(parsed_data.get('message', '')).lower()
        
        # Authentication success/failure
        if 'authenticate' in message or 'authentication' in message:
            if 'success' in message or 'accept' in message:
                metrics.append(('authentication_success_rate', 'ausf', 100.0))
            elif 'fail' in message or 'reject' in message:
                metrics.append(('authentication_success_rate', 'ausf', 0.0))
            
            # Extract latency
            if 'latency_ms' in parsed_data:
                try:
                    latency = float(parsed_data['latency_ms'])
                    metrics.append(('authentication_latency', 'ausf', latency))
                except (ValueError, TypeError):
                    pass
        
        return metrics


class MapperFactory:
    """Factory for creating NF mappers"""
    
    _mappers = {
        'amf': AMFMetricsMapper,
        'upf': UPFMetricsMapper,
        'nrf': NRFMetricsMapper,
        'ausf': AUSFMetricsMapper,
    }
    
    @classmethod
    def get_mapper(cls, nf_type: str) -> Optional[NFMetricsMapper]:
        """Get mapper for NF type"""
        mapper_class = cls._mappers.get(nf_type.lower())
        return mapper_class() if mapper_class else None
    
    @classmethod
    def register_mapper(cls, nf_type: str, mapper_class: type):
        """Register custom mapper for NF type"""
        cls._mappers[nf_type.lower()] = mapper_class
