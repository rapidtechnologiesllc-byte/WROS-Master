"""
AI Email Conversation Agent — API Endpoints
============================================
Prefix: /ai-agent
Tag:    ai-agent

Routes:
  POST   /ai-agent/assign
      Assign AI agent to a candidate. Checks missing fields, sends email,
      opens a conversation thread.

  GET    /ai-agent/missing-fields/{candidate_id}
      Dry-run: preview which fields are missing for a candidate.

  POST   /ai-agent/webhook/email-reply
      Process an incoming candidate reply (webhook mode).
      Supply raw_reply_text directly OR leave blank to trigger a live
      inbox poll against the Graph API.

  POST   /ai-agent/poll/{candidate_id}
      Convenience endpoint: polls the Graph inbox for new replies from
      the candidate and runs the full processing pipeline.

  GET    /ai-agent/conversations/{candidate_id}
      Return the full conversation thread (all conversations + events)
      for a candidate — used by the HR UI to display the dialogue timeline.

  GET    /ai-agent/conversations/{candidate_id}/active
      Return only the single active (open / awaiting) conversation + events.

  POST   /ai-agent/conversations/{conversation_id}/send
      Manually send a message to the candidate; transfers ownership to
      the sending HR user (S-009).

  POST   /ai-agent/conversations/{conversation_id}/take-over
      Take over a conversation from the AI agent or another HR user (S-010).

  POST   /ai-agent/conversations/{conversation_id}/hand-back
      Hand a conversation back to the AI agent (S-010).

  POST   /ai-agent/conversations/{conversation_id}/thunder-pause
      Pause Thunder for this candidate, optionally until a given time (S-075).

  POST   /ai-agent/conversations/{conversation_id}/thunder-resume
      Resume Thunder for this candidate immediately (S-075).

  GET    /ai-agent/assignments/{candidate_id}
      Return all AI agent assignments for a candidate.

  DELETE /ai-agent/assign/{candidate_id}
      Deactivate the AI agent assignment for a candidate.

  GET    /ai-agent/candidates/{candidate_id}/audit-log
      Compliance-grade audit trail of conversation actions (S-076).

  GET    /ai-agent/messages/{event_id}/explanation
      Why Thunder sent this specific message (S-064). 404 if the
      message has no explanation (recruiter-sent or templated).

  GET    /ai-agent/candidates/{candidate_id}/thunder-explanation-log
      Full, immutable history of every explained Thunder decision (S-064).
"""
from datetime import datetime as _datetime

from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission, require_resource_permission
from app.core.webhook_auth import require_webhook_secret_or_internal_user
from app.models.candidate import Candidate
from app.models.candidate_ai import (
    CandidateAIAssignment,
    CandidateConversation,
    ConversationEvent,
)
from app.models.conversation_audit_log import ConversationAuditLog
from app.models.user import Users
from app.schemas.candidate_memory import CandidateMemoryResponse, MemoryFactCorrectionRequest, MemoryFactItem
from app.schemas.ai_agent import (
    AIAgentAssignRequest,
    AIAgentAssignResponse,
    AIAssignmentOut,
    AuditLogEntryOut,
    AuditLogResponse,
    ConversationOwnershipResponse,
    ConversationThreadResponse,
    ConversationThreadItem,
    ConversationEventOut,
    EmailReplyWebhookRequest,
    MissingFieldItem,
    MissingFieldsResponse,
    ProcessReplyResponse,
    InboxMessageItem,
    InboxResponse,
    PauseThunderRequest,
    SendMessageRequest,
    SendMessageResponse,
    ThunderPauseResponse,
)
from app.services.ai_conversation_service import (
    assign_ai_agent,
    get_conversation_thread,
    get_missing_fields,
    process_candidate_reply,
    read_all_inbox,
    read_inbox_by_email,
    resolve_default_tenant_id,
    SERVICE_MAILBOX,
)
from app.services.audit_log_service import log_audit_event
from app.services.thunder_pause_service import pause_thunder, resume_thunder
from app.services.whatsapp_routing_service import (
    hand_back_conversation,
    NoWhatsAppNumberAvailable,
    send_whatsapp_message,
    take_over_conversation,
)

router = APIRouter(prefix="/ai-agent", tags=["ai-agent"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_candidate_or_404(candidate_id: str, db: Session) -> Candidate:
    try:
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()
    except Exception as e:
        logger.error(f"[GetCandidate] Database query failed for {candidate_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error retrieving candidate")

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return candidate

def _get_conversation_or_404(conversation_id: int, db: Session) -> CandidateConversation:
    try:
        conversation = db.query(CandidateConversation).filter(
            CandidateConversation.id == conversation_id
        ).first()
    except Exception as e:
        logger.error(f"[GetConversation] Database query failed for conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error retrieving conversation")

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return conversation

# ===========================================================================
# POST /ai-agent/assign
# ===========================================================================


# ===========================================================================
# GET /ai-agent/missing-fields/{candidate_id}
# ===========================================================================

@router.get(
    "/missing-fields/{candidate_id}",
    response_model=MissingFieldsResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Preview missing fields for a candidate (dry-run, no email sent)",
    description=(
        "Returns a list of all profile fields that are currently empty for "
        "the given candidate. This is a read-only check — no email is sent "
        "and no conversation is created."
    ),
)
def preview_missing_fields(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    candidate = _get_candidate_or_404(candidate_id, db)
    missing = get_missing_fields(candidate, db)
    return MissingFieldsResponse(
        candidate_id=candidate_id,
        total_missing=len(missing),
        missing_fields=[MissingFieldItem(**m) for m in missing],
    )

# ===========================================================================
# GET /ai-agent/portal-link/{candidate_id}
# ===========================================================================


# ===========================================================================
# GET /ai-agent/memory/{candidate_id}
# ===========================================================================

@router.get(
    "/memory/{candidate_id}",
    response_model=CandidateMemoryResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Candidate Memory Viewer (S-021/HRMS-0421)",
    description=(
        "Returns Thunder's rolling summary and categorized facts for this "
        "candidate (salary, preferences, constraints, motivators, etc.). "
        "Routed here rather than under /candidates/{id}/memory, matching "
        "this round's convention of hosting every Thunder-intelligence "
        "candidate-scoped read (missing-fields, portal-link) under /ai-agent."
    ),
)
def get_candidate_memory(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.ai_conversation_service import resolve_default_tenant_id
    from app.services.candidate_memory_service import get_memory
    from app.models.candidate_ai import CandidateConversation

    try:
        _get_candidate_or_404(candidate_id, db)
        tenant_id = resolve_default_tenant_id()

        try:
            memory = get_memory(db, candidate_id, tenant_id)
        except Exception as e:
            logger.error(f"[CandidateMemory] Failed to fetch memory for {candidate_id}: {e}", exc_info=True)
            memory = {"summary": None, "facts": [], "signals": []}

        # Fetch Thunder engagement data with error handling
        thunder_data = {
            "last_contact_at": None,
            "next_contact_at": None,
            "is_thunder_paused": False,
            "message_count": 0,
            "conversation_id": None,
        }

        try:
            conversation = db.query(CandidateConversation).filter(
                CandidateConversation.candidate_id == candidate_id,
                CandidateConversation.tenant_id == tenant_id
            ).order_by(CandidateConversation.created_at.desc()).first()

            if conversation:
                thunder_data["last_contact_at"] = conversation.last_touch_scheduled_at
                thunder_data["next_contact_at"] = conversation.next_touch_scheduled_at
                thunder_data["is_thunder_paused"] = conversation.is_thunder_paused or False
                thunder_data["message_count"] = len(conversation.events) if hasattr(conversation, 'events') else 0
                thunder_data["conversation_id"] = str(conversation.id)
        except Exception as e:
            logger.error(f"[CandidateMemory] Thunder engagement fetch failed: {e}", exc_info=True)

        return CandidateMemoryResponse(candidate_id=candidate_id, last_updated=memory.get("last_updated"), summary=memory.get("summary"), facts=memory.get("facts", []), signals=memory.get("signals", []), **thunder_data)
    except Exception as e:
        logger.error(f"[CandidateMemory] Endpoint error for {candidate_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memory: {str(e)}")

# ===========================================================================
# PATCH /ai-agent/memory/{candidate_id}/facts/{fact_id}
# ===========================================================================

@router.patch(
    "/memory/{candidate_id}/facts/{fact_id}",
    response_model=MemoryFactItem,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Correct a Thunder memory fact (S-023/HRMS-0423)",
    description=(
        "A recruiter's manual correction is treated as verified ground "
        "truth: confidence is always set to 1.0 (BR-01). If the fact_key "
        "maps to a real candidate profile column, the correction also "
        "updates the candidates table (BR-03)."
    ),
)
def correct_candidate_memory_fact(
    candidate_id: str,
    fact_id: int,
    body: MemoryFactCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.candidate_memory_service import FactNotFound, correct_fact

    _get_candidate_or_404(candidate_id, db)
    tenant_id = resolve_default_tenant_id()
    try:
        fact = correct_fact(db, candidate_id, tenant_id, fact_id, body.fact_value, corrected_by=current_user.UserID)
    except FactNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MemoryFactItem(
        id=fact.id, category=fact.fact_category, key=fact.fact_key, value=fact.fact_value,
        confidence=fact.confidence, is_low_confidence=fact.confidence < 0.7, extracted_at=fact.extracted_at,
    )

# ===========================================================================
# GET /ai-agent/skill-suggestions
# ===========================================================================


# ===========================================================================
# GET /ai-agent/resume-completeness/{candidate_id}
# ===========================================================================


# ===========================================================================
# GET /ai-agent/prompt-templates
# ===========================================================================


# ===========================================================================
# POST /ai-agent/webhook/email-reply
# ===========================================================================

@router.post(
    "/webhook/email-reply",
    response_model=ProcessReplyResponse,
    summary="Process an incoming candidate reply email",
    dependencies=[
        Depends(require_webhook_secret_or_internal_user),
        Depends(require_resource_permission("candidates", "edit"))
    ],
    description=(
        "Accepts a candidate reply (either raw text passed directly, or triggers "
        "a live Graph inbox poll if `raw_reply_text` is omitted). "
        "Gemini extracts field values from the reply, merges them into the candidate "
        "record, and sends a follow-up email if fields are still missing.\n\n"
        "This endpoint can be called:\n"
        "- By a scheduler polling the Graph inbox periodically, sending the shared "
        "secret in an X-Webhook-Secret header (WEBHOOK_SHARED_SECRET in .env).\n"
        "- By an external webhook when a new email arrives, same header.\n"
        "- Directly from the HR portal for manual testing, using a normal internal "
        "user's bearer token instead.\n\n"
        "Requires EITHER a valid X-Webhook-Secret header OR a valid internal-user "
        "bearer token -- see app.core.webhook_auth.require_webhook_secret_or_internal_user."
    ),
)
def webhook_email_reply(
    body: EmailReplyWebhookRequest,
    db: Session = Depends(get_db),
):
    try:
        result = process_candidate_reply(
            candidate_id=body.candidate_id,
            db=db,
            raw_reply_text=body.raw_reply_text,
            message_id=body.message_id,
        )
    except Exception as e:
        logger.error(f"[WebhookEmailReply] Failed to process candidate reply: {e}", exc_info=True)
        raise

    if not result:
        logger.error(f"[WebhookEmailReply] process_candidate_reply returned None for candidate {body.candidate_id}")
        raise HTTPException(status_code=500, detail="Failed to process reply")

    return ProcessReplyResponse(**result)

# ===========================================================================
# POST /ai-agent/poll/{candidate_id}
# ===========================================================================

@router.post(
    "/poll/{candidate_id}",
    response_model=ProcessReplyResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Manually poll Graph inbox and process reply for a candidate",
    description=(
        "Polls the service mailbox (`helpdesk_hrms@blitzenx.com`) for new reply "
        "emails from the candidate, then runs the full AI processing pipeline: "
        "parse with Gemini → merge into DB → send follow-up if needed.\n\n"
        "Useful for testing, manual HR-triggered processing, or scheduler integration."
    ),
)
def poll_and_process(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    try:
        result = process_candidate_reply(
            candidate_id=candidate_id,
            db=db,
            raw_reply_text=None,    # triggers live Graph inbox poll
            message_id=None,
        )
    except Exception as e:
        logger.error(f"[PollAndProcess] Failed to process candidate reply: {e}", exc_info=True)
        raise

    if not result:
        logger.error(f"[PollAndProcess] process_candidate_reply returned None for candidate {candidate_id}")
        raise HTTPException(status_code=500, detail="Failed to process reply")

    return ProcessReplyResponse(**result)

# ===========================================================================
# GET /ai-agent/conversations/{candidate_id}
# ===========================================================================

@router.get(
    "/conversations/{candidate_id}",
    response_model=ConversationThreadResponse,
    summary="Get full agent–candidate conversation thread",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    description=(
        "Returns **all conversations** for a candidate, each containing the full "
        "chronological event log. This is the primary endpoint for the HR UI to "
        "render the dialogue timeline between the AI agent and the candidate.\n\n"
        "Events include:\n"
        "- `ai_assigned` — agent was assigned\n"
        "- `field_check` — agent detected missing fields\n"
        "- `ai_message_sent` — agent sent an email\n"
        "- `candidate_reply` — candidate replied\n"
        "- `gemini_parse` — Gemini extracted field values\n"
        "- `fields_merged` — extracted values written to DB\n"
        "- `status_changed` — conversation status changed\n"
    ),
)
def get_conversations(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_candidate_or_404(candidate_id, db)
    thread = get_conversation_thread(candidate_id, db)

    return ConversationThreadResponse(
        candidate_id=candidate_id,
        total_conversations=len(thread),
        conversations=[ConversationThreadItem(**c) for c in thread],
    )

# ===========================================================================
# GET /ai-agent/conversations/{candidate_id}/active
# ===========================================================================


# ===========================================================================
# POST /ai-agent/conversations/{conversation_id}/send
# ===========================================================================

@router.post(
    "/conversations/{conversation_id}/send",
    response_model=SendMessageResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Manually send a message to the candidate on this conversation (S-009)",
    description=(
        "Sends a WhatsApp message from the current HR user to the candidate. "
        "Per HRMS-0409 BR-01, this unconditionally transfers ownership of the "
        "conversation to the sending HR user — Thunder will not send again "
        "until the conversation is handed back."
    ),
)
def send_hr_message(
    conversation_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    conversation = _get_conversation_or_404(conversation_id, db)
    candidate = _get_candidate_or_404(conversation.candidate_id, db)

    try:
        event = send_whatsapp_message(
            db,
            conversation,
            candidate,
            body.message,
            sender_type="hr_user",
            sender_id=current_user.UserID,
        )
    except NoWhatsAppNumberAvailable as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        logger.error(f"[SendHRMessage] Failed to send WhatsApp message: {e}", exc_info=True)
        raise

    if not event:
        logger.error(f"[SendHRMessage] send_whatsapp_message returned None for conversation {conversation_id}")
        raise HTTPException(status_code=500, detail="Failed to send message")

    log_audit_event(
        db,
        tenant_id=conversation.tenant_id,
        candidate_id=conversation.candidate_id,
        conversation_id=conversation.id,
        audit_event_type="MANUAL_MESSAGE_SENT",
        description=f"HR user {current_user.UserID} manually sent a message on conversation {conversation.id}.",
        actor_type="HR",
        actor_id=current_user.UserID,
        after_state={"channel": "whatsapp", "body": body.message},
    )

    try:
        db.commit()
        db.refresh(event)
        db.refresh(conversation)
    except Exception as e:
        logger.error(f"[ManualMessage] Failed to commit message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save message")

    return SendMessageResponse(
        conversation_id=conversation.id,
        event_id=event.id,
        delivered=bool(event.event_data.get("delivered")) if event.event_data else False,
        owner_type=conversation.owner_type,
        owner_id=conversation.owner_id,
    )

# ===========================================================================
# POST /ai-agent/conversations/{conversation_id}/take-over
# ===========================================================================

@router.post(
    "/conversations/{conversation_id}/take-over",
    response_model=ConversationOwnershipResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Take over a conversation from the AI agent or another HR user (S-010)",
    description=(
        "HRMS-0410 BR-03: any HR user can take over a conversation from "
        "anyone else (or from the AI), no permission check beyond "
        "candidate.edit, no lock."
    ),
)
def take_over(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    conversation = _get_conversation_or_404(conversation_id, db)
    before_state = {"owner_type": conversation.owner_type, "owner_id": conversation.owner_id}
    take_over_conversation(db, conversation, current_user.UserID)

    # Create ownership change event - check if recent duplicate exists
    from datetime import datetime, timedelta
    try:
        recent_ownership_event = db.query(ConversationEvent).filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type == "ownership_changed",
            ConversationEvent.created_at >= datetime.utcnow() - timedelta(seconds=5)
        ).first()

        if not recent_ownership_event:
            ownership_event = ConversationEvent(
                conversation_id=conversation.id,
                event_type="ownership_changed",
                event_data={"new_owner_type": "hr_user", "new_owner_id": current_user.UserID},
                triggered_by="hr_user",
            )
            db.add(ownership_event)
    except Exception as e:
        logger.error(f"[TakeOverConversation] Failed to create ownership event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record ownership change")
    log_audit_event(
        db,
        tenant_id=conversation.tenant_id,
        candidate_id=conversation.candidate_id,
        conversation_id=conversation.id,
        audit_event_type="OWNERSHIP_CHANGED",
        description=f"HR user {current_user.UserID} took over conversation {conversation.id}.",
        actor_type="HR",
        actor_id=current_user.UserID,
        before_state=before_state,
        after_state={"owner_type": "hr_user", "owner_id": current_user.UserID},
    )
    try:
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        logger.error(f"[TakeOverConversation] Failed to commit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to take over conversation")
    return ConversationOwnershipResponse(
        conversation_id=conversation.id,
        owner_type=conversation.owner_type,
        owner_id=conversation.owner_id,
    )

# ===========================================================================
# POST /ai-agent/conversations/{conversation_id}/hand-back
# ===========================================================================

@router.post(
    "/conversations/{conversation_id}/hand-back",
    response_model=ConversationOwnershipResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Hand a conversation back to the AI agent (S-010)",
    description="HRMS-0410 HAND_BACK: returns the conversation to Thunder.",
)
def hand_back(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    conversation = _get_conversation_or_404(conversation_id, db)
    before_state = {"owner_type": conversation.owner_type, "owner_id": conversation.owner_id}
    hand_back_conversation(db, conversation)

    # Create ownership change event - check if recent duplicate exists
    from datetime import datetime, timedelta
    try:
        recent_event = db.query(ConversationEvent).filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type == "ownership_changed",
            ConversationEvent.created_at >= datetime.utcnow() - timedelta(seconds=5)
        ).first()
    except Exception as e:
        logger.error(f"[HandBackConversation] Failed to query recent ownership event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error checking for duplicate event")

    if not recent_event:
        try:
            db.add(
                ConversationEvent(
                    conversation_id=conversation.id,
                    event_type="ownership_changed",
                    event_data={"new_owner_type": "ai_agent", "new_owner_id": conversation.owner_id},
                    triggered_by="hr_user",
                )
            )
        except Exception as e:
            logger.error(f"[HandBackConversation] Failed to add ownership event: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database error creating ownership change event")
    # S-035/HRMS-0435 Step 4 (de-escalation): hand-back from an escalated
    # conversation must also clear escalation_state, or it stays stuck at
    # "escalated" forever -- a real gap this endpoint had before this
    # story (hand_back_conversation() only ever touched ownership).
    if conversation.escalation_state == "escalated":
        from app.services.conversation_state_service import resolve_escalation
        resolve_escalation(
            db, conversation, reason=f"HR user {current_user.UserID} handed conversation back to the AI agent.",
            triggered_by="hr_user",
        )
    log_audit_event(
        db,
        tenant_id=conversation.tenant_id,
        candidate_id=conversation.candidate_id,
        conversation_id=conversation.id,
        audit_event_type="OWNERSHIP_CHANGED",
        description=f"HR user {current_user.UserID} handed conversation {conversation.id} back to the AI agent.",
        actor_type="HR",
        actor_id=current_user.UserID,
        before_state=before_state,
        after_state={"owner_type": conversation.owner_type, "owner_id": conversation.owner_id},
    )
    try:
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        logger.error(f"[HandBackConversation] Failed to commit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to hand back conversation")
    return ConversationOwnershipResponse(
        conversation_id=conversation.id,
        owner_type=conversation.owner_type,
        owner_id=conversation.owner_id,
    )

# ===========================================================================
# POST /ai-agent/conversations/{conversation_id}/thunder-pause
# ===========================================================================

@router.post(
    "/conversations/{conversation_id}/thunder-pause",
    response_model=ThunderPauseResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Pause Thunder for this candidate, optionally with an auto-resume time (S-075)",
    description=(
        "HRMS-0475 BR-01: does not change owner_type -- the conversation "
        "stays AI-owned, so Thunder resumes exactly where it left off "
        "with no 'Hand Back' needed. Omit resume_at to pause until "
        "manually resumed."
    ),
)
def thunder_pause(
    conversation_id: int,
    body: PauseThunderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):

    conversation = _get_conversation_or_404(conversation_id, db)
    resume_at = None
    if body.resume_at:
        try:
            resume_at = _datetime.fromisoformat(body.resume_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid resume_at datetime: {body.resume_at!r}")

    pause_thunder(db, conversation, paused_by=current_user.UserID, resume_at=resume_at)
    log_audit_event(
        db,
        tenant_id=conversation.tenant_id,
        candidate_id=conversation.candidate_id,
        conversation_id=conversation.id,
        audit_event_type="THUNDER_PAUSED",
        description=f"HR user {current_user.UserID} paused Thunder for conversation {conversation.id}.",
        actor_type="HR",
        actor_id=current_user.UserID,
        after_state={"is_thunder_paused": True, "thunder_resume_at": resume_at.isoformat() if resume_at else None},
    )
    try:
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        logger.error(f"[ThunderPause] Failed to commit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to pause Thunder")
    return ThunderPauseResponse(
        conversation_id=conversation.id,
        is_thunder_paused=conversation.is_thunder_paused,
        thunder_resume_at=conversation.thunder_resume_at.isoformat() if conversation.thunder_resume_at else None,
        thunder_paused_by=conversation.thunder_paused_by,
    )

# ===========================================================================
# POST /ai-agent/conversations/{conversation_id}/thunder-resume
# ===========================================================================

@router.post(
    "/conversations/{conversation_id}/thunder-resume",
    response_model=ThunderPauseResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Resume Thunder for this candidate immediately (S-075)",
)
def thunder_resume(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    conversation = _get_conversation_or_404(conversation_id, db)
    resume_thunder(db, conversation)
    log_audit_event(
        db,
        tenant_id=conversation.tenant_id,
        candidate_id=conversation.candidate_id,
        conversation_id=conversation.id,
        audit_event_type="THUNDER_RESUMED",
        description=f"HR user {current_user.UserID} resumed Thunder for conversation {conversation.id}.",
        actor_type="HR",
        actor_id=current_user.UserID,
        after_state={"is_thunder_paused": False},
    )
    try:
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        logger.error(f"[ThunderResume] Failed to commit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resume Thunder")
    return ThunderPauseResponse(
        conversation_id=conversation.id,
        is_thunder_paused=conversation.is_thunder_paused,
        thunder_resume_at=None,
        thunder_paused_by=conversation.thunder_paused_by,
    )

# ===========================================================================
# GET /ai-agent/assignments/{candidate_id}
# ===========================================================================

@router.get(
    "/assignments/{candidate_id}",
    response_model=List[AIAssignmentOut],
    summary="Get all AI agent assignments for a candidate",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    description=(
        "Returns the full history of AI agent assignments for a candidate, "
        "ordered newest-first. The active assignment has `is_active = true`."
    ),
)
def get_assignments(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_candidate_or_404(candidate_id, db)

    try:
        assignments = (
            db.query(CandidateAIAssignment)
            .filter(CandidateAIAssignment.candidate_id == candidate_id)
            .order_by(CandidateAIAssignment.assigned_at.desc())
            .all()
        )
    except Exception as e:
        logger.error(f"[GetAssignments] Failed to query assignments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error retrieving assignments")

    return [AIAssignmentOut.model_validate(a) for a in assignments]

# ===========================================================================
# DELETE /ai-agent/assign/{candidate_id}
# ===========================================================================

@router.delete(
    "/assign/{candidate_id}",
    status_code=200,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Deactivate AI agent for a candidate",
    description=(
        "Marks all active AI agent assignments for the candidate as inactive "
        "and closes any open conversations."
    ),
)
def deactivate_agent(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_candidate_or_404(candidate_id, db)

    try:
        updated_assignments = (
            db.query(CandidateAIAssignment)
            .filter(
                CandidateAIAssignment.candidate_id == candidate_id,
                CandidateAIAssignment.is_active == True,
            )
            .update({"is_active": False})
        )
    except Exception as e:
        logger.error(f"[DeactivateAgent] Failed to deactivate assignments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error deactivating assignments")

    # Close open conversations
    try:
        open_convs = (
            db.query(CandidateConversation)
            .filter(
                CandidateConversation.candidate_id == candidate_id,
                CandidateConversation.status.in_(["open", "awaiting_candidate"]),
            )
            .all()
        )
    except Exception as e:
        logger.error(f"[DeactivateAgent] Failed to query open conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error retrieving conversations")
    from app.services.conversation_state_service import transition_status

    if open_convs:
        for conv in open_convs:
            transition_status(db, conv, "closed", reason="AI agent manually deactivated by HR", triggered_by="hr_user")
            conv.next_action = "none"
            conv.summary = (conv.summary or "") + " [Manually deactivated by HR]"
            # Log the deactivation event - check for recent duplicates
            from datetime import datetime, timedelta
            try:
                recent_deassign = db.query(ConversationEvent).filter(
                    ConversationEvent.conversation_id == conv.id,
                    ConversationEvent.event_type == "ai_deassigned",
                    ConversationEvent.created_at >= datetime.utcnow() - timedelta(seconds=5)
                ).first()
            except Exception as e:
                logger.error(f"[DeactivateAgent] Failed to query deassignment event: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Database error checking for duplicate deassignment event")

            if not recent_deassign:
                event = ConversationEvent(
                    conversation_id=conv.id,
                    event_type="ai_deassigned",
                    event_data={"deactivated_by": current_user.UserID},
                    triggered_by="hr_user",
                )
                db.add(event)

    try:
        db.commit()
    except Exception as e:
        logger.error(f"[DeactivateAgent] Failed to commit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to deactivate AI agent")

    return {
        "message": f"AI agent deactivated for candidate '{candidate_id}'.",
        "candidate_id": candidate_id,
        "assignments_deactivated": updated_assignments,
        "conversations_closed": len(open_convs),
    }

# ===========================================================================
# GET /ai-agent/inbox
# ===========================================================================


def _inbox_not_implemented():
    """Service-mailbox reading has no implementation yet (read_all_inbox /
    read_inbox_by_email are placeholders that return nothing)."""
    raise HTTPException(
        status_code=501,
        detail="Reading the service mailbox is not implemented yet.",
    )


# ===========================================================================
# GET /ai-agent/inbox/by-email
# ===========================================================================


# ===========================================================================
# GET /ai-agent/candidates/{candidate_id}/audit-log
# ===========================================================================


# ===========================================================================
# GET /ai-agent/messages/{event_id}/explanation
# GET /ai-agent/candidates/{candidate_id}/thunder-explanation-log
# ===========================================================================

from app.schemas.thunder_explanation import ExplanationLogResponse, MessageExplanationResponse
from app.services.thunder_explanation_service import get_explanation_log, get_message_explanation

