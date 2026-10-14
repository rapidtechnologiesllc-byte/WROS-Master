"""Slack Integration Service - Send ops alerts to #ops-alerts channel via webhook.

Enables Thunder degradation monitoring and system failure notifications.
Uses Slack Incoming Webhook (simple, no auth complexity).
"""
import logging
import json
import os
from typing import Dict, Any
from datetime import datetime, timezone
import requests

logger = logging.getLogger(__name__)


class SlackIntegration:
    """Send formatted messages to Slack channels via Incoming Webhook."""

    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_OPS", "")

    # Severity color mapping for Slack
    SEVERITY_COLORS = {
        "CRITICAL": "#FF0000",    # Red
        "HIGH": "#FF9900",        # Orange
        "MEDIUM": "#FFFF00",      # Yellow
        "LOW": "#0099FF",         # Blue
    }

    @staticmethod
    def send_ops_alert(
        message: str,
        severity: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send ops alert to #ops-alerts channel via webhook.

        Args:
            message: Alert message text
            severity: CRITICAL, HIGH, MEDIUM, or LOW
            context: {alert_type, timestamp, recommendation, recovery_status}

        Returns:
            {
                'status': 'success' | 'failed',
                'message_ts': str (Slack message timestamp),
                'error': str (if failed)
            }
        """
        if not SlackIntegration.SLACK_WEBHOOK_URL:
            logger.warning("[Slack] SLACK_WEBHOOK_OPS not configured, skipping notification")
            return {
                "status": "skipped",
                "message": "Slack webhook not configured",
            }

        try:
            # Build Slack message payload
            color = SlackIntegration.SEVERITY_COLORS.get(severity, "#0099FF")

            payload = {
                "channel": "#ops-alerts",
                "username": "BlitzenX Ops Bot",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 {severity} Alert",
                        "text": message,
                        "fields": [
                            {
                                "title": "Alert Type",
                                "value": context.get("alert_type", "unknown"),
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": context.get("timestamp", datetime.utcnow().isoformat()),
                                "short": True
                            },
                            {
                                "title": "Recommendation",
                                "value": context.get("recommendation", "See dashboard for details"),
                                "short": False
                            },
                            {
                                "title": "Recovery Status",
                                "value": context.get("recovery_status", "Pending investigation"),
                                "short": False
                            }
                        ],
                        "footer": "BlitzenX Production Monitor",
                        "ts": int(datetime.now(timezone.utc).timestamp())
                    }
                ]
            }

            # Send to Slack
            response = requests.post(
                SlackIntegration.SLACK_WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 200:
                logger.info(f"[Slack] ✅ Alert sent: {severity} - {message[:100]}")
                return {
                    "status": "success",
                    "message_ts": response.text,
                    "severity": severity
                }
            else:
                logger.error(f"[Slack] Failed to send alert: HTTP {response.status_code}")
                return {
                    "status": "failed",
                    "error": f"HTTP {response.status_code}",
                    "severity": severity
                }

        except requests.exceptions.Timeout:
            logger.error("[Slack] Request timeout sending alert")
            return {
                "status": "failed",
                "error": "Request timeout",
                "severity": severity
            }
        except Exception as e:
            logger.error(f"[Slack] Unexpected error sending alert: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "severity": severity
            }

    @staticmethod
    def post_to_channel(
        channel: str,
        message: str,
        thread_ts: str = None
    ) -> Dict[str, Any]:
        """
        Post rich formatted message to Slack channel.

        Args:
            channel: Channel name (e.g., "#ops-alerts", "#engineering")
            message: Message text
            thread_ts: Optional thread timestamp for threaded messages

        Returns:
            {
                'status': 'success' | 'failed',
                'message_ts': str,
                'error': str (if failed)
            }
        """
        if not SlackIntegration.SLACK_WEBHOOK_URL:
            logger.warning("[Slack] SLACK_WEBHOOK_OPS not configured, skipping post")
            return {
                "status": "skipped",
                "message": "Slack webhook not configured",
            }

        try:
            payload = {
                "channel": channel,
                "text": message,
                "username": "BlitzenX Bot",
            }

            if thread_ts:
                payload["thread_ts"] = thread_ts

            response = requests.post(
                SlackIntegration.SLACK_WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 200:
                logger.info(f"[Slack] ✅ Message posted to {channel}")
                return {
                    "status": "success",
                    "message_ts": response.text,
                    "channel": channel
                }
            else:
                logger.error(f"[Slack] Failed to post: HTTP {response.status_code}")
                return {
                    "status": "failed",
                    "error": f"HTTP {response.status_code}",
                    "channel": channel
                }

        except Exception as e:
            logger.error(f"[Slack] Error posting to channel: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "channel": channel
            }
