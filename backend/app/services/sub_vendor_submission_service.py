"""
HRMS-P806 (FT-Only Enforcement Gate) + HRMS-P807 (Dedup Against Internal
DB) + HRMS-P808 (Recruiter Review) + HRMS-P811's compliance-escalation
import logging
half (deadline auto-close lives in app.services.sub_vendor_service).

The FT-only gate and dedup check reuse existing, real logic rather than
reimplementing it: employment-type validation reads the same allowed-
value convention as HRMS-P606 (candidates.employment_type), and dedup
calls app.services.candidate_service.find_duplicate_candidate() --
literally the same function HRMS-0711's Submission pipeline and
createCandidateSafe() both use -- per BR-0807-01's explicit "one dedup
path in the platform" requirement.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest
from app.models.sub_vendor_submission import (
    SubVendorDedupRejection,
    SubVendorSubmission,
    SubVendorViolation,
)
from app.services.candidate_service import create_candidate_safe, find_duplicate_candidate
from app.services.sub_vendor_service import is_approved_for_submission, SubVendorNotApproved

MIN_REJECTION_FEEDBACK_LENGTH = 20  # BR-0808-02
COMPLIANCE_REVIEW_THRESHOLD = 3   # BR-0806-02
COMPLIANCE_SUSPENSION_THRESHOLD = 5  # BR-0806-02
VIOLATION_WINDOW_DAYS = 90

logger = logging.getLogger(__name__)

class InvalidSubmissionReviewTransition(Exception):
    pass


class SubmissionValidationError(Exception):
    pass


def submit_candidate(
    db: Session,
    *,
    request: SubVendorRequest,
    sub_vendor: SubVendorAccount,
    candidate_name: str,
    candidate_email: str,
    employment_type: str,
    candidate_phone: Optional[str] = None,
    current_employer: Optional[str] = None,
    total_experience_years=None,
    expected_salary: Optional[str] = None,
    notice_period: Optional[str] = None,
    resume_url: Optional[str] = None,
) -> SubVendorSubmission:
    """
    Always creates a SubVendorSubmission row (a rejected attempt is
    still a real, auditable record -- "the vendor is notified" per
    P806, not silently dropped) -- runs the FT-only gate first, then
    dedup, short-circuiting on the first failure with an explicit,
    logged reason.
    """
    if not is_approved_for_submission(sub_vendor):
        raise SubVendorNotApproved(
            f"Sub-vendor {sub_vendor.id} is not approved for submissions "
            f"(status={sub_vendor.status}, compliance_status={sub_vendor.compliance_status})."
        )

    submission = SubVendorSubmission(
        request_id=request.id, sub_vendor_id=sub_vendor.id,
        candidate_name=candidate_name, candidate_email=candidate_email, candidate_phone=candidate_phone,
        current_employer=current_employer, total_experience_years=total_experience_years,
        expected_salary=expected_salary, notice_period=notice_period, resume_url=resume_url,
        employment_type=employment_type,
    )
    db.add(submission)
    db.flush()

    # HRMS-P806: server-side, regardless of what the vendor UI allowed.
    if employment_type != "W2_FULLTIME":
        submission.status = "REJECTED"
        submission.feedback_note = "BlitzenX only accepts full-time (W2) candidates."
        db.add(submission)
        db.add(SubVendorViolation(
            sub_vendor_id=sub_vendor.id, submission_id=submission.id,
            violation_type="C2C_NOT_ACCEPTED", employment_type=employment_type,
        ))
        return submission

    # HRMS-P807: same dedup path as createCandidateSafe() / the main
    # Submission pipeline -- not a separate implementation.
    existing, _matched_on = find_duplicate_candidate(db, email=candidate_email, mobile=candidate_phone)
    if existing:
        submission.status = "REJECTED"
        # BR-0807-02: never reveal which internal candidate matched, or any other detail.
        submission.feedback_note = "This candidate is already in BlitzenX's system."
        db.add(submission)
        db.add(SubVendorDedupRejection(submission_id=submission.id, matched_candidate_id=existing.candidateID))
        return submission

    return submission


def _split_name(full_name: str):
    parts = (full_name or "").strip().split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else None)


def accept_submission(db: Session, submission: SubVendorSubmission) -> Candidate:
    """HRMS-P808 BR-0808-01: always through create_candidate_safe(),
    never a direct insert -- even in a bulk-accept loop, one call per
    candidate (the caller iterates; this function handles exactly one)."""
    if submission.status != "PENDING_REVIEW":
        raise InvalidSubmissionReviewTransition(f"Cannot accept a submission in status '{submission.status}'.")

    first_name, last_name = _split_name(submission.candidate_name)
    candidate = create_candidate_safe(
        db,
        email=submission.candidate_email,
        mobile=submission.candidate_phone,
        candidateFirstName=first_name,
        candidateLastName=last_name,
        candidateExpectedSalary=submission.expected_salary,
        candidateSource="sub_vendor_portal",
        employment_type=submission.employment_type,  # already gated to W2_FULLTIME
        # HRMS-P816: immutable sourcing attribution, set only here.
        source_channel="SUBVENDOR",
        vendor_id=submission.sub_vendor_id,
    )

    submission.status = "ACCEPTED"
    submission.created_candidate_id = candidate.candidateID
    db.add(submission)
    return candidate


def reject_submission(db: Session, submission: SubVendorSubmission, *, feedback_note: str) -> SubVendorSubmission:
    """BR-0808-02: rejection always requires feedback, no silent rejects."""
    if submission.status != "PENDING_REVIEW":
        raise InvalidSubmissionReviewTransition(f"Cannot reject a submission in status '{submission.status}'.")
    if len(feedback_note or "") < MIN_REJECTION_FEEDBACK_LENGTH:
        raise SubmissionValidationError(f"Rejection feedback must be at least {MIN_REJECTION_FEEDBACK_LENGTH} characters.")

    submission.status = "REJECTED"
    submission.feedback_note = feedback_note
    db.add(submission)
    return submission


def request_more_info(db: Session, submission: SubVendorSubmission, *, note: str) -> SubVendorSubmission:
    if submission.status != "PENDING_REVIEW":
        raise InvalidSubmissionReviewTransition(f"Cannot request more info on a submission in status '{submission.status}'.")

    submission.status = "MORE_INFO_REQUESTED"
    submission.feedback_note = note
    db.add(submission)
    return submission


def evaluate_compliance_escalation(
    db: Session, sub_vendor: SubVendorAccount, *, now: Optional[datetime] = None,
) -> Optional[str]:
    """
    HRMS-P806 BR-0806-02 / HRMS-P811 BR-0811-02: 3 FT-only violations in
    90 days -> UNDER_REVIEW; 5 -> SUSPENSION_PENDING (NOT SUSPENDED --
    per BR-0811-02, actual suspension requires explicit Admin
    confirmation, the one deliberately non-automatic step in this
    domain; see confirm_suspension()). Dedup rejections never count
    toward this threshold, per BR-0807-03 -- only SubVendorViolation
    rows do.
    """
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=VIOLATION_WINDOW_DAYS)

    violation_count = db.query(SubVendorViolation).filter(
        SubVendorViolation.sub_vendor_id == sub_vendor.id,
        SubVendorViolation.occurred_at >= cutoff,
        SubVendorViolation.is_cleared.is_(False),
    ).count()

    if violation_count >= COMPLIANCE_SUSPENSION_THRESHOLD:
        sub_vendor.compliance_status = "SUSPENSION_PENDING"
    elif violation_count >= COMPLIANCE_REVIEW_THRESHOLD:
        sub_vendor.compliance_status = "UNDER_REVIEW"
    else:
        return None

    db.add(sub_vendor)
    return sub_vendor.compliance_status


def confirm_suspension(db: Session, sub_vendor: SubVendorAccount) -> SubVendorAccount:
    """BR-0811-02's deliberate exception to full automation -- an Admin
    must explicitly confirm before SUSPENSION_PENDING becomes SUSPENDED."""
    if sub_vendor.compliance_status != "SUSPENSION_PENDING":
        raise InvalidSubmissionReviewTransition(
            f"Cannot confirm suspension -- compliance_status is '{sub_vendor.compliance_status}', not SUSPENSION_PENDING."
        )
    sub_vendor.compliance_status = "SUSPENDED"
    db.add(sub_vendor)
    return sub_vendor
