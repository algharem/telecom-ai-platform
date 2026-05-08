"""
Pipeline monitoring and observability - tracks data flow health.

Monitors:
- Parse rate and success rate per NF
- Data freshness (lag between log timestamp and processing)
- Anomaly detection statistics
- Error tracking and retry counts
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParseMetrics:
    """Metrics for a parsing session"""
    nf_type: str
    timestamp: datetime
    total_events: int = 0
    successful_parses: int = 0
    failed_parses: int = 0
    parse_errors: Dict[str, int] = field(default_factory=dict)
    data_freshness_seconds: float = 0.0  # Lag between log time and parse time
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage"""
        total = self.total_events
        return (self.successful_parses / total * 100) if total > 0 else 0.0


@dataclass
class AnomalyMetrics:
    """Anomaly detection metrics"""
    timestamp: datetime
    gnb_id: str
    anomalies_detected: int = 0
    anomaly_types: Dict[str, int] = field(default_factory=dict)
    total_records_checked: int = 0
    
    @property
    def anomaly_rate(self) -> float:
        """Anomaly rate as percentage"""
        return (
            self.anomalies_detected / self.total_records_checked * 100
            if self.total_records_checked > 0 else 0.0
        )


class PipelineMonitor:
    """
    Monitor and track pipeline health and performance.
    
    Tracks:
    - Per-NF parse metrics (success rate, data freshness)
    - Anomaly detection rates
    - Error tracking
    - Data volume metrics
    """
    
    def __init__(self, retention_minutes: int = 60):
        """
        Initialize monitor.
        
        Args:
            retention_minutes: Keep metrics for this long
        """
        self.retention_minutes = retention_minutes
        self.start_time = datetime.now()
        
        # Metrics storage (keep rolling window)
        self.parse_metrics: List[ParseMetrics] = []
        self.anomaly_metrics: List[AnomalyMetrics] = []
        
        # Per-NF counters
        self.nf_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_parsed": 0,
            "total_errors": 0,
            "last_update": None,
            "last_error": None
        })
        
        # Per-gNB counters
        self.gnb_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_records": 0,
            "total_anomalies": 0,
            "last_update": None
        })
        
        # Overall stats
        self.total_records_processed = 0
        self.total_anomalies_detected = 0
        
        logger.info("[MONITOR] Pipeline monitor initialized")
    
    def record_parse(
        self,
        nf_type: str,
        total_events: int,
        successful_parses: int,
        parse_errors: Optional[Dict[str, int]] = None,
        data_freshness_seconds: float = 0.0
    ):
        """
        Record parsing metrics for an NF.
        
        Args:
            nf_type: Type of NF (amf, upf, nrf, ausf)
            total_events: Total events in log batch
            successful_parses: Successfully parsed
            parse_errors: Dict of error_type -> count
            data_freshness_seconds: Lag between log time and parse time
        """
        metric = ParseMetrics(
            nf_type=nf_type,
            timestamp=datetime.now(),
            total_events=total_events,
            successful_parses=successful_parses,
            failed_parses=total_events - successful_parses,
            parse_errors=parse_errors or {},
            data_freshness_seconds=data_freshness_seconds
        )
        
        self.parse_metrics.append(metric)
        self._cleanup_old_metrics()
        
        # Update NF stats
        self.nf_stats[nf_type]["total_parsed"] += successful_parses
        self.nf_stats[nf_type]["total_errors"] += metric.failed_parses
        self.nf_stats[nf_type]["last_update"] = datetime.now()
        
        if metric.failed_parses > 0:
            self.nf_stats[nf_type]["last_error"] = metric.parse_errors
        
        logger.info(
            f"[MONITOR] Parse metrics for {nf_type.upper()}: "
            f"{successful_parses}/{total_events} success "
            f"({metric.success_rate:.1f}%), "
            f"freshness: {data_freshness_seconds:.1f}s"
        )
    
    def record_anomaly(
        self,
        gnb_id: str,
        is_anomaly: bool,
        anomaly_type: Optional[str] = None
    ):
        """
        Record anomaly detection result.
        
        Args:
            gnb_id: gNB identifier
            is_anomaly: Whether it was anomalous
            anomaly_type: Type of anomaly (congestion, etc.)
        """
        self.gnb_stats[gnb_id]["total_records"] += 1
        self.total_records_processed += 1
        
        if is_anomaly:
            self.gnb_stats[gnb_id]["total_anomalies"] += 1
            self.total_anomalies_detected += 1
        
        self.gnb_stats[gnb_id]["last_update"] = datetime.now()
    
    def record_window_completion(
        self,
        gnb_id: str,
        anomalies_in_window: int,
        anomaly_types: Dict[str, int],
        total_records: int
    ):
        """
        Record completion of an aggregation window.
        
        Args:
            gnb_id: gNB identifier
            anomalies_in_window: Count of anomalies detected
            anomaly_types: Breakdown by type
            total_records: Total records in window
        """
        metric = AnomalyMetrics(
            timestamp=datetime.now(),
            gnb_id=gnb_id,
            anomalies_detected=anomalies_in_window,
            anomaly_types=anomaly_types,
            total_records_checked=total_records
        )
        
        self.anomaly_metrics.append(metric)
        self._cleanup_old_metrics()
    
    def _cleanup_old_metrics(self):
        """Remove old metrics outside retention window"""
        cutoff = datetime.now() - timedelta(minutes=self.retention_minutes)
        
        self.parse_metrics = [m for m in self.parse_metrics if m.timestamp > cutoff]
        self.anomaly_metrics = [m for m in self.anomaly_metrics if m.timestamp > cutoff]
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall pipeline health"""
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        # Average parse success rate
        avg_success_rate = 0.0
        if self.parse_metrics:
            avg_success_rate = (
                sum(m.success_rate for m in self.parse_metrics) / len(self.parse_metrics)
            )
        
        # Average data freshness
        avg_freshness = 0.0
        if self.parse_metrics:
            avg_freshness = (
                sum(m.data_freshness_seconds for m in self.parse_metrics) / len(self.parse_metrics)
            )
        
        return {
            "status": self._determine_health_status(avg_success_rate),
            "uptime_seconds": uptime_seconds,
            "total_records_processed": self.total_records_processed,
            "total_anomalies_detected": self.total_anomalies_detected,
            "overall_anomaly_rate": (
                self.total_anomalies_detected / self.total_records_processed * 100
                if self.total_records_processed > 0 else 0
            ),
            "parse_success_rate": avg_success_rate,
            "data_freshness_seconds": avg_freshness,
            "nfs_monitored": len(self.nf_stats),
            "gnbs_monitored": len(self.gnb_stats)
        }
    
    def get_nf_stats(self, nf_type: str) -> Dict[str, Any]:
        """Get stats for specific NF"""
        nf_type = nf_type.lower()
        stats = self.nf_stats.get(nf_type, {})
        
        # Add recent metrics
        recent_metrics = [m for m in self.parse_metrics if m.nf_type == nf_type]
        
        return {
            "nf_type": nf_type,
            "total_parsed": stats.get("total_parsed", 0),
            "total_errors": stats.get("total_errors", 0),
            "last_update": stats.get("last_update"),
            "last_error": stats.get("last_error"),
            "recent_success_rate": (
                sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
                if recent_metrics else 0
            ),
            "error_trend": self._get_error_trend(nf_type)
        }
    
    def get_gnb_stats(self, gnb_id: str) -> Dict[str, Any]:
        """Get stats for specific gNB"""
        stats = self.gnb_stats.get(gnb_id, {})
        total = stats.get("total_records", 0)
        anomalies = stats.get("total_anomalies", 0)
        
        # Get recent anomaly metrics
        recent_anomalies = [m for m in self.anomaly_metrics if m.gnb_id == gnb_id]
        
        return {
            "gnb_id": gnb_id,
            "total_records": total,
            "total_anomalies": anomalies,
            "anomaly_rate": (anomalies / total * 100) if total > 0 else 0,
            "last_update": stats.get("last_update"),
            "recent_anomaly_types": self._get_recent_anomaly_breakdown(gnb_id)
        }
    
    def get_parse_rate_per_minute(self, nf_type: Optional[str] = None) -> float:
        """Get recent parse rate (records per minute)"""
        # Get metrics from last minute
        cutoff = datetime.now() - timedelta(minutes=1)
        metrics = [
            m for m in self.parse_metrics
            if m.timestamp > cutoff and (not nf_type or m.nf_type == nf_type)
        ]
        
        total_parsed = sum(m.successful_parses for m in metrics)
        return total_parsed  # Already per minute
    
    def get_anomaly_rate_per_gnb(self) -> Dict[str, float]:
        """Get anomaly rates for all gNBs"""
        result = {}
        for gnb_id, stats in self.gnb_stats.items():
            total = stats.get("total_records", 0)
            anomalies = stats.get("total_anomalies", 0)
            result[gnb_id] = (anomalies / total * 100) if total > 0 else 0
        return result
    
    def _determine_health_status(self, success_rate: float) -> str:
        """Determine overall health status"""
        if success_rate >= 95:
            return "healthy"
        elif success_rate >= 85:
            return "degraded"
        else:
            return "critical"
    
    def _get_error_trend(self, nf_type: str) -> str:
        """Determine if errors are increasing, decreasing, or stable"""
        # Get recent metrics
        recent = [m for m in self.parse_metrics if m.nf_type == nf_type][-10:]
        
        if len(recent) < 2:
            return "unknown"
        
        # Compare first half vs second half
        mid = len(recent) // 2
        first_half_errors = sum(m.failed_parses for m in recent[:mid])
        second_half_errors = sum(m.failed_parses for m in recent[mid:])
        
        if second_half_errors > first_half_errors * 1.2:
            return "increasing"
        elif first_half_errors > second_half_errors * 1.2:
            return "decreasing"
        else:
            return "stable"
    
    def _get_recent_anomaly_breakdown(self, gnb_id: str) -> Dict[str, int]:
        """Get breakdown of anomaly types for gNB"""
        recent = [m for m in self.anomaly_metrics if m.gnb_id == gnb_id][-10:]
        
        breakdown = defaultdict(int)
        for metric in recent:
            for atype, count in metric.anomaly_types.items():
                breakdown[atype] += count
        
        return dict(breakdown)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics"""
        return {
            "health": self.get_health_status(),
            "nf_breakdown": {nf: self.get_nf_stats(nf) for nf in self.nf_stats.keys()},
            "gnb_breakdown": {gnb: self.get_gnb_stats(gnb) for gnb in self.gnb_stats.keys()},
            "metrics_retained": {
                "parse_metrics": len(self.parse_metrics),
                "anomaly_metrics": len(self.anomaly_metrics)
            }
        }
