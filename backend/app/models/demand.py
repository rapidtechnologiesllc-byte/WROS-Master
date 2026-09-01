"""
HRMS-0103 — Demand / Job Requisition Management, Phase 2 Domain 2/4.

Same SQL-Server/SQLite-portable translation conventions as
app.models.employee/client.

Note: this is a genuinely new entity, distinct from the existing `Jobs`
table (app.models.user.Jobs) -- Jobs was built for the onboarding
module's own recruiting flow and doesn't have a client_id FK, a demand
state machine, or the bench-first/sourcing gating fields this spec
calls for. Per this session's confirmed direction, `demands` is built
as its own table rather than retrofitting Jobs -- reconciling the two
(or migrating Jobs data into demands) is a separate decision, flagged
in the developer handoff, not resolved by silently picking one here.
"""
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.employee import DELIVERY_ENGINES


def _new_uuid() -> str:
    return str(uuid.uuid4())


WORK_LOCATIONS = ("REMOTE", "ONSITE", "HYBRID")
EMPLOYMENT_TYPES = ("W2_FULLTIME",)  # BR-01: the only allowed value, R-03
INTERVIEW_TYPES = ("L1_ONLY", "L1_AND_L2")
URGENCY_LEVELS = ("IMMEDIATE", "HIGH", "NORMAL", "FLEXIBLE")
DEMAND_STATUSES = ("DRAFT", "OPEN", "IN_PROGRESS", "FILLED", "CANCELLED", "ON_HOLD")
# HRMS-0210 BR-0210-01: a tag, not a schema branch -- opportunity-
# originated demands get identical sourcing/bench-first/allocation
# treatment to any other demand.
DEMAND_SOURCE_TYPES = ("DIRECT", "OPPORTUNITY")

# HRMS-0103 step 3 -- allowed status transitions.
ALLOWED_DEMAND_TRANSITIONS = {
    "DRAFT": {"OPEN"},
    "OPEN": {"IN_PROGRESS", "ON_HOLD", "CANCELLED"},
    "IN_PROGRESS": {"FILLED", "ON_HOLD", "CANCELLED"},
    "ON_HOLD": {"OPEN", "IN_PROGRESS", "CANCELLED"},
    "FILLED": set(),      # terminal
    "CANCELLED": set(),   # terminal
}


class Demand(Base):
    __tablename__ = "demands"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)

    job_title = Column(String(300), nullable=False)
    job_description = Column(Text, nullable=True)
    required_skills = Column(Text, nullable=False)      # JSON-encoded array
    nice_to_have_skills = Column(Text, nullable=True)   # JSON-encoded array, default '[]'
    min_experience_years = Column(Numeric(4, 1), nullable=False)
    max_experience_years = Column(Numeric(4, 1), nullable=True)

    work_location = Column(Enum(*WORK_LOCATIONS, name="demand_work_location", native_enum=False, create_constraint=True), nullable=False)
    job_location = Column(String(512), nullable=True)
    domain = Column(String(512), nullable=True)

    # BR-01 / R-03: hardcoded, no other value ever allowed -- see also
    # the CHECK constraint added in the migration for a DB-level guard
    # independent of application code, same discipline as delivery_engine.
    employment_type = Column(Enum(*EMPLOYMENT_TYPES, name="demand_employment_type", native_enum=False, create_constraint=True), nullable=False, default="W2_FULLTIME")
    interview_type_required = Column(Enum(*INTERVIEW_TYPES, name="demand_interview_type", native_enum=False, create_constraint=True), nullable=False, default="L1_AND_L2")

    headcount = Column(Integer, nullable=False, default = True)
    positions_filled = Column(Integer, nullable=False, default = False)

    billing_rate_usd_cents = Column(Integer, nullable=True)
    budget_min_usd_cents = Column(Integer, nullable=True)
    budget_max_usd_cents = Column(Integer, nullable=True)

    required_start_date = Column(Date, nullable=True)
    urgency = Column(Enum(*URGENCY_LEVELS, name="demand_urgency", native_enum=False, create_constraint=True), nullable=False, default="NORMAL")
    status = Column(Enum(*DEMAND_STATUSES, name="demand_status", native_enum=False, create_constraint=True), nullable=False, default="DRAFT")

    # BR-02 / R-04: sourcing_enabled (LinkedIn) cannot be set True unless
    # bench_first_checked is already True -- enforced in
    # app.services.demand_service.enable_sourcing(), not by hand-setting
    # the column, the same one-sanctioned-path discipline as everywhere
    # else in this codebase.
    sourcing_enabled = Column(Boolean, nullable=False, default=False)
    bench_first_checked = Column(Boolean, nullable=False, default=False)

    assigned_recruiter_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)
    assigned_bu_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    # S-353/HRMS-0514 (Core-Pull) + S-372/HRMS-0528 (Confirmed vs Potential)
    # both need to know which engine a demand belongs to -- reuses
    # Employee.DELIVERY_ENGINES rather than a second enum, same "one
    # vocabulary" discipline as the rest of this codebase. Defaults to
    # SPECIALITY, matching Employee's own default and this platform's
    # "Core is the exception, not the default" posture.
    delivery_engine = Column(
        Enum(*DELIVERY_ENGINES, name="demand_delivery_engine", native_enum=False, create_constraint=True),
        nullable=False, default="SPECIALITY",
    )

    # S-372/HRMS-0528 -- unifies the doc's "Confirmed" (SOW already signed)
    # and "Potential" (interview first, SOW later) paths into one status:
    # both converge on CONFIRMED the moment a real sow_reference is
    # recorded. See app.models.demand_confirmation for the per-candidate
    # alignment-call/fit-confirmation state this status gates.
    confirmation_status = Column(
        Enum("POTENTIAL", "CONFIRMED", "CANCELLED", name="demand_confirmation_status", native_enum=False, create_constraint=True),
        nullable=False, default="POTENTIAL",
    )
    sow_reference = Column(String(512), nullable=True)
    sow_received_date = Column(Date, nullable=True)

    # HRMS-0210/0211 -- opportunity-originated role demands. opportunity_id
    # is nullable: most demands aren't opportunity-sourced.
    opportunity_id = Column(String(512), ForeignKey("opportunities.id"), nullable=True, index=True)
    # HRMS-0805 -- links this demand's role requirement to the project
    # it's being staffed for, so unfilled-role gaps can be computed by
    # joining this demand against EmployeeAllocation.project_id. Nullable:
    # most demands aren't tied to a specific tracked project.
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)
    source_type = Column(
        Enum(*DEMAND_SOURCE_TYPES, name="demand_source_type", native_enum=False, create_constraint=True),
        nullable=False, default="DIRECT",
    )
    # Total engagement length this role represents, in hours -- feeds
    # revenue_potential_usd_cents below (HRMS-0211: bill_rate * duration * quantity,
    # quantity mapping to the existing `headcount` field rather than a
    # separate column, since headcount already means exactly that).
    duration_hours = Column(Integer, nullable=True)
    # HRMS-0211 BR-0211-01: recomputed on every write to billing_rate_usd_cents,
    # duration_hours, or headcount -- never a stale one-time snapshot. See
    # app.services.opportunity_service.recalculate_revenue_potential().
    revenue_potential_usd_cents = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(String(512), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # Spec says UNIQUE on (tenant_id, client_id, job_title, status='OPEN')
        # -- a partial/conditional unique index isn't portable across
        # SQLite/SQL Server the same way; enforced instead in
        # app.services.demand_service.create_demand() at the application
        # layer, checked before insert.
    )


class DemandHistory(Base):
    """Insert-only, same immutable pattern as employee/client history."""
    __tablename__ = "demand_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    change_type = Column(
        Enum("STATUS", "RECRUITER", "URGENCY", "HEADCOUNT", name="demand_change_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    changed_by = Column(String(512), nullable=True)
    changed_at = Column(DateTime, server_default=func.now())
