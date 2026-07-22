"""
Phase 4, Part B -- Resource & Bench Management basics.

`04-RESOURCE-MANAGEMENT.md` is explicit that no requirements doc exists
yet for this 11-story cluster -- it's the minimum viable schema/behavior
foundation Part A's stories (HRMS-1105, S-353/HRMS-0514, S-373, S-372)
actually need to run against. Building this FIRST despite the phase
doc's own "Part A builds first" framing, since Part A's own text admits
the contradiction: "HRMS-1105 can't rank or detect anything without a
real bench pool to query."

bench_pool: one row per employee CURRENTLY on the bench (not a history
table -- see mark_employee_on_bench()/remove_employee_from_bench() in
app.services.resource_management_service). bench_duration_days is
deliberately NOT a stored column here -- storing it would need a
periodic recompute job to stay accurate; it's derived from
available_from at read time instead (same "never a stale stored value"
discipline as HRMS-0804's delay_days).

employee_utilization_metrics: a per-employee-per-week utilization
snapshot. No requirements doc specifies the exact computation -- built
from real Timesheet data (billable_hours) against a standard
40-hour week baseline, the simplest reading that doesn't invent a
parallel "bench timesheet" concept bench employees don't have.

allocation_conflict_log: permanent record of every time
allocate_employee_to_project()'s existing AllocationOverCapacity check
(HRMS-0803/HRMS-0508 -- already built, not duplicated here) actually
blocks an attempt, for audit/reporting visibility.
"""
import uuid
from datetime import datetime as datetime_type

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class BenchPoolEntry(Base):
    """One row per employee currently on the bench. Deleted when they're
    allocated again -- see remove_employee_from_bench(); a fresh row is
    created each time they re-enter the bench, so bench_duration always
    reflects the CURRENT bench stint, not a cumulative lifetime total."""

    __tablename__ = "bench_pool"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, unique=True, index=True)

    available_from = Column(Date, nullable=False)
    # JSON-encoded array, mirrors Employee.current_skills's own convention.
    skill_tags = Column(Text, nullable=True)
    # Daily cost of this employee sitting on the bench -- derived from
    # base_salary_usd_cents at the moment they enter the bench (a monthly
    # figure / ~30 days), not recomputed daily; a raise mid-bench-stint
    # doesn't retroactively change what this stint has cost so far.
    bench_cost_usd_cents = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())


class EmployeeUtilizationMetric(Base):
    """Per-employee-per-week utilization snapshot, computed from real
    Timesheet data. See record_weekly_utilization_metric()."""

    __tablename__ = "employee_utilization_metrics"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)

    period_start = Column(Date, nullable=False)  # always a Monday, matches Timesheet.week_starting_date
    utilization_pct = Column(Numeric(5, 2), nullable=False)
    billable_hours = Column(Numeric(6, 2), nullable=False)
    bench_hours = Column(Numeric(6, 2), nullable=False)

    created_at = Column(DateTime, server_default=func.now())


class AllocationConflictLogEntry(Base):
    """Permanent record of a blocked over-capacity allocation attempt --
    written by allocate_employee_to_project() itself (employee_allocation_
    service.py) right before it raises AllocationOverCapacity, not a
    second/parallel conflict-detection implementation."""

    __tablename__ = "allocation_conflict_log"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)

    conflicting_allocation_ids_json = Column(Text, nullable=False)  # JSON-encoded array of EmployeeAllocation.id
    attempted_utilization_pct = Column(Numeric(5, 2), nullable=True)
    existing_utilization_pct = Column(Numeric(5, 2), nullable=True)
    resolution = Column(String(50), nullable=True)  # NULL until someone actually resolves it
    resolved_at = Column(DateTime, nullable=True)

    detected_at = Column(DateTime, server_default=func.now())
