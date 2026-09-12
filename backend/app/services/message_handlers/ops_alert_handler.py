"""
Ops Alert Handler - Converts queue ops_alert messages to visible dashboard tasks

When QueueDoctorService escalates a stuck message, it queues an 'ops_alert' task.
This handler converts that queue message into a visible Task record that ops users
can see on the dashboard based on their ops role.

Task routing:
- visibility_scope=ORG_WIDE: All ops users see this task
- assigned_to_user_id=None: Unassigned initially, ops team picks it up
- priority: Based on safety_score (URGENT if <60, HIGH if <80, MEDIUM otherwise)
- category="Operations", subcategory="StaleMessageDetection"
"""
import logging
import json
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.task import Task
from app.core.logging import logger as core_logger

logger = logging.getLogger(__name__)


class OpsAlertHandler:
    """Converts ops_alert queue messages to visible dashboard Task records"""

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Convert ops_alert queue message to Task record.

        Input message.payload:
        {
            'alert_type': 'stuck_message_diagnosis',
            'message_id': '...',
            'message_type': '...',
            'error_classification': 'TIMEOUT_LOOP' | 'LARGE_PAYLOAD' | 'DB_POOL' | etc,
            'safety_score': 0-100,
            'root_cause': 'Description of root cause',
            'recommended_action': 'What ops should do',
            'recovery_attempted': bool,
            'recovery_success': bool,
            'time_in_processing_seconds': int,
            'next_action': 'manual_intervention_required' | ...
        }

        Output:
        - Creates Task record visible to all ops users
        - Task appears on dashboard with priority based on safety_score
        - Returns task creation result
        """
        try:
            payload = message.payload or {}
            alert_type = payload.get('alert_type', 'ops_alert')
            message_id = payload.get('message_id', 'UNKNOWN')
            error_classification = payload.get('error_classification', 'UNKNOWN')
            safety_score = payload.get('safety_score', 50)
            root_cause = payload.get('root_cause', '')
            recommended_action = payload.get('recommended_action', '')

            logger.info(
                f"[OpsAlertHandler] Converting ops_alert to Task: "
                f"message_id={message_id}, classification={error_classification}, "
                f"safety_score={safety_score}"
            )

            # Determine priority based on safety_score
            # Lower score = higher risk = higher priority
            if safety_score < 60:
                priority = "URGENT"
            elif safety_score < 80:
                priority = "HIGH"
            else:
                priority = "MEDIUM"

            # Build task title
            title = f"Ops Alert: {error_classification} - Message {message_id[:8]}"

            # Build task description with full diagnosis data
            description = _build_task_description(payload)

            # Create Task record - visible to all ops users via ORG_WIDE scope
            task = Task(
                title=title,
                description=description,
                task_type="TICKET",
                category="Operations",
                subcategory="StaleMessageDetection",
                priority=priority,
                status="NEW",
                assigned_to_user_id=None,  # Unassigned - all ops users see it
                visibility_scope="ORG_WIDE",  # All ops users with ops-alerts permission
                tenant_id=1,
            )
            db.add(task)
            db.flush()
            task_id = task.id
            db.commit()

            logger.info(
                f"[OpsAlertHandler] Created ops task: Task #{task_id}, "
                f"priority={priority}, classification={error_classification}"
            )

            return {
                "status": "ops_alert_created",
                "task_id": task_id,
                "message_id": message_id,
                "error_classification": error_classification,
                "priority": priority,
                "visibility_scope": "ORG_WIDE"
            }

        except Exception as e:
            logger.error(
                f"[OpsAlertHandler] Failed to convert ops_alert to task: {e}",
                exc_info=True
            )
            raise


def _build_task_description(payload: Dict[str, Any]) -> str:
    """Build detailed task description from alert payload"""
    lines = [
        "=== OPS ALERT DIAGNOSIS ===",
        "",
        f"Message ID: {payload.get('message_id', 'N/A')}",
        f"Message Type: {payload.get('message_type', 'N/A')}",
        f"Error Classification: {payload.get('error_classification', 'UNKNOWN')}",
        f"Safety Score: {payload.get('safety_score', 'N/A')}/100",
        f"Time in Processing: {payload.get('time_in_processing_seconds', 'N/A')} seconds",
        "",
        "ROOT CAUSE:",
        payload.get('root_cause', 'Unknown'),
        "",
        "RECOMMENDED ACTION:",
        payload.get('recommended_action', 'Manual investigation required'),
        "",
        "RECOVERY ATTEMPT STATUS:",
        f"Attempted: {payload.get('recovery_attempted', False)}",
        f"Success: {payload.get('recovery_success', False) if payload.get('recovery_attempted') else 'N/A'}",
        "",
        "NEXT ACTION:",
        payload.get('next_action', 'Pending ops review'),
    ]

    return "\n".join(lines)
