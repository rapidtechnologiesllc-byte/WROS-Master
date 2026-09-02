"""
Per-staff WhatsApp number routing for candidate conversations, extending
HRMS-0410's ownership model (app.models.candidate_ai.CandidateConversation
import logging
.owner_type/.owner_id).

Background: the 357 requirements docs describe a SINGLE shared tenant-
level WhatsApp Business number for all candidate conversations (Thunder
and every recruiter send through the same number; "who's talking" is
carried only as owner_type/owner_id/triggered_by metadata). Avinash
wants something different: each staff member coordinates through their
OWN WhatsApp number, all still unifying back to one thread via
CandidateConversation.candidate_id/.id (this codebase's Candidate table
uses its own legacy string ID scheme, not a UUID -- see app.models.
candidate.Candidate -- so "mapped to UUID" is satisfied by that existing
candidate_id/conversation_id pairing, not a literal UUID column). This
is a genuinely new capability, not built against any existing story.

Scope, per Avinash's explicit choice: build the real, tested routing/
ownership logic; the actual outbound WhatsApp send is an injectable
stub (ChannelNotConfigured by default) since no WhatsApp Business API
credentials exist in this codebase -- same posture as
app.services.notification_service's WhatsApp channel. Do not conflate
the two: notification_service is for internal staff alerts (HRMS-0113);
this module is for candidate-facing Thunder/recruiter conversations
(HRMS-0401/0409/0410).

Also fixes a real, pre-existing gap found while building this: HRMS-0410
BR-01 ("Thunder must never send when a recruiter owns the conversation")
was never actually enforced anywhere in app.services.ai_conversation_
service.py -- there was no isAIOwner()-style gate, because no human
manual-send path existed yet to conflict with the AI's sends. is_ai_owner()
and the gate in send_whatsapp_message() below are that enforcement,
built for real now that a competing send path (per-recruiter WhatsApp)
exists.
"""
import os
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.notification_service import ChannelNotConfigured

# The shared/Thunder number -- used when the AI owns the conversation, or
# as a fallback for a human owner with no personal number registered.
# Env-configurable rather than a DB column since this codebase's
# candidate_ai.py tenant_id is actually users.UserID (the org owner), not
# the real multi-tenant `tenants` table used elsewhere in this session --
# adding a per-"tenant" column there would compound that pre-existing
# inconsistency rather than fix it.
DEFAULT_WHATSAPP_NUMBER = os.getenv("THUNDER_WHATSAPP_NUMBER")

logger = logging.getLogger(__name__)

class ConversationOwnedByHuman(Exception):
    """HRMS-0410 BR-01 / R-08: Thunder may not send while a recruiter/HR
    user owns the conversation."""


class NoWhatsAppNumberAvailable(Exception):
    pass


def _send_whatsapp_unconfigured(to_number: str, from_number: str, body: str) -> bool:
    raise ChannelNotConfigured("WhatsApp Business API is not provisioned in this codebase yet.")


def is_ai_owner(conversation: CandidateConversation) -> bool:
    """HRMS-0410's isAIOwner() -- the gate that was specified but never
    actually implemented anywhere in this codebase before this module."""
    return conversation.owner_type == "ai_agent"


def resolve_outbound_whatsapp_number(db: Session, conversation: CandidateConversation) -> Optional[str]:
    """
    HRMS-0410's owner_id points at either AI_AGENT_NAME (a constant
    string) or a users.UserID (when owner_type='hr_user'). Resolve the
    number that should send the NEXT outbound message for this
    conversation: the owning staff member's own number if they have one
    registered, else the shared fallback.
    """
    if conversation.owner_type == "hr_user" and conversation.owner_id:
        owner = db.query(Users).filter(Users.UserID == conversation.owner_id).first()
        if owner and owner.whatsapp_number:
            return owner.whatsapp_number

    return DEFAULT_WHATSAPP_NUMBER


def take_over_conversation(db: Session, conversation: CandidateConversation, hr_user_id: str) -> CandidateConversation:
    """HRMS-0410 BR-03: any recruiter/HR user can take over from anyone
    else (or from AI), no permission check, no lock."""
    conversation.owner_type = "hr_user"
    conversation.owner_id = hr_user_id
    db.add(conversation)
    return conversation


def hand_back_conversation(db: Session, conversation: CandidateConversation) -> CandidateConversation:
    """HRMS-0410 HAND_BACK: returns the conversation to Thunder."""
    conversation.owner_type = "ai_agent"
    conversation.owner_id = AI_AGENT_NAME
    db.add(conversation)
    return conversation


def send_whatsapp_message(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    message_body: str,
    *,
    sender_type: str,
    sender_id: Optional[str] = None,
    whatsapp_client: Optional[Callable[[str, str, str], bool]] = None,
    auto_generated: bool = False,
) -> ConversationEvent:
    """
    The one sanctioned send path for candidate-facing WhatsApp messages,
    covering both HRMS-0410's ownership gate (for AI sends) and
    HRMS-0409's auto-transfer-on-manual-send rule (for human sends).

    sender_type: 'ai_agent' or 'hr_user'. sender_id required for 'hr_user'.

    auto_generated: set by app.services.conversation_inactivity_service
    when this send is a system-triggered nudge attributed to a recruiter
    (sender_type='hr_user') rather than something they actually typed --
    the event is still recorded with sender_type='hr_user' (it goes out
    under their number, as their message, per Avinash's explicit call),
    but this flag keeps R-06/HRMS-P612's human-dependency tracking honest
    about which sends were genuinely manual versus automated on a
    recruiter's behalf.
    """
    if sender_type == "ai_agent":
        if not is_ai_owner(conversation):
            raise ConversationOwnedByHuman(
                f"Conversation {conversation.id} is owned by {conversation.owner_type}:"
                f"{conversation.owner_id} -- Thunder may not send."
            )
    elif sender_type == "hr_user":
        if not sender_id:
            raise ValueError("sender_id is required when sender_type='hr_user'.")
        # HRMS-0409 BR-01: every manual send transfers ownership, unconditionally.
        take_over_conversation(db, conversation, sender_id)
    else:
        raise ValueError(f"sender_type must be 'ai_agent' or 'hr_user', got '{sender_type}'.")

    from_number = resolve_outbound_whatsapp_number(db, conversation)
    if not from_number:
        raise NoWhatsAppNumberAvailable(
            f"No WhatsApp number available to send from for conversation {conversation.id} "
            f"(owner has none registered and no fallback number is configured)."
        )

    to_number = candidate.candidateMobile
    client = whatsapp_client or _send_whatsapp_unconfigured

    try:
        delivered = bool(client(to_number, from_number, message_body))
    except ChannelNotConfigured:
        delivered = False

    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="ai_message_sent" if sender_type == "ai_agent" else "hr_message_sent",
        event_data={
            "channel": "whatsapp",
            "from_number": from_number,
            "to_number": to_number,
            "body": message_body,
            "delivered": delivered,
            "auto_generated": auto_generated,
        },
        triggered_by=sender_type,
    )
    db.add(event)
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    return event
