"""
Event Processing Pipelines
"""

import logging
from typing import Dict, Any, Callable
from datetime import datetime

from models.events import (
    RANMetricEvent,
    AnomalyDetectedEvent,
    IncidentEvent,
    RecoveryEvent,
)
from .kafka_topics import KafkaTopics
from .producers import IncidentProducer, RecoveryProducer

logger = logging.getLogger(__name__)


class AnomalyPipeline:
    """Pipeline for processing anomaly events and creating incidents"""
    
    def __init__(self, incident_producer: IncidentProducer):
        self.incident_producer = incident_producer
    
    def process_anomaly(self, anomaly_event: Dict[str, Any]) -> Optional[IncidentEvent]:
        """Process anomaly event and create incident if needed"""
        try:
            event = AnomalyDetectedEvent(**anomaly_event)
            
            # Escalate to incident based on severity
            if event.severity in ["CRITICAL", "MAJOR"]:
                incident = IncidentEvent(
                    incident_id=f"INC-{event.event_id}",
                    gnb_id=event.gnb_id,
                    title=f"{event.anomaly_type} on {event.gnb_id}",
                    description=f"Anomaly detected: {event.details}",
                    severity=event.severity,
                    timestamp=datetime.utcnow(),
                    detected_at=event.timestamp,
                    status="OPEN",
                    root_cause="Unknown - pending analysis",
                    affected_services=[event.gnb_id],
                    tags=["anomaly-escalation"],
                )
                
                self.incident_producer.send_incident(incident)
                logger.info(f"Created incident {incident.incident_id}")
                return incident
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing anomaly: {e}")
            return None


class IncidentPipeline:
    """Pipeline for processing incidents and creating recovery actions"""
    
    def __init__(self, recovery_producer: RecoveryProducer):
        self.recovery_producer = recovery_producer
    
    def process_incident(self, incident_event: Dict[str, Any]) -> Optional[RecoveryEvent]:
        """Process incident event and create recovery action"""
        try:
            event = IncidentEvent(**incident_event)
            
            # Generate recovery action based on incident type
            recovery = self._generate_recovery_action(event)
            
            if recovery:
                self.recovery_producer.send_recovery(recovery)
                logger.info(f"Created recovery action {recovery.recovery_id}")
            
            return recovery
            
        except Exception as e:
            logger.error(f"Error processing incident: {e}")
            return None
    
    def _generate_recovery_action(self, incident: IncidentEvent) -> Optional[RecoveryEvent]:
        """Generate recovery action based on incident details"""
        
        if "PRB" in incident.title or "resource" in incident.description.lower():
            return RecoveryEvent(
                recovery_id=f"REC-{incident.incident_id}",
                incident_id=incident.incident_id,
                action="Increase PRB allocation",
                description="Automatic PRB allocation increase",
                priority="HIGH",
                estimated_time_minutes=5,
                status="PENDING",
                timestamp=datetime.utcnow(),
                tags=["auto-recovery"],
            )
        
        elif "latency" in incident.title.lower():
            return RecoveryEvent(
                recovery_id=f"REC-{incident.incident_id}",
                incident_id=incident.incident_id,
                action="Optimize routing",
                description="Automatic routing optimization",
                priority="HIGH",
                estimated_time_minutes=10,
                status="PENDING",
                timestamp=datetime.utcnow(),
                tags=["auto-recovery"],
            )
        
        elif "packet_loss" in incident.title.lower():
            return RecoveryEvent(
                recovery_id=f"REC-{incident.incident_id}",
                incident_id=incident.incident_id,
                action="Enable retransmission",
                description="Automatic retransmission policy",
                priority="MEDIUM",
                estimated_time_minutes=2,
                status="PENDING",
                timestamp=datetime.utcnow(),
                tags=["auto-recovery"],
            )
        
        return None
