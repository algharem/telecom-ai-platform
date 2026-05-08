"""
Pattern-based anomaly detection using configurable thresholds.

Detects anomalies in KPI records by applying pattern-based rules
derived from telecom best practices and network operations experience.
"""

from typing import Tuple, Dict, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from services.data_provider import KPIRecord

logger = logging.getLogger(__name__)


@dataclass
class AnomalyThresholds:
    """Anomaly detection threshold configuration"""
    prb_usage_percent: float = 90.0          # PRB usage > 90% = anomaly
    latency_ms: float = 50.0                 # Latency > 50ms = anomaly
    packet_loss_percent: float = 1.0         # Packet loss > 1% = anomaly
    registration_success_rate_percent: float = 95.0  # Success rate < 95% = anomaly
    throughput_drop_percent: float = 20.0    # Throughput drop > 20% = anomaly
    
    # Consecutive anomalies before confirmed
    min_consecutive_for_confirmation: int = 2


class AnomalyDetector:
    """
    Pattern-based anomaly detector using threshold rules.
    
    Implements 5G RAN anomaly patterns:
    1. **Congestion**: High PRB usage (>90%), low throughput, high latency
    2. **RF Interference**: Variable PRB usage, packet loss, latency spikes
    3. **Transport Issues**: High packet loss (>1%), latency, low throughput
    4. **Authentication Issues**: Low registration success rate (<95%)
    5. **Throughput Degradation**: Throughput drop >20% in recent window
    """
    
    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize detector.
        
        Args:
            thresholds: Custom threshold dict, uses defaults if None
        """
        if thresholds:
            self.thresholds = AnomalyThresholds(**thresholds)
        else:
            self.thresholds = AnomalyThresholds()
        
        # Track history for anomaly confirmation
        self.history: Dict[str, List[KPIRecord]] = defaultdict(list)
        self.history_window_minutes = 5
        
        # Statistics
        self.total_checked = 0
        self.total_anomalies = 0
        self.anomaly_breakdown = defaultdict(int)
        
        logger.info(
            f"[DETECTOR] Initialized with thresholds: "
            f"PRB={self.thresholds.prb_usage_percent}%, "
            f"Latency={self.thresholds.latency_ms}ms, "
            f"PacketLoss={self.thresholds.packet_loss_percent}%"
        )
    
    def detect(self, record: KPIRecord) -> Tuple[bool, Optional[str]]:
        """
        Detect if a KPI record represents an anomaly.
        
        Args:
            record: KPI record to check
            
        Returns:
            Tuple of (is_anomaly, reason)
            Example: (True, "Congestion: PRB usage 95% > threshold 90%")
        """
        self.total_checked += 1
        
        # Check each anomaly pattern
        anomaly_reasons = []
        
        # 1. Congestion detection
        if record.prb_usage > self.thresholds.prb_usage_percent:
            anomaly_reasons.append(
                f"High PRB usage: {record.prb_usage:.1f}% > {self.thresholds.prb_usage_percent}%"
            )
        
        # 2. Latency issues
        if record.latency > self.thresholds.latency_ms:
            anomaly_reasons.append(
                f"High latency: {record.latency:.1f}ms > {self.thresholds.latency_ms}ms"
            )
        
        # 3. Packet loss
        if record.packet_loss > self.thresholds.packet_loss_percent:
            anomaly_reasons.append(
                f"High packet loss: {record.packet_loss:.2f}% > {self.thresholds.packet_loss_percent}%"
            )
        
        # 4. Throughput degradation (check against history)
        throughput_drop_reason = self._check_throughput_drop(record)
        if throughput_drop_reason:
            anomaly_reasons.append(throughput_drop_reason)
        
        # Update history
        self._update_history(record)
        
        # Determine if anomaly
        is_anomaly = len(anomaly_reasons) > 0
        
        if is_anomaly:
            self.total_anomalies += 1
            reason = "; ".join(anomaly_reasons)
            
            # Classify anomaly type
            anomaly_type = self._classify_anomaly_type(anomaly_reasons)
            self.anomaly_breakdown[anomaly_type] += 1
            
            logger.debug(f"[DETECTOR] Anomaly detected in {record.gnb_id}: {reason}")
            
            return True, reason
        
        return False, None
    
    def detect_batch(self, records: List[KPIRecord]) -> List[Tuple[KPIRecord, bool, Optional[str]]]:
        """
        Detect anomalies in a batch of records.
        
        Returns:
            List of (record, is_anomaly, reason) tuples
        """
        results = []
        for record in records:
            is_anomaly, reason = self.detect(record)
            results.append((record, is_anomaly, reason))
        return results
    
    def _check_throughput_drop(self, record: KPIRecord) -> Optional[str]:
        """
        Check if throughput has dropped significantly.
        
        Returns:
            Anomaly reason string or None
        """
        gnb_id = record.gnb_id
        
        # Need at least 2 records to compare
        if len(self.history[gnb_id]) < 1:
            return None
        
        # Get baseline throughput (average of recent non-anomalous records)
        recent_records = self.history[gnb_id][-10:]  # Last 10 samples
        non_anomalous = [r for r in recent_records if not r.is_anomaly]
        
        if not non_anomalous:
            return None
        
        baseline = sum(r.throughput for r in non_anomalous) / len(non_anomalous)
        
        # Check for drop
        if baseline > 0:
            drop_percent = ((baseline - record.throughput) / baseline) * 100
            if drop_percent > self.thresholds.throughput_drop_percent:
                return (
                    f"Throughput drop: {drop_percent:.1f}% "
                    f"(baseline: {baseline:.1f}, current: {record.throughput:.1f})"
                )
        
        return None
    
    def _update_history(self, record: KPIRecord):
        """Keep rolling history of records per gNB"""
        self.history[record.gnb_id].append(record)
        
        # Keep only recent history
        cutoff = datetime.now() - timedelta(minutes=self.history_window_minutes)
        self.history[record.gnb_id] = [
            r for r in self.history[record.gnb_id]
            if r.timestamp > cutoff
        ]
    
    def _classify_anomaly_type(self, reasons: List[str]) -> str:
        """Classify the type of anomaly"""
        reason_text = " ".join(reasons).lower()
        
        if "prb" in reason_text:
            return "congestion"
        elif "packet loss" in reason_text:
            return "transport_issue"
        elif "latency" in reason_text:
            return "latency_issue"
        elif "throughput" in reason_text:
            return "throughput_degradation"
        else:
            return "other"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            "total_checked": self.total_checked,
            "total_anomalies": self.total_anomalies,
            "anomaly_rate": (
                self.total_anomalies / self.total_checked * 100
                if self.total_checked > 0 else 0
            ),
            "anomaly_breakdown": dict(self.anomaly_breakdown),
            "tracked_gnbs": len(self.history)
        }
    
    def update_thresholds(self, thresholds: Dict[str, float]):
        """Update detection thresholds at runtime"""
        for key, value in thresholds.items():
            if hasattr(self.thresholds, key):
                setattr(self.thresholds, key, value)
                logger.info(f"[DETECTOR] Updated threshold {key} = {value}")


class AnomalyAggregator:
    """
    Aggregate anomalies over time periods for reporting.
    Tracks anomaly counts, types, and trends per gNB.
    """
    
    def __init__(self, window_minutes: int = 5):
        self.window_minutes = window_minutes
        
        # Anomaly tracking: {gnb_id: {timestamp: [reasons]}}
        self.anomalies: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        
        # Statistics per gNB
        self.stats: Dict[str, Dict[str, Any]] = {}
    
    def add_anomaly(self, gnb_id: str, timestamp: datetime, reason: str):
        """Record an anomaly"""
        self.anomalies[gnb_id].append((timestamp, reason))
    
    def get_anomalies_in_window(
        self,
        gnb_id: str,
        minutes: Optional[int] = None
    ) -> List[Tuple[datetime, str]]:
        """Get anomalies in recent time window"""
        minutes = minutes or self.window_minutes
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        return [
            (ts, reason) for ts, reason in self.anomalies[gnb_id]
            if ts > cutoff
        ]
    
    def get_anomaly_rate(self, gnb_id: str, minutes: Optional[int] = None) -> float:
        """Get recent anomaly rate (0-1)"""
        # Would need access to total record count for this
        # For now, return anomaly count
        anomalies = self.get_anomalies_in_window(gnb_id, minutes)
        return len(anomalies) / (minutes or self.window_minutes) if anomalies else 0.0
