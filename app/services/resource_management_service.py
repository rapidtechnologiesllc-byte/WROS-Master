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
    BenchPoolEntry,
    EmployeeUtilizationMetric,
)
from app.models.timesheet import Timesheet

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

def mark_employee_on_bench(db: Session, employee: Employee) -> BenchPoolEntry:
    """
    Upserts this employee's bench_pool row. Idempotent -- calling this
    for an employee who's already on the bench just returns the
    existing entry rather than resetting available_from, so a redundant
    call doesn't silently reset their bench-aging clock.
    """
    existing = db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).first()
    if existing:
        return existing

    monthly_cost = employee.base_salary_usd_cents or 0
    entry = BenchPoolEntry(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        available_from=date.today(),
        skill_tags=employee.current_skills,
        bench_cost_usd_cents=round(monthly_cost / 30) if monthly_cost else None,
    )
    db.add(entry)
    db.flush()
    return entry


def remove_employee_from_bench(db: Session, employee: Employee) -> None:
    """Called the moment an employee is allocated off the bench. The row
    is deleted, not soft-closed -- bench_pool only ever represents WHO
    IS on the bench right now; historical bench stints are reconstructed
    from EmployeeEmploymentHistory's STATUS change log if ever needed,
    not duplicated here."""
    db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).delete()


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
