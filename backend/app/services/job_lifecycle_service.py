"""A job with hiring or delivery history is never deleted -- it is closed. Deleting it
would erase applications, interview verdicts (the rehire guard reads past No Hires),
offers, submissions and allocations, or fail on their foreign keys. Only a job nothing
refers to yet (created by mistake) may be deleted."""
from typing import Dict

from sqlalchemy.orm import Session


class JobHasHistory(ValueError):
    pass


def job_history(db: Session, job_id: str) -> Dict[str, int]:
    """What refers to this job, by kind (only kinds with rows)."""
    from app.models.candidate import CandidateJobApplication
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.offer import Offer
    from app.models.offer_letter import OfferLetter
    from app.models.submission import Submission
    from app.models.user import InterviewPanel

    counts = {
        "applications": db.query(CandidateJobApplication).filter(CandidateJobApplication.job_id == job_id).count(),
        "interview rounds": db.query(InterviewPanel).filter(InterviewPanel.job_id == job_id).count(),
        "submissions": db.query(Submission).filter(Submission.demand_id == job_id).count(),
        "offers": db.query(Offer).filter(Offer.job_id == job_id).count()
        + db.query(OfferLetter).filter(OfferLetter.job_id == job_id).count(),
        "allocations": db.query(EmployeeAllocation).filter(EmployeeAllocation.demand_id == job_id).count(),
    }
    return {k: v for k, v in counts.items() if v}


def assert_deletable(db: Session, job_id: str) -> None:
    history = job_history(db, job_id)
    if history:
        detail = ", ".join(f"{n} {k}" for k, n in history.items())
        raise JobHasHistory(f"Job {job_id} has history ({detail}); close it instead of deleting it.")
