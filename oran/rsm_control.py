"""
E2SM-RSM (RAN Slice Management) Control Module.
Handles network slice configuration and resource allocation.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

from utils.exceptions import ORANException


logger = logging.getLogger(__name__)


class SliceType(Enum):
    """3GPP Slice Types (SST)"""
    EMMBB = "eMBB"           # Enhanced Mobile Broadband
    URLLC = "URLLC"          # Ultra-Reliable Low Latency
    MIOT = "mMTC"            # Massive IoT
    V2X = "V2X"              # Vehicle-to-Everything
    CUSTOM = "CUSTOM"        # Operator-specific


class ResourceType(Enum):
    """Slice resource types"""
    PRB = "PRB"              # Physical Resource Blocks
    CPU = "CPU"              # Compute resources
    MEMORY = "MEMORY"        # Memory allocation
    BANDWIDTH = "BANDWIDTH"  # Transport bandwidth


@dataclass
class SliceProfile:
    """Network Slice profile configuration"""
    slice_id: str
    sst: SliceType           # Slice Service Type
    sd: Optional[str]        # Slice Differentiator
    dnn: str                 # Data Network Name
    
    # QoS parameters
    guaranteed_prb_percent: float = 0.0
    max_prb_percent: float = 100.0
    min_throughput_mbps: float = 0.0
    max_latency_ms: float = 100.0
    priority: int = 5        # 1 = highest
    
    # Resource allocation
    cpu_cores: int = 1
    memory_mb: int = 512
    bandwidth_mbps: int = 100


@dataclass
class UEAssociation:
    """UE to Slice association"""
    ue_id: str
    slice_id: str
    associated_at: datetime
    qos_rules: Dict[str, Any]


class RSMController:
    """
    E2SM-RSM (RAN Slice Management) Controller.
    
    Manages network slices in O-RAN:
    - Slice creation/modification/deletion
    - UE-to-slice association
    - Resource allocation per slice
    - Slice isolation enforcement
    """
    
    def __init__(self):
        self.slices: Dict[str, SliceProfile] = {}
        self.ue_associations: Dict[str, UEAssociation] = {}
        self.resource_usage: Dict[str, Dict[ResourceType, float]] = {}
        self._lock = asyncio.Lock()
        
        logger.info("RSM Controller initialized")
    
    async def create_slice(self, profile: SliceProfile) -> str:
        """
        Create new network slice.
        
        Validates resource availability and slice conflicts.
        """
        async with self._lock:
            # Validate slice ID uniqueness
            if profile.slice_id in self.slices:
                raise ORANException(
                    f"Slice {profile.slice_id} already exists",
                    "SLICE_EXISTS"
                )
            
            # Validate resource availability
            total_guaranteed = sum(
                s.guaranteed_prb_percent for s in self.slices.values()
            )
            
            if total_guaranteed + profile.guaranteed_prb_percent > 100:
                raise ORANException(
                    "Insufficient PRB resources for guaranteed allocation",
                    "RESOURCE_EXHAUSTED"
                )
            
            # Create slice
            self.slices[profile.slice_id] = profile
            self.resource_usage[profile.slice_id] = {
                ResourceType.PRB: 0.0,
                ResourceType.CPU: 0.0,
                ResourceType.MEMORY: 0.0,
                ResourceType.BANDWIDTH: 0.0
            }
            
            logger.info(
                f"Created slice {profile.slice_id}: "
                f"SST={profile.sst.value}, "
                f"PRB={profile.guaranteed_prb_percent}-{profile.max_prb_percent}%"
            )
            
            return profile.slice_id
    
    async def modify_slice(self, 
                          slice_id: str,
                          updates: Dict[str, Any]) -> SliceProfile:
        """
        Modify existing slice parameters.
        
        Supports dynamic reconfiguration without service interruption.
        """
        async with self._lock:
            if slice_id not in self.slices:
                raise ORANException(f"Slice {slice_id} not found", "SLICE_NOT_FOUND")
            
            slice_profile = self.slices[slice_id]
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(slice_profile, key):
                    setattr(slice_profile, key, value)
            
            logger.info(f"Modified slice {slice_id}: {updates}")
            
            return slice_profile
    
    async def delete_slice(self, slice_id: str) -> bool:
        """
        Delete network slice and clean up associations.
        """
        async with self._lock:
            if slice_id not in self.slices:
                return False
            
            # Check for active UE associations
            active_ues = [
                ue_id for ue_id, assoc in self.ue_associations.items()
                if assoc.slice_id == slice_id
            ]
            
            if active_ues:
                # Reassociate UEs to default slice or reject
                for ue_id in active_ues:
                    await self._reassociate_ue_to_default(ue_id)
            
            # Clean up
            del self.slices[slice_id]
            del self.resource_usage[slice_id]
            
            logger.info(f"Deleted slice {slice_id}")
            return True
    
    async def associate_ue_to_slice(self, 
                                   ue_id: str, 
                                   slice_id: str,
                                   qos_rules: Optional[Dict] = None) -> UEAssociation:
        """
        Associate UE to a network slice.
        
        Validates slice capacity and UE eligibility.
        """
        async with self._lock:
            if slice_id not in self.slices:
                raise ORANException(f"Slice {slice_id} not found", "SLICE_NOT_FOUND")
            
            slice_profile = self.slices[slice_id]
            
            # Check slice capacity (simplified)
            current_ues = sum(
                1 for assoc in self.ue_associations.values()
                if assoc.slice_id == slice_id
            )
            
            max_ues_per_slice = 1000  # Configurable
            if current_ues >= max_ues_per_slice:
                raise ORANException(
                    f"Slice {slice_id} at capacity",
                    "SLICE_CAPACITY_EXHAUSTED"
                )
            
            # Create or update association
            association = UEAssociation(
                ue_id=ue_id,
                slice_id=slice_id,
                associated_at=datetime.utcnow(),
                qos_rules=qos_rules or self._generate_default_qos(slice_profile)
            )
            
            self.ue_associations[ue_id] = association
            
            logger.info(f"Associated UE {ue_id} to slice {slice_id}")
            
            return association
    
    async def dissociate_ue(self, ue_id: str) -> bool:
        """Remove UE from its current slice"""
        async with self._lock:
            if ue_id not in self.ue_associations:
                return False
            
            association = self.ue_associations.pop(ue_id)
            
            logger.info(f"Dissociated UE {ue_id} from slice {association.slice_id}")
            return True
    
    async def get_slice_resources(self, slice_id: str) -> Dict[ResourceType, float]:
        """Get current resource allocation for slice"""
        async with self._lock:
            if slice_id not in self.slices:
                raise ORANException(f"Slice {slice_id} not found", "SLICE_NOT_FOUND")
            
            return self.resource_usage.get(slice_id, {}).copy()
    
    async def update_resource_usage(self,
                                    slice_id: str,
                                    resource: ResourceType,
                                    usage: float):
        """Update real-time resource usage metrics"""
        async with self._lock:
            if slice_id in self.resource_usage:
                self.resource_usage[slice_id][resource] = usage
    
    def get_slice_statistics(self, slice_id: str) -> Dict:
        """Get comprehensive slice statistics"""
        if slice_id not in self.slices:
            return {}
        
        profile = self.slices[slice_id]
        usage = self.resource_usage.get(slice_id, {})
        
        associated_ues = [
            assoc for assoc in self.ue_associations.values()
            if assoc.slice_id == slice_id
        ]
        
        return {
            "slice_id": slice_id,
            "sst": profile.sst.value,
            "sd": profile.sd,
            "configuration": {
                "guaranteed_prb_percent": profile.guaranteed_prb_percent,
                "max_prb_percent": profile.max_prb_percent,
                "max_latency_ms": profile.max_latency_ms,
                "priority": profile.priority
            },
            "current_usage": {
                r.value: v for r, v in usage.items()
            },
            "associated_ues": len(associated_ues),
            "ue_list": [assoc.ue_id for assoc in associated_ues[:10]]  # Sample
        }
    
    def list_slices(self, sst: Optional[SliceType] = None) -> List[SliceProfile]:
        """List all slices, optionally filtered by type"""
        slices = list(self.slices.values())
        if sst:
            slices = [s for s in slices if s.sst == sst]
        return slices
    
    async def _reassociate_ue_to_default(self, ue_id: str):
        """Move UE to default slice during cleanup"""
        # Find default eMBB slice or create temporary association
        default_slice = next(
            (s for s in self.slices.values() if s.sst == SliceType.EMMBB),
            None
        )
        
        if default_slice:
            await self.associate_ue_to_slice(ue_id, default_slice.slice_id)
            logger.info(f"Reassociated UE {ue_id} to default slice")
    
    def _generate_default_qos(self, slice_profile: SliceProfile) -> Dict:
        """Generate default QoS rules based on slice profile"""
        return {
            "5qi": self._map_sst_to_5qi(slice_profile.sst),
            "arp": slice_profile.priority,
            "gfbr_ul": f"{slice_profile.min_throughput_mbps} Mbps",
            "gfbr_dl": f"{slice_profile.min_throughput_mbps} Mbps",
            "session_ambr_ul": f"{slice_profile.bandwidth_mbps} Mbps",
            "session_ambr_dl": f"{slice_profile.bandwidth_mbps} Mbps"
        }
    
    @staticmethod
    def _map_sst_to_5qi(sst: SliceType) -> int:
        """Map Slice Type to 5QI (5G QoS Identifier)"""
        mapping = {
            SliceType.EMMBB: 9,    # Best effort for broadband
            SliceType.URLLC: 2,    # Critical for low latency
            SliceType.MIOT: 3,     # Low priority for IoT
            SliceType.V2X: 2,      # Critical for safety
            SliceType.CUSTOM: 9
        }
        return mapping.get(sst, 9)
    
    async def optimize_slice_resources(self, slice_id: str) -> Dict:
        """
        AI-driven slice resource optimization.
        
        Analyzes usage patterns and recommends resource adjustments.
        """
        stats = self.get_slice_statistics(slice_id)
        if not stats:
            return {"error": "Slice not found"}
        
        # Simple heuristic-based optimization
        # In production, use ML model for prediction
        current_prb = stats["current_usage"].get("PRB", 0)
        guaranteed = stats["configuration"]["guaranteed_prb_percent"]
        max_prb = stats["configuration"]["max_prb_percent"]
        
        recommendations = []
        
        if current_prb > max_prb * 0.9:
            recommendations.append({
                "action": "increase_max_prb",
                "current": max_prb,
                "recommended": min(100, max_prb + 10),
                "reason": "Approaching PRB limit"
            })
        
        if current_prb < guaranteed * 0.5 and stats["associated_ues"] > 0:
            recommendations.append({
                "action": "reduce_guaranteed_prb",
                "current": guaranteed,
                "recommended": max(5, guaranteed - 5),
                "reason": "Underutilized guaranteed resources"
            })
        
        return {
            "slice_id": slice_id,
            "current_state": stats,
            "recommendations": recommendations,
            "optimization_score": 100 - abs(current_prb - (guaranteed + max_prb) / 2)
        }