"""
import logging
S-070/HRMS-0470 -- Candidate Engagement Health Metrics.

Real architecture adaptations:
- No `conversation_messages` table -- reuses the real `ConversationEvent`
  log (`ai_message_sent`/`candidate_reply` event types, the same
  vocabulary every prior message-counting story this session has used).
- No `conversation_state_history`/fictional QUALIFIED state --
  `days_to_qualification` uses S-059's real SCREENED stage detection
  (`get_candidate_journey()`'s own docstring: SCREENED is the real
  substitute for "QUALIFIED," entered when a `CandidateJobScore` first
  exists) as the qualification marker, and the candidate's real
  `CandidateConversation.created_at` as the "first message" anchor.
- BR-01 (exclude ghost periods from response_rate) uses the real
  `CandidateGhostingStatus.ghosted_at` (S-043) -- outbound messages
  sent on/after that timestamp (until a real `reactivated_at`, if any)
  are excluded from the denominator.
- No internal event bus -- Step 3's "publish
  candidate.engagement_metrics_updated" has nothing to publish through
  (same gap this whole session has documented repeatedly); the
  upserted row itself is the real, durable signal a future HRMS-0471
  consumer would read.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_engagement_metrics import CandidateEngagementMetrics
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_sentiment_log import CandidateSentimentLog

MAX_RESPONSE_GAP_MINUTES = 7 * 24 * 60  # BR: exclude ghosting-period gaps, "< 7 days"
SENTIMENT_SCORES = {"NEGATIVE": -1, "NEUTRAL": 0, "POSITIVE": 1}


def _ghost_window(db: Session, candidate_id: str):
    """BR-01. Returns (ghosted_at, reactivated_at) or (None, None)."""
    ghosting = db.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == candidate_id).first()
    if ghosting is None:
        return None, None
    return ghosting.ghosted_at, ghosting.reactivated_at


def calculate_engagement_health(db: Session, candidate_id: str, tenant_id: str) -> Dict:
    """Step 2. Never raises -- returns {"outcome": "not_found"} if the
    candidate/conversation doesn't exist."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        conversation = (
            db.query(CandidateConversation)
            .filter(CandidateConversation.candidate_id == candidate_id)
            .order_by(CandidateConversation.id.desc())
            .first()
        )
        if candidate is None or conversation is None:
            return {"outcome": "not_found"}

        events = (
            db.query(ConversationEvent)
            .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type.in_(("ai_message_sent", "candidate_reply")))
            .order_by(ConversationEvent.created_at.asc())
            .all()
        )

        ghosted_at, reactivated_at = _ghost_window(db, candidate_id)

        def in_ghost_period(ts: datetime) -> bool:
            if ghosted_at is None or ts < ghosted_at:
                return False
            return reactivated_at is None or ts < reactivated_at

        outbound_count = 0
        inbound_count = 0
        last_inbound_at: Optional[datetime] = None
        gaps_minutes = []
        pending_outbound: Optional[datetime] = None

        for event in events:
            if event.event_type == "ai_message_sent":
                if not in_ghost_period(event.created_at):
                    outbound_count += 1
                pending_outbound = event.created_at
            elif event.event_type == "candidate_reply":
                inbound_count += 1
                last_inbound_at = event.created_at
                if pending_outbound is not None:
                    gap_minutes = (event.created_at - pending_outbound).total_seconds() / 60
                    if 0 <= gap_minutes < MAX_RESPONSE_GAP_MINUTES:
                        gaps_minutes.append(gap_minutes)
                    pending_outbound = None

        response_rate = round(min(100 * inbound_count / outbound_count, 100), 2) if outbound_count > 0 else 0
        avg_response_time_minutes = round(sum(gaps_minutes) / len(gaps_minutes)) if gaps_minutes else None
        total_messages_exchanged = len(events)

        days_to_qualification = None
        try:
            from app.services.candidate_journey_service import get_candidate_journey
            journey = get_candidate_journey(db, candidate_id, tenant_id)
            screened = next((s for s in journey["stages"] if s["stage_name"] == "SCREENED"), None)
            if screened and screened["entered_at"] and conversation.created_at:
                days_to_qualification = (screened["entered_at"] - conversation.created_at).days
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[EngagementMetrics] Could not resolve qualification stage for {candidate_id!r}: {exc}")

        sentiments = db.query(CandidateSentimentLog.sentiment).filter(CandidateSentimentLog.candidate_id == candidate_id).all()
        avg_sentiment_score = round(sum(SENTIMENT_SCORES.get(s[0], 0) for s in sentiments) / len(sentiments), 2) if sentiments else None

        existing = db.query(CandidateEngagementMetrics).filter(CandidateEngagementMetrics.tenant_id == tenant_id, CandidateEngagementMetrics.candidate_id == candidate_id).first()
        now = datetime.utcnow()
        values = dict(
            response_rate=response_rate, avg_response_time_minutes=avg_response_time_minutes,
            total_messages_exchanged=total_messages_exchanged, days_to_qualification=days_to_qualification,
            avg_sentiment_score=avg_sentiment_score, last_inbound_at=last_inbound_at, metrics_calculated_at=now,
        )
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            db.add(existing)
        else:
            db.add(CandidateEngagementMetrics(tenant_id=tenant_id, candidate_id=candidate_id, **values))
        db.commit()

        return {"outcome": "calculated", **values}
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[EngagementMetrics] Failed calculating engagement health for {candidate_id!r}: {exc}")
        db.rollback()
        return {"outcome": "calculation_failed"}


def run_engagement_metrics_job(db: Session) -> Dict:
    """Step 3. Runs every 4 hours. Never lets one bad row abort the batch."""
    result = {"processed": 0, "calculated": 0, "skipped": 0}

    conversations = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.status != "closed")
        .order_by(CandidateConversation.candidate_id, CandidateConversation.id.desc())
        .all()
    )
    seen_candidates = set()
    for conversation in conversations:
        if conversation.candidate_id in seen_candidates:
            continue
        seen_candidates.add(conversation.candidate_id)
        result["processed"] += 1
        try:
            calc = calculate_engagement_health(db, conversation.candidate_id, conversation.tenant_id)
            if calc.get("outcome") == "calculated":
                result["calculated"] += 1
            else:
                result["skipped"] += 1
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[EngagementMetrics] Failed processing candidate {conversation.candidate_id!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result
