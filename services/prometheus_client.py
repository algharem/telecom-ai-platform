"""
Prometheus HTTP API client for querying Open5GS metrics.

Provides a simple interface to Prometheus for fetching current and historical metrics.
"""

import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PrometheusClient:
    """
    HTTP client for Prometheus API.
    
    Queries live metrics from Prometheus server exposing Open5GS metrics.
    Supports instant queries and range queries for historical data.
    """
    
    def __init__(self, base_url: str = "http://172.25.0.36:9090", timeout: int = 10):
        """
        Initialize Prometheus client.
        
        Args:
            base_url: Base URL of Prometheus (e.g., http://localhost:9090)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_endpoint = f"{self.base_url}/api/v1"
        self.timeout = timeout
        self.logger = logger
    
    def query(self, promql: str) -> Optional[Dict[str, Any]]:
        """
        Execute instant PromQL query (current value).
        
        Args:
            promql: PromQL query string
        
        Returns:
            Query result data or None on failure
        """
        try:
            response = requests.get(
                f"{self.api_endpoint}/query",
                params={'query': promql},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success':
                self.logger.debug(f"[PROM] Query succeeded: {promql[:60]}...")
                return data.get('data', {})
            else:
                error_msg = data.get('error', 'Unknown error')
                self.logger.warning(f"[PROM] Query failed: {error_msg}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error(f"[PROM] Query timeout: {promql}")
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error(f"[PROM] Connection error to {self.base_url}")
            return None
        except Exception as e:
            self.logger.error(f"[PROM] Query error: {e}")
            return None
    
    def query_range(
        self, 
        promql: str, 
        start: datetime, 
        end: datetime, 
        step: str = "1m"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute range query for historical data.
        
        Args:
            promql: PromQL query string
            start: Start timestamp
            end: End timestamp
            step: Resolution step (e.g., '1m', '5m', '1h')
        
        Returns:
            Query result data or None on failure
        """
        try:
            params = {
                'query': promql,
                'start': int(start.timestamp()),
                'end': int(end.timestamp()),
                'step': step
            }
            
            response = requests.get(
                f"{self.api_endpoint}/query_range",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success':
                self.logger.debug(f"[PROM] Range query succeeded: {promql[:60]}...")
                return data.get('data', {})
            else:
                self.logger.warning(f"[PROM] Range query failed: {data.get('error', 'Unknown')}")
                return None
                
        except Exception as e:
            self.logger.error(f"[PROM] Range query error: {e}")
            return None
    
    def get_metric_names(self) -> List[str]:
        """
        Get all available metric names in Prometheus.
        
        Returns:
            List of metric names
        """
        try:
            response = requests.get(
                f"{self.api_endpoint}/label/__name__/values",
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success':
                metrics = data.get('data', [])
                self.logger.info(f"[PROM] Found {len(metrics)} available metrics")
                return metrics
            return []
            
        except Exception as e:
            self.logger.error(f"[PROM] Error fetching metric names: {e}")
            return []
    
    def get_query_value(self, promql: str) -> Optional[float]:
        """
        Execute query and extract single numeric value.
        
        Useful for gauge metrics. Returns the value if exactly one result exists.
        
        Args:
            promql: PromQL query string
        
        Returns:
            Numeric value or None
        """
        data = self.query(promql)
        if data and data.get('result'):
            try:
                # Extract value from first (and should be only) result
                value = float(data['result'][0]['value'][1])
                return value
            except (IndexError, ValueError, TypeError):
                return None
        return None
    
    def is_available(self) -> bool:
        """
        Check if Prometheus is reachable and responsive.
        
        Returns:
            True if Prometheus is available
        """
        try:
            response = requests.get(
                f"{self.base_url}/-/healthy",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def test_open5gs_metrics(self) -> bool:
        """
        Test if Open5GS metrics are available.
        
        Checks for presence of core Open5GS metric.
        
        Returns:
            True if Open5GS metrics detected
        """
        metrics = self.get_metric_names()
        open5gs_markers = [
            'fivegs_amffunction_rm_registeredsubnbr',
            'fivegs_smffunction_sm_sessionnbr',
            'fivegs_upffunction_upf_sessionnbr'
        ]
        
        has_open5gs = any(marker in metrics for marker in open5gs_markers)
        if has_open5gs:
            self.logger.info("[PROM] Open5GS metrics detected")
        else:
            self.logger.warning("[PROM] Open5GS metrics not found")
        
        return has_open5gs
