"""
S-311: Interview Decision Engine — Pydantic Schemas
Request/Response models for interview decision endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime


# ────────────────────────────────────────────────────────────────────────────
# Request Schemas
# ────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

class GetInterviewStatusRequest(BaseModel):
    """Request to get interview status."""
    interview_id: int = Field(..., description="Interview ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")

    class Config:
        schema_extra = {
            "example": {
                "interview_id": 1,
                "tenant_id": 1
            }
        }


class CalculatePanelDecisionRequest(BaseModel):
    """Request to calculate panel decision."""
    interview_id: int = Field(..., description="Interview ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")

    class Config:
        schema_extra = {
            "example": {
                "interview_id": 1,
                "tenant_id": 1
            }
        }


class MoveToOfferRequest(BaseModel):
    """Request to create offer after interview approval."""
    interview_id: int = Field(..., description="Interview ID")
    candidate_id: str = Field(..., description="Candidate ID")
    job_id: str = Field(..., description="Job ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")
    approved_salary_usd_cents: int = Field(..., description="Approved salary in USD cents")
    position_title: str = Field(..., description="Position title")
    start_date: datetime = Field(..., description="Expected start date")
    created_by_user_id: str = Field(..., description="User ID creating the offer")

    class Config:
        schema_extra = {
            "example": {
                "interview_id": 1,
                "candidate_id": "C123",
                "job_id": "J456",
                "tenant_id": 1,
                "approved_salary_usd_cents": 10000000,
                "position_title": "Senior Software Engineer",
                "start_date": "2026-09-01T00:00:00",
                "created_by_user_id": "U789"
            }
        }


class RejectCandidateRequest(BaseModel):
    """Request to reject candidate after interview."""
    interview_id: int = Field(..., description="Interview ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")
    rejection_reason: str = Field(..., description="Reason for rejection")
    rejected_by_user_id: str = Field(..., description="User ID rejecting the candidate")

    class Config:
        schema_extra = {
            "example": {
                "interview_id": 1,
                "tenant_id": 1,
                "rejection_reason": "Candidate did not meet technical requirements",
                "rejected_by_user_id": "U789"
            }
        }


# ────────────────────────────────────────────────────────────────────────────
# Response Schemas
# ────────────────────────────────────────────────────────────────────────────

class FeedbackDetail(BaseModel):
    """Detail of a single feedback."""
    feedback_id: Optional[str] = None
    interviewer_id: str
    technical_score: Optional[int] = None
    communication_score: Optional[int] = None
    problem_solving_score: Optional[int] = None
    culture_fit_score: Optional[int] = None
    submitted_at: Optional[str] = None


class GetInterviewStatusResponse(BaseModel):
    """Response for get interview status."""
    interview_id: int
    candidate_id: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    feedback_received: int
    feedbacks: List[FeedbackDetail]

    class Config:
        schema_extra = {
            "example": {
                "interview_id": 1,
                "candidate_id": "C123",
                "status": "Completed",
                "start_time": "2026-08-15T10:00:00",
                "end_time": "2026-08-15T11:00:00",
                "feedback_received": 3,
                "feedbacks": [
                    {
                        "feedback_id": "F001",
                        "interviewer_id": "U789",
                        "technical_score": 4,
                        "communication_score": 5,
                        "problem_solving_score": 4,
                        "culture_fit_score": 5,
                        "submitted_at": "2026-08-15T11:30:00"
                    }
                ]
            }
        }


class VotingResult(BaseModel):
    """Voting breakdown from panel."""
    strong_yes: int
    yes: int
    no: int
    strong_no: int
    abstain: int
    total_panelists: int


class AverageScores(BaseModel):
    """Average interview scores."""
    technical: Optional[float] = None
    communication: Optional[float] = None
    problem_solving: Optional[float] = None
    culture_fit: Optional[float] = None


class CalculatePanelDecisionResponse(BaseModel):
    """Response for calculate panel decision."""
    decision: str = Field(..., description="Decision: APPROVED, REJECTED, PENDING_REVIEW, etc.")
    reason: str = Field(..., description="Reason for decision")
    voting: VotingResult = Field(..., description="Voting breakdown")
    average_scores: AverageScores = Field(..., description="Average interview scores")

    class Config:
        schema_extra = {
            "example": {
                "decision": "APPROVED",
                "reason": "Panel majority: move to offer",
                "voting": {
                    "strong_yes": 2,
                    "yes": 1,
                    "no": 0,
                    "strong_no": 0,
                    "abstain": 0,
                    "total_panelists": 3
                },
                "average_scores": {
                    "technical": 4.33,
                    "communication": 4.67,
                    "problem_solving": 4.33,
                    "culture_fit": 4.67
                }
            }
        }


class MoveToOfferResponse(BaseModel):
    """Response for move to offer."""
    status: str = Field(..., description="Status: success or error")
    message: Optional[str] = None
    offer_id: Optional[str] = None
    candidate_id: Optional[str] = None
    position_title: Optional[str] = None
    salary_usd_cents: Optional[int] = None
    start_date: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "offer_id": "O123",
                "candidate_id": "C123",
                "position_title": "Senior Software Engineer",
                "salary_usd_cents": 10000000,
                "start_date": "2026-09-01"
            }
        }


class RejectCandidateResponse(BaseModel):
    """Response for reject candidate."""
    status: str = Field(..., description="Status: success or error")
    message: Optional[str] = None
    interview_id: Optional[int] = None
    candidate_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejected_at: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "interview_id": 1,
                "candidate_id": "C123",
                "rejection_reason": "Candidate did not meet technical requirements",
                "rejected_at": "2026-08-15T14:30:00"
            }
        }
