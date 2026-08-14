"""
S-071/HRMS-0471 -- AI Recruiter Performance Analytics.

Real architecture adaptations:
- No `agent_execution_log` table (this story's own literal HRMS-0466
  dependency -- the Supervisor Agent, S-066, held pending a design
  check-in per this session's own established discipline, see
  wros_project_status memory). The real, honest substitute for
  "Thunder vs human actions" is `ConversationEvent.triggered_by` --
  already a real field with real values ("ai_agent"/"hr_user"/
  "system"/"candidate") on every send event in this codebase.
  Thunder actions = `ai_message_sent` events; human actions =
  `hr_message_sent` events (S-009's manual send). Not literally the
  spec's `agent_execution_log` schema, but the same real signal it
  would have captured, already present and reliable.
- No `conversation_state_history`/fictional QUALIFIED state --
  "qualified" reuses S-059's real SCREENED stage marker (a
  `CandidateJobScore` row existing), same substitute S-070 already
  established. "Entered QUALIFYING" reuses the real
  `CandidateConversation.created_at` (ENGAGED, the real start of
  engagement).
- No `thunder_activity_feed` table -- escalation/ghosting counts read
  the real `ConversationEvent`/`CandidateGhostingStatus` rows directly
  (same S-061 vocabulary).
- avg_days_to_qualify / avg_messages_per_candidate reuse S-070's own
  real `CandidateEngagementMetrics` rows rather than recomputing the
  same thing twice.
- top_risk_candidates reuses S-060's real `CandidateDropRisk`
  (current snapshot, not date-filtered -- risk is a live property, not
  a historical one, same posture S-063's dashboard already takes).
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_engagement_metrics import CandidateEngagementMetrics
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_job_score import CandidateJobScore

DEFAULT_RANGE_DAYS = 30
TOP_RISK_COUNT = 5
HUMAN_DEPENDENCY_TARGET_PCT = 20  # BR-01


def _date_range(date_from: Optional[date], date_to: Optional[date]) -> (datetime, datetime):
    to_dt = datetime.combine(date_to or datetime.utcnow().date(), datetime.max.time())
    from_dt = datetime.combine(date_from or (to_dt.date() - timedelta(days=DEFAULT_RANGE_DAYS)), datetime.min.time())
    return from_dt, to_dt


def get_thunder_analytics(db: Session, tenant_id: str, *, date_from: Optional[date] = None, date_to: Optional[date] = None, scoped_user=None) -> Dict:
    """
    Get Thunder analytics with optional role-based scoping.

    scoped_user: If provided (non-Super User), data is scoped to user's business unit(s).
                 If None (Super User or no scoping), all data is returned.
    """
    from_dt, to_dt = _date_range(date_from, date_to)

    # Base query for conversations
    conversations_query = db.query(CandidateConversation).filter(
        CandidateConversation.tenant_id == tenant_id,
        CandidateConversation.created_at.between(from_dt, to_dt)
    )

    # Apply role-based scoping if user is not super user
    if scoped_user:
        # Non-super users see only conversations for candidates in their business unit(s)
        user_bu_id = getattr(scoped_user, 'business_unit_id', None)
        if user_bu_id:
            conversations_query = conversations_query.join(
                Candidate, CandidateConversation.candidate_id == Candidate.candidateID
            ).filter(Candidate.business_unit_id == user_bu_id)

    conversations = conversations_query.all()
    candidate_ids = [c.candidate_id for c in conversations]
    active_count = len(candidate_ids)

    # Get qualified scores - already scoped by candidate_ids which respect BU filter
    qualified_scores = (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.candidate_id.in_(candidate_ids), CandidateJobScore.calculated_at.between(from_dt, to_dt))
        .all()
        if candidate_ids else []
    )
    qualified_candidate_ids = {s.candidate_id for s in qualified_scores}
    qualification_rate = round(100 * len(qualified_candidate_ids) / active_count) if active_count else 0

    escalation_count = (
        db.query(ConversationEvent)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type == "escalation_triggered", ConversationEvent.created_at.between(from_dt, to_dt))
        .count()
    )
    escalation_rate = round(100 * escalation_count / active_count, 1) if active_count else 0

    ghosting_count = (
        db.query(CandidateGhostingStatus)
        .filter(CandidateGhostingStatus.tenant_id == tenant_id, CandidateGhostingStatus.ghosted_at.between(from_dt, to_dt))
        .count()
    )
    ghosting_rate = round(100 * ghosting_count / active_count, 1) if active_count else 0

    thunder_actions = (
        db.query(ConversationEvent)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type == "ai_message_sent", ConversationEvent.created_at.between(from_dt, to_dt))
        .count()
    )
    human_actions = (
        db.query(ConversationEvent)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type == "hr_message_sent", ConversationEvent.created_at.between(from_dt, to_dt))
        .count()
    )
    total_actions = thunder_actions + human_actions
    human_intervention_rate = round(100 * human_actions / total_actions, 1) if total_actions else 0
    thunder_pct = round(100 * thunder_actions / total_actions, 1) if total_actions else 0

    engagement_rows = (
        db.query(CandidateEngagementMetrics)
        .filter(CandidateEngagementMetrics.tenant_id == tenant_id, CandidateEngagementMetrics.candidate_id.in_(candidate_ids))
        .all()
        if candidate_ids else []
    )
    qualified_engagement = [r for r in engagement_rows if r.days_to_qualification is not None]
    avg_days_to_qualify = round(sum(r.days_to_qualification for r in qualified_engagement) / len(qualified_engagement), 1) if qualified_engagement else None
    avg_messages_per_candidate = round(sum(r.total_messages_exchanged for r in engagement_rows) / len(engagement_rows), 1) if engagement_rows else 0

    # NEW METRICS: Candidates reached, responded, jobs connected
    candidates_reached = len(candidate_ids)  # Total candidates with conversations initiated

    # Candidates that responded (have messages in conversations)
    candidates_with_responses = (
        db.query(ConversationEvent.candidate_id)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type.in_(["candidate_message", "candidate_reply"]), ConversationEvent.created_at.between(from_dt, to_dt))
        .distinct()
        .count()
    )

    # Jobs connected to Thunder (unique jobs with active Thunder connections)
    jobs_connected_to_thunder = (
        db.query(CandidateJobScore.job_id)
        .join(Candidate, CandidateJobScore.candidate_id == Candidate.candidateID)
        .filter(CandidateJobScore.tenant_id == tenant_id, Candidate.candidateID.in_(candidate_ids), CandidateJobScore.calculated_at.between(from_dt, to_dt))
        .distinct()
        .count()
    )

    trends = _build_trends(db, tenant_id, from_dt, to_dt)

    top_risk_rows = (
        db.query(CandidateDropRisk)
        .filter(CandidateDropRisk.tenant_id == tenant_id)
        .order_by(CandidateDropRisk.drop_risk_score.desc())
        .limit(TOP_RISK_COUNT)
        .all()
    )
    risk_candidate_ids = {r.candidate_id for r in top_risk_rows}
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(risk_candidate_ids)).all()} if risk_candidate_ids else {}
    top_risk_candidates = [
        {"candidate_id": r.candidate_id, "name": _display_name(candidates_by_id.get(r.candidate_id)), "drop_risk_score": r.drop_risk_score, "risk_level": r.risk_level}
        for r in top_risk_rows
    ]

    return {
        "summary": {
            "qualification_rate": qualification_rate,
            "escalation_rate": escalation_rate,
            "ghosting_rate": ghosting_rate,
            "avg_days_to_qualify": avg_days_to_qualify,
            "avg_messages_per_candidate": avg_messages_per_candidate,
            "human_intervention_rate": human_intervention_rate,
            "human_dependency_target_pct": HUMAN_DEPENDENCY_TARGET_PCT,
            "candidates_reached": candidates_reached,
            "candidates_responded": candidates_with_responses,
            "jobs_connected_to_thunder": jobs_connected_to_thunder,
        },
        "trends": trends,
        "top_risk_candidates": top_risk_candidates,
        "agent_actions_breakdown": {"thunder_actions": thunder_actions, "human_actions": human_actions, "thunder_pct": thunder_pct},
    }


def _display_name(candidate) -> str:
    if candidate is None:
        return "Unknown candidate"
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    return " ".join(p for p in parts if p).strip() or candidate.candidateEmail


def _build_trends(db: Session, tenant_id: str, from_dt: datetime, to_dt: datetime) -> List[Dict]:
    days = (to_dt.date() - from_dt.date()).days + 1
    trends = []
    for offset in range(days):
        day = from_dt.date() + timedelta(days=offset)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())

        qualifications = (
            db.query(CandidateJobScore)
            .join(Candidate, CandidateJobScore.candidate_id == Candidate.candidateID)
            .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.calculated_at.between(day_start, day_end))
            .count()
        )
        escalations = (
            db.query(ConversationEvent)
            .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
            .filter(CandidateConversation.tenant_id == tenant_id, ConversationEvent.event_type == "escalation_triggered", ConversationEvent.created_at.between(day_start, day_end))
            .count()
        )
        ghostings = (
            db.query(CandidateGhostingStatus)
            .filter(CandidateGhostingStatus.tenant_id == tenant_id, CandidateGhostingStatus.ghosted_at.between(day_start, day_end))
            .count()
        )
        new_candidates = (
            db.query(CandidateConversation)
            .filter(CandidateConversation.tenant_id == tenant_id, CandidateConversation.created_at.between(day_start, day_end))
            .count()
        )
        trends.append({"date": day.isoformat(), "qualifications": qualifications, "escalations": escalations, "ghostings": ghostings, "new_candidates": new_candidates})
    return trends
