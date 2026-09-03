"""
S-004/HRMS-0404 -- Web Portal Chat Messages
==============================================
Prefix: /portal/conversations
import logging
Tag:    portal-messages

Candidate-authenticated (get_current_candidate -- real JWT candidate
session, not the spec's never-built HRMS-P111 magic link). See
app.services.portal_message_service for the architecture adaptation
rationale (stores into ConversationEvent, not a new table).

Routes:
  POST /portal/conversations/{conversation_id}/messages
  GET  /portal/conversations/{conversation_id}/messages
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate
from app.models.candidate import Candidate
from app.schemas.portal_messages import (
    PortalMessageHistoryResponse,
    PortalMessageRequest,
    PortalMessageResponse,
)
from app.services.portal_message_service import (
    PortalConversationNotFound,
    PortalMessageEmpty,
    PortalMessageTooLong,
    PortalRateLimitExceeded,
    get_portal_message_history,
    send_portal_message,
)

router = APIRouter(prefix="/portal/conversations", tags=["portal-messages"])


@router.post(
    "/{conversation_id}/messages",
    dependencies=[Depends(get_current_internal_user)],
    response_model=PortalMessageResponse,
    status_code=201,
    summary="Candidate sends a message via the web portal",
)
def post_portal_message(
    conversation_id: int,
    body: PortalMessageRequest,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    try:
        result = send_portal_message(db, candidate, conversation_id, body.message_body)
    except PortalConversationNotFound:
        raise HTTPException(status_code=403, detail="You don't have access to this conversation.")
    except PortalMessageEmpty as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PortalMessageTooLong as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PortalRateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    return PortalMessageResponse(**result)


@router.get(
    "/{conversation_id}/messages",
    dependencies=[Depends(get_current_internal_user)],
    response_model=PortalMessageHistoryResponse,
    summary="Candidate retrieves their portal conversation history",
)
def list_portal_messages(
    conversation_id: int,
    page: int = 0,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    try:
        result = get_portal_message_history(db, candidate, conversation_id, page=page)
    except PortalConversationNotFound:
        raise HTTPException(status_code=403, detail="You don't have access to this conversation.")

    return PortalMessageHistoryResponse(**result)


@router.get(
    "/{conversation_id}/messages/poll",
    dependencies=[Depends(get_current_internal_user)],
    response_model=PortalMessageHistoryResponse,
    summary="S-346 -- long-poll for messages newer than after_id (WebSocket fallback)",
)
def poll_portal_messages(
    conversation_id: int,
    after_id: int = 0,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    """No WebSocket infra in this codebase (see portal_message_service's
    module docstring) -- the chat widget calls this on a short interval
    to pick up messages sent on another channel (e.g. a WhatsApp reply)
    while the portal tab is open, catching what the synchronous POST
    reply above already delivers for the common case."""
    try:
        result = get_portal_message_history(db, candidate, conversation_id, after_id=after_id)
    except PortalConversationNotFound:
        raise HTTPException(status_code=403, detail="You don't have access to this conversation.")

    return PortalMessageHistoryResponse(**result)
