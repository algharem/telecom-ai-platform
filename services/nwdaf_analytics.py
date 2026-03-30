import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
import logging

from models.schemas import (
    KPIMetrics,
    NetworkElementType,
    AnalyticsType,
    AnomalyResult
)
from services.kpi_simulator import TelecomKPISimulator
from services.ml_detector import AnomalyDetector
from utils.time_series import TimeSeriesAnalyzer, ForecastingEngine
from utils.exceptions import SubscriptionNotFoundException, AnalyticsNotSupportedException
from infrastructure.database import InMemoryTimeSeriesDB, TimeSeriesRecord


logger = logging.getLogger(__name__)


@dataclass
class AnalyticsSubscription:
    """
    3GPP TS 29.520 compliant subscription.
    Represents an NF (AMF, SMF, etc.) subscribing to analytics.
    """
    subscription_id: str
    nf_type: str                    # "AMF", "SMF", "PCF", "AF"
    nf_instance_id: str
    analytics_type: AnalyticsType
    target_gnbs: List[str]
    reporting_threshold: Optional[float] = None
    reporting_window_minutes: int = 5
    notification_uri: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_notification: Optional[datetime] = None
    notification_count: int = 0
    
    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        """Check if subscription expired"""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > ttl_seconds


@dataclass
class LoadLevelAnalytics:
    """NWDAF Load Level Information analytics output"""
    gnb_id: str
    load_level: int                 # 0-100 scale
    confidence: float
    trend_direction: str            # "increasing", "decreasing", "stable"
    forecast_24h: List[float]
    peak_hours_predicted: List[int]
    congestion_probability: float     # 0-1


@dataclass
class ServiceExperienceAnalytics:
    """NWDAF Service Experience analytics"""
    gnb_id: str
    predicted_mos: float            # Mean Opinion Score 1-5
    throughput_experience: str      # "good", "fair", "poor"
    latency_experience: str
    confidence: float


class NWDAFAnalyticsEngine:
    """
    3GPP NWDAF Network Data Analytics Function implementation.
    
    Provides:
    - Load Level Analytics (congestion prediction)
    - Service Experience (QoS prediction)
    - Anomaly Event exposure
    - Subscription management for NFs
    """
    
    def __init__(self, 
                 detector: AnomalyDetector,
                 simulator: TelecomKPISimulator):
        self.detector = detector
        self.simulator = simulator
        self.db = InMemoryTimeSeriesDB()  # Use InfluxDB in production
        self.subscriptions: Dict[str, AnalyticsSubscription] = {}
        self.analytics_cache: Dict[str, Dict] = {}
        self.notification_callbacks: Dict[str, Callable] = {}
        
        # Background task for subscription management
        self._cleanup_task = None
        
        logger.info("NWDAF Analytics Engine initialized")
    
    async def start(self):
        """Start background tasks"""
        self._cleanup_task = asyncio.create_task(self._subscription_cleanup_loop())
        logger.info("NWDAF background tasks started")
    
    async def stop(self):
        """Graceful shutdown"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("NWDAF stopped")
    
    # ==========================================
    # 3GPP Nnwdaf_AnalyticsInfo Operations
    # ==========================================
    
    async def subscribe(self,
                       nf_type: str,
                       nf_instance_id: str,
                       analytics_type: AnalyticsType,
                       target_gnbs: List[str],
                       notification_uri: str,
                       reporting_threshold: Optional[float] = None) -> str:
        """
        Nnwdaf_AnalyticsSubscription_Subscribe service operation.
        
        Allows NFs to subscribe to network analytics updates.
        """
        subscription_id = str(uuid.uuid4())
        
        sub = AnalyticsSubscription(
            subscription_id=subscription_id,
            nf_type=nf_type,
            nf_instance_id=nf_instance_id,
            analytics_type=analytics_type,
            target_gnbs=target_gnbs,
            notification_uri=notification_uri,
            reporting_threshold=reporting_threshold
        )
        
        self.subscriptions[subscription_id] = sub
        
        logger.info(
            f"New subscription: {subscription_id} from {nf_type} "
            f"for {analytics_type.value} on {target_gnbs}"
        )
        
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Nnwdaf_AnalyticsSubscription_Unsubscribe"""
        if subscription_id not in self.subscriptions:
            raise SubscriptionNotFoundException(subscription_id)
        
        del self.subscriptions[subscription_id]
        logger.info(f"Subscription {subscription_id} removed")
        return True
    
    async def get_analytics(self,
                           analytics_type: AnalyticsType,
                           target_gnb: str,
                           time_window_hours: int = 24) -> Dict:
        """
        Nnwdaf_AnalyticsInfo_Request service operation.
        
        Provides on-demand analytics for a specific network element.
        """
        if analytics_type == AnalyticsType.LOAD_LEVEL:
            return await self._calculate_load_level(target_gnb, time_window_hours)
        
        elif analytics_type == AnalyticsType.SERVICE_EXPERIENCE:
            return await self._calculate_service_experience(target_gnb, time_window_hours)
        
        elif analytics_type == AnalyticsType.ANOMALY_EVENTS:
            return await self._get_anomaly_summary(target_gnb, time_window_hours)
        
        else:
            raise AnalyticsNotSupportedException(analytics_type.value)
    
    # ==========================================
    # Analytics Calculation Methods
    # ==========================================
    # In services/nwdaf_analytics.py, the issue is here:

    async def _calculate_load_level(self,
                                gnb_id: str,
                                hours: int = 24) -> LoadLevelAnalytics:
        # ...
        # Fetch PRB usage history
        df = await self.db.query_range(gnb_id, 'prb_usage', start, end)
        
        if df.empty:
            # Generate synthetic data if no history
            logger.warning(f"No data for {gnb_id}, using simulation")
            # BUG: This passes hours=1 implicitly through the default parameter
            # But actually looking at the code, it passes hours=hours which is 1 from the call
            sim_data = self.simulator.generate_training_data(hours=hours, base_stations=1)

    async def _calculate_load_level2(self,
                                    gnb_id: str,
                                    hours: int = 24) -> LoadLevelAnalytics:
        """
        Calculate Load Level Information per 3GPP TS 28.554.
        
        Load Level represents resource utilization (0-100 scale).
        Used by AMF for load balancing and SMF for session management.
        """
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)
        
        # Fetch PRB usage history
        df = await self.db.query_range(gnb_id, 'prb_usage', start, end)
        
        if df.empty:
            # Generate synthetic data if no history
            logger.warning(f"No data for {gnb_id}, using simulation")
            sim_data = self.simulator.generate_training_data(hours=hours, base_stations=1)
            df = sim_data[sim_data['gNB'] == gnb_id][['timestamp', 'prb_usage']].copy()
            df = df.rename(columns={'prb_usage': 'value'})
            df = df.set_index('timestamp')
        
        # Calculate current load level (percentile-based for stability)
        if len(df) > 0:
            load_level = int(df['value'].quantile(0.90))  # Use 90th percentile
            load_level = max(0, min(100, load_level))
        else:
            load_level = 50  # Default
        
        # Trend analysis
        trend = TimeSeriesAnalyzer.calculate_trend(df['value'] if len(df) > 10 else pd.Series([50]))
        
        # Forecast next 24h
        forecast_result = ForecastingEngine.forecast_with_confidence(
            df['value'] if len(df) > 10 else pd.Series([50, 55, 52]),
            horizon=24
        )
        
        # Predict peak hours (simple heuristic: find hours with forecast > 80)
        peak_hours = [i for i, v in enumerate(forecast_result['forecast']) if v > 80]
        # Convert to actual hours (assume starting from now)
        current_hour = datetime.utcnow().hour
        peak_hours = [(current_hour + h) % 24 for h in peak_hours[:3]]
        
        # Congestion probability (based on forecast exceeding threshold)
        threshold = 85
        exceed_count = sum(1 for v in forecast_result['forecast'] if v > threshold)
        congestion_prob = exceed_count / 24.0
        
        return LoadLevelAnalytics(
            gnb_id=gnb_id,
            load_level=load_level,
            confidence=0.85 if len(df) > 20 else 0.60,
            trend_direction=trend['direction'],
            forecast_24h=forecast_result['forecast'][:12],  # Return first 12h
            peak_hours_predicted=peak_hours,
            congestion_probability=round(congestion_prob, 2)
        )
    
    async def _calculate_service_experience(self,
                                            gnb_id: str,
                                            hours: int = 24) -> ServiceExperienceAnalytics:
        """
        Predict service experience (MOS score) based on network metrics.
        
        Uses empirical formula: MOS = f(throughput, latency, packet_loss)
        """
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)
        
        # Get all metrics
        df = await self.db.get_all_metrics(gnb_id, start, end)
        
        if df.empty or len(df) < 5:
            # Use simulation
            sim_data = self.simulator.generate_training_data(hours=6, base_stations=1)
            metrics = {
                'throughput': sim_data['throughput_mbps'].mean(),
                'latency': sim_data['latency_ms'].mean(),
                'packet_loss': sim_data['packet_loss_percent'].mean()
            }
        else:
            metrics = {
                'throughput': df['throughput'].mean(),
                'latency': df['latency'].mean(),
                'packet_loss': df['packet_loss'].mean()
            }
        
        # Calculate MOS using E-model inspired formula
        # Simplified: base MOS reduced by impairment factors
        base_mos = 4.5
        
        # Throughput factor (diminishing returns above 50Mbps)
        if metrics['throughput'] < 10:
            throughput_factor = -1.5
        elif metrics['throughput'] < 50:
            throughput_factor = -0.5
        else:
            throughput_factor = 0
        
        # Latency factor (critical for voice/gaming)
        if metrics['latency'] > 100:
            latency_factor = -1.0
        elif metrics['latency'] > 50:
            latency_factor = -0.5
        else:
            latency_factor = 0
        
        # Packet loss factor (linear impact)
        loss_factor = -metrics['packet_loss'] * 0.5
        
        predicted_mos = max(1.0, min(5.0, base_mos + throughput_factor + latency_factor + loss_factor))
        
        # Determine experience categories
        throughput_exp = "poor" if metrics['throughput'] < 10 else "fair" if metrics['throughput'] < 50 else "good"
        latency_exp = "poor" if metrics['latency'] > 100 else "fair" if metrics['latency'] > 50 else "good"
        
        # Confidence based on data volume
        confidence = min(0.95, 0.5 + len(df) * 0.01) if not df.empty else 0.5
        
        return ServiceExperienceAnalytics(
            gnb_id=gnb_id,
            predicted_mos=round(predicted_mos, 2),
            throughput_experience=throughput_exp,
            latency_experience=latency_exp,
            confidence=round(confidence, 2)
        )
    
    async def _get_anomaly_summary(self,
                                   gnb_id: str,
                                   hours: int = 24) -> Dict:
        """Get summary of anomalies detected in time window"""
        # This would query anomaly events from database
        # For now, return simulated summary
        return {
            "gNB": gnb_id,
            "period_hours": hours,
            "total_anomalies": 3,
            "anomaly_types": ["congestion", "latency_spike"],
            "severity_breakdown": {"critical": 1, "warning": 2},
            "trend": "decreasing"
        }
    
    # ==========================================
    # Data Ingestion from Phase 1
    # ==========================================
    
    async def ingest_kpi(self,
                        gnb_id: str,
                        metrics: KPIMetrics,
                        timestamp: Optional[datetime] = None):
        """
        Ingest KPI from Phase 1 detector into time-series DB.
        Enables historical analytics.
        """
        ts = timestamp or datetime.utcnow()
        
        # Store each metric
        records = [
            TimeSeriesRecord(ts, gnb_id, 'prb_usage', metrics.prb_usage, {}),
            TimeSeriesRecord(ts, gnb_id, 'throughput', metrics.throughput, {}),
            TimeSeriesRecord(ts, gnb_id, 'latency', metrics.latency, {}),
            TimeSeriesRecord(ts, gnb_id, 'packet_loss', metrics.packet_loss, {}),
        ]
        
        for record in records:
            await self.db.write_kpi(record)
        
        # Check subscriptions for notification triggers
        await self._check_notification_triggers(gnb_id, metrics)
    
    async def _check_notification_triggers(self, gnb_id: str, metrics: KPIMetrics):
        """Check if any subscription thresholds are breached"""
        for sub_id, sub in self.subscriptions.items():
            if gnb_id not in sub.target_gnbs:
                continue
            
            should_notify = False
            reason = ""
            
            if sub.analytics_type == AnalyticsType.LOAD_LEVEL:
                if metrics.prb_usage > (sub.reporting_threshold or 80):
                    should_notify = True
                    reason = f"PRB usage {metrics.prb_usage}% exceeds threshold"
            
            elif sub.analytics_type == AnalyticsType.ANOMALY_EVENTS:
                # Use Phase 1 detector
                from models.schemas import PredictionRequest
                request = PredictionRequest(gnb_id=gnb_id, metrics=metrics)
                result = self.detector.predict(request)
                if result.is_anomaly:
                    should_notify = True
                    reason = result.explanation
            
            if should_notify:
                await self._send_notification(sub, gnb_id, reason)
    
    async def _send_notification(self, sub: AnalyticsSubscription, gnb_id: str, reason: str):
        """Send HTTP notification to subscribed NF"""
        import httpx
        
        payload = {
            "subscription_id": sub.subscription_id,
            "notification_type": sub.analytics_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "target_gnb": gnb_id,
            "reason": reason,
            "analytics": await self.get_analytics(sub.analytics_type, gnb_id, hours=1)
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(sub.notification_uri, json=payload, timeout=5.0)
            
            sub.last_notification = datetime.utcnow()
            sub.notification_count += 1
            
            logger.info(f"Notification sent to {sub.notification_uri} for {gnb_id}")
            
        except Exception as e:
            logger.error(f"Failed to notify {sub.notification_uri}: {e}")
    
    async def _subscription_cleanup_loop(self):
        """Background task to clean expired subscriptions"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                expired = [
                    sid for sid, sub in self.subscriptions.items()
                    if sub.is_expired()
                ]
                
                for sid in expired:
                    del self.subscriptions[sid]
                    logger.info(f"Cleaned expired subscription {sid}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def get_subscription_stats(self) -> Dict:
        """Admin statistics"""
        return {
            "active_subscriptions": len(self.subscriptions),
            "by_nf_type": self._count_by_nf_type(),
            "by_analytics_type": self._count_by_analytics_type(),
            "total_notifications": sum(s.notification_count for s in self.subscriptions.values())
        }
    
    def _count_by_nf_type(self) -> Dict:
        counts = {}
        for sub in self.subscriptions.values():
            counts[sub.nf_type] = counts.get(sub.nf_type, 0) + 1
        return counts
    
    def _count_by_analytics_type(self) -> Dict:
        counts = {}
        for sub in self.subscriptions.values():
            key = sub.analytics_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts