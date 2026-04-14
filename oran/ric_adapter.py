"""
O-RAN RIC (Radio Intelligent Controller) Platform Adapter.
Handles xApp lifecycle management, resource allocation, and platform integration.
"""

import asyncio
import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum

import httpx

from utils.exceptions import ORANException


logger = logging.getLogger(__name__)


class XAppState(Enum):
    """xApp lifecycle states per O-RAN WG2"""
    INIT = "INIT"
    REGISTERED = "REGISTERED"
    SUBSCRIBED = "SUBSCRIBED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    TERMINATING = "TERMINATING"
    ERROR = "ERROR"


@dataclass
class XAppDescriptor:
    """xApp registration descriptor"""
    xapp_id: str
    version: str
    name: str
    description: str
    vendor: str
    max_rics: int = 1
    required_services: List[str] = field(default_factory=list)
    optional_services: List[str] = field(default_factory=list)
    callbacks: Dict[str, str] = field(default_factory=dict)


@dataclass
class ResourceAllocation:
    """Resources allocated to xApp by RIC"""
    cpu_cores: float
    memory_mb: int
    storage_mb: int
    network_bandwidth_mbps: int
    rt_priority: int = 0  # Real-time scheduling priority


class RICPlatformAdapter:
    """
    Adapter for O-RAN RIC Platform (AppMgr, E2Mgr).
    
    Manages:
    - xApp registration and lifecycle
    - Resource allocation requests
    - E2 interface subscriptions
    - Health monitoring and heartbeat
    - Platform service discovery
    """
    
    def __init__(self, 
                 ric_platform_url: str = "http://ric.platform:8080",
                 xapp_descriptor: Optional[XAppDescriptor] = None):
        self.ric_url = ric_platform_url
        self.descriptor = xapp_descriptor
        self.xapp_instance_id: Optional[str] = None
        self.state = XAppState.INIT
        self.allocated_resources: Optional[ResourceAllocation] = None
        self.e2_subscriptions: Dict[str, str] = {}  # gnb_id -> subscription_id
        
        self._heartbeat_task = None
        self._heartbeat_interval = 30  # seconds
        self._running = False
        
        # Callbacks for platform events
        self._platform_callbacks: List[Callable] = []
        
        logger.info(f"RIC Adapter initialized for {ric_platform_url}")
    
    async def register_xapp(self, descriptor: XAppDescriptor) -> str:
        """
        Register xApp with RIC AppMgr.
        
        O-RAN WG2: xApp Registration Procedure
        """
        self.descriptor = descriptor
        
        registration_payload = {
            "xappName": descriptor.name,
            "xappVersion": descriptor.version,
            "xappId": descriptor.xapp_id,
            "vendor": descriptor.vendor,
            "maxRics": descriptor.max_rics,
            "requiredServices": descriptor.required_services,
            "optionalServices": descriptor.optional_services,
            "callbacks": descriptor.callbacks
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ric_url}/appmgr/xapps",
                    json=registration_payload,
                    timeout=10.0
                )
                response.raise_for_status()
                
                result = response.json()
                self.xapp_instance_id = result.get("instanceId", descriptor.xapp_id)
                self.state = XAppState.REGISTERED
                
                logger.info(
                    f"xApp registered: {self.xapp_instance_id} "
                    f"with RIC {self.ric_url}"
                )
                
                # Start heartbeat
                self._start_heartbeat()
                
                return self.xapp_instance_id
                
        except httpx.HTTPError as e:
            self.state = XAppState.ERROR
            raise ORANException(
                f"RIC registration failed: {str(e)}",
                "RIC_REGISTRATION_FAILED"
            )
    
    async def deregister_xapp(self) -> bool:
        """Deregister xApp from RIC"""
        if not self.xapp_instance_id:
            return False
        
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.ric_url}/appmgr/xapps/{self.xapp_instance_id}",
                    timeout=10.0
                )
                
                if response.status_code == 204:
                    self.state = XAppState.TERMINATING
                    logger.info(f"xApp {self.xapp_instance_id} deregistered")
                    return True
                    
        except Exception as e:
            logger.error(f"Deregistration error: {e}")
        
        return False
    
    async def request_resources(self, 
                               requirements: ResourceAllocation) -> ResourceAllocation:
        """
        Request resource allocation from RIC Platform.
        
        Near-RT RIC: Guaranteed resources for real-time control.
        """
        if self.state != XAppState.REGISTERED:
            raise ORANException(
                "xApp must be registered before requesting resources",
                "INVALID_STATE"
            )
        
        resource_request = {
            "instanceId": self.xapp_instance_id,
            "resources": {
                "cpuCores": requirements.cpu_cores,
                "memoryMB": requirements.memory_mb,
                "storageMB": requirements.storage_mb,
                "networkBandwidthMbps": requirements.network_bandwidth_mbps,
                "rtPriority": requirements.rt_priority
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ric_url}/appmgr/xapps/{self.xapp_instance_id}/resources",
                    json=resource_request,
                    timeout=10.0
                )
                response.raise_for_status()
                
                result = response.json()
                self.allocated_resources = ResourceAllocation(
                    cpu_cores=result.get("allocatedCpu", requirements.cpu_cores),
                    memory_mb=result.get("allocatedMemory", requirements.memory_mb),
                    storage_mb=result.get("allocatedStorage", requirements.storage_mb),
                    network_bandwidth_mbps=result.get("allocatedBandwidth", 
                                                      requirements.network_bandwidth_mbps),
                    rt_priority=result.get("rtPriority", requirements.rt_priority)
                )
                
                logger.info(
                    f"Resources allocated: "
                    f"CPU={self.allocated_resources.cpu_cores}, "
                    f"Mem={self.allocated_resources.memory_mb}MB"
                )
                
                return self.allocated_resources
                
        except httpx.HTTPError as e:
            raise ORANException(
                f"Resource request failed: {str(e)}",
                "RESOURCE_ALLOCATION_FAILED"
            )
    
    async def subscribe_to_e2_node(self,
                                   gnb_id: str,
                                   ran_function_id: int,
                                   event_trigger: str = "PERIODIC",
                                   reporting_period_ms: int = 100) -> str:
        """
        Subscribe to E2 node via RIC E2Mgr.
        
        Returns subscription ID for management.
        """
        if self.state not in [XAppState.REGISTERED, XAppState.RUNNING]:
            raise ORANException("xApp not ready for E2 subscription", "INVALID_STATE")
        
        subscription_payload = {
            "instanceId": self.xapp_instance_id,
            "e2NodeId": gnb_id,
            "ranFunctionId": ran_function_id,
            "eventTrigger": {
                "type": event_trigger,
                "periodMs": reporting_period_ms
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ric_url}/e2mgr/subscriptions",
                    json=subscription_payload,
                    timeout=10.0
                )
                response.raise_for_status()
                
                result = response.json()
                subscription_id = result.get("subscriptionId")
                
                self.e2_subscriptions[gnb_id] = subscription_id
                self.state = XAppState.SUBSCRIBED
                
                logger.info(
                    f"E2 subscription created: {subscription_id} "
                    f"for {gnb_id}, RAN function {ran_function_id}"
                )
                
                return subscription_id
                
        except httpx.HTTPError as e:
            raise ORANException(
                f"E2 subscription failed: {str(e)}",
                "E2_SUBSCRIPTION_FAILED"
            )
    
    async def unsubscribe_from_e2_node(self, gnb_id: str) -> bool:
        """Remove E2 subscription"""
        if gnb_id not in self.e2_subscriptions:
            return False
        
        subscription_id = self.e2_subscriptions[gnb_id]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.ric_url}/e2mgr/subscriptions/{subscription_id}",
                    timeout=10.0
                )
                
                if response.status_code == 204:
                    del self.e2_subscriptions[gnb_id]
                    logger.info(f"E2 subscription {subscription_id} removed")
                    return True
                    
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
        
        return False
    
    async def send_e2_control(self,
                             gnb_id: str,
                             control_action: Dict[str, Any]) -> bool:
        """
        Send E2 control request via RIC.
        
        Uses RIC as proxy to gNB for security and coordination.
        """
        if gnb_id not in self.e2_subscriptions:
            raise ORANException(f"No E2 subscription for {gnb_id}", "NOT_SUBSCRIBED")
        
        control_payload = {
            "instanceId": self.xapp_instance_id,
            "subscriptionId": self.e2_subscriptions[gnb_id],
            "controlAction": control_action,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ric_url}/e2mgr/control",
                    json=control_payload,
                    timeout=5.0  # Tight timeout for real-time
                )
                
                success = response.status_code == 200
                if success:
                    logger.debug(f"E2 control sent to {gnb_id}")
                
                return success
                
        except httpx.TimeoutException:
            logger.warning(f"E2 control timeout for {gnb_id}")
            return False
        except Exception as e:
            logger.error(f"E2 control failed: {e}")
            return False
    
    def _start_heartbeat(self):
        """Start periodic health heartbeat to RIC"""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self):
        """Send periodic health updates"""
        while self._running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)  # Retry quickly on error
    
    async def _send_heartbeat(self):
        """Send health status to RIC"""
        if not self.xapp_instance_id:
            return
        
        health_payload = {
            "instanceId": self.xapp_instance_id,
            "state": self.state.value,
            "timestamp": datetime.utcnow().isoformat(),
            "health": {
                "status": "healthy" if self.state == XAppState.RUNNING else "degraded",
                "cpuUsage": 0.0,  # Would get from psutil
                "memoryUsage": 0.0
            },
            "statistics": {
                "e2Subscriptions": len(self.e2_subscriptions),
                "controlMessagesSent": 0  # Would track actual count
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.ric_url}/appmgr/xapps/{self.xapp_instance_id}/health",
                    json=health_payload,
                    timeout=5.0
                )
        except Exception as e:
            logger.warning(f"Heartbeat send failed: {e}")
    
    async def get_platform_services(self) -> List[Dict]:
        """Discover available platform services"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.ric_url}/appmgr/services",
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json().get("services", [])
        except Exception as e:
            logger.error(f"Service discovery failed: {e}")
            return []
    
    def register_platform_callback(self, callback: Callable):
        """Register callback for platform events (e.g., resource changes)"""
        self._platform_callbacks.append(callback)
    
    def get_status(self) -> Dict:
        """Get current adapter status"""
        return {
            "xappInstanceId": self.xapp_instance_id,
            "state": self.state.value,
            "ricPlatform": self.ric_url,
            "allocatedResources": self.allocated_resources.__dict__ if self.allocated_resources else None,
            "e2Subscriptions": {
                gnb: sub for gnb, sub in self.e2_subscriptions.items()
            },
            "heartbeatActive": self._running
        }