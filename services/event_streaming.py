"""
Phase 4: Event Streaming Service
Kafka producer/consumer for real-time event distribution
"""

import json
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class EventStreamingConfig:
    """Kafka configuration"""
    def __init__(self, 
                 bootstrap_servers: str = "localhost:9092",
                 metrics_topic: str = "ran-metrics",
                 anomalies_topic: str = "anomalies-detected",
                 alarms_topic: str = "network-alarms",
                 incidents_topic: str = "incidents",
                 recovery_topic: str = "recovery-actions",
                 recommendations_topic: str = "recommendations",
                 forecast_topic: str = "forecasts"):
        self.bootstrap_servers = bootstrap_servers.split(",")
        self.metrics_topic = metrics_topic
        self.anomalies_topic = anomalies_topic
        self.alarms_topic = alarms_topic
        self.incidents_topic = incidents_topic
        self.recovery_topic = recovery_topic
        self.recommendations_topic = recommendations_topic
        self.forecast_topic = forecast_topic


class EventProducer:
    """Kafka event producer for publishing events"""
    
    def __init__(self, config: EventStreamingConfig):
        self.config = config
        self.producer = None
        self.enabled = False
        logger.info("[PRODUCER] Event producer initialized")
    
    async def connect(self):
        """Connect to Kafka cluster"""
        try:
            from aiokafka import AIOKafkaProducer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            await self.producer.start()
            self.enabled = True
            logger.info(f"[PRODUCER] Connected to Kafka: {self.config.bootstrap_servers}")
        except ImportError:
            logger.warning("[PRODUCER] aiokafka not installed, events disabled")
        except Exception as e:
            logger.warning(f"[PRODUCER] Failed to connect to Kafka: {e}")
    
    async def publish_metric_event(self, event: Dict[str, Any]):
        """Publish RAN metric event"""
        if not self.enabled:
            logger.debug("[PRODUCER] Events disabled, skipping metric publish")
            return
        
        try:
            await self.producer.send_and_wait(
                self.config.metrics_topic,
                value=event
            )
            logger.debug(f"[PRODUCER] Published metric event: {event.get('event_id')}")
        except Exception as e:
            logger.error(f"[PRODUCER] Error publishing metric event: {e}")
    
    async def publish_anomaly_event(self, event: Dict[str, Any]):
        """Publish anomaly detected event"""
        if not self.enabled:
            return
        
        try:
            await self.producer.send_and_wait(
                self.config.anomalies_topic,
                value=event
            )
            logger.info(f"[PRODUCER] Published anomaly event: {event.get('event_id')}")
        except Exception as e:
            logger.error(f"[PRODUCER] Error publishing anomaly event: {e}")
    
    async def publish_incident_event(self, event: Dict[str, Any]):
        """Publish incident event"""
        if not self.enabled:
            return
        
        try:
            await self.producer.send_and_wait(
                self.config.incidents_topic,
                value=event
            )
            logger.info(f"[PRODUCER] Published incident event: {event.get('event_id')}")
        except Exception as e:
            logger.error(f"[PRODUCER] Error publishing incident event: {e}")
    
    async def publish_recovery_event(self, event: Dict[str, Any]):
        """Publish recovery action event"""
        if not self.enabled:
            return
        
        try:
            await self.producer.send_and_wait(
                self.config.recovery_topic,
                value=event
            )
            logger.info(f"[PRODUCER] Published recovery event: {event.get('event_id')}")
        except Exception as e:
            logger.error(f"[PRODUCER] Error publishing recovery event: {e}")
    
    async def publish_recommendation_event(self, event: Dict[str, Any]):
        """Publish recommendation event"""
        if not self.enabled:
            return
        
        try:
            await self.producer.send_and_wait(
                self.config.recommendations_topic,
                value=event
            )
            logger.info(f"[PRODUCER] Published recommendation event: {event.get('event_id')}")
        except Exception as e:
            logger.error(f"[PRODUCER] Error publishing recommendation event: {e}")
    
    async def close(self):
        """Disconnect from Kafka"""
        if self.producer:
            await self.producer.stop()
            logger.info("[PRODUCER] Disconnected from Kafka")


class EventConsumer:
    """Kafka event consumer for subscribing to events"""
    
    def __init__(self, config: EventStreamingConfig, group_id: str):
        self.config = config
        self.group_id = group_id
        self.consumer = None
        self.enabled = False
        logger.info(f"[CONSUMER] Event consumer initialized: {group_id}")
    
    async def connect(self, topics: list):
        """Connect to Kafka and subscribe to topics"""
        try:
            from aiokafka import AIOKafkaConsumer
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest'
            )
            await self.consumer.start()
            self.enabled = True
            logger.info(f"[CONSUMER] Connected to Kafka topics: {topics}")
        except ImportError:
            logger.warning("[CONSUMER] aiokafka not installed")
        except Exception as e:
            logger.warning(f"[CONSUMER] Failed to connect: {e}")
    
    async def consume_events(self, callback: Callable):
        """Consume events and call callback"""
        if not self.enabled:
            return
        
        try:
            async for msg in self.consumer:
                try:
                    await callback(msg.value)
                except Exception as e:
                    logger.error(f"[CONSUMER] Error processing event: {e}")
        except asyncio.CancelledError:
            logger.info("[CONSUMER] Consumer stopped")
        except Exception as e:
            logger.error(f"[CONSUMER] Error consuming events: {e}")
    
    async def close(self):
        """Disconnect from Kafka"""
        if self.consumer:
            await self.consumer.stop()
            logger.info("[CONSUMER] Disconnected from Kafka")


# Global instances
event_producer: Optional[EventProducer] = None
event_consumer: Optional[EventConsumer] = None


async def initialize_event_streaming(config: EventStreamingConfig):
    """Initialize event streaming infrastructure"""
    global event_producer, event_consumer
    
    event_producer = EventProducer(config)
    await event_producer.connect()
    
    logger.info("[STREAMING] Event streaming initialized")


async def shutdown_event_streaming():
    """Shutdown event streaming"""
    global event_producer, event_consumer
    
    if event_producer:
        await event_producer.close()
    if event_consumer:
        await event_consumer.close()
    
    logger.info("[STREAMING] Event streaming shutdown complete")
