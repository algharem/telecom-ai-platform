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
    # -----------------------------

    # oran/e2_interface.py - Updated connect_gnb and send_control_request

    async def connect_gnb(self, gnb_id: str, address: str) -> bool:
        """
        E2 Setup procedure (E2AP E2setupRequest/E2setupResponse).
        Establishes association with gNB.
        """
        logger.info(f"E2 Setup: Connecting to {gnb_id} at {address}")
        
        # Validate gNB ID format
        if not gnb_id or gnb_id == "gNB" or not gnb_id.startswith("gNB_"):
            logger.error(f"Invalid gNB ID format: '{gnb_id}'")
            return False
        
        # Simulate E2 setup handshake
        try:
            # In production: SCTP handshake with gNB
            # For simulation: just mark as connected
            await asyncio.sleep(0.05)  # 50ms simulated handshake
            
            self.connected_gnbs[gnb_id] = True
            logger.info(f"E2 Setup complete: {gnb_id} connected")
            return True
            
        except Exception as e:
            logger.error(f"E2 Setup failed for {gnb_id}: {e}")
            return False

    async def send_control_request(self, action: ControlAction) -> bool:
        """
        E2AP RICcontrolRequest (Procedure Code 8).
        Send control action to gNB via E2SM-RAN Control.
        """
        # Validate inputs
        if not action.gnb_id:
            logger.error("Control action missing gNB ID")
            return False
        
        if action.gnb_id == "gNB":
            logger.error(f"Malformed gNB ID in action: {action.action_id}")
            return False
        
        # Check connection
        if not self.connected_gnbs.get(action.gnb_id):
            logger.warning(f"gNB {action.gnb_id} not in connected list: {list(self.connected_gnbs.keys())}")
            
            # Auto-connect in simulation mode
            connected = await self.connect_gnb(action.gnb_id, f"{action.gnb_id}:38472")
            if not connected:
                raise E2InterfaceException(f"gNB {action.gnb_id} connection failed", action.gnb_id)
        
        # Build and send E2AP message...
    #-------------------
    async def connect_gnb2(self, gnb_id: str, address: str) -> bool:
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
    
    async def send_control_request2(self, action: ControlAction) -> bool:
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