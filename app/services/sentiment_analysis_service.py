"""
S-036/HRMS-0436 -- Candidate Sentiment Analysis.

Real architecture adaptations:
- callLLM()/getContextForPrompt() are S-031/S-032's already-real
  prompt_framework_service.call_llm() and
  candidate_context_service.build_candidate_context(). Real LLM is
  Gemini, not the spec's Anthropic claude-sonnet-4-6 -- same adaptation
  every LLM-calling story this round has made.
- SENTIMENT_ANALYSIS's user_prompt_template is "Message:
  {{conversation_history}}" (same S-031-era placeholder hack
  INTENT_DETECTION uses) -- analyze_sentiment() overrides
  candidate_context's recent_messages to just the single message being
  classified, matching the spec's own analyzeSentiment(message_body)
  signature (a single message, not the last N).
- BR-01/BR-03: LLM failure or an invalid/unknown sentiment value both
  collapse to {sentiment: "NEUTRAL", confidence: 0.0} -- this function
  never raises to its caller.
- candidate_sentiment_log (app.models.candidate_sentiment_log) is a
  real, new, queryable table -- the spec's "publish
  candidate.sentiment_recorded / candidate.negative_sentiment_trend"
  events don't map onto anything real (no event bus exists anywhere in
  this codebase). candidate.sentiment_recorded has no real consumer
  (no EPIC-12 sentiment dashboard exists) -- not built, same honest-
  omission posture as detect_intent_service's NOT_BUILT/NOT_WIRED
  routing entries. candidate.negative_sentiment_trend DOES have a real
  consumer -- S-035's escalation_detection_service.check_escalation()
  Rule #3 -- wired as a direct DB read of the last 3
  candidate_sentiment_log rows (get_recent_sentiment_trend()), not a
  fabricated event/listener pair.
- BR-01's "asynchronous, never blocks Thunder's response" is honored
  by calling analyze_sentiment() via FastAPI's BackgroundTasks from the
  one live inbound path (public_chat_service.send_public_chat_message()),
  the same real mechanism already used elsewhere in this codebase
  (whatsapp_webhook.py, create_job.py, onboarding.py) -- not a fake
  "async" that actually still runs inline before the response.
"""
import json
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate_sentiment_log import SENTIMENT_VALUES, CandidateSentimentLog
from app.services import candidate_context_service, prompt_framework_service

NEUTRAL_RESULT = {"sentiment": "NEUTRAL", "confidence": 0.0}

# BR-02: 3 consecutive NEGATIVE rows -> escalation trigger (HRMS-0435 Rule #3).
NEGATIVE_TREND_THRESHOLD = 3


def analyze_sentiment(
    db: Session, tenant_id: str, candidate_id: str, message_body: str, *,
    conversation_id: Optional[int] = None, message_event_id: Optional[int] = None,
    llm_call: Optional[Callable[[str, str, int, float], str]] = None,
) -> Dict:
    """
    Step 1-2. Returns {sentiment, confidence, raw_response}. Always
    persists a CandidateSentimentLog row -- success or failure -- so
    the trend check (Step 3) always has a complete picture.
    BR-01/BR-03: never raises -- any failure resolves to the NEUTRAL
    default.
    """
    try:
        context = candidate_context_service.build_candidate_context(db, candidate_id, tenant_id)
        context["recent_messages"] = [{"sender": "Candidate", "body": message_body}]

        prompt = prompt_framework_service.build_prompt("SENTIMENT_ANALYSIS", {
            "thunder_name": context["thunder"]["name"], "name": context["candidate"]["name"],
            "memory": {}, "recent_messages": context["recent_messages"], "missing_fields": [],
        })
        response = prompt_framework_service.call_llm(
            db, tenant_id, candidate_id, "SENTIMENT_ANALYSIS", prompt["template_version"],
            prompt["system_prompt"], prompt["user_prompt"], prompt["max_tokens"], prompt["temperature"],
            llm_call=llm_call,
        )
        parsed = json.loads(response)
        sentiment = parsed.get("sentiment")
        confidence = float(parsed.get("confidence", 0.0))
        if sentiment not in SENTIMENT_VALUES:
            sentiment, confidence = NEUTRAL_RESULT["sentiment"], NEUTRAL_RESULT["confidence"]
        confidence = max(0.0, min(1.0, confidence))
    except Exception as exc:
        logger.warning(f"[Sentiment] SENTIMENT_LLM_FAILED for candidate {candidate_id!r}: {exc}")
        sentiment, confidence, response = NEUTRAL_RESULT["sentiment"], NEUTRAL_RESULT["confidence"], None

    db.add(CandidateSentimentLog(
        tenant_id=tenant_id, candidate_id=candidate_id, conversation_id=conversation_id,
        message_event_id=message_event_id, sentiment=sentiment, confidence=confidence,
    ))
    db.commit()

    # S-347/HRMS-P117 -- every sentiment score is a desire signal.
    # Fire-and-forget, never raises.
    from app.services.desire_signal_service import record_sentiment_signal
    record_sentiment_signal(db, tenant_id, candidate_id, sentiment, confidence, message_event_id)

    return {"sentiment": sentiment, "confidence": confidence, "raw_response": response}


def get_recent_sentiment_trend(db: Session, candidate_id: str, *, limit: int = 5) -> List[str]:
    """Step 3's trend-check input -- last `limit` sentiments for this
    candidate, most recent first."""
    rows = (
        db.query(CandidateSentimentLog)
        .filter(CandidateSentimentLog.candidate_id == candidate_id)
        .order_by(CandidateSentimentLog.analyzed_at.desc(), CandidateSentimentLog.id.desc())
        .limit(limit)
        .all()
    )
    return [row.sentiment for row in rows]


def has_negative_sentiment_trend(db: Session, candidate_id: str) -> bool:
    """BR-02: the last NEGATIVE_TREND_THRESHOLD sentiments are all
    NEGATIVE. Used directly by escalation_detection_service's Rule #3 --
    a plain DB read, not a fabricated candidate.negative_sentiment_trend
    event (no event bus exists in this codebase)."""
    recent = get_recent_sentiment_trend(db, candidate_id, limit=NEGATIVE_TREND_THRESHOLD)
    if len(recent) < NEGATIVE_TREND_THRESHOLD:
        return False
    return all(s == "NEGATIVE" for s in recent)
