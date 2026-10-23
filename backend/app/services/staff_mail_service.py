"""Email to a member of staff through the working mail path: the send_staff_email queue task, sent
from the HRMS mailbox over Graph by SendStaffEmailHandler (draft-then-send, retried until Graph
accepts it). Used where a person must act: a timesheet waiting for approval, a decision on their
timesheet, a missing timesheet.

queue_staff_email() is called after the caller's commit. key makes it idempotent: the same key
never queues a second email (enqueue_once on a deterministic task id)."""
import html
import logging
from typing import Optional

from app.core.config import settings
from app.models.user import Users

logger = logging.getLogger(__name__)

STAFF_EMAIL_TASK = "send_staff_email"


def app_link(path: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{path}"


def queue_staff_email(user: Users, *, key: str, subject: str, paragraphs, link_path: Optional[str] = None,
                      link_label: str = "Open in WROS") -> bool:
    """Queue one email to `user`. Returns False when this key was already queued. A user without
    an email address is a data problem: raised, never skipped."""
    from app.services.thunder_mail.cadence_service import enqueue_once

    if not user.UserEmail:
        raise ValueError(f"User {user.UserID} has no email address; cannot send '{subject}'.")
    body = f"<p>Hello {html.escape(user.UserName or user.UserEmail.split('@')[0])},</p>"
    body += "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs if p)
    if link_path:
        body += f"<p><a href=\"{html.escape(app_link(link_path), quote=True)}\">{html.escape(link_label)}</a></p>"
    task_id = f"staff-email-{key}"
    queued = enqueue_once(STAFF_EMAIL_TASK, task_id,
                          {"user_id": user.UserID, "subject": subject, "html": body}, user.tenant_id)
    logger.info(f"[StaffEmail] {task_id} {'queued' if queued else 'already queued'} for {user.UserID}")
    return queued
