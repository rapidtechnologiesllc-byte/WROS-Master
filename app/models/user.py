from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func, Boolean, JSON, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base

# S-039/HRMS-0439 -- real values, no native DB enum (SQL Server, same
# native_enum=False/create_constraint=True convention Candidate.employment_type
# and app.models.client's enums already use).
JOB_URGENCY_LEVELS = ("IMMEDIATE", "HIGH", "NORMAL", "FLEXIBLE")

class Users(Base):
    __tablename__ = "users"
    UserID = Column(String(50), primary_key=True, index=True)
    UserRole = Column(String(50), nullable=False)
    UserName = Column(String(150), nullable=True)
    UserEmail = Column(String(200), unique=True, nullable=False, index=True)
    UserPassword = Column(String(200), nullable=False)
    CreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    # RBAC — nullable so existing users are not broken on upgrade
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True, index=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    # HRMS-0109 — nullable for the same reason: existing rows get backfilled
    # in a follow-up step, not broken by this migration. Every tenant-scoped
    # query must filter on this column via app.core.tenant_context, never
    # trust a tenant id supplied by the caller.
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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
    ai_agent_name = Column(String(100), nullable=True)
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
    terminated_by_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True, index=True)

    role = relationship("Role", foreign_keys=[role_id], lazy="select")
    bu_context = relationship("BusinessUnitContext", foreign_keys=[bu_context_id], lazy="select")
    department = relationship("Department", foreign_keys=[department_id], lazy="select")
    terminated_by_user = relationship("Users", foreign_keys=[terminated_by_user_id], remote_side=[UserID], lazy="select")
    # Multi-role support (2026-08-12 RBAC)
    user_roles = relationship("UserRole", foreign_keys="UserRole.user_id", lazy="select")

    # Job title and org hierarchy (2026-08-13 Permission System)
    # TEMPORARY: Commented out until DB migration applies these columns
    # job_title_id = Column(Integer, ForeignKey("job_titles.id"), nullable=True, index=True)
    # org_position_id = Column(Integer, ForeignKey("org_positions.id"), nullable=True, index=True)
    # org_node_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True, index=True)

    # job_title = relationship("JobTitle", foreign_keys=[job_title_id], lazy="select")
    # org_position = relationship("OrgPosition", foreign_keys=[org_position_id], lazy="select")
    # org_node = relationship("OrgNode", foreign_keys=[org_node_id], lazy="select")

    def is_active(self) -> bool:
        """Return True if user is not terminated."""
        return self.terminated_at is None


class UserRole(Base):
    """Multi-role assignment junction table (2026-08-12 RBAC)"""
    __tablename__ = "user_roles"
    id = Column(String(255), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.UserID"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    role = relationship("Role", foreign_keys=[role_id], lazy="select")
    bu_context = relationship("BusinessUnitContext", foreign_keys=[bu_context_id], lazy="select")

class Jobs(Base):
    __tablename__ = "jobs"
    jobID = Column(String(50), primary_key=True, index=True)
    jobTitle = Column(String(200), nullable=False)
    jobDescription = Column(Text, nullable=False)
    jobSkills = Column(Text, nullable=False)
    jobExperience = Column(String(50), nullable=False)
    jobLocation = Column(String(50), nullable=False)
    salaryRange = Column(String(50), nullable=True)
    jobCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    companyType = Column(String(50), nullable=True)#full time, part time, contract, temporary, internship
    companyName = Column(String(50), nullable=True)
    contactPerson = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    jobStatus = Column(String(50), nullable=True)
    noOfPositions = Column(Integer, nullable=True)
    startDate = Column(Date, nullable=True)
    endDate = Column(Date, nullable=True)
    recuriterID = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    hiringManagerID = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    # HRMS-0109 — same nullable-first pattern as Users.tenant_id.
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # S-037/HRMS-0437 -- structured requirements the spec assumes exist on
    # the job record already (required_skills/min_experience_years/domain/
    # certifications_preferred). The real jobSkills/jobExperience columns
    # above are free text a recruiter typed, never structured -- these are
    # lazily populated the first time technical_scoring_service parses
    # them (see that module), not filled in at job-creation time, since no
    # recruiter UI exists yet to enter them directly.
    required_skills_canonical = Column(JSON, nullable=True)
    min_experience_years = Column(Integer, nullable=True)
    domain = Column(String(100), nullable=True)
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
    # EPIC-06-HM-SCREENING -- Hiring Manager validation checkpoint
    # Questions HM must answer before candidate can be interviewed
    hm_validation_questions = Column(JSON, nullable=True)  # Array of validation questions
    hm_validation_required = Column(Boolean, nullable=False, server_default="0", default=False)  # Enable/disable
    hm_validation_timeout_hours = Column(Integer, nullable=False, server_default="24", default=24)  # Response deadline
    auto_schedule_after_approval = Column(Boolean, nullable=False, server_default="1", default=True)  # Auto-schedule interview if HM approves
    hm_auto_reject_threshold = Column(Integer, nullable=True)  # Auto-reject if <N responses negative

    bu_context = relationship("BusinessUnitContext", foreign_keys=[bu_context_id], lazy="select")
    department = relationship("Department", foreign_keys=[department_id], lazy="select")
    hiring_manager = relationship("Users", foreign_keys=[hiringManagerID], lazy="select")
    recuriter = relationship("Users", foreign_keys=[recuriterID], lazy="select")
    contact_person_user = relationship("Users", foreign_keys=[contactPerson], lazy="select")
    candidates = relationship("Candidate", foreign_keys="Candidate.job_id", lazy="select", back_populates="job")



class CandidateAssignment(Base):
    __tablename__ = "candidate_assignments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)

    hiring_manager_id = Column(String(50), ForeignKey("users.UserID"))
    reporting_manager_id = Column(String(50), ForeignKey("users.UserID"))

    hiring_manager = relationship("Users", foreign_keys=[hiring_manager_id])
    reporting_manager = relationship("Users", foreign_keys=[reporting_manager_id])

    created_at = Column(DateTime, default=datetime.utcnow)

class InterviewPanel(Base):
    __tablename__ = "interview_panels"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"))
    job_id = Column(String(50), ForeignKey("jobs.jobID"), nullable=True)  # job the candidate is interviewed for
    round_name = Column(String(50))  # HR, Tech, Manager

    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")


class PanelMember(Base):
    __tablename__ = "panel_members"

    id = Column(Integer, primary_key=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id"))
    interviewer_id = Column(String(50), ForeignKey("users.UserID"))

    interviewer = relationship("Users")

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True)
    interviewID = Column(String(50), unique=True, nullable=False, index=True)  # String ID for API/exports
    panel_id = Column(Integer, ForeignKey("interview_panels.id"))
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"))

    start_time = Column(DateTime)
    end_time = Column(DateTime)
    meeting_link = Column(Text)
    outlook_event_id = Column(Text)

    status = Column(String(50))  # Scheduled, Completed, Cancelled

    feedback_status = Column(String(50), nullable=False, server_default='Pending')  # Pending, Completed, Cancelled

class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    interviewer_id = Column(String(50), ForeignKey("users.UserID"))

    technical_score = Column(Integer)
    communication_score = Column(Integer)
    problem_solving_score = Column(Integer)
    culture_fit_score = Column(Integer)

    comments = Column(Text)
    recommendation = Column(String(20))  # Hire / Hold / Reject

    submitted_at = Column(DateTime, default=datetime.utcnow)
