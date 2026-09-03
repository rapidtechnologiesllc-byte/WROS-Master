"""
HRMS-0515 -- PerformanceStoreWriter. The one function every story that
needs to log a performance-relevant event should call, rather than
inserting into employee_performance_events directly -- same single-
sanctioned-writer discipline as write_audit_log() and
import logging
create_candidate_safe().

Read side (get_performance_events/get_score_summary) added alongside
S-356's milestone tracker, the first caller that also needed to read
this store back. The source doc's own schema (Step 1) specifies
normalized `score`/`score_category` columns; this codebase's real,
already-shipped writer (used by buddy_program_service.py and
htd_phase_gate_service.py before this round) stores everything in a
single JSON `event_data` blob instead, with "score" only present as a
key inside that blob for event types that have one (BUDDY_KPI does,
CERTIFICATION_GATE doesn't). Migrating those two existing callers onto
new top-level columns is real, separate scope -- not done here.
get_score_summary() below reads score out of the JSON blob generically
rather than assuming a column that doesn't exist.

LLM weekly performance-summary generation (the doc's Step 3,
PerformanceSummaryGenerator) is NOT built -- deferred and flagged, not
silently skipped: it's a real LLM-integration decision (model choice,
cost, prompt design) on the same footing as this session's other
flagged AI pieces, even though it doesn't need a persona/tone call the
way Thunder or the S-355/S-357 agentic bots do.
"""
import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.performance_store import EmployeePerformanceEvent

def write_performance_event(
    db: Session,
    *,
    employee_id: str,
    event_type: str,
    event_data: Optional[dict] = None,
    tenant_id=None,
) -> EmployeePerformanceEvent:
    event = EmployeePerformanceEvent(
        tenant_id=tenant_id, employee_id=employee_id, event_type=event_type,
        event_data=json.dumps(event_data) if event_data is not None else None,
    )
    db.add(event)
    return event

def get_performance_events(
    db: Session, employee_id: str, *, since_days: int = 90, now: Optional[date] = None,
) -> List[EmployeePerformanceEvent]:
    """HRMS-0515 Step 4: 'last 90 days', most recent first. `now` is
    injectable for tests, same pattern as every other since-days scan
    this codebase already uses (e.g. scan_project_revenue_leakage)."""
    cutoff = datetime.combine((now or date.today()) - timedelta(days=since_days), datetime.min.time())
    return (
        db.query(EmployeePerformanceEvent)
        .filter(
            EmployeePerformanceEvent.employee_id == employee_id,
            EmployeePerformanceEvent.occurred_at >= cutoff,
        )
        .order_by(EmployeePerformanceEvent.occurred_at.desc())
        .all()
    )

def get_score_averages_by_event_type(db: Session, employee_id: str, *, since_days: int = 90) -> dict:
    """AC-4: score averages -- grouped by event_type (the real
    discriminator this store uses), not the doc's score_category column
    which doesn't exist here. Only events whose event_data JSON contains
    a numeric "score" key contribute; event types with no score
    (e.g. CERTIFICATION_GATE) are silently excluded, not zero-filled."""
    events = get_performance_events(db, employee_id, since_days=since_days)
    totals: dict = {}
    for event in events:
        if not event.event_data:
            continue
        try:
            data = json.loads(event.event_data)
        except (TypeError, ValueError):
            continue
        score = data.get("score") if isinstance(data, dict) else None
        if not isinstance(score, (int, float)):
            continue
        bucket = totals.setdefault(event.event_type, [])
        bucket.append(score)
    return {
        event_type: round(sum(scores) / len(scores), 2)
        for event_type, scores in totals.items()
    }
