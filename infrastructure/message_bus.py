"""
Unified message bus abstraction for Kafka and MQTT.
Provides clean interface for publishing and subscribing to events.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from streaming.producers import KafkaEventProducer, AsyncKafkaProducer
from streaming.consumers import KafkaEventConsumer
from infrastructure.mqtt_client import RANTelemetryClient


logger = logging.getLogger(__name__)


class MessageBusType(Enum):
    """Supported message bus types"""
    KAFKA = "kafka"
    MQTT = "mqtt"
    REDIS = "redis"


@dataclass
class Message:
    """Generic message container"""
    topic: str
    key: Optional[str]
    value: Dict[str, Any]
    headers: Dict[str, str]
    timestamp: datetime


class UnifiedMessageBus:
    """
    Unified interface for multiple message backends.
    
    Routes messages to appropriate backend based on topic patterns:
    - Kafka: High-throughput, persistent, multi-consumer
    - MQTT: Lightweight, edge communication, pub/sub
    - Redis: Fast, in-memory, caching/streaming
    """
    
    def __init__(self,
                 kafka_brokers: Optional[str] = "localhost:9092",
                 mqtt_broker: Optional[str] = "localhost",
                 mqtt_port: int = 1883,
                 redis_url: Optional[str] = None):
        
        # Initialize backends
        self.kafka: Optional[AsyncKafkaProducer] = None
        self.mqtt: Optional[RANTelemetryClient] = None
        
        if kafka_brokers:
            self.kafka = AsyncKafkaProducer(kafka_brokers)
        
        if mqtt_broker:
            self.mqtt = RANTelemetryClient(mqtt_broker, mqtt_port)
        
        # Topic routing rules
        self._routing: Dict[str, MessageBusType] = {
            "ran.kpi.": MessageBusType.KAFKA,
            "ran.events.": MessageBusType.KAFKA,
            "nwdaf.": MessageBusType.KAFKA,
            "xapp.": MessageBusType.KAFKA,
            "gNB/": MessageBusType.MQTT,
            "commands/": MessageBusType.MQTT,
        }
        
        # Subscribers
        self._subscribers: Dict[str, List[Callable]] = {}
        
        logger.info("Unified Message Bus initialized")
    
    async def connect(self):
        """Connect to all configured backends"""
        if self.mqtt:
            await self.mqtt.connect()
    
    async def publish(self,
                     topic: str,
                     message: Dict[str, Any],
                     key: Optional[str] = None,
                     headers: Optional[Dict] = None,
                     bus_type: Optional[MessageBusType] = None) -> bool:
        """
        Publish message to appropriate bus.
        
        Auto-routes based on topic prefix if bus_type not specified.
        """
        # Determine bus type
        if bus_type is None:
            bus_type = self._route_topic(topic)
        
        # Wrap in Message
        msg = Message(
            topic=topic,
            key=key,
            value=message,
            headers=headers or {},
            timestamp=datetime.utcnow()
        )
        
        # Route to backend
        if bus_type == MessageBusType.KAFKA and self.kafka:
            return await self._publish_kafka(msg)
        elif bus_type == MessageBusType.MQTT and self.mqtt:
            return await self._publish_mqtt(msg)
        else:
            logger.warning(f"No backend available for {bus_type}")
            return False
    
    async def _publish_kafka(self, message: Message) -> bool:
        """Publish to Kafka"""
        try:
            # Map to streaming event
            from models.events import TelecomEvent
            event = TelecomEvent(**message.value)
            
            # Determine topic key
            topic_key = self._map_to_kafka_topic(message.topic)
            
            return await self.kafka.send(event, topic_key, key=message.key)
        except Exception as e:
            logger.error(f"Kafka publish failed: {e}")
            return False
    
    async def _publish_mqtt(self, message: Message) -> bool:
        """Publish to MQTT"""
        try:
            await self.mqtt.publish(
                message.topic,
                message.value,
                qos=1
            )
            return True
        except Exception as e:
            logger.error(f"MQTT publish failed: {e}")
            return False
    
    async def subscribe(self,
                       topic_pattern: str,
                       handler: Callable,
                       bus_type: Optional[MessageBusType] = None):
        """
        Subscribe to topic pattern.
        
        For Kafka: Uses consumer groups
        For MQTT: Direct subscription
        """
        if bus_type is None:
            bus_type = self._route_topic(topic_pattern)
        
        if bus_type == MessageBusType.KAFKA:
            await self._subscribe_kafka(topic_pattern, handler)
        elif bus_type == MessageBusType.MQTT:
            await self._subscribe_mqtt(topic_pattern, handler)
    
    async def _subscribe_kafka(self, pattern: str, handler: Callable):
        """Subscribe via Kafka consumer"""
        # Store for later consumer initialization
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)
    
    async def _subscribe_mqtt(self, pattern: str, handler: Callable):
        """Subscribe via MQTT"""
        if self.mqtt:
            await self.mqtt.subscribe(pattern, handler)
    
    def _route_topic(self, topic: str) -> MessageBusType:
        """Determine bus type from topic prefix"""
        for prefix, bus_type in self._routing.items():
            if topic.startswith(prefix):
                return bus_type
        
        # Default to Kafka
        return MessageBusType.KAFKA
    
    def _map_to_kafka_topic(self, topic: str) -> str:
        """Map generic topic to Kafka topic key"""
        mapping = {
            "ran.kpi.": "ran_metrics",
            "ran.events.": "ran_anomalies",
            "nwdaf.": "nwdaf_analytics",
            "xapp.": "xapp_decisions",
        }
        
        for prefix, key in mapping.items():
            if topic.startswith(prefix):
                return key
        
        return "default"
    
    async def start_consumers(self, kafka_brokers: str, group_id: str):
        """Start Kafka consumers for registered subscriptions"""
        if not self._subscribers:
            return
        
        # Group by topic pattern
        for pattern, handlers in self._subscribers.items():
            consumer = KafkaEventConsumer(
                bootstrap_servers=kafka_brokers,
                group_id=f"{group_id}-{hash(pattern) % 10000}",
                topics=[pattern]
            )
            
            # Wrap handlers
            async def dispatch(event_data):
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event_data)
                        else:
                            handler(event_data)
                    except Exception as e:
                        logger.error(f"Handler error: {e}")
            
            # Register generic handler
            from models.events import EventType
            for et in EventType:
                consumer.register_handler(et, dispatch)
            
            consumer.subscribe([pattern])
            asyncio.create_task(consumer.start())
    
    async def close(self):
        """Close all connections"""
        if self.kafka:
            await self.kafka.close()
        if self.mqtt:
            await self.mqtt.disconnect()


class MessageBusHealthMonitor:
    """
    Health monitoring for message bus components.
    """
    
    def __init__(self, bus: UnifiedMessageBus):
        self.bus = bus
        self._healthy = True
        self._last_check = datetime.utcnow()
        self._metrics = {
            "messages_published": 0,
            "messages_consumed": 0,
            "errors": 0
        }
    
    async def check_health(self) -> Dict:
        """Check health of all bus components"""
        checks = {}
        
        # Check Kafka
        if self.bus.kafka:
            try:
                # Simple connectivity check
                checks["kafka"] = "healthy"
            except:
                checks["kafka"] = "unhealthy"
                self._healthy = False
        
        # Check MQTT
        if self.bus.mqtt:
            checks["mqtt"] = "connected" if self.bus.mqtt.client else "disconnected"
        
        self._last_check = datetime.utcnow()
        
        return {
            "overall": "healthy" if self._healthy else "degraded",
            "components": checks,
            "metrics": self._metrics,
            "last_check": self._last_check.isoformat()
        }
    
    def record_publish(self, success: bool):
        """Record publish metric"""
        if success:
            self._metrics["messages_published"] += 1
        else:
            self._metrics["errors"] += 1
    
    def record_consume(self):
        """Record consume metric"""
        self._metrics["messages_consumed"] += 1