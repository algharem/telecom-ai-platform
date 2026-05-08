"""
Phase 4: Background Event Processor Worker
Processes Kafka events and triggers downstream actions
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from models.events import (
    EventType, SeverityLevel, AnomalyType,
    RANMetricEvent, AnomalyDetectedEvent, IncidentEvent
)

logger = logging.getLogger(__name__)


class EventProcessor:
    """Background worker processing events from Kafka"""
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.incident_cache = {}  # Track open incidents
        logger.info("[PROCESSOR] Event processor initialized")
    
    async def process_metric_event(self, event_data: Dict[str, Any]):
        """Process RAN metric event"""
        try:
            event = RANMetricEvent(**event_data)
            
            # Check for anomalies
            if event.is_anomaly and event.confidence > 0.7:
                await self._escalate_to_anomaly(event)
            
            self.processed_count += 1
            logger.debug(f"[PROCESSOR] Processed metric event: {event.event_id}")
        except Exception as e:
            logger.error(f"[PROCESSOR] Error processing metric event: {e}")
            self.error_count += 1
    
    async def process_anomaly_event(self, event_data: Dict[str, Any]):
        """Process anomaly detected event"""
        try:
            event = AnomalyDetectedEvent(**event_data)
            
            # Critical anomalies escalate to incidents
            if event.severity in [SeverityLevel.CRITICAL, SeverityLevel.EMERGENCY]:
                await self._escalate_to_incident(event)
            
            self.processed_count += 1
            logger.info(f"[PROCESSOR] Processed anomaly event: {event.event_id}")
        except Exception as e:
            logger.error(f"[PROCESSOR] Error processing anomaly event: {e}")
            self.error_count += 1
    
    async def process_incident_event(self, event_data: Dict[str, Any]):
        """Process incident event"""
        try:
            event = IncidentEvent(**event_data)
            
            # Track incident
            self.incident_cache[event.event_id] = event
            
            # Trigger response workflows
            if event.severity == SeverityLevel.EMERGENCY:
                await self._trigger_emergency_response(event)
            elif event.severity == SeverityLevel.CRITICAL:
                await self._trigger_critical_response(event)
            
            self.processed_count += 1
            logger.info(f"[PROCESSOR] Processed incident: {event.event_id} - {event.incident_title}")
        except Exception as e:
            logger.error(f"[PROCESSOR] Error processing incident event: {e}")
            self.error_count += 1
    
    async def _escalate_to_anomaly(self, metric_event: RANMetricEvent):
        """Escalate detected anomaly to anomaly event"""
        anomaly_event = AnomalyDetectedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            severity=self._infer_severity(metric_event),
            gnb_id=metric_event.gnb_id,
            anomaly_types=self._classify_anomalies(metric_event),
            detection_method="pattern",
            anomaly_score=metric_event.confidence,
            explanation=f"Anomaly detected in metrics for {metric_event.gnb_id}",
            affected_metrics={
                "prb_usage": metric_event.prb_usage,
                "throughput": metric_event.throughput,
                "latency": metric_event.latency,
                "packet_loss": metric_event.packet_loss
            },
            correlation_id=metric_event.event_id
        )
        
        # Publish to anomalies topic
        from services.event_streaming import event_producer
        if event_producer:
            await event_producer.publish_anomaly_event(anomaly_event.model_dump(mode='json'))
        
        logger.info(f"[PROCESSOR] Escalated to anomaly: {anomaly_event.event_id}")
    
    async def _escalate_to_incident(self, anomaly_event: AnomalyDetectedEvent):
        """Escalate critical anomaly to incident"""
        incident = IncidentEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            severity=anomaly_event.severity,
            incident_title=f"Incident detected on {anomaly_event.gnb_id}",
            incident_description=anomaly_event.explanation,
            affected_gnbs=[anomaly_event.gnb_id],
            impact_score=anomaly_event.anomaly_score,
            related_event_ids=[anomaly_event.event_id],
            status="open"
        )
        
        # Publish to incidents topic
        from services.event_streaming import event_producer
        if event_producer:
            await event_producer.publish_incident_event(incident.model_dump(mode='json'))
        
        logger.warning(f"[PROCESSOR] Escalated to incident: {incident.event_id}")
    
    async def _trigger_emergency_response(self, incident: IncidentEvent):
        """Trigger emergency response actions"""
        logger.critical(f"[PROCESSOR] EMERGENCY RESPONSE TRIGGERED: {incident.event_id}")
        # TODO: Integrate with ChatOps for immediate notification
    
    async def _trigger_critical_response(self, incident: IncidentEvent):
        """Trigger critical response actions"""
        logger.warning(f"[PROCESSOR] CRITICAL RESPONSE TRIGGERED: {incident.event_id}")
        # TODO: Integrate with ChatOps for critical incident management
    
    def _infer_severity(self, metric_event: RANMetricEvent) -> SeverityLevel:
        """Infer severity from metric values"""
        if metric_event.latency > 100 or metric_event.packet_loss > 5:
            return SeverityLevel.CRITICAL
        elif metric_event.latency > 50 or metric_event.packet_loss > 2:
            return SeverityLevel.WARNING
        return SeverityLevel.INFO
    
    def _classify_anomalies(self, metric_event: RANMetricEvent) -> list:
        """Classify anomaly types from metrics"""
        anomalies = []
        
        if metric_event.prb_usage > 85:
            anomalies.append(AnomalyType.CONGESTION)
        if metric_event.latency > 50:
            anomalies.append(AnomalyType.LATENCY)
        if metric_event.packet_loss > 1:
            anomalies.append(AnomalyType.PACKET_LOSS)
        if metric_event.throughput < 100:
            anomalies.append(AnomalyType.THROUGHPUT_DROP)
        
        return anomalies if anomalies else [AnomalyType.CONGESTION]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "open_incidents": len(self.incident_cache)
        }


# Global processor instance
event_processor: Optional[EventProcessor] = None


async def start_event_processor():
    """Start background event processor"""
    global event_processor
    event_processor = EventProcessor()
    logger.info("[PROCESSOR] Background event processor started")


async def stop_event_processor():
    """Stop background event processor"""
    global event_processor
    if event_processor:
        stats = event_processor.get_stats()
        logger.info(f"[PROCESSOR] Stopping with stats: {stats}")
