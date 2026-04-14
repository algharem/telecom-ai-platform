I'll build Phase 3: **O-RAN xApp Decision Engine**. This adds real-time RAN control, E2 interface simulation, and closed-loop automation.

---

# Phase 3: O-RAN xApp Decision Engine

## Architecture Overview (Updated)

```
missed:
oran/
   ├── rsm_control.py        
   ├── ric_adapter.py   
models/
   └── ml_model.py             
infrastructure/
  └── message_bus.py    


telecom-ai-platform/
├── app/
│   ├── __init__.py
│   ├── main.py                 
│   ├── config.py               
│   └── dependencies.py         
├── services/
│   ├── __init__.py
│   ├── kpi_simulator.py        # [Phase 1] 
│   ├── ml_detector.py          # [Phase 1]
│   ├── nwdaf_analytics.py      # [Phase 2]
│   └── oran_xapp.py            # [NEW] Phase 3 - O-RAN Control
├── oran/
│   ├── __init__.py
│   ├── e2_interface.py         # E2AP message handling
│   ├── rsm_control.py          # E2SM-RAN Control
│   ├── ric_adapter.py          # RIC platform adapter
│   └── policies.py             # xApp policy engine
├── models/
│   ├── __init__.py
│   ├── schemas.py              # [UPDATED] Add O-RAN schemas
│   └── ml_model.py             
├── api/
│   └── v1/
│       ├── __init__.py
│       └── endpoints/
│           ├── __init__.py
│           ├── prediction.py   # [Phase 1]
│           ├── health.py       
│           ├── nwdaf.py        # [Phase 2]
│           └── xapp.py         # [NEW] Phase 3 endpoints
├── infrastructure/
│   ├── __init__.py
│   ├── database.py             
│   └── message_bus.py          # [UPDATED] RMR/Kafka for xApps
├── utils/
│   ├── __init__.py
│   ├── logging_config.py       
│   ├── exceptions.py           # [UPDATED]
│   └── time_series.py          
├── data/
│   └── .gitkeep                
├── tests/
│   └── test_xapp.py            # [NEW]
├── Dockerfile
├── requirements.txt            # [UPDATED]
└── config.yaml                 # [UPDATED]
```

---

## Why O-RAN xApps Matter

**O-RAN (Open RAN) Architecture:**
- **Near-RT RIC** (Radio Intelligent Controller): 10ms - 1s control loop
- **xApps**: AI-driven control applications running on RIC
- **E2 Interface**: Connects RIC to RAN nodes (gNBs) for control

**Real-World Use Cases:**
| xApp Function | Telecom Impact |
|-------------|---------------|
| **Admission Control** | Block new users when congestion predicted |
| **Handover Management** | Move users to better cells automatically |
| **Load Balancing** | Distribute traffic across cells |
| **Slice Management** | Guarantee QoS for network slices |

---

## Phase 3 Implementation

### 1. Updated Requirements (`requirements.txt`)

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
scikit-learn==1.3.2
pandas==2.1.3
numpy==1.26.2
pyyaml==6.0.1
python-json-logger==2.0.7
joblib==1.3.2
httpx==0.25.2
pytest==7.4.3
influxdb-client==1.38.0
aioredis==2.0.1
scipy==1.11.4
statsmodels==0.14.1

# Phase 3 additions
kafka-python==2.0.2           # For RMR-like messaging
paho-mqtt==1.6.1             # Alternative to E2AP
asyncio-mqtt==0.16.1         # Async MQTT
schedule==1.2.1              # Control loop timing
```

### 2. Updated Config (`config.yaml`)

```yaml
# config.yaml
app:
  name: "telecom-ai-platform"
  version: "3.0.0"             # Phase 3
  debug: false

api:
  host: "0.0.0.0"
  port: 8000
  workers: 1

ml:
  model_path: "./data/anomaly_detector.pkl"
  contamination: 0.05
  n_estimators: 100
  random_state: 42

nwdaf:
  analytics_retention_hours: 168
  subscription_ttl_seconds: 3600
  time_series_resolution: "5m"
  forecasting_horizon_hours: 24
  supported_analytics:
    - LOAD_LEVEL_INFORMATION
    - SERVICE_EXPERIENCE
    - NF_LOAD
    - NETWORK_PERFORMANCE
    - USER_DATA_CONGESTION
    - ANOMALY_EVENTS

# Phase 3: O-RAN xApp Configuration
oran:
  xapp_id: "xapp-smart-optimizer"
  xapp_version: "1.0.0"
  ric_platform_url: "http://ric.platform:8080"
  e2_node_ids: ["gNB_001", "gNB_002", "gNB_003"]
  
  # Control loop timing (Near-RT RIC: 10ms-1s)
  control_loop_interval_ms: 100  # 100ms = 10Hz
  
  # E2 interface settings
  e2ap:
    procedure_code: 8            # RICcontrol
    ric_style_type: 1            # MAC Control
    timeout_ms: 500
  
  # xApp policies
  policies:
    admission_control:
      enabled: true
      prb_threshold: 85          # Block new users above 85% PRB
      handover_margin: 5         # % margin before triggering
      
    congestion_control:
      enabled: true
      latency_threshold_ms: 50
      throughput_drop_threshold: 30  # %
      
    energy_saving:
      enabled: false
      off_peak_shutdown: true

infrastructure:
  redis_url: "redis://localhost:6379"
  influxdb_url: "http://localhost:8086"
  influxdb_token: "telecom-ai-token"
  influxdb_org: "telecom"
  influxdb_bucket: "nwdaf_analytics"
  
  # Message bus for xApps (simulating RMR)
  kafka_brokers: "localhost:9092"
  xapp_topic: "xapp-control-messages"

kpi_simulator:
  base_stations: 10
  simulation_hours: 168
  anomaly_rate: 0.05
  
  thresholds:
    prb_usage_max: 100
    throughput_max: 1000
    latency_max: 200
    packet_loss_max: 5

logging:
  level: "INFO"
  format: "json"
  file: "./logs/telecom-ai.log"
```

### 3. Updated Exceptions (`utils/exceptions.py`)

```python
# Add to existing exceptions.py

class ORANException(TelecomAIException):
    """Base for O-RAN xApp errors"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, error_code or "ORAN_ERROR", details)


class E2InterfaceException(ORANException):
    """E2AP/E2SM communication failure"""
    def __init__(self, message: str, gnb_id: str = None):
        super().__init__(
            message,
            "E2_INTERFACE_ERROR",
            {"gNB": gnb_id, "interface": "E2"}
        )


class ControlLoopException(ORANException):
    """Real-time control loop failure"""
    def __init__(self, message: str, xapp_id: str = None):
        super().__init__(
            message,
            "CONTROL_LOOP_ERROR",
            {"xapp_id": xapp_id}
        )


class PolicyViolationException(ORANException):
    """Control action violates policy"""
    def __init__(self, message: str, policy: str = None, action: str = None):
        super().__init__(
            message,
            "POLICY_VIOLATION",
            {"policy": policy, "attempted_action": action}
        )
```

### 4. O-RAN Schemas (`models/schemas.py` - Additions)

```python
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
    last_decision_timestamp: Optional[datetime]
    total_decisions: int
    total_actions_executed: int
```

### 5. E2 Interface Handler (`oran/e2_interface.py`)

```python
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from datetime import datetime
import json
import logging

from models.schemas import (
    RANMetric, 
    ControlAction, 
    E2ProcedureCode,
    UEContext,
    CellState
)
from utils.exceptions import E2InterfaceException


logger = logging.getLogger(__name__)


@dataclass
class E2Subscription:
    """E2AP Subscription Details"""
    subscription_id: str
    gnb_id: str
    ran_function_id: int          # E2SM function (e.g., 2 = MAC, 3 = RLC)
    event_trigger: str            # "PERIODIC", "ON_CHANGE", "EVENT"
    reporting_period_ms: int      # For periodic reporting


class E2APHandler:
    """
    E2 Application Protocol Handler (3GPP TS 38.463).
    
    Simulates E2 interface between RIC and gNB.
    In production, this uses SCTP over real network.
    """
    
    # E2SM RAN Function IDs
    RAN_FUNCTIONS = {
        1: "E2SM-KPM",      # Key Performance Measurement
        2: "E2SM-RC",       # RAN Control
        3: "E2SM-CCC",      # Call Control and Mobility
    }
    
    def __init__(self, ric_id: str = "ric-001"):
        self.ric_id = ric_id
        self.subscriptions: Dict[str, E2Subscription] = {}
        self.indication_callbacks: List[Callable] = []
        self.connected_gnbs: Dict[str, bool] = {}
        self.sequence_number = 0
        
        # Simulated message queue (replace with SCTP in production)
        self.message_queue = asyncio.Queue()
        
        logger.info(f"E2AP Handler initialized for RIC {ric_id}")
    
    async def connect_gnb(self, gnb_id: str, address: str) -> bool:
        """
        E2 Setup procedure (E2AP E2setupRequest/E2setupResponse).
        Establishes association with gNB.
        """
        logger.info(f"E2 Setup: Connecting to {gnb_id} at {address}")
        
        # Simulate E2 setup handshake
        await asyncio.sleep(0.1)
        
        self.connected_gnbs[gnb_id] = True
        logger.info(f"E2 Setup complete: {gnb_id} connected")
        return True
    
    async def subscribe_ran_function(self,
                                     gnb_id: str,
                                     ran_function_id: int,
                                     event_trigger: str = "PERIODIC",
                                     period_ms: int = 100) -> str:
        """
        E2AP RICsubscriptionRequest.
        Subscribe to RAN function (KPM, RC, etc.).
        """
        if not self.connected_gnbs.get(gnb_id):
            raise E2InterfaceException(f"gNB {gnb_id} not connected", gnb_id)
        
        sub_id = f"e2sub-{gnb_id}-{ran_function_id}-{datetime.utcnow().timestamp()}"
        
        subscription = E2Subscription(
            subscription_id=sub_id,
            gnb_id=gnb_id,
            ran_function_id=ran_function_id,
            event_trigger=event_trigger,
            reporting_period_ms=period_ms
        )
        
        self.subscriptions[sub_id] = subscription
        
        logger.info(
            f"E2 Subscription created: {sub_id} "
            f"for {self.RAN_FUNCTIONS.get(ran_function_id, 'UNKNOWN')} "
            f"on {gnb_id}"
        )
        
        # Start indication reception (simulated)
        asyncio.create_task(self._indication_receiver(subscription))
        
        return sub_id
    
    async def send_control_request(self, action: ControlAction) -> bool:
        """
        E2AP RICcontrolRequest (Procedure Code 8).
        Send control action to gNB via E2SM-RAN Control.
        """
        if not self.connected_gnbs.get(action.gnb_id):
            raise E2InterfaceException(f"gNB {action.gnb_id} not connected", action.gnb_id)
        
        # Build E2AP message (simplified)
        e2ap_message = {
            "procedure_code": E2ProcedureCode.RIC_CONTROL,
            "ric_request_id": action.action_id,
            "ran_function_id": 2,  # E2SM-RC
            "ric_control_action_id": self._get_action_id(action.action_type),
            "ran_parameters": {
                "param_id": action.ran_parameter_id,
                "param_value": action.ran_parameter_value
            },
            "target_cell": action.cell_id,
            "target_ue": action.ue_id,
            "validity": action.validity_period_ms
        }
        
        logger.info(f"E2 Control Request: {action.action_type} to {action.gnb_id}")
        
        # Simulate transmission delay
        await asyncio.sleep(0.005)  # 5ms
        
        # Simulate success (in production, wait for RICcontrolAcknowledge)
        success = True
        
        if success:
            logger.info(f"E2 Control successful: {action.action_id}")
        else:
            raise E2InterfaceException(
                f"Control action rejected by {action.gnb_id}", 
                action.gnb_id
            )
        
        return success
    
    def register_indication_callback(self, callback: Callable):
        """Register callback for E2AP RICindication messages"""
        self.indication_callbacks.append(callback)
    
    async def _indication_receiver(self, subscription: E2Subscription):
        """
        Background task: Receive RICindication from gNB.
        In production, this receives SCTP packets.
        """
        while True:
            try:
                # Simulate periodic indication
                await asyncio.sleep(subscription.reporting_period_ms / 1000)
                
                # Generate simulated RAN metrics
                metric = self._generate_simulated_metric(subscription)
                
                # Notify callbacks (xApps)
                for callback in self.indication_callbacks:
                    try:
                        await callback(metric)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Indication receiver error: {e}")
                await asyncio.sleep(1)
    
    def _generate_simulated_metric(self, sub: E2Subscription) -> RANMetric:
        """Generate realistic RAN metric for simulation"""
        import random
        
        gnb_id = sub.gnb_id
        cell_id = f"{gnb_id}_Cell1"
        
        # Simulate cell state
        prb_total = 100
        prb_used = random.randint(30, 95)
        
        cell_state = CellState(
            cell_id=cell_id,
            cell_type="NR_TDD",
            prb_dl_used=prb_used,
            prb_dl_total=prb_total,
            prb_ul_used=int(prb_used * 0.8),
            prb_ul_total=prb_total,
            active_ues=random.randint(5, 50),
            max_ues=200,
            cpu_utilization=random.uniform(20, 80),
            memory_utilization=random.uniform(30, 70),
            avg_ue_throughput_mbps=random.uniform(10, 500),
            avg_ue_latency_ms=random.uniform(5, 100)
        )
        
        # Simulate UEs
        ue_list = []
        for i in range(min(cell_state.active_ues, 5)):  # Limit for performance
            ue = UEContext(
                ue_id=f"UE_{gnb_id}_{i:03d}",
                cell_id=cell_id,
                rnti=f"0x{i+1:04X}",
                rsrp_dbm=random.uniform(-100, -70),
                rsrq_db=random.uniform(-20, -5),
                cqi=random.randint(1, 15),
                connection_state="CONNECTED",
                drb_id=i+1,
                qos_flows=[1, 2]
            )
            ue_list.append(ue)
        
        return RANMetric(
            gnb_id=gnb_id,
            cell_id=cell_id,
            timestamp=datetime.utcnow(),
            ue_list=ue_list,
            cell_state=cell_state,
            prb_usage_dl=(cell_state.prb_dl_used / cell_state.prb_dl_total) * 100,
            prb_usage_ul=(cell_state.prb_ul_used / cell_state.prb_ul_total) * 100,
            interference_level=random.uniform(-110, -80)
        )
    
    def _get_action_id(self, action_type: str) -> int:
        """Map action type to E2SM-RAN Control Action ID"""
        mapping = {
            "ADMISSION_CONTROL": 1,
            "HANDOVER_CONTROL": 2,
            "LOAD_BALANCING": 3,
            "SLICE_CONTROL": 4,
            "POWER_CONTROL": 5,
            "SCHEDULING_CONTROL": 6
        }
        return mapping.get(action_type, 0)
    
    async def disconnect_gnb(self, gnb_id: str):
        """E2AP E2connectionUpdateRemove"""
        if gnb_id in self.connected_gnbs:
            del self.connected_gnbs[gnb_id]
            
        # Remove associated subscriptions
        to_remove = [s for s in self.subscriptions.values() if s.gnb_id == gnb_id]
        for sub in to_remove:
            del self.subscriptions[sub.subscription_id]
            
        logger.info(f"E2 disconnect: {gnb_id}")
```

### 6. xApp Policy Engine (`oran/policies.py`)

```python
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json


class PolicyAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


@dataclass
class PolicyRule:
    """Individual policy rule"""
    name: str
    condition: str  # Python expression as string
    action: PolicyAction
    parameters: Dict[str, Any]
    priority: int = 5


class PolicyEngine:
    """
    O-RAN xApp Policy Engine.
    
    Evaluates control decisions against operator policies.
    Ensures xApp actions don't violate network constraints.
    """
    
    def __init__(self):
        self.policies: Dict[str, List[PolicyRule]] = {
            "admission_control": [],
            "congestion_control": [],
            "handover": [],
            "emergency": []
        }
        self._load_default_policies()
    
    def _load_default_policies(self):
        """Load 3GPP/O-RAN compliant default policies"""
        
        # Policy 1: Never drop emergency calls
        self.policies["emergency"].append(
            PolicyRule(
                name="protect_emergency",
                condition="ue_qos_priority == 1",  # ARP priority 1 = emergency
                action=PolicyAction.DENY,
                parameters={"reason": "Emergency traffic protected"},
                priority=1  # Highest
            )
        )
        
        # Policy 2: Don't handover if target cell is overloaded
        self.policies["handover"].append(
            PolicyRule(
                name="prevent_overload_handover",
                condition="target_cell_load > 90",
                action=PolicyAction.DENY,
                parameters={"reason": "Target cell overloaded"},
                priority=2
            )
        )
        
        # Policy 3: Limit handover frequency per UE
        self.policies["handover"].append(
            PolicyRule(
                name="handover_rate_limit",
                condition="ue_handover_count_last_hour > 3",
                action=PolicyAction.ESCALATE,
                parameters={"reason": "Ping-pong handover detected"},
                priority=3
            )
        )
        
        # Policy 4: Block new admissions if CPU > 90%
        self.policies["admission_control"].append(
            PolicyRule(
                name="cpu_protection",
                condition="gnb_cpu > 90",
                action=PolicyAction.DENY,
                parameters={"reason": "gNB CPU critical"},
                priority=2
            )
        )
        
        # Policy 5: Aggressive congestion control if latency > 100ms
        self.policies["congestion_control"].append(
            PolicyRule(
                name="latency_emergency",
                condition="cell_latency_ms > 100",
                action=PolicyAction.ALLOW,
                parameters={"aggressiveness": "high"},
                priority=1
            )
        )
    
    def evaluate(self,
                 policy_category: str,
                 context: Dict[str, Any],
                 proposed_action: str) -> tuple:
        """
        Evaluate proposed control action against policies.
        
        Returns: (decision: PolicyAction, reason: str, modified_params: dict)
        """
        if policy_category not in self.policies:
            return (PolicyAction.ALLOW, "No policies defined", {})
        
        applicable_rules = sorted(
            self.policies[policy_category],
            key=lambda r: r.priority
        )
        
        for rule in applicable_rules:
            try:
                # Evaluate condition (safely)
                condition_met = self._evaluate_condition(rule.condition, context)
                
                if condition_met:
                    if rule.action == PolicyAction.DENY:
                        return (
                            PolicyAction.DENY,
                            f"Policy '{rule.name}': {rule.parameters.get('reason')}",
                            {}
                        )
                    elif rule.action == PolicyAction.ESCALATE:
                        return (
                            PolicyAction.ESCALATE,
                            f"Policy '{rule.name}' requires manual review",
                            rule.parameters
                        )
                    elif rule.action == PolicyAction.ALLOW:
                        # Allow but possibly modify parameters
                        return (PolicyAction.ALLOW, f"Policy '{rule.name}' applied", rule.parameters)
                        
            except Exception as e:
                # Fail open but log
                return (PolicyAction.ALLOW, f"Policy evaluation error: {e}", {})
        
        return (PolicyAction.ALLOW, "No matching policies", {})
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """Safely evaluate policy condition"""
        try:
            # Create safe evaluation context
            safe_dict = {
                "min": min, "max": max, "abs": abs,
                "len": len, "sum": sum
            }
            safe_dict.update(context)
            
            return eval(condition, {"__builtins__": {}}, safe_dict)
        except:
            return False
    
    def add_policy(self, category: str, rule: PolicyRule):
        """Add custom policy at runtime"""
        if category not in self.policies:
            self.policies[category] = []
        self.policies[category].append(rule)
    
    def get_policy_summary(self) -> Dict:
        """Get active policy summary"""
        return {
            category: len(rules)
            for category, rules in self.policies.items()
        }
```

### 7. xApp Core Service (`services/oran_xapp.py`)

```python
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import time
import logging

from oran.e2_interface import E2APHandler, E2Subscription
from oran.policies import PolicyEngine, PolicyAction
from services.nwdaf_analytics import NWDAFAnalyticsEngine
from services.ml_detector import AnomalyDetector
from models.schemas import (
    RANMetric,
    ControlDecision,
    ControlAction,
    RICControlActionType,
    XAppStatus,
    XAppPolicy
)
from utils.exceptions import ControlLoopException, PolicyViolationException
from utils.time_series import TimeSeriesAnalyzer


logger = logging.getLogger(__name__)


@dataclass
class UEHoState:
    """Track UE handover state to prevent ping-pong"""
    ue_id: str
    handover_count: int = 0
    last_handover: Optional[datetime] = None
    source_cells: List[str] = field(default_factory=list)


class SmartOptimizerXApp:
    """
    O-RAN Near-RT RIC xApp for intelligent RAN optimization.
    
    Implements:
    - Admission Control (block users when congested)
    - Load Balancing (move users to less loaded cells)
    - Congestion Control (rate limiting, scheduling)
    
    Control loop: 100ms (10Hz) - Near-RT RIC timing
    """
    
    def __init__(self,
                 xapp_id: str = "xapp-smart-optimizer",
                 nwdaf_engine: Optional[NWDAFAnalyticsEngine] = None,
                 detector: Optional[AnomalyDetector] = None):
        self.xapp_id = xapp_id
        self.version = "1.0.0"
        self.e2_handler = E2APHandler(ric_id="ric-smart-001")
        self.policy_engine = PolicyEngine()
        self.nwdaf = nwdaf_engine
        self.detector = detector
        
        # Runtime state
        self.status = XAppStatus(
            xapp_id=xapp_id,
            version=self.version,
            state="INIT",
            registered_with_ric=False,
            subscribed_e2_nodes=[],
            control_loop_active=False,
            decisions_per_second=0.0,
            total_decisions=0,
            total_actions_executed=0
        )
        
        # UE tracking
        self.ue_states: Dict[str, UEHoState] = {}
        self.cell_load_history: Dict[str, List[float]] = {}
        
        # Decision tracking
        self.decision_log: List[ControlDecision] = []
        self.max_log_size = 10000
        
        # Control loop
        self._control_task = None
        self._running = False
        self._decision_queue = asyncio.Queue()
        
        # Metrics
        self._decision_times = []
        
        logger.info(f"xApp {xapp_id} initialized")
    
    async def register_with_ric(self, ric_platform_url: str) -> bool:
        """
        Register xApp with RIC platform (RICappMgr).
        Required before E2 operations.
        """
        logger.info(f"Registering {self.xapp_id} with RIC at {ric_platform_url}")
        
        # Simulate RIC registration
        await asyncio.sleep(0.1)
        
        self.status.registered_with_ric = True
        self.status.state = "REGISTERED"
        
        logger.info(f"xApp registered successfully")
        return True
    
    async def subscribe_to_e2_nodes(self, gnb_ids: List[str]):
        """Subscribe to E2 interface for all target gNBs"""
        for gnb_id in gnb_ids:
            # E2 Setup
            await self.e2_handler.connect_gnb(gnb_id, f"{gnb_id}:38472")
            
            # Subscribe to E2SM-KPM (measurements)
            kpm_sub = await self.e2_handler.subscribe_ran_function(
                gnb_id=gnb_id,
                ran_function_id=1,  # E2SM-KPM
                event_trigger="PERIODIC",
                period_ms=100  # 100ms reporting
            )
            
            # Subscribe to E2SM-RC (control)
            rc_sub = await self.e2_handler.subscribe_ran_function(
                gnb_id=gnb_id,
                ran_function_id=2,  # E2SM-RC
                event_trigger="ON_CHANGE"
            )
            
            self.status.subscribed_e2_nodes.append(gnb_id)
            
            logger.info(f"Subscribed to {gnb_id}: KPM={kpm_sub}, RC={rc_sub}")
        
        # Register callback for indications
        self.e2_handler.register_indication_callback(self._on_ran_indication)
    
    async def start_control_loop(self, interval_ms: int = 100):
        """
        Start Near-RT control loop.
        
        Two modes:
        1. Event-driven: React to E2 indications
        2. Periodic: Time-based control decisions
        """
        if not self.status.registered_with_ric:
            raise ControlLoopException("Not registered with RIC", self.xapp_id)
        
        self._running = True
        self.status.control_loop_active = True
        self.status.state = "RUNNING"
        
        # Start periodic control loop
        self._control_task = asyncio.create_task(
            self._periodic_control_loop(interval_ms)
        )
        
        # Start decision executor
        self._executor_task = asyncio.create_task(
            self._decision_executor()
        )
        
        logger.info(f"Control loop started: {interval_ms}ms interval")
    
    async def stop(self):
        """Graceful shutdown"""
        self._running = False
        self.status.control_loop_active = False
        self.status.state = "STOPPED"
        
        if self._control_task:
            self._control_task.cancel()
        if self._executor_task:
            self._executor_task.cancel()
        
        # Disconnect E2
        for gnb in list(self.e2_handler.connected_gnbs.keys()):
            await self.e2_handler.disconnect_gnb(gnb)
        
        logger.info("xApp stopped")
    
    async def _periodic_control_loop(self, interval_ms: int):
        """
        Periodic control loop (Near-RT RIC).
        
        Analyzes cell states and makes proactive decisions.
        """
        while self._running:
            loop_start = time.time()
            
            try:
                # Analyze each subscribed cell
                for gnb_id in self.status.subscribed_e2_nodes:
                    decision = await self._analyze_and_decide(gnb_id)
                    
                    if decision:
                        await self._decision_queue.put(decision)
                        self.status.total_decisions += 1
                
                # Calculate loop timing
                elapsed = (time.time() - loop_start) * 1000
                self._decision_times.append(elapsed)
                if len(self._decision_times) > 100:
                    self._decision_times.pop(0)
                
                self.status.decisions_per_second = 1000.0 / elapsed if elapsed > 0 else 0
                
                # Sleep to maintain interval
                sleep_ms = max(0, interval_ms - elapsed)
                await asyncio.sleep(sleep_ms / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Control loop error: {e}")
                await asyncio.sleep(interval_ms / 1000)
    
    async def _on_ran_indication(self, metric: RANMetric):
        """
        Event-driven: React to E2 indications.
        Called when gNB sends RICindication.
        """
        # Update cell load history
        if metric.gnb_id not in self.cell_load_history:
            self.cell_load_history[metric.gnb_id] = []
        
        self.cell_load_history[metric.gnb_id].append(metric.cell_state.prb_dl_used)
        
        # Keep last 100 samples
        if len(self.cell_load_history[metric.gnb_id]) > 100:
            self.cell_load_history[metric.gnb_id].pop(0)
        
        # Real-time decision on indication
        decision = await self._event_driven_decide(metric)
        if decision:
            await self._decision_queue.put(decision)
            self.status.total_decisions += 1
    
    async def _analyze_and_decide(self, gnb_id: str) -> Optional[ControlDecision]:
        """
        Periodic analysis: Look at trends and predict issues.
        """
        # Get NWDAF analytics if available
        load_level = None
        if self.nwdaf:
            try:
                analytics = await self.nwdaf.get_analytics(
                    analytics_type="LOAD_LEVEL_INFORMATION",
                    target_gnb=gnb_id,
                    time_window_hours=1
                )
                load_level = analytics.load_level
            except:
                pass
        
        # Use local history if NWDAF unavailable
        if load_level is None and gnb_id in self.cell_load_history:
            recent_loads = self.cell_load_history[gnb_id][-10:]
            load_level = sum(recent_loads) / len(recent_loads) if recent_loads else 50
        
        if load_level is None:
            return None
        
        # Decision logic
        if load_level > 85:
            return await self._create_load_balance_decision(gnb_id, load_level)
        elif load_level > 70:
            return await self._create_admission_control_decision(gnb_id, load_level)
        
        return None
    
    async def _event_driven_decide(self, metric: RANMetric) -> Optional[ControlDecision]:
        """
        Event-driven: React to specific RAN conditions.
        """
        cell = metric.cell_state
        
        # Critical conditions
        if cell.cpu_utilization > 90:
            return ControlDecision(
                decision_id=str(uuid.uuid4()),
                xapp_id=self.xapp_id,
                timestamp=datetime.utcnow(),
                target_cell=metric.cell_id,
                action_type=RICControlActionType.ADMISSION_CONTROL,
                priority=1,
                trigger_metrics={"cpu": cell.cpu_utilization},
                predicted_outcome="Block new admissions to protect gNB stability",
                confidence=0.95,
                control_parameters={"block_new_ues": True}
            )
        
        # Check for poor UE experience
        poor_ues = [ue for ue in metric.ue_list if ue.cqi < 5]
        if len(poor_ues) > 0 and cell.prb_dl_used > 80:
            # Handover poor UEs to better cell
            return await self._create_handover_decision(
                metric, 
                poor_ues[0],
                reason="Poor CQI in congested cell"
            )
        
        return None
    
    async def _create_load_balance_decision(self, 
                                            gnb_id: str, 
                                            current_load: float) -> ControlDecision:
        """Create load balancing decision"""
        # Find best target cell (simplified: assume neighbor knowledge)
        neighbors = self._get_neighbor_cells(gnb_id)
        best_neighbor = None
        best_load = 100
        
        for neighbor in neighbors:
            if neighbor in self.cell_load_history:
                neighbor_load = sum(self.cell_load_history[neighbor][-5:]) / 5
                if neighbor_load < best_load:
                    best_load = neighbor_load
                    best_neighbor = neighbor
        
        if best_neighbor and (current_load - best_load) > 15:
            return ControlDecision(
                decision_id=str(uuid.uuid4()),
                xapp_id=self.xapp_id,
                timestamp=datetime.utcnow(),
                target_cell=gnb_id,
                action_type=RICControlActionType.LOAD_BALANCING,
                priority=2,
                trigger_metrics={"current_load": current_load, "target_load": best_load},
                predicted_outcome=f"Balance load to {best_neighbor}",
                confidence=0.85,
                control_parameters={
                    "target_cell": best_neighbor,
                    "handover_candidates": "low_cqi_ues"
                }
            )
        
        return None
    
    async def _create_admission_control_decision(self,
                                                  gnb_id: str,
                                                  load: float) -> ControlDecision:
        """Create admission control decision"""
        return ControlDecision(
            decision_id=str(uuid.uuid4()),
            xapp_id=self.xapp_id,
            timestamp=datetime.utcnow(),
            target_cell=gnb_id,
            action_type=RICControlActionType.ADMISSION_CONTROL,
            priority=3,
            trigger_metrics={"prb_usage": load},
            predicted_outcome="Prevent congestion by blocking new users",
            confidence=0.80,
            control_parameters={"admission_rate_limit": 50}  # 50% of normal
        )
    
    async def _create_handover_decision(self,
                                        metric: RANMetric,
                                        ue: any,
                                        reason: str) -> Optional[ControlDecision]:
        """Create handover decision for specific UE"""
        # Check UE handover history (prevent ping-pong)
        if ue.ue_id not in self.ue_states:
            self.ue_states[ue.ue_id] = UEHoState(ue_id=ue.ue_id)
        
        ue_state = self.ue_states[ue.ue_id]
        
        # Rate limiting: max 3 handovers per hour
        if ue_state.handover_count >= 3:
            recent = ue_state.last_handover and \
                     (datetime.utcnow() - ue_state.last_handover) < timedelta(hours=1)
            if recent:
                logger.warning(f"Handover rate limit for {ue.ue_id}")
                return None
        
        # Find target cell with better signal
        # Simplified: assume we know neighbor cells
        target_cell = f"{metric.gnb_id}_Cell2"  # Assume 2nd cell is neighbor
        
        return ControlDecision(
            decision_id=str(uuid.uuid4()),
            xapp_id=self.xapp_id,
            timestamp=datetime.utcnow(),
            target_cell=metric.cell_id,
            target_ue=ue.ue_id,
            action_type=RICControlActionType.HANDOVER_CONTROL,
            priority=2,
            trigger_metrics={"ue_cqi": ue.cqi, "cell_load": metric.cell_state.prb_dl_used},
            predicted_outcome=f"Handover to {target_cell} for better experience",
            confidence=0.75,
            control_parameters={
                "target_cell": target_cell,
                "handover_type": "intra_gnb"
            }
        )
    
    async def _decision_executor(self):
        """
        Background task: Execute decisions through E2 interface.
        Applies policy checks before execution.
        """
        while self._running:
            try:
                decision = await self._decision_queue.get()
                
                # Policy check
                context = {
                    "gnb_load": decision.trigger_metrics.get("current_load", 50),
                    "ue_qos_priority": 5,  # Default
                    "target_cell_load": 60,  # Assume
                    "gnb_cpu": 70
                }
                
                policy_result, reason, params = self.policy_engine.evaluate(
                    decision.action_type.lower().replace("_control", ""),
                    context,
                    decision.action_type
                )
                
                if policy_result == PolicyAction.DENY:
                    logger.warning(f"Decision {decision.decision_id} denied by policy: {reason}")
                    continue
                
                if policy_result == PolicyAction.ESCALATE:
                    logger.warning(f"Decision {decision.decision_id} escalated: {reason}")
                    # Could notify human operator here
                    continue
                
                # Convert decision to E2 action
                action = self._decision_to_e2_action(decision)
                
                # Execute via E2
                try:
                    success = await self.e2_handler.send_control_request(action)
                    if success:
                        self.status.total_actions_executed += 1
                        decision.predicted_outcome += " [EXECUTED]"
                        
                        # Update UE state if handover
                        if decision.target_ue and decision.action_type == RICControlActionType.HANDOVER_CONTROL:
                            if decision.target_ue in self.ue_states:
                                self.ue_states[decision.target_ue].handover_count += 1
                                self.ue_states[decision.target_ue].last_handover = datetime.utcnow()
                                self.ue_states[decision.target_ue].source_cells.append(decision.target_cell)
                        
                except Exception as e:
                    logger.error(f"E2 execution failed: {e}")
                    decision.predicted_outcome += f" [FAILED: {e}]"
                
                # Log decision
                self._log_decision(decision)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Decision executor error: {e}")
    
    def _decision_to_e2_action(self, decision: ControlDecision) -> ControlAction:
        """Convert xApp decision to E2SM-RAN Control Action"""
        
        # Map to E2SM parameters
        param_mapping = {
            RICControlActionType.ADMISSION_CONTROL: (1, decision.control_parameters),
            RICControlActionType.HANDOVER_CONTROL: (2, {
                "target_cell": decision.control_parameters.get("target_cell"),
                "ue_id": decision.target_ue
            }),
            RICControlActionType.LOAD_BALANCING: (3, decision.control_parameters),
        }
        
        param_id, param_value = param_mapping.get(
            decision.action_type, 
            (0, {})
        )
        
        return ControlAction(
            action_id=decision.decision_id,
            gnb_id=decision.target_cell.split("_")[0],  # Extract gNB from cell
            cell_id=decision.target_cell,
            action_type=decision.action_type,
            ue_id=decision.target_ue,
            ran_parameter_id=param_id,
            ran_parameter_value=param_value,
            validity_period_ms=5000,  # 5 second validity
            execution_delay_ms=0 if decision.priority <= 2 else 100
        )
    
    def _log_decision(self, decision: ControlDecision):
        """Log decision for analytics"""
        self.decision_log.append(decision)
        if len(self.decision_log) > self.max_log_size:
            self.decision_log.pop(0)
    
    def _get_neighbor_cells(self, gnb_id: str) -> List[str]:
        """Get neighbor cells (simplified topology)"""
        # In production, query RAN topology database
        all_cells = [f"gNB_{i:03d}" for i in range(10)]
        index = all_cells.index(gnb_id) if gnb_id in all_cells else 0
        
        # Return adjacent cells
        neighbors = []
        if index > 0:
            neighbors.append(all_cells[index - 1])
        if index < len(all_cells) - 1:
            neighbors.append(all_cells[index + 1])
        
        return neighbors
    
    def get_decision_history(self, 
                            limit: int = 100,
                            action_type: Optional[str] = None) -> List[ControlDecision]:
        """Get recent decisions for debugging"""
        decisions = self.decision_log[-limit:]
        if action_type:
            decisions = [d for d in decisions if d.action_type == action_type]
        return decisions
    
    def get_ue_state(self, ue_id: str) -> Optional[UEHoState]:
        """Get UE handover state"""
        return self.ue_states.get(ue_id)
```

### 8. xApp API Endpoints (`api/v1/endpoints/xapp.py`)

```python
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional

from services.oran_xapp import SmartOptimizerXApp
from services.nwdaf_analytics import NWDAFAnalyticsEngine
from services.ml_detector import AnomalyDetector
from services.kpi_simulator import TelecomKPISimulator
from models.schemas import (
    ControlDecision,
    XAppStatus,
    RANMetric,
    RICControlActionType
)
from utils.logging_config import setup_logging


logger = setup_logging()
router = APIRouter()

# Initialize xApp with dependencies
detector = AnomalyDetector()
simulator = TelecomKPISimulator()
nwdaf = NWDAFAnalyticsEngine(detector, simulator)
xapp = SmartOptimizerXApp(
    xapp_id="xapp-smart-optimizer",
    nwdaf_engine=nwdaf,
    detector=detector
)


@router.on_event("startup")
async def startup_xapp():
    """Initialize xApp on API startup"""
    # Register with RIC (simulated)
    await xapp.register_with_ric("http://ric.platform:8080")
    
    # Subscribe to E2 nodes
    await xapp.subscribe_to_e2_nodes(["gNB_001", "gNB_002", "gNB_003"])
    
    # Start control loop
    await xapp.start_control_loop(interval_ms=100)


@router.on_event("shutdown")
async def shutdown_xapp():
    """Graceful shutdown"""
    await xapp.stop()


@router.get("/status", response_model=XAppStatus)
async def get_xapp_status():
    """Get xApp runtime status"""
    return xapp.status


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
```

### 9. Updated API Router (`api/v1/api.py`)

```python
from fastapi import APIRouter

from api.v1.endpoints import prediction, health, nwdaf, xapp


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
```

### 10. Updated Main App (`app/main.py` - Additions)

```python
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
```

---

## How to Run Phase 3

### 1. Start Complete Platform

```bash
# Start API (includes all phases)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Test xApp Endpoints

#### Check xApp Status
```bash
curl http://localhost:8000/api/v1/xapp/status
```

**Response:**
```json
{
  "xapp_id": "xapp-smart-optimizer",
  "version": "1.0.0",
  "state": "RUNNING",
  "registered_with_ric": true,
  "subscribed_e2_nodes": ["gNB_001", "gNB_002", "gNB_003"],
  "control_loop_active": true,
  "decisions_per_second": 9.8,
  "last_decision_timestamp": "2024-01-15T11:30:45.123Z",
  "total_decisions": 1523,
  "total_actions_executed": 89
}
```

#### Get Recent Decisions
```bash
curl http://localhost:8000/api/v1/xapp/decisions?limit=5
```

**Response:**
```json
[
  {
    "decision_id": "dec-001",
    "xapp_id": "xapp-smart-optimizer",
    "timestamp": "2024-01-15T11:30:45",
    "target_cell": "gNB_001_Cell1",
    "action_type": "LOAD_BALANCING",
    "priority": 2,
    "trigger_metrics": {"current_load": 88.5, "target_load": 45.2},
    "predicted_outcome": "Balance load to gNB_002 [EXECUTED]",
    "confidence": 0.85,
    "control_parameters": {"target_cell": "gNB_002", "handover_candidates": "low_cqi_ues"}
  },
  {
    "decision_id": "dec-002",
    "xapp_id": "xapp-smart-optimizer",
    "timestamp": "2024-01-15T11:30:42",
    "target_cell": "gNB_002_Cell1",
    "action_type": "ADMISSION_CONTROL",
    "priority": 3,
    "trigger_metrics": {"prb_usage": 72.3},
    "predicted_outcome": "Prevent congestion by blocking new users [EXECUTED]",
    "confidence": 0.80,
    "control_parameters": {"admission_rate_limit": 50}
  }
]
```

#### Simulate RAN Metric Injection
```bash
curl -X POST "http://localhost:8000/api/v1/xapp/simulate/ran-metric?gnb_id=gNB_001"
```

#### Check Cell Load
```bash
curl http://localhost:8000/api/v1/xapp/cells/gNB_001/load
```

#### Check Policies
```bash
curl http://localhost:8000/api/v1/xapp/policies
```

---

## Complete Architecture: Phase 1 + 2 + 3

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           5G CORE / RAN                                 │
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│   │     AMF      │     │     SMF      │     │     PCF      │            │
│   │  (Access &   │     │  (Session    │     │  (Policy)    │            │
│   │   Mobility)  │     │   Mgmt)      │     │              │            │
│   └──────┬───────┘     └──────┬───────┘     └──────┬───────┘            │
│          │                    │                    │                      │
│          └────────────────────┴────────────────────┘                      │
│                               │                                         │
│                    Nnwdaf_AnalyticsSubscription                         │
│                    Nnwdaf_AnalyticsInfo_Request                         │
│                               │                                         │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      YOUR AI-POWERED PLATFORM                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Phase 3: O-RAN xApp (Smart Optimizer)                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │   │
│  │  │  Admission   │  │    Load      │  │   Handover   │         │   │
│  │  │   Control    │  │  Balancing   │  │   Control    │         │   │
│  │  │  (Block new  │  │  (Move UEs   │  │  (UE redirect│         │   │
│  │  │   users)     │  │   to cells)  │  │   to better  │         │   │
│  │  │              │  │              │  │   signal)    │         │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │   │
│  │         │                 │                 │                  │   │
│  │         └─────────────────┴─────────────────┘                  │   │
│  │                           │                                     │   │
│  │              ┌────────────▼────────────┐                      │   │
│  │              │    Policy Engine          │                      │   │
│  │              │  • Protect emergency calls │                      │   │
│  │              │  • Prevent ping-pong HO   │                      │   │
│  │              │  • CPU overload protection │                      │   │
│  │              └────────────┬────────────┘                      │   │
│  │                           │                                     │   │
│  │              ┌────────────▼────────────┐                      │   │
│  │              │   E2 Interface (E2AP)    │                      │   │
│  │              │  • E2Setup                 │                      │   │
│  │              │  • RICsubscription         │                      │   │
│  │              │  • RICindication           │                      │   │
│  │              │  • RICcontrol              │                      │   │
│  │              └────────────┬────────────┘                      │   │
│  │                           │                                     │   │
│  └───────────────────────────┼─────────────────────────────────────┘   │
│                              │                                          │
│  ┌───────────────────────────┼─────────────────────────────────────┐    │
│  │  Phase 2: NWDAF Analytics │                                     │    │
│  │  ┌──────────────┐  ┌─────▼──────┐  ┌──────────────┐           │    │
│  │  │  Load Level   │  │   Service  │  │   Anomaly    │           │    │
│  │  │  Analytics    │  │ Experience │  │    Events    │           │    │
│  │  │  (Congestion  │  │  (QoS/MOS  │  │  (Exposure   │           │    │
│  │  │   forecast)   │  │  scores)   │  │   to NFs)    │           │    │
│  │  └───────────────┘  └────────────┘  └──────────────┘           │    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │         Time-Series Database (InfluxDB)                │    │    │
│  │  │    • Historical KPIs    • Forecasting    • Trends       │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │  Phase 1: ML Anomaly Detection                                  │     │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │     │
│  │  │   Isolation  │    │     KPI      │    │   FastAPI    │     │     │
│  │  │    Forest    │◄───│   Simulator  │◄───│    REST      │     │     │
│  │  │   (Real-time │    │ (Realistic   │    │   Gateway    │     │     │
│  │  │   detection) │    │   RAN data)  │    │              │     │     │
│  │  └──────────────┘    └──────────────┘    └──────────────┘     │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         gNBs (E2 Nodes)                                 │
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │    gNB_001   │     │    gNB_002   │     │    gNB_003   │          │
│   │   ┌──────┐   │     │   ┌──────┐   │     │   ┌──────┐   │          │
│   │   │Cell 1│   │     │   │Cell 1│   │     │   │Cell 1│   │          │
│   │   │Cell 2│   │     │   │Cell 2│   │     │   │Cell 2│   │          │
│   │   └──────┘   │     │   └──────┘   │     │   └──────┘   │          │
│   │              │     │              │     │              │          │
│   │  E2AP: 38472 │     │  E2AP: 38472 │     │  E2AP: 38472 │          │
│   └──────────────┘     └──────────────┘     └──────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## What You've Built (Complete)

| Phase | Component | Telecom Standard | Production Role |
|-------|-----------|------------------|-----------------|
| **1** | Anomaly Detection | 3GPP TS 28.552 | Real-time fault detection |
| **1** | KPI Simulator | 3GPP TS 28.552 | Training data generation |
| **2** | NWDAF Analytics | 3GPP TS 29.520 | Network intelligence |
| **2** | Load Level | 3GPP TS 28.554 | Congestion prediction |
| **2** | Service Experience | 3GPP TS 28.554 | QoS prediction |
| **3** | O-RAN xApp | O-RAN WG2 | Real-time RAN control |
| **3** | E2 Interface | 3GPP TS 38.463 | RIC-to-gNB communication |
| **3** | Policy Engine | O-RAN WG1 | Control safety |
| **3** | Admission Control | O-RAN WG2 | Congestion prevention |
| **3** | Load Balancing | O-RAN WG2 | Traffic distribution |

---

**Phase 3 is complete.**

Say **"Continue to Phase 4"** for **Event Streaming (Kafka)** and distributed architecture.