import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict
import random

from models.schemas import KPIMetrics
from utils.logging_config import setup_logging

logger = setup_logging()

class TelecomKPISimulator:
    """
    Robust 5G RAN KPI simulator with guaranteed positive-definite correlations
    and detailed logging.
    """
    def __init__(self, base_stations: int = 10, random_seed: int = 42):
        self.base_stations = [f"gNB_{i:03d}" for i in range(base_stations)]
        # self.base_stations = base_stations

        self.random_seed = random_seed
        np.random.seed(random_seed)
        random.seed(random_seed)
        
        # Peak hours: morning + evening
        self.peak_hours = [9, 10, 11, 19, 20, 21, 22]
        self.off_peak_multiplier = 0.6
        
        # Positive definite correlation matrix
        self.correlation_matrix = np.array([
            [1.0, 0.5, 0.3, 0.2],
            [0.5, 1.0, 0.1, 0.0],
            [0.3, 0.1, 1.0, 0.2],
            [0.2, 0.0, 0.2, 1.0]
        ])
        
        # Ensure strictly positive definite
        eps = 1e-6
        self.correlation_matrix += np.eye(4) * eps
        
        logger.info(f"[SIMULATOR] Initialized with {base_stations} base stations.")

    def _get_time_factor(self, hour: int, day_of_week: int) -> float:
        is_peak = hour in self.peak_hours
        is_weekend = day_of_week >= 5
        factor = 1.0 if is_peak else self.off_peak_multiplier
        if is_weekend:
            factor *= 0.7
        return factor


    def _generate_base_metrics(self, time_factor: float) -> Dict[str, float]:
        means = np.array([50.0, 300.0, 20.0, 0.1])
        stds = np.array([15.0, 100.0, 5.0, 0.05])
        
        adjusted_means = means * np.array([time_factor, time_factor, 1/time_factor, 1.0])
        
        # Generate correlated metrics safely
        L = np.linalg.cholesky(self.correlation_matrix)
        uncorrelated = np.random.normal(size=4)
        correlated = L @ uncorrelated
        
        metrics = adjusted_means + correlated * stds
        
        return {
            'prb_usage': float(np.clip(metrics[0], 0, 100)),
            'throughput': float(max(0, metrics[1])),
            'latency': float(max(1, metrics[2])),
            'packet_loss': float(np.clip(metrics[3], 0, 5))
        }

    def _inject_anomaly(self, metrics: Dict[str, float], anomaly_type: str) -> Dict[str, float]:
        anomalous = metrics.copy()
        if anomaly_type == "congestion":
            anomalous['prb_usage'] = min(100, metrics['prb_usage'] * 1.5 + 20)
            anomalous['throughput'] = metrics['throughput'] * 0.3
            anomalous['latency'] = metrics['latency'] * 3 + 50
            anomalous['packet_loss'] = min(5, metrics['packet_loss'] + 1.0)
        elif anomaly_type == "rf_interference":
            anomalous['prb_usage'] = min(100, metrics['prb_usage'] * 1.2)
            anomalous['throughput'] = metrics['throughput'] * 0.5
            anomalous['latency'] = metrics['latency'] * 1.5
        elif anomaly_type == "transport_issue":
            anomalous['packet_loss'] = min(5, metrics['packet_loss'] + 2.0)
            anomalous['latency'] = metrics['latency'] * 2
            anomalous['throughput'] = metrics['throughput'] * 0.7
        elif anomaly_type == "hardware_degradation":
            anomalous['prb_usage'] = 95 + np.random.uniform(0, 5)
            anomalous['throughput'] = metrics['throughput'] * 0.1
            anomalous['latency'] = 150 + np.random.uniform(0, 50)
        return anomalous
    # services/kpi_simulator.py - Fixed generate_training_data method
    # def generate_training_data2(self, hours: int = 168, anomaly_rate: float = 0.05, base_stations=None) -> pd.DataFrame:

    def generate_training_data(self, 
                                    hours: int = 168,
                                    anomaly_rate: float = 0.05,
                                    base_stations=None) -> pd.DataFrame:
        """
        Generate labeled dataset for ML training.
        Returns DataFrame with 'is_anomaly' label.
        """
        # Use provided base_stations or default
        num_stations = base_stations or len(self.base_stations)
        stations = [f"gNB_{i:03d}" for i in range(num_stations)]
        
        records = []
        anomaly_types = ["congestion", "rf_interference", "transport_issue", "hardware_degradation"]
        
        start_time = datetime.now() - timedelta(hours=hours)
        
        # FIXED: Generate hourly samples for each base station
        # Was generating per-hour total, not per-hour per-station
        for hour_offset in range(hours):
            current_time = start_time + timedelta(hours=hour_offset)
            hour = current_time.hour
            day_of_week = current_time.weekday()
            time_factor = self._get_time_factor(hour, day_of_week)
            
            # Generate for EACH base station
            for gnb in stations:
                # Generate base metrics
                metrics = self._generate_base_metrics(time_factor)
                
                # Decide if anomaly
                is_anomaly = random.random() < anomaly_rate
                anomaly_type = None
                
                if is_anomaly:
                    anomaly_type = random.choice(anomaly_types)
                    metrics = self._inject_anomaly(metrics, anomaly_type)
                
                record = {
                    'timestamp': current_time,
                    'gNB': gnb,
                    'prb_usage': round(metrics['prb_usage'], 2),
                    'throughput_mbps': round(metrics['throughput'], 2),
                    'latency_ms': round(metrics['latency'], 2),
                    'packet_loss_percent': round(metrics['packet_loss'], 4),
                    'is_anomaly': is_anomaly,
                    'anomaly_type': anomaly_type,
                    'hour': hour,
                    'day_of_week': day_of_week
                }
                records.append(record)
        
        df = pd.DataFrame(records)
        
        # Calculate expected records: hours * stations
        expected = hours * num_stations
        actual = len(df)
        
        anomaly_count = df['is_anomaly'].sum()
        logger.info(
            f"Generated {actual} records (expected {expected}) with "
            f"{anomaly_count} anomalies ({anomaly_count/actual*100:.1f}%)"
        )
        
        return df
    def generate_training_data2(self, hours: int = 168, anomaly_rate: float = 0.05, base_stations=None) -> pd.DataFrame:
        records = []
        if base_stations is None:
            base_stations = self.base_stations
        anomaly_types = ["congestion", "rf_interference", "transport_issue", "hardware_degradation"]
        start_time = datetime.now() - timedelta(hours=hours)
        
        logger.info(f"[SIMULATOR] Generating {hours}h of training data...")
        
        for hour_offset in range(hours):
            current_time = start_time + timedelta(hours=hour_offset)
            hour = current_time.hour
            day_of_week = current_time.weekday()
            time_factor = self._get_time_factor(hour, day_of_week)
            
            for gnb in self.base_stations:
                metrics = self._generate_base_metrics(time_factor)
                is_anomaly = random.random() < anomaly_rate
                anomaly_type = None
                if is_anomaly:
                    anomaly_type = random.choice(anomaly_types)
                    metrics = self._inject_anomaly(metrics, anomaly_type)
                record = {
                    'timestamp': current_time,
                    'gNB': gnb,
                    'prb_usage': round(metrics['prb_usage'], 2),
                    'throughput_mbps': round(metrics['throughput'], 2),
                    'latency_ms': round(metrics['latency'], 2),
                    'packet_loss_percent': round(metrics['packet_loss'], 4),
                    'is_anomaly': is_anomaly,
                    'anomaly_type': anomaly_type
                }
                records.append(record)
        
        df = pd.DataFrame(records)
        # Rename to match AnomalyDetector expected columns
        df = df.rename(columns={
            'throughput_mbps': 'throughput',
            'latency_ms': 'latency',
            'packet_loss_percent': 'packet_loss'
        })

        anomaly_count = df['is_anomaly'].sum()
        logger.info(f"[SIMULATOR] Generated {len(df)} records with {anomaly_count} anomalies ({anomaly_count/len(df)*100:.1f}%)")
        return df
        
        # logger.info(f"[SIMULATOR] Generated {len(df)} records with {df['is_anomaly'].sum()} anomalies")
        # return df

    def generate_single_kpi(self, gnb_id: str, scenario: str = "normal") -> KPIMetrics:
        hour = datetime.now().hour
        time_factor = self._get_time_factor(hour, datetime.now().weekday())
        metrics = self._generate_base_metrics(time_factor)
        if scenario != "normal":
            metrics = self._inject_anomaly(metrics, scenario)
        return KPIMetrics(
            prb_usage=round(metrics['prb_usage'], 2),
            throughput=round(metrics['throughput'], 2),
            latency=round(metrics['latency'], 2),
            packet_loss=round(metrics['packet_loss'], 4)
        )

    def get_statistics(self, df: pd.DataFrame) -> Dict:
        return {
            "total_records": len(df),
            "anomaly_count": int(df['is_anomaly'].sum()),
            "anomaly_rate": float(df['is_anomaly'].mean())
        }

# Quick test
if __name__ == "__main__":
    sim = TelecomKPISimulator(base_stations=5)
    df = sim.generate_training_data(hours=24, anomaly_rate=0.1)
    print(df.head())
    print(sim.get_statistics(df))



    