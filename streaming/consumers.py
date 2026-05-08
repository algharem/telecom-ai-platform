"""
Kafka Consumers for Event Subscription
"""

import json
import logging
from typing import Callable, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from .kafka_topics import KafkaTopics

logger = logging.getLogger(__name__)


class BaseConsumer:
    """Base Kafka consumer with message handling"""
    
    def __init__(
        self,
        topic: str,
        group_id: str,
        bootstrap_servers: str = "localhost:9092",
        auto_offset_reset: str = "earliest",
    ):
        self.topic = topic
        self.group_id = group_id
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            session_timeout_ms=30000,
        )
    
    def start_consuming(self, callback: Callable):
        """Start consuming messages"""
        try:
            for message in self.consumer:
                try:
                    callback(message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except KafkaError as e:
            logger.error(f"Consumer error: {e}")
        finally:
            self.close()
    
    def close(self):
        """Close consumer"""
        self.consumer.close()


class AnomalyConsumer(BaseConsumer):
    """Consumes anomaly detection events"""
    
    def __init__(self, group_id: str = "anomaly-processor"):
        super().__init__(KafkaTopics.ANOMALIES, group_id)


class IncidentConsumer(BaseConsumer):
    """Consumes incident events"""
    
    def __init__(self, group_id: str = "incident-processor"):
        super().__init__(KafkaTopics.INCIDENTS, group_id)


class MetricConsumer(BaseConsumer):
    """Consumes RAN metric events"""
    
    def __init__(self, group_id: str = "metric-processor"):
        super().__init__(KafkaTopics.RAN_METRICS, group_id)


class RecoveryConsumer(BaseConsumer):
    """Consumes recovery action events"""
    
    def __init__(self, group_id: str = "recovery-processor"):
        super().__init__(KafkaTopics.RECOVERY, group_id)


class ForecastConsumer(BaseConsumer):
    """Consumes forecast events"""
    
    def __init__(self, group_id: str = "forecast-processor"):
        super().__init__(KafkaTopics.FORECASTS, group_id)
