"""
import logging
HRMS-0905 -- Timesheet Analytics & Compliance.

Pure reporting layer over the existing Timesheet table -- no new
schema. calculate_utilization_pct_phase2() is the Phase 2 hours-based
utilization calculation this story specifies ("switch from Phase 1
status-based to Phase 2 hours-based automatically once approved
timesheets exist") -- HRMS-0510's actual Phase 1 calculateUtilization()
function doesn't exist anywhere in this codebase, so this returns None
when no approved timesheets exist in the period (signalling "fall back
to your own Phase 1 logic") rather than fabricating that Phase 1
calculation here.
"""
from datetime import datetime, time, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.timesheet import Timesheet
from app.models.timesheet_dispute import TimesheetDispute

SUBMISSION_DEADLINE_DAYS = 7   # BR-01: following Monday 9 AM
MISSING_CUTOFF_DAYS = 9       # BR-01: following Wednesday EOD

def classify_submission_timeliness(timesheet: Timesheet, *, now: Optional[datetime] = None) -> str:
    """HRMS-0905 BR-01. Returns ON_TIME, LATE, MISSING, or NOT_YET_DUE."""
    now = now or datetime.utcnow()
    deadline = datetime.combine(timesheet.week_starting_date + timedelta(days=SUBMISSION_DEADLINE_DAYS), time(9, 0))
    missing_cutoff = datetime.combine(
        timesheet.week_starting_date + timedelta(days=MISSING_CUTOFF_DAYS), time(23, 59, 59),
    )

    if timesheet.submitted_at is not None:
        return "ON_TIME" if timesheet.submitted_at <= deadline else "LATE"
    return "MISSING" if now > missing_cutoff else "NOT_YET_DUE"

def get_timesheet_compliance_report(
    db: Session, *, tenant_id: Optional[int], date_from, date_to, now: Optional[datetime] = None,
) -> Dict:
    now = now or datetime.utcnow()
    timesheets = db.query(Timesheet).filter(
        Timesheet.tenant_id == tenant_id,
        Timesheet.week_starting_date >= date_from,
        Timesheet.week_starting_date <= date_to,
    ).all()

    total = len(timesheets)
    by_employee: Dict[str, Dict[str, int]] = {}
    on_time = late = missing = 0

    for ts in timesheets:
        classification = classify_submission_timeliness(ts, now=now)
        entry = by_employee.setdefault(ts.employee_id, {"on_time": 0, "late": 0, "missing": 0})
        if classification == "ON_TIME":
            on_time += 1
            entry["on_time"] += 1
        elif classification == "LATE":
            late += 1
            entry["late"] += 1
        elif classification == "MISSING":
            missing += 1
            entry["missing"] += 1

    submission_rate_pct = ((on_time + late) / total * 100) if total else 0.0
    late_submission_rate_pct = (late / total * 100) if total else 0.0

    turnarounds = [
        (ts.approved_at - ts.submitted_at).total_seconds() / 3600
        for ts in timesheets if ts.approved_at and ts.submitted_at
    ]
    avg_approval_turnaround_hours = sum(turnarounds) / len(turnarounds) if turnarounds else None

    timesheet_ids = [ts.id for ts in timesheets]
    disputed_count = 0
    if timesheet_ids:
        disputed_count = db.query(TimesheetDispute.timesheet_id).filter(
            TimesheetDispute.timesheet_id.in_(timesheet_ids)
        ).distinct().count()
    dispute_rate_pct = (disputed_count / total * 100) if total else 0.0

    return {
        "submission_rate_pct": submission_rate_pct,
        "late_submission_rate_pct": late_submission_rate_pct,
        "avg_approval_turnaround_hours": avg_approval_turnaround_hours,
        "dispute_rate_pct": dispute_rate_pct,
        "by_employee": by_employee,
    }

def calculate_utilization_pct_phase2(
    db: Session, employee_id: str, period_start, period_end,
) -> Optional[float]:
    """HRMS-0905 BR-02. Returns None (signal: fall back to Phase 1
    logic) when no approved timesheets exist in the period, rather than
    reporting a misleading 0%."""
    approved = db.query(Timesheet).filter(
        Timesheet.employee_id == employee_id,
        Timesheet.status == "APPROVED",
        Timesheet.week_starting_date >= period_start,
        Timesheet.week_starting_date <= period_end,
    ).all()
    if not approved:
        return None

    total_billable_hours = sum(float(ts.billable_hours) for ts in approved)
    working_weeks = len(approved)
    return total_billable_hours / (working_weeks * 40) * 100
