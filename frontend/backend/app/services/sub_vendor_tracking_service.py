"""
HRMS-P803/P810 (vendor-facing submission tracking) + HRMS-P805/P812
(scorecard & portfolio analytics). Pure read-only query layers over the
schema built for HRMS-P801/P806/P807/P808 -- no new tables needed for
either, per BR-0812-01's "computed, not manually entered" requirement.

P803 and P810 describe the same vendor-facing concept from two doc
batches (submission status + demand + dates); built as one function.
P805 and P812 likewise (a per-vendor scorecard); P812 is the richer,
later version and was built as authoritative, covering P805's simpler
metric set as a subset.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.demand import Demand
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest
from app.models.sub_vendor_submission import (
    SubVendorDedupRejection,
    SubVendorSubmission,
    SubVendorViolation,
)

VIOLATION_WINDOW_DAYS = 90


def get_submissions_for_vendor(db: Session, sub_vendor: SubVendorAccount) -> List[dict]:
    """
    HRMS-P803 BR-01 / HRMS-P810: a vendor sees only their own
    submissions (the sub_vendor_id filter is the isolation boundary --
    this is the only sanctioned read path, don't query
    SubVendorSubmission directly from a route). HRMS-P810 BR-0810-01:
    Rejected always shows feedback_note, never bare -- surfaced here
    unconditionally since there's nothing else to omit it from.
    Internal recruiter notes/interview feedback are never included
    (they don't exist on this table at all, so there's nothing to leak).
    """
    submissions = db.query(SubVendorSubmission).filter(
        SubVendorSubmission.sub_vendor_id == sub_vendor.id
    ).order_by(SubVendorSubmission.created_at.desc()).all()

    results = []
    for s in submissions:
        request = db.query(SubVendorRequest).filter(SubVendorRequest.id == s.request_id).first()
        demand = db.query(Demand).filter(Demand.id == request.demand_id).first() if request else None
        results.append({
            "submission_id": s.id,
            "candidate_name": s.candidate_name,
            "demand_job_title": demand.job_title if demand else None,
            "status": s.status,
            "submitted_at": s.created_at,
            "feedback_note": s.feedback_note,
        })
    return results


def get_sub_vendor_scorecard(db: Session, sub_vendor: SubVendorAccount, *, now: Optional[datetime] = None) -> dict:
    """
    HRMS-P805 BR-01 / HRMS-P812 BR-0812-01: every figure here is
    computed from underlying submission/violation records, nothing
    manually entered. Visible to Admin/RM only per HRMS-P805 BR-01 --
    enforcement of that visibility rule is an API-layer concern (no
    REST endpoints exist yet for this domain), not this function's job.
    """
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=VIOLATION_WINDOW_DAYS)

    submissions = db.query(SubVendorSubmission).filter(SubVendorSubmission.sub_vendor_id == sub_vendor.id).all()
    total = len(submissions)
    accepted = sum(1 for s in submissions if s.status == "ACCEPTED")
    rejected = sum(1 for s in submissions if s.status == "REJECTED")

    submission_to_acceptance_rate_pct = (accepted / total * 100) if total else 0.0

    violation_count_90d = db.query(SubVendorViolation).filter(
        SubVendorViolation.sub_vendor_id == sub_vendor.id,
        SubVendorViolation.occurred_at >= cutoff,
    ).count()

    dedup_rejection_count = db.query(SubVendorDedupRejection).join(
        SubVendorSubmission, SubVendorDedupRejection.submission_id == SubVendorSubmission.id
    ).filter(SubVendorSubmission.sub_vendor_id == sub_vendor.id).count()

    return {
        "submissions_total": total,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "submission_to_acceptance_rate_pct": submission_to_acceptance_rate_pct,
        "ft_compliance_violations_90d": violation_count_90d,
        "dedup_rejection_count": dedup_rejection_count,
        "compliance_status": sub_vendor.compliance_status,
    }


def get_sub_vendor_portfolio_analytics(db: Session, *, tenant_id: Optional[int] = None) -> dict:
    """
    HRMS-P812's Admin portfolio view. sub_vendor_sourced_candidate_pct
    is computed from candidates.source_channel=SUBVENDOR (HRMS-P816),
    per this story's own data-mapping confirmation -- joined to
    placements is a later-pipeline concept (Submission.status=PLACED)
    not reproduced here in full; this reports raw candidate-sourcing
    contribution, the metric P812 itself calls out as the clearest
    confirmation of where source_channel is read from.
    """
    active_vendors = db.query(SubVendorAccount).filter(
        SubVendorAccount.tenant_id == tenant_id, SubVendorAccount.status == "APPROVED",
    ).count()

    total_submissions = db.query(SubVendorSubmission).count()
    accepted_submissions = db.query(SubVendorSubmission).filter(SubVendorSubmission.status == "ACCEPTED").count()
    overall_acceptance_rate_pct = (accepted_submissions / total_submissions * 100) if total_submissions else 0.0

    total_candidates = db.query(Candidate).count()
    sub_vendor_candidates = db.query(Candidate).filter(Candidate.source_channel == "SUBVENDOR").count()
    sub_vendor_contribution_pct = (sub_vendor_candidates / total_candidates * 100) if total_candidates else 0.0

    return {
        "active_vendors": active_vendors,
        "total_submissions": total_submissions,
        "overall_acceptance_rate_pct": overall_acceptance_rate_pct,
        "sub_vendor_sourced_candidate_count": sub_vendor_candidates,
        "sub_vendor_contribution_pct": sub_vendor_contribution_pct,
    }
