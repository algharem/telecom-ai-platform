from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import asyncio
from dataclasses import dataclass

from app.config import settings


@dataclass
class TimeSeriesRecord:
    """Standardized time-series record for telecom metrics"""
    timestamp: datetime
    gnb_id: str
    metric_name: str
    value: float
    tags: Dict[str, str]


class TimeSeriesDB:
    """
    InfluxDB wrapper for NWDAF analytics storage.
    Optimized for high-throughput RAN KPI ingestion.
    """
    
    def __init__(self):
        self.client = InfluxDBClient(
            url=settings.infrastructure['influxdb_url'],
            token=settings.infrastructure['influxdb_token'],
            org=settings.infrastructure['influxdb_org']
        )
        self.bucket = settings.infrastructure['influxdb_bucket']
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
    
    async def write_kpi(self, record: TimeSeriesRecord) -> bool:
        """Write single KPI measurement"""
        point = Point(record.metric_name) \
            .tag("gNB", record.gnb_id) \
            .tag("domain", "RAN") \
            .field("value", record.value) \
            .time(record.timestamp)
        
        # Add custom tags
        for key, value in record.tags.items():
            point = point.tag(key, value)
        
        try:
            self.write_api.write(bucket=self.bucket, record=point)
            return True
        except Exception as e:
            print(f"Write failed: {e}")
            return False
    
    async def write_batch(self, records: List[TimeSeriesRecord]) -> int:
        """Batch write for efficiency"""
        points = []
        for record in records:
            point = Point(record.metric_name) \
                .tag("gNB", record.gnb_id) \
                .field("value", record.value) \
                .time(record.timestamp)
            
            for key, value in record.tags.items():
                point = point.tag(key, value)
            points.append(point)
        
        try:
            self.write_api.write(bucket=self.bucket, record=points)
            return len(points)
        except Exception as e:
            print(f"Batch write failed: {e}")
            return 0
    
    async def query_range(self,
                         gnb_id: str,
                         metric: str,
                         start: datetime,
                         end: datetime) -> pd.DataFrame:
        """
        Query time-series data for analytics.
        Returns DataFrame for ML processing.
        """
        flux_query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start.isoformat()}, stop: {end.isoformat()})
            |> filter(fn: (r) => r._measurement == "{metric}")
            |> filter(fn: (r) => r.gNB == "{gnb_id}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        try:
            result = self.query_api.query_data_frame(flux_query)
            if result.empty:
                return pd.DataFrame()
            
            result['_time'] = pd.to_datetime(result['_time'])
            result = result.set_index('_time')
            result = result.rename(columns={'value': metric})
            return result
        except Exception as e:
            print(f"Query failed: {e}")
            return pd.DataFrame()
    
    async def get_latest(self,
                        gnb_id: str,
                        metric: str,
                        minutes: int = 5) -> Optional[float]:
        """Get latest value for real-time analytics"""
        end = datetime.utcnow()
        start = end - timedelta(minutes=minutes)
        
        df = await self.query_range(gnb_id, metric, start, end)
        if not df.empty:
            return float(df[metric].iloc[-1])
        return None
    
    async def aggregate_window(self,
                              gnb_id: str,
                              metric: str,
                              window: str = "1h",
                              agg_func: str = "mean") -> pd.DataFrame:
        """
        Aggregate metrics over time windows.
        Used for load level analytics (e.g., hourly average PRB).
        """
        flux_query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r._measurement == "{metric}")
            |> filter(fn: (r) => r.gNB == "{gnb_id}")
            |> aggregateWindow(every: {window}, fn: {agg_func})
        '''
        
        try:
            result = self.query_api.query_data_frame(flux_query)
            return result
        except Exception as e:
            print(f"Aggregation failed: {e}")
            return pd.DataFrame()


# In-memory fallback for Phase 2 (before InfluxDB setup)
class InMemoryTimeSeriesDB:
    """Fallback storage using Pandas for development"""
    
    def __init__(self):
        self.data: Dict[str, pd.DataFrame] = {}
        self.lock = asyncio.Lock()
    
    async def write_kpi(self, record: TimeSeriesRecord) -> bool:
        async with self.lock:
            key = f"{record.gnb_id}_{record.metric_name}"
            
            if key not in self.data:
                self.data[key] = pd.DataFrame(columns=['timestamp', 'value'])
            
            new_row = pd.DataFrame([{
                'timestamp': record.timestamp,
                'value': record.value
            }])
            
            self.data[key] = pd.concat([self.data[key], new_row], ignore_index=True)
            
            # Keep only last 7 days
            cutoff = datetime.utcnow() - timedelta(days=7)
            self.data[key] = self.data[key][self.data[key]['timestamp'] > cutoff]
            
            return True
    
    async def query_range(self,
                         gnb_id: str,
                         metric: str,
                         start: datetime,
                         end: datetime) -> pd.DataFrame:
        async with self.lock:
            key = f"{gnb_id}_{metric}"
            if key not in self.data:
                return pd.DataFrame()
            
            df = self.data[key].copy()
            df = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
            df = df.set_index('timestamp')
            return df
    
    async def get_all_metrics(self,
                             gnb_id: str,
                             start: datetime,
                             end: datetime) -> pd.DataFrame:
        """Get all metrics for a gNB as single DataFrame"""
        async with self.lock:
            metrics = ['prb_usage', 'throughput', 'latency', 'packet_loss']
            frames = []
            
            for metric in metrics:
                key = f"{gnb_id}_{metric}"
                if key in self.data:
                    df = self.data[key].copy()
                    df = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
                    df = df.rename(columns={'value': metric})
                    df = df.set_index('timestamp')
                    frames.append(df)
            
            if not frames:
                return pd.DataFrame()
            
            # Join all metrics on timestamp
            combined = pd.concat(frames, axis=1)
            return combined