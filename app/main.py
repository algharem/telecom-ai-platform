from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

from app.config import settings
from api.v1.api import api_router
from utils.logging_config import setup_logging
from utils.exceptions import TelecomAIException


# logger = setup_logging(settings.DEBUG)
# logger = setup_logging(settings.DEBUG, log_format="json")
logger = setup_logging("DEBUG" if settings.DEBUG else "INFO", log_format="json")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    AI-Driven Telecom Network Optimization Platform - Phase 1
    
    This API provides:
    - Real-time RAN KPI anomaly detection using Isolation Forest
    - Synthetic KPI generation for testing
    - 3GPP NWDAF-style analytics interface
    
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
