"""
Phase 5: AIOpsAssistant
LLM-powered incident analysis, root cause analysis, and auto-recovery recommendations
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class AIOpsAssistant:
    """
    LLM-powered assistant for AIOps:
    - Analyzes incidents and anomalies
    - Suggests root causes
    - Recommends recovery actions
    - Learns from resolutions
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        self.conversation_history = {}
        self.learned_patterns = {}
        self.is_enabled = openai_api_key is not None
        
        if self.is_enabled:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=openai_api_key)
                logger.info("[AIOPS] AIOpsAssistant initialized with OpenAI API")
            except ImportError:
                logger.warning("[AIOPS] openai library not installed")
                self.is_enabled = False
        else:
            logger.warning("[AIOPS] AIOpsAssistant disabled - no OpenAI API key")
    
    async def analyze_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze incident and provide recommendations"""
        
        if not self.is_enabled:
            return self._generate_fallback_analysis(incident_data)
        
        try:
            incident_id = incident_data.get('event_id', 'unknown')
            
            # Build context for LLM
            context = self._build_incident_context(incident_data)
            
            # Call LLM for analysis
            analysis = await self._call_llm_for_analysis(context)
            
            # Extract structured insights
            insights = self._parse_llm_response(analysis)
            
            # Store in conversation history
            self.conversation_history[incident_id] = {
                'incident': incident_data,
                'analysis': insights,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"[AIOPS] Analyzed incident: {incident_id}")
            return insights
            
        except Exception as e:
            logger.error(f"[AIOPS] Error analyzing incident: {e}")
            return self._generate_fallback_analysis(incident_data)
    
    async def get_recovery_recommendations(self, incident_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recovery action recommendations"""
        
        if not self.is_enabled:
            return self._generate_fallback_recommendations(incident_data)
        
        try:
            incident_id = incident_data.get('event_id', 'unknown')
            
            # Get incident type and context
            affected_gnbs = incident_data.get('affected_gnbs', [])
            severity = incident_data.get('severity', 'warning')
            description = incident_data.get('incident_description', '')
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                affected_gnbs, severity, description
            )
            
            logger.info(f"[AIOPS] Generated {len(recommendations)} recommendations for {incident_id}")
            return recommendations
            
        except Exception as e:
            logger.error(f"[AIOPS] Error generating recommendations: {e}")
            return self._generate_fallback_recommendations(incident_data)
    
    async def suggest_root_cause(self, incident_data: Dict[str, Any], 
                                  related_metrics: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Suggest probable root causes using LLM"""
        
        if not self.is_enabled:
            return self._generate_fallback_root_cause(incident_data)
        
        try:
            # Prepare context
            context = {
                'incident': incident_data.get('incident_description', ''),
                'severity': incident_data.get('severity', 'unknown'),
                'affected_elements': incident_data.get('affected_gnbs', []),
                'related_metrics': related_metrics or {},
                'historical_similar_incidents': self._find_similar_incidents(incident_data)
            }
            
            # Call LLM
            root_cause = await self._call_llm_for_root_cause(context)
            
            logger.info(f"[AIOPS] Identified root cause for incident")
            return root_cause
            
        except Exception as e:
            logger.error(f"[AIOPS] Error suggesting root cause: {e}")
            return self._generate_fallback_root_cause(incident_data)
    
    def _build_incident_context(self, incident_data: Dict[str, Any]) -> str:
        """Build text context for LLM"""
        return f"""
        Incident Analysis Request:
        
        Title: {incident_data.get('incident_title', 'Unknown')}
        Description: {incident_data.get('incident_description', 'No description')}
        Severity: {incident_data.get('severity', 'Unknown')}
        Affected gNBs: {', '.join(incident_data.get('affected_gnbs', []))}
        Impact Score: {incident_data.get('impact_score', 0)}/1.0
        
        Please analyze this incident and provide:
        1. Root cause hypothesis
        2. Affected services/metrics
        3. Recommended recovery actions
        4. Expected recovery time
        """
    
    async def _call_llm_for_analysis(self, context: str) -> str:
        """Call OpenAI API for analysis"""
        try:
            message = await self.client.messages.create(
                model="gpt-4-turbo-preview",
                max_tokens=1000,
                system="You are an expert telecom/5G network AIOps specialist. Analyze incidents and provide actionable recommendations.",
                messages=[
                    {"role": "user", "content": context}
                ]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"[AIOPS] LLM call failed: {e}")
            return ""
    
    async def _call_llm_for_root_cause(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM for root cause analysis"""
        prompt = f"""
        Analyze the following incident and suggest probable root causes:
        
        Incident: {context.get('incident', '')}
        Severity: {context.get('severity', '')}
        Affected: {context.get('affected_elements', [])}
        Metrics: {context.get('related_metrics', {})}
        Similar Past Incidents: {len(context.get('historical_similar_incidents', []))}
        
        Provide response in JSON format with:
        {{"probable_causes": [...], "confidence": 0.0-1.0, "recommended_checks": [...]}}
        """
        
        try:
            message = await self.client.messages.create(
                model="gpt-4-turbo-preview",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"[AIOPS] Root cause analysis failed: {e}")
            return {"probable_causes": [], "confidence": 0, "recommended_checks": []}
    
    async def _generate_recommendations(self, affected_gnbs: List[str], 
                                       severity: str, description: str) -> List[Dict[str, Any]]:
        """Generate recovery recommendations"""
        
        recommendations = []
        
        # Immediate actions for critical incidents
        if severity in ["critical", "emergency"]:
            recommendations.append({
                "action_id": str(uuid.uuid4()),
                "priority": "immediate",
                "action": "Escalate to NOC",
                "description": "Route incident to network operations center",
                "estimated_time": "1-5 minutes"
            })
        
        # Load balancing recommendation
        if "congestion" in description.lower() or "prb" in description.lower():
            recommendations.append({
                "action_id": str(uuid.uuid4()),
                "priority": "high",
                "action": "Trigger Load Balancing",
                "description": f"Redistribute traffic from {affected_gnbs[0] if affected_gnbs else 'affected'} gNB",
                "estimated_time": "5-10 minutes"
            })
        
        # Capacity increase recommendation
        if "throughput" in description.lower() or "latency" in description.lower():
            recommendations.append({
                "action_id": str(uuid.uuid4()),
                "priority": "medium",
                "action": "Scale Resources",
                "description": "Increase processing capacity on affected gNBs",
                "estimated_time": "10-20 minutes"
            })
        
        return recommendations
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured format"""
        try:
            # Try to extract JSON from response
            if "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                return json.loads(response[json_start:json_end])
        except:
            pass
        
        return {
            "analysis": response,
            "root_cause": "Unable to determine",
            "recommendations": []
        }
    
    def _find_similar_incidents(self, incident_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar historical incidents"""
        return []  # TODO: Implement incident similarity search
    
    def _generate_fallback_analysis(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback analysis when LLM is unavailable"""
        return {
            "incident_id": incident_data.get('event_id', 'unknown'),
            "analysis": "LLM analysis unavailable",
            "root_cause_hypothesis": "Unable to determine without LLM",
            "recommended_actions": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _generate_fallback_recommendations(self, incident_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate fallback recommendations"""
        return [
            {
                "action_id": str(uuid.uuid4()),
                "priority": "medium",
                "action": "Manual Investigation",
                "description": "Review metrics and logs manually",
                "estimated_time": "15-30 minutes"
            }
        ]
    
    def _generate_fallback_root_cause(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback root cause"""
        return {
            "probable_causes": ["Unable to determine without LLM analysis"],
            "confidence": 0.0,
            "recommended_checks": ["Check system logs", "Monitor resource usage"]
        }
    
    def get_conversation_history(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation history for incident"""
        return self.conversation_history.get(incident_id)


# Global instance
aiops_assistant: Optional[AIOpsAssistant] = None


def initialize_aiops_assistant(openai_api_key: Optional[str] = None):
    """Initialize the AIOps assistant"""
    global aiops_assistant
    aiops_assistant = AIOpsAssistant(openai_api_key)
    logger.info("[AIOPS] AIOpsAssistant initialized")


async def analyze_incident_with_aiops(incident_data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to analyze incident"""
    if not aiops_assistant:
        logger.warning("[AIOPS] AIOpsAssistant not initialized")
        return {}
    
    return await aiops_assistant.analyze_incident(incident_data)
