"""
import logging
S-359/HRMS-P511 -- HTD Intake Pause Engine: Conversion Rate Breach.

WhatsApp/email notification to "BU Head + Hemant" (AC-3) is NOT wired
here -- flagged, not silently dropped: this codebase has no lookup
that resolves the "HEMANT_BU_HEAD" gate-owner role (already referenced
in htd_phase_gate_service.py) to a real email/WhatsApp number anywhere.
A real EmailService.send_notification() exists and could be called
once that lookup is built; inventing a hardcoded recipient address
here would be worse than not sending anything. The permanent
htd_pause_log entry this module writes on every pause/resume already
satisfies AC-6 regardless.

Also NOT wired: "Block HRMS-0307 SourcingWorkflowTrigger" (AC-4) --
that trigger doesn't exist anywhere in this codebase yet.
is_htd_intake_paused() below is the real, callable gate a future build
of it would check, same "real function, deferred wiring" posture as
every other not-yet-existing consumer this session.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.htd_intake_pause import HtdIntakeStatus, HtdMonthlyMetric, HtdPauseLogEntry
from app.core.logging import logger

CONVERSION_RATE_THRESHOLD = Decimal("0.50")
CORE_CONVERSION_WINDOW_DAYS = 400
MIN_AUDIT_TEXT_LENGTH = 200

logger = logging.getLogger(__name__)

class ResumeValidationError(Exception):
    pass


def _month_bounds(month_start: date) -> tuple:
    first = month_start.replace(day=1)
    if first.month == 12:
        next_month = first.replace(year=first.year + 1, month=1)
    else:
        next_month = first.replace(month=first.month + 1)
    return first, next_month


def calculate_monthly_conversion_rate(
    db: Session, *, tenant_id: Optional[int], month_start: date,
) -> HtdMonthlyMetric:
    """
    AC-1: idempotent per (tenant, month) -- re-running for a month
    already calculated updates the existing row rather than duplicating
    it, same upsert discipline as record_weekly_utilization_metric().
    """
    first, next_month = _month_bounds(month_start)

    cohort = db.query(Employee).filter(
        Employee.tenant_id == tenant_id, Employee.htd_track.is_(True),
        Employee.htd_start_date >= first, Employee.htd_start_date < next_month,
    ).all()
    cohort_size = len(cohort)

    converted = 0
    for employee in cohort:
        if not employee.core_certified or not employee.core_certified_date:
            continue
        if (employee.core_certified_date - employee.htd_start_date).days <= CORE_CONVERSION_WINDOW_DAYS:
            converted += 1

    conversion_rate = Decimal(converted) / Decimal(cohort_size) if cohort_size > 0 else None

    existing = db.query(HtdMonthlyMetric).filter(
        HtdMonthlyMetric.tenant_id == tenant_id, HtdMonthlyMetric.month_start == first,
    ).first()
    if existing:
        existing.cohort_size = cohort_size
        existing.converted = converted
        existing.conversion_rate = conversion_rate
        db.add(existing)
        return existing

    metric = HtdMonthlyMetric(
        tenant_id=tenant_id, month_start=first, cohort_size=cohort_size,
        converted=converted, conversion_rate=conversion_rate,
    )
    db.add(metric)
    return metric


def _get_or_create_status(db: Session, tenant_id: Optional[int]) -> HtdIntakeStatus:
    status = db.query(HtdIntakeStatus).filter(HtdIntakeStatus.tenant_id == tenant_id).first()
    if status is None:
        status = HtdIntakeStatus(tenant_id=tenant_id, is_paused=False)
        db.add(status)
    return status


def check_and_apply_breach(db: Session, *, tenant_id: Optional[int], as_of: Optional[date] = None) -> HtdIntakeStatus:
    """
    AC-2: the two most recently CALCULATED months (not necessarily
    calendar-consecutive if a month was never run) must both exist and
    both be below threshold. A month with cohort_size=0 (conversion_rate
    None) never counts as a breach month -- "insufficient data" is not
    "failing," same convention as everywhere else in this codebase.

    Idempotent: if already paused, re-checking does not write a second
    PAUSED log entry.
    """
    status = _get_or_create_status(db, tenant_id)
    if status.is_paused:
        return status

    recent = (
        db.query(HtdMonthlyMetric)
        .filter(HtdMonthlyMetric.tenant_id == tenant_id)
        .order_by(HtdMonthlyMetric.month_start.desc())
        .limit(2)
        .all()
    )
    if len(recent) < 2:
        return status

    rates = [m.conversion_rate for m in recent]
    if any(r is None for r in rates):
        return status
    if all(r < CONVERSION_RATE_THRESHOLD for r in rates):
        month_labels = ", ".join(f"{m.month_start.strftime('%b %Y')}: {float(m.conversion_rate) * 100:.0f}%" for m in reversed(recent))
        reason = f"Conversion rate below 50% for 2 consecutive months ({month_labels})."
        status.is_paused = True
        status.paused_at = as_of or datetime.utcnow()
        status.pause_reason = reason
        db.add(status)
        db.add(HtdPauseLogEntry(tenant_id=tenant_id, action="PAUSED", reason=reason))

    return status


def is_htd_intake_paused(db: Session, tenant_id: Optional[int]) -> bool:
    status = db.query(HtdIntakeStatus).filter(HtdIntakeStatus.tenant_id == tenant_id).first()
    return bool(status and status.is_paused)


def resume_htd_intake(
    db: Session, *, tenant_id: Optional[int], audit_findings: str, corrective_actions: str, resumed_by: str,
) -> HtdIntakeStatus:
    """AC-5: both fields must independently clear the minimum length --
    no shortcut, no partial credit."""
    if len(audit_findings or "") < MIN_AUDIT_TEXT_LENGTH:
        raise ResumeValidationError(f"Audit findings must be at least {MIN_AUDIT_TEXT_LENGTH} characters.")
    if len(corrective_actions or "") < MIN_AUDIT_TEXT_LENGTH:
        raise ResumeValidationError(f"Corrective actions must be at least {MIN_AUDIT_TEXT_LENGTH} characters.")

    status = _get_or_create_status(db, tenant_id)
    status.is_paused = False
    status.paused_at = None
    status.pause_reason = None
    db.add(status)
    db.add(HtdPauseLogEntry(
        tenant_id=tenant_id, action="RESUMED", audit_findings=audit_findings,
        corrective_actions=corrective_actions, resumed_by=resumed_by,
    ))
    return status
