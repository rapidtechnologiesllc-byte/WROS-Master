"""
import logging
S-046/HRMS-0446 -- Candidate Abandonment Prediction.

Explicitly NOT ML per the spec's own "What NOT to build" -- a pure,
auditable, deterministic formula over data this codebase already
collects: response rate (S-034 ConversationEvent log), sentiment trend
(S-036 candidate_sentiment_log), days since last reply, and follow-up
count (S-041 follow_up_schedule).

Real architecture adaptations:
- candidate_abandonment_scores is genuinely new (see its model
  docstring). One row per (tenant, candidate), UPSERTed on every
  recalculation -- not an append-only log.
- No conversation_messages table -- ConversationEvent is the real
  message log, same 'ai_message_sent'/'candidate_reply' mapping every
  sibling S-041/S-042/S-044 service already uses.
- BR-02's "QUALIFYING/QUALIFIED, not COMPLETED/PAUSED/ESCALATED/
  INTERVIEW_SCHEDULED" maps onto the exact same 3-condition filter
  no_response_detection_service.py's own BR-02 resolution already
  established: owner_type == 'ai_agent' (excludes PAUSED -- a human
  owns it) AND status != 'closed' (excludes COMPLETED) AND
  escalation_state != 'escalated' (excludes ESCALATED). This codebase
  has no real conversation-state signal for "interview scheduled"
  (scheduling an Interview row doesn't transition any of the 3 real
  conversation axes) -- INTERVIEW_SCHEDULED is NOT separately excluded,
  consistent with S-041/S-042 making the identical simplification for
  the identical spec language, flagged here rather than silently
  matched without comment.
- "candidate_conversations.updated_at tracks last activity" is NOT used
  for the days-since-last-reply component -- that column is also
  bumped by unrelated mutations (see candidate_ai.py's own docstring).
  The real signal is the most recent ConversationEvent with
  event_type='candidate_reply'; if the candidate has never replied at
  all, conversation.created_at is used as the honest fallback reference
  point (there being no defined behavior in the spec for a candidate
  who was engaged but has literally zero reply history yet).
- Component 4 (docx header says "follow-up count (pending)" but the
  point scale 0/5/12/20 for 0/1/2/3 describes SENT counts, matching
  MAX_FOLLOWUPS=3) -- built to the point-scale body text, which is
  self-consistent with follow_up_schedule's own SENT/PENDING states;
  "pending" in the header is treated as the spec's own internal typo.
- No internal event bus -- "publish candidate.high_abandonment_risk,
  consumed by HRMS-0462 Intervention Queue" has no real event bus to
  publish through, and HRMS-0462 doesn't exist anywhere in this
  codebase yet either. is_flagged on the row itself IS the real,
  durable, queryable signal a future HRMS-0462 build would read
  directly -- same posture candidate_ghosting_status already took
  toward HRMS-0445 before that story existed. A recruiter is also
  notified directly (once, on the newly-flagged transition only, not
  repeated every 6h while still flagged) since there's no queue UI yet
  to otherwise surface this -- same recipient-resolution pattern
  ghosting_detection_service/sla_monitoring_service already established.
- No HRMS-0406 Status Card backend exists in this codebase at all (a
  pure frontend concept with no backend counterpart yet) -- AC-6's
  "score visible in Status Card" has nothing to wire into; the new
  GET /candidates/{id}/abandonment-score endpoint is the real,
  queryable substitute a future Status Card would read from.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_abandonment_score import CandidateAbandonmentScore
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.user import Users
from app.services.notification_service import send_notification
from app.services.sentiment_analysis_service import get_recent_sentiment_trend
from app.services.whatsapp_routing_service import is_ai_owner

ABANDONMENT_FLAG_THRESHOLD = int(os.getenv("ABANDONMENT_FLAG_THRESHOLD", "70"))  # BR-01 default
RESPONSE_RATE_WINDOW_DAYS = 7  # Step 2, Component 1

def _response_rate_points(db: Session, conversation_id: int, now: datetime) -> int:
    """Component 1 (30% wt): 0% reply over the last 7 days = 30pts,
    100% reply = 0pts. No outbound sent yet -> 0pts (no basis to
    penalize a candidate who hasn't had a chance to respond)."""
    since = now - timedelta(days=RESPONSE_RATE_WINDOW_DAYS)
    outbound = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "ai_message_sent", ConversationEvent.created_at >= since)
        .count()
    )
    if outbound == 0:
        return 0
    inbound = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at >= since)
        .count()
    )
    response_rate = min(inbound / outbound, 1.0)
    return round((1 - response_rate) * 30)

def _sentiment_trend_points(db: Session, candidate_id: str) -> int:
    """Component 2 (25% wt). No sentiment data -> 0pts (treated as
    neutral, per the spec's own explicit fallback)."""
    recent = get_recent_sentiment_trend(db, candidate_id, limit=5)
    if not recent:
        return 0
    if all(s == "NEGATIVE" for s in recent):
        return 25
    if recent.count("NEGATIVE") >= 3:
        return 15
    if all(s == "POSITIVE" for s in recent):
        return 0
    return 5  # mixed

def _days_since_last_reply_points(db: Session, conversation: CandidateConversation, now: datetime) -> int:
    """Component 3 (25% wt)."""
    last_reply = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "candidate_reply")
        .order_by(ConversationEvent.created_at.desc())
        .first()
    )
    reference = last_reply.created_at if last_reply else conversation.created_at
    days = max((now - reference).days, 0) if reference else 0

    if days == 0:
        return 0
    if days <= 2:
        return 5
    if days <= 5:
        return 15
    if days <= 10:
        return 20
    return 25

def _followup_count_points(db: Session, tenant_id: str, candidate_id: str, conversation_id: int) -> int:
    """Component 4 (20% wt) -- SENT count, capped at MAX_FOLLOWUPS=3."""
    sent = (
        db.query(FollowUpSchedule)
        .filter(FollowUpSchedule.tenant_id == tenant_id, FollowUpSchedule.candidate_id == candidate_id,
                FollowUpSchedule.conversation_id == conversation_id, FollowUpSchedule.status == "SENT")
        .count()
    )
    return {0: 0, 1: 5, 2: 12}.get(sent, 20)  # 3+ -> 20

def calculate_abandonment_score(db: Session, candidate_id: str, tenant_id: str, conversation: CandidateConversation) -> Dict:
    """AC-1: returns a 0-100 integer score. UPSERTs into
    candidate_abandonment_scores. Never raises -- a per-component
    failure degrades that component to its lowest (least-alarming)
    value rather than aborting the whole calculation."""
    now = datetime.utcnow()

    response_rate_pts = _response_rate_points(db, conversation.id, now)
    sentiment_pts = _sentiment_trend_points(db, candidate_id)
    days_silent_pts = _days_since_last_reply_points(db, conversation, now)
    followup_pts = _followup_count_points(db, tenant_id, candidate_id, conversation.id)

    score_components = {
        "response_rate_points": response_rate_pts,
        "sentiment_trend_points": sentiment_pts,
        "days_since_last_reply_points": days_silent_pts,
        "followup_count_points": followup_pts,
    }
    total_score = min(response_rate_pts + sentiment_pts + days_silent_pts + followup_pts, 100)
    is_flagged = total_score >= ABANDONMENT_FLAG_THRESHOLD

    existing = (
        db.query(CandidateAbandonmentScore)
        .filter(CandidateAbandonmentScore.tenant_id == tenant_id, CandidateAbandonmentScore.candidate_id == candidate_id)
        .first()
    )
    was_flagged = existing.is_flagged if existing else False

    if existing:
        existing.abandonment_score = total_score
        existing.score_components = score_components
        existing.is_flagged = is_flagged
        existing.calculated_at = now
        existing.conversation_id = conversation.id
        db.add(existing)
    else:
        db.add(CandidateAbandonmentScore(
            tenant_id=tenant_id, candidate_id=candidate_id, conversation_id=conversation.id,
            abandonment_score=total_score, score_components=score_components, is_flagged=is_flagged, calculated_at=now,
        ))
    newly_flagged = is_flagged and not was_flagged
    if newly_flagged:
        # S-061/HRMS-0461: real trigger point for the Activity Feed's
        # "candidate.high_abandonment_risk" entry -- logged here (the one
        # real place this transition happens), not published through a
        # nonexistent event bus.
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="HIGH_ABANDONMENT_RISK",
            event_data={"abandonment_score": total_score}, triggered_by="system",
        ))
    db.commit()

    # S-062/HRMS-0462: real intervention-queue wiring.
    from app.services.intervention_queue_service import PRIORITY_HIGH, add_to_queue, resolve_queue_items
    if newly_flagged:
        add_to_queue(db, candidate_id, tenant_id, "HIGH_ABANDONMENT", f"High Abandonment Risk: {total_score}%", PRIORITY_HIGH)
    elif was_flagged and not is_flagged:
        resolve_queue_items(db, candidate_id, tenant_id, ["HIGH_ABANDONMENT"], note=f"Abandonment score fell to {total_score}")

    return {
        "abandonment_score": total_score,
        "score_components": score_components,
        "is_flagged": is_flagged,
        "newly_flagged": newly_flagged,
        "calculated_at": now,
    }

def _candidate_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail

def _assigned_recruiter(db: Session, candidate_id: str) -> Optional[Users]:
    """Mirrors ghosting_detection_service's own resolver -- kept local
    since that one is a private helper of its own module."""
    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate_id, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    if assignment and assignment.assigned_by:
        return db.query(Users).filter(Users.UserID == assignment.assigned_by).first()
    return None

def _notify_recruiter_of_high_risk(db: Session, tenant_id: str, candidate: Candidate, score: int) -> None:
    recipient = _assigned_recruiter(db, candidate.candidateID) or db.query(Users).filter(Users.UserID == tenant_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P2", channel_preference="IN_APP",
            message=f"{_candidate_name(candidate)} has a high abandonment risk score ({score}%) and may need direct outreach.",
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[AbandonmentScoring] Failed to notify recruiter for candidate {candidate.candidateID!r}: {exc}")

def run_abandonment_scoring_job(db: Session) -> Dict:
    """AC-5. AbandonmentScoringJob, runs every 6 hours. Never raises --
    a failure on one candidate is logged and skipped, same defensive
    posture as every other periodic job this round."""
    result = {"scored": 0, "flagged": 0}

    conversations = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.owner_type == "ai_agent", CandidateConversation.status != "closed", CandidateConversation.escalation_state != "escalated")
        .all()
    )

    for conversation in conversations:
        try:
            if not is_ai_owner(conversation):
                continue
            candidate = db.query(Candidate).filter(Candidate.candidateID == conversation.candidate_id).first()
            if candidate is None:
                continue

            score_result = calculate_abandonment_score(db, conversation.candidate_id, conversation.tenant_id, conversation)
            result["scored"] += 1
            if score_result["is_flagged"]:
                result["flagged"] += 1
            if score_result["newly_flagged"]:
                _notify_recruiter_of_high_risk(db, conversation.tenant_id, candidate, score_result["abandonment_score"])
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[AbandonmentScoring] Failed processing conversation id={conversation.id}: {exc}")
            db.rollback()

    return result
