"""Message Handler: send_account_email

Emails an account activation (new employee) or password-reset link from the HRMS
mailbox. The token is created here, so its plaintext exists only inside the email.
Anything that stops delivery raises DeliveryDeferred: the message stays PENDING as
"not sent" until Graph accepts it. Draft-then-send with the draft id stored on the
token row, so a retry re-sends the same draft instead of a second link.

Compensation: none needed; an unsent draft is re-sent by the next attempt, and a
superseded/used token is skipped.
"""
import html
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account_activation import AccountActivationToken
from app.models.user import Users
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45

COPY = {
    "ACTIVATE": ("Set up your {company} account",
                 "<p>Hello {name},</p><p>Your {company} account is ready. Set your password to sign in "
                 "(the link works once and expires in 7 days):</p><p><a href=\"{link}\">Set my password</a></p>"
                 "<p>Your login is this email address. You can log your timesheets and expenses, see your "
                 "assignments and tasks once you're in.</p>"),
    "RESET": ("Reset your {company} password",
              "<p>Hello {name},</p><p>Use this link to set a new password (it works once and expires in "
              "2 hours):</p><p><a href=\"{link}\">Reset my password</a></p>"
              "<p>If you didn't ask for this, ignore this email.</p>"),
}


class SendAccountEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None) -> Dict[str, Any]:
        from app.services.account_activation_service import issue_token, link_for

        payload = message.payload or {}
        user_id, purpose = payload.get("user_id"), payload.get("purpose") or "ACTIVATE"
        if not user_id or purpose not in COPY:
            raise ValueError(f"Message {message.id} missing user_id/purpose")
        logger.info(f"[AccountEmail] handler_start user={user_id} purpose={purpose}")

        user = db.query(Users).filter(Users.UserID == user_id).with_for_update().first()
        if user is None or not user.UserEmail:
            raise ValueError(f"User {user_id} not found or has no email")
        if purpose == "ACTIVATE" and not user.password_reset_required:
            return {"status": "already_active", "user_id": user_id}

        # a draft from an interrupted earlier attempt is re-sent as is
        row = db.query(AccountActivationToken).filter(
            AccountActivationToken.user_id == user_id, AccountActivationToken.purpose == purpose,
            AccountActivationToken.used_at.is_(None), AccountActivationToken.emailed_at.is_(None),
            AccountActivationToken.email_graph_id.isnot(None),
            AccountActivationToken.expires_at > datetime.utcnow(),
        ).order_by(AccountActivationToken.id.desc()).first()

        mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
        if row is None:
            from app.models.tenant import Tenant

            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            company = tenant.name if tenant else "company"
            row, plaintext = issue_token(db, user, purpose)
            subject, body = COPY[purpose]
            body = body.format(company=html.escape(company),
                               name=html.escape(user.UserName or user.UserEmail.split("@")[0]),
                               link=html.escape(link_for(plaintext), quote=True))
            row.email_graph_id, _, _ = mailbox.create_draft(user.UserEmail, subject.format(company=company),
                                                            body, f"account:{row.id}")
            db.commit()
        if mailbox.is_draft(row.email_graph_id):
            mailbox.send(row.email_graph_id)
        row.emailed_at = datetime.utcnow()
        db.commit()
        logger.info(f"[AccountEmail] handler_complete user={user_id} purpose={purpose} token={row.id}")
        return {"status": "sent", "user_id": user_id, "message_sent": True, "delivery_confirmed": True}
