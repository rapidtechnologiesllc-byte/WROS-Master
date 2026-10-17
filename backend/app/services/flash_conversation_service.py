"""The one Flash conversation per user (flash spec B): get-or-create, append, recent turns,
events posted by Flash itself, the open workflow. Nothing here commits; the caller does."""
import logging
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.flash_conversation import FlashConversation, FlashMessage
from app.models.user import Users

logger = logging.getLogger(__name__)


def find_active(db: Session, user_id: str) -> Optional[FlashConversation]:
    return (db.query(FlashConversation)
            .filter(FlashConversation.user_id == user_id, FlashConversation.status == "ACTIVE").first())


def _get_or_create(db: Session, user_id: str, tenant_id: int) -> FlashConversation:
    conversation = find_active(db, user_id)
    if conversation is not None:
        return conversation
    try:
        with db.begin_nested():  # a second tab may create it at the same moment: the unique index decides
            conversation = FlashConversation(tenant_id=tenant_id, user_id=user_id, status="ACTIVE")
            db.add(conversation)
            db.flush()
        return conversation
    except IntegrityError:
        existing = find_active(db, user_id)
        if existing is None:
            raise
        return existing


def active_conversation(db: Session, user: Users) -> FlashConversation:
    """The user's ACTIVE conversation, created on first use (tenant from the user)."""
    if user.tenant_id is None:
        raise ValueError(f"User {user.UserID} has no tenant; Flash cannot keep a conversation for them")
    return _get_or_create(db, user.UserID, user.tenant_id)


def append(db: Session, conversation: FlashConversation, role: str, body: str,
           payload: Optional[Dict] = None) -> FlashMessage:
    if not body:
        raise ValueError("A Flash message needs a body")
    message = FlashMessage(conversation_id=conversation.id, role=role, body=body, payload=payload)
    db.add(message)
    db.flush()
    return message


def messages(db: Session, conversation: FlashConversation, *, after_id: Optional[int] = None,
             limit: Optional[int] = None) -> List[FlashMessage]:
    """Messages after `after_id` (oldest first), or the most recent page when no id is given."""
    query = db.query(FlashMessage).filter(FlashMessage.conversation_id == conversation.id)
    if after_id is not None:
        return query.filter(FlashMessage.id > after_id).order_by(FlashMessage.id).all()
    recent = query.order_by(FlashMessage.id.desc()).limit(limit or settings.FLASH_CONVERSATION_PAGE).all()
    return list(reversed(recent))


def unread_count(db: Session, conversation: FlashConversation) -> int:
    query = db.query(FlashMessage).filter(FlashMessage.conversation_id == conversation.id,
                                          FlashMessage.role != "user")
    if conversation.last_read_message_id is not None:
        query = query.filter(FlashMessage.id > conversation.last_read_message_id)
    return query.count()


def mark_read(conversation: FlashConversation, up_to_id: int, db: Optional[Session] = None) -> None:
    """Messages up to `up_to_id` have been shown. With `db`, an id beyond the conversation's
    newest message is capped there, so later messages still count as unread."""
    if db is not None:
        newest = (db.query(func.max(FlashMessage.id))
                  .filter(FlashMessage.conversation_id == conversation.id).scalar())
        up_to_id = min(up_to_id, newest or 0)
    if conversation.last_read_message_id is None or up_to_id > conversation.last_read_message_id:
        conversation.last_read_message_id = up_to_id


def recent_text_turns(db: Session, conversation: FlashConversation,
                      limit: Optional[int] = None) -> List[Dict]:
    """The last `limit` user/Flash exchanges as plain text ({"role": "user"|"assistant",
    "content"}), oldest first. Events and stored tool data are never included."""
    limit = limit or settings.FLASH_CONTEXT_TURNS
    rows = (db.query(FlashMessage)
            .filter(FlashMessage.conversation_id == conversation.id, FlashMessage.role.in_(("user", "flash")))
            .order_by(FlashMessage.id.desc()).limit(limit * 2).all())
    return [{"role": "user" if m.role == "user" else "assistant", "content": m.body} for m in reversed(rows)]


def question_reply_pairs(turns: List[Dict]) -> List[Dict]:
    """Plain turns as {question, reply} pairs (what the rules' follow-up resolution reads)."""
    pairs = []
    for asked, answered in zip(turns, turns[1:]):
        if asked["role"] == "user" and answered["role"] == "assistant":
            pairs.append({"question": asked["content"], "reply": answered["content"]})
    return pairs


def post_event(db: Session, user_id: str, tenant_id: int, body: str, payload: Optional[Dict] = None) -> FlashMessage:
    """Something Flash tells a user on its own (a decision waiting, progress on a search)."""
    return append(db, _get_or_create(db, user_id, tenant_id), "event", body, payload)


def set_workflow(db: Session, conversation: FlashConversation, kind: str, ref: Optional[str],
                 state: Optional[Dict] = None) -> None:
    conversation.active_workflow, conversation.workflow_ref, conversation.workflow_state = kind, ref, state
    db.flush()


def clear_workflow(db: Session, conversation: FlashConversation) -> None:
    set_workflow(db, conversation, None, None, None)


def archive(db: Session, user: Users) -> Optional[str]:
    """Reset: the active conversation is archived; the next message starts a new one."""
    conversation = find_active(db, user.UserID)
    if conversation is None:
        return None
    conversation.status = "ARCHIVED"
    db.flush()
    return conversation.id
