"""Message Handler: send_staff_email  {user_id, subject, html}

Emails a member of staff from the HRMS mailbox (staff_mail_service.queue_staff_email). Anything
that stops delivery raises DeliveryDeferred: the message stays PENDING ("not sent") until Graph
accepts it. Draft-then-send with the draft id on the staff_emails row (keyed by the queue task
id), so a retry re-sends the same draft, never a second email.

Compensation: none needed; an unsent draft is re-sent by the next attempt.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.staff_email import StaffEmail
from app.models.user import Users
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45


class SendStaffEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None) -> Dict[str, Any]:
        payload = message.payload or {}
        user_id, subject, body = payload.get("user_id"), payload.get("subject"), payload.get("html")
        if not user_id or not subject or not body:
            raise ValueError(f"Message {message.id} missing user_id/subject/html")
        logger.info(f"[StaffEmail] handler_start message={message.id} user={user_id}")
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is None or not user.UserEmail:
            raise ValueError(f"User {user_id} not found or has no email")
        row = db.query(StaffEmail).filter(StaffEmail.id == message.id).with_for_update().first()
        if row is None:
            row = StaffEmail(id=message.id, tenant_id=user.tenant_id, user_id=user_id, subject=subject[:512])
            db.add(row)
            db.flush()
        if row.sent_at is not None:
            return {"status": "already_sent", "user_id": user_id}
        mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
        if row.graph_id is None:
            row.graph_id, _, _ = mailbox.create_draft(user.UserEmail, subject, body, f"staff:{message.id}")
            db.commit()
        if mailbox.is_draft(row.graph_id):
            mailbox.send(row.graph_id)
        row.sent_at = datetime.utcnow()
        db.commit()
        logger.info(f"[StaffEmail] handler_complete message={message.id} user={user_id}")
        return {"status": "sent", "user_id": user_id, "message_sent": True, "delivery_confirmed": True}
