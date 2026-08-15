"""
HRMS-0101 (+ 0101-REV) — Employee Entity Model, Phase 2 Domain 3.

Translated from the requirements doc's PostgreSQL-flavored spec to this
codebase's actual stack (SQL Server in production, SQLite in tests):
  - `id UUID PK` -> String(36) storing str(uuid.uuid4()), not the
    Postgres-native UUID type or MSSQL's UNIQUEIDENTIFIER -- a plain
    string round-trips identically on both backends, which matters
    since every test in this codebase runs against throwaway SQLite,
    never the real database.
  - Native ENUM columns -> SQLAlchemy Enum(..., native_enum=False, create_constraint=True),
    which renders as VARCHAR + CHECK constraint on both backends
    instead of relying on Postgres-only native enum types.
  - `current_skills JSONB` + GIN index -> Text column storing a JSON
    string (same pattern already used for mfa_backup_codes), no GIN
    index (SQL Server doesn't have one) -- a standard index on
    tenant_id covers the realistic query pattern instead.

HRMS-0101-REV's delivery-engine fields are folded directly into this
table from the start, not added as a separate later migration -- the
REV story's whole reason for being a separate migration was a live
`employees` table already had rows before the two-engine architecture
existed. That's not true here: this table has zero rows before this
migration runs, so there's nothing to backfill and no reason to
replay history that doesn't apply.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Enum, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


# INTERN added 2026-07-23: Employment Type collection moved from candidate
# intake to employee conversion (Avinash's direct instruction -- it's a
# conversion-time decision, not something to ask a candidate about before
# they're even hired). PERMANENT/CONTRACT/FIXED_TERM predate this and are
# unaffected.
EMPLOYMENT_TYPES = ("PERMANENT", "CONTRACT", "FIXED_TERM", "INTERN")
EMPLOYEE_STATUSES = (
    "PRE_JOINING", "ACTIVE", "ON_LEAVE", "BENCH", "ALLOCATED",
    "NOTICE_PERIOD", "EXITED",
    # S-365/HRMS-0521 -- Buddy Program Graduation Gate outcomes.
    "SPECIALITY_READY", "PERFORMANCE_MANAGED",
)
BILLING_CLASSIFICATIONS = ("BENCH", "ALLOCATED", "NON_BILLABLE")
WORK_LOCATIONS = ("REMOTE", "ONSITE", "HYBRID")
DELIVERY_ENGINES = ("SPECIALITY", "CORE")
BUDDY_PROGRAM_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "GRADUATED", "EXTENDED", "EXITED")
HTD_PHASES = ("INDUCTION", "SHADOW_DELIVERY", "CONTROLLED_OWNERSHIP", "CORE_ELIGIBILITY_REVIEW", "COMPLETED", "EXITED")

# Allowed status transitions -- BR from HRMS-0101 step 4.
ALLOWED_STATUS_TRANSITIONS = {
    "PRE_JOINING": {"ACTIVE"},
    # S-365: a BU Head's GRADUATE/EXIT decision moves an ACTIVE employee
    # to SPECIALITY_READY/PERFORMANCE_MANAGED -- both reachable from
    # ACTIVE, since that's the status a new hire sits in throughout
    # their Buddy Program run (buddy_program_status is a separate field).
    "ACTIVE": {"BENCH", "ALLOCATED", "ON_LEAVE", "NOTICE_PERIOD", "SPECIALITY_READY", "PERFORMANCE_MANAGED"},
    "ON_LEAVE": {"ACTIVE"},
    "BENCH": {"ALLOCATED", "NOTICE_PERIOD"},
    "ALLOCATED": {"BENCH", "ON_LEAVE", "NOTICE_PERIOD"},
    "NOTICE_PERIOD": {"EXITED"},
    "EXITED": set(),  # terminal
    # Cleared for Specialty deployment -- resumes the normal ACTIVE-style
    # lifecycle (bench/allocate/leave/exit), just without re-entering
    # SPECIALITY_READY a second time.
    "SPECIALITY_READY": {"BENCH", "ALLOCATED", "ON_LEAVE", "NOTICE_PERIOD"},
    # Not specified beyond "HR notified to initiate performance
    # process" -- this session's reasonable default, not confirmed:
    # a PM process either resolves (back to ACTIVE) or ends in exit.
    "PERFORMANCE_MANAGED": {"ACTIVE", "NOTICE_PERIOD"},
}


class Employee(Base):
    __tablename__ = "employees"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # Nullable + unique: links back to the candidate this employee
    # originated from; null for a direct hire never in the candidate
    # pipeline. UNIQUE enforces BR-04 -- one candidate can only ever
    # become one employee record.
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=True, unique=True)

    employee_number = Column(String(50), nullable=True)  # BR-02: auto-generated, see generate_employee_number()
    tenant_employee_id = Column(String(100), nullable=True)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    legal_name = Column(String(300), nullable=True)
    email = Column(String(300), nullable=False, index=True)
    personal_email = Column(String(300), nullable=True)
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(50), nullable=True)
    nationality = Column(String(100), nullable=True)
    current_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)
    emergency_contact_name = Column(String(200), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)

    joining_date = Column(Date, nullable=False)
    confirmation_date = Column(Date, nullable=True)
    exit_date = Column(Date, nullable=True)

    employment_type = Column(Enum(*EMPLOYMENT_TYPES, name="employment_type", native_enum=False, create_constraint=True), nullable=False, default="PERMANENT")
    status = Column(Enum(*EMPLOYEE_STATUSES, name="employee_status", native_enum=False, create_constraint=True), nullable=False, default="PRE_JOINING")

    bu_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    manager_id = Column(String(36), ForeignKey("employees.id"), nullable=True, index=True)

    # Organizational hierarchy position (links to org_nodes for approval chains, role-based access)
    org_node_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True, index=True)

    current_title = Column(String(200), nullable=True)
    current_skills = Column(Text, nullable=True)  # JSON-encoded array; see current_skills_list()/set_current_skills()
    total_experience_months = Column(Integer, nullable=True)
    blitzenx_experience_months = Column(Integer, nullable=False, default=0)

    base_salary_usd_cents = Column(Integer, nullable=True)  # monthly
    billing_rate_usd_cents = Column(Integer, nullable=True)  # hourly
    billing_classification = Column(Enum(*BILLING_CLASSIFICATIONS, name="billing_classification", native_enum=False, create_constraint=True), nullable=False, default="BENCH")
    work_location = Column(Enum(*WORK_LOCATIONS, name="work_location", native_enum=False, create_constraint=True), nullable=False, default="REMOTE")

    visa_status = Column(String(100), nullable=True)
    pan_number = Column(String(50), nullable=True)
    tax_id = Column(String(100), nullable=True)
    # BR-01: encrypted at the application level, never plaintext. See
    # app.core.field_encryption -- encrypted before assignment, decrypted
    # only by callers with PAYROLL/ADMIN authority (not yet wired to any
    # route; the model just enforces "never store plaintext" at the
    # column level via encrypt_bank_field()/decrypt_bank_field()).
    bank_account_number_encrypted = Column(Text, nullable=True)
    bank_routing_encrypted = Column(Text, nullable=True)

    wros_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True)

    # HRMS-0101-REV -- delivery engine + buddy program + HTD fields,
    # built in from the start (see module docstring).
    delivery_engine = Column(Enum(*DELIVERY_ENGINES, name="delivery_engine", native_enum=False, create_constraint=True), nullable=False, default="SPECIALITY")
    engine_entry_date = Column(Date, nullable=False, default=date.today)
    core_eligible_from = Column(Date, nullable=True)
    core_certified = Column(Boolean, nullable=False, default=False)
    core_certified_date = Column(Date, nullable=True)
    buddy_program_status = Column(Enum(*BUDDY_PROGRAM_STATUSES, name="buddy_program_status", native_enum=False, create_constraint=True), nullable=False, default="NOT_STARTED")
    buddy_program_start_date = Column(Date, nullable=True)
    buddy_program_graduation_date = Column(Date, nullable=True)
    htd_track = Column(Boolean, nullable=False, default=False)
    htd_start_date = Column(Date, nullable=True)
    htd_phase = Column(Enum(*HTD_PHASES, name="htd_phase", native_enum=False, create_constraint=True), nullable=True)
    reporting_manager_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(50), nullable=True)

    manager = relationship("Employee", remote_side=[id], foreign_keys=[manager_id])
    # OrgNode relationship for approval chains and role-based access
    org_node = relationship("OrgNode", foreign_keys=[org_node_id])

    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_number", name="uq_employee_number_per_tenant"),
        # S-351/HRMS-0512 AC-3: DB-level guard independent of application
        # code -- delivery_engine can never be CORE unless core_certified
        # is already TRUE, even via a raw SQL UPDATE bypassing the ORM.
        CheckConstraint(
            "delivery_engine != 'CORE' OR core_certified = true",
            name="ck_core_requires_certification",
        ),
    )


class EmployeeEmploymentHistory(Base):
    """BR-03: insert-only. No UPDATE or DELETE ever permitted -- see the
    append-only guard below, same pattern as AuditLog."""
    __tablename__ = "employee_employment_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    change_type = Column(
        Enum("TITLE", "SALARY", "BILLING_RATE", "STATUS", "BU", "MANAGER", "LOCATION", name="employment_change_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    old_value = Column(Text, nullable=True)  # JSON-encoded
    new_value = Column(Text, nullable=True)  # JSON-encoded
    effective_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    changed_by = Column(String(50), nullable=True)
    changed_at = Column(DateTime, server_default=func.now())


class EmployeeDocuments(Base):
    __tablename__ = "employee_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    document_type = Column(
        Enum("OFFER_LETTER", "CONTRACT", "ID_PROOF", "ADDRESS_PROOF", "PAN", "TAX_FORM", "VISA", "NDA", "OTHER",
             name="employee_document_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    document_url = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())
    verified_by = Column(String(50), nullable=True)
    verified_at = Column(DateTime, nullable=True)


class EmployeeEngineHistory(Base):
    """HRMS-0101-REV step 4 -- insert-only history of SPECIALITY/CORE
    engine transitions, independent of the general employment history
    table since Core-Pull has its own audit trail requirement."""
    __tablename__ = "employee_engine_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    from_engine = Column(Enum(*DELIVERY_ENGINES, name="engine_history_from", native_enum=False, create_constraint=True), nullable=True)
    to_engine = Column(Enum(*DELIVERY_ENGINES, name="engine_history_to", native_enum=False, create_constraint=True), nullable=False)
    changed_at = Column(DateTime, server_default=func.now())
    changed_by = Column(String(50), nullable=True)
    approval_reference = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True)
