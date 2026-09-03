"""
Pydantic Schemas -- S-037/HRMS-0437 Technical Qualification Score,
S-038/HRMS-0438 Compensation Fit Score, S-039/HRMS-0439 Availability
Score, S-040/HRMS-0440 Overall Candidate Score & Ranking.
"""
from datetime import datetime
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class TechnicalScoreResponse(BaseModel):
    candidate_id: str
    job_id: str
    technical_score: Optional[int]
    compensation_score: Optional[int]
    availability_score: Optional[int]
    overall_score: Optional[int]
    score_breakdown: Optional[Dict]
    calculated_at: Optional[datetime]


class RankedCandidateItem(BaseModel):
    rank: int
    candidate_id: str
    candidate_name: str
    overall_score: Optional[int]
    technical_score: Optional[int]
    compensation_score: Optional[int]
    availability_score: Optional[int]
    resume_completeness_score: Optional[int]
    score_breakdown: Optional[Dict]


class RankedCandidatesResponse(BaseModel):
    job_id: str
    job_title: str
    candidates: List[RankedCandidateItem]
    total_count: int
