"""
S-013/HRMS-0413 -- Email First Engagement, parallel channel to S-012's
WhatsApp first engagement.

Adapted to real architecture, same posture as S-012: no message_templates
table (hardcoded fallback IS the real template), no per-tenant
sender_email (this codebase's real email sender is the single service
mailbox, EmailService.SERVICE_EMAIL / helpdesk_hrms@blitzenx.com,
already used for every other Thunder-sent email).

BR-01 "parallel execution via Promise.all()" -- this codebase's request/
background-task handling is fully synchronous SQLAlchemy, no async DB
driver; a shared db Session isn't safe to use from two concurrent
threads/tasks. Real adaptation: auto_assign_ai_agent_on_creation calls
WhatsApp and Email first-engagement back-to-back, each independently
resilient (one failing never blocks or delays the other) -- not
literally concurrent, but satisfying the real intent (both channels go
out promptly, independently, within the same SLA window) without
introducing threading into an otherwise single-threaded codebase.
candidate.email is a NOT NULL unique column in this schema (every
candidate has one) -- EMAIL_SKIPPED_NO_EMAIL is implemented per spec
but is structurally unreachable here, not a live gap.
"""
import time
from datetime import datetime
from typing import Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.services.ai_conversation_service import resolve_thunder_config
from app.services.email_service import EmailService

SLA_SECONDS = 60
RETRY_DELAY_SECONDS = 5
COMPANY_NAME = "BlitzenX"
THUNDER_SIGNATURE = "Thunder | Talent Scout | BlitzenX | Powering our global team at lightning speed."

FALLBACK_SUBJECT_TEMPLATE = "Hi {candidate_name} — Thunder from BlitzenX wants to connect"
FALLBACK_BODY_TEMPLATE = (
    "<p>Hi {candidate_name},</p>"
    "<p>I am {agent_name} from {company_name}. I would love to connect about your "
    "background and career goals. Do you have a few minutes?</p>"
    f"<p>{THUNDER_SIGNATURE}</p>"
)


class EmailTemplateRenderFailure(Exception):
    pass


class FirstEmailEngagementFailed(Exception):
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


def _first_name(candidate: Candidate) -> str:
    return candidate.candidateFirstName or candidate.candidateEmail


def _render_greeting_email(db: Session, candidate: Candidate, agent_name: str, tenant_id: str) -> Dict[str, str]:
    """S-014/HRMS-0414 -- tries the real, admin-activated GREETING_EMAIL
    template first; falls back to the hardcoded default otherwise (no
    active template, a render failure, or BR-03's signature missing)."""
    from app.services.message_template_service import TemplateNotFoundError, TemplateRenderError, render_template

    variables = {"candidate_name": _first_name(candidate), "agent_name": agent_name, "company_name": COMPANY_NAME}
    try:
        result = render_template(db, "GREETING_EMAIL", "EMAIL", tenant_id, variables)
        if result["rendered_subject"] and THUNDER_SIGNATURE in result["rendered_body"]:
            return {"subject": result["rendered_subject"], "body": result["rendered_body"]}
        logger.warning("[EmailFirstEngagement] Active GREETING_EMAIL template is missing subject or signature -- using hardcoded fallback.")
    except (TemplateNotFoundError, TemplateRenderError) as exc:
        logger.info(f"[EmailFirstEngagement] Using hardcoded GREETING_EMAIL fallback ({exc.__class__.__name__}): {exc}")

    subject = FALLBACK_SUBJECT_TEMPLATE.format(candidate_name=_first_name(candidate))
    body = FALLBACK_BODY_TEMPLATE.format(candidate_name=_first_name(candidate), agent_name=agent_name, company_name=COMPANY_NAME)

    # BR-04/critical validation: no un-replaced {...} anywhere in EITHER
    # subject or body, and BR-03: signature must be present.
    for label, text in (("subject", subject), ("body", body)):
        if "{" in text and "}" in text:
            raise EmailTemplateRenderFailure(f"Un-replaced template variable in rendered {label}: {text!r}")
    if THUNDER_SIGNATURE not in body:
        raise EmailTemplateRenderFailure("Rendered body is missing the mandatory Thunder signature block.")

    return {"subject": subject, "body": body}


def _already_sent(db: Session, conversation_id: int) -> bool:
    return (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "FIRST_EMAIL_SENT")
        .first()
        is not None
    )


def _send_attempt(candidate: Candidate, subject: str, body: str) -> bool:
    try:
        EmailService.send_email(to_email=candidate.candidateEmail, subject=subject, body_content=body, is_html=True)
        return True
    except HTTPException as exc:
        logger.warning(f"[EmailFirstEngagement] Send attempt failed: {exc.detail}")
        return False
    except Exception as exc:
        logger.warning(f"[EmailFirstEngagement] Send attempt raised: {exc}")
        return False


def send_first_email_engagement(
    db: Session, candidate_id: str, tenant_id: str, *, _sleep=time.sleep,
) -> Dict:
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise FirstEmailEngagementFailed("CANDIDATE_NOT_FOUND", candidate_id)

    if not candidate.candidateEmail:
        # Structurally unreachable (candidateEmail is NOT NULL/unique in
        # this schema) -- implemented per spec anyway, fails closed.
        logger.info(f"[EmailFirstEngagement] EMAIL_SKIPPED_NO_EMAIL for candidate {candidate_id}")
        return {"status": "skipped", "reason": "NO_EMAIL", "candidate_id": candidate_id}

    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id, CandidateConversation.tenant_id == tenant_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if not conversation:
        raise FirstEmailEngagementFailed("NO_CONVERSATION", candidate_id)

    if _already_sent(db, conversation.id):
        logger.info(f"[EmailFirstEngagement] DUPLICATE_PREVENTED for candidate {candidate_id}")
        return {"status": "duplicate_prevented", "candidate_id": candidate_id, "conversation_id": conversation.id}

    thunder_config = resolve_thunder_config(db, tenant_id)

    try:
        rendered = _render_greeting_email(db, candidate, thunder_config["name"], tenant_id)
    except EmailTemplateRenderFailure as exc:
        logger.error(f"[EmailFirstEngagement] TEMPLATE_RENDER_FAILURE: {exc}")
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="FIRST_ENGAGEMENT_FAILED", event_data={"channel": "email", "reason": "TEMPLATE_RENDER_FAILURE", "detail": str(exc)}, triggered_by="system"))
        db.commit()
        raise FirstEmailEngagementFailed("TEMPLATE_RENDER_FAILURE", str(exc))

    # BR: at most two attempts, one retry after 5s -- independent of
    # WhatsApp's own retry loop.
    delivered = _send_attempt(candidate, rendered["subject"], rendered["body"])
    if not delivered:
        _sleep(RETRY_DELAY_SECONDS)
        delivered = _send_attempt(candidate, rendered["subject"], rendered["body"])

    if not delivered:
        logger.warning(f"[EmailFirstEngagement] FIRST_EMAIL_FAILED for candidate {candidate_id} after 2 attempts")
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="FIRST_EMAIL_FAILED", event_data={"reason": "API_FAILURE", "candidate_id": candidate_id}, triggered_by="system"))
        db.commit()
        return {"status": "failed", "reason": "API_FAILURE", "candidate_id": candidate_id, "conversation_id": conversation.id}

    # Real storeOutboundEmailMessage() equivalent -- same ConversationEvent
    # log every other channel this session writes to.
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ai_message_sent",
        event_data={"channel": "email", "subject": rendered["subject"], "body": rendered["body"], "to": candidate.candidateEmail, "delivered": True, "auto_generated": True, "message_type": "first_engagement"},
        triggered_by="ai_agent",
    ))

    # BR-02: SLA measured independently per channel.
    now = datetime.utcnow()
    created_at = candidate.candidateCreatedAt or now
    elapsed_seconds = max((now - created_at).total_seconds(), 0)
    sla_event_type = "SLA_MET" if elapsed_seconds <= SLA_SECONDS else "SLA_BREACH"
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type=sla_event_type,
        event_data={"channel": "email", "candidate_id": candidate_id, "elapsed_seconds": elapsed_seconds, "breach_type": "FIRST_EMAIL" if sla_event_type == "SLA_BREACH" else None},
        triggered_by="system",
    ))
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="FIRST_EMAIL_SENT",
        event_data={"candidate_id": candidate_id, "conversation_id": conversation.id, "sent_at": now.isoformat()},
        triggered_by="system",
    ))
    conversation.updated_at = now
    db.add(conversation)
    db.commit()

    logger.info(f"[EmailFirstEngagement] Sent first email to candidate {candidate_id} in {elapsed_seconds:.1f}s ({sla_event_type})")
    return {
        "status": "sent", "candidate_id": candidate_id, "conversation_id": conversation.id,
        "elapsed_seconds": elapsed_seconds, "sla_met": sla_event_type == "SLA_MET",
    }
