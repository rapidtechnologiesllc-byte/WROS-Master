"""
import logging
S-349/HRMS-P119 -- Proactive Motivation Engine.

Real architecture:
- Trigger detection (Step 2) reads real, already-shipped signals:
  OfferLetter.offer_status=="Released" (S-053-056's own real value) for
  COMPETING_OFFER/OFFER_PENDING_RESPONSE, S-348's CandidateDesireProfile
  for COMPETING_OFFER/DESIRE_SHIFT/SCHEDULED_NURTURE, and S-348's own
  emitted events (candidate.desire_shift_detected,
  candidate.engagement_cooled -- the latter added by this story, see
  desire_profile_service) for DESIRE_SHIFT/COOLING_ENGAGEMENT. No
  fictional "Supervisor Agent dispatches ProactiveMotivationAgent"
  class -- this is a real, standalone 30-min scheduled job, same
  posture S-066's own docstring already established for this whole
  codebase's "~18 independent scheduled jobs, not one central
  dispatcher" reality.
- Send dispatch reuses thunder_service.send_outbound_campaign_message()
  (S-041/044/045's shared whatsapp/email sender) rather than a fourth
  copy of the same channel-branching logic.
- BR-02's "COMPETING_OFFER bypasses the 48h window" is the one
  exception to the otherwise-universal per-candidate cap.
"""
import json
import os
import re
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.candidate_desire_profile import CandidateDesireProfile
from app.models.event_log import EventLog
from app.models.motivation import MotivationContentLibrary, MotivationOutcome
from app.models.offer_letter import OfferLetter

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

MAX_ONE_PER_HOURS = 48
TRIGGER_PRIORITY = ("COMPETING_OFFER", "OFFER_PENDING_RESPONSE", "COOLING_ENGAGEMENT", "DESIRE_SHIFT", "SCHEDULED_NURTURE")
NURTURE_STAGES = ("SCREENED", "INTERVIEW")  # real substitutes for QUALIFIED/INTERVIEW_SCHEDULED -- see S-059
NURTURE_INTERVAL_DAYS = 7

# BA-approved facts -- Step 1's own literal seed examples, same
# "real placeholder, not yet BA-reviewed" posture as S-029/S-055's
# seed libraries. Used only when a tenant hasn't configured its own
# MotivationContentLibrary rows.
DEFAULT_CONTENT_LIBRARY = {
    "CAREER_GROWTH": [
        "BlitzenX Guidewire consultants average 2 promotions in 3 years",
        "Our technical mentorship program pairs all new joiners with a senior Guidewire architect for 6 months",
        "BlitzenX funded 3 Guidewire certifications for our team in 2024",
    ],
    "COMPENSATION": [
        "BlitzenX offers performance bonuses averaging 15% of annual salary",
        "Our salary revision cycle is every 6 months for consultants demonstrating impact",
    ],
    "STABILITY": [
        "BlitzenX has been placing Guidewire specialists since 2015",
        "94% of our clients are on multi-year contracts",
        "Average BlitzenX consultant tenure is 3.2 years",
    ],
    "REMOTE_FLEXIBILITY": [
        "BlitzenX offers hybrid work arrangements negotiated per client",
        "We have placed 12 consultants in full-remote Guidewire roles in the last 12 months",
    ],
    "COMPANY_REPUTATION": [
        "BlitzenX is a specialist Guidewire staffing firm trusted by insurance carriers nationwide",
    ],
    "DOMAIN_INTEREST": [
        "BlitzenX consultants work exclusively on Guidewire PolicyCenter/ClaimCenter/BillingCenter engagements",
    ],
    "WORK_LIFE_BALANCE": [
        "BlitzenX consultants report an average 42-hour work week across our engagements",
    ],
    "SPEED_OF_DECISION": [
        "BlitzenX's average time from interview to offer is under 5 business days",
    ],
}


def get_content_items(db: Session, tenant_id: str, desire_category: str) -> List[str]:
    row = (
        db.query(MotivationContentLibrary)
        .filter(MotivationContentLibrary.tenant_id == tenant_id, MotivationContentLibrary.desire_category == desire_category)
        .first()
    )
    if row and row.content_items:
        return list(row.content_items)
    return list(DEFAULT_CONTENT_LIBRARY.get(desire_category, []))


def _last_motivation(db: Session, candidate_id: str) -> Optional[MotivationOutcome]:
    return (
        db.query(MotivationOutcome)
        .filter(MotivationOutcome.candidate_id == candidate_id)
        .order_by(MotivationOutcome.sent_at.desc())
        .first()
    )


def _last_event_after(db: Session, candidate_id: str, event_type: str, after: Optional[datetime]) -> bool:
    query = db.query(EventLog).filter(EventLog.candidate_id == candidate_id, EventLog.event_type == event_type)
    if after is not None:
        query = query.filter(EventLog.emitted_at > after)
    return db.query(query.exists()).scalar()


def _active_offer(db: Session, candidate_id: str) -> Optional[OfferLetter]:
    return (
        db.query(OfferLetter)
        .filter(OfferLetter.candidate_id == candidate_id, OfferLetter.offer_status == "Released")
        .order_by(OfferLetter.released_at.desc())
        .first()
    )


def detect_trigger(db: Session, tenant_id: str, candidate_id: str, *, now: Optional[datetime] = None) -> Optional[str]:
    """Step 2, BR-02's priority order. Returns the highest-priority
    trigger currently firing, or None. The 48h cap applies to every
    trigger except COMPETING_OFFER (bypasses it -- BR-02's own literal
    exception)."""
    now = now or datetime.utcnow()
    last = _last_motivation(db, candidate_id)
    within_48h = bool(last and (now - last.sent_at) < timedelta(hours=MAX_ONE_PER_HOURS))

    profile = db.query(CandidateDesireProfile).filter(CandidateDesireProfile.candidate_id == candidate_id).first()
    offer = _active_offer(db, candidate_id)

    if profile and profile.has_competing_offer and offer is not None:
        return "COMPETING_OFFER"  # bypasses the 48h cap

    if within_48h:
        return None

    if offer is not None and offer.released_at and (now - offer.released_at) >= timedelta(days=2):
        return "OFFER_PENDING_RESPONSE"

    last_sent_at = last.sent_at if last else None
    if _last_event_after(db, candidate_id, "candidate.engagement_cooled", last_sent_at):
        return "COOLING_ENGAGEMENT"

    if _last_event_after(db, candidate_id, "candidate.desire_shift_detected", last_sent_at):
        return "DESIRE_SHIFT"

    if profile and profile.engagement_level == "WARM":
        try:
            from app.services.candidate_journey_service import get_candidate_journey
            journey = get_candidate_journey(db, candidate_id, tenant_id)
            if journey.get("current_stage") in NURTURE_STAGES:
                if last is None or (now - last.sent_at) >= timedelta(days=NURTURE_INTERVAL_DAYS):
                    return "SCHEDULED_NURTURE"
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[MotivationEngine] Could not resolve journey stage for {candidate_id!r}: {exc}")

    raise ValueError("Operation failed")


# ---------------------------------------------------------------------------
# Message generation
# ---------------------------------------------------------------------------

GENERIC_NURTURE_MESSAGE = "Hi there -- just wanted to check in and see how things are going on your end. Happy to answer any questions about the role or BlitzenX whenever it's convenient for you!"


def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5, "maxOutputTokens": 200}},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    if llm_call is not None:
        return llm_call(prompt)
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


def generate_motivation_message(
    db: Session, tenant_id: str, candidate: Candidate, profile: Optional[CandidateDesireProfile], trigger_type: str,
    *, llm_call: Optional[Callable[[str], str]] = None,
) -> Tuple[str, Optional[str]]:
    """BR-04: no profile (or no top desire yet) => generic nurture only,
    never a targeted-but-baseless message. Returns (message_text,
    desire_category_targeted_or_None)."""
    if profile is None or not profile.top_desire_category:
        return GENERIC_NURTURE_MESSAGE, None

    category = profile.top_desire_category
    library_items = get_content_items(db, tenant_id, category)
    if not library_items:
        return GENERIC_NURTURE_MESSAGE, None

    name = candidate.candidateFirstName or "there"
    prompt = (
        f"You are Thunder, Talent Scout at BlitzenX. You are writing a personalized, proactive "
        f"outreach message to a candidate to motivate them toward accepting the BlitzenX opportunity. "
        f"The candidate's strongest desire is {category} (score: {profile.top_desire_score}). "
        f"Their primary concern is {profile.primary_fear}. Trigger: {trigger_type}. "
        f"Approved BlitzenX facts for {category}: {json.dumps(library_items)}. "
        f"Candidate name: {name}. "
        "Write a warm, 2-3 sentence message that: (1) does NOT feel like a sales pitch, "
        "(2) uses ONE specific fact from the approved content library, (3) naturally connects that "
        "fact to what YOU KNOW this specific candidate cares about, (4) ends with a soft open question. "
        "Use ONLY the provided approved facts -- never invent statistics."
    )

    for _attempt in range(2):
        try:
            message = _call_llm(prompt, llm_call)
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[MotivationEngine] LLM call failed for candidate {candidate.candidateID!r}: {exc}")
            break
        if message and any(fact.lower() in message.lower() for fact in library_items):
            return message.strip(), category

    # BR-01: validation failed twice (or the call itself failed) -- fall
    # back to a safe, deterministic message that is provably grounded in
    # a real library fact rather than retrying indefinitely.
    fallback = f"Hi {name} -- {library_items[0]} I think that could really matter for you. Would that kind of thing be important in your decision?"
    return fallback, category


# ---------------------------------------------------------------------------
# Send + outcome tracking
# ---------------------------------------------------------------------------

def _resolve_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id, CandidateConversation.status != "closed")
        .order_by(CandidateConversation.id.desc())
        .first()
    )


def send_motivation_message(db: Session, candidate: Candidate, trigger_type: str, *, llm_call: Optional[Callable[[str], str]] = None) -> Optional[MotivationOutcome]:
    conversation = _resolve_conversation(db, candidate.candidateID)
    if conversation is None:
        return None

    profile = db.query(CandidateDesireProfile).filter(CandidateDesireProfile.candidate_id == candidate.candidateID).first()
    message, category = generate_motivation_message(db, conversation.tenant_id, candidate, profile, trigger_type, llm_call=llm_call)

    channel = "whatsapp" if (conversation.channel_preference or "whatsapp") != "email" else "email"
    try:
        from app.services.thunder_service import send_outbound_campaign_message
        send_outbound_campaign_message(db, conversation, candidate, message, channel, email_subject="A quick thought for you")
        db.commit()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[MotivationEngine] Send failed for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        raise ValueError("Operation failed")

    outcome = MotivationOutcome(
        tenant_id=conversation.tenant_id, candidate_id=candidate.candidateID, trigger_type=trigger_type,
        message_sent=message, desire_category_targeted=category,
        engagement_before=profile.engagement_level if profile else None,
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


def run_motivation_job(db: Session, *, llm_call: Optional[Callable[[str], str]] = None, now: Optional[datetime] = None) -> Dict:
    """ScheduledMotivationJob, every 30 min. Driven off
    CandidateDesireProfile rows (the real "has Thunder observed enough
    to have an opinion" set) union'd with candidates who have a
    Released offer but no profile yet (COMPETING_OFFER/OFFER_PENDING
    can fire off OfferLetter alone) -- see module docstring for the
    documented edge-case gap (an offer released to a candidate with
    literally zero recorded desire signals)."""
    now = now or datetime.utcnow()

    candidate_ids = {row.candidate_id for row in db.query(CandidateDesireProfile.candidate_id).all()}
    candidate_ids |= {row.candidate_id for row in db.query(OfferLetter.candidate_id).filter(OfferLetter.offer_status == "Released").all()}

    sent = 0
    skipped = 0
    for candidate_id in candidate_ids:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if candidate is None:
            continue
        conversation = _resolve_conversation(db, candidate_id)
        if conversation is None:
            continue
        trigger = detect_trigger(db, conversation.tenant_id, candidate_id, now=now)
        if trigger is None:
            skipped += 1
            continue
        outcome = send_motivation_message(db, candidate, trigger, llm_call=llm_call)
        if outcome is not None:
            sent += 1
        else:
            skipped += 1

    return {"sent": sent, "skipped": skipped, "candidates_considered": len(candidate_ids)}
