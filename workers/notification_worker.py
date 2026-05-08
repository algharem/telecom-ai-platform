"""
Notification Worker - Subscribes to incidents and sends ChatOps alerts
"""

import logging
from typing import Dict, Any

from streaming.consumers import IncidentConsumer, RecoveryConsumer
from chatops.slack_bot import SlackBot
from services.aiops_assistant import AIOpsAssistant

logger = logging.getLogger(__name__)


class NotificationWorker:
    """Worker that processes incidents and sends notifications"""
    
    def __init__(
        self,
        slack_bot: SlackBot,
        aiops_assistant: AIOpsAssistant,
        kafka_bootstrap_servers: str = "localhost:9092",
    ):
        self.slack_bot = slack_bot
        self.aiops_assistant = aiops_assistant
        self.incident_consumer = IncidentConsumer()
        self.recovery_consumer = RecoveryConsumer()
        self.incidents_processed = 0
        self.alerts_sent = 0
    
    def process_incident(self, incident_dict: Dict[str, Any]):
        """Process incident and send notifications"""
        try:
            self.incidents_processed += 1
            
            # Send to Slack
            if self.slack_bot.send_incident_alert(incident_dict):
                self.alerts_sent += 1
                logger.info(f"Incident alert sent for {incident_dict.get('incident_id')}")
            
            # Get AI-powered analysis
            analysis = self.aiops_assistant.analyze_incident(incident_dict)
            
            # Send analysis to Slack
            if analysis:
                self.slack_bot.send_message(
                    "#incidents",
                    f"AI Analysis: {analysis.get('summary')}"
                )
                logger.info("AI analysis sent to Slack")
            
        except Exception as e:
            logger.error(f"Error processing incident: {e}")
    
    def process_recovery(self, recovery_dict: Dict[str, Any]):
        """Process recovery action and send notifications"""
        try:
            # Send to Slack
            if self.slack_bot.send_recovery_action(recovery_dict):
                logger.info(f"Recovery action sent for {recovery_dict.get('recovery_id')}")
            
        except Exception as e:
            logger.error(f"Error processing recovery: {e}")
    
    def start(self):
        """Start the worker"""
        logger.info("Notification Worker started")
        
        # Create separate threads for incident and recovery consumers
        import threading
        
        incident_thread = threading.Thread(
            target=self.incident_consumer.start_consuming,
            args=(self.process_incident,),
            daemon=True,
        )
        
        recovery_thread = threading.Thread(
            target=self.recovery_consumer.start_consuming,
            args=(self.process_recovery,),
            daemon=True,
        )
        
        incident_thread.start()
        recovery_thread.start()
        
        logger.info("Notification Worker threads started")
    
    def get_stats(self) -> dict:
        """Get worker statistics"""
        return {
            "incidents_processed": self.incidents_processed,
            "alerts_sent": self.alerts_sent,
        }
