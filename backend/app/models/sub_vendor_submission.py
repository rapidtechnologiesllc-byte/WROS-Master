"""
HRMS-P802 (Submission Form) + HRMS-P806 (FT-Only Gate) + HRMS-P807
(Dedup) + HRMS-P808 (Recruiter Review).

Flow, per the research reconciling P802's own "creates a real
submissions row immediately" language against P806-P808's staged
design (treated as authoritative -- the later, more carefully-reasoned
docs, and the only ones that actually gate on R-01/R-03/R-07 before a
candidate exists): a vendor's candidate offer sits in
`sub_vendor_submissions` (a staging table, NOT the `submissions` table
from HRMS-0711 -- that's an unrelated, later-stage concept: BlitzenX
presenting a candidate to a CLIENT, not a vendor presenting a candidate
to BlitzenX) until it clears the FT-only gate and dedup, then a
recruiter Accepts/Rejects/Requests-more-info. Only Accept calls
app.services.candidate_service.create_candidate_safe() -- the real R-07
path, never a direct insert, per BR-0808-01.

Field name note: P808's own data-mapping table calls this column
`review_decision`; P810's calls the same concept `status`. Named it
`status` here since the value space includes PENDING_REVIEW (nothing's
been decided yet), which "review_decision" implies excludes.
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Numeric,
    String, Text, func,
)

from app.models.base import Base
from app.models.candidate import CANDIDATE_EMPLOYMENT_TYPES


def _new_uuid() -> str:
    return str(uuid.uuid4())


SUBMISSION_REVIEW_STATUSES = ("PENDING_REVIEW", "ACCEPTED", "REJECTED", "MORE_INFO_REQUESTED")
SUBVENDOR_VIOLATION_TYPES = ("C2C_NOT_ACCEPTED",)


class SubVendorSubmission(Base):
    __tablename__ = "sub_vendor_submissions"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    request_id = Column(String(512), ForeignKey("sub_vendor_requests.id"), nullable=False, index=True)
    sub_vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=False, index=True)

    candidate_name = Column(String(300), nullable=False)
    candidate_email = Column(String(300), nullable=False)
    candidate_phone = Column(String(512), nullable=True)
    current_employer = Column(String(300), nullable=True)
    total_experience_years = Column(Numeric(4, 1), nullable=True)
    expected_salary = Column(String(512), nullable=True)
    notice_period = Column(String(512), nullable=True)
    resume_url = Column(Text, nullable=True)

    # HRMS-P806: server-validated regardless of what the vendor UI's
    # dropdown allows -- reuses the same allowed-value set as the
    # existing Candidate.employment_type (CANDIDATE_EMPLOYMENT_TYPES),
    # not a separately-maintained list.
    employment_type = Column(
        Enum(*CANDIDATE_EMPLOYMENT_TYPES, name="subvendor_submission_employment_type", native_enum=False, create_constraint=True),
        nullable=False, default="UNKNOWN",
    )

    status = Column(
        Enum(*SUBMISSION_REVIEW_STATUSES, name="subvendor_submission_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING_REVIEW",
    )
    feedback_note = Column(Text, nullable=True)  # BR-0808-02: required (>= 20 chars) on REJECTED

    # Set only once Accepted via create_candidate_safe() -- never a
    # direct FK to a pre-existing candidate.
    created_candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())


class SubVendorViolation(Base):
    """HRMS-P806 BR-0806-03: every FT-only rejection is logged, never
    silently dropped. Separate from dedup rejections (BR-0807-03)."""
    __tablename__ = "sub_vendor_violations"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    sub_vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=False, index=True)
    submission_id = Column(String(512), ForeignKey("sub_vendor_submissions.id"), nullable=True)
    violation_type = Column(
        Enum(*SUBVENDOR_VIOLATION_TYPES, name="subvendor_violation_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    employment_type = Column(String(20), nullable=True)
    occurred_at = Column(DateTime, server_default=func.now())
    is_cleared = Column(Boolean, nullable=False, default=False)


class SubVendorDedupRejection(Base):
    """HRMS-P807 BR-0807-02/03: tracked separately from FT-only
    violations (a dedup match isn't a vendor compliance issue).
    matched_candidate_id is internal-audit-only -- BR-0807-02 requires
    the vendor never learns which internal candidate matched; this
    field is never surfaced in any vendor-facing response."""
    __tablename__ = "sub_vendor_dedup_rejections"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    submission_id = Column(String(512), ForeignKey("sub_vendor_submissions.id"), nullable=False, index=True)
    matched_candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=True)
    occurred_at = Column(DateTime, server_default=func.now())
