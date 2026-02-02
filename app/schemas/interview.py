from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ============================================
# Interview Panel Schemas
# ============================================

class InterviewPanelCreate(BaseModel):
    """Schema for creating a new interview panel"""
    candidate_id: str
    round_name: str = Field(..., description="Round name: HR, Technical, Managerial, etc.")

class InterviewPanelResponse(BaseModel):
    """Schema for interview panel response"""
    id: int
    candidate_id: str
    round_name: str
    created_at: datetime

class InterviewPanelWithDetails(BaseModel):
    """Schema for interview panel with member details"""
    id: int
    candidate_id: str
    candidate_name: str
    round_name: str
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

class PanelMemberWithDetails(BaseModel):
    """Schema for panel member with interviewer details"""
    id: int
    panel_id: int
    interviewer_id: str
    interviewer_name: str
    interviewer_email: str


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

class InterviewDetailedResponse(BaseModel):
    """Schema for detailed interview response with related data"""
    id: int
    panel_id: int
    panel_round_name: str
    candidate_id: str
    candidate_name: str
    candidate_email: str
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: str
    feedback_count: int


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
