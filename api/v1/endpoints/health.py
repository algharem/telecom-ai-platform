from fastapi import APIRouter
from datetime import datetime
import time

from models.schemas import HealthStatus
from services.ml_detector import AnomalyDetector


router = APIRouter()
detector = AnomalyDetector()

# Simple uptime tracking
start_time = time.time()


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Service health check for Kubernetes probes.
    Returns model status and basic metrics.
    """
    return HealthStatus(
        status="healthy",
        version="1.0.0",
        # model_trained=detector.is_trained,
        is_trained=detector.is_trained,  # updated
        uptime_seconds=time.time() - start_time,
        total_predictions=detector.prediction_count
    )


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes readiness probe.
    Service is ready when model is trained.
    """
    if not detector.is_trained:
        return {
            "status": "not_ready",
            "reason": "ML model not trained"
        }
    return {"status": "ready"}


@router.get("/model/info")
async def model_info():
    """Detailed model information for debugging"""
    return detector.get_model_info()