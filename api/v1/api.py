from fastapi import APIRouter

from api.v1.endpoints import prediction, health, nwdaf, xapp, monitoring

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    prediction.router,
    prefix="/ml",
    tags=["ml-anomaly-detection"]
)

# Phase 2: NWDAF routes
api_router.include_router(
    nwdaf.router,
    prefix="/nwdaf",
    tags=["nwdaf-analytics"]
)

# Phase 3: xApp routes
api_router.include_router(
    xapp.router,
    prefix="/xapp",
    tags=["oran-xapp"]
)

# Phase 4: Monitoring and observability routes
api_router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"]
)
