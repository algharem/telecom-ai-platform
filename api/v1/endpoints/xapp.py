# api/v1/endpoints/xapp.py - Complete fixed version

from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime  # Missing import
from typing import List, Optional

from services.oran_xapp import SmartOptimizerXApp
from services.ml_detector import AnomalyDetector
from services.kpi_simulator import TelecomKPISimulator
from services.nwdaf_analytics import NWDAFAnalyticsEngine  # MISSING IMPORT
from models.schemas import (
    ControlDecision,
    XAppStatus,
    RANMetric,
    RICControlActionType,
    PredictionRequest
)
from utils.logging_config import setup_logging


logger = setup_logging()
router = APIRouter()

# Global instances - properly initialized
detector = AnomalyDetector()
simulator = TelecomKPISimulator(base_stations=5)
nwdaf_engine = NWDAFAnalyticsEngine(detector, simulator)  # NOW IMPORTED
xapp = SmartOptimizerXApp(
    xapp_id="xapp-smart-optimizer",
    nwdaf_engine=nwdaf_engine,
    detector=detector
)


@router.on_event("startup")
async def startup_xapp():
    """Initialize xApp on API startup"""
    try:
        # Register with RIC (simulated)
        await xapp.register_with_ric("http://ric.platform:8080")
        
        # Subscribe to E2 nodes
        await xapp.subscribe_to_e2_nodes(["gNB_001", "gNB_002", "gNB_003"])
        
        # Start control loop
        await xapp.start_control_loop(interval_ms=10000)
        
        logger.info("xApp startup complete")
    except Exception as e:
        logger.error(f"xApp startup failed: {e}", exc_info=True)
        # Don't raise - allow API to start even if xApp has issues


@router.on_event("shutdown")
async def shutdown_xapp():
    """Graceful shutdown"""
    try:
        await xapp.stop()
        logger.info("xApp shutdown complete")
    except Exception as e:
        logger.error(f"xApp shutdown error: {e}")


@router.get("/status", response_model=XAppStatus)
async def get_xapp_status():
    """Get xApp runtime status"""
    return xapp.status


# @router.on_event("startup")
# async def startup_xapp():
#     """Initialize xApp on API startup"""
#     # Register with RIC (simulated)
#     await xapp.register_with_ric("http://ric.platform:8080")
    
#     # Subscribe to E2 nodes
#     # await xapp.subscribe_to_e2_nodes(["gNB_001", "gNB_002", "gNB_003"])
#     await xapp.subscribe_to_e2_nodes(["gNB_001", "gNB_002", "gNB_003"])

#     # Start control loop
#     await xapp.start_control_loop(interval_ms=10000)


# @router.on_event("shutdown")
# async def shutdown_xapp():
#     """Graceful shutdown"""
#     await xapp.stop()


# @router.get("/status", response_model=XAppStatus)
# async def get_xapp_status():
#     """Get xApp runtime status"""
#     return xapp.status


@router.post("/control/start")
async def start_control():
    """Start control loop manually"""
    if xapp.status.control_loop_active:
        return {"status": "already_running"}
    
    await xapp.start_control_loop()
    return {"status": "started"}


@router.post("/control/stop")
async def stop_control():
    """Stop control loop"""
    await xapp.stop()
    return {"status": "stopped"}


@router.get("/decisions", response_model=List[ControlDecision])
async def get_decisions(
    limit: int = 100,
    action_type: Optional[RICControlActionType] = None
):
    """Get recent control decisions"""
    decisions = xapp.get_decision_history(limit=limit, action_type=action_type)
    return decisions


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str):
    """Get specific decision details"""
    for decision in xapp.decision_log:
        if decision.decision_id == decision_id:
            return decision
    raise HTTPException(status_code=404, detail="Decision not found")


@router.get("/ue/{ue_id}/state")
async def get_ue_state(ue_id: str):
    """Get UE handover state"""
    state = xapp.get_ue_state(ue_id)
    if not state:
        raise HTTPException(status_code=404, detail="UE not found")
    
    return {
        "ue_id": state.ue_id,
        "handover_count": state.handover_count,
        "last_handover": state.last_handover,
        "source_cells": state.source_cells,
        "recent_handover_rate": "high" if state.handover_count > 2 else "normal"
    }


@router.get("/cells/{gnb_id}/load")
async def get_cell_load(gnb_id: str):
    """Get cell load history"""
    if gnb_id not in xapp.cell_load_history:
        raise HTTPException(status_code=404, detail="No data for this cell")
    
    history = xapp.cell_load_history[gnb_id]
    return {
        "gnb_id": gnb_id,
        "current_load": history[-1] if history else None,
        "load_history": history[-20:],  # Last 20 samples
        "trend": "increasing" if len(history) > 2 and history[-1] > history[-5] else "stable"
    }


@router.post("/simulate/ran-metric")
async def simulate_ran_metric(gnb_id: str):
    """
    Inject simulated RAN metric for testing.
    Triggers event-driven control decision.
    """
    from oran.e2_interface import E2APHandler
    from oran.e2_interface import E2APHandler, E2Subscription

    # Generate metric
    handler = E2APHandler()
    sub = E2Subscription(
        subscription_id="test",
        gnb_id=gnb_id,
        ran_function_id=1,
        event_trigger="PERIODIC",
        reporting_period_ms=100
    )
    
    metric = handler._generate_simulated_metric(sub)
    
    # Trigger callback
    await xapp._on_ran_indication(metric)
    
    return {
        "status": "metric_injected",
        "gnb_id": gnb_id,
        "cell_load": metric.cell_state.prb_dl_used,
        "active_ues": metric.cell_state.active_ues
    }


@router.get("/policies")
async def get_policies():
    """Get active policy summary"""
    return xapp.policy_engine.get_policy_summary()