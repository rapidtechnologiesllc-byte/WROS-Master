"""Message Handler: send_pipeline_email  {email_id, candidate_id, kind, ref}

Emails a candidate the next step of their hiring pipeline from the HRMS mailbox, with a
link to their portal. The body (and its portal link) is built here, at send time, so the
link is never stored. Draft-then-send with the draft id on the pipeline_emails row: a
retry re-sends the same draft, never a second email. Anything that stops delivery raises
DeliveryDeferred, so the message stays PENDING ("not sent") until Graph accepts it.

Compensation: none needed; an unsent draft is re-sent by the next attempt.
"""
import html
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.pipeline_email import PipelineEmail
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45


def _onboarding_body(db: Session, candidate: Candidate, company: str, link: str) -> str:
    from app.models.preboarding_document import PreboardingDocument

    docs = db.query(PreboardingDocument).filter(PreboardingDocument.candidate_id == candidate.candidateID,
                                                PreboardingDocument.status == "PENDING").order_by(PreboardingDocument.id).all()
    items = "".join(f"<li>{html.escape(d.document_label)}</li>" for d in docs)
    return (f"<p>Hello {html.escape(candidate.candidateFirstName or 'there')},</p>"
            f"<p>Welcome to {html.escape(company)}! To complete your joining, please upload these documents "
            f"on your portal:</p><ul>{items}</ul>"
            f"<p><a href=\"{html.escape(link, quote=True)}\">Open my portal</a></p>"
            f"<p>Once they are verified we start your background verification. Reply to this email if you "
            f"have any questions.</p>")


COPY = {
    "ONBOARDING_START": ("Welcome to {company} - your joining documents", _onboarding_body),
}


class SendPipelineEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None) -> Dict[str, Any]:
        from app.models.tenant import Tenant
        from app.services.candidate_portal_service import generate_portal_link_url

        payload = message.payload or {}
        email_id = payload.get("email_id")
        row = db.query(PipelineEmail).filter(PipelineEmail.id == email_id).with_for_update().first()
        if row is None or row.kind not in COPY:
            raise ValueError(f"Message {message.id}: pipeline email {email_id!r} not found or unknown kind")
        if row.sent_at is not None:
            return {"status": "already_sent", "email_id": email_id}
        candidate = db.query(Candidate).filter(Candidate.candidateID == row.candidate_id).first()
        if candidate is None or not candidate.candidateEmail:
            raise ValueError(f"Candidate {row.candidate_id} not found or has no email")
        logger.info(f"[PipelineEmail] handler_start {email_id} kind={row.kind}")

        mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
        if row.graph_id is None:
            tenant = db.query(Tenant).filter(Tenant.id == candidate.tenant_id).first()
            company = tenant.name if tenant else "BlitzenX"
            subject, build = COPY[row.kind]
            body = build(db, candidate, company, generate_portal_link_url(db, candidate.candidateID))
            row.graph_id, _, _ = mailbox.create_draft(candidate.candidateEmail, subject.format(company=company),
                                                      body, f"pipeline:{row.id}")
            db.commit()
        if mailbox.is_draft(row.graph_id):
            mailbox.send(row.graph_id)
        row.sent_at = datetime.utcnow()
        db.commit()
        logger.info(f"[PipelineEmail] handler_complete {email_id}")
        return {"status": "sent", "email_id": email_id, "message_sent": True, "delivery_confirmed": True}
