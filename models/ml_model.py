"""
ML Model persistence, versioning, and lifecycle management.
Handles model storage, loading, and A/B testing infrastructure.
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import pickle
import joblib

import numpy as np
from sklearn.base import BaseEstimator


logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """ML model metadata and lineage"""
    model_id: str
    model_name: str
    version: str
    created_at: datetime
    training_samples: int
    features: List[str]
    algorithm: str
    hyperparameters: Dict[str, Any]
    metrics: Dict[str, float]  # accuracy, precision, recall, etc.
    training_data_hash: str    # For reproducibility
    deployed_at: Optional[datetime] = None
    status: str = "staging"    # staging, production, archived
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None
        }


class ModelRegistry:
    """
    ML Model Registry for versioning and lifecycle management.
    
    Supports:
    - Model versioning (semantic versioning)
    - A/B testing (shadow deployment)
    - Rollback capabilities
    - Model lineage tracking
    """
    
    def __init__(self, registry_path: str = "./data/model_registry"):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.models: Dict[str, ModelMetadata] = {}
        self._active_model_id: Optional[str] = None
        self._shadow_model_id: Optional[str] = None  # For A/B testing
        
        self._load_registry()
        logger.info(f"Model registry initialized at {registry_path}")
    
    def _load_registry(self):
        """Load existing model registry"""
        registry_file = self.registry_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                
                for model_id, meta_dict in data.items():
                    meta_dict['created_at'] = datetime.fromisoformat(
                        meta_dict['created_at']
                    ) if meta_dict.get('created_at') else None
                    meta_dict['deployed_at'] = datetime.fromisoformat(
                        meta_dict['deployed_at']
                    ) if meta_dict.get('deployed_at') else None
                    
                    self.models[model_id] = ModelMetadata(**meta_dict)
                    
                # Restore active model
                active_file = self.registry_path / "active_model.txt"
                if active_file.exists():
                    self._active_model_id = active_file.read_text().strip()
                    
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
    
    def _save_registry(self):
        """Persist registry to disk"""
        registry_file = self.registry_path / "registry.json"
        try:
            with open(registry_file, 'w') as f:
                json.dump(
                    {mid: meta.to_dict() for mid, meta in self.models.items()},
                    f,
                    indent=2
                )
            
            # Save active model reference
            if self._active_model_id:
                active_file = self.registry_path / "active_model.txt"
                active_file.write_text(self._active_model_id)
                
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
    
    def register_model(self,
                      model: BaseEstimator,
                      metadata: ModelMetadata,
                      sample_data: Optional[np.ndarray] = None) -> str:
        """
        Register new model version.
        
        Args:
            model: Trained sklearn model
            metadata: Model metadata
            sample_data: Sample of training data for hash
        
        Returns:
            model_id: Unique identifier
        """
        # Generate model ID
        model_hash = self._compute_model_hash(model, sample_data)
        model_id = f"{metadata.model_name}-{metadata.version}-{model_hash[:8]}"
        
        # Save model artifact
        model_dir = self.registry_path / model_id
        model_dir.mkdir(exist_ok=True)
        
        model_path = model_dir / "model.joblib"
        joblib.dump(model, model_path)
        
        # Save metadata
        metadata.model_id = model_id
        if sample_data is not None:
            metadata.training_data_hash = self._compute_data_hash(sample_data)
        
        meta_path = model_dir / "metadata.json"
        with open(meta_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
        
        # Register
        self.models[model_id] = metadata
        self._save_registry()
        
        logger.info(f"Model registered: {model_id}")
        return model_id
    
    def load_model(self, model_id: Optional[str] = None) -> Tuple[BaseEstimator, ModelMetadata]:
        """
        Load model by ID or active model.
        
        Args:
            model_id: Specific model, or None for active model
        
        Returns:
            (model, metadata) tuple
        """
        target_id = model_id or self._active_model_id
        
        if not target_id:
            raise ValueError("No model ID specified and no active model")
        
        if target_id not in self.models:
            raise ValueError(f"Model {target_id} not found in registry")
        
        model_dir = self.registry_path / target_id
        model_path = model_dir / "model.joblib"
        meta_path = model_dir / "metadata.json"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model artifact not found: {model_path}")
        
        model = joblib.load(model_path)
        metadata = self.models[target_id]
        
        logger.debug(f"Model loaded: {target_id}")
        return model, metadata
    
    def deploy_model(self, model_id: str, shadow: bool = False) -> bool:
        """
        Deploy model to production.
        
        Args:
            model_id: Model to deploy
            shadow: If True, deploy as shadow (A/B testing)
        """
        if model_id not in self.models:
            return False
        
        metadata = self.models[model_id]
        metadata.deployed_at = datetime.utcnow()
        metadata.status = "production"
        
        if shadow:
            self._shadow_model_id = model_id
            logger.info(f"Model {model_id} deployed as shadow")
        else:
            # Promote to active
            if self._active_model_id:
                old_meta = self.models.get(self._active_model_id)
                if old_meta:
                    old_meta.status = "archived"
            
            self._active_model_id = model_id
            logger.info(f"Model {model_id} promoted to active production")
        
        self._save_registry()
        return True
    
    def rollback(self) -> Optional[str]:
        """
        Rollback to previous model version.
        
        Returns:
            ID of rolled-back model, or None if no history
        """
        if not self._active_model_id:
            return None
        
        # Find previous production model
        production_models = [
            (mid, meta) for mid, meta in self.models.items()
            if meta.status == "archived" and meta.deployed_at
        ]
        
        if not production_models:
            return None
        
        # Sort by deployment time, get most recent
        previous = sorted(production_models, key=lambda x: x[1].deployed_at or datetime.min)[-1]
        previous_id = previous[0]
        
        # Rollback
        self.deploy_model(previous_id)
        logger.info(f"Rolled back to {previous_id}")
        
        return previous_id
    
    def compare_models(self, 
                      model_id_a: str, 
                      model_id_b: str) -> Dict:
        """
        Compare two model versions.
        
        Returns:
            Comparison metrics and differences
        """
        if model_id_a not in self.models or model_id_b not in self.models:
            raise ValueError("One or both models not found")
        
        meta_a = self.models[model_id_a]
        meta_b = self.models[model_id_b]
        
        return {
            "model_a": {
                "id": model_id_a,
                "version": meta_a.version,
                "created": meta_a.created_at.isoformat(),
                "metrics": meta_a.metrics
            },
            "model_b": {
                "id": model_id_b,
                "version": meta_b.version,
                "created": meta_b.created_at.isoformat(),
                "metrics": meta_b.metrics
            },
            "metric_differences": {
                k: meta_b.metrics.get(k, 0) - meta_a.metrics.get(k, 0)
                for k in set(meta_a.metrics.keys()) & set(meta_b.metrics.keys())
            },
            "feature_changes": list(set(meta_a.features) ^ set(meta_b.features))
        }
    
    def get_model_lineage(self, model_id: str) -> List[Dict]:
        """Get training lineage for model"""
        if model_id not in self.models:
            return []
        
        target = self.models[model_id]
        
        # Find related models (same name, different versions)
        related = [
            meta for meta in self.models.values()
            if meta.model_name == target.model_name
        ]
        
        return sorted(
            [m.to_dict() for m in related],
            key=lambda x: x.get('created_at', '')
        )
    
    def list_models(self, 
                   status: Optional[str] = None,
                   model_name: Optional[str] = None) -> List[ModelMetadata]:
        """List models with optional filtering"""
        results = list(self.models.values())
        
        if status:
            results = [m for m in results if m.status == status]
        
        if model_name:
            results = [m for m in results if m.model_name == model_name]
        
        return sorted(results, key=lambda x: x.created_at, reverse=True)
    
    def delete_model(self, model_id: str) -> bool:
        """Archive and remove model"""
        if model_id not in self.models:
            return False
        
        # Don't delete active model
        if model_id == self._active_model_id:
            raise ValueError("Cannot delete active production model")
        
        # Archive
        self.models[model_id].status = "deleted"
        
        # Remove files (optional: move to archive instead)
        import shutil
        model_dir = self.registry_path / model_id
        if model_dir.exists():
            shutil.rmtree(model_dir)
        
        del self.models[model_id]
        self._save_registry()
        
        logger.info(f"Model deleted: {model_id}")
        return True
    
    @property
    def active_model_id(self) -> Optional[str]:
        return self._active_model_id
    
    @property
    def shadow_model_id(self) -> Optional[str]:
        return self._shadow_model_id
    
    @staticmethod
    def _compute_model_hash(model: BaseEstimator, 
                           sample_data: Optional[np.ndarray] = None) -> str:
        """Compute hash of model parameters"""
        try:
            params = json.dumps(model.get_params(), sort_keys=True)
            hash_input = params
            
            if sample_data is not None:
                data_hash = hashlib.sha256(sample_data.tobytes()).hexdigest()[:16]
                hash_input += data_hash
            
            return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        except:
            return hashlib.sha256(str(id(model)).encode()).hexdigest()[:16]
    
    @staticmethod
    def _compute_data_hash(data: np.ndarray) -> str:
        """Compute hash of training data sample"""
        return hashlib.sha256(data.tobytes()).hexdigest()[:16]


class ModelAEnsemble:
    """
    Ensemble predictor using active and shadow models.
    For A/B testing and gradual rollout.
    """
    
    def __init__(self, registry: ModelRegistry, shadow_ratio: float = 0.1):
        self.registry = registry
        self.shadow_ratio = shadow_ratio  # 10% traffic to shadow model
        self._rng = np.random.RandomState(42)
    
    def predict(self, X: np.ndarray) -> Tuple[Any, Dict]:
        """
        Predict using active or shadow model based on ratio.
        
        Returns:
            (prediction, metadata about which model was used)
        """
        active_id = self.registry.active_model_id
        shadow_id = self.registry.shadow_model_id
        
        # Decide which model to use
        use_shadow = shadow_id and self._rng.random() < self.shadow_ratio
        
        if use_shadow and shadow_id:
            model, meta = self.registry.load_model(shadow_id)
            model_used = "shadow"
        else:
            model, meta = self.registry.load_model(active_id)
            model_used = "active"
        
        prediction = model.predict(X)
        
        metadata = {
            "model_used": model_used,
            "model_id": meta.model_id,
            "version": meta.version
        }
        
        return prediction, metadata