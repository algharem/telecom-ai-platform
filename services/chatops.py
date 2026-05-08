"""
Phase 5: ChatOps Integration
Slack and Teams integration for incident management and automation
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class SlackIntegration:
    """Slack ChatOps integration"""
    
    def __init__(self, webhook_url: Optional[str] = None, bot_token: Optional[str] = None):
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.is_enabled = webhook_url is not None or bot_token is not None
        
        if self.is_enabled:
            try:
                from slack_sdk import WebClient
                if bot_token:
                    self.client = WebClient(token=bot_token)
                    logger.info("[SLACK] Slack bot initialized")
            except ImportError:
                logger.warning("[SLACK] slack-sdk not installed")
                self.is_enabled = False
    
    async def send_incident_alert(self, incident_data: Dict[str, Any]) -> bool:
        """Send incident alert to Slack"""
        if not self.is_enabled:
            return False
        
        try:
            message = self._build_incident_message(incident_data)
            
            if self.webhook_url:
                return await self._send_via_webhook(message)
            elif self.bot_token:
                return await self._send_via_bot(message)
            
        except Exception as e:
            logger.error(f"[SLACK] Error sending alert: {e}")
            return False
    
    async def send_recovery_notification(self, incident_id: str, recovery_actions: List[Dict]) -> bool:
        """Notify about recovery actions"""
        if not self.is_enabled:
            return False
        
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Recovery Actions Initiated"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Incident:* {incident_id}\n*Actions:* {len(recovery_actions)}"
                    }
                }
            ]
            
            for action in recovery_actions:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• *{action.get('action', 'Unknown')}*\n  {action.get('description', '')}"
                    }
                })
            
            message = {"blocks": blocks}
            
            if self.webhook_url:
                return await self._send_via_webhook(message)
            elif self.bot_token:
                return await self._send_via_bot(message)
            
        except Exception as e:
            logger.error(f"[SLACK] Error sending recovery notification: {e}")
            return False
    
    def _build_incident_message(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Slack message for incident"""
        severity = incident_data.get('severity', 'warning').upper()
        severity_color = {
            'INFO': '#36a64f',
            'WARNING': '#ff9900',
            'CRITICAL': '#ff0000',
            'EMERGENCY': '#8b0000'
        }.get(severity, '#808080')
        
        return {
            "attachments": [
                {
                    "color": severity_color,
                    "title": incident_data.get('incident_title', 'Network Incident'),
                    "text": incident_data.get('incident_description', ''),
                    "fields": [
                        {
                            "title": "Severity",
                            "value": severity,
                            "short": True
                        },
                        {
                            "title": "Affected gNBs",
                            "value": ", ".join(incident_data.get('affected_gnbs', [])),
                            "short": True
                        },
                        {
                            "title": "Impact Score",
                            "value": f"{incident_data.get('impact_score', 0):.2%}",
                            "short": True
                        },
                        {
                            "title": "Incident ID",
                            "value": incident_data.get('event_id', 'unknown'),
                            "short": True
                        }
                    ],
                    "footer": "Telecom AI Platform",
                    "ts": int(datetime.utcnow().timestamp())
                }
            ]
        }
    
    async def _send_via_webhook(self, message: Dict[str, Any]) -> bool:
        """Send message via webhook"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=message)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"[SLACK] Webhook send failed: {e}")
            return False
    
    async def _send_via_bot(self, message: Dict[str, Any]) -> bool:
        """Send message via bot API"""
        try:
            # TODO: Implement bot message sending
            logger.debug("[SLACK] Bot message sending not yet implemented")
            return False
        except Exception as e:
            logger.error(f"[SLACK] Bot send failed: {e}")
            return False


class TeamsIntegration:
    """Microsoft Teams ChatOps integration"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.is_enabled = webhook_url is not None
        logger.info("[TEAMS] Teams integration initialized")
    
    async def send_incident_alert(self, incident_data: Dict[str, Any]) -> bool:
        """Send incident alert to Teams"""
        if not self.is_enabled:
            return False
        
        try:
            message = self._build_adaptive_card(incident_data)
            return await self._send_message(message)
        except Exception as e:
            logger.error(f"[TEAMS] Error sending alert: {e}")
            return False
    
    async def send_recovery_notification(self, incident_id: str, recovery_actions: List[Dict]) -> bool:
        """Notify about recovery actions"""
        if not self.is_enabled:
            return False
        
        try:
            message = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": "Recovery Actions",
                "themeColor": "28a745",
                "sections": [
                    {
                        "activityTitle": "Recovery Actions Initiated",
                        "facts": [
                            {"name": "Incident ID", "value": incident_id},
                            {"name": "Actions Count", "value": str(len(recovery_actions))}
                        ]
                    }
                ]
            }
            return await self._send_message(message)
        except Exception as e:
            logger.error(f"[TEAMS] Error sending notification: {e}")
            return False
    
    def _build_adaptive_card(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Microsoft Teams adaptive card"""
        severity_color = {
            'info': '#0078d4',
            'warning': '#ff9500',
            'critical': '#e81123',
            'emergency': '#a80000'
        }.get(incident_data.get('severity', 'warning').lower(), '#0078d4')
        
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "Container",
                    "style": "emphasis",
                    "items": [
                        {
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "width": "stretch",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": incident_data.get('incident_title', 'Network Incident'),
                                            "weight": "bolder",
                                            "size": "large"
                                        },
                                        {
                                            "type": "TextBlock",
                                            "text": incident_data.get('incident_description', ''),
                                            "wrap": True,
                                            "spacing": "small"
                                        }
                                    ]
                                },
                                {
                                    "width": "auto",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": incident_data.get('severity', 'WARNING').upper(),
                                            "color": severity_color,
                                            "weight": "bolder"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {
                            "name": "Affected gNBs:",
                            "value": ", ".join(incident_data.get('affected_gnbs', []))
                        },
                        {
                            "name": "Impact Score:",
                            "value": f"{incident_data.get('impact_score', 0):.2%}"
                        },
                        {
                            "name": "Incident ID:",
                            "value": incident_data.get('event_id', 'unknown')
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "View Incident",
                    "url": f"https://monitoring.example.com/incidents/{incident_data.get('event_id', 'unknown')}"
                },
                {
                    "type": "Action.OpenUrl",
                    "title": "Dashboard",
                    "url": "https://monitoring.example.com/dashboard"
                }
            ]
        }
    
    async def _send_message(self, message: Dict[str, Any]) -> bool:
        """Send message via Teams webhook"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"[TEAMS] Send failed: {e}")
            return False


class ChatOpsManager:
    """Central ChatOps management"""
    
    def __init__(self):
        self.slack: Optional[SlackIntegration] = None
        self.teams: Optional[TeamsIntegration] = None
    
    def initialize_slack(self, webhook_url: Optional[str] = None, bot_token: Optional[str] = None):
        """Initialize Slack integration"""
        self.slack = SlackIntegration(webhook_url, bot_token)
    
    def initialize_teams(self, webhook_url: Optional[str] = None):
        """Initialize Teams integration"""
        self.teams = TeamsIntegration(webhook_url)
    
    async def notify_incident(self, incident_data: Dict[str, Any]):
        """Notify all integrated platforms about incident"""
        tasks = []
        
        if self.slack and self.slack.is_enabled:
            tasks.append(self.slack.send_incident_alert(incident_data))
        
        if self.teams and self.teams.is_enabled:
            tasks.append(self.teams.send_incident_alert(incident_data))
        
        if tasks:
            import asyncio
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"[CHATOPS] Notified {len(tasks)} platforms")
            return all(r is True for r in results)
        
        return False
    
    async def notify_recovery(self, incident_id: str, recovery_actions: List[Dict]):
        """Notify about recovery actions"""
        tasks = []
        
        if self.slack and self.slack.is_enabled:
            tasks.append(self.slack.send_recovery_notification(incident_id, recovery_actions))
        
        if self.teams and self.teams.is_enabled:
            tasks.append(self.teams.send_recovery_notification(incident_id, recovery_actions))
        
        if tasks:
            import asyncio
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return all(r is True for r in results)
        
        return False


# Global instance
chatops_manager: Optional[ChatOpsManager] = None


def initialize_chatops(slack_webhook: Optional[str] = None,
                      slack_bot_token: Optional[str] = None,
                      teams_webhook: Optional[str] = None):
    """Initialize ChatOps integrations"""
    global chatops_manager
    chatops_manager = ChatOpsManager()
    
    if slack_webhook or slack_bot_token:
        chatops_manager.initialize_slack(slack_webhook, slack_bot_token)
    
    if teams_webhook:
        chatops_manager.initialize_teams(teams_webhook)
    
    logger.info("[CHATOPS] ChatOps manager initialized")
