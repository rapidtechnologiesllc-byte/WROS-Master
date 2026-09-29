"""Dead Letter Escalation Handler - Surfaces permanently-failed queue messages
as visible ops tasks.

Without this handler, every message that exhausts its retries and gets
dead-lettered enqueues a 'dead_letter_escalation' follow-up that nobody ever
processes - the failure becomes invisible instead of escalated.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.task import Task

logger = logging.getLogger(__name__)


def handle_dead_letter_escalation(message: Any, db: Session) -> Dict[str, Any]:
    """Create a visible ops Task for a message that was dead-lettered."""
    payload = message.payload or {}
    dead_letter_message_id = payload.get("dead_letter_message_id", "UNKNOWN")
    task_type = payload.get("task_type", "unknown")
    error = payload.get("error", "Unknown error")
    retry_count = payload.get("retry_count", 0)

    title = f"Dead-lettered queue message: {task_type} ({dead_letter_message_id[:8] if isinstance(dead_letter_message_id, str) else dead_letter_message_id})"
    description = (
        "=== DEAD LETTER ESCALATION ===\n\n"
        f"Message ID: {dead_letter_message_id}\n"
        f"Task Type: {task_type}\n"
        f"Retry Count: {retry_count}\n"
        f"Created At: {payload.get('created_at', 'N/A')}\n\n"
        "FINAL ERROR:\n"
        f"{error}\n\n"
        "This message exhausted all retries and will not be processed again "
        "automatically. Manual investigation required."
    )

    task = Task(
        title=title,
        description=description,
        task_type="TICKET",
        category="Operations",
        subcategory="DeadLetterQueue",
        priority="HIGH",
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
        f"[DeadLetterEscalation] Created ops task #{task_id} for dead-lettered "
        f"message {dead_letter_message_id} (type={task_type})"
    )

    return {
        "status": "dead_letter_escalated",
        "task_id": task_id,
        "dead_letter_message_id": dead_letter_message_id,
        "task_type": task_type,
    }
