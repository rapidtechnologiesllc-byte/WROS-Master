from pydantic import BaseModel, Field
from typing import Optional, List
import logging
from datetime import datetime
from app.core.logging import logger

# ============================================
# Interview Panel Schemas
# ============================================
logger = logging.getLogger(__name__)

class InterviewPanelCreate(BaseModel):
    """Schema for creating a new interview panel"""
    candidate_id: str
    round_name: str = Field(..., description="Round name: HR, Technical, Managerial, etc.")
    job_id: Optional[str] = Field(None, description="Job the candidate is being interviewed for")
    rehire_justification: Optional[str] = Field(
        None,
        description=(
            "Required only when the candidate has a past no-hire (Reject) outcome on "
            "record -- explains why they should be re-interviewed. Reviewed by AI, "
            "escalated to the hiring manager if not clearly justified."
        ),
    )

class InterviewPanelResponse(BaseModel):
    """Schema for interview panel response"""
    id: int
    candidate_id: str
    round_name: str
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    created_at: datetime
    rehire_review_id: Optional[int] = Field(
        None, description="Set only when this panel was created via the rehire guard."
    )
    rehire_cleared_by: Optional[str] = Field(
        None, description="'AI' or 'Hiring Manager' -- only set when the rehire guard applied."
    )

class InterviewPanelWithDetails(BaseModel):
    """Schema for interview panel with member details"""
    id: int
    candidate_id: str
    candidate_name: str
    round_name: str
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    created_at: datetime
    member_count: int
    interview_count: int

# ============================================
# Panel Member Schemas
# ============================================

class PanelMemberCreate(BaseModel):
    """Schema for assigning an interviewer to a panel"""
    panel_id: int
    interviewer_id: str

class PanelMemberResponse(BaseModel):
    """Schema for panel member response"""
    id: int
    panel_id: int
    interviewer_id: str
    diversity_warning: Optional[str] = Field(
        None,
        description="Set when this interviewer already served on a panel for this "
                    "same candidate on a different job -- assignment still succeeds, "
                    "this is advisory only.",
    )

class PanelMemberWithDetails(BaseModel):
    """Schema for panel member with interviewer details"""
    id: int
    panel_id: int
    interviewer_id: str
    interviewer_name: str
    interviewer_email: str
    interviewer_role: Optional[str] = None
    business_unit_name: Optional[str] = None

# ============================================
# Interview Schemas
# ============================================

class InterviewCreate(BaseModel):
    """Schema for creating a new interview"""
    panel_id: int
    candidate_id: str
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: str = Field(default="Scheduled", description="Status: Scheduled, Completed, Cancelled")

class InterviewUpdate(BaseModel):
    """Schema for updating an interview"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: Optional[str] = None
    feedback_status: Optional[str] = None # pending, completed, cancelled

class InterviewResponse(BaseModel):
    """Schema for interview response"""
    id: int
    panel_id: int
    candidate_id: str
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: str
    feedback_status: Optional[str] = None # pending, completed, cancelled

class InterviewDetailedResponse(BaseModel):
    """Schema for detailed interview response with related data"""
    id: int
    panel_id: int
    panel_round_name: str
    # 2026-08-05 -- InterviewPanel.job_id already existed (a candidate can
    # be interviewed for more than one job, each panel/round tied to a
    # specific one) but was never surfaced here, so the frontend had no
    # way to group a candidate's interview history by job. Both nullable:
    # a panel with no job_id (legacy data) still returns real round info,
    # just ungrouped.
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    candidate_id: str
    candidate_name: str
    candidate_email: str
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: str
    feedback_count: int
    feedback_status: Optional[str] = None # pending, completed, cancelled

# ============================================
# Interview Feedback Schemas
# ============================================

class InterviewFeedbackCreate(BaseModel):
    """Schema for creating interview feedback"""
    interview_id: int
    interviewer_id: str
    technical_score: int = Field(..., ge=0, le=10, description="Score from 0-10")
    communication_score: int = Field(..., ge=0, le=10, description="Score from 0-10")
    problem_solving_score: int = Field(..., ge=0, le=10, description="Score from 0-10")
    culture_fit_score: int = Field(..., ge=0, le=10, description="Score from 0-10")
    comments: Optional[str] = None
    recommendation: str = Field(..., description="Recommendation: Hire, Hold, or Reject")

class InterviewFeedbackUpdate(BaseModel):
    """Schema for updating interview feedback"""
    technical_score: Optional[int] = Field(None, ge=0, le=10)
    communication_score: Optional[int] = Field(None, ge=0, le=10)
    problem_solving_score: Optional[int] = Field(None, ge=0, le=10)
    culture_fit_score: Optional[int] = Field(None, ge=0, le=10)
    comments: Optional[str] = None
    recommendation: Optional[str] = None

class InterviewFeedbackResponse(BaseModel):
    """Schema for interview feedback response"""
    id: int
    interview_id: int
    interviewer_id: str
    technical_score: int
    communication_score: int
    problem_solving_score: int
    culture_fit_score: int
    comments: Optional[str] = None
    recommendation: str
    submitted_at: datetime

class InterviewFeedbackWithDetails(BaseModel):
    """Schema for feedback with interviewer details"""
    id: int
    interview_id: int
    interviewer_id: str
    interviewer_name: str
    interviewer_email: str
    technical_score: int
    communication_score: int
    problem_solving_score: int
    culture_fit_score: int
    average_score: float
    comments: Optional[str] = None
    recommendation: str
    submitted_at: datetime

# ============================================
# Filter and Query Schemas
# ============================================

class InterviewFilterParams(BaseModel):
    """Schema for filtering interviews"""
    candidate_id: Optional[str] = None
    panel_id: Optional[int] = None
    job_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class InterviewStatistics(BaseModel):
    """Schema for interview statistics"""
    total_interviews: int
    scheduled: int
    completed: int
    cancelled: int
    total_panels: int
    total_feedback: int
    average_feedback_score: Optional[float] = None

# ============================================
# Candidate Interview History
# ============================================

class CandidateInterviewHistory(BaseModel):
    """Schema for candidate's complete interview history"""
    candidate_id: str
    candidate_name: str
    candidate_email: str
    total_interviews: int
    scheduled_interviews: int
    completed_interviews: int
    cancelled_interviews: int
    interviews: List[InterviewDetailedResponse]

# ============================================
# Interviewer Workload
# ============================================

class InterviewerWorkload(BaseModel):
    """Schema for interviewer workload statistics"""
    interviewer_id: str
    interviewer_name: str
    interviewer_email: str
    total_panels: int
    total_interviews: int
    scheduled_interviews: int
    completed_interviews: int
    feedback_submitted: int
    upcoming_interviews: List[InterviewDetailedResponse]

# ============================================
# My Interviews (Panel Member view)
# ============================================

class MyInterviewFeedback(BaseModel):
    """Feedback submitted by the current panel member for a completed interview"""
    feedback_id: int
    technical_score: int
    communication_score: int
    problem_solving_score: int
    culture_fit_score: int
    average_score: float
    comments: Optional[str] = None
    recommendation: str
    submitted_at: datetime

class MyInterviewItem(BaseModel):
    """A single interview entry as seen by the current panel member"""
    interview_id: int
    panel_id: int
    round_name: str
    candidate_id: str
    candidate_name: str
    candidate_email: str
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    status: str
    feedback_submitted: bool
    my_feedback: Optional[MyInterviewFeedback] = None

class MyInterviewsResponse(BaseModel):
    """Response for 'Get My Interviews' endpoint"""
    interviewer_id: str
    interviewer_name: str
    total_interviews: int
    pending_feedback: int
    interviews: List[MyInterviewItem]

# ============================================
# Common Response Schemas
# ============================================

class DeleteResponse(BaseModel):
    """Schema for delete operation response"""
    status: str = "Success"
    message: str

class BulkDeleteResponse(BaseModel):
    """Schema for bulk delete operation response"""
    status: str = "Success"
    message: str
    deleted_count: int

# ============================================
# Hiring Manager Candidate Review
# ============================================

class HMFeedbackDetail(BaseModel):
    """Single interviewer's feedback on one interview round."""
    feedback_id: int
    interviewer_id: str
    interviewer_name: str
    technical_score: int
    communication_score: int
    problem_solving_score: int
    culture_fit_score: int
    average_score: float
    comments: Optional[str] = None
    recommendation: str
    submitted_at: datetime

class HMInterviewRound(BaseModel):
    """One completed interview round with all its feedback entries."""
    interview_id: int
    round_name: str
    start_time: datetime
    end_time: datetime
    status: str
    panel_id: int
    feedbacks: List[HMFeedbackDetail]
    overall_recommendation: str  # "Hire" | "Must Hire" | "Mixed" | "No Feedback"

class HMCandidateReviewItem(BaseModel):
    """Full interview summary for one candidate — used by Hiring Manager review list."""
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_mobile: Optional[str] = None
    candidate_experience: Optional[str] = None
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    pipeline_status: str
    completed_interview_count: int
    approval_endpoint: str   # convenience: the POST path to approve/reject
    interviews: List[HMInterviewRound]

class HMCandidateReviewListResponse(BaseModel):
    """Response for the Hiring Manager candidate review list endpoint."""
    hiring_manager_id: str
    hiring_manager_name: str
    total_candidates: int

# ============================================
# Rehire Guard Schemas (2026-08-05)
# ============================================

class RehireReviewResponse(BaseModel):
    """A single rehire-guard review row."""
    id: int
    candidate_id: str
    candidate_name: Optional[str] = None
    round_name: str
    job_id: Optional[str] = None
    job_title: Optional[str] = None
    requested_by: Optional[str] = None
    requested_by_name: Optional[str] = None
    justification: str
    past_no_hire_panel_ids: Optional[List[int]] = None
    status: str  # PENDING_HM_APPROVAL | AI_CLEARED | APPROVED | REJECTED
    ai_decision: Optional[str] = None
    ai_reasoning: Optional[str] = None
    ai_confidence: Optional[float] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    resulting_panel_id: Optional[int] = None
    created_at: datetime

class RehireReviewListResponse(BaseModel):
    total: int
    reviews: List[RehireReviewResponse]

class RehireReviewDecideRequest(BaseModel):
    decision: str = Field(..., description="'approve' or 'reject'")
    note: Optional[str] = None
    candidates: List[HMCandidateReviewItem]
