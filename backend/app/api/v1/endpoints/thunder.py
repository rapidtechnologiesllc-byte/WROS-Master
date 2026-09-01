"""
"Test Thunder" â€” API Endpoints
================================
Prefix: /thunder
Tag:    thunder

Internal QA harness, gated behind the "thunder.test" RBAC permission
(Super User only by default as of 2026-07-23 -- see rbac_service.py's
PERMISSIONS_SEED/ROLE_PERMISSIONS_SEED) rather than the coarse
get_current_internal_user check every other internal role used to satisfy.
Tightened after this tool's frontend nav entry ("Test Thunder", first
item for every role) caused real confusion about account identity --
removed from Shell.js's nav entirely; this backend gate is defense in
depth for anyone still hitting the route directly by URL.

Lets a permitted internal user chat with Thunder as if they were a
candidate, without a live WhatsApp Business API (none is provisioned in
this codebase). The real send path
(app.services.thunder_service.send_thunder_message) still runs underneath â€”
R-08 ownership lock, consent, and the 60s debounce are all live â€” only the
outbound WhatsApp transport is mocked.

Routes:
  POST   /thunder/test-chat
      Send a message as the test candidate; get Thunder's real,
      LLM-generated reply back.

  GET    /thunder/test-chat/history
      The current tester's test conversation history so far.

  POST   /thunder/test-chat/reset
      Start a fresh test conversation (closes the current one; nothing
      is deleted).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.user import Users
from app.schemas.thunder import (
    TestChatHistoryItem,
    TestChatHistoryResponse,
    TestChatMessageRequest,
    TestChatMessageResponse,
)
from app.services.thunder_service import (
    ConsentNotGiven,
    DuplicateMessageSuppressed,
    ThunderReplyGenerationFailed,
    test_candidate_id_for,
    get_test_chat_history,
    reset_test_chat,
    run_test_chat_turn,
)
from app.services.whatsapp_routing_service import ConversationOwnedByHuman

router = APIRouter(prefix="/thunder", tags=["thunder"])


@router.post(
    "/test-chat",
    response_model=TestChatMessageResponse,
    summary="Send a message to Thunder as a test candidate and get a real reply",
    description=(
        "Sends `message` as if it came from a candidate over WhatsApp, generates "
        "Thunder's reply with the real LLM (Gemini) using the candidate's full "
        "cross-channel context, and sends it back through the real, governed send "
        "path â€” R-08 ownership lock, consent, and the 60s duplicate-message "
        "debounce all still apply. Only the outbound WhatsApp transport is mocked "
        "(no live WhatsApp Business API is provisioned in this codebase)."
    ),
)
def send_test_chat_message(
    body: TestChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("thunder", "edit")),
):
    try:
        result = run_test_chat_turn(
            db, current_user=current_user, message_body=body.message,
        )
    except ConversationOwnedByHuman as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Thunder can't reply: this test conversation is currently owned by "
                "a human (R-08 ownership lock). Reset the test chat to hand it back "
                f"to Thunder. ({exc})"
            ),
        )
    except DuplicateMessageSuppressed as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ConsentNotGiven as exc:
        raise HTTPException(status_code=424, detail=str(exc))
    except ThunderReplyGenerationFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return TestChatMessageResponse(**result)


@router.get(
    "/test-chat/history",
    response_model=TestChatHistoryResponse,
    summary="Get the current tester's Test Thunder conversation history",
)
def get_test_chat_history_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("thunder", "edit")),
):
    messages = get_test_chat_history(db, tenant_id=current_user.UserID)
    return TestChatHistoryResponse(
        conversation_candidate_id=test_candidate_id_for(current_user.UserID),
        messages=[TestChatHistoryItem(**m) for m in messages],
    )


@router.post(
    "/test-chat/reset",
    status_code=200,
    summary="Start a fresh Test Thunder conversation",
    description=(
        "Closes the current tester's test conversation so the next message "
        "starts a clean thread. Nothing is deleted â€” the prior conversation and "
        "its events stay in the database."
    ),
)
def reset_test_chat_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("thunder", "edit")),
):
    reset_test_chat(db, tenant_id=current_user.UserID)
    return {"message": "Test Thunder conversation reset."}
