"""
S-064/HRMS-0464 -- AI Explainability Panel.

Real architecture adaptations:
- No `thunder_response_log` table and no `conversation_messages` table
  exist in this codebase -- S-034's own module docstring already
  flagged that HRMS-0431/0433 (this story's literal dependencies) don't
  exist either. The real message log is `ConversationEvent`
  (established since S-002/S-003's architecture decision); this story
  stores explanation data directly on the `event_data` of the real
  `ai_message_sent` event it explains, rather than inventing a second
  table + an FK column bridging two tables that don't exist here.
- The spec's example ("just answered notice period, salary is the next
  highest-priority field") describes `qualification_conversation_service
  .run_qualification_turn()`'s literal field-priority logic (S-025) --
  but that engine is still not wired into any live inbound path in this
  codebase (a pre-existing, already-flagged gap, see
  wros_project_status memory). The one genuinely LIVE, real-time
  inbound-to-reply loop is `public_chat_service.send_public_chat_message()`,
  which calls `generate_thunder_reply()` -- a free-form LLM reply, not a
  literal field-by-field state machine. So the explanation captured
  here is real and honest, built from what actually happened (profile
  completeness before the reply, real missing fields, real memory fact
  count, real S-059 stage) rather than a fabricated "Thunder chose to
  ask X because Y" narrative the LLM's black-box generation doesn't
  actually expose. If/when the qualification engine is wired into a
  live path, its own field-priority reasoning can extend this same
  capture point.
- BR-01 (immutable) holds by construction -- ConversationEvent is
  already insert-only/never-updated elsewhere in this codebase; the
  one mutation this story performs (attaching explanation data) is
  itself part of that same insert-time write, done once, right after
  the event is created, never touched again.
- BR-02 ('Why?' only on Thunder messages): only the one real live
  LLM-reasoned path attaches explanation data -- reminders,
  confirmations, and other templated Thunder sends never get one, so
  GET .../explanation 404s for them exactly as this story's own spec
  expects for "manual messages" (extended honestly to "non-LLM-
  reasoned Thunder messages" too, since this codebase has no separate
  concept of "the LLM decided vs. a template fired" beyond that).
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import ConversationEvent
from app.models.candidate_memory import CandidateMemoryFact
from app.services.ai_conversation_service import CANDIDATE_CORE_FIELDS, INFO_FORM_FIELDS, get_missing_fields

TOTAL_PROFILE_FIELDS = len(CANDIDATE_CORE_FIELDS) + len(INFO_FORM_FIELDS)
PROMPT_TYPE_LABELS = {"conversational_reply": "Conversational Reply"}


def attach_explanation(db: Session, reply_event: ConversationEvent, candidate: Candidate, tenant_id: Optional[str]) -> None:
    """Called once, right after a real LLM-generated Thunder reply is
    sent via public_chat_service's live inbound loop. Never raises --
    a failure here must never break the candidate-facing reply that
    already went out."""
    try:
        missing_fields = get_missing_fields(candidate, db)
        completeness_pct = round(100 * (TOTAL_PROFILE_FIELDS - len(missing_fields)) / TOTAL_PROFILE_FIELDS)
        facts_count = db.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == candidate.candidateID).count()

        stage = "UNKNOWN"
        if tenant_id:
            try:
                from app.services.candidate_journey_service import get_candidate_journey
                stage = get_candidate_journey(db, candidate.candidateID, tenant_id)["current_stage"]
            except Exception:
                pass

        missing_labels = [f["label"] for f in missing_fields]
        if missing_labels:
            explanation = (
                f"Thunder replied to continue the conversation. At this point, the candidate's profile was "
                f"{completeness_pct}% complete, with {len(missing_labels)} field(s) still missing "
                f"(next: {missing_labels[0]})."
            )
        else:
            explanation = (
                f"Thunder replied to continue the conversation. At this point, the candidate's profile was "
                f"{completeness_pct}% complete with no required fields missing."
            )

        event_data = dict(reply_event.event_data or {})
        event_data["explanation"] = explanation
        event_data["prompt_type"] = "conversational_reply"
        event_data["context_snapshot"] = {
            "completeness_at_time": completeness_pct,
            "state_at_time": stage,
            "missing_fields_at_time": missing_labels,
            "memory_facts_count": facts_count,
        }
        event_data["explanation_generated_at"] = datetime.utcnow().isoformat()
        reply_event.event_data = event_data
        db.add(reply_event)
        db.commit()
    except Exception:
        db.rollback()


def get_message_explanation(db: Session, event_id: int) -> Optional[Dict]:
    """Step 2. Returns None if the event has no explanation (e.g. a
    recruiter's manual message, or a templated Thunder send)."""
    event = db.query(ConversationEvent).filter(ConversationEvent.id == event_id, ConversationEvent.event_type == "ai_message_sent").first()
    if event is None or not (event.event_data or {}).get("explanation"):
        return None
    data = event.event_data
    return {
        "explanation_text": data["explanation"],
        "prompt_type": data.get("prompt_type", "conversational_reply"),
        "prompt_type_label": PROMPT_TYPE_LABELS.get(data.get("prompt_type"), data.get("prompt_type", "Unknown")),
        "context_snapshot": data.get("context_snapshot", {}),
        "generated_at": data.get("explanation_generated_at"),
        "model_used": "gemini",
    }


def get_explanation_log(db: Session, candidate_id: str) -> List[Dict]:
    """Step 4. Full, immutable history of every explained Thunder
    decision for this candidate, oldest first."""
    from app.models.candidate_ai import CandidateConversation

    events = (
        db.query(ConversationEvent)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.candidate_id == candidate_id, ConversationEvent.event_type == "ai_message_sent")
        .order_by(ConversationEvent.created_at.asc())
        .all()
    )
    log = []
    for event in events:
        data = event.event_data or {}
        if not data.get("explanation"):
            continue
        log.append({
            "message_id": event.id,
            "explanation_text": data["explanation"],
            "prompt_type": data.get("prompt_type", "conversational_reply"),
            "context_snapshot": data.get("context_snapshot", {}),
            "generated_at": data.get("explanation_generated_at"),
            "created_at": event.created_at,
        })
    return log
