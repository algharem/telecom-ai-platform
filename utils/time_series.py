import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from scipy import stats
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TimeSeriesAnalyzer:
    """
    Statistical analysis for telecom KPI time-series.
    Used by NWDAF for trend detection and forecasting.
    """
    
    @staticmethod
    def calculate_trend(series: pd.Series) -> Dict:
        """
        Calculate trend direction and strength.
        Uses linear regression slope.
        """
        if len(series) < 2:
            return {"direction": "stable", "slope": 0, "strength": 0}
        
        x = np.arange(len(series))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, series)
        
        # Normalize slope to percentage change per period
        mean_val = series.mean()
        if mean_val > 0:
            normalized_slope = (slope / mean_val) * 100
        else:
            normalized_slope = 0
        
        # Determine direction
        if abs(normalized_slope) < 1:
            direction = "stable"
        elif normalized_slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        
        # Strength based on R-squared
        strength = abs(r_value)
        
        return {
            "direction": direction,
            "slope_per_period": float(slope),
            "normalized_slope_pct": float(normalized_slope),
            "r_squared": float(r_value ** 2),
            "p_value": float(p_value),
            "strength": float(strength),
            "is_significant": p_value < 0.05
        }
    
    @staticmethod
    def detect_seasonality(series: pd.Series, 
                          period: int = 12) -> Dict:
        """
        Detect daily/weekly patterns in telecom traffic.
        Critical for capacity planning.
        """
        if len(series) < period * 2:
            return {"has_seasonality": False, "reason": "insufficient_data"}
        
        # Autocorrelation at lag = period
        autocorr = series.autocorr(lag=period)
        
        # Seasonal decomposition would go here (using statsmodels)
        # Simplified: check if autocorrelation is significant
        has_seasonality = abs(autocorr) > 0.3
        
        return {
            "has_seasonality": has_seasonality,
            "autocorrelation": float(autocorr),
            "period": period,
            "pattern": "daily" if period == 24 else "weekly" if period == 168 else "unknown"
        }
    
    @staticmethod
    def calculate_percentiles(series: pd.Series) -> Dict:
        """Calculate load distribution percentiles"""
        return {
            "p50": float(series.median()),
            "p75": float(series.quantile(0.75)),
            "p90": float(series.quantile(0.90)),
            "p95": float(series.quantile(0.95)),
            "p99": float(series.quantile(0.99)),
            "max": float(series.max()),
            "min": float(series.min())
        }
    
    @staticmethod
    def volatility_index(series: pd.Series) -> float:
        """
        Calculate coefficient of variation.
        High volatility = unstable network conditions.
        """
        if series.mean() == 0:
            return 0.0
        return float(series.std() / series.mean())
    
    @staticmethod
    def change_point_detection(series: pd.Series, 
                               threshold: float = 2.0) -> List[Dict]:
        """
        Detect sudden changes in network behavior.
        Uses Z-score based change detection.
        """
        changes = []
        window = min(20, len(series) // 4)
        
        if window < 5:
            return changes
        
        for i in range(window, len(series) - window):
            before = series.iloc[i-window:i]
            after = series.iloc[i:i+window]
            
            # Welch's t-test for unequal variances
            t_stat, p_val = stats.ttest_ind(before, after, equal_var=False)
            
            if p_val < 0.01:  # Significant difference
                mean_diff = abs(after.mean() - before.mean())
                std_pooled = np.sqrt((before.std()**2 + after.std()**2) / 2)
                
                if std_pooled > 0:
                    effect_size = mean_diff / std_pooled
                    if effect_size > threshold:
                        changes.append({
                            "index": i,
                            "timestamp": series.index[i] if hasattr(series.index, 'i') else i,
                            "before_mean": float(before.mean()),
                            "after_mean": float(after.mean()),
                            "percent_change": float((after.mean() - before.mean()) / before.mean() * 100),
                            "confidence": float(1 - p_val)
                        })
        
        return changes


class ForecastingEngine:
    """
    Simple forecasting for network capacity planning.
    Uses exponential smoothing (lightweight for production).
    """
    
    @staticmethod
    def exponential_smoothing(series: pd.Series,
                            alpha: float = 0.3,
                            horizon: int = 24) -> List[float]:
        """
        Holt-Winters exponential smoothing.
        Alpha: smoothing factor (higher = more responsive to recent changes)
        """
        if len(series) < 2:
            return [float(series.iloc[-1])] * horizon if len(series) > 0 else [0.0] * horizon
        
        # Initialize with first value
        smoothed = [series.iloc[0]]
        
        # Apply smoothing
        for i in range(1, len(series)):
            smoothed.append(alpha * series.iloc[i] + (1 - alpha) * smoothed[-1])
        
        # Forecast: assume trend continues
        last_value = smoothed[-1]
        trend = smoothed[-1] - smoothed[-2] if len(smoothed) > 1 else 0
        
        forecasts = []
        for i in range(1, horizon + 1):
            forecast = last_value + (trend * i)
            forecasts.append(float(max(0, forecast)))  # Telecom metrics can't be negative
        
        return forecasts
    
    @staticmethod
    def forecast_with_confidence(series: pd.Series,
                                  horizon: int = 24) -> Dict:
        """
        Generate forecast with confidence intervals.
        Returns dict with forecast, upper/lower bounds.
        """
        base_forecast = ForecastingEngine.exponential_smoothing(series, horizon=horizon)
        
        # Calculate historical error for confidence bands
        if len(series) > 10:
            errors = []
            for i in range(5, min(20, len(series))):
                pred = ForecastingEngine.exponential_smoothing(
                    series.iloc[:i], horizon=1
                )[0]
                actual = series.iloc[i]
                errors.append(abs(pred - actual))
            
            mae = np.mean(errors)
            std_error = np.std(errors)
        else:
            mae = series.std() * 0.1 if len(series) > 0 else 0
            std_error = mae
        
        upper = [f + 1.96 * std_error for f in base_forecast]
        lower = [max(0, f - 1.96 * std_error) for f in base_forecast]
        
        return {
            "forecast": base_forecast,
            "upper_95": upper,
            "lower_95": lower,
            "mae": float(mae),
            "reliability": "high" if mae < series.mean() * 0.1 else "medium" if mae < series.mean() * 0.2 else "low"
        }