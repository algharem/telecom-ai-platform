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
    # --------------

    def _decision_to_e2_action(self, decision: ControlDecision) -> ControlAction:
        """Convert xApp decision to E2SM-RAN Control Action"""
        
        # FIX: Properly extract gNB ID from cell ID
        # Cell ID format: "gNB_001_Cell1" or "gNB_001"
        cell_id = decision.target_cell
        
        # Extract gNB ID (first two parts: "gNB_001")
        parts = cell_id.split("_")
        if len(parts) >= 2:
            gnb_id = f"{parts[0]}_{parts[1]}"  # "gNB_001"
        else:
            gnb_id = cell_id  # Fallback
        
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
            gnb_id=gnb_id,  # Now correctly "gNB_001" not "gNB"
            cell_id=cell_id,
            action_type=decision.action_type,
            ue_id=decision.target_ue,
            ran_parameter_id=param_id,
            ran_parameter_value=param_value,
            validity_period_ms=5000,
            execution_delay_ms=0 if decision.priority <= 2 else 100
        )
    # -----------
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
    
    def _decision_to_e2_action2(self, decision: ControlDecision) -> ControlAction:
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