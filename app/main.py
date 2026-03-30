from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import os

from app.config import settings
from api.v1.api import api_router
from utils.logging_config import setup_logging
from utils.exceptions import TelecomAIException
from services.data_provider import create_data_provider, get_provider_config
from services.anomaly_detector import AnomalyDetector
from services.pipeline_monitor import PipelineMonitor
from parsers.aggregators.gnb_aggregator import GnBMetricsAggregator


# logger = setup_logging(settings.DEBUG)
# logger = setup_logging(settings.DEBUG, log_format="json")
logger = setup_logging("DEBUG" if settings.DEBUG else "INFO", log_format="json")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    AI-Driven Telecom Network Optimization Platform - Phase 1+2
    
    This API provides:
    - Real-time RAN KPI anomaly detection using Isolation Forest
    - Open5GS log parsing and aggregation (real-world data)
    - Synthetic KPI generation for testing (simulator fallback)
    - 3GPP NWDAF-style analytics interface
    
    ## Data Sources
    
    * **Simulator**: Synthetic KPI generation with configurable anomalies
    * **Logs**: Real Open5GS network function logs (AMF, UPF, NRF, AUSF)
    
    ## Telecom Context
    
    * **PRB Usage**: Physical Resource Block utilization (0-100%)
    * **Throughput**: User plane data rate (Mbps)
    * **Latency**: Round-trip time (ms)
    * **Packet Loss**: IP packet drop rate (%)
    
    ## Architecture Alignment
    
    * 3GPP TS 28.552 (5G Performance Measurements)
    * O-RAN RIC architecture (xApp data source)
    * ETSI NFV MANO monitoring
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global services (initialized on startup)
app.data_provider = None
app.anomaly_detector = None
app.pipeline_monitor = None
app.gnb_aggregator = None

# Middleware
@app.middleware("http")
async def add_telecom_headers(request: Request, call_next):
    """Add telecom-specific headers for tracing"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Telecom-Service"] = "anomaly-detection"
    
    return response

# CORS (for web dashboards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize data pipeline and AI services on startup"""
    try:
        # Determine data source (default to simulator)
        data_source = os.getenv("DATA_SOURCE", "simulator").lower()
        logger.info(f"[STARTUP] Initializing data source: {data_source}")
        
        # Create data provider
        provider_config = get_provider_config(data_source)
        app.data_provider = create_data_provider(data_source, provider_config)
        logger.info(f"[STARTUP] Data provider initialized: {app.data_provider.get_source_info()}")
        
        # Initialize anomaly detector with thresholds
        anomaly_config = {
            "prb_usage_percent": float(os.getenv("ANOMALY_PRB_THRESHOLD", 90)),
            "latency_ms": float(os.getenv("ANOMALY_LATENCY_THRESHOLD", 50)),
            "packet_loss_percent": float(os.getenv("ANOMALY_PACKET_LOSS_THRESHOLD", 1)),
        }
        app.anomaly_detector = AnomalyDetector(anomaly_config)
        logger.info("[STARTUP] Anomaly detector initialized")
        
        # Initialize monitoring
        app.pipeline_monitor = PipelineMonitor(retention_minutes=60)
        logger.info("[STARTUP] Pipeline monitor initialized")
        
        # Initialize gNB aggregator for log processing
        app.gnb_aggregator = GnBMetricsAggregator(window_seconds=60)
        logger.info("[STARTUP] gNB aggregator initialized")
        
        logger.info("[STARTUP] All services initialized successfully")
        
    except Exception as e:
        logger.error(f"[STARTUP] Failed to initialize services: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        if app.data_provider:
            app.data_provider.close()
            logger.info("[SHUTDOWN] Data provider closed")
        
        if app.gnb_aggregator:
            # Flush any pending windows
            pending = app.gnb_aggregator.flush()
            logger.info(f"[SHUTDOWN] Flushed {len(pending)} pending windows")
        
        logger.info("[SHUTDOWN] Cleanup complete")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error during cleanup: {e}", exc_info=True)

# Exception handlers
@app.exception_handler(TelecomAIException)
async def telecom_exception_handler(request: Request, exc: TelecomAIException):
    logger.error(f"Telecom error: {exc.message}", extra={
        "error_code": exc.error_code,
        "request_id": getattr(request.state, 'request_id', 'unknown')
    })
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "request_id": getattr(request.state, 'request_id', 'unknown')
        }
    )

# Include routers
app.include_router(api_router, prefix="/api/v1")

# Update root endpoint
@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": "Phase 3 - O-RAN xApp Decision Engine",
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health/health",
            "ml_predict": "/api/v1/ml/predict",
            "nwdaf_subscribe": "/api/v1/nwdaf/subscriptions",
            "nwdaf_analytics": "/api/v1/nwdaf/analytics/request",
            "xapp_status": "/api/v1/xapp/status",
            "xapp_decisions": "/api/v1/xapp/decisions"
        },
        "telecom_standards": [
            "3GPP_TS28.552", 
            "3GPP_TS29.520",
            "3GPP_TS38.463",      # E2AP
            "O-RAN_WG2",          # Near-RT RIC
            "O-RAN_WG3",          # E2 Interface
            "ETSI_NFV"
        ],
        "features": [
            "Real-time anomaly detection (Phase 1)",
            "NWDAF analytics service (Phase 2)",
            "O-RAN xApp control loop (Phase 3)",
            "E2 interface simulation",
            "Admission control",
            "Load balancing",
            "Handover management"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
