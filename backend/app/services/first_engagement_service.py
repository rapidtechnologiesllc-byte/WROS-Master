"""
import logging
S-012/HRMS-0412 -- WhatsApp First Engagement, 60-Second Rule.

Adapted to real architecture: no `message_templates` table exists here
(the spec's own Step 3 explicitly sanctions a hardcoded fallback when
no active template is found -- that fallback IS this codebase's real
template, since no template-management story is built either). No
`tenants` row per candidate (this subsystem's real "tenant" is the org-
owner Users row -- see ai_conversation_service.resolve_thunder_config).
Stores via the existing ConversationEvent log through
send_whatsapp_message() directly (not the higher-level
send_thunder_message() wrapper) -- see _send_first_whatsapp_attempt()'s
docstring for why the retry-once rule needs the lower-level call.

Real gap this story exposed and fixed: WhatsApp sends were structurally
impossible for any newly-created candidate before this round -- nothing
captured whatsapp_outreach consent at candidate creation. Fixed at the
source (candidate_service.create_candidate_safe), not worked around
here.
"""
import logging
import time
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.services.ai_conversation_service import DEFAULT_THUNDER_DISPLAY_NAME, resolve_thunder_config
from app.services.thunder_service import ConsentNotGiven, has_active_consent
from app.services.whatsapp_routing_service import (
    ConversationOwnedByHuman,
    NoWhatsAppNumberAvailable,
    is_ai_owner,
    resolve_outbound_whatsapp_number,
)

SLA_SECONDS = 60
RETRY_DELAY_SECONDS = 5
MAX_MESSAGE_LENGTH = 4096

FALLBACK_GREETING_TEMPLATE = (
    "Hi {candidate_name}, I am {agent_name} from {company_name}. I would love to "
    "connect about your background and career goals. Do you have a few minutes?"
)
COMPANY_NAME = "BlitzenX"

def _first_name(candidate: Candidate) -> str:
    return candidate.candidateFirstName or candidate.candidateEmail

def _render_greeting(db: Session, candidate: Candidate, agent_name: str, tenant_id: str) -> str:
    """
    S-014/HRMS-0414 -- tries the real, admin-activated GREETING_WHATSAPP
    template first; falls back to the hardcoded default (this module's
    own pre-S-014 behavior) if no single active template exists yet, or
    if it renders with something still un-replaced. A tenant that's
    never touched /templates gets exactly the old behavior.
    """
    from app.services.message_template_service import TemplateNotFoundError, TemplateRenderError, render_template

    variables = {"candidate_name": _first_name(candidate), "agent_name": agent_name, "company_name": COMPANY_NAME}
    try:
        result = render_template(db, "GREETING_WHATSAPP", "WHATSAPP", tenant_id, variables)
        return result["rendered_body"]
    except (TemplateNotFoundError, TemplateRenderError) as exc:
        logger.info(f"[FirstEngagement] Using hardcoded GREETING_WHATSAPP fallback ({exc.__class__.__name__}): {exc}")

    rendered = FALLBACK_GREETING_TEMPLATE.format(
        candidate_name=_first_name(candidate), agent_name=agent_name, company_name=COMPANY_NAME,
    )
    # BR-02: zero tolerance for an un-replaced {{...}}/{...} placeholder
    # reaching a candidate -- str.format() already raises KeyError on a
    # genuinely missing field (caught by the caller), this is the
    # belt-and-suspenders scan for anything that slips through.
    if "{" in rendered and "}" in rendered:
        raise TemplateRenderFailure(f"Un-replaced template variable in rendered greeting: {rendered!r}")
    return rendered

logger = logging.getLogger(__name__)

class TemplateRenderFailure(Exception):
    pass

class FirstEngagementFailed(Exception):
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)

def _already_sent(db: Session, conversation_id: int) -> bool:
    """BR-03: idempotent -- one first message only."""
    return (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "FIRST_WHATSAPP_SENT")
        .first()
        is not None
    )

def _send_first_whatsapp_attempt(
    db: Session, conversation: CandidateConversation, candidate: Candidate, body: str, whatsapp_client,
) -> bool:
    """
    One raw send attempt -- calls the WhatsApp transport directly
    (bypassing send_thunder_message()'s 60-second duplicate-body
    debounce) rather than through the standard wrapper. That debounce
    exists to stop two independent trigger events from double-sending
    the same text; BR-04's mandated retry is the opposite case --a
    SINGLE logical send operation reattempting the identical body
    within seconds on purpose. R-08 ownership and consent are still
    checked explicitly here, just not through the wrapper that would
    also reject the second attempt as a "duplicate."
    """
    if not is_ai_owner(conversation):
        raise ConversationOwnedByHuman(f"Conversation {conversation.id} is owned by a human -- Thunder may not send.")
    if not has_active_consent(db, candidate.candidateID):
        raise ConsentNotGiven(f"Candidate {candidate.candidateID} has no active whatsapp_outreach consent.")

    from_number = resolve_outbound_whatsapp_number(db, conversation)
    if not from_number:
        raise NoWhatsAppNumberAvailable("No WhatsApp number available to send from.")

    from app.services.whatsapp_routing_service import _send_whatsapp_unconfigured
    client = whatsapp_client or _send_whatsapp_unconfigured
    try:
        delivered = bool(client(candidate.candidateMobile, from_number, body))
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FirstEngagement] WhatsApp send attempt raised: {exc}")
        delivered = False

    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="ai_message_sent",
        event_data={"channel": "whatsapp", "from_number": from_number, "to_number": candidate.candidateMobile, "body": body, "delivered": delivered, "auto_generated": True},
        triggered_by="ai_agent",
    )
    db.add(event)
    return delivered

def send_first_whatsapp_engagement(
    db: Session, candidate_id: str, tenant_id: str, *, whatsapp_client=None, _sleep=time.sleep,
) -> Dict:
    """
    S-012/HRMS-0412's WhatsAppFirstEngagementService, adapted to run as
    a direct function call from the real candidate-creation flow
    (auto_assign_ai_agent_on_creation) rather than a separate message-
    queue listener -- this codebase has no message queue; the real
    CONVERSATION_INITIATED-equivalent moment already exists as the
    synchronous point right after assign_ai_agent() creates the
    conversation, so this hooks there instead of inventing new queue
    infrastructure the spec's "listens for an event on the internal
    message queue" framing assumes.

    _sleep is injectable so tests don't sleep 5 real seconds on retry.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise FirstEngagementFailed("CANDIDATE_NOT_FOUND", candidate_id)

    if not candidate.candidateMobile:
        logger.info(f"[FirstEngagement] WHATSAPP_SKIPPED_NO_PHONE for candidate {candidate_id}")
        return {"status": "skipped", "reason": "NO_PHONE", "candidate_id": candidate_id}

    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id, CandidateConversation.tenant_id == tenant_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if not conversation:
        raise FirstEngagementFailed("NO_CONVERSATION", candidate_id)

    if _already_sent(db, conversation.id):
        logger.info(f"[FirstEngagement] DUPLICATE_PREVENTED for candidate {candidate_id}, conversation {conversation.id}")
        return {"status": "duplicate_prevented", "candidate_id": candidate_id, "conversation_id": conversation.id}

    thunder_config = resolve_thunder_config(db, tenant_id)

    try:
        body = _render_greeting(db, candidate, thunder_config["name"], tenant_id)
    except TemplateRenderFailure as exc:
        logger.error(f"[FirstEngagement] TEMPLATE_RENDER_FAILURE: {exc}")
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="FIRST_ENGAGEMENT_FAILED", event_data={"reason": "TEMPLATE_RENDER_FAILURE", "detail": str(exc)}, triggered_by="system"))
        db.commit()
        raise FirstEngagementFailed("TEMPLATE_RENDER_FAILURE", str(exc))

    if len(body) > MAX_MESSAGE_LENGTH:
        raise FirstEngagementFailed("MESSAGE_TOO_LONG", f"{len(body)} chars")

    # BR-04: at most two attempts total, one retry after 5s.
    delivered = False
    try:
        delivered = _send_first_whatsapp_attempt(db, conversation, candidate, body, whatsapp_client)
        if not delivered:
            _sleep(RETRY_DELAY_SECONDS)
            delivered = _send_first_whatsapp_attempt(db, conversation, candidate, body, whatsapp_client)
    except (ConversationOwnedByHuman, ConsentNotGiven, NoWhatsAppNumberAvailable) as exc:
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="FIRST_ENGAGEMENT_FAILED", event_data={"reason": "SEND_BLOCKED", "detail": str(exc)}, triggered_by="system"))
        db.commit()
        raise FirstEngagementFailed("SEND_BLOCKED", str(exc))

    if not delivered:
        logger.warning(f"[FirstEngagement] FIRST_WHATSAPP_FAILED for candidate {candidate_id} after 2 attempts")
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="FIRST_WHATSAPP_FAILED", event_data={"reason": "API_FAILURE", "candidate_id": candidate_id}, triggered_by="system"))
        db.commit()
        return {"status": "failed", "reason": "API_FAILURE", "candidate_id": candidate_id, "conversation_id": conversation.id}

    # BR-01: SLA measured from candidate.created_at to the moment the
    # WhatsApp API call succeeded (now).
    now = datetime.utcnow()
    created_at = candidate.candidateCreatedAt or now
    elapsed_seconds = max((now - created_at).total_seconds(), 0)
    sla_seconds = SLA_SECONDS
    try:
        from app.services.tenant_ai_config_service import get_sla_first_contact_seconds
        sla_seconds = get_sla_first_contact_seconds(db, tenant_id)
    except Exception:
        pass
    sla_event_type = "SLA_MET" if elapsed_seconds <= sla_seconds else "SLA_BREACH"
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type=sla_event_type,
        event_data={"candidate_id": candidate_id, "elapsed_seconds": elapsed_seconds, "breach_type": "FIRST_WHATSAPP" if sla_event_type == "SLA_BREACH" else None},
        triggered_by="system",
    ))
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="FIRST_WHATSAPP_SENT",
        event_data={"candidate_id": candidate_id, "conversation_id": conversation.id, "sent_at": now.isoformat()},
        triggered_by="system",
    ))
    conversation.updated_at = now
    db.add(conversation)
    db.commit()

    logger.info(f"[FirstEngagement] Sent first WhatsApp message to candidate {candidate_id} in {elapsed_seconds:.1f}s ({sla_event_type})")
    return {
        "status": "sent", "candidate_id": candidate_id, "conversation_id": conversation.id,
        "elapsed_seconds": elapsed_seconds, "sla_met": sla_event_type == "SLA_MET",
    }
