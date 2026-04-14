from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Dict
from datetime import datetime, timedelta

from models.schemas import (
    NWDAFSubscriptionRequest,
    NWDAFSubscriptionResponse,
    NWDAFAnalyticsRequest,
    NWDAFAnalyticsResponse,
    LoadLevelInfo,
    ServiceExperienceInfo,
    AnalyticsType
)
from services.nwdaf_analytics import NWDAFAnalyticsEngine
from services.ml_detector import AnomalyDetector
from services.kpi_simulator import TelecomKPISimulator
from utils.logging_config import setup_logging
from utils.exceptions import NWDAFException, SubscriptionNotFoundException


logger = setup_logging()
router = APIRouter()

# Service instances (use DI in production)
detector = AnomalyDetector()
simulator = TelecomKPISimulator()
nwdaf_engine = NWDAFAnalyticsEngine(detector, simulator)


@router.on_event("startup")
async def startup_nwdaf():
    """Initialize NWDAF background tasks"""
    await nwdaf_engine.start()


@router.on_event("shutdown")
async def shutdown_nwdaf():
    """Graceful shutdown"""
    await nwdaf_engine.stop()


@router.post("/subscriptions", response_model=NWDAFSubscriptionResponse)
async def create_subscription(request: NWDAFSubscriptionRequest):
    """
    Nnwdaf_AnalyticsSubscription_Subscribe
    
    Allows 5G NFs (AMF, SMF, PCF) to subscribe to network analytics.
    Example: AMF subscribes to load levels for load balancing decisions.
    """
    try:
        sub_id = await nwdaf_engine.subscribe(
            nf_type=request.nf_type,
            nf_instance_id=request.nf_instance_id,
            analytics_type=request.analytics_type,
            target_gnbs=request.target_gnbs,
            notification_uri=request.notification_uri,
            reporting_threshold=request.reporting_threshold
        )
        
        expires = datetime.utcnow() + timedelta(seconds=request.validity_period_seconds)
        
        return NWDAFSubscriptionResponse(
            subscription_id=sub_id,
            nf_type=request.nf_type,
            analytics_type=request.analytics_type,
            target_gnbs=request.target_gnbs,
            created_at=datetime.utcnow(),
            expires_at=expires,
            notification_uri=request.notification_uri
        )
        
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """Nnwdaf_AnalyticsSubscription_Unsubscribe"""
    try:
        success = await nwdaf_engine.unsubscribe(subscription_id)
        if success:
            return {"status": "deleted", "subscription_id": subscription_id}
    except SubscriptionNotFoundException:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics/request", response_model=NWDAFAnalyticsResponse)
async def request_analytics(request: NWDAFAnalyticsRequest):
    """
    Nnwdaf_AnalyticsInfo_Request
    
    On-demand analytics query. Used by NFs to get current network state.
    Priority field for emergency scenarios (e.g., handover assistance).
    """
    import time
    start = time.time()
    
    try:
        # Get analytics from engine
        analytics_data = await nwdaf_engine.get_analytics(
            request.analytics_type,
            request.target_gnb,
            request.time_window_hours
        )
        
        # Build response based on analytics type
        response_data = {
            "analytics_type": request.analytics_type,
            "timestamp": datetime.utcnow(),
            "target_gnb": request.target_gnb,
            "load_level": None,
            "service_experience": None,
            "anomaly_summary": None
        }
        
        if request.analytics_type == AnalyticsType.LOAD_LEVEL:
            ll = analytics_data  # LoadLevelAnalytics dataclass
            response_data["load_level"] = LoadLevelInfo(
                gnb_id=ll.gnb_id,
                load_level=ll.load_level,
                load_level_status=_classify_load(ll.load_level),
                confidence=ll.confidence,
                trend=ll.trend_direction,
                forecast_next_hours=ll.forecast_24h,
                congestion_probability_24h=ll.congestion_probability,
                recommended_action=_load_recommendation(ll)
            )
            
        elif request.analytics_type == AnalyticsType.SERVICE_EXPERIENCE:
            se = analytics_data  # ServiceExperienceAnalytics dataclass
            response_data["service_experience"] = ServiceExperienceInfo(
                gnb_id=se.gnb_id,
                predicted_mos=se.predicted_mos,
                qos_class=_classify_qos(se.predicted_mos),
                throughput_experience=se.throughput_experience,
                latency_experience=se.latency_experience,
                confidence=se.confidence
            )
            
        elif request.analytics_type == AnalyticsType.ANOMALY_EVENTS:
            response_data["anomaly_summary"] = analytics_data
        
        processing_time = (time.time() - start) * 1000
        
        return NWDAFAnalyticsResponse(
            **response_data,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Analytics request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def list_subscriptions():
    """Admin: List active subscriptions"""
    return nwdaf_engine.get_subscription_stats()


@router.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details"""
    if subscription_id not in nwdaf_engine.subscriptions:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    sub = nwdaf_engine.subscriptions[subscription_id]
    return {
        "subscription_id": sub.subscription_id,
        "nf_type": sub.nf_type,
        "nf_instance_id": sub.nf_instance_id,
        "analytics_type": sub.analytics_type.value,
        "target_gnbs": sub.target_gnbs,
        "notification_uri": sub.notification_uri,
        "created_at": sub.created_at,
        "last_notification": sub.last_notification,
        "notification_count": sub.notification_count
    }


# ==========================================
# Integration with Phase 1
# ==========================================

@router.post("/ingest/from-detector")
async def ingest_from_detector(gnb_id: str, background_tasks: BackgroundTasks):
    """
    Bridge endpoint: Take output from Phase 1 ML detector,
    store in NWDAF time-series DB for analytics.
    """
    # Simulate getting latest metrics
    kpi = simulator.generate_single_kpi(gnb_id, "normal")
    
    # Ingest into NWDAF
    await nwdaf_engine.ingest_kpi(gnb_id, kpi)
    
    return {
        "status": "ingested",
        "gnb_id": gnb_id,
        "metrics": kpi.dict(),
        "timestamp": datetime.utcnow()
    }


# Helper functions

def _classify_load(load_level: int) -> str:
    if load_level < 30:
        return "low"
    elif load_level < 60:
        return "medium"
    elif load_level < 85:
        return "high"
    else:
        return "overload"


def _classify_qos(mos: float) -> str:
    if mos >= 4.0:
        return "premium"
    elif mos >= 3.0:
        return "standard"
    else:
        return "best_effort"


def _load_recommendation(ll) -> str:
    if ll.congestion_probability > 0.7:
        return "URGENT: Initiate load balancing and scale capacity"
    elif ll.congestion_probability > 0.4:
        return "PLAN: Prepare additional resources for predicted peak"
    elif ll.trend_direction == "increasing":
        return "MONITOR: Watch for capacity exhaustion"
    else:
        return "MAINTAIN: Current capacity sufficient"