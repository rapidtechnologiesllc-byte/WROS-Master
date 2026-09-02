"""
import logging
S-073/HRMS-0473 -- Candidate Preference Capture Engine.

Real architecture adaptations:
- `candidate_memory_facts` (S-021) and `upsert_fact()` are real,
  already-built, and reused directly -- no new table. `PREFERENCE` is
  already a real member of `FACT_CATEGORIES`.
- BR-01 ("only after completeness=100%") reuses the same real
  `get_missing_fields()`/`TOTAL_PROFILE_FIELDS` denominator S-059/S-070
  already established -- no fictional "QUALIFIED" state check.
- Real, honest gap, not silently hidden: `qualification_conversation_
  service.run_qualification_turn()` (S-025) is this codebase's real
  qualification loop, but its own completion branch (`plan["is_complete"]`)
  immediately transitions the conversation to `status="closed"` --
  already-shipped, tested behavior this story does not change. That
  means only the FIRST preference question (Step 3's "append to the
  completion message") is wired into a live trigger point here; the
  full multi-turn preference loop (capture an answer, ask the next
  question, BR-02's 2-consecutive-non-answer stop) has no real live
  channel to run on today, since the conversation is already closed by
  the time a candidate could reply to that first question -- same
  "built for real, live multi-turn trigger doesn't exist yet" posture
  already flagged for `run_qualification_turn()` itself (per
  wros_project_status memory: it isn't wired into any live inbound
  path at all). `mark_preference_skipped()` (BR-02's "Not specified"
  default) is built and tested as a real, standalone function, ready
  for whenever that live loop exists.
- The Memory Viewer AC ("PREFERENCE facts visible") needs no new
  frontend work -- `ThunderMemorySection.js`'s `CATEGORY_LABELS`
  already includes `PREFERENCE: "Preferences"` (built generically by
  S-023, before this story existed), so any fact recorded here
  surfaces automatically.
"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.ai_conversation_service import CANDIDATE_CORE_FIELDS, INFO_FORM_FIELDS, get_missing_fields
from app.services.candidate_memory_service import get_memory, upsert_fact

TOTAL_PROFILE_FIELDS = len(CANDIDATE_CORE_FIELDS) + len(INFO_FORM_FIELDS)
NOT_SPECIFIED = "Not specified"  # BR-02

# Step 1 -- BA-approved catalog, code constants, asked in this exact order.
PREFERENCE_QUESTIONS: List[Dict[str, str]] = [
    {"preference_type": "WORK_ENVIRONMENT", "question": "Once everything is set up, are you looking for fully remote work, a hybrid arrangement, or would you prefer to be in an office environment?"},
    {"preference_type": "DOMAIN_PREFERENCE", "question": "Do you have a preference for the type of industry or domain you work in? For example, insurance, healthcare, banking, or are you open to any domain?"},
    {"preference_type": "ROLE_TYPE", "question": "Are you more interested in a hands-on technical role, or are you looking to move into a more leadership or management track?"},
    {"preference_type": "COMPANY_SIZE", "question": "Do you have a preference for the size of company you join? Larger enterprises or smaller, faster-moving teams?"},
    {"preference_type": "CAREER_GOAL", "question": "What is your primary career goal for your next role -- technical growth, leadership opportunities, stability, or something else?"},
]
PREFERENCE_TYPES = [q["preference_type"] for q in PREFERENCE_QUESTIONS]


def _profile_complete(candidate: Candidate, db: Session) -> bool:
    return len(get_missing_fields(candidate, db)) == 0


def _asked_preference_types(db: Session, candidate_id: str, tenant_id: str) -> set:
    memory = get_memory(db, candidate_id, tenant_id)
    return {f["key"] for f in memory["facts"] if f["category"] == "PREFERENCE"}


def ask_preference_question(db: Session, candidate_id: str, tenant_id: str) -> Optional[Dict]:
    """Step 2. BR-01: only once completeness=100%. Returns the next
    un-asked preference question in catalog order, or None once all 5
    have been asked."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None or not _profile_complete(candidate, db):
        return None

    asked = _asked_preference_types(db, candidate_id, tenant_id)
    for item in PREFERENCE_QUESTIONS:
        if item["preference_type"] not in asked:
            return dict(item)
    return None


def record_preference_answer(db: Session, candidate_id: str, tenant_id: str, preference_type: str, answer: str, *, confidence: float = 1.0) -> None:
    """Integrations table: stores a candidate's real preference answer,
    same real upsert_fact() every other memory-writing story uses."""
    upsert_fact(db, candidate_id, tenant_id, fact_category="PREFERENCE", fact_key=preference_type, fact_value=answer, confidence=confidence)


def mark_preference_skipped(db: Session, candidate_id: str, tenant_id: str, preference_type: str) -> None:
    """BR-02: candidate didn't answer or said 'not sure' -- record
    'Not specified' and move on, never repeat the question."""
    upsert_fact(db, candidate_id, tenant_id, fact_category="PREFERENCE", fact_key=preference_type, fact_value=NOT_SPECIFIED, confidence=1.0)


def append_preference_question_to_message(message: str, question_item: Optional[Dict]) -> str:
    """Step 3's literal wording: 'That's everything I needed! Just one
    more thing -- [preference question]', appended to the real
    qualification-completion message."""
    if question_item is None:
        return message
    return f"{message} Just one more thing -- {question_item['question']}"
