"""Flash Notification Handler - Generic handler for internal lifecycle-event
notifications that had no registered handler at all.

Every task name here was enqueued at a call site that had already completed
its real work (the job was updated, the invoice was created, the milestone
was completed, etc.) before enqueuing - the queued task itself is purely a
fan-out notification for other systems to react to. None of these call
sites describe any further mutation beyond "this happened", so the correct,
verifiable action is to make the event durable and visible via a structured
log line (today they simply vanished - dead-lettered with no handler at
all), not to invent unverified downstream behavior.

If a specific one of these later needs real side effects (send an email,
update a cache, trigger a workflow), split it out into its own handler and
remove it from FLASH_NOTIFICATION_TASK_NAMES below.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Every task name that should use this generic handler.
FLASH_NOTIFICATION_TASK_NAMES = [
    "employee_created_flash",
    "invoice_created_flash",
    "invoice_updated_flash",
    "interview_completed_flash",
    "job_approved_flash",
    "job_updated_flash",
    "job_deleted_flash",
    "candidate_job_application_created",
    "candidate_assigned_to_job",
    "candidate_unassigned_from_job",
    "job_application_created",
    "job_application_removed",
    "job_application_status_updated",
    "milestone_created",
    "milestone_completed",
    "revenue_dashboard_update",
    "offer_sent_notification",
]


def handle_flash_notification(message: Any, db: Session) -> Dict[str, Any]:
    """Record a lifecycle-event notification durably via a structured log line."""
    payload = message.payload or {}
    task_type = message.type

    logger.info(f"[FlashNotification] {task_type}: {payload}")

    return {
        "status": "notification_recorded",
        "task_type": task_type,
    }
