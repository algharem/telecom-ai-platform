"""
Kafka Producers for Event Publishing
"""

import json
import logging
from typing import Optional
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

from models.events import (
    RANMetricEvent,
    AnomalyDetectedEvent,
    IncidentEvent,
    RecoveryEvent,
    ForecastEvent,
)
from .kafka_topics import KafkaTopics

logger = logging.getLogger(__name__)


class BaseProducer:
    """Base Kafka producer with error handling"""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            acks="all",
            retries=3,
            compression_type="snappy",
        )
    
    def send(self, topic: str, value: dict, key: Optional[str] = None):
        """Send message to Kafka topic"""
        try:
            future = self.producer.send(topic, value=value, key=key.encode() if key else None)
            future.get(timeout=10)
            logger.debug(f"Message sent to {topic}")
        except KafkaError as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            raise
    
    def flush(self):
        """Flush pending messages"""
        self.producer.flush()
    
    def close(self):
        """Close producer"""
        self.producer.close()


class MetricProducer(BaseProducer):
    """Produces RAN metrics events"""
    
    def send_metric(self, event: RANMetricEvent):
        """Send RAN metric event"""
        self.send(
            KafkaTopics.RAN_METRICS,
            value=event.dict(),
            key=event.gnb_id
        )


class AnomalyProducer(BaseProducer):
    """Produces anomaly detection events"""
    
    def send_anomaly(self, event: AnomalyDetectedEvent):
        """Send anomaly event"""
        self.send(
            KafkaTopics.ANOMALIES,
            value=event.dict(),
            key=event.gnb_id
        )


class IncidentProducer(BaseProducer):
    """Produces incident events"""
    
    def send_incident(self, event: IncidentEvent):
        """Send incident event"""
        self.send(
            KafkaTopics.INCIDENTS,
            value=event.dict(),
            key=event.incident_id
        )


class RecoveryProducer(BaseProducer):
    """Produces recovery action events"""
    
    def send_recovery(self, event: RecoveryEvent):
        """Send recovery action event"""
        self.send(
            KafkaTopics.RECOVERY,
            value=event.dict(),
            key=event.incident_id
        )


class ForecastProducer(BaseProducer):
    """Produces forecast events"""
    
    def send_forecast(self, event: ForecastEvent):
        """Send forecast event"""
        self.send(
            KafkaTopics.FORECASTS,
            value=event.dict(),
            key=event.gnb_id
        )
