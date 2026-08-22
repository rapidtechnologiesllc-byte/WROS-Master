"""
HRMS-0901 (Timesheet Submission) + HRMS-0902 (Timesheet Approval
Workflow), Phase 2 Domain 4.

Depends on employee_allocations (HRMS-0507) -- a timesheet is always
tied to an active allocation; bench employees never get one (BR-04).
The weekly auto-creation job and the approval-reminder job described in
both stories are NOT wired to a scheduler here -- app.services.
timesheet_service exposes the underlying idempotent functions
(create_weekly_draft, approval reminders would read the same status
field); actually scheduling them (APScheduler, like the existing
interview-reminder jobs in app/api/v1/endpoints/interviews.py) is
follow-up work, not built in this pass.

DISPUTED is included in the status enum for schema completeness (the
doc's own CREATE TABLE lists it) but no code path in this build
transitions a timesheet into it -- that's HRMS-0904's dispute process,
a separate story.
"""
import uuid

from sqlalchemy import (
    CheckConstraint, Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


TIMESHEET_STATUSES = ("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "DISPUTED")
TIMESHEET_ENTRY_TYPES = ("BILLABLE", "NON_BILLABLE", "LEAVE", "HOLIDAY")

MAX_WEEKLY_HOURS = 60  # BR-01
MAX_SUBMISSION_LOOKBACK_WEEKS = 4  # BR-02


class Timesheet(Base):
    __tablename__ = "timesheets"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    # Backlog item, 2026-08-05 (Task<->Timesheet tie): allocation_id is
    # now nullable -- a timesheet backed by internal Task work (an HR
    # ticket, an IT request) has no client allocation to bill against.
    # task_id is the alternative source. Exactly one of the two must be
    # set, enforced by ck_timesheet_allocation_or_task below -- a real
    # structural invariant, not a soft conditional-field rule, so this
    # one IS a DB CHECK constraint (unlike si_partner/business_type on
    # Project, which are service-layer only).
    allocation_id = Column(String(36), ForeignKey("employee_allocations.id"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)

    week_starting_date = Column(Date, nullable=False)  # always a Monday
    total_hours = Column(Numeric(6, 2), nullable=False, default = False)
    billable_hours = Column(Numeric(6, 2), nullable=False, default = False)
    non_billable_hours = Column(Numeric(6, 2), nullable=False, default = False)

    status = Column(
        Enum(*TIMESHEET_STATUSES, name="timesheet_status", native_enum=False, create_constraint=True),
        nullable=False, default="DRAFT",
    )
    submitted_at = Column(DateTime, nullable=True)
    approved_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    # EPIC-P7 client portal field -- schema-only, no client-side approval
    # path exists in this codebase yet.
    client_approver_email = Column(String(300), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "employee_id", "allocation_id", "week_starting_date",
            name="uq_timesheet_per_employee_allocation_week",
        ),
        UniqueConstraint(
            "tenant_id", "employee_id", "task_id", "week_starting_date",
            name="uq_timesheet_per_employee_task_week",
        ),
        CheckConstraint(
            "(allocation_id IS NOT NULL) OR (task_id IS NOT NULL)",
            name="ck_timesheet_allocation_or_task",
        ),
    )


class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    timesheet_id = Column(String(36), ForeignKey("timesheets.id"), nullable=False, index=True)

    entry_date = Column(Date, nullable=False)
    hours = Column(Numeric(4, 2), nullable=False)
    entry_type = Column(
        Enum(*TIMESHEET_ENTRY_TYPES, name="timesheet_entry_type", native_enum=False, create_constraint=True),
        nullable=False, default="BILLABLE",
    )
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("timesheet_id", "entry_date", name="uq_timesheet_entry_per_day"),
        CheckConstraint("hours >= 0 AND hours <= 24", name="ck_timesheet_entry_hours_range"),
    )
