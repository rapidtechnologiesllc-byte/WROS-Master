"""
Public Thunder Chat — API Endpoints
=====================================
Prefix: /public/thunder-chat
Tag:    public-thunder-chat

Real, unauthenticated candidate-facing chat widget (careers page / job
listing) — a second real intake channel alongside WhatsApp, not an
internal test tool. See app.services.public_chat_service for the full
rationale and app.middleware.auth_middleware.AuthenticationMiddleware.
PUBLIC_ROUTES for the exemption from the global auth gate. Covered by
the app-wide RateLimitMiddleware (app/main.py) like every other route.

Routes:
  POST /public/thunder-chat/start
      First contact: visitor supplies name/email/phone + consent,
      becomes a real Candidate row (or resumes an existing one, matched
      by email/phone — the same R-07 dedup every candidate-creation
      path in this codebase uses), gets a real Thunder greeting back.

  POST /public/thunder-chat/message
      A real chat turn: Thunder's reply is generated with the exact
      same context-aware LLM path WhatsApp candidates get.

  GET  /public/thunder-chat/history
      This session's transcript so far.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.schemas.public_chat import (
    PublicChatHistoryItem,
    PublicChatHistoryResponse,
    PublicChatMessageRequest,
    PublicChatMessageResponse,
    PublicChatStartRequest,
    PublicChatStartResponse,
)
from app.services.public_chat_service import (
    PublicChatConsentRequired,
    PublicChatNoTenantAvailable,
    PublicChatSessionNotFound,
    get_public_chat_history,
    send_public_chat_message,
    start_public_chat,
)
from app.services.thunder_service import ConsentNotGiven, DuplicateMessageSuppressed
from app.services.whatsapp_routing_service import ConversationOwnedByHuman

router = APIRouter(prefix="/public/thunder-chat", tags=["public-thunder-chat"])


@router.post(
    "/start",
    response_model=PublicChatStartResponse,
    summary="Start (or resume) a public Thunder chat session — no auth required",
)
def start_chat(body: PublicChatStartRequest, db: Session = Depends(get_db)):
    # This endpoint is anonymous and external -- every error message
    # below is written for a stranger, never the real exception text.
    # Internal details (user IDs, conversation IDs, consent-type names)
    # are logged server-side only. Per Avinash's explicit instruction,
    # 2026-07-23: external candidates must never get internal information.
    try:
        result = start_public_chat(
            db,
            full_name=body.full_name,
            email=body.email,
            phone=body.phone,
            job_id=body.job_id,
            consent=body.consent,
        )
    except PublicChatConsentRequired:
        raise HTTPException(status_code=400, detail="Please agree to be contacted to start chatting with Thunder.")
    except PublicChatNoTenantAvailable as exc:
        logger.error(f"[PublicChat] /start misconfigured: {exc}")
        raise HTTPException(status_code=500, detail="Thunder isn't available right now. Please try again shortly.")
    except (ConsentNotGiven, ConversationOwnedByHuman) as exc:
        logger.warning(f"[PublicChat] /start blocked: {exc}")
        raise HTTPException(status_code=424, detail="Thunder can't start this chat right now. Please try again shortly.")
    except DuplicateMessageSuppressed as exc:
        logger.info(f"[PublicChat] /start duplicate suppressed: {exc}")
        raise HTTPException(status_code=429, detail="Please wait a moment before trying again.")

    return PublicChatStartResponse(**result)


@router.post(
    "/message",
    response_model=PublicChatMessageResponse,
    summary="Send a message to Thunder in an existing public chat session — no auth required",
)
def send_message(body: PublicChatMessageRequest, db: Session = Depends(get_db)):
    # Same posture as /start above -- generic messages to the caller,
    # real detail logged server-side only.
    try:
        result = send_public_chat_message(db, candidate_id=body.candidate_id, message=body.message)
    except PublicChatSessionNotFound:
        raise HTTPException(status_code=404, detail="We couldn't find that chat session. Please start a new chat.")
    except ConversationOwnedByHuman as exc:
        logger.info(f"[PublicChat] /message blocked by human ownership: {exc}")
        raise HTTPException(
            status_code=409,
            detail="Thunder can't reply right now -- a member of our team will follow up directly.",
        )
    except DuplicateMessageSuppressed as exc:
        logger.info(f"[PublicChat] /message duplicate suppressed: {exc}")
        raise HTTPException(status_code=429, detail="Please wait a moment before sending that again.")
    except ConsentNotGiven as exc:
        logger.warning(f"[PublicChat] /message blocked, no consent: {exc}")
        raise HTTPException(status_code=424, detail="Thunder can't reply right now. Please start a new chat.")

    return PublicChatMessageResponse(**result)


@router.get(
    "/history",
    response_model=PublicChatHistoryResponse,
    summary="Get this session's chat history — no auth required",
)
def chat_history(candidate_id: str, db: Session = Depends(get_db)):
    messages = get_public_chat_history(db, candidate_id=candidate_id)
    return PublicChatHistoryResponse(
        candidate_id=candidate_id,
        messages=[PublicChatHistoryItem(**m) for m in messages],
    )
