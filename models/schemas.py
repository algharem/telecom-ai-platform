
# Add to existing schemas.py

from enum import Enum

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Dict
from datetime import datetime
from enum import Enum


class NetworkElementType(str, Enum):
    """3GPP-defined network element types"""
    GNB = "gNB"
    ENB = "eNB"
    NG_ENB = "ng-eNB"
    CELL = "Cell"


class KPIMetrics(BaseModel):
    """
    3GPP-compliant RAN KPI metrics.
    These map to 3GPP TS 28.552 (5G performance measurements).
    """
    prb_usage: float = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Physical Resource Block usage percentage (0-100%)",
        alias="prb_usage"
    )
    throughput: float = Field(
        ..., 
        ge=0, 
        le=10000, 
        description="User plane throughput in Mbps",
        alias="throughput"
    )
    latency: float = Field(
        ..., 
        ge=0, 
        le=1000, 
        description="Round-trip latency in milliseconds",
        alias="latency"
    )
    packet_loss: float = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Packet loss percentage",
        alias="packet_loss"
    )
    
    class Config:
        populate_by_name = True  # Allow both field name and alias
    
    @validator('prb_usage')
    def validate_prb_realistic(cls, v):
        """PRB > 85% typically indicates congestion in live networks"""
        return v
    
    @validator('latency')
    def validate_latency_realistic(cls, v):
        """5G target latency is <10ms, >100ms indicates issues"""
        return v


class PredictionRequest(BaseModel):
    """Input for anomaly prediction - metrics can be omitted to auto-fetch from data source"""
    gnb_id: str = Field(..., description="gNB identifier (e.g., gNB_001)")
    cell_id: Optional[str] = Field(None, description="Cell ID within gNB")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    metrics: Optional[KPIMetrics] = Field(
        None, 
        description="KPI metrics (optional - if omitted, fetched from configured data source like Prometheus)"
    )
    network_type: NetworkElementType = NetworkElementType.GNB
    
    class Config:
        json_schema_extra = {
            "example": {
                "gnb_id": "gNB_001",
                "cell_id": "Cell_1",
                "metrics": {
                    "prb_usage": 85.5,
                    "throughput": 450.2,
                    "latency": 25.0,
                    "packet_loss": 0.1
                }
            },
            "example_with_auto_fetch": {
                "gnb_id": "gNB_001",
                "description": "Metrics will be auto-fetched from Prometheus"
            }
        }


class AnomalyResult(BaseModel):
    """Detailed anomaly detection result"""
    is_anomaly: bool
    anomaly_score: float = Field(..., description="Isolation Forest score (negative = anomaly)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level")
    severity: Literal["critical", "warning", "normal"] = "normal"
    contributing_features: List[str] = []
    explanation: str = ""


class PredictionResponse(BaseModel):
    """Complete API response"""
    prediction_id: str
    gnb_id: str
    timestamp: datetime
    metrics: KPIMetrics
    result: AnomalyResult
    recommended_action: str
    processing_time_ms: float


# class HealthStatus(BaseModel):
#     """Service health check"""
#     status: str
#     version: str
#     model_trained: bool
#     uptime_seconds: float
#     total_predictions: int

class HealthStatus(BaseModel):
    """Service health check"""
    status: str
    version: str
    is_trained: bool  # renamed from model_trained
    uptime_seconds: float
    total_predictions: int

class SimulationConfig(BaseModel):
    """Configuration for KPI simulation"""
    duration_hours: int = 24
    base_stations: int = 5
    anomaly_rate: float = 0.05
    output_format: Literal["dataframe", "list"] = "list"
    
class AnalyticsType(str, Enum):
    """3GPP TS 29.520 Analytics Types"""
    LOAD_LEVEL = "LOAD_LEVEL_INFORMATION"
    SERVICE_EXPERIENCE = "SERVICE_EXPERIENCE"
    NF_LOAD = "NF_LOAD"
    NETWORK_PERFORMANCE = "NETWORK_PERFORMANCE"
    USER_DATA_CONGESTION = "USER_DATA_CONGESTION"
    ANOMALY_EVENTS = "ANOMALY_EVENTS"


# NWDAF Request/Response Schemas

class NWDAFSubscriptionRequest(BaseModel):
    """NF subscription request per 3GPP TS 29.520"""
    nf_type: str = Field(..., description="NF type: AMF, SMF, PCF, AF, NEF")
    nf_instance_id: str
    analytics_type: AnalyticsType
    target_gnbs: List[str] = Field(..., min_items=1)
    reporting_threshold: Optional[float] = Field(None, description="Threshold for event-based reporting")
    reporting_window_minutes: int = Field(5, ge=1, le=60)
    notification_uri: str = Field(..., description="Callback URI for notifications")
    validity_period_seconds: int = Field(3600, ge=300, le=86400)


class NWDAFSubscriptionResponse(BaseModel):
    """Subscription creation response"""
    subscription_id: str
    nf_type: str
    analytics_type: AnalyticsType
    target_gnbs: List[str]
    created_at: datetime
    expires_at: datetime
    notification_uri: str


class NWDAFAnalyticsRequest(BaseModel):
    """On-demand analytics request"""
    analytics_type: AnalyticsType
    target_gnb: str
    time_window_hours: int = Field(24, ge=1, le=168)
    priority: int = Field(5, ge=1, le=10)  # 1 = highest


class LoadLevelInfo(BaseModel):
    """3GPP Load Level Information output"""
    gnb_id: str
    load_level: int = Field(..., ge=0, le=100)
    load_level_status: str = Field(..., description="low, medium, high, overload")
    confidence: float = Field(..., ge=0, le=1)
    trend: str = Field(..., description="increasing, decreasing, stable")
    forecast_next_hours: List[float]
    congestion_probability_24h: float
    recommended_action: str


class ServiceExperienceInfo(BaseModel):
    """3GPP Service Experience output"""
    gnb_id: str
    predicted_mos: float = Field(..., ge=1, le=5)
    qos_class: str = Field(..., description="premium, standard, best_effort")
    throughput_experience: str
    latency_experience: str
    confidence: float
    estimated_user_count: Optional[int] = None


class NWDAFAnalyticsResponse(BaseModel):
    """Unified analytics response"""
    analytics_type: AnalyticsType
    timestamp: datetime
    target_gnb: str
    load_level: Optional[LoadLevelInfo] = None
    service_experience: Optional[ServiceExperienceInfo] = None
    anomaly_summary: Optional[Dict] = None
    processing_time_ms: float


class NWDAFNotification(BaseModel):
    """Notification sent to subscribed NFs"""
    subscription_id: str
    notification_type: AnalyticsType
    timestamp: datetime
    target_gnb: str
    trigger_reason: str
    analytics_data: Dict
    recommended_actions: List[str]
# Add to existing schemas.py

from enum import Enum
from typing import Optional, Dict, Any


class E2ProcedureCode(int, Enum):
    """E2AP Procedure Codes"""
    RIC_SUBSCRIPTION = 201
    RIC_INDICATION = 202
    RIC_CONTROL = 203


class RICControlActionType(str, Enum):
    """E2SM-RAN Control Actions"""
    ADMISSION_CONTROL = "ADMISSION_CONTROL"
    HANDOVER_CONTROL = "HANDOVER_CONTROL"
    LOAD_BALANCING = "LOAD_BALANCING"
    SLICE_CONTROL = "SLICE_CONTROL"
    POWER_CONTROL = "POWER_CONTROL"
    SCHEDULING_CONTROL = "SCHEDULING_CONTROL"


class UEContext(BaseModel):
    """User Equipment context from RAN"""
    ue_id: str = Field(..., description="RAN UE NGAP ID")
    cell_id: str
    rnti: Optional[str] = None          # Radio Network Temporary Identifier
    imsi: Optional[str] = None          # Masked for privacy
    
    # Radio conditions
    rsrp_dbm: float = Field(..., description="Reference Signal Received Power")
    rsrq_db: float = Field(..., description="Reference Signal Received Quality")
    cqi: int = Field(..., ge=0, le=15, description="Channel Quality Indicator")
    
    # Connection state
    connection_state: str = Field(..., description="IDLE, CONNECTED, INACTIVE")
    drb_id: Optional[int] = None        # Data Radio Bearer ID
    qos_flows: List[int] = []


class CellState(BaseModel):
    """gNB cell state from E2SM"""
    cell_id: str
    cell_type: str = Field(..., description="FDD, TDD, NR")
    
    # Resource status
    prb_dl_used: int                      # Downlink PRBs used
    prb_dl_total: int
    prb_ul_used: int                      # Uplink PRBs used
    prb_ul_total: int
    
    # Load metrics
    active_ues: int
    max_ues: int
    cpu_utilization: float                # gNB CPU %
    memory_utilization: float
    
    # Performance
    avg_ue_throughput_mbps: float
    avg_ue_latency_ms: float


class RANMetric(BaseModel):
    """E2AP RIC Indication message content"""
    gnb_id: str
    cell_id: str
    timestamp: datetime
    ue_list: List[UEContext]
    cell_state: CellState
    
    # Raw measurements
    prb_usage_dl: float
    prb_usage_ul: float
    interference_level: float


class ControlDecision(BaseModel):
    """xApp control decision output"""
    decision_id: str
    xapp_id: str
    timestamp: datetime
    target_cell: str
    action_type: RICControlActionType
    target_ue: Optional[str] = None
    priority: int = Field(..., ge=1, le=10)  # 1 = highest
    
    # Decision rationale
    trigger_metrics: Dict[str, float]     # What triggered this action
    predicted_outcome: str                # Expected result
    confidence: float                     # AI confidence 0-1
    
    # Control parameters
    control_parameters: Dict[str, Any]    # E2SM-RAN Control parameters


class ControlAction(BaseModel):
    """E2SM-RAN Control Action to be sent to gNB"""
    action_id: str
    gnb_id: str
    cell_id: str
    action_type: RICControlActionType
    ue_id: Optional[str] = None
    
    # E2SM encoding
    ran_parameter_id: int                 # 3GPP-defined parameter ID
    ran_parameter_value: Any              # Value to set
    
    # Timing
    validity_period_ms: int = 1000        # How long action is valid
    execution_delay_ms: int = 0           # Delay before execution


class XAppPolicy(BaseModel):
    """xApp policy configuration"""
    policy_id: str
    policy_type: str
    enabled: bool
    constraints: Dict[str, Any]
    thresholds: Dict[str, float]


class XAppStatus(BaseModel):
    """xApp runtime status"""
    xapp_id: str
    version: str
    state: str = Field(..., description="INIT, RUNNING, STOPPED, ERROR")
    registered_with_ric: bool
    subscribed_e2_nodes: List[str]
    control_loop_active: bool
    decisions_per_second: float
    # last_decision_timestamp: Optional[datetime]
    last_decision_timestamp: Optional[datetime] = None  # ✅ FIX
    total_decisions: int
    total_actions_executed: int


        
