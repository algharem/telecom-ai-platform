"""
Monitoring and observability endpoints for pipeline health tracking.

Provides endpoints to:
- Check overall pipeline health
- Monitor parse rates and success rates per NF
- Track anomaly detection statistics
- View data source status
"""

from fastapi import APIRouter, Request
from datetime import datetime
from typing import Dict, Any, Optional

router = APIRouter()


@router.get("/health")
async def get_health_status(request: Request) -> Dict[str, Any]:
    """
    Get overall pipeline health status.
    
    Returns:
    - status: "healthy", "degraded", or "critical"
    - uptime_seconds: How long the service has been running
    - total_records_processed: Total KPI records processed
    - total_anomalies_detected: Count of detected anomalies
    - parse_success_rate: Overall parsing success percentage
    - data_freshness_seconds: Average lag between log time and processing
    """
    monitor = request.app.pipeline_monitor
    
    if not monitor:
        return {
            "status": "unknown",
            "message": "Pipeline monitor not initialized"
        }
    
    health = monitor.get_health_status()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "status": health["status"],
        "uptime_seconds": health["uptime_seconds"],
        "records_processed": health["total_records_processed"],
        "anomalies_detected": health["total_anomalies_detected"],
        "overall_anomaly_rate": health["overall_anomaly_rate"],
        "parse_success_rate": f"{health['parse_success_rate']:.1f}%",
        "data_freshness_seconds": health["data_freshness_seconds"],
        "monitoring": {
            "nfs": health["nfs_monitored"],
            "gnbs": health["gnbs_monitored"]
        }
    }


@router.get("/stats")
async def get_pipeline_stats(request: Request) -> Dict[str, Any]:
    """
    Get comprehensive pipeline statistics.
    
    Returns breakdown by NF and gNB with parse rates and anomaly counts.
    """
    monitor = request.app.pipeline_monitor
    
    if not monitor:
        return {"error": "Pipeline monitor not initialized"}
    
    stats = monitor.get_stats()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "health": stats["health"],
        "nf_stats": stats["nf_breakdown"],
        "gnb_stats": stats["gnb_breakdown"],
        "metrics_retained": stats["metrics_retained"]
    }


@router.get("/nf/{nf_type}")
async def get_nf_stats(
    request: Request,
    nf_type: str
) -> Dict[str, Any]:
    """
    Get detailed stats for a specific Network Function.
    
    Args:
        nf_type: NF type (amf, upf, nrf, ausf)
    
    Returns:
    - total_parsed: Total events successfully parsed
    - total_errors: Total parse failures
    - recent_success_rate: Success rate in last few minutes
    - error_trend: "increasing", "decreasing", or "stable"
    """
    monitor = request.app.pipeline_monitor
    
    if not monitor:
        return {"error": "Pipeline monitor not initialized"}
    
    stats = monitor.get_nf_stats(nf_type)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "nf_type": nf_type,
        "total_parsed": stats["total_parsed"],
        "total_errors": stats["total_errors"],
        "recent_success_rate": f"{stats['recent_success_rate']:.1f}%",
        "error_trend": stats["error_trend"],
        "last_update": stats["last_update"]
    }


@router.get("/gnb/{gnb_id}")
async def get_gnb_stats(
    request: Request,
    gnb_id: str
) -> Dict[str, Any]:
    """
    Get detailed stats for a specific gNB.
    
    Args:
        gnb_id: gNB identifier (e.g., gNB_001)
    
    Returns:
    - total_records: Total records processed for this gNB
    - total_anomalies: Total anomalies detected
    - anomaly_rate: Percentage of records that were anomalous
    - anomaly_breakdown: Count by anomaly type
    """
    monitor = request.app.pipeline_monitor
    
    if not monitor:
        return {"error": "Pipeline monitor not initialized"}
    
    stats = monitor.get_gnb_stats(gnb_id)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "gnb_id": gnb_id,
        "total_records": stats["total_records"],
        "total_anomalies": stats["total_anomalies"],
        "anomaly_rate": f"{stats['anomaly_rate']:.2f}%",
        "recent_anomaly_types": stats["recent_anomaly_types"],
        "last_update": stats["last_update"]
    }


@router.get("/data-source")
async def get_data_source(request: Request) -> Dict[str, Any]:
    """
    Get current data source configuration and status.
    
    Returns:
    - type: "simulator" or "logs"
    - status: "available" or "unavailable"
    - source_info: Provider-specific metadata
    """
    provider = request.app.data_provider
    
    if not provider:
        return {"error": "Data provider not initialized"}
    
    return {
        "timestamp": datetime.now().isoformat(),
        "source": provider.get_source_info(),
        "is_available": provider.is_available(),
        "status": "available" if provider.is_available() else "unavailable"
    }


@router.get("/parse-rate")
async def get_parse_rate(
    request: Request,
    nf_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get current parsing rate.
    
    Args:
        nf_type: Optional - filter by NF type (amf, upf, etc.)
    
    Returns:
    - parse_rate: Records parsed per minute
    - nf_type: Filter applied (if any)
    """
    monitor = request.app.pipeline_monitor
    
    if not monitor:
        return {"error": "Pipeline monitor not initialized"}
    
    rate = monitor.get_parse_rate_per_minute(nf_type)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "parse_rate_per_minute": rate,
        "nf_type_filter": nf_type or "all"
    }


@router.get("/anomaly-rates")
async def get_anomaly_rates(request: Request) -> Dict[str, Any]:
    """
    Get anomaly rates per gNB.
    
    Returns:
    - anomaly_rates: Dict of {gnb_id: anomaly_rate_percent}
    """
    monitor = request.app.pipeline_monitor
    
    if not monitor:
        return {"error": "Pipeline monitor not initialized"}
    
    rates = monitor.get_anomaly_rate_per_gnb()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "anomaly_rates": {
            gnb: f"{rate:.2f}%" for gnb, rate in rates.items()
        }
    }


@router.get("/detector-stats")
async def get_detector_stats(request: Request) -> Dict[str, Any]:
    """
    Get anomaly detector statistics.
    
    Returns:
    - total_checked: Total records evaluated
    - total_anomalies: Total anomalies detected
    - anomaly_rate: Overall anomaly percentage
    - breakdown: Anomaly count by type (congestion, latency, etc.)
    """
    detector = request.app.anomaly_detector
    
    if not detector:
        return {"error": "Anomaly detector not initialized"}
    
    stats = detector.get_stats()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_checked": stats["total_checked"],
        "total_anomalies": stats["total_anomalies"],
        "anomaly_rate": f"{stats['anomaly_rate']:.2f}%",
        "tracked_gnbs": stats["tracked_gnbs"],
        "anomaly_breakdown": stats["anomaly_breakdown"]
    }


@router.get("/aggregator-stats")
async def get_aggregator_stats(request: Request) -> Dict[str, Any]:
    """
    Get gNB metrics aggregator statistics.
    
    Returns:
    - active_gnbs: Number of gNBs with active windows
    - active_windows: Total open aggregation windows
    - completed_windows: Total windows processed
    - metrics_added: Total metrics received
    """
    aggregator = request.app.gnb_aggregator
    
    if not aggregator:
        return {"error": "gNB aggregator not initialized"}
    
    stats = aggregator.get_stats()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "active_gnbs": stats["total_gnbs_active"],
        "active_windows": stats["active_windows"],
        "completed_windows": stats["completed_windows"],
        "total_metrics_added": stats["total_metrics_added"],
        "completed_pending": stats["completed_pending"]
    }
