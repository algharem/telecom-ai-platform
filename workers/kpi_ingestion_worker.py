"""
KPI Ingestion Worker - Subscribes to metrics and runs anomaly detection
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

from streaming.consumers import MetricConsumer
from streaming.producers import AnomalyProducer
from services.ml_detector import AnomalyDetector as MLAnomalyDetector
from services.anomaly_detector import AnomalyDetector as PatternAnomalyDetector
from models.events import AnomalyDetectedEvent
from models.schemas import KPIRecord

logger = logging.getLogger(__name__)


class KPIIngestionWorker:
    """Worker that processes incoming metrics and detects anomalies"""
    
    def __init__(
        self,
        ml_detector: MLAnomalyDetector,
        pattern_detector: PatternAnomalyDetector,
        kafka_bootstrap_servers: str = "localhost:9092",
    ):
        self.ml_detector = ml_detector
        self.pattern_detector = pattern_detector
        self.metric_consumer = MetricConsumer()
        self.anomaly_producer = AnomalyProducer(kafka_bootstrap_servers)
        self.metrics_processed = 0
        self.anomalies_detected = 0
    
    def process_metric(self, metric_dict: dict) -> Optional[AnomalyDetectedEvent]:
        """Process a single metric and detect anomalies"""
        try:
            # Convert dict to KPIRecord
            kpi = KPIRecord(
                timestamp=datetime.fromisoformat(metric_dict.get("timestamp", datetime.utcnow().isoformat())),
                gnb_id=metric_dict.get("gnb_id"),
                prb_usage=metric_dict.get("prb_usage"),
                throughput=metric_dict.get("throughput"),
                latency=metric_dict.get("latency"),
                packet_loss=metric_dict.get("packet_loss"),
                source="kafka",
            )
            
            self.metrics_processed += 1
            
            # Try ML detection first
            is_anomaly = False
            explanation = "Normal operation"
            anomaly_type = None
            
            if self.ml_detector.is_trained:
                # Use ML detector
                try:
                    ml_prediction = self.ml_detector.predict_single(kpi)
                    is_anomaly = ml_prediction.get("is_anomaly", False)
                    explanation = ml_prediction.get("explanation", "ML detection")
                    anomaly_type = ml_prediction.get("anomaly_type", "unknown")
                except Exception as e:
                    logger.warning(f"ML detection failed: {e}, falling back to pattern detection")
                    is_anomaly, explanation = self.pattern_detector.detect(kpi)
            else:
                # Use pattern detector
                is_anomaly, explanation = self.pattern_detector.detect(kpi)
            
            # Create anomaly event if detected
            if is_anomaly:
                self.anomalies_detected += 1
                
                anomaly_event = AnomalyDetectedEvent(
                    event_id=f"ANO-{self.metrics_processed}",
                    gnb_id=kpi.gnb_id,
                    timestamp=kpi.timestamp,
                    anomaly_type=anomaly_type or self._infer_anomaly_type(kpi),
                    severity=self._infer_severity(kpi),
                    details=explanation,
                    affected_metrics={
                        "prb_usage": kpi.prb_usage,
                        "throughput": kpi.throughput,
                        "latency": kpi.latency,
                        "packet_loss": kpi.packet_loss,
                    },
                    tags=["auto-detected"],
                )
                
                # Publish to Kafka
                self.anomaly_producer.send_anomaly(anomaly_event)
                logger.info(f"Anomaly detected: {anomaly_event.event_id}")
                
                return anomaly_event
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing metric: {e}")
            return None
    
    def _infer_anomaly_type(self, kpi: KPIRecord) -> str:
        """Infer anomaly type from KPI values"""
        if kpi.prb_usage > 90:
            return "resource_exhaustion"
        elif kpi.latency > 50:
            return "latency_spike"
        elif kpi.packet_loss > 5:
            return "packet_loss"
        elif kpi.throughput < 100:
            return "throughput_degradation"
        return "unknown"
    
    def _infer_severity(self, kpi: KPIRecord) -> str:
        """Infer severity from KPI values"""
        critical_conditions = sum([
            kpi.prb_usage > 95,
            kpi.latency > 100,
            kpi.packet_loss > 10,
            kpi.throughput < 50,
        ])
        
        if critical_conditions >= 3:
            return "CRITICAL"
        elif critical_conditions >= 2:
            return "MAJOR"
        elif any([
            kpi.prb_usage > 85,
            kpi.latency > 50,
            kpi.packet_loss > 5,
            kpi.throughput < 100,
        ]):
            return "MINOR"
        return "WARNING"
    
    def start(self):
        """Start the worker (blocking)"""
        logger.info("KPI Ingestion Worker started")
        self.metric_consumer.start_consuming(self.process_metric)
    
    async def start_async(self):
        """Start the worker (non-blocking, async)"""
        logger.info("KPI Ingestion Worker started (async)")
        while True:
            try:
                # Process metrics in a loop
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("KPI Ingestion Worker stopped")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def get_stats(self) -> dict:
        """Get worker statistics"""
        return {
            "metrics_processed": self.metrics_processed,
            "anomalies_detected": self.anomalies_detected,
            "anomaly_rate": (
                self.anomalies_detected / max(self.metrics_processed, 1) * 100
            ),
        }
