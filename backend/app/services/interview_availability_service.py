"""
import logging
S-047/HRMS-0447 -- Interview Availability Collection.

Real architecture adaptations:
- candidate_availability_slots is genuinely new (see its model
  docstring).
- No `INTERVIEW_SCHEDULING` conversation-state enum value / no
  `transitionState()` function exists (same fictional 10-state enum
  every prior S-041-046 story has already flagged against this
  codebase's real 3-axis model: status/escalation_state/owner_type).
  "Awaiting availability" has no dedicated state slot -- it's tracked
  the same way S-041's follow-up-schedule and S-024's missing-fields
  ask already are: a ConversationEvent audit trail
  (`availability_requested`/`availability_parsed`/etc.), not a new
  enum value bolted onto ALLOWED_STATUS_TRANSITIONS.
- No conversation_messages table -- ConversationEvent is the real
  message log, same mapping every sibling service uses.
- No internal event bus -- BR-03/AC-7's "publish
  candidate.availability_provided, consumed by HRMS-0448 (Interviewer
  Calendar Matching)" has no bus to publish through, and HRMS-0448
  does not exist anywhere in this codebase (interview_service.py's own
  docstring confirms it's not built). `AVAILABILITY_PROVIDED` is
  logged as a real ConversationEvent instead -- the honest, durable
  signal a future HRMS-0448 build would read directly, same posture
  every "downstream story doesn't exist yet" case this round has taken.
- Uses Gemini (this codebase's only real LLM), reusing
  response_parser_service.py's exact call shape (raw REST to
  gemini-2.0-flash, `llm_call` injectable for tests so no test ever
  hits a real external API) -- not the spec's Anthropic assumption.
- BR-01 "infer timezone from candidate.location" has no real
  location-capture flow to draw on (Candidate has no `location` column;
  `Candidate.timezone` exists but is just an unbackfilled
  "Asia/Kolkata" default for almost every real row, not a genuine
  inferred value -- see that column's own comment). Fallback chain,
  most-to-least reliable: (1) an explicit timezone the LLM extracted
  from the message itself, (2) a `location`-category PERSONAL fact in
  candidate_memory_facts if S-022's extraction ever captured one (using
  it as a literal timezone string only in the rare case that's what
  was actually stored, since there's no real geocoding library in this
  codebase to convert a free-text location into an IANA zone), (3)
  `Candidate.timezone` as the last, least-reliable resort. This
  weakness is deliberate and documented, not silently trusted.
- Step 4's business-hours window has an internal spec inconsistency
  (validation text says 08:00-20:00, the prescribed Thunder copy in
  Step 5 says "9 AM and 6 PM") -- built to the 08:00-20:00 validation
  text since that's what the BR/AC/TC actually enforce, not the
  conversational copy.
- BR-03's "≥2 valid slots" gate counts ALL of this candidate's stored,
  unconfirmed slots across every message they've ever sent (a slot
  from a prior message plus one new valid slot this message still
  crosses the threshold), not just slots parsed out of the current
  message -- matching the spec's own framing of an ongoing collection
  process, not a single-message quota.
- Deliberately NOT wired into process_candidate_reply()/
  public_chat_service's live reply loop this round, same posture
  S-024 (Qualification Questionnaire Engine) and
  qualification_conversation_service.run_qualification_turn() already
  took: there is no real "qualification just completed, now ask for
  availability" trigger signal anywhere in this codebase today (no
  QUALIFIED state, no interview_requested flag -- see the research
  behind this story). Forcing every post-qualification reply through
  this parser without a real, safe trigger condition would risk
  misrouting ordinary conversation as availability slots. Built and
  fully tested standalone (send_availability_request()/
  parse_availability_response() are both real, callable, ready to be
  wired in), flagged as a follow-up integration decision rather than
  guessed at unilaterally.
"""
import json
import os
import re
from datetime import date as date_cls, datetime, timezone as dt_timezone
from typing import Callable, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
from app.services.candidate_memory_service import get_memory

MIN_VALID_SLOTS = 2  # BR-03
BUSINESS_HOURS_START = 8  # Step 4 -- see module docstring on the 08:00-20:00 vs "9 AM-6 PM" spec inconsistency
BUSINESS_HOURS_END = 20
WEEKEND_WEEKDAYS = (5, 6)  # Saturday, Sunday

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

AVAILABILITY_REQUEST_MESSAGE = (
    "Great! To schedule your interview, could you share 2-3 time windows that work for you over the "
    "next week or two? Please include the day, time, and your timezone if possible -- for example, "
    "'I'm free Tuesday 2-4 PM Chicago time and Thursday morning.'"
)
NO_SLOTS_FOUND_MESSAGE = (
    "I didn't quite catch your availability. Could you share specific days and times you're free for "
    "an interview? For example: 'Tuesday afternoon and Thursday morning.'"
)
NEED_MORE_SLOTS_MESSAGE = "Thanks! Could you share at least one more time window so we have a couple of options to work with?"
PAST_DATE_REJECTION_MESSAGE = "That date has already passed -- could you share an upcoming date instead?"
WEEKEND_REJECTION_MESSAGE = "We schedule interviews on weekdays -- could you share a Monday-Friday time instead?"
OUTSIDE_HOURS_REJECTION_MESSAGE = "That time is outside our interview hours (8 AM-8 PM your time) -- could you share a different time?"


def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500}},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    if llm_call is not None:
        return llm_call(prompt)
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


def _extract_raw_slots(message_body: str, today: date_cls, llm_call: Optional[Callable[[str], str]]) -> List[Dict]:
    """AC-2/AC-3. Returns a list of {date, start_time, end_time, timezone}
    dicts (any field may be null if not mentioned). Raises on LLM/parse
    failure -- caller handles as parse_failed."""
    prompt = (
        f"Today's date is {today.isoformat()}. Extract every interview availability time window mentioned "
        "in this candidate message. Return ONLY a valid JSON array, one object per time window: "
        '[{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "timezone": "IANA timezone or null"}]. '
        'Resolve relative days ("Tuesday", "tomorrow") to an actual date on or after today. '
        'For a vague period with no explicit times, use "morning"=09:00-12:00, "afternoon"=13:00-17:00, '
        '"evening"=17:00-20:00. If no timezone is stated, use null for that field. '
        'If nothing resolvable is found, return [].\n\n'
        f"Message: {message_body}"
    )
    raw = _call_llm(prompt, llm_call)
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"LLM response was not a JSON array: {parsed!r}")
    return parsed


def _resolve_timezone(db: Session, candidate: Candidate, tenant_id: str, extracted_tz: Optional[str]) -> str:
    """BR-01 fallback chain -- see module docstring for the honest
    limitation on step (2)."""
    if extracted_tz:
        try:
            ZoneInfo(extracted_tz)
            return extracted_tz
        except (ZoneInfoNotFoundError, ValueError):
            pass

    memory = get_memory(db, candidate.candidateID, tenant_id)
    for fact in memory.get("facts", []):
        if fact.get("category") == "PERSONAL" and fact.get("key") == "location":
            candidate_value = fact.get("value")
            try:
                ZoneInfo(candidate_value)
                return candidate_value
            except (ZoneInfoNotFoundError, ValueError, TypeError):
                pass

    return candidate.timezone or "Asia/Kolkata"


def _validate_slot(slot_date: date_cls, start_time, end_time, tz_name: str) -> Optional[str]:
    """BR-02, Step 4. Returns None if valid, else a rejection reason:
    'past_date' | 'weekend' | 'outside_business_hours' | 'invalid_range'."""
    today = datetime.now(dt_timezone.utc).astimezone(ZoneInfo(tz_name)).date()
    if slot_date < today:
        return "past_date"
    if slot_date.weekday() in WEEKEND_WEEKDAYS:
        return "weekend"
    if end_time <= start_time:
        return "invalid_range"
    if start_time.hour < BUSINESS_HOURS_START or end_time.hour > BUSINESS_HOURS_END:
        return "outside_business_hours"
    return None


def _count_valid_slots(db: Session, candidate_id: str, tenant_id: str) -> int:
    return (
        db.query(CandidateAvailabilitySlot)
        .filter(CandidateAvailabilitySlot.tenant_id == tenant_id, CandidateAvailabilitySlot.candidate_id == candidate_id, CandidateAvailabilitySlot.is_confirmed == False)
        .count()
    )


def send_availability_request(db: Session, conversation: CandidateConversation) -> str:
    """Sends the initial ask (Step 3's prescribed copy). Returns the
    message body; caller is responsible for actually dispatching it via
    whichever channel-specific send path is live for this conversation."""
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="availability_requested",
        event_data={"message": AVAILABILITY_REQUEST_MESSAGE}, triggered_by="ai_agent",
    ))
    db.commit()
    return AVAILABILITY_REQUEST_MESSAGE


def parse_availability_response(
    db: Session, conversation: CandidateConversation, candidate: Candidate, tenant_id: str, message_body: str,
    *, llm_call: Optional[Callable[[str], str]] = None,
) -> Dict:
    """Never raises. Returns:
      {"outcome": "parse_failed"}
      {"outcome": "no_slots_found", "message": ...}
      {"outcome": "slots_need_more", "message": ..., "slots_stored": int, "rejections": [...]}
      {"outcome": "slots_sufficient", "message": None, "slots_stored": int, "total_valid": int, "rejections": [...]}
    """
    today = datetime.now(dt_timezone.utc).astimezone(ZoneInfo(candidate.timezone or "Asia/Kolkata")).date()

    try:
        raw_slots = _extract_raw_slots(message_body, today, llm_call)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[InterviewAvailability] Parse failed for candidate {candidate.candidateID!r}: {exc}")
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="availability_parse_failed",
            event_data={"reason": str(exc)}, triggered_by="system",
        ))
        db.commit()
        return {"outcome": "parse_failed"}

    if not raw_slots:
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="availability_clarification_requested",
            event_data={"original_message": message_body[:500]}, triggered_by="system",
        ))
        db.commit()
        return {"outcome": "no_slots_found", "message": NO_SLOTS_FOUND_MESSAGE}

    stored_count = 0
    rejections: List[str] = []

    for raw in raw_slots:
        try:
            slot_date = date_cls.fromisoformat(raw["date"])
            start_time = datetime.strptime(raw["start_time"], "%H:%M").time()
            end_time = datetime.strptime(raw["end_time"], "%H:%M").time()
        except (KeyError, TypeError, ValueError):
            rejections.append("unparseable")
            continue

        tz_name = _resolve_timezone(db, candidate, tenant_id, raw.get("timezone"))
        rejection_reason = _validate_slot(slot_date, start_time, end_time, tz_name)
        if rejection_reason:
            rejections.append(rejection_reason)
            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type=f"availability_rejected_{rejection_reason}",
                event_data={"slot_date": raw.get("date"), "start_time": raw.get("start_time")}, triggered_by="system",
            ))
            continue

        db.add(CandidateAvailabilitySlot(
            tenant_id=tenant_id, candidate_id=candidate.candidateID, conversation_id=conversation.id,
            slot_date=slot_date, slot_start_time=start_time, slot_end_time=end_time, timezone=tz_name,
        ))
        stored_count += 1

    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="availability_parsed",
        event_data={"slots_stored": stored_count, "rejections": rejections}, triggered_by="system",
    ))
    db.commit()

    total_valid = _count_valid_slots(db, candidate.candidateID, tenant_id)

    if total_valid < MIN_VALID_SLOTS:  # AC-6, BR-03
        message = NEED_MORE_SLOTS_MESSAGE
        if "past_date" in rejections:
            message = PAST_DATE_REJECTION_MESSAGE
        elif "weekend" in rejections:
            message = WEEKEND_REJECTION_MESSAGE
        elif "outside_business_hours" in rejections:
            message = OUTSIDE_HOURS_REJECTION_MESSAGE
        return {"outcome": "slots_need_more", "message": message, "slots_stored": stored_count, "rejections": rejections}

    # AC-7, BR-03 -- no event bus to publish candidate.availability_provided
    # through; this ConversationEvent IS the real, durable signal a
    # future HRMS-0448 (not built) would read directly.
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="AVAILABILITY_PROVIDED",
        event_data={"total_valid_slots": total_valid}, triggered_by="system",
    ))
    db.commit()

    return {"outcome": "slots_sufficient", "message": None, "slots_stored": stored_count, "total_valid": total_valid, "rejections": rejections}
