from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import uuid
from datetime import datetime
import time

from models.schemas import (
    PredictionRequest, 
    PredictionResponse, 
    AnomalyResult,
    SimulationConfig,
    HealthStatus
)
from services.ml_detector import AnomalyDetector
from services.kpi_simulator import TelecomKPISimulator
from utils.logging_config import setup_logging
from utils.exceptions import TelecomAIException, ModelNotTrainedException


logger = setup_logging()
router = APIRouter()

# Global service instances (in production, use dependency injection)
detector = AnomalyDetector()
simulator = TelecomKPISimulator()


@router.post("/predict", response_model=PredictionResponse)
async def predict_anomaly(
    request: PredictionRequest,
    background_tasks: BackgroundTasks
):
    """
    Predict anomaly for a single gNB KPI measurement.
    
    This endpoint mimics NWDAF's "Nnwdaf_AnalyticsInfo" service operation.
    In 5G Core, AMF/SMF would call this to get network analytics.
    """
    start_time = time.time()
    
    try:
        # Perform prediction
        result = detector.predict(request)
        
        # Determine recommended action (SON-style automation)
        action = _determine_action(result, request.metrics)
        
        processing_time = (time.time() - start_time) * 1000
        
        response = PredictionResponse(
            prediction_id=str(uuid.uuid4()),
            gnb_id=request.gnb_id,
            timestamp=datetime.utcnow(),
            metrics=request.metrics,
            result=result,
            recommended_action=action,
            processing_time_ms=processing_time
        )
        
        # Async logging for high-throughput scenarios
        background_tasks.add_task(_log_prediction, response)
        
        return response
        
    except ModelNotTrainedException as e:
        logger.error(f"Model not trained: {e.message}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": e.error_code,
                "message": e.message,
                "resolution": "POST /train to initialize model"
            }
        )
    except TelecomAIException as e:
        logger.error(f"Telecom AI error: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal processing error")


@router.post("/predict/batch", response_model=List[PredictionResponse])
async def predict_batch(requests: List[PredictionRequest]):
    """
    Batch prediction for multiple gNBs.
    Efficient for RIC (RAN Intelligent Controller) periodic polling.
    """
    if not detector.is_trained:
        raise HTTPException(
            status_code=503,
            detail="Model not trained. Call /train first."
        )
    
    start_time = time.time()
    results = detector.batch_predict(requests)
    
    responses = []
    for req, res in zip(requests, results):
        action = _determine_action(res, req.metrics)
        responses.append(PredictionResponse(
            prediction_id=str(uuid.uuid4()),
            gnb_id=req.gnb_id,
            timestamp=datetime.utcnow(),
            metrics=req.metrics,
            result=res,
            recommended_action=action,
            processing_time_ms=(time.time() - start_time) * 1000 / len(requests)
        ))
    
    return responses


@router.post("/train")
async def train_model(config: SimulationConfig = SimulationConfig()):
    """
    Initialize and train the anomaly detection model.
    Generates synthetic training data and fits Isolation Forest.
    
    In production, this would fetch historical data from PM/CM databases.
    """
    try:
        # Generate training data
        logger.info(f"Generating {config.duration_hours}h of training data")
        df = simulator.generate_training_data(
            hours=config.duration_hours,
            anomaly_rate=config.anomaly_rate
        )
        
        # Train model
        metrics = detector.train(df)
        
        return {
            "status": "success",
            "training_metrics": metrics,
            "simulation_stats": simulator.get_statistics(df),
            "model_info": detector.get_model_info()
        }
        
    except Exception as e:
        logger.error(f"Training failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/simulate/anomaly")
async def simulate_anomaly_scenario(scenario: str = "congestion"):
    """
    Generate anomalous KPI data for testing.
    Scenarios: congestion, rf_interference, transport_issue, hardware_degradation
    """
    valid_scenarios = ["congestion", "rf_interference", "transport_issue", "hardware_degradation", "normal"]
    
    if scenario not in valid_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario. Choose from: {valid_scenarios}"
        )
    
    kpi = simulator.generate_single_kpi("gNB_TEST", scenario=scenario)
    
    # Create prediction request
    request = PredictionRequest(
        gnb_id=f"gNB_TEST_{scenario}",
        metrics=kpi
    )
    
    # Get prediction if model trained
    if detector.is_trained:
        result = detector.predict(request)
        return {
            "scenario": scenario,
            "generated_metrics": kpi.dict(),
            "anomaly_detection": result.dict()
        }
    else:
        return {
            "scenario": scenario,
            "generated_metrics": kpi.dict(),
            "note": "Model not trained - no prediction available"
        }


def _determine_action(result: AnomalyResult, metrics) -> str:
    """
    Determine recommended action based on SON (Self-Organizing Network) principles.
    """
    if not result.is_anomaly:
        return "CONTINUE_MONITORING"
    
    if result.severity == "critical":
        if "prb_usage" in result.contributing_features:
            return "TRIGGER_LOAD_BALANCING: Initiate handover to neighbor cells"
        elif "latency" in result.contributing_features:
            return "ALERT_CORE_TEAM: Check transport layer and UPF status"
        else:
            return "ESCALATE_TO_L2: Immediate engineer intervention required"
    
    elif result.severity == "warning":
        if metrics.prb_usage > 80:
            return "PREPARE_LOAD_BALANCING: Monitor for congestion trend"
        elif metrics.latency > 50:
            return "CHECK_BACKHAUL: Verify transport network health"
        else:
            return "INCREASE_MONITORING: Collect detailed traces"
    
    return "INVESTIGATE_ANOMALY"


def _log_prediction(response: PredictionResponse) -> None:
    """Async logging for analytics"""
    logger.info(
        f"Prediction logged: {response.prediction_id}, "
        f"gNB={response.gnb_id}, anomaly={response.result.is_anomaly}"
    )


# Data source endpoints (Phase 4: Real log integration)

@router.get("/data-source/status")
async def get_data_source_status(request: Request) -> Dict[str, Any]:
    """
    Get current data source configuration and status.
    
    Returns info about whether using simulator or real logs,
    plus source-specific metadata.
    """
    provider = request.app.data_provider
    
    if not provider:
        return {
            "status": "error",
            "message": "Data provider not initialized"
        }
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "available": provider.is_available(),
        "source_info": provider.get_source_info()
    }


@router.get("/logs/status")
async def get_logs_status(request: Request) -> Dict[str, Any]:
    """
    Get status of log file data source.
    
    Returns:
    - logs_path: Directory being monitored
    - nfs_monitored: Network functions being parsed
    - last_parse_time: When logs were last processed
    - parse_rate: Records parsed per minute
    """
    provider = request.app.data_provider
    monitor = request.app.pipeline_monitor
    
    if not provider or not monitor:
        return {"error": "Services not initialized"}
    
    source_info = provider.get_source_info()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "data_source": source_info.get("type", "unknown"),
        "base_path": source_info.get("base_path"),
        "watched_nfs": source_info.get("watched_nfs", []),
        "is_ready": source_info.get("is_ready", False),
        "parse_rate_per_minute": monitor.get_parse_rate_per_minute(),
        "source_details": source_info
    }


@router.post("/kpi/batch/from-data-source")
async def get_kpi_batch(
    request: Request,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get next batch of KPI records from current data source.
    
    Used to fetch real log data or simulator data for batch processing.
    
    Args:
        limit: Max number of records to return (default 100)
    
    Returns:
    - records: List of KPI records with anomaly labels
    - source: Whether records came from "simulator" or "logs"
    - count: Number of records returned
    """
    provider = request.app.data_provider
    detector = request.app.anomaly_detector
    monitor = request.app.pipeline_monitor
    
    if not provider or not detector:
        raise HTTPException(
            status_code=503,
            detail="Data provider or detector not initialized"
        )
    
    try:
        # Get batch from data provider
        batch = provider.get_next_batch(limit)
        
        if not batch:
            return {
                "records": [],
                "source": provider.get_source_info().get("type", "unknown"),
                "count": 0
            }
        
        # Apply anomaly detection
        results = []
        for record in batch:
            is_anomaly, reason = detector.detect(record)
            
            # Track in monitor
            if monitor:
                monitor.record_anomaly(record.gnb_id, is_anomaly)
            
            results.append({
                "timestamp": record.timestamp.isoformat(),
                "gnb_id": record.gnb_id,
                "prb_usage": record.prb_usage,
                "throughput": record.throughput,
                "latency": record.latency,
                "packet_loss": record.packet_loss,
                "is_anomaly": is_anomaly,
                "anomaly_reason": reason,
                "source": record.source
            })
        
        return {
            "records": results,
            "source": provider.get_source_info().get("type", "unknown"),
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error fetching KPI batch: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching batch: {str(e)}")
