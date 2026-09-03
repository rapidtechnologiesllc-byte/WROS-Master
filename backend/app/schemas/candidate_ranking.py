# pyrefly: ignore [missing-import]
"""
import logging
HRMS-1105 (S-320) -- Candidate Ranking & Scoring Schemas.

Pydantic models for request/response validation.
"""
import logging
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from app.core.logging import logger

logger = logging.getLogger(__name__)

class FitScoreComponentsResponse(BaseModel):
    """Score breakdown for candidate-job fit."""
    skills_match: int = Field(..., ge=0, le=100, description="Skills match score 0-100")
    experience_level: int = Field(..., ge=0, le=100, description="Experience match score 0-100")
    location_match: int = Field(..., ge=0, le=100, description="Location match score 0-100")
    resume_completeness: int = Field(..., ge=0, le=100, description="Resume quality score 0-100")

class ScoringWeightsResponse(BaseModel):
    """Weights used in fit score calculation."""
    skills: int = Field(default=40, description="Skills component weight")
    experience: int = Field(default=35, description="Experience component weight")
    location: int = Field(default=15, description="Location component weight")
    resume: int = Field(default=10, description="Resume component weight")

class CalculateFitScoreRequest(BaseModel):
    """Request to calculate fit score for a candidate against a job."""
    candidate_id: str = Field(..., description="Candidate ID")
    demand_id: str = Field(..., description="Demand (job) ID")

class CalculateFitScoreResponse(BaseModel):
    """Response with calculated fit score and components."""
    status: str = Field(..., description="success or error")
    candidate_id: str
    demand_id: str
    fit_score: Optional[int] = Field(None, ge=0, le=100, description="Overall fit score 0-100")
    components: Optional[FitScoreComponentsResponse] = None
    weights: Optional[ScoringWeightsResponse] = None
    recommendation: Optional[str] = Field(
        None,
        description="STRONG_MATCH (85+), GOOD_MATCH (70-84), FAIR_MATCH (50-69), WEAK_MATCH (<50)"
    )
    calculated_at: Optional[str] = None
    error: Optional[str] = None

class RankedCandidateResponse(BaseModel):
    """A single candidate in the ranking."""
    rank: int = Field(..., description="Rank position (1 = best match)")
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_job_title: Optional[str] = None
    fit_score: int = Field(..., ge=0, le=100)
    recommendation: str
    components: FitScoreComponentsResponse

class RankCandidatesRequest(BaseModel):
    """Request to rank candidates for a job."""
    demand_id: str = Field(..., description="Demand (job) ID")
    limit: Optional[int] = Field(50, ge=1, le=1000, description="Max candidates to evaluate")

class RankCandidatesResponse(BaseModel):
    """Response with ranked candidates."""
    status: str = Field(..., description="success or error")
    demand_id: str
    total_candidates_evaluated: Optional[int] = None
    ranked_candidates: Optional[List[RankedCandidateResponse]] = None
    ranked_at: Optional[str] = None
    error: Optional[str] = None

class IdentifyBestMatchRequest(BaseModel):
    """Request to identify best candidate for a job."""
    demand_id: str = Field(..., description="Demand (job) ID")

class BestMatchComponentsResponse(BaseModel):
    """Score breakdown for best match."""
    skills_match: int = Field(..., ge=0, le=100)
    experience_level: int = Field(..., ge=0, le=100)
    location_match: int = Field(..., ge=0, le=100)
    resume_completeness: int = Field(..., ge=0, le=100)

class IdentifyBestMatchResponse(BaseModel):
    """Response with best matching candidate."""
    status: str = Field(..., description="success or error")
    demand_id: str
    best_match_candidate_id: Optional[str] = None
    best_match_candidate_name: Optional[str] = None
    best_match_candidate_email: Optional[str] = None
    fit_score: Optional[int] = Field(None, ge=0, le=100)
    recommendation: Optional[str] = None
    components: Optional[BestMatchComponentsResponse] = None
    ready_to_interview: Optional[bool] = Field(None, description="True if fit_score >= 70")
    identified_at: Optional[str] = None
    error: Optional[str] = None
