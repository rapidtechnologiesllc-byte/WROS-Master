"""
Pydantic schemas — HRMS-0711 Client Submission Pipeline API. Also closes
canonical S-249 ("Restrict Market Candidate Submission"): the real
employee-eligibility guard (check_market_profile_rule()) is already
enforced inside create_submission() -- this just makes the whole
pipeline reachable over HTTP for the first time.
import logging
"""

import logging
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CreateSubmissionRequest(BaseModel):
    demand_id: str
    candidate_id: str
    submission_rank: Optional[int] = None
    submitted_as_resume_url: Optional[str] = None
    source: str = "INTERNAL"
    subvendor_id: Optional[str] = None


class SubmissionBlocker(BaseModel):
    error: str
    message: str


class SubmissionItem(BaseModel):
    id: str
    demand_id: str
    demand_job_title: str
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
    new_status: str = Field(..., min_length=1)
    client_feedback: Optional[str] = None


class SubmissionViolationItem(BaseModel):
    id: str
    candidate_id: str
    violation_type: str
    candidate_status_at_time: Optional[str] = None
    blocked_message: Optional[str] = None
    attempted_at: Optional[datetime] = None


class SubmissionViolationListResponse(BaseModel):
    violations: List[SubmissionViolationItem]
