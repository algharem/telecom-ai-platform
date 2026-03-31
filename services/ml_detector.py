import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import time

from models.schemas import KPIMetrics, AnomalyResult, PredictionRequest
from utils.logging_config import setup_logging
from utils.exceptions import ModelNotTrainedException, InvalidKPIException


logger = setup_logging()


class AnomalyDetector:
    """
    Production-grade anomaly detection for telecom KPIs.
    
    Uses Isolation Forest (unsupervised) for:
    - No need for labeled data in production
    - Handles high-dimensional KPI space
    - Efficient for streaming data
    
    In telecom context:
    - Isolation Forest detects multivariate anomalies (combinations of metrics)
    - StandardScaler normalizes different units (%, Mbps, ms)
    """
    
    FEATURE_COLUMNS = ['prb_usage', 'throughput', 'latency', 'packet_loss']
    
    def __init__(self, 
                 model_path: str = "./data/anomaly_detector.pkl",
                 contamination: float = 0.05,
                 n_estimators: int = 100):
        self.model_path = Path(model_path)
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self.prediction_count = 0
        self.feature_importance: Dict[str, float] = {}
        
        # Try to load existing model
        self._load_model()
    
    def _load_model(self) -> bool:
        """Load pre-trained model if exists"""
        if self.model_path.exists():
            try:
                artifact = joblib.load(self.model_path)
                self.model = artifact['model']
                self.scaler = artifact['scaler']
                self.is_trained = True
                self.feature_importance = artifact.get('feature_importance', {})
                logger.info(f"Loaded pre-trained model from {self.model_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
        return False
    
    def _save_model(self) -> None:
        """Persist model to disk"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_importance': self.feature_importance,
            'contamination': self.contamination,
            'version': '1.0.0'
        }
        joblib.dump(artifact, self.model_path)
        logger.info(f"Model saved to {self.model_path}")
    
    def train(self, df: pd.DataFrame) -> Dict:
        """
        Train anomaly detection model on historical KPI data.
        
        Args:
            df: DataFrame with columns [prb_usage, throughput_mbps, latency_ms, packet_loss_percent]
                or [prb_usage, throughput, latency, packet_loss]
        
        Returns:
            Training metrics
        """
        logger.info(f"Training model on {len(df)} records")
        
        # Normalize column names (handle both naming conventions)
        df_normalized = df.copy()
        column_mapping = {
            'throughput_mbps': 'throughput',
            'latency_ms': 'latency',
            'packet_loss_percent': 'packet_loss'
        }
        df_normalized = df_normalized.rename(columns=column_mapping)
        
        # Prepare features
        X = df_normalized[self.FEATURE_COLUMNS].copy()
        
        # Handle missing values (forward fill for time series)
        X = X.ffill().bfill()
        
        # Scale features (critical for telecom: different units)
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        
        self.model.fit(X_scaled)
        self.is_trained = True
        
        # Calculate feature importance (mean impact on anomaly score)
        self._calculate_feature_importance(X_scaled)
        
        # Save model
        self._save_model()
        
        # Training metrics
        scores = self.model.decision_function(X_scaled)
        predictions = self.model.predict(X_scaled)
        
        metrics = {
            "training_samples": len(df),
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "detected_anomalies": int((predictions == -1).sum()),
            "anomaly_ratio": float((predictions == -1).mean()),
            "score_mean": float(scores.mean()),
            "score_std": float(scores.std())
        }
        
        logger.info(f"Training complete: {metrics['detected_anomalies']} anomalies detected")
        return metrics
    
    def _calculate_feature_importance(self, X_scaled: np.ndarray) -> None:
        """Calculate per-feature contribution to anomaly detection"""
        # Use path length variance as importance proxy
        n_samples = min(1000, len(X_scaled))
        indices = np.random.choice(len(X_scaled), n_samples, replace=False)
        sample = X_scaled[indices]
        
        # Get anomaly scores with each feature permuted
        base_scores = self.model.decision_function(sample)
        
        for i, feature in enumerate(self.FEATURE_COLUMNS):
            X_permuted = sample.copy()
            np.random.shuffle(X_permuted[:, i])
            permuted_scores = self.model.decision_function(X_permuted)
            
            importance = np.mean(np.abs(base_scores - permuted_scores))
            self.feature_importance[feature] = float(importance)
    
    def predict(self, request: PredictionRequest) -> AnomalyResult:
        """
        Predict anomaly for single KPI measurement.
        
        Args:
            request: PredictionRequest with gNB ID and metrics
        
        Returns:
            AnomalyResult with detection details
        """
        if not self.is_trained:
            raise ModelNotTrainedException()
        
        start_time = time.time()
        
        # Extract and validate features
        metrics = request.metrics
        features = np.array([[
            metrics.prb_usage,
            metrics.throughput,
            metrics.latency,
            metrics.packet_loss
        ]])
        
        # Validate ranges (telecom-specific)
        self._validate_telecom_ranges(metrics)
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Predict
        anomaly_score = self.model.decision_function(features_scaled)[0]
        is_anomaly = self.model.predict(features_scaled)[0] == -1
        
        # Calculate confidence (0-1 based on score distribution)
        # Isolation Forest: negative = anomaly, positive = normal
        # Transform to 0-1 confidence
        confidence = self._calculate_confidence(anomaly_score)
        
        # Determine severity and contributing features
        severity = self._determine_severity(metrics, is_anomaly, anomaly_score)
        contributing = self._identify_contributing_features(features_scaled[0], anomaly_score)
        
        # Generate explanation
        explanation = self._generate_explanation(metrics, is_anomaly, contributing, severity)
        
        processing_time = (time.time() - start_time) * 1000  # ms
        self.prediction_count += 1
        
        logger.info(
            f"Prediction for {request.gnb_id}: anomaly={is_anomaly}, "
            f"score={anomaly_score:.3f}, time={processing_time:.2f}ms"
        )
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=float(anomaly_score),
            confidence=confidence,
            severity=severity,
            contributing_features=contributing,
            explanation=explanation
        )
    
    def _validate_telecom_ranges(self, metrics: KPIMetrics) -> None:
        """Validate metrics against realistic telecom thresholds"""
        issues = []
        
        if metrics.prb_usage > 95:
            issues.append("PRB usage critical (>95%)")
        if metrics.latency > 100:
            issues.append("Latency excessive (>100ms)")
        if metrics.packet_loss > 2:
            issues.append("Packet loss severe (>2%)")
            
        if len(issues) >= 2:
            logger.warning(f"Multiple critical thresholds breached: {issues}")
    
    def _calculate_confidence(self, score: float) -> float:
        """Convert Isolation Forest score to confidence 0-1"""
        # Typical range: -0.5 (anomaly) to 0.5 (normal)
        # Transform to 0-1 with sigmoid-like scaling
        normalized = (score + 0.5)  # Shift to 0-1 range roughly
        confidence = 1 / (1 + np.exp(-5 * normalized))  # Sigmoid
        return float(confidence)
    
    def _determine_severity(self, 
                           metrics: KPIMetrics, 
                           is_anomaly: bool,
                           score: float) -> str:
        """Determine anomaly severity based on telecom thresholds"""
        if not is_anomaly:
            return "normal"
        
        # Critical thresholds (3GPP/operator specific)
        critical_checks = [
            metrics.prb_usage > 90,
            metrics.latency > 100,
            metrics.packet_loss > 3,
            metrics.throughput < 50 and metrics.prb_usage > 80,  # Low efficiency
            score < -0.3  # Strong anomaly signal
        ]
        
        if sum(critical_checks) >= 2 or score < -0.4:
            return "critical"
        elif any(critical_checks) or score < -0.2:
            return "warning"
        
        return "warning"
    
    def _identify_contributing_features(self, 
                                       features_scaled: np.ndarray,
                                       score: float) -> List[str]:
        """Identify which KPIs contributed most to anomaly"""
        if score > 0:  # Normal
            return []
        
        # For anomalies, check which features are most deviant
        contributions = []
        for i, feature in enumerate(self.FEATURE_COLUMNS):
            if abs(features_scaled[i]) > 2:  # >2 standard deviations
                contributions.append(feature)
        
        # Sort by absolute z-score
        contributions.sort(key=lambda f: abs(features_scaled[self.FEATURE_COLUMNS.index(f)]), reverse=True)
        return contributions[:2]  # Top 2 contributors
    
    def _generate_explanation(self,
                             metrics: KPIMetrics,
                             is_anomaly: bool,
                             contributing: List[str],
                             severity: str) -> str:
        """Generate human-readable explanation for operators"""
        if not is_anomaly:
            return "All KPIs within normal operating ranges."
        
        explanations = []
        
        if "prb_usage" in contributing:
            explanations.append(f"High resource utilization ({metrics.prb_usage:.1f}% PRB usage)")
        if "latency" in contributing:
            explanations.append(f"Elevated latency ({metrics.latency:.1f}ms)")
        if "packet_loss" in contributing:
            explanations.append(f"Packet loss detected ({metrics.packet_loss:.2f}%)")
        if "throughput" in contributing:
            explanations.append(f"Throughput degradation ({metrics.throughput:.1f} Mbps)")
        
        base = "Anomaly detected: " + "; ".join(explanations)
        
        if severity == "critical":
            base += ". Immediate intervention recommended."
        else:
            base += ". Monitor closely."
            
        return base
    
    def batch_predict(self, requests: List[PredictionRequest]) -> List[AnomalyResult]:
        """Efficient batch prediction for multiple gNBs"""
        if not self.is_trained:
            raise ModelNotTrainedException()
        
        features = np.array([[
            r.metrics.prb_usage,
            r.metrics.throughput,
            r.metrics.latency,
            r.metrics.packet_loss
        ] for r in requests])
        
        features_scaled = self.scaler.transform(features)
        scores = self.model.decision_function(features_scaled)
        predictions = self.model.predict(features_scaled)
        
        results = []
        for i, request in enumerate(requests):
            is_anomaly = predictions[i] == -1
            results.append(AnomalyResult(
                is_anomaly=is_anomaly,
                anomaly_score=float(scores[i]),
                confidence=self._calculate_confidence(scores[i]),
                severity=self._determine_severity(request.metrics, is_anomaly, scores[i]),
                contributing_features=self._identify_contributing_features(features_scaled[i], scores[i]),
                explanation=self._generate_explanation(request.metrics, is_anomaly, [], "warning")
            ))
        
        return results
    
    def get_model_info(self) -> Dict:
        """Return model metadata for monitoring"""
        return {
            "is_trained": self.is_trained,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "feature_importance": self.feature_importance,
            "prediction_count": self.prediction_count,
            "model_path": str(self.model_path),
            "feature_columns": self.FEATURE_COLUMNS
        }
