"""
Flash — Internal Query Agent — API Endpoints
=======================================
Prefix: /flash
Tag:    flash

Real, authenticated conversational query surface for BlitzenX staff and
employees. 2026-08-06, Avinash's explicit product split: Thunder is the
EXTERNAL-facing agent (open jobs, a logged-in candidate's own
application/onboarding status) -- Flash is the INTERNAL-facing agent,
used by staff and by anyone once they convert from candidate to
employee. See app.services.flash_service for the full rationale: every
answer comes from a real DB query, never a fabricated one; a language
model (app.services.flash_brain) only classifies intent and extracts a
search term, and sees work data only -- "strict mode,"
per Avinash's own words, not a general-purpose chat model guessing.

Renamed 2026-08-06 from "Ask Thunder" (module/route prefix were
internal_ask_thunder.py / /ask-thunder) -- functionally unchanged,
this is a branding/naming correction only. Git history preserved via
`git mv`.

Since 2026-10-15 (flash spec B) the conversation is server-side, one per
user: the bubble loads it on any screen, polls it while closed, opens a
workflow from a deep link (?flash=kind:ref) and shows decisions waiting.

Routes:
  GET  /flash/conversation?after_id=      messages, open workflow, decisions waiting, unread
  POST /flash/                            one turn ({message})
  POST /flash/conversation/reset          archive; the next message starts a new conversation
  POST /flash/conversation/read           the bubble has shown messages up to an id
  POST /flash/workflows/open              {kind, ref}: deep-link target

Gated the same way app.api.v1.endpoints.clients is (get_current_internal_user)
-- this system has no dedicated BU Head / Resource Manager role yet
(see src/layout/Shell.js's own note on this), so the broad internal-
staff check is the closest real gate available today. Individual
intents (finance_pnl, ar_aging) apply a stricter, additional gate on
top of this (see flash_service.can_view_pnl) for financial data
specifically.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.schemas.flash import (
    FlashConversationResponse,
    FlashReadRequest,
    FlashReadResponse,
    FlashRequest,
    FlashResetResponse,
    FlashResponse,
    FlashWorkflowOpenRequest,
)
from app.services import flash_conversation_service as conversations
from app.services.flash_brain.agent import message_dict, run_turn
from app.services.flash_brain.decisions import pending_decisions
from app.services.flash_brain.llm import Brains, get_brains
from app.services.flash_brain.workflows import open_workflow

router = APIRouter(prefix="/flash", tags=["flash"])

FLASH_ACCESS = [Depends(require_resource_permission("ask-flash", "create")), Depends(get_current_internal_user)]


@router.get("/conversation", dependencies=FLASH_ACCESS, response_model=FlashConversationResponse,
            summary="The caller's Flash conversation: messages (after an id), decisions waiting, unread count")
def get_conversation(
    after_id: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
    brains: Brains = Depends(get_brains),
):
    conversation = conversations.find_active(db, current_user.UserID)
    messages = conversations.messages(db, conversation, after_id=after_id) if conversation else []
    return FlashConversationResponse(
        conversation_id=conversation.id if conversation else None,
        messages=[message_dict(m) for m in messages],
        active_workflow=conversation.active_workflow if conversation else None,
        brain_status=brains.status(),
        pending_decisions=[d.as_dict() for d in pending_decisions(db, current_user)],
        unread=conversations.unread_count(db, conversation) if conversation else 0,
        poll_seconds=settings.FLASH_POLL_SECONDS,
    )


@router.post("/", dependencies=FLASH_ACCESS, response_model=FlashResponse,
             summary="Ask Flash — real data, no hallucinated answers")
def ask_flash(
    body: FlashRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
    brains: Brains = Depends(get_brains),
):
    return FlashResponse(**run_turn(db, current_user, body.message.strip(), brains=brains))


@router.post("/conversation/reset", dependencies=FLASH_ACCESS, response_model=FlashResetResponse,
             summary="Archive the conversation; the next message starts a new one")
def reset_conversation(db: Session = Depends(get_db), current_user=Depends(get_current_internal_user)):
    archived = conversations.archive(db, current_user)
    db.commit()
    return FlashResetResponse(archived_conversation_id=archived)


@router.post("/conversation/read", dependencies=FLASH_ACCESS, response_model=FlashReadResponse,
             summary="The bubble has shown the messages up to this id")
def mark_read(body: FlashReadRequest, db: Session = Depends(get_db),
              current_user=Depends(get_current_internal_user)):
    conversation = conversations.find_active(db, current_user.UserID)
    if conversation is None:
        return FlashReadResponse()
    conversations.mark_read(conversation, body.up_to_id, db)
    db.commit()
    return FlashReadResponse(last_read_message_id=conversation.last_read_message_id)


@router.post("/workflows/open", dependencies=FLASH_ACCESS, response_model=FlashResponse,
             summary="Open a Flash discussion on a record (deep-link target, e.g. core_cert:<request id>)")
def open_flash_workflow(
    body: FlashWorkflowOpenRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
    brains: Brains = Depends(get_brains),
):
    conversation = conversations.active_conversation(db, current_user)
    result = open_workflow(db, current_user, conversation, body.kind, body.ref)
    said = conversations.append(db, conversation, "flash", result["reply"],
                                {"intent": f"workflow:{body.kind}", "workflow": {"kind": body.kind, "ref": body.ref}})
    conversations.mark_read(conversation, said.id)
    db.commit()
    return FlashResponse(reply=result["reply"], messages=[message_dict(said)],
                         active_workflow=conversation.active_workflow, brain_status=brains.status(),
                         intent=f"workflow:{body.kind}")
