"""Ops Alert Handler - Converts queue ops_alert messages to visible dashboard tasks."""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.models.task import Task
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class OpsAlertHandler:
    """Converts ops_alert queue messages to visible dashboard Task records."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 10

    @staticmethod
    @time_bound(timeout_seconds=8)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Convert ops_alert queue message to Task record.

        Args:
            message: ChannelQueueItem with type='ops_alert'
            db: SQLAlchemy session

        Returns:
            {status, task_id, message_id, error_classification, priority, visibility_scope}
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
                f"[OpsAlert] Converting ops_alert to Task: "
                f"message_id={message_id}, classification={error_classification}, "
                f"safety_score={safety_score}"
            )

            # Determine priority based on safety_score
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
                assigned_to_user_id=None,
                visibility_scope="ORG_WIDE",
                tenant_id=1,
            )
            db.add(task)
            db.flush()
            task_id = task.id
            db.commit()

            logger.info(
                f"[OpsAlert] Created ops task: Task #{task_id}, "
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

        except ValueError as ve:
            logger.error(f"[OpsAlert] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[OpsAlert] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[OpsAlert] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that ops alert notification was sent successfully."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_ops_alert_notification_sent(result, db, "ops_alert")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        return message.retry_count < OpsAlertHandler.MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        db.rollback()
        message.retry_count += 1
        message.error = error[:1000]
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=OpsAlertHandler.RETRY_DELAY_MINUTES)
        db.commit()

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        OpsAlertHandler.validate(message, result, db)
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        db.rollback()
        message.status = "FAILED"
        message.error = final_error[:1000]
        message.completed_at = datetime.utcnow()
        db.commit()


def _build_task_description(payload: Dict[str, Any]) -> str:
    """Build detailed task description from alert payload."""
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


def handle_ops_alert(message: Any, db: Session) -> Dict[str, Any]:
    """Handle ops_alert message."""
    return OpsAlertHandler.process(message, db)
