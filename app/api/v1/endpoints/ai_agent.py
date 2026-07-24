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

  GET    /ai-agent/assignments/{candidate_id}
      Return all AI agent assignments for a candidate.

  DELETE /ai-agent/assign/{candidate_id}
      Deactivate the AI agent assignment for a candidate.

  GET    /ai-agent/candidates/{candidate_id}/audit-log
      Compliance-grade audit trail of conversation actions (S-076).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
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
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.ai_conversation_service import (
    assign_ai_agent,
    get_conversation_thread,
    get_missing_fields,
    process_candidate_reply,
    read_all_inbox,
    read_inbox_by_email,
    SERVICE_MAILBOX,
)
from app.services.audit_log_service import log_audit_event
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
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return candidate


def _get_conversation_or_404(conversation_id: int, db: Session) -> CandidateConversation:
    conversation = db.query(CandidateConversation).filter(
        CandidateConversation.id == conversation_id
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return conversation


# ===========================================================================
# POST /ai-agent/assign
# ===========================================================================

@router.post(
    "/assign",
    response_model=AIAgentAssignResponse,
    status_code=201,
    dependencies=[Depends(require_permission("candidate.edit"))],
    summary="Assign AI agent to a candidate",
    description=(
        "Assigns the onboarding AI agent to a candidate. "
        "The agent immediately checks for missing profile fields and sends "
        "a polite email to the candidate requesting the information. "
        "All activity is logged to the conversation tables."
    ),
)
def assign_agent(
    body: AIAgentAssignRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    **Flow:**
    1. Deactivates any previous AI assignment for the candidate.
    2. Creates a new `candidate_ai_assignments` row.
    3. Opens a `candidate_conversations` thread.
    4. Detects missing core profile fields.
    5. Sends a missing-fields email to the candidate.
    6. Logs `ai_assigned`, `field_check`, and `ai_message_sent` events.

    **Required permission:** `candidate.edit`
    """
    result = assign_ai_agent(
        candidate_id=body.candidate_id,
        tenant_id=current_user.UserID,
        assigned_by=current_user.UserID,
        db=db,
    )
    return AIAgentAssignResponse(**result)


# ===========================================================================
# GET /ai-agent/missing-fields/{candidate_id}
# ===========================================================================

@router.get(
    "/missing-fields/{candidate_id}",
    response_model=MissingFieldsResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
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
    current_user: Users = Depends(get_current_hr_or_admin),
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

@router.get(
    "/portal-link/{candidate_id}",
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get this candidate's Candidate Portal magic link (S-017/HRMS-0417)",
    description=(
        "Returns the /candidate/{token} URL a recruiter can send the "
        "candidate (WhatsApp/Email) so they can view their own "
        "conversation, complete missing profile fields, and see "
        "upcoming interviews without a password."
    ),
)
def get_candidate_portal_link(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    from app.services.candidate_portal_service import generate_portal_link_url

    _get_candidate_or_404(candidate_id, db)
    return {"candidate_id": candidate_id, "portal_url": generate_portal_link_url(candidate_id)}


# ===========================================================================
# GET /ai-agent/memory/{candidate_id}
# ===========================================================================

@router.get(
    "/memory/{candidate_id}",
    response_model=CandidateMemoryResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
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
    current_user: Users = Depends(get_current_hr_or_admin),
):
    from app.services.ai_conversation_service import resolve_default_tenant_id
    from app.services.candidate_memory_service import get_memory

    _get_candidate_or_404(candidate_id, db)
    tenant_id = resolve_default_tenant_id(db)
    memory = get_memory(db, candidate_id, tenant_id)
    return CandidateMemoryResponse(candidate_id=candidate_id, **memory)


# ===========================================================================
# PATCH /ai-agent/memory/{candidate_id}/facts/{fact_id}
# ===========================================================================

@router.patch(
    "/memory/{candidate_id}/facts/{fact_id}",
    response_model=MemoryFactItem,
    dependencies=[Depends(require_permission("candidate.edit"))],
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
    current_user: Users = Depends(get_current_hr_or_admin),
):
    from app.services.ai_conversation_service import resolve_default_tenant_id
    from app.services.candidate_memory_service import FactNotFound, correct_fact

    _get_candidate_or_404(candidate_id, db)
    tenant_id = resolve_default_tenant_id(db)
    try:
        fact = correct_fact(db, candidate_id, tenant_id, fact_id, body.fact_value, corrected_by=current_user.UserID)
    except FactNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MemoryFactItem(
        id=fact.id, category=fact.fact_category, key=fact.fact_key, value=fact.fact_value,
        confidence=fact.confidence, is_low_confidence=fact.confidence < 0.7, extracted_at=fact.extracted_at,
    )


# ===========================================================================
# POST /ai-agent/webhook/email-reply
# ===========================================================================

@router.post(
    "/webhook/email-reply",
    response_model=ProcessReplyResponse,
    summary="Process an incoming candidate reply email",
    dependencies=[Depends(require_webhook_secret_or_internal_user)],
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
    result = process_candidate_reply(
        candidate_id=body.candidate_id,
        db=db,
        raw_reply_text=body.raw_reply_text,
        message_id=body.message_id,
    )
    return ProcessReplyResponse(**result)


# ===========================================================================
# POST /ai-agent/poll/{candidate_id}
# ===========================================================================

@router.post(
    "/poll/{candidate_id}",
    response_model=ProcessReplyResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
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
    current_user: Users = Depends(get_current_hr_or_admin),
):
    result = process_candidate_reply(
        candidate_id=candidate_id,
        db=db,
        raw_reply_text=None,    # triggers live Graph inbox poll
        message_id=None,
    )
    return ProcessReplyResponse(**result)


# ===========================================================================
# GET /ai-agent/conversations/{candidate_id}
# ===========================================================================

@router.get(
    "/conversations/{candidate_id}",
    response_model=ConversationThreadResponse,
    summary="Get full agent–candidate conversation thread",
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
    current_user: Users = Depends(get_current_hr_or_admin),
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

@router.get(
    "/conversations/{candidate_id}/active",
    response_model=ConversationThreadItem,
    summary="Get the active conversation for a candidate",
    description=(
        "Returns the single most-recent open or awaiting conversation for the "
        "candidate, with its full event log. Returns 404 if no active conversation exists."
    ),
)
def get_active_conversation(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    _get_candidate_or_404(candidate_id, db)

    conv = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate_id,
            CandidateConversation.status.in_(["open", "awaiting_candidate"]),
        )
        .order_by(CandidateConversation.created_at.desc())
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=404,
            detail=f"No active conversation found for candidate '{candidate_id}'.",
        )

    events = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conv.id)
        .order_by(ConversationEvent.created_at.asc())
        .all()
    )

    from datetime import datetime as _datetime
    from app.services.sla_monitoring_service import get_active_no_contact_breach_for_conversation
    breach = get_active_no_contact_breach_for_conversation(db, conv.id)
    no_contact_hours = round((_datetime.utcnow() - breach.breached_at).total_seconds() / 3600.0, 1) if breach else None

    return ConversationThreadItem(
        conversation_id=conv.id,
        status=conv.status,
        ai_agent_name=conv.ai_agent_name,
        channel_preference=conv.channel_preference,
        summary=conv.summary,
        summary_generated_at=conv.summary_generated_at.isoformat() if conv.summary_generated_at else None,
        no_contact_breach_hours=no_contact_hours,
        next_action=conv.next_action,
        owner_type=conv.owner_type,
        escalation_state=conv.escalation_state,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        events=[
            ConversationEventOut(
                id=ev.id,
                event_type=ev.event_type,
                event_data=ev.event_data,
                triggered_by=ev.triggered_by,
                created_at=ev.created_at.isoformat() if ev.created_at else None,
            )
            for ev in events
        ],
    )


# ===========================================================================
# POST /ai-agent/conversations/{conversation_id}/send
# ===========================================================================

@router.post(
    "/conversations/{conversation_id}/send",
    response_model=SendMessageResponse,
    status_code=201,
    dependencies=[Depends(require_permission("candidate.edit"))],
    summary="Manually send a message to the candidate on this conversation (S-009)",
    description=(
        "Sends a WhatsApp message from the current HR user to the candidate. "
        "Per HRMS-0409 BR-01, this unconditionally transfers ownership of the "
        "conversation to the sending HR user — Thunder will not send again "
        "until the conversation is handed back."
    ),
)
def send_manual_message(
    conversation_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
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

    db.commit()
    db.refresh(event)
    db.refresh(conversation)

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
    dependencies=[Depends(require_permission("candidate.edit"))],
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
    current_user: Users = Depends(get_current_hr_or_admin),
):
    conversation = _get_conversation_or_404(conversation_id, db)
    before_state = {"owner_type": conversation.owner_type, "owner_id": conversation.owner_id}
    take_over_conversation(db, conversation, current_user.UserID)
    db.add(
        ConversationEvent(
            conversation_id=conversation.id,
            event_type="ownership_changed",
            event_data={"new_owner_type": "hr_user", "new_owner_id": current_user.UserID},
            triggered_by="hr_user",
        )
    )
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
    db.commit()
    db.refresh(conversation)
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
    dependencies=[Depends(require_permission("candidate.edit"))],
    summary="Hand a conversation back to the AI agent (S-010)",
    description="HRMS-0410 HAND_BACK: returns the conversation to Thunder.",
)
def hand_back(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    conversation = _get_conversation_or_404(conversation_id, db)
    before_state = {"owner_type": conversation.owner_type, "owner_id": conversation.owner_id}
    hand_back_conversation(db, conversation)
    db.add(
        ConversationEvent(
            conversation_id=conversation.id,
            event_type="ownership_changed",
            event_data={"new_owner_type": "ai_agent", "new_owner_id": conversation.owner_id},
            triggered_by="hr_user",
        )
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
    db.commit()
    db.refresh(conversation)
    return ConversationOwnershipResponse(
        conversation_id=conversation.id,
        owner_type=conversation.owner_type,
        owner_id=conversation.owner_id,
    )


# ===========================================================================
# GET /ai-agent/assignments/{candidate_id}
# ===========================================================================

@router.get(
    "/assignments/{candidate_id}",
    response_model=List[AIAssignmentOut],
    summary="Get all AI agent assignments for a candidate",
    description=(
        "Returns the full history of AI agent assignments for a candidate, "
        "ordered newest-first. The active assignment has `is_active = true`."
    ),
)
def get_assignments(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    _get_candidate_or_404(candidate_id, db)

    assignments = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate_id)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .all()
    )
    return [AIAssignmentOut.model_validate(a) for a in assignments]


# ===========================================================================
# DELETE /ai-agent/assign/{candidate_id}
# ===========================================================================

@router.delete(
    "/assign/{candidate_id}",
    status_code=200,
    dependencies=[Depends(require_permission("candidate.edit"))],
    summary="Deactivate AI agent for a candidate",
    description=(
        "Marks all active AI agent assignments for the candidate as inactive "
        "and closes any open conversations."
    ),
)
def deactivate_agent(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    _get_candidate_or_404(candidate_id, db)

    updated_assignments = (
        db.query(CandidateAIAssignment)
        .filter(
            CandidateAIAssignment.candidate_id == candidate_id,
            CandidateAIAssignment.is_active == True,
        )
        .update({"is_active": False})
    )

    # Close open conversations
    open_convs = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate_id,
            CandidateConversation.status.in_(["open", "awaiting_candidate"]),
        )
        .all()
    )
    from app.services.conversation_state_service import transition_status

    for conv in open_convs:
        transition_status(db, conv, "closed", reason="AI agent manually deactivated by HR", triggered_by="hr_user")
        conv.next_action = "none"
        conv.summary = (conv.summary or "") + " [Manually deactivated by HR]"
        # Log the deactivation event
        event = ConversationEvent(
            conversation_id=conv.id,
            event_type="ai_deassigned",
            event_data={"deactivated_by": current_user.UserID},
            triggered_by="hr_user",
        )
        db.add(event)

    db.commit()

    return {
        "message": f"AI agent deactivated for candidate '{candidate_id}'.",
        "candidate_id": candidate_id,
        "assignments_deactivated": updated_assignments,
        "conversations_closed": len(open_convs),
    }


# ===========================================================================
# GET /ai-agent/inbox
# ===========================================================================

@router.get(
    "/inbox",
    response_model=InboxResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Show all inbox messages from the service mailbox",
    description=(
        "Returns the most recent emails received in the `helpdesk_hrms@blitzenx.com` "
        "service mailbox, newest-first. Supports pagination via `top` and `skip`.\n\n"
        "> **Prerequisite**: The Azure AD application must have `Mail.Read` or "
        "`Mail.ReadWrite` **Application** permission granted by an admin.\n"
        "Go to: *Azure Portal → App Registrations → API permissions → Add permission "
        "→ Microsoft Graph → Application permissions → Mail.Read → Grant admin consent*."
    ),
)
def list_inbox(
    top: int = 50,
    skip: int = 0,
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Lists all inbox messages from the service mailbox.
    Returns 403 with a permission hint if Mail.Read is not granted.
    """
    messages = read_all_inbox(top=top, skip=skip)
    return InboxResponse(
        mailbox=SERVICE_MAILBOX,
        total_returned=len(messages),
        messages=[InboxMessageItem(**m) for m in messages],
    )


# ===========================================================================
# GET /ai-agent/inbox/by-email
# ===========================================================================

@router.get(
    "/inbox/by-email",
    response_model=InboxResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Show all inbox messages from a specific sender email",
    description=(
        "Returns all inbox messages from `helpdesk_hrms@blitzenx.com` that were "
        "sent **by** the given email address. Use this to view the full email "
        "conversation thread with a specific candidate or sender.\n\n"
        "> **Prerequisite**: `Mail.Read` or `Mail.ReadWrite` Application permission."
    ),
)
def list_inbox_by_email(
    email: str,
    top: int = 50,
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Returns inbox messages filtered by sender email address.
    Returns 403 with a permission hint if Mail.Read is not granted.
    """
    messages = read_inbox_by_email(email=email, top=top)
    return InboxResponse(
        mailbox=SERVICE_MAILBOX,
        total_returned=len(messages),
        messages=[InboxMessageItem(**m) for m in messages],
    )


# ===========================================================================
# GET /ai-agent/candidates/{candidate_id}/audit-log
# ===========================================================================

@router.get(
    "/candidates/{candidate_id}/audit-log",
    response_model=AuditLogResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Compliance-grade audit trail for a candidate's conversation actions (S-076)",
    description=(
        "Returns every ConversationAuditLog entry for this candidate, ordered "
        "chronologically. Insert-only at the application level — no endpoint "
        "in this API ever updates or deletes an audit record.\n\n"
        "NOTE: strict Recruiter-excluded (HR/Admin only) enforcement is not "
        "wired here — this codebase's RBAC permissions aren't seeded at that "
        "granularity yet. Gated on `candidate.view` like the rest of this "
        "router, same as `/missing-fields`."
    ),
)
def get_audit_log(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    _get_candidate_or_404(candidate_id, db)
    entries = (
        db.query(ConversationAuditLog)
        .filter(ConversationAuditLog.candidate_id == candidate_id)
        .order_by(ConversationAuditLog.created_at.asc())
        .all()
    )
    return AuditLogResponse(
        candidate_id=candidate_id,
        total_count=len(entries),
        audit_entries=[
            AuditLogEntryOut(
                id=e.id,
                audit_event_type=e.audit_event_type,
                audit_event_description=e.audit_event_description,
                actor_type=e.actor_type,
                actor_id=e.actor_id,
                before_state=e.before_state,
                after_state=e.after_state,
                created_at=e.created_at.isoformat() if e.created_at else None,
            )
            for e in entries
        ],
    )
