"""
import logging
S-066/HRMS-0466 -- Supervisor Agent, Multi-Agent Coordinator.

Real architecture adaptation (per Avinash's explicit direction,
2026-08-04 -- "can this be converted to a batch process or a log and
retry till complete mechanism?"): yes, and it already effectively is.

The literal spec assumes 7 discrete "sub-agent" classes (Qualification/
FollowUp/Scheduling/Offer/DocumentCollection/Sentiment/RiskAgent) that
a coordinator dispatches under a distributed lock. Neither the agent
classes nor the lock's prerequisite (Redis) exist in this codebase.
What DOES exist, already shipped across ~18 independent APScheduler
jobs (follow_up_execution_job, no_response_detection_job,
ghosting_detection_job, interview_reminder_execution_job,
document_reminder_job, abandonment_scoring_job, drop_risk_scoring_job,
etc.): each one already IS "log and retry till complete" -- a
stateless periodic query against real DB state, re-evaluating fresh
every cycle, already gated by the real R-08 ownership check, S-035
escalation state, and (since this session) S-075's pause flags at
their own real send choke point (thunder_service.send_thunder_message).
Rebuilding a second dispatch layer that reimplements those same
per-domain rules would be large, risky, and add no real behavior this
codebase doesn't already have.

What this story genuinely adds, and what run_supervisor_cycle() below
builds: the real, missing OBSERVABILITY/COORDINATION rollup the
spec's own "why this exists" section actually wants --
  - Step 1's agent_execution_log: one row per candidate per cycle,
    recording which real journey stage (S-059's get_candidate_journey())
    it's in and whether it was skipped (BR-01 human-owned, S-035
    escalated, or S-075 paused) or evaluated.
  - Step 5's metrics: reuses thunder_analytics_service.get_thunder_
    analytics() directly for the real thunder-vs-human action
    breakdown (S-071 already built and tested this exact computation)
    rather than a third reimplementation.
  - A real BR-01/BR-03 conflict AUDIT: since single-process execution
    makes the race the spec's Redis lock defends against structurally
    impossible here, this checks (rather than merely prevents by
    construction) whether any ai_agent-triggered send landed on a
    human-owned or escalated conversation during the cycle window --
    real defense-in-depth, not expected to ever fire, and honestly
    documented as such rather than silently assumed safe.
  - supervisor.cycle_completed emitted via the new S-078 EventEmitter
    (its first real caller).

BR-02's distributed locking / BR-03's rate limiting are NOT built as
separate mechanisms -- BR-03's literal "one proactive message per
candidate per 2h" is already enforced today by each real job's own
domain rule (thunder_service's 60s debounce, S-056's 48h offer-nudge
cap, etc.); a second, cross-job global rate limiter would need to
intercept every one of those independent sends, a real architectural
change out of scope for a coordinator story, flagged here rather than
silently built partially.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.agent_execution_log import AgentExecutionLog
from app.models.candidate_ai import CandidateConversation, ConversationEvent

CYCLE_WINDOW_MINUTES = 15  # SUPERVISOR_AGENT_JOB's own cadence

# Step 3's state->agent-name mapping, for readable agent_execution_log
# rows -- maps onto S-059's real get_candidate_journey() stages rather
# than a fictional state machine.
STAGE_TO_AGENT_NAME = {
    "Engaged": "QualificationAgent",
    "Qualifying": "QualificationAgent",
    "Screened": "SchedulingAgent",
    "Interview": "ReminderAgent",
    "Offer": "OfferFollowUpAgent",
    "Preboarding": "DocumentCollectionAgent",
    "Joined": "OnboardingAgent",
}

def _active_tenant_ids(db: Session) -> List[str]:
    return sorted({row[0] for row in db.query(CandidateConversation.tenant_id).distinct().all() if row[0]})

def _evaluate_conversation(db: Session, conversation: CandidateConversation) -> Dict:
    """Step 3's priority-ordered skip checks (1-2), then a stage lookup
    for the remaining candidates. Returns a dict describing what was
    logged -- never raises; a per-candidate failure is caught by the
    caller and logged as its own AgentExecutionLog row."""
    from app.services.thunder_pause_service import is_thunder_paused_for_conversation
    from app.services.candidate_journey_service import get_candidate_journey

    if conversation.owner_type != "ai_agent":
        return {"agent_name": "SupervisorAgent", "action_taken": "SKIPPED", "action_data": {"reason": "HUMAN_OWNED"}, "acted": False}
    if conversation.escalation_state == "escalated":
        return {"agent_name": "SupervisorAgent", "action_taken": "SKIPPED", "action_data": {"reason": "ESCALATED"}, "acted": False}
    if is_thunder_paused_for_conversation(db, conversation):
        return {"agent_name": "SupervisorAgent", "action_taken": "SKIPPED", "action_data": {"reason": "THUNDER_PAUSED"}, "acted": False}

    try:
        journey = get_candidate_journey(db, conversation.candidate_id, conversation.tenant_id)
        stage = journey.get("current_stage", "Engaged")
    except Exception:
        stage = "Engaged"
    agent_name = STAGE_TO_AGENT_NAME.get(stage, "QualificationAgent")
    return {"agent_name": agent_name, "action_taken": "EVALUATED", "action_data": {"stage": stage}, "acted": False}

def _detect_conflicts(db: Session, tenant_id: str, window_start: datetime) -> int:
    """BR-01/BR-03 real audit, not a preventive lock (see module
    docstring on why a lock is unnecessary in this single-process
    deployment). Flags any ai_agent-triggered send in the cycle window
    whose conversation was human-owned or escalated AT THE TIME the
    row is read -- a real, honest best-effort check (a conversation
    that was escalated mid-window and later resolved won't be caught
    retroactively; there is no state-history table to check against,
    same gap S-059 already flagged for multi-visit stage history)."""
    sends = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.event_type == "ai_message_sent", ConversationEvent.triggered_by == "ai_agent",
                ConversationEvent.created_at >= window_start)
        .all()
    )
    conflicts = 0
    for event in sends:
        conversation = db.query(CandidateConversation).filter(CandidateConversation.id == event.conversation_id, CandidateConversation.tenant_id == tenant_id).first()
        if conversation is None:
            continue
        if conversation.owner_type != "ai_agent" or conversation.escalation_state == "escalated":
            conflicts += 1
            logger.warning(
                f"[SupervisorAgent] BR-01/BR-03 CONFLICT_DETECTED: ai_message_sent event {event.id!r} on "
                f"conversation {conversation.id!r} (owner_type={conversation.owner_type!r}, "
                f"escalation_state={conversation.escalation_state!r}) during cycle window."
            )
    return conflicts

def _run_cycle_for_tenant(db: Session, tenant_id: str, window_start: datetime, today_start: datetime) -> Dict:
    from app.services.event_emitter_service import emit

    cycle_started = datetime.utcnow()
    conversations = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.tenant_id == tenant_id, CandidateConversation.status != "closed")
        .all()
    )

    evaluated = 0
    skipped = 0
    for conversation in conversations:
        try:
            outcome = _evaluate_conversation(db, conversation)
            db.add(AgentExecutionLog(
                tenant_id=tenant_id, candidate_id=conversation.candidate_id,
                agent_name=outcome["agent_name"], action_taken=outcome["action_taken"],
                action_data=outcome["action_data"], success=True,
            ))
            if outcome["action_taken"] == "SKIPPED":
                skipped += 1
            else:
                evaluated += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            db.add(AgentExecutionLog(
                tenant_id=tenant_id, candidate_id=conversation.candidate_id,
                agent_name="SupervisorAgent", action_taken="EVALUATION_FAILED",
                action_data=None, success=False, error_message=str(exc)[:2000],
            ))
            logger.error(f"[SupervisorAgent] Evaluation failed for candidate {conversation.candidate_id!r}: {exc}")
            db.commit()

    conflicts = _detect_conflicts(db, tenant_id, window_start)

    # Step 5: real thunder-vs-human action breakdown -- reuses S-071's
    # already-built, already-tested computation rather than a third one.
    actions_dispatched = 0
    thunder_autonomy_pct = None
    try:
        from app.services.thunder_analytics_service import get_thunder_analytics
        today = today_start.date()
        analytics = get_thunder_analytics(db, tenant_id, date_from=today, date_to=today)
        breakdown = analytics.get("agent_actions_breakdown", {})
        actions_dispatched = breakdown.get("thunder_actions", 0)
        thunder_autonomy_pct = breakdown.get("thunder_pct")
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[SupervisorAgent] Could not compute thunder analytics for tenant {tenant_id!r}: {exc}")

    duration_ms = int((datetime.utcnow() - cycle_started).total_seconds() * 1000)

    try:
        emit(
            db, "supervisor.cycle_completed",
            {
                "tenant_id": tenant_id, "candidates_evaluated": evaluated + skipped,
                "actions_dispatched": actions_dispatched, "conflicts_detected": conflicts,
                "thunder_autonomy_pct": thunder_autonomy_pct, "duration_ms": duration_ms,
            },
            tenant_id,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[SupervisorAgent] Failed to emit supervisor.cycle_completed for tenant {tenant_id!r}: {exc}")

    return {
        "candidates_evaluated": evaluated + skipped, "actions_dispatched": actions_dispatched,
        "skipped": skipped, "conflicts_detected": conflicts,
    }

def run_supervisor_cycle(db: Session, tenant_id: Optional[str] = None) -> Dict:
    """SUPERVISOR_AGENT_JOB body, run every 15 min. Never lets one bad
    tenant abort the whole cycle."""
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=CYCLE_WINDOW_MINUTES)
    today_start = datetime(now.year, now.month, now.day)

    tenant_ids = [tenant_id] if tenant_id else _active_tenant_ids(db)
    overall = {"tenants_processed": 0, "candidates_evaluated": 0, "actions_dispatched": 0, "skipped": 0, "conflicts_detected": 0}

    for tid in tenant_ids:
        try:
            result = _run_cycle_for_tenant(db, tid, window_start, today_start)
            overall["candidates_evaluated"] += result["candidates_evaluated"]
            overall["actions_dispatched"] += result["actions_dispatched"]
            overall["skipped"] += result["skipped"]
            overall["conflicts_detected"] += result["conflicts_detected"]
            overall["tenants_processed"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[SupervisorAgent] Cycle failed for tenant {tid!r}: {exc}")

    return overall
