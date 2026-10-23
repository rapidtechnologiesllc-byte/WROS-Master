"""
HRMS-0507 -- Employee Allocation Records.

This is deliberately the minimal "allocate employee to project" data
primitive, not Phase 4's full Resource Management build
(docs/build-package/04-RESOURCE-MANAGEMENT.md is explicit that HRMS-1105's
agent, the Core-Pull engine HRMS-0312, and the 40-person Specialty floor
guard are Phase 4, "unlocked in parallel with Phase 3"). What IS built
here -- the table itself, and the single human-driven allocate/end
action -- is exactly what that same Phase 4 doc calls out as the
foundational piece Phase 4's agent depends on ("Part B", item 3:
"Allocate Employee to Project ... always a distinct human (RM) decision,
never automatic"). Built now because HRMS-0901 Timesheet Submission
genuinely can't exist without it (timesheets are always tied to an
active allocation).

FK note: 02-DATA-MODEL.md's Domain 3 sketch names the column
`project_id`, but this codebase had no `projects` table when this model
was first built (Domain 4, EPIC-08). Linked to `demands.id` at the time
-- kept, since it's still meaningful history (what sourcing decision
led here) -- and now ALSO linked to `projects.id` (nullable, since an
allocation predating HRMS-0801 or made outside a tracked project has
none) once HRMS-0801 landed. `role`/`utilization_pct` double as HRMS-
0803's "role"/"allocation_pct" fields -- same concept, no new column
needed for the latter.
"""
import logging
import uuid
from datetime import date as date_type, datetime

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, func, text,
)

from app.models.base import Base
from app.models.project import SI_PARTNERS

def _new_uuid() -> str:
    return str(uuid.uuid4())

# CORE_PULLED (S-353/HRMS-0514): distinct from a normal ENDED -- a Specialty
# allocation that was cut short by a same-day Core-Pull transfer, not a
# regular project end. Kept separate so reporting can tell the two apart
# without inferring intent from end_date proximity to another allocation's
# start_date.
# PENDING_MARGIN_APPROVAL (CEO 2026-10-23): a placement priced below the margin floor waits for
# a BU Head / Partner decision; it is not ACTIVE, so no timesheet (and so no invoice) can be made
# for it. MARGIN_REJECTED is that decision's "no": the placement never started.
ALLOCATION_STATUSES = ("ACTIVE", "ENDED", "CORE_PULLED", "PENDING_MARGIN_APPROVAL", "MARGIN_REJECTED")
# Statuses that hold the employee: an allocation awaiting margin approval still books the
# person, so nobody double-books them while the approver decides.
HOLDING_STATUSES = ("ACTIVE", "PENDING_MARGIN_APPROVAL")
# Renewal pipeline (CEO 2026-10-23): where the extension conversation for this term stands.
RENEWAL_STATUSES = ("NOT_STARTED", "IN_DISCUSSION", "EXTENDED", "ROLLING_OFF")
# AllocationChange: CREATE (the placement), EDIT (PATCH /allocations/{id}), RENEWAL (renewal
# status / owner / note)
CHANGE_TYPES = ("CREATE", "EDIT", "RENEWAL")
CHANGE_STATUSES = ("APPLIED", "PENDING_APPROVAL", "REJECTED")
# Who must approve a placement below the margin floor (levels from settings, never names)
APPROVAL_LEVELS = ("BU_HEAD", "PARTNER")

logger = logging.getLogger(__name__)

class EmployeeAllocation(Base):
    __tablename__ = "employee_allocations"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    demand_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=False, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    # HRMS-0803 -- nullable: not every allocation is tied to a tracked project.
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)
    role = Column(String(512), nullable=True)

    status = Column(
        Enum(*ALLOCATION_STATUSES, name="employee_allocation_status", native_enum=False, create_constraint=True),
        nullable=False, default="ACTIVE",
    )
    utilization_pct = Column(Numeric(5, 2), nullable=True)
    start_date = Column(Date, nullable=False, default=date_type.today)
    end_date = Column(Date, nullable=True)

    client_reporting_manager_contact_id = Column(String(512), ForeignKey("client_contacts.id"), nullable=True)
    # HRMS-0902 -- the RM/Admin who approves this allocation's timesheets.
    timesheet_approver_email = Column(String(300), nullable=True)
    billing_rate_usd_cents = Column(Integer, nullable=True)
    # Billable client time or non-billable (internal) time; defaults from the project. Entries on a
    # non-billable allocation are NON_BILLABLE and never invoiced (CEO 2026-10-22)
    billable = Column(Boolean, nullable=False, default=True, server_default="true")
    # S-358/HRMS-0519 -- denormalized copy of Project.si_partner at
    # allocation-creation time (per the doc's own "enables fast 'who is
    # at PwC right now' queries without project table joins" rationale).
    # Nullable: allocations with no project, or a CORE-engine project
    # with no si_partner, legitimately have none.
    si_partner = Column(
        Enum(*SI_PARTNERS, name="employee_allocation_si_partner", native_enum=False, create_constraint=True),
        nullable=True,
    )

    # Renewal pipeline for the current term (reset to NOT_STARTED when the term is extended).
    # renewal_owner_user_id None = the default owner (client account manager, else BU Head):
    # app.services.allocation_renewal_service.effective_owner
    renewal_status = Column(
        Enum(*RENEWAL_STATUSES, name="employee_allocation_renewal_status", native_enum=False, create_constraint=True),
        nullable=False, default="NOT_STARTED", server_default="NOT_STARTED",
    )
    renewal_owner_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True, index=True)
    renewal_note = Column(Text, nullable=True)
    renewal_updated_at = Column(DateTime, nullable=True)
    renewal_updated_by = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    # Margin at the last placement check (app.services.margin_guard_service): percent of the bill
    # rate, and the check's outcome (OK, BELOW_MIN, BELOW_HARD_FLOOR, NO_FLOOR_CONFIGURED,
    # NO_COST_DATA, NO_BILL_RATE, NOT_BILLABLE). Null on allocations made before the guard.
    margin_pct = Column(Numeric(7, 2), nullable=True)
    margin_check = Column(String(40), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AllocationChange(Base):
    """Allocation history (CEO 2026-10-23): who changed what, when, old -> new and why. One row
    per placement (CREATE), edit (EDIT) and renewal update (RENEWAL). An edit below the margin
    floor waits here (PENDING_APPROVAL) and changes nothing on the allocation until approved; a
    bill-rate change applies from effective_from, so weeks before it keep the old rate on
    invoices and in the P&L (employee_allocation_service.RateHistory)."""
    __tablename__ = "allocation_changes"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    allocation_id = Column(String(512), ForeignKey("employee_allocations.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    change_type = Column(Enum(*CHANGE_TYPES, name="allocation_change_type", native_enum=False, create_constraint=True),
                         nullable=False)
    status = Column(Enum(*CHANGE_STATUSES, name="allocation_change_status", native_enum=False, create_constraint=True),
                    nullable=False, default="APPLIED")
    # {field: value} of the changed fields only; dates as ISO strings
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=False)
    effective_from = Column(Date, nullable=True)
    reason = Column(Text, nullable=False)
    changed_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True, index=True)
    # client-side clock: several changes in one transaction still order correctly
    changed_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    # the margin check of the proposed values, and the floor it was held against
    margin_pct = Column(Numeric(7, 2), nullable=True)
    margin_check = Column(String(40), nullable=True)
    loaded_hourly_cost_usd_cents = Column(Integer, nullable=True)
    margin_policy_id = Column(Integer, ForeignKey("margin_policies.id", ondelete="SET NULL"), nullable=True)
    min_margin_pct = Column(Numeric(6, 2), nullable=True)
    hard_floor_pct = Column(Numeric(6, 2), nullable=True)

    approval_level = Column(Enum(*APPROVAL_LEVELS, name="allocation_change_approval_level", native_enum=False,
                                 create_constraint=True), nullable=True)
    approver_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    decided_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_reason = Column(Text, nullable=True)

    __table_args__ = (
        # one change awaiting approval per allocation: a second edit waits for the first decision
        Index("uq_allocation_change_one_pending", "allocation_id", unique=True,
              postgresql_where=text("status = 'PENDING_APPROVAL'")),
    )


class AllocationRenewalAlert(Base):
    """One renewal alert task per allocation, term (its end date) and threshold (days before the
    end, settings.RENEWAL_ALERT_DAYS): the daily job never raises the same alert twice. A new
    term (the end date moved) gets its own alerts."""
    __tablename__ = "allocation_renewal_alerts"
    __table_args__ = (UniqueConstraint("allocation_id", "end_date", "threshold_days",
                                       name="uq_allocation_renewal_alert"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    allocation_id = Column(String(512), ForeignKey("employee_allocations.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    threshold_days = Column(Integer, nullable=False)
    # the task raised for this alert (None for a threshold passed together with a closer one:
    # one task covers both)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
