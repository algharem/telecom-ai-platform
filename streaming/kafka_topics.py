"""
Kafka Topics Configuration for Telecom AI Platform
"""

from dataclasses import dataclass
from typing import List


@dataclass
class KafkaTopics:
    """Kafka topic configuration"""
    
    # Real-time metrics from RAN
    RAN_METRICS = "ran-metrics"
    
    # Anomaly detection results
    ANOMALIES = "anomalies"
    
    # Incident notifications
    INCIDENTS = "incidents"
    
    # Recovery actions
    RECOVERY = "recovery-actions"
    
    # Predictions and forecasts
    FORECASTS = "forecasts"
    
    # ChatOps notifications
    NOTIFICATIONS = "notifications"
    
    @classmethod
    def get_all_topics(cls) -> List[str]:
        """Get all Kafka topics"""
        return [
            cls.RAN_METRICS,
            cls.ANOMALIES,
            cls.INCIDENTS,
            cls.RECOVERY,
            cls.FORECASTS,
            cls.NOTIFICATIONS,
        ]
    
    @classmethod
    def get_topic_config(cls) -> dict:
        """Get topic creation configuration"""
        return {
            cls.RAN_METRICS: {
                "partitions": 3,
                "replication_factor": 2,
                "retention_ms": 86400000,  # 24 hours
                "compression_type": "snappy",
            },
            cls.ANOMALIES: {
                "partitions": 2,
                "replication_factor": 2,
                "retention_ms": 604800000,  # 7 days
            },
            cls.INCIDENTS: {
                "partitions": 1,
                "replication_factor": 3,
                "retention_ms": 1209600000,  # 14 days
            },
            cls.RECOVERY: {
                "partitions": 1,
                "replication_factor": 2,
                "retention_ms": 86400000,  # 24 hours
            },
            cls.FORECASTS: {
                "partitions": 1,
                "replication_factor": 2,
                "retention_ms": 604800000,  # 7 days
            },
            cls.NOTIFICATIONS: {
                "partitions": 1,
                "replication_factor": 2,
                "retention_ms": 3600000,  # 1 hour (short-lived)
            },
        }
