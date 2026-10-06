"""Candidate pipeline stage filters.

A candidate's stage is not on Candidate (there is no Candidate.status); it
lives in CandidateStatus.piplineStatus as free text written by several
screens ("Applied", "Interview", "Pre-Onboarding", "Pre-onboarding-Approval",
"Rejected", "EMPLOYEE", ...). Services that need "candidates at stage X"
use pipeline_stage_in(), a drop-in filter expression:

    db.query(Candidate).filter(pipeline_stage_in("OFFER", "HIRED"))
"""
from sqlalchemy import func, or_, select

from app.models.candidate import Candidate, CandidateStatus

# Stage -> case-insensitive LIKE patterns over the spellings in use
STAGE_PATTERNS = {
    "APPLIED": ["applied", "new", "open"],
    "ENGAGED": ["engaged"],
    "QUALIFYING": ["qualif%"],
    "QUALIFIED": ["qualif%"],
    "SCREENING": ["screen%"],
    "SCREENED": ["screen%"],
    "SUBMITTED": ["submitted%"],
    "SUBMITTED_TO_JOB": ["submitted%"],
    "INTERVIEW": ["%interview%"],
    "INTERVIEWING": ["%interview%"],
    "INTERVIEWED": ["%interview%"],
    "OFFER": ["%offer%"],
    "PREBOARDING": ["pre-onboarding%", "preboarding%", "pre_onboarding%"],
    "HIRED": ["hired", "joined", "employee", "onboarded"],
    "JOINED": ["hired", "joined", "employee", "onboarded"],
    "REJECTED": ["%reject%"],
}


def pipeline_stage_condition(*stages: str):
    """SQL condition on CandidateStatus.piplineStatus for any of the stages."""
    patterns = []
    for stage in stages:
        key = stage.upper()
        if key not in STAGE_PATTERNS:
            raise ValueError(f"Unknown candidate pipeline stage {stage!r}; known: {sorted(STAGE_PATTERNS)}")
        patterns.extend(STAGE_PATTERNS[key])
    column = func.lower(CandidateStatus.piplineStatus)
    return or_(*[column.like(p) for p in patterns])


def pipeline_stage_in(*stages: str):
    """Filter expression on Candidate: its pipeline stage is one of stages."""
    return Candidate.candidateID.in_(
        select(CandidateStatus.candidateID).where(pipeline_stage_condition(*stages))
    )


# ---- Shared real-data definitions for funnel/accountability reporting ----

def has_thunder_conversation():
    """Filter on Candidate: Thunder has a conversation with them (contacted)."""
    from app.models.candidate_ai import CandidateConversation
    return Candidate.candidateID.in_(select(CandidateConversation.candidate_id))


def interview_scheduled_condition():
    """Interview (app.models.user.Interview) not cancelled. Statuses are
    free text: Scheduled / Completed / Cancelled."""
    from app.models.user import Interview
    return func.lower(Interview.status) != "cancelled"


def interview_feedback_done_condition():
    from app.models.user import Interview
    return func.lower(Interview.feedback_status) == "completed"


OFFER_EXTENDED_STATUSES = ("Released", "Accepted")


def employee_active_allocation_ids():
    """Employee ids with an ACTIVE allocation (Employee has no project column)."""
    from app.models.employee_allocation import EmployeeAllocation
    return select(EmployeeAllocation.employee_id).where(EmployeeAllocation.status == "ACTIVE")
