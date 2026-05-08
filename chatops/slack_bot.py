"""
Slack Bot Integration for ChatOps
"""

import logging
import os
from typing import Optional, Dict, Any
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class SlackBot:
    """Slack bot for incident notifications and ChatOps"""
    
    def __init__(self, webhook_url: Optional[str] = None, token: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        self.bot_name = "TelecomAI"
    
    def send_message(self, channel: str, text: str, blocks: Optional[list] = None) -> bool:
        """Send message to Slack channel"""
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        try:
            payload = {
                "channel": channel,
                "text": text,
                "username": self.bot_name,
                "icon_emoji": ":robot_face:",
            }
            
            if blocks:
                payload["blocks"] = blocks
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False
    
    def send_incident_alert(self, incident: Dict[str, Any]) -> bool:
        """Send incident alert to Slack"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 INCIDENT ALERT",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident ID:*\n{incident.get('incident_id')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{incident.get('severity')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*gNB:*\n{incident.get('gnb_id')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{incident.get('status')}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title:*\n{incident.get('title')}\n\n*Description:*\n{incident.get('description')}",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Details",
                        },
                        "url": f"http://localhost:8000/incidents/{incident.get('incident_id')}",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Acknowledge",
                        },
                        "value": f"ack_{incident.get('incident_id')}",
                    },
                ],
            },
        ]
        
        return self.send_message(
            "#incidents",
            f"Incident Alert: {incident.get('title')}",
            blocks=blocks
        )
    
    def send_recovery_action(self, recovery: Dict[str, Any]) -> bool:
        """Send recovery action notification"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ AUTO-RECOVERY ACTION",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Recovery ID:*\n{recovery.get('recovery_id')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Priority:*\n{recovery.get('priority')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*ETA:*\n{recovery.get('estimated_time_minutes')} min",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{recovery.get('status')}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Action:*\n{recovery.get('action')}\n\n*Details:*\n{recovery.get('description')}",
                },
            },
        ]
        
        return self.send_message(
            "#recovery",
            f"Recovery Action: {recovery.get('action')}",
            blocks=blocks
        )
    
    def send_forecast(self, forecast: Dict[str, Any]) -> bool:
        """Send forecast notification"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 FORECAST UPDATE",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*gNB:* {forecast.get('gnb_id')}\n*Metric:* {forecast.get('metric')}\n*Forecast:* {forecast.get('forecast_value')} {forecast.get('unit')}",
                },
            },
        ]
        
        return self.send_message(
            "#forecasts",
            f"Forecast for {forecast.get('metric')}",
            blocks=blocks
        )
