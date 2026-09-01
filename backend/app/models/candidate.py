from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func, Boolean, Index, Enum
from sqlalchemy.orm import relationship
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


class Candidate(Base):
    __tablename__ = "candidates"
    candidateID = Column(String(50), primary_key=True, index=True)
    candidateRole = Column(String(50), nullable=True, default="Candidate")
    # Employee type: "Intern" | "Full Time Employee"
    candidateEmployeeType = Column(String(50), nullable=True)
    candidateJobTitle = Column(String(50), nullable=True)
    candidateFirstName = Column(String(150), nullable=True)
    candidateMiddleName = Column(String(150), nullable=True)
    candidateLastName = Column(String(150), nullable=True)
    candidateEmail = Column(String(200), unique=True, nullable=False, index=True)
    candidateMobile = Column(String(20), nullable=True)
    # R-07 -- the Dev Review Standard's own example of the dedup gap:
    # "missing phone/LinkedIn" matching. See app.services.candidate_service
    # .create_candidate_safe() -- this field lets LinkedIn dedup run for
    # the first time in this codebase.
    linkedin_url = Column(String(500), nullable=True)
    candidateGender = Column(String(10), nullable=True)
    candidateDateOfBirth = Column(Date, nullable=True)
    candidateSource = Column(String(50), nullable=True)
    candidateExperience = Column(String(50), nullable=True)
    candidateSkills = Column(Text, nullable=True)
    candidateJoiningDate = Column(Date, nullable=True)
    candidateExpectedSalary = Column(String(50), nullable=True)
    candidateCurrentSalary = Column(String(50), nullable=True)
    candidateCurrentLocation = Column(String(200), nullable=True)
    candidatePassword = Column(String(200), nullable=False)
    candidateTempPassword = Column(String(200), nullable=True)  # plain-text password for credential emails
    candidateIsVerified = Column(Boolean, nullable=True)
    candidateCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    # HRMS-P601 (R-01) -- the 5-year experience gate. Populated by real
    # resume parsing (S-028/HRMS-0428, app.services.resume_parsing_service);
    # NULL means "not yet verified" and is treated as ineligible, per the
    # spec's own rule, not as an exemption from the check.
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
    vendor_id = Column(String(36), ForeignKey("sub_vendor_accounts.id"), nullable=True)
    # Job mapping — which job this candidate applied for / was assigned to
    job_id = Column(String(50), ForeignKey("jobs.jobID"), nullable=True, index=True)
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
    submission_timestamp = Column(DateTime, nullable=True)  # When candidate was submitted to BU

    # Relationships
    documents = relationship("CandidateDocument", back_populates="candidate", foreign_keys="CandidateDocument.candidate_id")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select", back_populates="candidates")
    submission_bu = relationship("BusinessUnit", foreign_keys=[submission_bu_id], lazy="select")
    associated_bu = relationship("BusinessUnit", foreign_keys=[associated_bu_id], lazy="select")


class CandidateInfoForm(Base):
    __tablename__ = "candidate_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    position = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    dob = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    marital_status = Column(String(10), nullable=True)
    nationality = Column(String(10), nullable=True)
    current_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)
    submittedAt = Column(Date, nullable=True)
    formCreatedAt = Column(DateTime(timezone=False), server_default=func.now())
    formUpdatedAt = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    # candidate = relationship("Candidate")


class CandidateEducationForm(Base):
    __tablename__ = "candidate_education_forms"
    formID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    education_institute = Column(String(255), nullable=True)
    degree = Column(String(255), nullable=True)
    field_of_study = Column(String(255), nullable=True)
    starting_year = Column(String(50), nullable=True)
    year_of_passing = Column(String(50), nullable=True)
    percentage = Column(String(10), nullable=True)
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
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    company_name = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    year_of_experience = Column(String(50), nullable=True)
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
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    aadhar = Column(String(12), nullable=True)
    name_in_aadhar = Column(String(100), nullable=True)
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
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    pan = Column(String(10), nullable=True)
    name_in_pan = Column(String(100), nullable=True)
    father_name_in_pan = Column(String(100), nullable=True)
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
    candidateID = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False)
    piplineStatus = Column(String(50), nullable=True, default="Applied")
    status = Column(String(50), nullable=True, default="Active")
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
    candidate_id = Column(String(50),
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
    application_status = Column(String(50), nullable=True, default="Applied")
    applied_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships for easy ORM access
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")
