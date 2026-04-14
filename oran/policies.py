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