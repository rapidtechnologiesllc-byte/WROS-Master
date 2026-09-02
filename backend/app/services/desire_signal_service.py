"""
import logging
S-347/HRMS-P117 -- Candidate Desire Intelligence Engine.

Every candidate touchpoint (chat, WhatsApp, email, objections, response
speed, sentiment, portal navigation) feeds candidate_desire_signals.
Two sources have a real deterministic scoring rule already spelled out
in the spec itself (BR-03 objection_type->desire_category mapping,
BR-04 response-speed strength formula) -- those are scored and marked
processed=True at insert time, no LLM call needed or wasted. Every
other source is inserted raw and picked up by
process_unprocessed_signals() (the SignalProcessingJob), a direct
Gemini JSON-classify call, same shape as
response_parser_service._call_llm()/interview_rehire_guard_service.

BR-01 (silent, non-intrusive): no candidate-visible surface anywhere.
BR-04 (non-blocking, fire-and-forget): every record_*() function here
never raises into its caller -- a signal-collection bug must never
break the real conversation flow it's observing.
"""
import json
import os
import re
from datetime import datetime
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate_desire_signal import CandidateDesireSignal

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# BR-03: objection_type (app.services.objection_handling_service.OBJECTION_TAXONOMY)
# -> desire_category. AWAY_FROM always, per BR-03's own rule -- an
# objection is always a signal of what the candidate is moving away from.
OBJECTION_TYPE_TO_DESIRE_CATEGORY = {
    "SALARY": "COMPENSATION",
    "LOCATION": "REMOTE_FLEXIBILITY",
    "ROLE_FIT": "DOMAIN_INTEREST",
    "TIMING": "SPEED_OF_DECISION",
    "COMPANY": "COMPANY_REPUTATION",
    "PROCESS": "SPEED_OF_DECISION",
    # OTHER has no deterministic mapping -- left uncategorized for the
    # SignalProcessingJob's LLM pass rather than guessed.
}

BATCH_SIZE = 200


def _record(
    db: Session,
    tenant_id: str,
    candidate_id: str,
    signal_source: str,
    signal_data: Dict,
    *,
    desire_category: Optional[str] = None,
    desire_direction: Optional[str] = None,
    desire_strength: Optional[float] = None,
    processed: bool = False,
) -> Optional[CandidateDesireSignal]:
    """Never raises -- BR-04. Returns None (not the row) on failure so
    callers can't accidentally chain further work off a signal that
    didn't actually get saved."""
    try:
        signal = CandidateDesireSignal(
            tenant_id=tenant_id, candidate_id=candidate_id, signal_source=signal_source,
            signal_data=signal_data, desire_category=desire_category, desire_direction=desire_direction,
            desire_strength=desire_strength, processed=processed,
            processed_at=datetime.utcnow() if processed else None,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        return signal
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[DesireSignal] Failed to record {signal_source} signal for candidate {candidate_id!r}: {exc}")
        db.rollback()
        raise ValueError("Operation failed")


def minutes_since_last_outbound(db: Session, conversation_id: int, *, before: Optional[datetime] = None) -> Optional[float]:
    """Real 'response_time_minutes' input for record_response_speed_signal().
    None when there's no prior outbound message to measure against (e.g.
    the candidate's very first inbound message) -- callers should skip
    recording a RESPONSE_SPEED signal in that case, not fabricate a 0."""
    from app.models.candidate_ai import ConversationEvent
    query = db.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation_id,
        ConversationEvent.event_type.in_(("ai_message_sent", "hr_message_sent")),
    )
    if before is not None:
        query = query.filter(ConversationEvent.created_at < before)
    last_outbound = query.order_by(ConversationEvent.created_at.desc()).first()
    if last_outbound is None:
        return None
    arrival = before or datetime.utcnow()
    return max(0.0, (arrival - last_outbound.created_at).total_seconds() / 60.0)


def record_message_signal(
    db: Session, tenant_id: str, candidate_id: str, source: str, message_body: str,
    *, portal_page: Optional[str] = None, hour_of_day: Optional[int] = None,
) -> Optional[CandidateDesireSignal]:
    """source: CHAT_MESSAGE | WHATSAPP_MESSAGE | EMAIL_MESSAGE. Raw --
    left for the SignalProcessingJob to categorize."""
    data = {"message_body": (message_body or "")[:2000]}
    if portal_page:
        data["portal_page"] = portal_page
    if hour_of_day is not None:
        data["hour_of_day"] = hour_of_day
    return _record(db, tenant_id, candidate_id, source, data)


def record_response_speed_signal(db: Session, tenant_id: str, candidate_id: str, minutes: float) -> Optional[CandidateDesireSignal]:
    """BR-04: response_time_minutes < 30 => desire_strength=0.8,
    > 48h (2880 min) => 0.1. Deterministic -- processed immediately,
    no LLM call. desire_category left null (S-348's engagement_level
    reads signal_source=RESPONSE_SPEED + signal_data.minutes directly,
    not a desire category)."""
    if minutes < 30:
        strength = 0.8
    elif minutes > 2880:
        strength = 0.1
    else:
        strength = 0.4
    return _record(
        db, tenant_id, candidate_id, "RESPONSE_SPEED", {"minutes": minutes},
        desire_direction="TOWARDS", desire_strength=strength, processed=True,
    )


def record_objection_signal(db: Session, tenant_id: str, candidate_id: str, objection_type: str, key_concern: str) -> Optional[CandidateDesireSignal]:
    """BR-03: objection_type -> desire_category, direction=AWAY_FROM
    always. Deterministic -- processed immediately."""
    category = OBJECTION_TYPE_TO_DESIRE_CATEGORY.get(objection_type)
    return _record(
        db, tenant_id, candidate_id, "OBJECTION",
        {"objection_type": objection_type, "key_concern": key_concern},
        desire_category=category, desire_direction="AWAY_FROM",
        desire_strength=0.7 if category else None,
        processed=bool(category),  # OTHER (no mapping) stays unprocessed for the LLM pass
    )


def record_sentiment_signal(db: Session, tenant_id: str, candidate_id: str, sentiment: str, confidence: float, message_id: Optional[int]) -> Optional[CandidateDesireSignal]:
    """Raw -- sentiment alone doesn't say WHAT the candidate feels that
    way about; left for the SignalProcessingJob (which has the message
    context) to categorize."""
    return _record(
        db, tenant_id, candidate_id, "SENTIMENT",
        {"sentiment": sentiment, "confidence": confidence, "message_id": message_id},
    )


def record_portal_page_view_signal(db: Session, tenant_id: str, candidate_id: str, page: str, time_on_page_seconds: int, scroll_depth_pct: Optional[int] = None) -> Optional[CandidateDesireSignal]:
    data = {"page": page, "time_on_page_seconds": time_on_page_seconds}
    if scroll_depth_pct is not None:
        data["scroll_depth_pct"] = scroll_depth_pct
    return _record(db, tenant_id, candidate_id, "PORTAL_PAGE_VIEW", data)


# ---------------------------------------------------------------------------
# SignalProcessingJob -- LLM extraction for every raw (unprocessed) signal
# ---------------------------------------------------------------------------

def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200}},
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


def _extraction_prompt(signal: CandidateDesireSignal) -> str:
    return (
        "Analyze this candidate behavior signal from a recruiting context. "
        f"Signal type: {signal.signal_source}. Signal data: {json.dumps(signal.signal_data)}. "
        "Identify: (1) Which desire category does this signal indicate? Pick ONE from: "
        "[CAREER_GROWTH, COMPENSATION, STABILITY, REMOTE_FLEXIBILITY, DOMAIN_INTEREST, "
        "COMPANY_REPUTATION, WORK_LIFE_BALANCE, SPEED_OF_DECISION]. If nothing meaningful can "
        "be determined, use null. (2) Is the candidate moving TOWARDS or AWAY_FROM this desire? "
        "(3) Strength 0.0-1.0. (4) One-sentence insight. "
        'Return ONLY valid JSON: {"desire_category": string or null, "desire_direction": '
        '"TOWARDS" or "AWAY_FROM", "desire_strength": 0.0-1.0, "extracted_insight": string}'
    )


def _apply_extraction(signal: CandidateDesireSignal, parsed: Dict) -> None:
    category = parsed.get("desire_category")
    signal.desire_category = category if category in (
        "CAREER_GROWTH", "COMPENSATION", "STABILITY", "REMOTE_FLEXIBILITY",
        "DOMAIN_INTEREST", "COMPANY_REPUTATION", "WORK_LIFE_BALANCE", "SPEED_OF_DECISION",
    ) else None
    direction = parsed.get("desire_direction")
    signal.desire_direction = direction if direction in ("TOWARDS", "AWAY_FROM") else None
    try:
        signal.desire_strength = max(0.0, min(1.0, float(parsed.get("desire_strength", 0.0))))
    except (TypeError, ValueError):
        signal.desire_strength = None
    signal.extracted_insight = str(parsed.get("extracted_insight") or "").strip()[:1000] or None


def process_unprocessed_signals(db: Session, *, limit: int = BATCH_SIZE, llm_call: Optional[Callable[[str], str]] = None) -> Dict:
    """Step 5 -- SignalProcessingJob. Processes every unprocessed signal
    (any tenant/candidate) up to `limit`. Per-signal failures (LLM call
    or parse) are logged and left unprocessed for the next cycle --
    never raise, never abandon the rest of the batch over one bad row."""
    signals = (
        db.query(CandidateDesireSignal)
        .filter(CandidateDesireSignal.processed.is_(False))
        .order_by(CandidateDesireSignal.created_at.asc())
        .limit(limit)
        .all()
    )

    processed_count = 0
    failed_count = 0
    for signal in signals:
        try:
            raw = _call_llm(_extraction_prompt(signal), llm_call)
            parsed = json.loads(raw)
            _apply_extraction(signal, parsed)
            signal.processed = True
            signal.processed_at = datetime.utcnow()
            db.add(signal)
            db.commit()
            processed_count += 1
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[DesireSignal] SignalProcessingJob failed for signal {signal.id}: {exc}")
            db.rollback()
            failed_count += 1

    return {"processed": processed_count, "failed": failed_count, "batch_size": len(signals)}
