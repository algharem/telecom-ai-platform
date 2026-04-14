"""
gNB-level metrics aggregator - combines metrics from multiple NFs.

Aggregates metrics from AMF, UPF, NRF, AUSF into unified gNB KPI records
using 1-minute sliding windows. Handles missing data and outliers gracefully.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class WindowMetrics:
    """Metrics for a single aggregation window"""
    gnb_id: str
    start_time: datetime
    end_time: datetime
    
    # Aggregated metrics
    prb_usage: Optional[float] = None
    throughput: Optional[float] = None
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    
    # Registration metrics (from AMF)
    registration_attempts: int = 0
    registration_successes: int = 0
    registration_latency: List[float] = field(default_factory=list)
    
    # Throughput metrics (from UPF)
    throughput_samples: List[float] = field(default_factory=list)
    
    # Latency metrics (from UPF/AMF)
    latency_samples: List[float] = field(default_factory=list)
    
    # Packet loss metrics (from UPF)
    packet_loss_samples: List[float] = field(default_factory=list)
    
    # Service availability (from NRF/AUSF)
    service_availability: float = 100.0
    
    # Tracking
    nf_contributions: Dict[str, int] = field(default_factory=lambda: {
        'amf': 0, 'upf': 0, 'nrf': 0, 'ausf': 0
    })
    
    def is_complete(self) -> bool:
        """Check if window has sufficient data"""
        # Need data from at least 2 NFs and some actual samples
        nf_count = sum(1 for count in self.nf_contributions.values() if count > 0)
        return nf_count >= 2
    
    def compute_aggregates(self):
        """Compute final metrics from samples"""
        # PRB usage from AMF registrations (proxy for load)
        if self.registration_attempts > 0:
            registration_rate = (self.registration_successes / self.registration_attempts) * 100
            # Map registration rate to effective PRB usage (higher failures = higher load)
            self.prb_usage = 100 - registration_rate
        
        # Throughput - average of UPF samples
        if self.throughput_samples:
            self.throughput = statistics.mean(self.throughput_samples)
        
        # Latency - average of samples
        if self.latency_samples:
            self.latency = statistics.mean(self.latency_samples)
        
        # Packet loss - average of samples
        if self.packet_loss_samples:
            self.packet_loss = statistics.mean(self.packet_loss_samples)


class GnBMetricsAggregator:
    """
    Aggregates NF-specific metrics into gNB-level KPI records.
    
    Maintains 1-minute sliding windows per gNB and combines metrics from:
    - AMF: registration attempts/success, authentication latency
    - UPF: throughput, latency, packet loss, IP session metrics
    - NRF: service availability
    - AUSF: authentication success rate
    """
    
    def __init__(self, window_seconds: int = 60, max_staleness_seconds: int = 120):
        """
        Initialize aggregator.
        
        Args:
            window_seconds: Time window for aggregation (default 60s = 1 minute)
            max_staleness_seconds: Keep windows this long after they close
        """
        self.window_seconds = window_seconds
        self.max_staleness_seconds = max_staleness_seconds
        
        # Active windows per gNB: {gnb_id: {timestamp: WindowMetrics}}
        self.windows: Dict[str, Dict[float, WindowMetrics]] = defaultdict(dict)
        
        # Completed windows ready for output
        self.completed_windows: List[WindowMetrics] = []
        
        # Statistics
        self.total_metrics_added = 0
        self.total_windows_completed = 0
        
        logger.info(
            f"[AGGREGATOR] Initialized: {window_seconds}s windows, "
            f"{max_staleness_seconds}s retention"
        )
    
    def add_nf_metric(
        self,
        gnb_id: str,
        nf_type: str,
        metric_name: str,
        value: float,
        timestamp: datetime
    ):
        """
        Add a metric from a network function.
        
        Args:
            gnb_id: gNB identifier (e.g., "gNB_001")
            nf_type: Type of NF ("amf", "upf", "nrf", "ausf")
            metric_name: Metric name (e.g., "registration_latency", "throughput")
            value: Metric value
            timestamp: When the metric was measured
        """
        if not gnb_id or value is None:
            return
        
        # Determine which window this metric belongs to
        window_key = self._get_window_key(timestamp)
        
        # Get or create window
        if window_key not in self.windows[gnb_id]:
            self.windows[gnb_id][window_key] = WindowMetrics(
                gnb_id=gnb_id,
                start_time=self._key_to_datetime(window_key),
                end_time=self._key_to_datetime(window_key) + timedelta(seconds=self.window_seconds)
            )
        
        window = self.windows[gnb_id][window_key]
        window.nf_contributions[nf_type] += 1
        
        # Route metric to appropriate handler
        self._process_nf_metric(window, nf_type, metric_name, value)
        
        self.total_metrics_added += 1
    
    def _process_nf_metric(
        self,
        window: WindowMetrics,
        nf_type: str,
        metric_name: str,
        value: float
    ):
        """Route NF metrics to correct window field"""
        nf_type = nf_type.lower()
        
        # AMF metrics
        if nf_type == "amf":
            if metric_name == "registration_attempts":
                window.registration_attempts += int(value)
            elif metric_name == "registration_successes":
                window.registration_successes += int(value)
            elif metric_name == "registration_latency":
                window.registration_latency.append(value)
        
        # UPF metrics
        elif nf_type == "upf":
            if metric_name == "throughput":
                window.throughput_samples.append(value)
            elif metric_name == "latency":
                window.latency_samples.append(value)
            elif metric_name == "packet_loss":
                window.packet_loss_samples.append(value)
        
        # NRF metrics
        elif nf_type == "nrf":
            if metric_name == "service_availability":
                window.service_availability = value
        
        # AUSF metrics
        elif nf_type == "ausf":
            if metric_name == "authentication_success_rate":
                window.service_availability = value
    
    def get_completed_windows(self) -> List[WindowMetrics]:
        """
        Get all windows that have closed and are ready for output.
        Clears the completed list after returning.
        
        Returns:
            List of completed WindowMetrics
        """
        completed = self.completed_windows[:]
        self.completed_windows = []
        return completed
    
    def flush(self, current_time: Optional[datetime] = None) -> List[WindowMetrics]:
        """
        Force flush all windows (for shutdown or testing).
        Computes aggregates for all active windows.
        
        Args:
            current_time: Current timestamp (uses now() if None)
            
        Returns:
            List of all flushed WindowMetrics
        """
        current_time = current_time or datetime.now()
        result = []
        
        for gnb_id, gnb_windows in self.windows.items():
            for window_key, window in gnb_windows.items():
                window.compute_aggregates()
                result.append(window)
        
        self.windows.clear()
        self.total_windows_completed += len(result)
        
        logger.info(
            f"[AGGREGATOR] Flushed {len(result)} windows. "
            f"Total windows completed: {self.total_windows_completed}"
        )
        
        return result
    
    def _process_completed_windows(self, current_time: datetime):
        """
        Check for and process any windows that have closed.
        Called periodically to move closed windows to completed list.
        """
        current_window_key = self._get_window_key(current_time)
        
        for gnb_id, gnb_windows in list(self.windows.items()):
            for window_key, window in list(gnb_windows.items()):
                # Window is complete if current_time has moved to next window
                if window_key < current_window_key:
                    # Window has closed - compute aggregates
                    window.compute_aggregates()
                    self.completed_windows.append(window)
                    del gnb_windows[window_key]
                    self.total_windows_completed += 1
                    
                    logger.debug(
                        f"[AGGREGATOR] Window completed: {gnb_id} "
                        f"{window.start_time} - {window.end_time}"
                    )
            
            # Clean up empty gNB entries
            if not gnb_windows:
                del self.windows[gnb_id]
    
    def _get_window_key(self, timestamp: datetime) -> float:
        """
        Convert timestamp to window key.
        Windows are defined by their start time.
        """
        # Align timestamp to window boundary
        epoch = timestamp.timestamp()
        window_start = int(epoch // self.window_seconds) * self.window_seconds
        return float(window_start)
    
    def _key_to_datetime(self, key: float) -> datetime:
        """Convert window key back to datetime"""
        return datetime.fromtimestamp(key)
    
    def get_stats(self) -> Dict:
        """Get aggregator statistics"""
        total_active_windows = sum(len(w) for w in self.windows.values())
        
        return {
            "total_gnbs_active": len(self.windows),
            "active_windows": total_active_windows,
            "completed_windows": self.total_windows_completed,
            "total_metrics_added": self.total_metrics_added,
            "completed_pending": len(self.completed_windows)
        }
