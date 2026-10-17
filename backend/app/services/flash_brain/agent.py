"""One Flash turn on the user's server-side conversation (flash spec C, "turn function").

1. The user's message is stored.
2. An open workflow (a Core certification decision, a job being drafted) takes the message.
3. Otherwise:
   - finance questions (P&L, overdue invoices) are answered from the database by the rules --
     no figure ever goes to a model (CEO 2026-10-15);
   - with the large brain (Claude), a tool loop: Claude is offered the tools this user may call
     (flash_brain.tools) and every answer comes from them;
   - without it (or when it fails or refuses), the rules and the small-model router pick one
     known intent (flash_service.answer_internal_query). "Create a job" opens the job_intake
     workflow, which asks for each missing detail.
4. When the brain tier differs from the one this conversation last ran on, the reply starts
   with the offline note once.
5. The reply is stored and the turn committed.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.flash_conversation import FlashConversation, FlashMessage
from app.models.user import Users
from app.services import flash_conversation_service as conversations
from app.services.flash_brain.llm import BrainUnavailable, Brains
from app.services.flash_brain.tools import ToolContext, execute, tools_for
from app.services.flash_brain.workflows import WORKFLOWS, open_workflow, step_workflow

logger = logging.getLogger(__name__)

FLASH_SYSTEM = (
    "You are Flash, BlitzenX's internal staffing assistant. Answer only from the tools: never invent a "
    "candidate, job, client, number or status. Call the tools you need, then reply in a few plain "
    "sentences. To create a job, call search_clients and update_job_draft with the details given and ask "
    "only for what its result says is missing; create_client and create_job run only after the user said "
    "yes to the exact question update_job_draft gave you. You never record interview verdicts, reject or "
    "hire candidates, approve offers or submit candidates to clients: people decide those, and "
    "pending_decisions lists what waits for this user. Financial figures are not available to you: tell "
    "the user to ask Flash for the P&L or overdue invoices directly. If no tool fits, say what you can help "
    "with.")


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


def _tool_reply(trace: List[Dict]) -> Optional[str]:
    """What the tools that already ran said (Claude stopped before writing its reply)."""
    texts = [step["outcome"].get("error") or step["outcome"].get("text") for step in trace]
    texts = [t for t in texts if t]
    return texts[-1] if texts else None


def _agent_answer(db: Session, user: Users, conversation: FlashConversation, text: str, brains: Brains,
                  earlier: List[Dict], now: datetime):
    """(answer or None, brains): the Claude tool loop; None means "fall back to the rules"."""
    tool_ctx = ToolContext(db, user, conversation, now, brains=brains)
    try:
        result = brains.large.run_tools(system=FLASH_SYSTEM, history=earlier, user_message=text,
                                        tools=tools_for(db, user),
                                        execute=lambda name, args: execute(tool_ctx, name, args),
                                        tenant_id=user.tenant_id, purpose="agent")
    except BrainUnavailable as exc:
        logger.warning(f"[Flash] Claude unavailable, answering from the rules: {exc}")
        reply = _tool_reply(tool_ctx.trace)
        brains = brains.without("large", str(exc))
        return ({"reply": reply, "intent": "agent"} if reply else None), brains
    if result.refused or not result.text:
        reply = _tool_reply(tool_ctx.trace)
        brains = brains.without("large", f"Claude stopped ({result.stop_reason})")
        return ({"reply": reply, "intent": "agent"} if reply else None), brains
    created = [s["outcome"] for s in tool_ctx.trace if s["name"] == "create_job" and "job_id" in s["outcome"]]
    return {"reply": result.text, "intent": "agent", "job_id": created[-1]["job_id"] if created else None,
            "mission_id": created[-1].get("mission_id") if created else None}, brains


def _answer(db: Session, user: Users, conversation: FlashConversation, text: str, brains: Brains,
            earlier: List[Dict], now: datetime):
    from app.services.flash_service import (
        INTENT_AR_AGING,
        INTENT_FINANCE_PNL,
        MAX_HISTORY_TURNS,
        answer_internal_query,
        classify_internal_query,
    )

    history = conversations.question_reply_pairs(earlier)[-MAX_HISTORY_TURNS:]
    finance = classify_internal_query(text, history=history)["intent"] in (INTENT_FINANCE_PNL, INTENT_AR_AGING)
    if brains.large is not None and not finance:
        answer, brains = _agent_answer(db, user, conversation, text, brains, earlier, now)
        if answer is not None:
            return answer, brains
    answer = answer_internal_query(db, text, current_user=user, history=history,
                                   brains=Brains(small=brains.small) if finance else brains)
    if answer.get("open_workflow"):
        result = open_workflow(db, user, conversation, answer["open_workflow"], None, brains=brains)
        if not result.get("done"):
            result = step_workflow(db, user, conversation, text, brains=brains, history=earlier, now=now)
            brains = result.get("brains") or brains
        answer = {"reply": result["reply"], "intent": answer["intent"], "job_id": result.get("job_id"),
                  "mission_id": result.get("mission_id")}
    return answer, brains


def run_turn(db: Session, user: Users, text: str, *, brains: Brains, now: Optional[datetime] = None) -> Dict:
    now = now or datetime.utcnow()
    conversation = conversations.active_conversation(db, user)
    earlier = conversations.recent_text_turns(db, conversation)
    asked = conversations.append(db, conversation, "user", text)

    kind = conversation.active_workflow
    if kind:
        result = step_workflow(db, user, conversation, text, brains=brains, history=earlier, now=now)
        answer = {"reply": result["reply"], "intent": f"workflow:{kind}", "job_id": result.get("job_id"),
                  "mission_id": result.get("mission_id")}
        uses_brains = getattr(WORKFLOWS.get(kind), "uses_brains", False)
        brains = result.get("brains") or brains
    else:
        answer, brains = _answer(db, user, conversation, text, brains, earlier, now)
        uses_brains = True
    reply = answer["reply"]
    note = status_note(conversation, brains) if uses_brains else None  # deterministic workflows: no model
    if note:
        reply = f"{note}\n\n{reply}"
    answered = conversations.append(db, conversation, "flash", reply, {"intent": answer["intent"]})
    conversations.mark_read(conversation, answered.id)
    db.commit()
    new = conversations.messages(db, conversation, after_id=asked.id - 1)
    return {"reply": reply, "intent": answer["intent"], "job_id": answer.get("job_id"),
            "mission_id": answer.get("mission_id"), "messages": [message_dict(m) for m in new],
            "active_workflow": conversation.active_workflow, "brain_status": brains.status()}
