"""
Phase 4: Event Streaming Models
Defines Kafka/MQTT event schemas for RAN telemetry and anomaly detection
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event type classification"""
    RAN_METRIC = "ran_metric"
    ANOMALY_DETECTED = "anomaly_detected"
    ALARM = "alarm"
    INCIDENT = "incident"
    RECOVERY = "recovery"
    RECOMMENDATION = "recommendation"
    FORECAST = "forecast"


class SeverityLevel(str, Enum):
    """Event severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AnomalyType(str, Enum):
    """Anomaly classifications"""
    CONGESTION = "congestion"
    LATENCY = "latency"
    PACKET_LOSS = "packet_loss"
    THROUGHPUT_DROP = "throughput_drop"
    AUTH_FAILURE = "auth_failure"
    REGISTRATION_FAILURE = "registration_failure"
    SESSION_DROP = "session_drop"
    QOS_DEGRADATION = "qos_degradation"


class RANMetricEvent(BaseModel):
    """KPI metrics from RAN data sources"""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.RAN_METRIC)
    
    # Source information
    source: str = Field(..., description="Data source (prometheus/logs/simulator)")
    gnb_id: str = Field(..., description="gNB identifier")
    cell_id: Optional[str] = Field(None, description="Cell identifier")
    
    # KPI metrics
    prb_usage: float = Field(..., ge=0, le=100)
    throughput: float = Field(..., ge=0)
    latency: float = Field(..., ge=0)
    packet_loss: float = Field(..., ge=0, le=100)
    
    # Metadata
    is_anomaly: bool = Field(default=False)
    confidence: float = Field(default=1.0, ge=0, le=1)


class AnomalyDetectedEvent(BaseModel):
    """Anomaly detection alert event"""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.ANOMALY_DETECTED)
    severity: SeverityLevel = Field(...)
    
    # Source context
    gnb_id: str = Field(...)
    anomaly_types: List[AnomalyType] = Field(...)
    
    # Detection details
    detection_method: str = Field(..., description="ml/pattern/hybrid")
    anomaly_score: float = Field(..., ge=0, le=1)
    explanation: str = Field(...)
    
    # Affected metrics
    affected_metrics: Dict[str, float] = Field(default_factory=dict)
    
    # Correlation
    correlation_id: Optional[str] = Field(None, description="Link to related events")


class AlarmEvent(BaseModel):
    """Network alarm/fault event"""
    event_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.ALARM)
    severity: SeverityLevel = Field(...)
    
    # Alarm classification
    alarm_type: str = Field(..., description="e.g., 'link_down', 'high_cpu', 'low_memory'")
    alarm_code: int = Field(..., description="Numeric alarm code")
    
    # Context
    affected_element: str = Field(..., description="Component/NF/gNB")
    description: str = Field(...)
    
    # State
    is_clear: bool = Field(default=False, description="True if alarm is cleared")
    clear_reason: Optional[str] = Field(None)


class IncidentEvent(BaseModel):
    """Incident event (orchestrated from anomalies/alarms)"""
    event_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.INCIDENT)
    severity: SeverityLevel = Field(...)
    
    # Incident details
    incident_title: str = Field(...)
    incident_description: str = Field(...)
    root_cause: Optional[str] = Field(None)
    
    # Context
    affected_gnbs: List[str] = Field(default_factory=list)
    affected_users_count: Optional[int] = Field(None)
    impact_score: float = Field(default=0.5, ge=0, le=1)
    
    # Related events
    related_event_ids: List[str] = Field(default_factory=list)
    
    # Status
    status: str = Field(default="open", description="open/investigating/resolved")
    assignee: Optional[str] = Field(None)


class RecoveryEvent(BaseModel):
    """Automated recovery action event"""
    event_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.RECOVERY)
    severity: SeverityLevel = Field(default=SeverityLevel.INFO)
    
    # Recovery details
    action_type: str = Field(..., description="e.g., 'load_balance', 'increase_capacity', 'restart_service'")
    action_description: str = Field(...)
    
    # Target
    target_gnb: str = Field(...)
    target_component: Optional[str] = Field(None)
    
    # Outcome
    success: bool = Field(...)
    result_message: str = Field(...)
    
    # Impact
    metrics_before: Dict[str, float] = Field(default_factory=dict)
    metrics_after: Dict[str, float] = Field(default_factory=dict)


class RecommendationEvent(BaseModel):
    """AI recommendation event"""
    event_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.RECOMMENDATION)
    severity: SeverityLevel = Field(default=SeverityLevel.INFO)
    
    # Recommendation
    recommendation_title: str = Field(...)
    recommendation_description: str = Field(...)
    recommendation_type: str = Field(..., description="e.g., 'capacity_planning', 'parameter_tuning', 'alert_threshold'")
    
    # Context
    based_on_incident_id: Optional[str] = Field(None)
    confidence: float = Field(..., ge=0, le=1)
    
    # Implementation
    estimated_benefit: str = Field(..., description="Expected improvement")
    implementation_steps: List[str] = Field(default_factory=list)
    estimated_effort: Optional[str] = Field(None, description="Easy/Medium/Hard")
    
    # Status
    status: str = Field(default="pending", description="pending/approved/implemented/rejected")


class ForecastEvent(BaseModel):
    """Predictive forecast event"""
    event_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType = Field(default=EventType.FORECAST)
    severity: SeverityLevel = Field(default=SeverityLevel.INFO)
    
    # Forecast details
    forecast_type: str = Field(..., description="e.g., 'capacity', 'reliability', 'cost'")
    forecast_metric: str = Field(..., description="e.g., 'prb_usage', 'latency'")
    
    # Target
    target_gnb: str = Field(...)
    forecast_window: str = Field(..., description="e.g., '1h', '24h', '7d'")
    
    # Prediction
    predicted_value: float = Field(...)
    confidence_interval: tuple = Field(..., description="(lower_bound, upper_bound)")
    likelihood: float = Field(..., ge=0, le=1, description="Probability of occurrence")
    
    # Recommendation
    recommended_action: Optional[str] = Field(None)


class EventBatch(BaseModel):
    """Batch of events for efficient transport"""
    batch_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    events: List[Any] = Field(...)  # Can contain any event type
    event_count: int = Field(...)
    
    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "batch_20240330_001",
                "timestamp": "2024-03-30T14:30:00Z",
                "events": [],
                "event_count": 0
            }
        }
