"""
Kafka producer for streaming parsed Open5GS events.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class KafkaLogProducer:
    """
    Produce parsed Open5GS events to Kafka topics.
    
    Features:
    - Async production
    - Topic routing by event type
    - Key-based partitioning
    - Error handling and retries
    """
    
    # Topic mapping
    TOPIC_MAPPING = {
        'amf': 'open5gs_amf_events',
        'smf': 'open5gs_smf_events',
        'upf': 'open5gs_upf_events',
        'pcf': 'open5gs_pcf_events',
        'nrf': 'open5gs_nrf_events',
    }
    
    KPI_TOPIC = 'open5gs_kpi_metrics'
    RAW_TOPIC = 'open5gs_raw_events'
    
    def __init__(self,
                 bootstrap_servers: str = 'localhost:9092',
                 client_id: str = 'open5gs-importer',
                 max_retries: int = 3,
                 retry_delay: float = 1.0):
        """
        Initialize Kafka producer.
        
        Args:
            bootstrap_servers: Kafka broker addresses
            client_id: Client identifier
            max_retries: Maximum send retries
            retry_delay: Delay between retries in seconds
        """
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self._producer = None
        self._initialized = False
        self._send_count = 0
        self._error_count = 0
    
    async def initialize(self):
        """Initialize Kafka producer"""
        try:
            import aiokafka
            self._producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                enable_idempotence=True,
                acks='all'
            )
            await self._producer.start()
            self._initialized = True
            logger.info(f"Kafka producer connected to {self.bootstrap_servers}")
        except ImportError:
            logger.warning("aiokafka not installed, Kafka production disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
    
    async def send_event(self, 
                         event_data: Dict[str, Any],
                         nf_type: str,
                         key: Optional[str] = None):
        """
        Send parsed event to appropriate topic.
        
        Args:
            event_data: Event data dictionary
            nf_type: Network function type
            key: Partition key (e.g., IMSI, gNB ID)
        """
        if not self._initialized:
            return
        
        topic = self.TOPIC_MAPPING.get(nf_type.lower(), self.RAW_TOPIC)
        await self._send_with_retry(topic, event_data, key)
    
    async def send_kpi(self,
                       kpi_data: Dict[str, Any],
                       key: Optional[str] = None):
        """
        Send KPI metric to KPI topic.
        
        Args:
            kpi_data: KPI data dictionary
            key: Partition key
        """
        if not self._initialized:
            return
        
        await self._send_with_retry(self.KPI_TOPIC, kpi_data, key)
    
    async def send_raw(self,
                       raw_event: Dict[str, Any],
                       nf_type: str,
                       key: Optional[str] = None):
        """
        Send raw event to raw topic.
        
        Args:
            raw_event: Raw event data
            nf_type: Network function type
            key: Partition key
        """
        if not self._initialized:
            return
        
        await self._send_with_retry(self.RAW_TOPIC, raw_event, key)
    
    async def _send_with_retry(self,
                                topic: str,
                                value: Dict[str, Any],
                                key: Optional[str]):
        """Send message with retry logic"""
        for attempt in range(self.max_retries):
            try:
                await self._producer.send_and_wait(topic, value=value, key=key)
                self._send_count += 1
                return
            except Exception as e:
                self._error_count += 1
                if attempt < self.max_retries - 1:
                    logger.warning(f"Kafka send error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"Kafka send failed after {self.max_retries} attempts: {e}")
    
    async def flush(self):
        """Flush pending messages"""
        if self._producer and self._initialized:
            await self._producer.flush()
    
    async def close(self):
        """Close producer"""
        if self._producer and self._initialized:
            await self._producer.stop()
            self._initialized = False
            logger.info("Kafka producer closed")
    
    def get_stats(self) -> Dict:
        """Get producer statistics"""
        return {
            'initialized': self._initialized,
            'messages_sent': self._send_count,
            'errors': self._error_count,
            'error_rate': self._error_count / (self._send_count + self._error_count) 
                         if (self._send_count + self._error_count) > 0 else 0
        }
