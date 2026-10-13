from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func, Boolean, Enum
from sqlalchemy.orm import column_property, relationship
import logging
from app.models.base import Base

# HRMS-P606 (R-03): only W2_FULLTIME may ever be submitted. UNKNOWN is the
# safe-upgrade default for every existing row -- fails closed, same as C2C/1099,
# until someone explicitly confirms the candidate is W2 full-time.
CANDIDATE_EMPLOYMENT_TYPES = ("W2_FULLTIME", "C2C", "1099", "UNKNOWN")

# HRMS-P816: sourcing attribution. Immutable once set (BR-0816-01) --
# enforced at the service layer (only set at creation time, in
# app.services.sub_vendor_submission_service.accept_submission() for
# SUBVENDOR, never exposed as an updatable field elsewhere), not by a
# DB trigger.
CANDIDATE_SOURCE_CHANNELS = ("DIRECT", "SUBVENDOR")

logger = logging.getLogger(__name__)

class Candidate(Base):
    __tablename__ = "candidates"
    candidateID = Column(String(512), primary_key=True, index=True)
    candidateRole = Column(String(512), nullable=True, default="Candidate")
    # Employee type: "Intern" | "Full Time Employee"
    candidateEmployeeType = Column(String(512), nullable=True)
    candidateJobTitle = Column(String(512), nullable=True)
    candidateFirstName = Column(String(150), nullable=True)
    candidateMiddleName = Column(String(150), nullable=True)
    candidateLastName = Column(String(150), nullable=True)
    candidateEmail = Column(String(512), unique=True, nullable=False, index=True)
    candidateMobile = Column(String(20), nullable=True)
    # R-07 -- the Dev Review Standard's own example of the dedup gap:
    # "missing phone/LinkedIn" matching. See app.services.candidate_service
    # .create_candidate() -- this field lets LinkedIn dedup run for
    # the first time in this codebase.
    linkedin_url = Column(String(512), nullable=True)
    candidateGender = Column(String(100), nullable=True)
    candidateDateOfBirth = Column(Date, nullable=True)
    candidateSource = Column(String(512), nullable=True)
    candidateExperience = Column(String(512), nullable=True)
    candidateSkills = Column(Text, nullable=True)
    candidateJoiningDate = Column(Date, nullable=True)
    candidate_notice_period = Column(Integer, nullable=True)  # Notice period in days (30, 45, 60)
    candidateExpectedSalary = Column(String(512), nullable=True)
    candidateCurrentSalary = Column(String(512), nullable=True)
    # Rate unit for the salary amounts ("$/Year", "INR/Month", "$/Hour", ...)
    candidateExpectedSalaryType = Column(String(50), nullable=True)
    candidateCurrentSalaryType = Column(String(50), nullable=True)
    candidateCurrentLocation = Column(String(512), nullable=True)
    candidatePassword = Column(String(512), nullable=False)
    candidateTempPassword = Column(String(512), nullable=True)  # plain-text password for credential emails
    candidateIsVerified = Column(Boolean, nullable=True)
    candidateCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    # HRMS-P601 (R-01) -- the 5-year experience gate. Populated by real
    # resume parsing (S-028/HRMS-0428, app.services.resume_parsing_service);
    # NULL means "not yet verified" and is treated as ineligible, per the
    # spec's own rule, not as an exemption from the check.
    # Derived from candidateExperience on every save (see the before_insert/
    # before_update listener below): the submission gate reads it.
    total_experience_months = Column(Integer, nullable=True)
    # S-030/HRMS-0430 -- denormalized copy of
    # candidate_resume_parsed.resume_completeness_score for fast reads.
    # Distinct from profile completeness (BR-01) -- never combine the two.
    resume_completeness_score = Column(Integer, nullable=True)
    # HRMS-P606 (R-03) -- fails closed to UNKNOWN for every existing row
    # (see CANDIDATE_EMPLOYMENT_TYPES above); direct WROS-sourced candidates
    # should be set to W2_FULLTIME explicitly by whichever story owns
    # candidate creation/intake -- not assumed here.
    employment_type = Column(
        Enum(*CANDIDATE_EMPLOYMENT_TYPES, name="candidate_employment_type", native_enum=False, create_constraint=True),
        nullable=False, server_default="UNKNOWN", default="UNKNOWN",
    )
    # app.services.conversation_inactivity_service -- candidate-local
    # timezone, used only to decide whether it's a reasonable hour
    # (9am-9pm) to auto-message the candidate. Every existing row
    # backfills to BlitzenX's default (same as Users.timezone); real
    # per-candidate values would come from whichever intake flow
    # eventually captures location -- not resolved here.
    timezone = Column(String(64), nullable=False, server_default="Asia/Kolkata", default="Asia/Kolkata")
    # HRMS-P816 -- internal-analytics-only, BR-0816-02: never exposed to
    # any candidate- or client-facing view/API response.
    source_channel = Column(
        Enum(*CANDIDATE_SOURCE_CHANNELS, name="candidate_source_channel", native_enum=False, create_constraint=True),
        nullable=False, server_default="DIRECT", default="DIRECT",
    )
    vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=True)
    # Job mapping — which job this candidate applied for / was assigned to
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True, index=True)
    # Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate half) --
    # opt-in email OTP, reusing app.core.mfa's role-agnostic EMAIL_OTP_*
    # functions. Tri-state, not a plain boolean: NULL = never asked
    # (show the opt-in popup once), True = opted in (challenge every
    # login), False = explicitly declined (never ask again unless they
    # change it in a future settings screen). email_otp_code_hash/
    # email_otp_expires_at mirror Users' own fields exactly -- only
    # populated at the moment a code is issued, cleared on verify/expiry.
    email_2fa_opted_in = Column(Boolean, nullable=True)
    email_otp_code_hash = Column(String(64), nullable=True)
    email_otp_expires_at = Column(DateTime, nullable=True)
    # CANDIDATE ISOLATION: Once submitted to a BU, candidate is locked to that BU
    # submission_bu_id: IMMUTABLE - which BU first submitted this candidate (NULL = not yet submitted)
    # associated_bu_id: READ-ONLY - current BU association (follows submission_bu_id, used for queries)
    # Candidate visibility: unassociated (NULL) = visible to all HR, associated = visible only to that BU
    submission_bu_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    associated_bu_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    # Multi-tenant isolation: tenant_id must be set, never allow None
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, server_default="1", default=1, index=True)
    submission_timestamp = Column(DateTime, nullable=True)  # When candidate was submitted to BU
    thunder_enabled = Column(Boolean, nullable=False, default=True, server_default="1")  # Enable/disable Thunder autonomous processing

    # Referral tracking - link to employee referral if this candidate was referred
    referral_id = Column(
        String(512),
        ForeignKey("employee_referrals.referral_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Creation audit trail
    created_by_user_id = Column(String(512), nullable=True, index=True)
    created_by_name = Column(String(512), nullable=True)

    # Recruitment source (EMPLOYEE_REFERRAL, LINKEDIN, DIRECT, SUBVENDOR, etc.)
    recruitment_source = Column(String(512), nullable=True, index=True)

    # Status tracking for event-driven architecture
    status_changed_at = Column(DateTime, nullable=True)  # When status actually changed (not every commit)
    previous_status = Column(String(100), nullable=True)  # Previous status for tracking transitions
    status_change_reason = Column(String(500), nullable=True)  # Why status changed (interview scheduled, offer accepted, etc.)

    # Recruiter assignment (Thunder autonomous assignment)
    assigned_recruiter_id = Column(String(512), ForeignKey("users.UserID"), nullable=True, index=True)  # Auto-assigned recruiter
    assigned_recruiter_changed_at = Column(DateTime, nullable=True)  # When recruiter was assigned
    assigned_recruiter_changed_by = Column(String(512), nullable=True)  # Who/what assigned (usually "THUNDER_AUTO_ASSIGN")

    # Progressive Upload Status Tracking
    upload_status = Column(String(50), nullable=True, default="uploading")  # uploading, queued, processing, complete, error
    expected_document_count = Column(Integer, nullable=True, default=0)  # Total documents expected
    actual_document_count = Column(Integer, nullable=True, default=0)  # Documents actually uploaded
    upload_started_at = Column(DateTime, nullable=True)  # When upload session started
    last_document_uploaded_at = Column(DateTime, nullable=True)  # When last document was uploaded
    queued_at = Column(DateTime, nullable=True)  # When queued for processing
    processing_started_at = Column(DateTime, nullable=True)  # When Celery task started
    processing_completed_at = Column(DateTime, nullable=True)  # When Celery task completed
    upload_error = Column(Text, nullable=True)  # Error message if upload failed
    celery_task_id = Column(String(512), nullable=True)  # Task ID for monitoring

    # Relationships
    documents = relationship("CandidateDocument", back_populates="candidate", foreign_keys="CandidateDocument.candidate_id")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select", back_populates="candidates")
    submission_bu = relationship("BusinessUnit", foreign_keys=[submission_bu_id], lazy="select")
    associated_bu = relationship("BusinessUnit", foreign_keys=[associated_bu_id], lazy="select")

    # Referral relationship
    referral = relationship(
        "EmployeeReferral",
        foreign_keys=[referral_id],
        lazy="select",
        backref="candidates_referred"
    )

    # Created by user relationship
    created_by_user = relationship(
        "Users",
        foreign_keys=[created_by_user_id],
        lazy="select",
        primaryjoin="Candidate.created_by_user_id==Users.UserID"
    )

    # Assigned recruiter relationship (Thunder autonomous assignment)
    assigned_recruiter = relationship(
        "Users",
        foreign_keys=[assigned_recruiter_id],
        lazy="select",
        primaryjoin="Candidate.assigned_recruiter_id==Users.UserID"
    )

    # History entries relationship
    history_entries = relationship(
        "CandidateHistory",
        back_populates="candidate",
        foreign_keys="CandidateHistory.candidateID",
        cascade="all, delete-orphan"
    )

class CandidateInfoForm(Base):
    __tablename__ = "candidate_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)
    position = Column(String(512), nullable=True)
    department = Column(String(512), nullable=True)
    dob = Column(Date, nullable=True)
    gender = Column(String(100), nullable=True)
    marital_status = Column(String(100), nullable=True)
    nationality = Column(String(100), nullable=True)
    current_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)
    submittedAt = Column(Date, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateEducationForm(Base):
    __tablename__ = "candidate_education_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)
    education_institute = Column(String(512), nullable=True)
    degree = Column(String(512), nullable=True)
    field_of_study = Column(String(512), nullable=True)
    starting_year = Column(String(512), nullable=True)
    year_of_passing = Column(String(512), nullable=True)
    percentage = Column(String(10), nullable=True)
    # Level (e.g. "Bachelor's", "Master's") entered on the HR profile
    education_level = Column(String(100), nullable=True)
    submittedAt = Column(Date, nullable=True)
    document_is_submitted = Column(Boolean, nullable=True)
    # Optional link to the uploaded document in candidate_documents
    document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateExperienceForm(Base):
    __tablename__ = "candidate_experience_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)
    company_name = Column(String(512), nullable=True)
    job_title = Column(String(512), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    year_of_experience = Column(String(512), nullable=True)
    responsibilities = Column(Text, nullable=True)
    document_is_submitted = Column(Boolean, nullable=True)
    submittedAt = Column(Date, nullable=True)
    # Optional link to the uploaded document in candidate_documents
    document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateAadharForm(Base):
    __tablename__ = "candidate_aadhar_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)
    aadhar = Column(String(12), nullable=True)
    name_in_aadhar = Column(String(512), nullable=True)
    enrollment_number = Column(String(20), nullable=True)
    aadhar_is_submitted = Column(Boolean, nullable=True)
    submittedAt = Column(Date, nullable=True)
    is_verified = Column(Boolean, nullable=True)
    # Optional link to the uploaded document in candidate_documents
    document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidatePanForm(Base):
    __tablename__ = "candidate_pan_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)
    pan = Column(String(10), nullable=True)
    name_in_pan = Column(String(512), nullable=True)
    father_name_in_pan = Column(String(512), nullable=True)
    pan_is_submitted = Column(Boolean, nullable=True)
    submittedAt = Column(Date, nullable=True)
    is_verified = Column(Boolean, nullable=True)
    # Optional link to the uploaded document in candidate_documents
    document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateStatus(Base):
    __tablename__ = "candidate_status"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False)
    # active_history: the previous value is loaded on change, so the status hook knows old -> new
    piplineStatus = column_property(Column(String(512), nullable=True, default="Applied"), active_history=True)
    status = Column(String(512), nullable=True, default="Active")
    thunder_assigned_at = Column(DateTime(timezone=True), nullable=True)
    createdAt = Column(DateTime(timezone=False), server_default=func.now())
    updatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")

class CandidateJobApplication(Base):
    """
    Many-to-many junction table between Candidate and Jobs.
    Allows a single candidate to be assigned to / applied for multiple jobs.
    """
    __tablename__ = "candidate_job_applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(String(512),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        String(50),
        ForeignKey("jobs.jobID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Per-application status independent of the candidate's global status
    application_status = Column(String(512), nullable=True, default="Applied")
    applied_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships for easy ORM access
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")


# Keep total_experience_months in step with the experience the recruiter entered
def _sync_experience_months(mapper, connection, candidate):
    from sqlalchemy import inspect as sa_inspect
    from app.services.candidate_service import parse_experience_to_months

    state = sa_inspect(candidate)
    if state.attrs.candidateExperience.history.has_changes() or candidate.total_experience_months is None:
        months = parse_experience_to_months(candidate.candidateExperience)
        if months is not None:
            candidate.total_experience_months = months


from sqlalchemy import event as _event  # noqa: E402
_event.listen(Candidate, "before_insert", _sync_experience_months)
_event.listen(Candidate, "before_update", _sync_experience_months)


# Every pipeline-status change notifies the candidate once the transaction commits
# (app.services.candidate_status_notifications). Recorded at flush, queued after commit,
# dropped on rollback -- so every writer is covered and nothing is sent for an undone change.
from sqlalchemy import event as _event  # noqa: E402
from sqlalchemy import inspect as _inspect  # noqa: E402
from sqlalchemy.orm import Session as _Session  # noqa: E402

_STATUS_CHANGES_KEY = "candidate_status_changes"


@_event.listens_for(_Session, "before_flush")
def _record_pipeline_status_changes(session, flush_context, instances):
    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, CandidateStatus) or not obj.piplineStatus:
            continue
        history = _inspect(obj).attrs.piplineStatus.history
        if obj in session.new or history.has_changes():
            old = history.deleted[0] if history.deleted else None
            if old != obj.piplineStatus:
                session.info.setdefault(_STATUS_CHANGES_KEY, []).append(
                    (obj.candidateID, old, obj.piplineStatus))


@_event.listens_for(_Session, "after_commit")
def _queue_pipeline_status_changes(session):
    changes = session.info.pop(_STATUS_CHANGES_KEY, None)
    if not changes:
        return
    from app.services.candidate_status_notifications import queue_status_change
    for candidate_id, old, new in changes:
        queue_status_change(candidate_id, old, new)


@_event.listens_for(_Session, "after_rollback")
def _drop_pipeline_status_changes(session):
    session.info.pop(_STATUS_CHANGES_KEY, None)
