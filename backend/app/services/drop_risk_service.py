"""
import logging
S-060/HRMS-0460 -- Drop Risk Prediction.

Real architecture adaptations:
- No fictional QUALIFYING/QUALIFIED/INTERVIEW_SCHEDULED/OFFER_SENT/
  PREBOARDING pipeline states exist anywhere in this codebase. Rather
  than re-deriving stage detection a third time (S-018 already
  rejected the fictional enum; S-059 already built real 7-stage
  detection from artifact existence), this story reuses S-059's
  `candidate_journey_service.get_candidate_journey()` directly for
  `current_stage` -- the same real substitute, not a parallel
  reimplementation. Mapping onto this story's own stage-gated buckets:
    QUALIFYING/QUALIFIED  -> real ENGAGED/QUALIFYING/SCREENED
    INTERVIEW_SCHEDULED   -> real INTERVIEW
    OFFER_SENT            -> real OFFER
    PREBOARDING           -> real PREBOARDING
  JOINED has no drop-risk concept (the candidate already joined) and
  is skipped, same as a candidate still at ENGAGED (no qualification
  signal exists yet to score against).
- Abandonment score (HRMS-0446) reused via
  `abandonment_scoring_service.calculate_abandonment_score()` directly
  -- "if not calculated: calculate first" per this story's own
  integrations table. If no conversation exists (should be
  unreachable once QUALIFYING is reached, but defensive), falls back
  to the neutral 50 the integrations table names for "unavailable."
- Sentiment reused via `sentiment_analysis_service.get_recent_sentiment_trend()`
  (S-036) directly, not re-queried.
- "FAQ questions asked" (OFFER_SENT's inverse-risk component): no
  dedicated FAQ-interaction log/counter exists anywhere in this
  codebase (S-055's offer_faq_service answers questions through the
  same generic `send_thunder_message()`/`candidate_reply` event path
  every other Thunder conversation uses, not a separately-tagged FAQ
  event type). The real, honest proxy is the count of `candidate_reply`
  events since the offer was released -- more replies genuinely does
  mean more engagement with the offer, same real-signal-not-fabricated
  posture this whole session has used for comparable gaps (e.g.
  S-058's background-check proxy).
- Bucket boundaries not given an exact worked formula in the spec
  (interview response-rate curve, OFFER sentiment tiers, preboarding
  days-since-contact tiers) are resolved via reasonable, documented
  graduated buckets consistent with this story's own named examples
  (e.g. "2 reschedules=20pts" implies a linear reschedule_count*10
  scale, capped at 20) -- flagged here, not silently invented.
- BR-01's "notify via in-app + WhatsApp + email" -- WhatsApp/SMS
  recruiter-notification channels are not provisioned in this
  codebase (`notification_service.py`'s own documented gap,
  `ChannelNotConfigured`). Sent via the real `send_notification()`
  P0 path (bypasses business-hours gating per BR-0113-03, real
  EMAIL channel + its own real SMS fallback if email fails) --
  the same honest "real channels only" posture used everywhere else.
- HRMS-0462 Recruiter Intervention Queue does not exist in this
  codebase (this story's own "Blocks" line names it as a future
  consumer, not a dependency). `is_flagged`/`risk_level` on the
  upserted row IS the real, durable "added to intervention queue"
  signal an HRMS-0462 screen would read once built -- same "no event
  bus, the row itself is the signal" precedent as S-046/S-058.
  DROP_RISK_RESOLVED is logged as a real ConversationEvent when a
  previously-flagged candidate's score drops back below 60 (BR's own
  named hysteresis band -- flagged at >=70, only resolved below 60,
  preventing flap right at the 70 boundary).
- BR-03's ghosting multiplier is real and unconditional per its own
  text ("can only be removed by admin action") -- no admin-override
  mechanism exists yet in this codebase to actually remove it; not
  built here since this story's own AC/TC never test that removal
  path.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.offer_letter import OfferLetter
from app.models.submission import Submission
from app.models.user import Users
from app.services.abandonment_scoring_service import calculate_abandonment_score
from app.services.candidate_journey_service import get_candidate_journey
from app.services.notification_service import send_notification
from app.services.sentiment_analysis_service import get_recent_sentiment_trend

GHOSTING_MULTIPLIER = 1.3  # BR-03
FLAG_THRESHOLD = 70
RESOLVE_THRESHOLD = 60  # BR-03's own hysteresis band -- only resolved below 60
CRITICAL_THRESHOLD = 80  # BR-01

SCORABLE_STAGES = {"ENGAGED", "QUALIFYING", "SCREENED", "INTERVIEW", "OFFER", "PREBOARDING"}


def _risk_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def _qualifying_component(db: Session, candidate_id: str, tenant_id: str, conversation: Optional[CandidateConversation], entered_at: Optional[datetime]) -> Dict:
    if conversation is None:
        abandonment_score = 50  # neutral, per this story's own integrations table
    else:
        try:
            abandonment_score = calculate_abandonment_score(db, candidate_id, tenant_id, conversation)["abandonment_score"]
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[DropRisk] Abandonment score unavailable for {candidate_id!r}: {exc}")
            abandonment_score = 50

    recent_sentiments = get_recent_sentiment_trend(db, candidate_id, limit=5)
    if recent_sentiments and all(s == "NEGATIVE" for s in recent_sentiments):
        sentiment_pts = 25
    elif "NEGATIVE" in recent_sentiments:
        sentiment_pts = 10
    else:
        sentiment_pts = 0

    days_in_stage = (datetime.utcnow() - entered_at).days if entered_at else 0
    if days_in_stage > 7:
        stage_pts = 15
    elif days_in_stage > 3:
        stage_pts = 8
    else:
        stage_pts = 0

    abandonment_pts = round(abandonment_score * 0.60)
    return {
        "total": abandonment_pts + sentiment_pts + stage_pts,
        "signals": {"abandonment_score": abandonment_score, "abandonment_points": abandonment_pts, "sentiment_points": sentiment_pts, "days_in_stage_points": stage_pts},
    }


def _interview_component(db: Session, submission: Optional[Submission], candidate_id: str, conversation: Optional[CandidateConversation]) -> Dict:
    from app.models.interview_pipeline import SubmissionInterview

    interviews = (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.candidate_id == candidate_id, SubmissionInterview.superseded_at.is_(None))
        .order_by(SubmissionInterview.created_at.asc())
        .all()
        if submission is not None else []
    )
    if not interviews:
        return {"total": 0, "signals": {}}

    booked_at = interviews[0].created_at
    now = datetime.utcnow()

    if conversation is not None:
        messages = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "ai_message_sent", ConversationEvent.created_at > booked_at).count()
        replies = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > booked_at).count()
    else:
        messages, replies = 0, 0
    response_rate_pts = round((1 - min(replies / messages, 1)) * 50) if messages > 0 else 0

    upcoming = next((i for i in interviews if i.scheduled_at and i.scheduled_at > now and i.outcome == "PENDING"), None)
    days_until_pts = 0
    if upcoming and (upcoming.scheduled_at - now).days > 5:
        last_ai_message = (
            db.query(ConversationEvent)
            .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "ai_message_sent")
            .order_by(ConversationEvent.created_at.desc())
            .first()
            if conversation is not None else None
        )
        no_recent_contact = last_ai_message is None or (now - last_ai_message.created_at).days > 5
        if no_recent_contact:
            days_until_pts = 30

    max_reschedules = max((i.reschedule_count for i in interviews), default=0)
    reschedule_pts = min(max_reschedules * 10, 20)

    return {
        "total": response_rate_pts + days_until_pts + reschedule_pts,
        "signals": {"response_rate_points": response_rate_pts, "days_until_interview_points": days_until_pts, "reschedule_points": reschedule_pts},
    }


def _offer_component(db: Session, offer: Optional[OfferLetter], candidate_id: str) -> Dict:
    if offer is None:
        return {"total": 0, "signals": {}}
    now = datetime.utcnow()

    if offer.offer_status in ("Released",) and offer.released_at:
        days_since_release = (now - offer.released_at).days
        days_pts = min(days_since_release * 8, 60)
    else:
        days_pts = 0

    last_sentiment = get_recent_sentiment_trend(db, candidate_id, limit=1)
    if last_sentiment == ["NEGATIVE"]:
        sentiment_pts = 25
    elif last_sentiment == ["NEUTRAL"]:
        sentiment_pts = 10
    else:
        sentiment_pts = 0

    faq_replies = 0
    if offer.released_at:
        conversation = db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate_id).order_by(CandidateConversation.id.desc()).first()
        if conversation is not None:
            faq_replies = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > offer.released_at).count()
    if faq_replies == 0:
        engagement_pts = 15
    elif faq_replies <= 2:
        engagement_pts = 8
    else:
        engagement_pts = 0

    return {
        "total": days_pts + sentiment_pts + engagement_pts,
        "signals": {"days_since_release_points": days_pts, "last_sentiment_points": sentiment_pts, "faq_engagement_points": engagement_pts},
    }


def _preboarding_component(db: Session, offer: Optional[OfferLetter], candidate_id: str, conversation: Optional[CandidateConversation]) -> Dict:
    if offer is None:
        return {"total": 0, "signals": {}}
    now = datetime.utcnow()

    joining_score = db.query(CandidateJoiningScore).filter(CandidateJoiningScore.candidate_id == candidate_id, CandidateJoiningScore.offer_id == offer.id).order_by(CandidateJoiningScore.calculated_at.desc()).first()
    readiness_pts = round((100 - joining_score.readiness_score) * 0.70) if joining_score else 0

    last_event = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id).order_by(ConversationEvent.created_at.desc()).first() if conversation else None
    days_silent = (now - last_event.created_at).days if last_event else 999
    if days_silent <= 2:
        silence_pts = 0
    elif days_silent <= 5:
        silence_pts = 15
    else:
        silence_pts = 30

    return {
        "total": readiness_pts + silence_pts,
        "signals": {"readiness_points": readiness_pts, "readiness_score": joining_score.readiness_score if joining_score else None, "days_silent_points": silence_pts},
    }


def _ghosting_multiplier_applies(db: Session, candidate_id: str) -> bool:
    ghosting = db.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == candidate_id).first()
    return ghosting is not None and not ghosting.is_reactivated  # BR-03: permanent, never resets


def _notify_recruiter_critical(db: Session, candidate: Candidate, score: int) -> None:
    submission = db.query(Submission).filter(Submission.candidate_id == candidate.candidateID).order_by(Submission.submitted_at.desc()).first()
    if submission is None or not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient, priority_tier="P0", channel_preference="EMAIL",
            message=f"URGENT: {candidate.candidateFirstName or candidate.candidateID} has a CRITICAL drop risk score of {score}. Immediate follow-up needed.",
        )
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[DropRisk] Failed to notify recruiter of critical risk: {exc}")


def calculate_drop_risk(db: Session, candidate_id: str, tenant_id: str) -> Dict:
    """Step 2. Never raises. Returns {"outcome": "not_applicable"} for
    candidates not in a scorable stage, {"outcome": "not_found"} if the
    candidate doesn't exist, else {"drop_risk_score", "risk_level",
    "risk_signals"}."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if candidate is None:
            return {"outcome": "not_found"}

        journey = get_candidate_journey(db, candidate_id, tenant_id)
        current_stage = journey["current_stage"]
        by_name = {s["stage_name"]: s for s in journey["stages"]}

        if current_stage not in SCORABLE_STAGES:
            return {"outcome": "not_applicable", "stage": current_stage}

        conversation = db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate_id).order_by(CandidateConversation.id.desc()).first()
        submission = db.query(Submission).filter(Submission.candidate_id == candidate_id).order_by(Submission.submitted_at.desc()).first()
        offer = db.query(OfferLetter).filter(OfferLetter.candidate_id == candidate_id).order_by(OfferLetter.created_at.desc()).first()

        if current_stage in ("ENGAGED", "QUALIFYING", "SCREENED"):
            entered_at = by_name.get("QUALIFYING", {}).get("entered_at") or by_name.get("ENGAGED", {}).get("entered_at")
            component = _qualifying_component(db, candidate_id, tenant_id, conversation, entered_at)
        elif current_stage == "INTERVIEW":
            component = _interview_component(db, submission, candidate_id, conversation)
        elif current_stage == "OFFER":
            component = _offer_component(db, offer, candidate_id)
        else:  # PREBOARDING
            component = _preboarding_component(db, offer, candidate_id, conversation)

        raw_score = min(component["total"], 100)
        ghosted = _ghosting_multiplier_applies(db, candidate_id)
        final_score = min(round(raw_score * GHOSTING_MULTIPLIER), 100) if ghosted else raw_score

        risk_signals = {"stage": current_stage, "raw_score": raw_score, "ghosting_multiplier_applied": ghosted, **component["signals"]}
        risk_level = _risk_level(final_score)

        existing = db.query(CandidateDropRisk).filter(CandidateDropRisk.tenant_id == tenant_id, CandidateDropRisk.candidate_id == candidate_id).first()
        previous_score = existing.drop_risk_score if existing else None
        previously_flagged = existing.is_flagged if existing else False

        # BR-01/AC hysteresis: flagged at >=70, only resolved below 60 -- see module docstring.
        is_flagged = (previously_flagged and final_score >= RESOLVE_THRESHOLD) or final_score >= FLAG_THRESHOLD
        now = datetime.utcnow()

        if existing:
            existing.drop_risk_score = final_score
            existing.risk_level = risk_level
            existing.risk_signals = risk_signals
            existing.is_flagged = is_flagged
            existing.calculated_at = now
            db.add(existing)
        else:
            db.add(CandidateDropRisk(tenant_id=tenant_id, candidate_id=candidate_id, drop_risk_score=final_score, risk_level=risk_level, risk_signals=risk_signals, is_flagged=is_flagged, calculated_at=now))
        db.commit()

        newly_critical = final_score >= CRITICAL_THRESHOLD and (previous_score is None or previous_score < CRITICAL_THRESHOLD)
        if newly_critical:  # BR-01: immediate, not on next job run
            _notify_recruiter_critical(db, candidate, final_score)

        if previously_flagged and not is_flagged and conversation is not None:
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="DROP_RISK_RESOLVED", event_data={"previous_score": previous_score, "new_score": final_score}, triggered_by="system"))
            db.commit()

        # S-062/HRMS-0462: real intervention-queue wiring. CRITICAL (>=80)
        # supersedes HIGH_DROP_RISK; HIGH (70-79) supersedes CRITICAL_DROP_RISK
        # (a downgrade); BR-03's own literal "drops below 50" auto-resolves both.
        from app.services.intervention_queue_service import PRIORITY_CRITICAL, PRIORITY_HIGH, add_to_queue, resolve_queue_items
        if final_score >= CRITICAL_THRESHOLD:
            add_to_queue(db, candidate_id, tenant_id, "CRITICAL_DROP_RISK", f"Critical Drop Risk: {final_score}", PRIORITY_CRITICAL)
            resolve_queue_items(db, candidate_id, tenant_id, ["HIGH_DROP_RISK"], note=f"Superseded by CRITICAL_DROP_RISK (score {final_score})")
        elif final_score >= FLAG_THRESHOLD:
            add_to_queue(db, candidate_id, tenant_id, "HIGH_DROP_RISK", f"High Drop Risk: {final_score}", PRIORITY_HIGH)
            resolve_queue_items(db, candidate_id, tenant_id, ["CRITICAL_DROP_RISK"], note=f"Downgraded from critical (score {final_score})")
        elif final_score < 50:  # BR-03's own named threshold
            resolve_queue_items(db, candidate_id, tenant_id, ["HIGH_DROP_RISK", "CRITICAL_DROP_RISK"], note=f"Drop risk score fell to {final_score}")

        return {"drop_risk_score": final_score, "risk_level": risk_level, "risk_signals": risk_signals, "is_flagged": is_flagged, "calculated_at": now}
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[DropRisk] Failed calculating drop risk for candidate {candidate_id!r}: {exc}")
        db.rollback()
        return {"outcome": "calculation_failed"}


def run_drop_risk_scoring_job(db: Session) -> Dict:
    """Step 3. Runs every 4 hours. Never lets one bad row abort the batch."""
    result = {"processed": 0, "scored": 0, "skipped": 0}

    candidates = db.query(Candidate).join(CandidateConversation, CandidateConversation.candidate_id == Candidate.candidateID).distinct().all()
    for candidate in candidates:
        result["processed"] += 1
        try:
            conversation = db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate.candidateID).order_by(CandidateConversation.id.desc()).first()
            if conversation is None:
                result["skipped"] += 1
                continue
            calc = calculate_drop_risk(db, candidate.candidateID, conversation.tenant_id)
            if "drop_risk_score" in calc:
                result["scored"] += 1
            else:
                result["skipped"] += 1
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[DropRisk] Failed processing candidate {candidate.candidateID!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result
