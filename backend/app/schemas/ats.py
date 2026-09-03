"""
ATS Pydantic Schemas
import logging
"""

import logging
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ATSScoreBreakdown(BaseModel):
    """Fine-grained dimension scores."""
    skills_score: int       # 0–25
    experience_score: int   # 0–25
    education_score: int    # 0–20
    location_score: int     # 0–15
    culture_fit_score: int  # 0–15


class ATSScoreResponse(BaseModel):
    """Full ATS result returned to the caller."""
    ats_score_id: int
    candidate_id: str
    job_id: Optional[str] = None

    overall_score: int          # 0–100
    breakdown: ATSScoreBreakdown

    profile_summary: Optional[str] = None
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendation: str         # Shortlist | Review | Reject
    score_rationale: Optional[str] = None
    ats_verdict: Optional[str] = None

    scored_at: datetime


class CandidateATSListItem(BaseModel):
    """Summary row for HR dashboard listing."""
    ats_score_id: int
    candidate_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    overall_score: int
    recommendation: Optional[str] = None
    ats_verdict: Optional[str] = None
    scored_at: datetime


class AllATSScoresResponse(BaseModel):
    total: int
    scores: List[CandidateATSListItem]


class ATSRescoringRequest(BaseModel):
    """Re-trigger ATS scoring for an existing candidate/job pair."""
    candidate_id: str
    job_id: str
