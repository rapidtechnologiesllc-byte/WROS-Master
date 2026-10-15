"""One Flash turn on the user's server-side conversation (flash spec C, "turn function").

1. The user's message is stored.
2. An open workflow (e.g. a Core certification decision) takes the message; workflows are
   deterministic, so they carry no offline note.
3. Otherwise the question is answered from real data: the rules, and for phrasings they miss the
   brain router (flash_service.answer_internal_query). The large-model tool loop replaces this
   step in the agent phase; every read answer stays the same.
4. For a question, when the brain tier differs from the one this conversation last ran on, the
   reply starts with the offline note once.
5. The reply is stored and the turn committed.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.flash_conversation import FlashConversation, FlashMessage
from app.models.user import Users
from app.services import flash_conversation_service as conversations
from app.services.flash_brain.llm import Brains
from app.services.flash_brain.workflows import step_workflow

logger = logging.getLogger(__name__)


def message_dict(message: FlashMessage) -> Dict:
    return {"id": message.id, "role": message.role, "body": message.body, "payload": message.payload,
            "created_at": message.created_at}


def status_note(conversation: FlashConversation, brains: Brains) -> Optional[str]:
    """Say what is offline once, when the tier changes (a first conversation counts as a change)."""
    current = brains.status()
    if conversation.brain_status == current:
        return None
    conversation.brain_status = current
    return brains.offline_note()


def run_turn(db: Session, user: Users, text: str, *, brains: Brains, now: Optional[datetime] = None) -> Dict:
    from app.services.flash_service import MAX_HISTORY_TURNS, answer_internal_query

    conversation = conversations.active_conversation(db, user)
    earlier = conversations.recent_text_turns(db, conversation)
    asked = conversations.append(db, conversation, "user", text)

    job_id = None
    if conversation.active_workflow:  # deterministic: no model involved, so no offline note
        kind = conversation.active_workflow
        result = step_workflow(db, user, conversation, text)
        reply, intent = result["reply"], f"workflow:{kind}"
    else:
        history = conversations.question_reply_pairs(earlier)[-MAX_HISTORY_TURNS:]
        answer = answer_internal_query(db, text, current_user=user, history=history, brains=brains)
        reply, intent, job_id = answer["reply"], answer["intent"], answer.get("job_id")
        note = status_note(conversation, brains)
        if note:
            reply = f"{note}\n\n{reply}"
    answered = conversations.append(db, conversation, "flash", reply, {"intent": intent})
    conversations.mark_read(conversation, answered.id)
    db.commit()
    return {"reply": reply, "intent": intent, "job_id": job_id, "messages": [message_dict(asked), message_dict(answered)],
            "active_workflow": conversation.active_workflow, "brain_status": brains.status()}
