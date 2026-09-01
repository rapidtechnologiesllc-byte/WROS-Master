"""
HRMS-0711 -- Client Submission Pipeline, Phase 2 Domain 2 (the piece
connecting Demand -> Candidate -> Employee).

Follows the EPIC-01/Phase A track -- the same sprint sequence that
produced Employee/Client/Demand -- not the later, structurally
different EPIC-07 "Talent Engine ATS Layer" Kanban-based submissions
design that happens to reuse the same HRMS-ID range for a later-phase
story. See this session's build notes for the full reasoning.

Compliance gates (HRMS-P601/P605/P606) are enforced for real at the
hard-block level in app.services.submission_service -- but only the
block itself. The full override workflows these stories also specify
(HRMS-P601's Director+BU Head sequential experience override,
HRMS-P605/P606's 3-strike/5-strike compliance-review + account-
suspension escalation) are separate, dedicated Phase 3 EPIC-P6 stories
and are NOT built here. SubmissionViolation exists as a real audit log
of every blocked attempt; the escalation cascade reading it does not
exist yet -- flagged as explicit follow-up work, not silently skipped.
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


SUBMISSION_STATUSES = (
    "SUBMITTED", "SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED",
    "REJECTED_BY_CLIENT", "OFFER_EXTENDED", "PLACED", "WITHDRAWN",
)
SUBMISSION_SOURCES = ("INTERNAL", "SUBVENDOR")

# HRMS-0711 step 3 -- client-response-driven transitions. WITHDRAWN is
# reachable from any non-terminal state (recruiter pulls the submission).
ALLOWED_SUBMISSION_TRANSITIONS = {
    "SUBMITTED": {"SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED", "REJECTED_BY_CLIENT", "WITHDRAWN"},
    "SHORTLISTED": {"CLIENT_INTERVIEW_REQUESTED", "REJECTED_BY_CLIENT", "WITHDRAWN"},
    "CLIENT_INTERVIEW_REQUESTED": {"OFFER_EXTENDED", "REJECTED_BY_CLIENT", "WITHDRAWN"},
    "OFFER_EXTENDED": {"PLACED", "REJECTED_BY_CLIENT", "WITHDRAWN"},
    "REJECTED_BY_CLIENT": set(),  # terminal
    "PLACED": set(),              # terminal
    "WITHDRAWN": set(),           # terminal
}

VIOLATION_TYPES = ("NO_MARKET_PROFILE", "EXPERIENCE_INELIGIBLE", "C2C_NOT_ACCEPTED")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    demand_id = Column(String(256), ForeignKey("demands.id"), nullable=False, index=True)
    client_id = Column(String(256), ForeignKey("clients.id"), nullable=False, index=True)
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID"), nullable=False, index=True)

    submitted_by_user_id = Column(String(256), ForeignKey("users.UserID"), nullable=True)
    submitted_at = Column(DateTime, server_default=func.now())

    status = Column(
        Enum(*SUBMISSION_STATUSES, name="submission_status", native_enum=False, create_constraint=True),
        nullable=False, default="SUBMITTED",
    )

    client_feedback = Column(Text, nullable=True)
    client_response_at = Column(DateTime, nullable=True)

    # HRMS-0710 rank at the moment of submission -- an audit snapshot,
    # deliberately not recalculated later even if the candidate's score
    # (ats_scores.overall_score, the existing scoring model -- HRMS-0440's
    # full Thunder ranking pipeline isn't built yet) changes afterward.
    submission_rank = Column(Integer, nullable=True)
    # Resume URL snapshot at submission time (BR-02) -- this codebase's
    # Candidate model has no resume_url field yet (resumes live on
    # CandidateDocument); stored here as free text so a future resume
    # upload doesn't retroactively change what the client was shown.
    submitted_as_resume_url = Column(Text, nullable=True)

    source = Column(
        Enum(*SUBMISSION_SOURCES, name="submission_source", native_enum=False, create_constraint=True),
        nullable=False, default="INTERNAL",
    )
    # EPIC-P8 Sub-Vendor Portal is now built (see app.models.sub_vendor) --
    # FK completed, still nullable since most submissions aren't sub-vendor-sourced.
    subvendor_id = Column(String(256), ForeignKey("sub_vendor_accounts.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "demand_id", "candidate_id", name="uq_submission_per_demand_candidate"),
    )


class SubmissionViolation(Base):
    """
    HRMS-P605/P606's violation log. Real audit trail of every blocked
    submission attempt -- the 3-strike/5-strike compliance-review and
    account-suspension escalation that's supposed to read this table is
    deferred (see module docstring), so is_cleared exists for schema
    completeness but nothing currently sets it.
    """
    __tablename__ = "submission_violations"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    recruiter_user_id = Column(String(256), ForeignKey("users.UserID"), nullable=True, index=True)
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID"), nullable=False)
    violation_type = Column(
        Enum(*VIOLATION_TYPES, name="submission_violation_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    attempted_at = Column(DateTime, server_default=func.now())
    candidate_status_at_time = Column(String(256), nullable=True)
    blocked_message = Column(Text, nullable=True)
    is_cleared = Column(Boolean, nullable=False, default=False)
