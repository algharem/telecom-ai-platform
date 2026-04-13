"""
Data provider abstraction layer - switch between simulator and real log sources.

Allows pluggable data sources for feeding the AI model:
- SimulatorDataProvider: Uses KPI simulator for testing
- LogFileDataProvider: Reads from real Open5GS log files
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from models.schemas import KPIMetrics, PredictionRequest
from services.kpi_simulator import TelecomKPISimulator
from parsers.open5gs_real_parser import parse_open5gs_logs
from utils.gnb_utils import normalize_gnb_id
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class KPIRecord:
    """Unified KPI record from any data source"""
    timestamp: datetime
    gnb_id: str
    prb_usage: float
    throughput: float
    latency: float
    packet_loss: float
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    source: str = "unknown"  # "simulator" or "logs"
    
    def to_prediction_request(self) -> PredictionRequest:
        """Convert to API prediction request"""
        return PredictionRequest(
            gnb_id=self.gnb_id,
            timestamp=self.timestamp,
            metrics=KPIMetrics(
                prb_usage=self.prb_usage,
                throughput=self.throughput,
                latency=self.latency,
                packet_loss=self.packet_loss
            )
        )


class DataProvider(ABC):
    """Abstract base class for data sources"""
    
    @abstractmethod
    def get_next_batch(self, limit: int = 100) -> List[KPIRecord]:
        """
        Fetch next batch of KPI records.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of KPIRecord objects
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if data source is available"""
        pass
    
    @abstractmethod
    def get_source_info(self) -> Dict[str, Any]:
        """Return metadata about the data source"""
        pass
    
    @abstractmethod
    def close(self):
        """Cleanup resources"""
        pass


class SimulatorDataProvider(DataProvider):
    """
    Data provider using KPI simulator.
    
    Useful for testing and development when real logs are not available.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.simulator = TelecomKPISimulator(
            base_stations=config.get("base_stations", 10),
            random_seed=config.get("random_seed", 42)
        )
        self.batch_index = 0
        self.generated_data = None
        self.current_position = 0
        
        # Generate initial dataset
        self._regenerate_data()
        logger.info("[PROVIDER] SimulatorDataProvider initialized")
    
    def _regenerate_data(self):
        """Generate new training data"""
        hours = self.config.get("hours", 168)
        anomaly_rate = self.config.get("anomaly_rate", 0.05)
        
        df = self.simulator.generate_training_data(
            hours=hours,
            anomaly_rate=anomaly_rate
        )
        
        # Convert DataFrame to KPIRecord list
        self.generated_data = []
        for _, row in df.iterrows():
            record = KPIRecord(
                timestamp=row['timestamp'],
                gnb_id=row['gNB'],
                prb_usage=row['prb_usage'],
                throughput=row['throughput_mbps'],
                latency=row['latency_ms'],
                packet_loss=row['packet_loss_percent'],
                is_anomaly=row['is_anomaly'],
                anomaly_reason=row['anomaly_type'],
                source="simulator"
            )
            self.generated_data.append(record)
        
        self.current_position = 0
        logger.info(f"[PROVIDER] Generated {len(self.generated_data)} simulator records")
    
    def get_next_batch(self, limit: int = 100) -> List[KPIRecord]:
        """Return next batch from simulator"""
        if self.current_position >= len(self.generated_data):
            # Regenerate data if we've exhausted current dataset
            self._regenerate_data()
        
        end_pos = min(self.current_position + limit, len(self.generated_data))
        batch = self.generated_data[self.current_position:end_pos]
        self.current_position = end_pos
        
        self.batch_index += 1
        return batch
    
    def is_available(self) -> bool:
        """Simulator is always available"""
        return True
    
    def get_source_info(self) -> Dict[str, Any]:
        """Return simulator metadata"""
        return {
            "type": "simulator",
            "base_stations": len(self.simulator.base_stations),
            "total_records": len(self.generated_data),
            "current_position": self.current_position,
            "batches_fetched": self.batch_index
        }
    
    def close(self):
        """Cleanup"""
        self.generated_data = None


class PrometheusDataProvider(DataProvider):
    """
    Data provider fetching live metrics from Prometheus.
    
    Queries Prometheus for Open5GS metrics and derives RAN-level KPIs.
    Provides real-time monitoring without file parsing overhead.
    """
    
    def __init__(self, config: Dict[str, Any]):
        from services.prometheus_client import PrometheusClient
        
        self.config = config
        self.prometheus_url = config.get("prometheus_url", "http://172.25.0.36:9090")
        self.gnb_id = config.get("gnb_id", "gNB-001")
        self.derivation_config = config.get("derivation", {})
        
        # Initialize Prometheus client
        self.client = PrometheusClient(base_url=self.prometheus_url)
        self.is_ready = False
        self.last_fetch_time = None
        
        # Metric mappings
        self.gauge_metrics = {
            'fivegs_amffunction_rm_registeredsubnbr': 'registered_ues',
            'fivegs_smffunction_sm_sessionnbr': 'pdu_sessions',
            'fivegs_upffunction_upf_sessionnbr': 'upf_sessions',
            'fivegs_smffunction_sm_qos_flow_nbr': 'qos_flows',
        }
        
        self.rate_metrics = {
            'fivegs_ep_n3_gtp_indatapktn3upf': 'n3_in_packets',
            'fivegs_ep_n3_gtp_outdatapktn3upf': 'n3_out_packets',
            'fivegs_amffunction_amf_authfail': 'auth_fails',
            'fivegs_amffunction_amf_authreq': 'auth_requests',
            'fivegs_amffunction_rm_reginitsucc': 'reg_success',
        }
        
        # Test connection
        self._test_connection()
        logger.info("[PROVIDER] PrometheusDataProvider initialized")
    
    def _test_connection(self):
        """Test Prometheus connectivity and Open5GS metrics availability"""
        try:
            if not self.client.is_available():
                logger.warning(f"[PROVIDER] Cannot connect to Prometheus at {self.prometheus_url}")
                return
            
            if self.client.test_open5gs_metrics():
                self.is_ready = True
                logger.info("[PROVIDER] Prometheus connected with Open5GS metrics")
            else:
                logger.warning("[PROVIDER] Prometheus available but Open5GS metrics not found")
                
        except Exception as e:
            logger.error(f"[PROVIDER] Connection test failed: {e}")
    
    def _fetch_gauge_metrics(self) -> Dict[str, float]:
        """Fetch gauge metrics (current values)"""
        results = {}
        
        for prom_metric, internal_name in self.gauge_metrics.items():
            try:
                value = self.client.get_query_value(prom_metric)
                if value is not None:
                    results[internal_name] = value
            except Exception as e:
                logger.debug(f"[PROVIDER] Error fetching {prom_metric}: {e}")
        
        return results
    
    def _fetch_rate_metrics(self) -> Dict[str, float]:
        """Fetch rate metrics (5-minute rate)"""
        results = {}
        
        for prom_metric, internal_name in self.rate_metrics.items():
            try:
                query = f"rate({prom_metric}[5m])"
                value = self.client.get_query_value(query)
                if value is not None:
                    results[internal_name] = value
            except Exception as e:
                logger.debug(f"[PROVIDER] Error fetching rate for {prom_metric}: {e}")
        
        return results
    
    def _derive_kpis(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """Derive RAN-level KPIs from core network metrics"""
        
        registered_ues = metrics.get('registered_ues', 0)
        pdu_sessions = metrics.get('pdu_sessions', 0)
        auth_requests = metrics.get('auth_requests', 1)
        auth_fails = metrics.get('auth_fails', 0)
        
        # Calculate auth failure rate
        auth_fail_rate = auth_fails / max(auth_requests, 1)
        
        # PRB usage derivation
        prb_base = self.derivation_config.get('prb_base', 20.0)
        prb_per_ue = self.derivation_config.get('prb_per_ue', 15.0)
        prb_usage = min(100.0, prb_base + registered_ues * prb_per_ue)
        
        # Throughput derivation
        mbps_per_session = self.derivation_config.get('mbps_per_session', 5.0)
        throughput = pdu_sessions * mbps_per_session
        
        # Latency derivation
        latency_base = self.derivation_config.get('latency_base_ms', 20.0)
        latency_penalty = self.derivation_config.get('latency_penalty_ms', 100.0)
        latency = latency_base + auth_fail_rate * latency_penalty
        
        # Packet loss from auth failures
        packet_loss = auth_fail_rate * 100.0
        
        return {
            'prb_usage': round(min(prb_usage, 100.0), 2),
            'throughput': round(throughput, 2),
            'latency': round(min(latency, 100.0), 2),
            'packet_loss': round(min(packet_loss, 100.0), 2)
        }
    
    def get_next_batch(self, limit: int = 100) -> List[KPIRecord]:
        """Fetch current metrics from Prometheus and return as KPIRecord"""
        
        if not self.is_ready:
            logger.warning("[PROVIDER] Prometheus not ready")
            return []
        
        try:
            # Fetch all metrics
            gauge_metrics = self._fetch_gauge_metrics()
            rate_metrics = self._fetch_rate_metrics()
            all_metrics = {**gauge_metrics, **rate_metrics}
            
            logger.debug(f"[PROVIDER] Fetched metrics: {all_metrics}")
            
            # Derive RAN KPIs
            kpis = self._derive_kpis(all_metrics)
            
            # Create KPIRecord (Prometheus gives snapshot, so 1 record)
            record = KPIRecord(
                timestamp=datetime.utcnow(),
                gnb_id=self.gnb_id,
                prb_usage=kpis['prb_usage'],
                throughput=kpis['throughput'],
                latency=kpis['latency'],
                packet_loss=kpis['packet_loss'],
                source="prometheus"
            )
            
            self.last_fetch_time = datetime.utcnow()
            return [record]
            
        except Exception as e:
            logger.error(f"[PROVIDER] Error fetching Prometheus metrics: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Prometheus is ready"""
        return self.is_ready
    
    def get_source_info(self) -> Dict[str, Any]:
        """Return Prometheus source metadata"""
        return {
            "type": "prometheus",
            "url": self.prometheus_url,
            "gnb_id": self.gnb_id,
            "is_ready": self.is_ready,
            "last_fetch": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "gauge_metrics": list(self.gauge_metrics.keys()),
            "rate_metrics": list(self.rate_metrics.keys())
        }
    
    def close(self):
        """Cleanup"""
        self.is_ready = False


class LogFileDataProvider(DataProvider):
    """
    Data provider reading from real Open5GS log files.
    
    Parses actual Open5GS logs (AMF, SMF, UPF, etc.) and converts
    session/event data into gNB-level KPI metrics.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_path = Path(config.get("base_path", "/var/log/open5gs"))
        self.watched_nfs = config.get("watched_nfs", ["amf", "upf", "nrf", "ausf"])
        self.polling_interval = config.get("polling_interval_seconds", 5)
        
        # Load and parse logs
        self.kpi_records = []
        self.current_position = 0
        self.is_ready = False
        self.last_parse_time = None
        
        # Try to load logs
        self._load_logs()
        
        logger.info(f"[PROVIDER] LogFileDataProvider initialized: {self.base_path}")
        logger.info(f"[PROVIDER] Loaded {len(self.kpi_records)} KPI records from logs")
    
    def _load_logs(self):
        """Load and parse all log files in directory"""
        try:
            if not self.base_path.exists():
                logger.warning(f"Log directory not found: {self.base_path}")
                return
            
            # Parse logs using real parser
            kpi_dicts = parse_open5gs_logs(self.base_path)
            logger.info(f"[PROVIDER] Parsed logs returned {len(kpi_dicts)} gNB metrics")
            
            # Convert to KPIRecord format with normalized gNB IDs
            for kpi_dict in kpi_dicts:
                normalized_gnb_id = normalize_gnb_id(kpi_dict['gnb_id'])
                record = KPIRecord(
                    timestamp=datetime.fromisoformat(kpi_dict['timestamp']),
                    gnb_id=normalized_gnb_id,
                    prb_usage=kpi_dict['prb_usage'],
                    throughput=kpi_dict['throughput'],
                    latency=kpi_dict['latency'],
                    packet_loss=kpi_dict['packet_loss'],
                    source="logs"
                )
                self.kpi_records.append(record)
            
            self.is_ready = True
            self.last_parse_time = datetime.utcnow()
            
            if self.kpi_records:
                logger.info(f"[PROVIDER] Successfully loaded {len(self.kpi_records)} KPI records from logs")
            else:
                logger.warning("[PROVIDER] No KPI records generated from logs")
                
        except Exception as e:
            logger.error(f"[PROVIDER] Error loading logs: {e}", exc_info=True)
            self.is_ready = False
    
    def get_next_batch(self, limit: int = 100) -> List[KPIRecord]:
        """Return next batch from logs"""
        if not self.kpi_records:
            return []
        
        # Cycle through records if we reach the end
        if self.current_position >= len(self.kpi_records):
            self.current_position = 0
        
        end_pos = min(self.current_position + limit, len(self.kpi_records))
        batch = self.kpi_records[self.current_position:end_pos]
        self.current_position = end_pos
        
        return batch
    
    def is_available(self) -> bool:
        """Check if logs are loaded and ready"""
        return self.is_ready and len(self.kpi_records) > 0
    
    def get_source_info(self) -> Dict[str, Any]:
        """Return log source metadata"""
        return {
            "type": "logs",
            "base_path": str(self.base_path),
            "watched_nfs": self.watched_nfs,
            "records_loaded": len(self.kpi_records),
            "is_ready": self.is_ready,
            "last_parse_time": self.last_parse_time.isoformat() if self.last_parse_time else None
        }
    
    def close(self):
        """Cleanup"""
        self.kpi_records = []
        self.current_position = 0


def create_data_provider(source_type: str, config: Dict[str, Any]) -> DataProvider:
    """
    Factory function to create appropriate data provider.
    
    Args:
        source_type: "prometheus", "simulator", or "logs"
        config: Configuration dict for the provider
        
    Returns:
        DataProvider instance
        
    Raises:
        ValueError: If source_type is invalid
    """
    source_type = source_type.lower().strip()
    
    if source_type == "prometheus":
        return PrometheusDataProvider(config)
    elif source_type == "simulator":
        return SimulatorDataProvider(config)
    elif source_type == "logs":
        return LogFileDataProvider(config)
    else:
        raise ValueError(f"Unknown data source type: {source_type}. Use 'prometheus', 'simulator', or 'logs'")


def get_provider_config(source_type: str, env_config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Build provider config from environment or defaults.
    
    Args:
        source_type: "prometheus", "simulator", or "logs"
        env_config: Optional config from environment/settings
        
    Returns:
        Configuration dict
    """
    env_config = env_config or {}
    
    if source_type == "prometheus":
        return {
            "prometheus_url": env_config.get("PROMETHEUS_URL", "http://172.25.0.36:9090"),
            "gnb_id": env_config.get("GNB_ID", "gNB-001"),
            "derivation": {
                "prb_base": float(env_config.get("PRB_BASE", 20.0)),
                "prb_per_ue": float(env_config.get("PRB_PER_UE", 15.0)),
                "mbps_per_session": float(env_config.get("MBPS_PER_SESSION", 5.0)),
                "latency_base_ms": float(env_config.get("LATENCY_BASE_MS", 20.0)),
                "latency_penalty_ms": float(env_config.get("LATENCY_PENALTY_MS", 100.0))
            }
        }
    elif source_type == "simulator":
        return {
            "base_stations": env_config.get("SIMULATOR_BASE_STATIONS", 10),
            "random_seed": env_config.get("SIMULATOR_RANDOM_SEED", 42),
            "hours": env_config.get("SIMULATOR_HOURS", 168),
            "anomaly_rate": env_config.get("SIMULATOR_ANOMALY_RATE", 0.05)
        }
    elif source_type == "logs":
        return {
            "base_path": env_config.get("LOG_BASE_PATH", "/var/log/open5gs"),
            "watched_nfs": env_config.get("LOG_WATCHED_NFS", ["amf", "upf", "nrf", "ausf"]),
            "polling_interval_seconds": env_config.get("LOG_POLLING_INTERVAL", 5)
        }
    else:
        raise ValueError(f"Unknown source type: {source_type}")
