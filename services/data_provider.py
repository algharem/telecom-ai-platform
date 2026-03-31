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
        source_type: "simulator" or "logs"
        config: Configuration dict for the provider
        
    Returns:
        DataProvider instance
        
    Raises:
        ValueError: If source_type is invalid
    """
    source_type = source_type.lower().strip()
    
    if source_type == "simulator":
        return SimulatorDataProvider(config)
    elif source_type == "logs":
        return LogFileDataProvider(config)
    else:
        raise ValueError(f"Unknown data source type: {source_type}. Use 'simulator' or 'logs'")


def get_provider_config(source_type: str, env_config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Build provider config from environment or defaults.
    
    Args:
        source_type: "simulator" or "logs"
        env_config: Optional config from environment/settings
        
    Returns:
        Configuration dict
    """
    env_config = env_config or {}
    
    if source_type == "simulator":
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
