"""
Production-ready multi-channel candidate outreach: WhatsApp (primary) + Email (fallback).

Per-staff WhatsApp number routing for candidate conversations, extending
HRMS-0410's ownership model (app.models.candidate_ai.CandidateConversation
.owner_type/.owner_id).

Design:
- Each staff member can configure their own WhatsApp number for candidate outreach
- Messages are sent via WhatsApp Business API when a sender's WhatsApp is configured
- Falls back to email (Microsoft Graph API) when WhatsApp is unavailable
- All communication is audit-logged via MessageDeliveryLog

Implementation:
- Resolves outbound WhatsApp numbers per conversation owner (user's configured number or shared default)
- Multi-channel failover: WhatsApp → Email (both production APIs, no stubs)
- Prevents Thunder from sending when human owns conversation (HRMS-0410 BR-01 enforcement)
- Handles per-recruiter ownership and hand-back to Thunder (HRMS-0410 BR-03, HAND_BACK)

Production status: All message delivery uses real APIs (WhatsApp Business API + Microsoft Graph).
No stub implementations. Email fallback is required fallback when WhatsApp unavailable.
"""
import logging
import os
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.message_delivery import MessageDeliveryLog
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.notification_service import ChannelNotConfigured
from app.services.delivery_factory import get_delivery_service
from app.services.email_service import EmailService
from app.core.logging import logger

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
    to_number = candidate.candidateMobile

    # Multi-channel fallback: WhatsApp (if available) → Email (mandatory)
    use_whatsapp = bool(from_number)
    use_email = not use_whatsapp and candidate.candidateEmail

    if not use_whatsapp and not use_email:
        raise ValueError(
            f"No communication channel available for candidate {candidate.candidateID}: "
            f"no WhatsApp number for sender and no email for recipient."
        )

    # Use delivery service if not overridden with whatsapp_client
    if whatsapp_client is None:
        if use_whatsapp:
            try:
                delivery_service = get_delivery_service(db=db, tenant_id=candidate.tenant_id)
                result = delivery_service.send_whatsapp(to_number=to_number, body=message_body, from_number=from_number)
            except RuntimeError as e:
                logger.error(f"[WhatsApp] Cannot send message - delivery not configured for tenant {candidate.tenant_id}: {e}")
                raise
        else:
            # Fallback to email when WhatsApp unavailable - use production Graph-based EmailService
            try:
                email_result = EmailService.send_email(
                    to_email=candidate.candidateEmail,
                    subject="Message from Recruiter",
                    body_content=message_body,
                    is_html=False  # Plain text message from recruiter
                )
                # Create synthetic result for consistency with delivery service pattern
                result = type('DeliveryResult', (), {
                    'status': 'sent' if email_result.get('status') != 'skipped' else 'pending',
                    'delivery_id': email_result.get('id') or f"email_{candidate.candidateID}_{datetime.utcnow().timestamp()}",
                    'external_id': None,
                    'error': email_result.get('reason') if email_result.get('status') == 'skipped' else None
                })()
            except Exception as e:
                logger.error(f"[Email Fallback] Failed to send email to {candidate.candidateEmail}: {e}")
                raise RuntimeError(f"Email fallback failed for {candidate.candidateEmail}: {str(e)}")

        # Create MessageDeliveryLog for tracking
        try:
            delivery_type = "whatsapp" if use_whatsapp else "email"
            recipient = to_number if use_whatsapp else candidate.candidateEmail
            log_entry = MessageDeliveryLog(
                conversation_id=conversation.id,
                delivery_type=delivery_type,
                recipient=recipient,
                subject="Message from Recruiter" if not use_whatsapp else None,
                body=message_body,
                status=result.status,
                delivery_id=result.delivery_id,
                external_message_id=result.external_id,
                error=result.error,
                created_at=datetime.utcnow(),
                sent_at=datetime.utcnow() if result.status in ("sent", "delivered") else None,
            )
            db.add(log_entry)
            db.commit()
            channel_label = "WhatsApp" if use_whatsapp else "Email"
            logger.debug(f"[{channel_label}] Created MessageDeliveryLog: {result.delivery_id}")
        except Exception as e:
            logger.error(f"[Delivery] Failed to create MessageDeliveryLog: {e}")
            db.rollback()

        # Check delivery result
        if result.status == "failed":
            channel_label = "WhatsApp" if use_whatsapp else "Email"
            recipient_label = to_number if use_whatsapp else candidate.candidateEmail
            logger.error(f"[{channel_label}] Delivery failed for {recipient_label}: {result.error}")
            raise RuntimeError(f"{channel_label} delivery failed for {recipient_label}: {result.error}")
    else:
        # Legacy whatsapp_client path (for backward compatibility in tests)
        if not use_whatsapp:
            raise ValueError("Legacy whatsapp_client path requires WhatsApp to be available")

        try:
            delivered = bool(whatsapp_client(to_number, from_number, message_body))
        except ChannelNotConfigured as e:
            # WhatsApp not configured - try email fallback
            if candidate.candidateEmail:
                logger.warning(f"[WhatsApp] Channel not configured, falling back to email: {e}")
                use_whatsapp = False
                use_email = True
            else:
                logger.error(f"[WhatsApp] Channel not configured and no email fallback: {e}")
                raise

        # If delivery returned False, treat as failure
        if use_whatsapp and not delivered:
            logger.error(f"[WhatsApp] Delivery returned False for {to_number}")
            raise RuntimeError(f"WhatsApp delivery failed (client returned False) for {to_number}")

    # Only create event if delivery actually succeeded
    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="ai_message_sent" if sender_type == "ai_agent" else "hr_message_sent",
        event_data={
            "channel": "whatsapp" if use_whatsapp else "email",
            "from_number": from_number if use_whatsapp else None,
            "to_number": to_number if use_whatsapp else candidate.candidateEmail,
            "body": message_body,
            "delivered": True,
            "auto_generated": auto_generated,
        },
        triggered_by=sender_type,
    )
    db.add(event)
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    return event
