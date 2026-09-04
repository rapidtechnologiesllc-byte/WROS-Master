"""
S-348/HRMS-P118 -- Desire Profile Builder.

Aggregates S-347's raw candidate_desire_signals into one ranked,
narrative-summarized profile per candidate. Depends on
candidate_desire_signals.processed=True rows only -- a signal still
awaiting the SignalProcessingJob (or a deterministically-scored
OBJECTION/RESPONSE_SPEED row, also processed=True at insert time)
contributes once it's processed, never before.

Real architecture notes:
- desire_ranking only ranks TOWARDS-direction, categorized signals --
  AWAY_FROM signals feed the separate primary_fear calculation instead
  (BR: "AWAY_FROM signals contribute to fears", the spec's own words).
- engagement_level's HOT/WARM/COOL/COLD thresholds (<2h/2-12h/12-48h/>48h)
  are the spec's own literal cutoffs, computed from RESPONSE_SPEED
  signals' raw signal_data.minutes -- a DIFFERENT bucketing than
  desire_signal_service.record_response_speed_signal()'s own
  <30min/30min-48h/>48h desire_strength tiers (that formula scores
  strength for the desire-ranking calc; this one buckets literal
  average response time for engagement display). Not a duplicate rule
  by accident -- two different real questions asked of the same raw data.
"""
import json
import os
import re
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_desire_profile import CandidateDesireProfile
from app.models.candidate_desire_signal import CandidateDesireSignal

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

COMPETING_OFFER_KEYWORDS = ("other offer", "another company", "counter offer", "considering other options")

DESIRE_CATEGORIES = (
    "CAREER_GROWTH", "COMPENSATION", "STABILITY", "REMOTE_FLEXIBILITY",
    "DOMAIN_INTEREST", "COMPANY_REPUTATION", "WORK_LIFE_BALANCE", "SPEED_OF_DECISION",
)


def _recency_weight(created_at: datetime, *, now: datetime) -> float:
    """BR-01: last 7 days *1.5, last 30 days *1.0, older *0.5."""
    age_days = (now - created_at).days
    if age_days <= 7:
        return 1.5
    if age_days <= 30:
        return 1.0
    return 0.5


def _weighted_category_scores(signals: List[CandidateDesireSignal], direction: str, *, now: datetime) -> Dict[str, Dict]:
    buckets: Dict[str, Dict] = {}
    for signal in signals:
        if signal.desire_category not in DESIRE_CATEGORIES or signal.desire_direction != direction or signal.desire_strength is None:
            continue
        weight = _recency_weight(signal.created_at, now=now)
        bucket = buckets.setdefault(signal.desire_category, {"weighted_sum": 0.0, "weight_total": 0.0, "count": 0})
        bucket["weighted_sum"] += signal.desire_strength * weight
        bucket["weight_total"] += weight
        bucket["count"] += 1
    return {
        category: {
            "score": round(b["weighted_sum"] / b["weight_total"], 3) if b["weight_total"] else 0.0,
            "signal_count": b["count"],
        }
        for category, b in buckets.items()
    }


def _engagement_level(response_speed_signals: List[CandidateDesireSignal]) -> Optional[str]:
    minutes = [s.signal_data.get("minutes") for s in response_speed_signals if isinstance(s.signal_data, dict) and s.signal_data.get("minutes") is not None]
    if not minutes:
        return None
    avg = sum(minutes) / len(minutes)
    if avg < 120:
        return "HOT"
    if avg <= 720:
        return "WARM"
    if avg <= 2880:
        return "COOL"
    return "COLD"


def _has_competing_offer(message_signals: List[CandidateDesireSignal]) -> bool:
    for signal in message_signals:
        body = (signal.signal_data or {}).get("message_body", "") if isinstance(signal.signal_data, dict) else ""
        if any(keyword in body.lower() for keyword in COMPETING_OFFER_KEYWORDS):
            return True
    return False


def _decision_urgency(response_speed_signals: List[CandidateDesireSignal], has_competing_offer: bool) -> str:
    """BR-02: has_competing_offer always wins, regardless of trend."""
    if has_competing_offer:
        return "URGENT"

    ordered = sorted(
        (s for s in response_speed_signals if isinstance(s.signal_data, dict) and s.signal_data.get("minutes") is not None),
        key=lambda s: s.created_at,
    )
    if len(ordered) < 4:
        return "NORMAL"  # not enough data for a real trend read

    midpoint = len(ordered) // 2
    earlier = ordered[:midpoint]
    later = ordered[midpoint:]
    earlier_avg = sum(s.signal_data["minutes"] for s in earlier) / len(earlier)
    later_avg = sum(s.signal_data["minutes"] for s in later) / len(later)

    if later_avg < earlier_avg * 0.8:  # responding meaningfully faster over time
        return "URGENT"
    if later_avg > earlier_avg * 1.2:  # responding meaningfully slower over time
        return "SLOW"
    return "NORMAL"


def build_desire_profile(db: Session, tenant_id: str, candidate_id: str, *, now: Optional[datetime] = None) -> CandidateDesireProfile:
    now = now or datetime.utcnow()

    signals = (
        db.query(CandidateDesireSignal)
        .filter(CandidateDesireSignal.candidate_id == candidate_id, CandidateDesireSignal.processed.is_(True))
        .all()
    )

    towards_scores = _weighted_category_scores(signals, "TOWARDS", now=now)
    away_scores = _weighted_category_scores(signals, "AWAY_FROM", now=now)

    desire_ranking = sorted(
        [
            {"category": category, "score": data["score"], "signal_count": data["signal_count"], "direction": "TOWARDS"}
            for category, data in towards_scores.items()
        ],
        key=lambda item: item["score"], reverse=True,
    )
    top = desire_ranking[0] if desire_ranking else None

    fear_ranking = sorted(away_scores.items(), key=lambda item: item[1]["score"], reverse=True)
    primary_fear, primary_fear_score = (fear_ranking[0][0], fear_ranking[0][1]["score"]) if fear_ranking else (None, None)

    message_signals = [s for s in signals if s.signal_source in ("CHAT_MESSAGE", "WHATSAPP_MESSAGE", "EMAIL_MESSAGE")]
    response_speed_signals = [s for s in signals if s.signal_source == "RESPONSE_SPEED"]

    engagement_level = _engagement_level(response_speed_signals)
    has_competing_offer = _has_competing_offer(message_signals)
    decision_urgency = _decision_urgency(response_speed_signals, has_competing_offer)

    profile = db.query(CandidateDesireProfile).filter(CandidateDesireProfile.candidate_id == candidate_id).first()
    was_competing_offer = bool(profile.has_competing_offer) if profile else False
    previous_top_category = profile.top_desire_category if profile else None
    previous_engagement_level = profile.engagement_level if profile else None

    if profile is None:
        profile = CandidateDesireProfile(tenant_id=tenant_id, candidate_id=candidate_id)

    profile.top_desire_category = top["category"] if top else None
    profile.top_desire_score = top["score"] if top else None
    profile.desire_ranking = desire_ranking
    profile.primary_fear = primary_fear
    profile.primary_fear_score = primary_fear_score
    profile.engagement_level = engagement_level
    profile.has_competing_offer = has_competing_offer
    profile.decision_urgency = decision_urgency
    profile.profile_updated_at = now

    db.add(profile)
    db.commit()
    db.refresh(profile)

    # S-348 Step 4 -- real event publishing via S-078's EventEmitter.
    # Never blocks/raises the profile build itself over an event bug.
    try:
        from app.services.event_emitter_service import emit
        emit(db, "candidate.desire_profile_updated", {"top_desire_category": profile.top_desire_category, "engagement_level": profile.engagement_level}, tenant_id, candidate_id)
        if profile.top_desire_category and profile.top_desire_category != previous_top_category:
            emit(db, "candidate.desire_shift_detected", {"from": previous_top_category, "to": profile.top_desire_category}, tenant_id, candidate_id)
        if has_competing_offer and not was_competing_offer:
            emit(db, "candidate.competing_offer_detected", {"candidate_id": candidate_id, "urgency": "URGENT"}, tenant_id, candidate_id)
        # S-349/HRMS-P119's COOLING_ENGAGEMENT trigger consumes this --
        # only fires on the real HOT/WARM -> COOL transition, not every
        # rebuild that happens to still read COOL.
        if previous_engagement_level in ("HOT", "WARM") and engagement_level == "COOL":
            emit(db, "candidate.engagement_cooled", {"from": previous_engagement_level, "to": "COOL"}, tenant_id, candidate_id)
    except Exception as exc:
        logger.warning(f"[DesireProfile] Event emission failed for candidate {candidate_id!r}: {exc}")

    return profile


# ---------------------------------------------------------------------------
# Narrative summary (LLM)
# ---------------------------------------------------------------------------

def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 500}},
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


def generate_desire_narrative(db: Session, profile: CandidateDesireProfile, *, llm_call: Optional[Callable[[str], str]] = None) -> Optional[str]:
    """Never raises -- a narrative failure must not block the (already
    committed) profile build. Returns None on failure; caller decides
    whether to leave narrative_summary as its previous value."""
    memory_summary = ""
    try:
        from app.services.candidate_memory_service import get_memory
        memory = get_memory(db, profile.candidate_id, profile.tenant_id)
        memory_summary = (memory or {}).get("summary") or ""
    except Exception:
        pass

    prompt = (
        "You are a senior talent psychologist. Based on the desire profile below, write a "
        "3-paragraph candidate motivation briefing for the HR team. Paragraph 1: What this "
        "candidate wants most and WHY they would say yes to BlitzenX. Paragraph 2: What this "
        "candidate fears or is uncertain about -- and how to address it. Paragraph 3: Your "
        "recommended approach for the HR team to close this candidate -- specific actions, "
        f"specific talking points, specific timing.\n\nDesire Profile: {json.dumps(profile.desire_ranking or [])}\n"
        f"Engagement Level: {profile.engagement_level}\nPrimary Fear: {profile.primary_fear}\n"
        f"Has competing offer: {profile.has_competing_offer}\nCandidate memory: {memory_summary}\n\n"
        "Be specific, actionable, and write as if briefing a senior recruiter."
    )
    try:
        narrative = _call_llm(prompt, llm_call)
        return narrative.strip() or None
    except Exception as exc:
        logger.warning(f"[DesireProfile] Narrative generation failed for candidate {profile.candidate_id!r}: {exc}")
        return None


def generate_talking_points(db: Session, profile: CandidateDesireProfile, *, llm_call: Optional[Callable[[str], str]] = None) -> Optional[List[str]]:
    """S-350 Step 4 -- 3-5 bullet points for HR's next conversation,
    grounded in the same content library S-349's motivation engine
    uses (BR-03: library facts only, never fabricated). Never raises;
    returns None on failure so the caller can leave the previous
    talking_points value untouched rather than clearing real content."""
    if not profile.top_desire_category:
        return None

    try:
        from app.services.motivation_engine_service import get_content_items
        library_items = get_content_items(db, profile.tenant_id, profile.top_desire_category)
    except Exception:
        library_items = []

    prompt = (
        "You are briefing a BlitzenX recruiter before their next conversation with a candidate. "
        f"Top desire: {profile.top_desire_category} (score {profile.top_desire_score}). "
        f"Primary fear: {profile.primary_fear}. Has competing offer: {profile.has_competing_offer}. "
        f"Approved facts for {profile.top_desire_category}: {json.dumps(library_items)}. "
        "Write 3-5 short, specific, actionable talking points for this conversation. Each point is one "
        "sentence, prefixed with either '✓ Lead with:' (something to proactively raise, grounded in an "
        "approved fact) or '⚠ Address:' (a concern to preempt). Use ONLY the approved facts above -- "
        "never invent statistics or promises. "
        'Return ONLY valid JSON: {"talking_points": ["...", "..."]}'
    )
    try:
        raw = _call_llm(prompt, llm_call)
        parsed = json.loads(raw)
        points = parsed.get("talking_points")
        if not isinstance(points, list) or not points:
            return None
        return [str(p).strip() for p in points if str(p).strip()][:5]
    except Exception as exc:
        logger.warning(f"[DesireProfile] Talking points generation failed for candidate {profile.candidate_id!r}: {exc}")
        return None


def build_and_narrate(db: Session, tenant_id: str, candidate_id: str, *, llm_call: Optional[Callable[[str], str]] = None, now: Optional[datetime] = None) -> CandidateDesireProfile:
    profile = build_desire_profile(db, tenant_id, candidate_id, now=now)
    narrative = generate_desire_narrative(db, profile, llm_call=llm_call)
    talking_points = generate_talking_points(db, profile, llm_call=llm_call)
    if narrative:
        profile.narrative_summary = narrative
        profile.narrative_updated_at = now or datetime.utcnow()
    if talking_points:
        profile.talking_points = talking_points
    if narrative or talking_points:
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# DesireProfileUpdateJob -- every 4 hours
# ---------------------------------------------------------------------------

def _candidates_with_new_signals_since_last_update(db: Session) -> List[Dict]:
    """Every candidate with a processed signal newer than their own
    profile's last update (or no profile yet). Returns [{tenant_id,
    candidate_id}, ...]."""
    signal_rows = (
        db.query(CandidateDesireSignal.tenant_id, CandidateDesireSignal.candidate_id, CandidateDesireSignal.processed_at)
        .filter(CandidateDesireSignal.processed.is_(True))
        .all()
    )
    latest_signal_at: Dict[str, datetime] = {}
    tenant_by_candidate: Dict[str, str] = {}
    for tenant_id, candidate_id, processed_at in signal_rows:
        if processed_at is None:
            continue
        tenant_by_candidate[candidate_id] = tenant_id
        if candidate_id not in latest_signal_at or processed_at > latest_signal_at[candidate_id]:
            latest_signal_at[candidate_id] = processed_at

    profiles = {p.candidate_id: p.profile_updated_at for p in db.query(CandidateDesireProfile).all()}

    due = []
    for candidate_id, latest_at in latest_signal_at.items():
        last_update = profiles.get(candidate_id)
        if last_update is None or latest_at > last_update:
            due.append({"tenant_id": tenant_by_candidate[candidate_id], "candidate_id": candidate_id})
    return due


def run_desire_profile_update_job(db: Session, *, llm_call: Optional[Callable[[str], str]] = None) -> Dict:
    """BR-03: max 4-hour staleness -- this job's own interval enforces
    that; each run picks up every candidate with signals newer than
    their profile's last build."""
    due = _candidates_with_new_signals_since_last_update(db)
    updated = 0
    failed = 0
    for item in due:
        try:
            build_and_narrate(db, item["tenant_id"], item["candidate_id"], llm_call=llm_call)
            updated += 1
        except Exception as exc:
            logger.warning(f"[DesireProfile] Update job failed for candidate {item['candidate_id']!r}: {exc}")
            db.rollback()
            failed += 1
    return {"updated": updated, "failed": failed, "candidates_due": len(due)}
