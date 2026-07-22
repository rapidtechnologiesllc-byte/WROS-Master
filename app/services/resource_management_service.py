"""
Phase 4, Part B -- Resource & Bench Management basics.

See app.models.resource_management for the schema rationale. This
module owns the bench_pool lifecycle, utilization snapshots, the
allocation-conflict audit log, and the Staffing Eligibility Engine that
HRMS-1105 (Part A) will call to pre-filter candidates before ranking.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import (
    AllocationConflictLogEntry,
    BENCH_PERIOD_REASONS,
    BenchPeriod,
    BenchPoolEntry,
    EmployeeUtilizationMetric,
)
from app.models.timesheet import Timesheet

# S-248/HRMS-0504 doc's own alert milestones. Canonical sheet also names
# 90 days; included here too even though the source doc only specifies
# 30/60.
BENCH_AGING_ALERT_DAYS = (30, 60, 90)

# No requirements doc specifies a standard work week for utilization
# math (Part B has none at all) -- 40h/week is this session's plain
# assumption, flagged rather than silently baked in with no comment.
STANDARD_WEEKLY_HOURS = 40

# S-365/HRMS-0521's gate, per 04-RESOURCE-MANAGEMENT.md Part B item 5.
# Reuses the SAME interpretation employee_allocation_service.py already
# established (blocks only IN_PROGRESS/EXTENDED, not NOT_STARTED) rather
# than a second, differently-scoped copy of the same business rule --
# two interpretations of one rule is exactly the kind of drift this
# project's Core-Pull doc calls a defect, not a stylistic choice.
_BUDDY_PROGRAM_BLOCKING_STATUSES = ("IN_PROGRESS", "EXTENDED")


# ---------------------------------------------------------------------------
# Bench pool -- "Mark Employee as Bench" + "Bench Duration & Aging"
# ---------------------------------------------------------------------------

def mark_employee_on_bench(
    db: Session, employee: Employee, *, reason: str = "PROJECT_ENDED",
) -> BenchPoolEntry:
    """
    Upserts this employee's bench_pool row AND opens a bench_periods
    history row (S-246, extended per the real requirement doc found
    this round -- see BenchPeriod's docstring). Idempotent on the
    bench_pool side -- calling this for an employee who's already on
    the bench just returns the existing entry rather than resetting
    available_from, so a redundant call doesn't silently reset their
    bench-aging clock. Idempotent on the bench_periods side too (BR-02:
    only one open period per employee) -- a redundant call does not
    open a second history row.

    reason defaults to PROJECT_ENDED (the existing caller,
    end_allocation(), only ever benches someone because their
    allocation just ended); pass an explicit reason for other entry
    paths (e.g. NEWLY_JOINED for a fresh hire who's never been
    allocated).
    """
    if reason not in BENCH_PERIOD_REASONS:
        raise ValueError(f"reason must be one of {BENCH_PERIOD_REASONS}, got '{reason}'.")

    existing = db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).first()
    if not existing:
        monthly_cost = employee.base_salary_usd_cents or 0
        existing = BenchPoolEntry(
            tenant_id=employee.tenant_id,
            employee_id=employee.id,
            available_from=date.today(),
            skill_tags=employee.current_skills,
            bench_cost_usd_cents=round(monthly_cost / 30) if monthly_cost else None,
        )
        db.add(existing)
        db.flush()

    open_period = (
        db.query(BenchPeriod)
        .filter(BenchPeriod.employee_id == employee.id, BenchPeriod.bench_end_date.is_(None))
        .first()
    )
    if not open_period:
        db.add(BenchPeriod(
            tenant_id=employee.tenant_id, employee_id=employee.id,
            bench_start_date=date.today(), reason_for_bench=reason,
        ))
        db.flush()

    return existing


def remove_employee_from_bench(db: Session, employee: Employee) -> None:
    """Called the moment an employee is allocated off the bench. The
    bench_pool row is deleted, not soft-closed -- it only ever
    represents WHO IS on the bench right now (see BenchPoolEntry's own
    docstring). The bench_periods history row (if one is open) is
    closed instead -- end_date set, cost frozen per BR-01 -- so the
    full episode survives for reporting even though bench_pool itself
    doesn't keep history."""
    db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).delete()

    open_period = (
        db.query(BenchPeriod)
        .filter(BenchPeriod.employee_id == employee.id, BenchPeriod.bench_end_date.is_(None))
        .first()
    )
    if open_period:
        today = date.today()
        days_on_bench = max((today - open_period.bench_start_date).days, 0)
        monthly_cost = employee.base_salary_usd_cents or 0
        open_period.bench_end_date = today
        open_period.bench_cost_usd_cents = (
            round(monthly_cost / 30 * days_on_bench) if monthly_cost else None
        )
        db.add(open_period)


def get_bench_period_history(db: Session, employee_id: str) -> List[BenchPeriod]:
    """Every bench episode for this employee, most recent first --
    S-248's aging/trend reporting and S-255's cumulative cost reporting
    both read this rather than bench_pool (which only ever has the
    current stint, if any)."""
    return (
        db.query(BenchPeriod)
        .filter(BenchPeriod.employee_id == employee_id)
        .order_by(BenchPeriod.bench_start_date.desc())
        .all()
    )


def check_bench_aging_alerts(db: Session, *, tenant_id: Optional[int] = None) -> List[dict]:
    """S-248 BR: idempotent, directly-callable function (same "real
    function, scheduler wiring deferred" posture as every other cron-
    shaped story in this codebase, e.g. HRMS-0901's weekly draft job) --
    not a self-scheduling daily job. Returns one entry per currently-
    open bench period that has crossed a 30/60/90-day milestone,
    computed from BenchPoolEntry.available_from (bench_periods.
    bench_start_date is the same value for the currently-open period,
    but the pool entry is the one HRMS-1105's scan already trusts as
    the live source, so this reads from there for consistency)."""
    alerts = []
    for entry in get_current_bench_pool(db, tenant_id=tenant_id):
        days = get_bench_duration_days(entry)
        if days in BENCH_AGING_ALERT_DAYS:
            alerts.append({
                "employee_id": entry.employee_id,
                "days_on_bench": days,
                "bench_cost_usd_cents": entry.bench_cost_usd_cents,
            })
    return alerts


def get_bench_duration_days(entry: BenchPoolEntry, *, as_of: Optional[date] = None) -> int:
    """Always computed from available_from, never trusted as a stale
    stored value -- see the module docstring's note on HRMS-0804 delay_days."""
    return ((as_of or date.today()) - entry.available_from).days


# ---------------------------------------------------------------------------
# Utilization metrics
# ---------------------------------------------------------------------------

def record_weekly_utilization_metric(
    db: Session, employee: Employee, week_starting_date: date,
) -> EmployeeUtilizationMetric:
    """
    Computes and upserts one employee's utilization snapshot for a given
    week from real APPROVED Timesheet rows. Bench employees never file a
    timesheet (per HRMS-0901's own scope note), so bench_hours here is
    derived as the gap between the standard week and whatever billable
    hours were actually logged -- the only way to represent bench time
    without inventing a parallel "bench timesheet" concept.
    """
    timesheets = (
        db.query(Timesheet)
        .filter(
            Timesheet.employee_id == employee.id,
            Timesheet.week_starting_date == week_starting_date,
            Timesheet.status == "APPROVED",
        )
        .all()
    )
    billable_hours = sum((t.billable_hours or Decimal("0")) for t in timesheets) or Decimal("0")
    bench_hours = max(Decimal(STANDARD_WEEKLY_HOURS) - billable_hours, Decimal("0"))
    utilization_pct = min(
        (billable_hours / Decimal(STANDARD_WEEKLY_HOURS)) * 100, Decimal("100"),
    ) if STANDARD_WEEKLY_HOURS else Decimal("0")

    existing = (
        db.query(EmployeeUtilizationMetric)
        .filter(
            EmployeeUtilizationMetric.employee_id == employee.id,
            EmployeeUtilizationMetric.period_start == week_starting_date,
        )
        .first()
    )
    if existing:
        existing.billable_hours = billable_hours
        existing.bench_hours = bench_hours
        existing.utilization_pct = utilization_pct
        db.add(existing)
        return existing

    metric = EmployeeUtilizationMetric(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        period_start=week_starting_date,
        billable_hours=billable_hours,
        bench_hours=bench_hours,
        utilization_pct=utilization_pct,
    )
    db.add(metric)
    db.flush()
    return metric


def get_current_bench_pool(db: Session, tenant_id: Optional[int] = None) -> List[BenchPoolEntry]:
    """HRMS-1105's 30-minute scan reads this -- 'near-real-time bench-
    pool composition' per that story's own prerequisite on HRMS-0510."""
    query = db.query(BenchPoolEntry)
    if tenant_id is not None:
        query = query.filter(BenchPoolEntry.tenant_id == tenant_id)
    return query.order_by(BenchPoolEntry.available_from.asc()).all()


# ---------------------------------------------------------------------------
# Allocation conflict log
# ---------------------------------------------------------------------------

def log_allocation_conflict(
    db: Session,
    employee: Employee,
    *,
    conflicting_allocation_ids: List[str],
    attempted_utilization_pct: Optional[float],
    existing_utilization_pct: Optional[float],
) -> AllocationConflictLogEntry:
    """Called by employee_allocation_service.allocate_employee_to_project()
    right before it raises AllocationOverCapacity -- a permanent audit
    trail of blocked over-capacity attempts, not a second conflict-
    detection implementation."""
    entry = AllocationConflictLogEntry(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        conflicting_allocation_ids_json=json.dumps(conflicting_allocation_ids),
        attempted_utilization_pct=attempted_utilization_pct,
        existing_utilization_pct=existing_utilization_pct,
    )
    db.add(entry)
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# Staffing Eligibility Engine -- 04-RESOURCE-MANAGEMENT.md Part B item 5
# ---------------------------------------------------------------------------

def is_staffing_eligible(employee: Employee, delivery_engine: str) -> Tuple[bool, Optional[str]]:
    """
    Confirms an employee can even APPEAR in HRMS-1105's ranking for a
    demand of the given delivery_engine -- a read-time pre-filter, not
    the write-time allocate_employee_to_project() gate (which stays
    exactly as-is; this doesn't duplicate or replace it).

    Returns (eligible, reason_if_not).
    """
    if employee.buddy_program_status in _BUDDY_PROGRAM_BLOCKING_STATUSES:
        return False, f"Buddy Program not graduated (status={employee.buddy_program_status})"

    if delivery_engine == "CORE" and not employee.core_certified:
        return False, "Not Core-certified"

    return True, None
