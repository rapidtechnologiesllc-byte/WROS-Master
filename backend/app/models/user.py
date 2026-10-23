from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func, Boolean, JSON, Enum, Numeric, event
from sqlalchemy.orm import relationship, synonym
import logging
from app.models.base import Base

# S-039/HRMS-0439 -- real values, no native DB enum (SQL Server, same
# native_enum=False/create_constraint=True convention Candidate.employment_type
# and app.models.client's enums already use).
JOB_URGENCY_LEVELS = ("IMMEDIATE", "HIGH", "NORMAL", "FLEXIBLE")
JOB_WORK_LOCATIONS = ("REMOTE", "ONSITE", "HYBRID")
logger = logging.getLogger(__name__)

class Users(Base):
    __tablename__ = "users"
    UserID = Column(String(512), primary_key=True, index=True)
    UserRole = Column(String(512), nullable=False)
    UserName = Column(String(150), nullable=True)
    UserEmail = Column(String(512), unique=True, nullable=False, index=True)
    UserPassword = Column(String(512), nullable=False)
    password_reset_required = Column(Boolean, nullable=False, default=True, index=True)  # Force password change on first login
    CreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    # RBAC — single role template per user (replaces UserRole junction table)
    # PRODUCTION SAFETY: role_template_id MUST be set, never allow None
    role_template_id = Column(Integer, ForeignKey("role_templates.id"), nullable=False, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    job_title = Column(String(150), nullable=True)  # e.g., "CEO", "Developer", "HR Manager"
    department_id = Column(String(512), ForeignKey("departments.id"), nullable=True, index=True)
    # The user's own seat in the org chart (created alongside the account)
    org_node_id = Column(String(512), ForeignKey("org_nodes.id", use_alter=True, name="fk_users_org_node_id"), nullable=True, index=True)
    # Delivery center (locations table) the user works out of
    location_id = Column(String(512), ForeignKey("locations.id"), nullable=True, index=True)
    # PRODUCTION SAFETY: tenant_id MUST be set, never allow None. Default to 1
    # All new users get tenant_id from creator's tenant (fallback to 1)
    # Every tenant-scoped query must filter on this column via app.core.tenant_context,
    # never trust a tenant id supplied by the caller.
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, server_default="1", default=1, index=True)
    # Phase 1 B3 — MFA. mfa_enabled starts False for every existing row;
    # mfa_secret is populated at enrollment, never before. See
    # app.core.mfa -- enforcement itself is behind a separate,
    # off-by-default feature flag, so adding these columns changes no
    # existing behavior on its own.
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret = Column(String(64), nullable=True)
    mfa_backup_codes = Column(Text, nullable=True)  # JSON-encoded list of hashed codes
    # Backlog item, 2026-08-05 -- email OTP, supplementing the TOTP flow
    # above (see app.core.mfa's EMAIL_OTP_* section). Both nullable and
    # only ever populated at the moment a code is issued; cleared again
    # once verified or expired -- never a long-lived stored secret the
    # way mfa_secret is.
    email_otp_code_hash = Column(String(64), nullable=True)
    email_otp_expires_at = Column(DateTime, nullable=True)
    # EPIC-14/S-435 (HRMS-1408) -- Candidate & Employee Lifecycle
    # Communication Linking. Tracks the high-water mark for this user's
    # M365 mail sync (app.services.msgraph_mail_sync_service) so each
    # sync pass only fetches messages sent/received since the last one,
    # not the user's entire mailbox history every time. Null means
    # never synced -- the first sync uses a short default lookback
    # window instead of a full-mailbox pull.
    msgraph_mail_last_synced_at = Column(DateTime, nullable=True)
    # HRMS-0113 BR-0113-03 -- business-hours notification gating needs each
    # recipient's local timezone. HRMS-0121 (Locale & Currency Config), the
    # story this was supposed to come from, doesn't exist in this codebase.
    # IANA tz name (e.g. "Asia/Kolkata"); every existing row backfills to
    # BlitzenX's primary timezone, same default already hardcoded for
    # interview reminders in app/api/v1/endpoints/interviews.py.
    timezone = Column(String(64), nullable=False, server_default="Asia/Kolkata", default="Asia/Kolkata")
    # Per-staff WhatsApp Business number for candidate-facing conversations
    # (extends HRMS-0410's owner_type/owner_id ownership model -- see
    # app.services.whatsapp_routing_service). Nullable: not every staff
    # member has one registered; conversations they own fall back to the
    # tenant's shared/Thunder number. E.164 format (e.g. "+14155550100").
    whatsapp_number = Column(String(20), nullable=True, unique=True)
    # S-011/HRMS-0411 -- per-tenant Thunder identity config. tenant_id
    # throughout candidate_ai.py/whatsapp_routing_service is genuinely
    # this table's UserID (the org owner), not app.models.tenant.Tenant
    # -- see wros_build_conventions memory on this pre-existing
    # inconsistency; these columns live where "tenant_id" actually
    # resolves in this subsystem, not on the separate Tenant table.
    # Nullable: assign_ai_agent() falls back to the hardcoded
    # AI_AGENT_NAME/AI_AGENT_PERSONA defaults when unset (BR-02 -- an
    # agent name must never reach a candidate blank).
    ai_agent_name = Column(String(512), nullable=True)
    ai_agent_persona = Column(Text, nullable=True)
    # S-065/HRMS-0465 -- no system_configuration table exists in this
    # codebase (same repeated gap every prior story flagged) -- this is
    # a real, per-recruiter toggle column, same posture as mfa_enabled
    # above. Send time itself is a module constant (08:00 local, see
    # daily_digest_service.py), not separately configurable -- no
    # admin UI asked for a time picker beyond the on/off toggle this
    # story's own UI fields table actually specifies as required.
    digest_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    # S-075/HRMS-0475 -- global per-tenant Thunder kill switch (BR-03:
    # takes precedence over every individual conversation's own
    # is_thunder_paused). Same "tenant_id genuinely resolves to this
    # table's own UserID" convention as ai_agent_name/digest_enabled above.
    thunder_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    # User Lifecycle Management — termination tracking
    terminated_at = Column(DateTime(timezone=False), nullable=True, index=True)
    terminated_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True, index=True)

    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id], lazy="select")
    department = relationship("Department", foreign_keys=[department_id], lazy="select")
    role_template = relationship("RoleTemplate", foreign_keys=[role_template_id], lazy="select")
    terminated_by_user = relationship("Users", foreign_keys=[terminated_by_user_id], remote_side=[UserID], lazy="select")
    user_business_units = relationship("UserBusinessUnit", foreign_keys="UserBusinessUnit.user_id", back_populates="user", lazy="select")

    def is_active(self) -> bool:
        """Return True if user is not terminated."""
        return self.terminated_at is None

class Jobs(Base):
    """The one requisition record: a recruiting job and a client demand are
    the same thing. Recruiting fields use the original camelCase columns;
    the delivery/billing side (client, project, opportunity, fulfilment
    status, SOW confirmation, billing) uses the former Demand columns, and
    the Demand attribute names (id, job_title, headcount, status, ...) are
    synonyms, so `Demand` (app.models.demand) is this class."""
    __tablename__ = "jobs"
    jobID = Column(String(512), primary_key=True, index=True, default=lambda: str(uuid4()))
    jobTitle = Column(String(512), nullable=False)
    jobDescription = Column(Text, nullable=False)
    jobSkills = Column(Text, nullable=False)
    jobExperience = Column(String(512), nullable=False)
    jobLocation = Column(String(512), nullable=False)
    salaryRange = Column(String(512), nullable=True)
    jobCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    companyType = Column(String(512), nullable=True)#full time, part time, contract, temporary, internship
    companyName = Column(String(512), nullable=True)
    contactPerson = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    jobStatus = Column(String(512), nullable=True)
    noOfPositions = Column(Integer, nullable=True)
    startDate = Column(Date, nullable=True)
    endDate = Column(Date, nullable=True)
    recuriterID = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    hiringManagerID = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    department_id = Column(String(512), ForeignKey("departments.id"), nullable=True, index=True)
    # HRMS-0109 — same nullable-first pattern as Users.tenant_id.
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # S-037/HRMS-0437 -- structured requirements with metadata for skill matching
    # Skills format (NEW): [{"name": "Java", "years_of_experience": 5, "last_used_date": "2026-09-01", "is_primary": true}, ...]
    # Skills format (OLD - auto-converted): ["Java", "Python", "SQL"] → structured format with null metadata
    # Supports both formats for backward compatibility. Lazy-converts flat lists to structured on first score.
    required_skills_canonical = Column(JSON, nullable=True, default=list)
    # job_skills_boolean_mode: "AND" requires all mandatory skills, "OR" allows any skill
    job_skills_boolean_mode = Column(String(10), nullable=False, server_default="AND", default="AND")
    min_experience_years = Column(Numeric(4, 1), nullable=True)
    domain = Column(String(512), nullable=True)
    certifications_preferred = Column(JSON, nullable=True)
    # S-038/HRMS-0438 -- same lazy-parse posture as the S-037 columns
    # above. The real recruiter-entered field is salaryRange (free text,
    # e.g. "18-22 LPA"); budget_min/budget_max (paise -- this codebase's
    # normalize_salary() default base unit, see compensation_scoring_service
    # module docstring for the real, documented currency-convention
    # caveat) are lazily parsed from it the first time a job's
    # compensation fit is scored.
    budget_min = Column(Integer, nullable=True)
    budget_max = Column(Integer, nullable=True)
    # S-039/HRMS-0439 -- no urgency/priority field existed on Jobs at all.
    # Nullable: most jobs won't have this set until a real recruiter UI
    # exists to enter it (same "genuinely new, no UI yet" posture as
    # S-037's domain/certifications_preferred). startDate (already a real
    # column, Date) is the real equivalent of the spec's required_start_date
    # -- reused as-is, not duplicated.
    urgency = Column(
        Enum(*JOB_URGENCY_LEVELS, name="job_urgency", native_enum=False, create_constraint=True),
        nullable=True,
    )
    # Soft delete support - jobs can be marked deleted without removing from DB
    deleted_at = Column(DateTime, nullable=True, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    # ---- Client / delivery side (formerly the separate `demands` table) ----
    # Client the role is for; empty for an internal (BlitzenX) hire.
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=True, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)
    opportunity_id = Column(String(512), ForeignKey("opportunities.id"), nullable=True, index=True)
    required_skills = Column(Text, nullable=True)        # JSON array, kept in step with jobSkills
    nice_to_have_skills = Column(Text, nullable=True)    # JSON array
    max_experience_years = Column(Numeric(4, 1), nullable=True)
    work_location = Column(Enum(*JOB_WORK_LOCATIONS, name="job_work_location", native_enum=False, create_constraint=True),
                           nullable=False, default="REMOTE", server_default="REMOTE")
    employment_type = Column(String(50), nullable=False, default="FULLTIME", server_default="FULLTIME")
    interview_type_required = Column(String(20), nullable=False, default="L1_AND_L2", server_default="L1_AND_L2")
    positions_filled = Column(Integer, nullable=False, default=0, server_default="0")
    billing_rate_usd_cents = Column(Integer, nullable=True)
    budget_min_usd_cents = Column(Integer, nullable=True)
    budget_max_usd_cents = Column(Integer, nullable=True)
    # Fulfilment state (DRAFT/OPEN/IN_PROGRESS/FILLED/CANCELLED/ON_HOLD). jobStatus
    # is the publish/approval state; the two are kept in step on save.
    demand_status = Column(String(20), nullable=False, default="DRAFT", server_default="DRAFT", index=True)
    sourcing_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    bench_first_checked = Column(Boolean, nullable=False, default=False, server_default="false")
    assigned_recruiter_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)
    delivery_engine = Column(String(20), nullable=False, default="SPECIALITY", server_default="SPECIALITY")
    confirmation_status = Column(String(20), nullable=False, default="POTENTIAL", server_default="POTENTIAL")
    sow_reference = Column(String(512), nullable=True)
    sow_received_date = Column(Date, nullable=True)
    source_type = Column(String(20), nullable=False, default="DIRECT", server_default="DIRECT")
    duration_hours = Column(Integer, nullable=True)
    revenue_potential_usd_cents = Column(Integer, nullable=True)
    created_by = Column(String(512), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime, nullable=True)

    # Demand attribute names, so code written against Demand reads/writes this record
    id = synonym("jobID")
    job_title = synonym("jobTitle")
    job_description = synonym("jobDescription")
    job_location = synonym("jobLocation")
    headcount = synonym("noOfPositions")
    assigned_bu_id = synonym("business_unit_id")
    required_start_date = synonym("startDate")
    created_at = synonym("jobCreatedAt")
    status = synonym("demand_status")

    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id], lazy="select")
    department = relationship("Department", foreign_keys=[department_id], lazy="select")
    hiring_manager = relationship("Users", foreign_keys=[hiringManagerID], lazy="select")
    recuriter = relationship("Users", foreign_keys=[recuriterID], lazy="select")
    contact_person_user = relationship("Users", foreign_keys=[contactPerson], lazy="select")
    candidates = relationship("Candidate", foreign_keys="Candidate.job_id", lazy="select", back_populates="job")
    client = relationship("Client", foreign_keys=[client_id], lazy="select")


# ---- Keep the recruiting and delivery views of a Jobs row consistent ----
_JOB_TO_DEMAND = {"active": "OPEN", "draft": "DRAFT", "pending_approval": "DRAFT", "closed": "CANCELLED"}
_DEMAND_TO_JOB = {"OPEN": "active", "IN_PROGRESS": "active", "FILLED": "closed", "CANCELLED": "closed"}


def _skills_list(job):
    import json
    if job.required_skills:
        try:
            return [str(s) for s in json.loads(job.required_skills) if s]
        except (ValueError, TypeError):
            return [s.strip() for s in str(job.required_skills).split(",") if s.strip()]
    return [s.strip() for s in (job.jobSkills or "").split(",") if s.strip()]


def _sync_job_fields(job, *, inserting):
    """Fill whichever side is missing, and keep jobStatus/demand_status in step.

    A row created as a client demand gets readable recruiting fields
    (description, skills text, experience, location); a row created on
    the Create Job screen gets the structured demand fields. When one
    status changes, the other follows.
    """
    import json
    import re
    from sqlalchemy import inspect as sa_inspect

    if not job.jobDescription:
        job.jobDescription = job.jobTitle or ""
    skills = _skills_list(job)
    if not job.jobSkills:
        job.jobSkills = ", ".join(skills)
    if not job.required_skills:
        job.required_skills = json.dumps(skills)
    if job.min_experience_years is None and job.jobExperience:
        m = re.search(r"(\d+(?:\.\d+)?)", job.jobExperience)
        if m:
            job.min_experience_years = float(m.group(1))
    if not job.jobExperience:
        lo, hi = job.min_experience_years, job.max_experience_years
        job.jobExperience = (f"{lo:g}-{hi:g} years" if lo is not None and hi is not None
                             else f"{lo:g}+ years" if lo is not None else "")
    if not job.jobLocation:
        job.jobLocation = (job.work_location or "").title()

    state = sa_inspect(job)
    job_changed = inserting or state.attrs.jobStatus.history.has_changes()
    demand_changed = state.attrs.demand_status.history.has_changes()
    if demand_changed and not (inserting and job.jobStatus):
        mapped = _DEMAND_TO_JOB.get(job.demand_status)
        if mapped:
            job.jobStatus = mapped
    elif job_changed and job.jobStatus:
        mapped = _JOB_TO_DEMAND.get(str(job.jobStatus).lower())
        current = job.demand_status or "DRAFT"
        if mapped == "OPEN" and current in ("DRAFT", "CANCELLED"):
            job.demand_status = "OPEN"
        elif mapped == "CANCELLED" and current not in ("FILLED", "CANCELLED"):
            job.demand_status = "CANCELLED"
        elif mapped == "DRAFT" and current == "OPEN":
            job.demand_status = "DRAFT"
    if job.demand_status in ("FILLED", "CANCELLED") and job.closed_at is None:
        job.closed_at = datetime.utcnow()


@event.listens_for(Jobs, "before_insert")
def _jobs_before_insert(mapper, connection, job):
    _sync_job_fields(job, inserting=True)


@event.listens_for(Jobs, "before_update")
def _jobs_before_update(mapper, connection, job):
    _sync_job_fields(job, inserting=False)

class CandidateAssignment(Base):
    __tablename__ = "candidate_assignments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)

    hiring_manager_id = Column(String(512), ForeignKey("users.UserID"))
    reporting_manager_id = Column(String(512), ForeignKey("users.UserID"))

    hiring_manager = relationship("Users", foreign_keys=[hiring_manager_id])
    reporting_manager = relationship("Users", foreign_keys=[reporting_manager_id])

    created_at = Column(DateTime, default=datetime.utcnow)

class InterviewPanel(Base):
    __tablename__ = "interview_panels"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"))
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True)  # job the candidate is interviewed for
    round_name = Column(String(50))  # HR, Tech, Manager

    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")

class PanelMember(Base):
    __tablename__ = "panel_members"

    id = Column(Integer, primary_key=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id"))
    interviewer_id = Column(String(512), ForeignKey("users.UserID"))

    interviewer = relationship("Users")

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id"))
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"))

    start_time = Column(DateTime)
    end_time = Column(DateTime)
    meeting_link = Column(Text)
    outlook_event_id = Column(Text)
 
    status = Column(String(50))  # Scheduled, Completed, Cancelled

    feedback_status = Column(String(512), nullable=False, server_default='Pending')  # Pending, Completed, Cancelled

class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    interviewer_id = Column(String(512), ForeignKey("users.UserID"))

    technical_score = Column(Integer)
    communication_score = Column(Integer)
    problem_solving_score = Column(Integer)
    culture_fit_score = Column(Integer)

    comments = Column(Text)
    recommendation = Column(String(20))  # Hire / Hold / Reject

    submitted_at = Column(DateTime, default=datetime.utcnow)

class UserCustomPermission(Base):
    """
    Custom permission override for a user.

    Allows granting or restricting specific permissions to a user,
    independent of their role template permissions.

    Architecture: Single role + manual overrides
    - User has one role_template (via users.role_id)
    - Can have custom permission overrides for specific resources
    - Permission = role permission OR custom override
    """
    __tablename__ = "user_custom_permissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)

    # Permission flags (TRUE = grant, FALSE = restrict)
    can_view = Column(Boolean, nullable=False, default=False)
    can_create = Column(Boolean, nullable=False, default=False)
    can_edit = Column(Boolean, nullable=False, default=False)
    can_delete = Column(Boolean, nullable=False, default=False)

    # Audit trail
    override_reason = Column(String(512), nullable=True)  # Why was this override set?
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)  # Admin who set it
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("Users", foreign_keys=[user_id])
    resource = relationship("Resource", foreign_keys=[resource_id])
    created_by_user = relationship("Users", foreign_keys=[created_by])
