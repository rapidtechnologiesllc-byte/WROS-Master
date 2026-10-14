"""
Pydantic schemas — HRMS-0711 Client Submission Pipeline API. Also closes
canonical S-249 ("Restrict Market Candidate Submission"): the real
employee-eligibility guard (check_market_profile_rule()) is already
enforced inside create_submission() -- this just makes the whole
pipeline reachable over HTTP for the first time.
"""

import logging
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, model_validator

from app.models.submission import SUBMISSION_SOURCES, SUBMISSION_STATUSES

logger = logging.getLogger(__name__)

class CreateSubmissionRequest(BaseModel):
    demand_id: str
    candidate_id: str
    submission_rank: Optional[int] = None
    submitted_as_resume_url: Optional[str] = None
    # the submissions.source check constraint (app.models.submission.SUBMISSION_SOURCES): any other
    # value is a 422 here, not a constraint violation (500) at insert
    source: Literal[SUBMISSION_SOURCES] = "INTERNAL"
    subvendor_id: Optional[str] = None

    @model_validator(mode="after")
    def _subvendor_named(self):
        if self.source == "SUBVENDOR" and not self.subvendor_id:
            raise ValueError("subvendor_id is required when source is SUBVENDOR.")
        return self

class SubmissionBlocker(BaseModel):
    error: str
    message: str

class SubmissionItem(BaseModel):
    id: str
    demand_id: str
    demand_job_title: str
    client_name: Optional[str] = None
    candidate_id: str
    candidate_name: str
    status: str
    submitted_at: Optional[datetime] = None
    client_feedback: Optional[str] = None
    client_response_at: Optional[datetime] = None
    submission_rank: Optional[int] = None
    source: str

class SubmissionListResponse(BaseModel):
    submissions: List[SubmissionItem]

class ClientResponseRequest(BaseModel):
    new_status: Literal[SUBMISSION_STATUSES]
    client_feedback: Optional[str] = None

class SubmissionJobOption(BaseModel):
    id: str
    job_title: str
    client_id: str
    client_name: str
    status: str
    business_unit_id: Optional[int] = None

class SubmissionCandidateOption(BaseModel):
    id: str
    name: str
    employee_status: str
    total_experience_months: Optional[int] = None
    employment_type: Optional[str] = None
    submission_bu_id: Optional[int] = None
    # experience / employment-type gate messages that will block any submission (same checks
    # as POST); BGV and hiring-pipeline gates are only decided on POST
    issues: List[str] = []

class SubmissionOptionsResponse(BaseModel):
    """What the Submissions screen offers: open client jobs and bench/active/allocated employees
    in the caller's scope. Eligibility is still decided by POST /submissions."""
    jobs: List[SubmissionJobOption]
    candidates: List[SubmissionCandidateOption]

class SubmissionViolationItem(BaseModel):
    id: str
    candidate_id: str
    violation_type: str
    candidate_status_at_time: Optional[str] = None
    blocked_message: Optional[str] = None
    attempted_at: Optional[datetime] = None

class SubmissionViolationListResponse(BaseModel):
    violations: List[SubmissionViolationItem]
