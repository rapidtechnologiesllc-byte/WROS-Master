"""
import logging
S-063/HRMS-0463 -- Candidate Risk Dashboard.

Real architecture adaptations:
- BR-01 ("exclude COMPLETED and WITHDRAWN") has no literal
  conversation.status value matching either -- CandidateConversation
  only has 3 real axes (S-018). "COMPLETED" is naturally already
  excluded for free: S-060's calculate_drop_risk() only ever computes
  a score for candidates in a SCORABLE_STAGES stage (ENGAGED through
  PREBOARDING) -- a JOINED candidate never gets a CandidateDropRisk
  row in the first place. "WITHDRAWN" maps to the real
  conversation.status=='closed' terminal state (a declined offer,
  resolved ghosting, etc.) -- those candidates' rows are filtered out
  here even if a stale drop-risk row still exists from before closure.
- "stage" per candidate is read directly from
  CandidateDropRisk.risk_signals['stage'] (S-060 already stores this
  on every row via S-059's real get_candidate_journey() stage
  detection) rather than recomputing the journey for every candidate
  on every dashboard load -- same real data, no redundant recompute.
- top_risk_signal: risk_signals is a flat dict of named point
  contributions (S-060's own real shape), not literally the spec's
  JSONB array -- the single highest-point component is picked and
  rendered as a short human phrase. Where the underlying count isn't
  separately tracked (e.g. sentiment_points is a tier, not a literal
  "3 negative messages" counter), the phrase names the CATEGORY
  honestly rather than fabricating a precise count S-060 never stored.
- Sentiment trend/stage breakdown are real aggregate reads over
  CandidateSentimentLog (S-036) and CandidateDropRisk -- no new table.
"""
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_sentiment_log import CandidateSentimentLog

CANDIDATES_AT_RISK_THRESHOLD = 40  # Step 1
TREND_DAYS = 14

SIGNAL_LABELS = {
    "sentiment_points": lambda s: "Negative sentiment trend",
    "abandonment_points": lambda s: f"Abandonment score {s.get('abandonment_score', '?')}",
    "days_in_stage_points": lambda s: "Stuck in stage",
    "response_rate_points": lambda s: "Low response rate since interview booked",
    "days_until_interview_points": lambda s: "No contact before upcoming interview",
    "reschedule_points": lambda s: "Multiple interview reschedules",
    "days_since_release_points": lambda s: "No response since offer sent",
    "last_sentiment_points": lambda s: "Negative sentiment",
    "faq_engagement_points": lambda s: "Low engagement with offer",
    "readiness_points": lambda s: f"Low joining readiness ({s.get('readiness_score', '?')}%)",
    "days_silent_points": lambda s: "No recent contact",
}


def _candidate_name(candidate) -> str:
    if candidate is None:
        return "Unknown candidate"
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    return " ".join(p for p in parts if p).strip() or candidate.candidateEmail


def _top_risk_signal(risk_signals: Dict) -> str:
    if not risk_signals:
        return "Unknown"
    candidates = [(key, value) for key, value in risk_signals.items() if key in SIGNAL_LABELS and isinstance(value, (int, float))]
    if not candidates:
        return "Unknown"
    top_key, _ = max(candidates, key=lambda kv: kv[1])
    return SIGNAL_LABELS[top_key](risk_signals)


def _active_drop_risk_rows(db: Session, tenant_id: str) -> List:
    """BR-01: excludes candidates whose conversation has closed
    (real WITHDRAWN proxy) -- JOINED (real COMPLETED proxy) is already
    excluded by construction, see module docstring."""
    rows = (
        db.query(CandidateDropRisk, CandidateConversation)
        .join(CandidateConversation, CandidateDropRisk.candidate_id == CandidateConversation.candidate_id)
        .filter(CandidateDropRisk.tenant_id == tenant_id, CandidateConversation.status != "closed")
        .all()
    )
    # A candidate can have multiple historical conversations; keep the most recent per candidate.
    latest_by_candidate = {}
    for risk, conv in rows:
        existing = latest_by_candidate.get(risk.candidate_id)
        if existing is None or conv.id > existing[1].id:
            latest_by_candidate[risk.candidate_id] = (risk, conv)
    return list(latest_by_candidate.values())


def get_risk_dashboard(db: Session, tenant_id: str) -> Dict:
    """Step 1. Never raises internally is not guaranteed here (a genuine
    DB failure should surface as a 500) -- callers show the "unavailable"
    message per this story's own integrations table."""
    active = _active_drop_risk_rows(db, tenant_id)

    risk_summary = {"critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
    for risk, _ in active:
        key = f"{risk.risk_level.lower()}_count"
        if key in risk_summary:
            risk_summary[key] += 1

    candidate_ids = {risk.candidate_id for risk, _ in active}
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()} if candidate_ids else {}

    at_risk = [(risk, conv) for risk, conv in active if risk.drop_risk_score >= CANDIDATES_AT_RISK_THRESHOLD]
    at_risk.sort(key=lambda pair: pair[0].drop_risk_score, reverse=True)

    candidates_at_risk = [
        {
            "candidate_id": risk.candidate_id,
            "name": _candidate_name(candidates_by_id.get(risk.candidate_id)),
            "drop_risk_score": risk.drop_risk_score,
            "risk_level": risk.risk_level,
            "stage": (risk.risk_signals or {}).get("stage", "UNKNOWN"),
            "top_risk_signal": _top_risk_signal(risk.risk_signals or {}),
        }
        for risk, conv in at_risk
    ]

    now = datetime.utcnow()
    since = now - timedelta(days=TREND_DAYS)
    sentiment_rows = (
        db.query(CandidateSentimentLog)
        .filter(CandidateSentimentLog.tenant_id == tenant_id, CandidateSentimentLog.analyzed_at >= since)
        .all()
    )
    by_date: Dict[str, Dict[str, int]] = {}
    for row in sentiment_rows:
        date_key = row.analyzed_at.strftime("%Y-%m-%d")
        bucket = by_date.setdefault(date_key, {"total": 0, "positive": 0, "negative": 0})
        bucket["total"] += 1
        if row.sentiment == "POSITIVE":
            bucket["positive"] += 1
        elif row.sentiment == "NEGATIVE":
            bucket["negative"] += 1

    sentiment_trend = []
    for offset in range(TREND_DAYS - 1, -1, -1):
        day = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        bucket = by_date.get(day, {"total": 0, "positive": 0, "negative": 0})
        total = bucket["total"]
        sentiment_trend.append({
            "date": day,
            "avg_positive_pct": round(100 * bucket["positive"] / total) if total else 0,
            "avg_negative_pct": round(100 * bucket["negative"] / total) if total else 0,
        })

    stage_totals: Dict[str, Dict[str, float]] = {}
    for risk, _ in active:
        stage = (risk.risk_signals or {}).get("stage", "UNKNOWN")
        bucket = stage_totals.setdefault(stage, {"sum": 0, "count": 0})
        bucket["sum"] += risk.drop_risk_score
        bucket["count"] += 1
    stage_risk_breakdown = [
        {"stage": stage, "avg_risk_score": round(bucket["sum"] / bucket["count"]), "candidate_count": bucket["count"]}
        for stage, bucket in stage_totals.items()
    ]
    stage_risk_breakdown.sort(key=lambda row: row["avg_risk_score"], reverse=True)

    return {
        "risk_summary": risk_summary,
        "candidates_at_risk": candidates_at_risk,
        "sentiment_trend": sentiment_trend,
        "stage_risk_breakdown": stage_risk_breakdown,
    }
