"""
PHASE 3: MONITORING ALERTS (2026-09-19)

Real-time alerts for zero-tolerance policy violations:
- Bypass attempt detection (--no-verify, force push)
- Gate failure escalation
- Cascade failure detection
- Architect accuracy drops
- Production incidents

Alerts integrate with Slack, email, and escalation to leadership.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # Within 1 hour
    MEDIUM = "medium"  # Within 4 hours
    LOW = "low"  # Informational


class AlertChannel(Enum):
    """Where alerts are sent."""
    SLACK = "slack"
    EMAIL = "email"
    ESCALATION = "escalation"  # To CEO/leadership


class Phase3MonitoringAlerts:
    """
    Real-time alert system for zero-tolerance violations.

    Endpoints:
    - POST /alerts/bypass-attempt
    - POST /alerts/gate-failure
    - POST /alerts/cascade-detected
    - POST /alerts/accuracy-drop
    - POST /alerts/incident
    - GET /alerts/status
    """

    def __init__(self):
        """Initialize monitoring alerts."""
        self.alerts_sent: List[Dict] = []
        self.escalation_history: List[Dict] = []
        self.alert_thresholds = {
            "bypass_attempts_per_hour": 1,  # Alert if > 1 per hour
            "gate_failures_per_hour": 5,  # Alert if > 5 per hour
            "accuracy_drop_threshold": 0.85,  # Alert if < 85%
            "cascade_detection_threshold": 3,  # Alert if > 3 cascades per hour
        }

    def alert_bypass_attempt(
        self,
        developer: str,
        commit_id: str,
        attempt_type: str,  # --no-verify, force_push
    ) -> None:
        """Alert on gate bypass attempt."""
        alert = {
            "timestamp": datetime.now(),
            "type": "bypass_attempt",
            "severity": AlertSeverity.CRITICAL,
            "developer": developer,
            "commit_id": commit_id,
            "attempt_type": attempt_type,
        }

        self.alerts_sent.append(alert)

        logger.warning(
            f"[ALERT] CRITICAL: Bypass attempt by {developer} "
            f"({attempt_type}) on commit {commit_id}"
        )

        # Send to Slack + Escalate
        self._send_alert(alert, [AlertChannel.SLACK, AlertChannel.ESCALATION])

        # Record escalation
        self._escalate_to_leadership(
            f"Gate bypass attempted by {developer}",
            f"Developer {developer} attempted {attempt_type} on {commit_id}. "
            f"This violates zero-tolerance policy.",
        )

    def alert_gate_failure(
        self,
        developer: str,
        violations_count: int,
        top_violations: List[str],
    ) -> None:
        """Alert on repeated gate failures."""
        alert = {
            "timestamp": datetime.now(),
            "type": "gate_failure",
            "severity": AlertSeverity.HIGH,
            "developer": developer,
            "violations_count": violations_count,
            "top_violations": top_violations,
        }

        self.alerts_sent.append(alert)

        logger.warning(
            f"[ALERT] HIGH: Gate failure for {developer} "
            f"({violations_count} violations)"
        )

        # Send to Slack
        self._send_alert(alert, [AlertChannel.SLACK, AlertChannel.EMAIL])

    def alert_cascade_detected(
        self,
        cascade_id: str,
        affected_services: List[str],
        depth: int,
    ) -> None:
        """Alert on cascade failure detection."""
        alert = {
            "timestamp": datetime.now(),
            "type": "cascade_detected",
            "severity": AlertSeverity.CRITICAL,
            "cascade_id": cascade_id,
            "affected_services": affected_services,
            "depth": depth,
        }

        self.alerts_sent.append(alert)

        logger.error(
            f"[ALERT] CRITICAL: Cascade detected {cascade_id} "
            f"({len(affected_services)} services, depth {depth})"
        )

        # Escalate immediately
        self._send_alert(alert, [AlertChannel.SLACK, AlertChannel.ESCALATION])
        self._escalate_to_leadership(
            f"Cascade failure detected: {cascade_id}",
            f"Cascade depth {depth} affects {', '.join(affected_services)}. "
            f"Immediate human review required.",
        )

    def alert_accuracy_drop(
        self,
        component: str,  # architect, gate, incident_response
        previous_accuracy: float,
        current_accuracy: float,
    ) -> None:
        """Alert on quality metric drop."""
        drop = previous_accuracy - current_accuracy

        alert = {
            "timestamp": datetime.now(),
            "type": "accuracy_drop",
            "severity": AlertSeverity.MEDIUM if drop < 0.1 else AlertSeverity.HIGH,
            "component": component,
            "previous_accuracy": previous_accuracy,
            "current_accuracy": current_accuracy,
            "drop": drop,
        }

        self.alerts_sent.append(alert)

        logger.warning(
            f"[ALERT] {alert['severity'].value}: {component} accuracy "
            f"dropped from {previous_accuracy:.0%} to {current_accuracy:.0%}"
        )

        self._send_alert(alert, [AlertChannel.SLACK, AlertChannel.EMAIL])

    def alert_production_incident(
        self,
        incident_id: str,
        severity: str,
        affected_service: str,
        affected_users: int,
    ) -> None:
        """Alert on production incident."""
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "medium": AlertSeverity.MEDIUM,
            "low": AlertSeverity.LOW,
        }

        alert = {
            "timestamp": datetime.now(),
            "type": "production_incident",
            "severity": severity_map.get(severity, AlertSeverity.HIGH),
            "incident_id": incident_id,
            "affected_service": affected_service,
            "affected_users": affected_users,
        }

        self.alerts_sent.append(alert)

        logger.error(
            f"[ALERT] {severity.upper()}: Production incident {incident_id} "
            f"({affected_service}, {affected_users} users)"
        )

        channels = [AlertChannel.SLACK, AlertChannel.EMAIL]
        if alert["severity"] == AlertSeverity.CRITICAL:
            channels.append(AlertChannel.ESCALATION)

        self._send_alert(alert, channels)

    def _send_alert(
        self,
        alert: Dict,
        channels: List[AlertChannel],
    ) -> None:
        """Send alert to specified channels."""
        for channel in channels:
            if channel == AlertChannel.SLACK:
                logger.info(f"[SLACK] Alert: {alert['type']} ({alert['severity'].value})")
            elif channel == AlertChannel.EMAIL:
                logger.info(f"[EMAIL] Alert: {alert['type']} ({alert['severity'].value})")
            elif channel == AlertChannel.ESCALATION:
                logger.info(f"[ESCALATION] Alert: {alert['type']} ({alert['severity'].value})")

    def _escalate_to_leadership(
        self,
        title: str,
        description: str,
    ) -> None:
        """Escalate critical issue to leadership."""
        escalation = {
            "timestamp": datetime.now(),
            "title": title,
            "description": description,
            "status": "pending",
        }

        self.escalation_history.append(escalation)

        logger.error(f"[ESCALATION] {title}: {description}")

    # ======== DASHBOARD ENDPOINTS ========

    def get_alert_status(self) -> Dict:
        """
        GET /alerts/status

        Current alert status and recent alerts.
        """
        critical_alerts = [
            a for a in self.alerts_sent
            if a["severity"] == AlertSeverity.CRITICAL
        ]

        high_alerts = [
            a for a in self.alerts_sent
            if a["severity"] == AlertSeverity.HIGH
        ]

        pending_escalations = [
            e for e in self.escalation_history
            if e["status"] == "pending"
        ]

        return {
            "critical_alerts": len(critical_alerts),
            "high_alerts": len(high_alerts),
            "pending_escalations": len(pending_escalations),
            "recent_critical": [
                {
                    "timestamp": a["timestamp"].isoformat(),
                    "type": a["type"],
                    "details": {k: v for k, v in a.items() if k not in ["timestamp", "type", "severity"]},
                }
                for a in critical_alerts[-5:]
            ],
            "pending_escalations_list": [
                {
                    "timestamp": e["timestamp"].isoformat(),
                    "title": e["title"],
                    "description": e["description"],
                }
                for e in pending_escalations
            ],
        }


# Global instance
_monitoring_alerts_instance: Optional[Phase3MonitoringAlerts] = None


def get_monitoring_alerts() -> Phase3MonitoringAlerts:
    """Get or create global monitoring alerts instance."""
    global _monitoring_alerts_instance
    if _monitoring_alerts_instance is None:
        _monitoring_alerts_instance = Phase3MonitoringAlerts()
    return _monitoring_alerts_instance
