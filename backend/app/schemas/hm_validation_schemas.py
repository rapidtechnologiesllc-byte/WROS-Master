"""
Pydantic schemas for Hiring Manager Validation (HRMS-1104 / S-319)
Validation questions before interview scheduling
import logging
"""

import logging
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationQuestionType(str, Enum):
    """Question type enum"""
    YES_NO = "yes_no"
    YES_NO_MAYBE = "yes_no_maybe"
    TEXT = "text"
    MULTIPLE_CHOICE = "multiple_choice"
    RATING = "rating"


class ValidationQuestion(BaseModel):
    """Single validation question definition"""
    question_id: str = Field(..., description="Unique question ID (q_001, q_002, etc.)")
    question_text: str = Field(..., min_length=10, max_length=500, description="Question text")
    question_type: ValidationQuestionType = Field(default=ValidationQuestionType.YES_NO)
    required: bool = Field(default=True, description="Is this question required?")
    follow_up: Optional[str] = Field(None, description="Follow-up question if 'no' answer")
    follow_up_type: Optional[ValidationQuestionType] = Field(None)
    options: Optional[List[str]] = Field(None, description="For multiple choice questions")
    determine_flow: bool = Field(default=False, description="Does this question determine approval flow?")

    class Config:
        use_enum_values = True


class CreateValidationQuestionsRequest(BaseModel):
    """Request to create validation questions for a job"""
    job_id: str = Field(..., description="Job ID to attach questions to")
    questions: List[ValidationQuestion] = Field(..., min_items=1, max_items=10)
    timeout_hours: int = Field(default=24, ge=1, le=72)
    auto_schedule_after_approval: bool = Field(default=True)
    description: Optional[str] = Field(None)


class CreateValidationQuestionsResponse(BaseModel):
    """Response after creating validation questions"""
    status: str = Field("success")
    job_id: str
    question_count: int
    template_version: str
    created_at: datetime
    timeout_hours: int


class HMValidationListResponse(BaseModel):
    """Minimal validation info for list endpoints"""
    id: str
    candidate_id: str
    job_id: str
    hiring_manager_id: str
    status: str
    created_at: datetime
    due_at: datetime
    responded_at: Optional[datetime] = None
    response_time_hours: Optional[int] = None

    class Config:
        from_attributes = True


class CandidateDataResponse(BaseModel):
    """Candidate data for validation display"""
    name: str
    email: str
    phone: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: int = 0
    education: Optional[str] = None
    resume_url: Optional[str] = None


class HMValidationDetailResponse(BaseModel):
    """Full validation with questions and candidate details"""
    id: str
    candidate_id: str
    job_id: str
    status: str
    created_at: datetime
    due_at: datetime
    questions: List[ValidationQuestion]
    candidate_data: CandidateDataResponse
    resume_url: Optional[str] = None
    match_score: float = 0.0


class HMValidationResponseSubmit(BaseModel):
    """HM's submission of validation responses"""
    responses: Dict[str, Any] = Field(..., description="Map of question_id -> response value")
    decision_comment: Optional[str] = Field(None, max_length=1000)
    decision_score: Optional[int] = Field(None, ge=1, le=10)

    @validator('responses')
    def validate_responses(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one response required')
        return v


class HMValidationDecisionResponse(BaseModel):
    """Response after HM submits validation"""
    status: str = Field(..., description="APPROVED, REJECTED, MAYBE, EXPIRED, ESCALATED")
    next_action: str = Field(..., description="What happens next (schedule_interview, return_to_pool, escalate_for_review)")
    interview_scheduled: Optional[Dict[str, Any]] = None
    candidate_notification: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SendValidationToHMRequest(BaseModel):
    """Request to send validation form to hiring manager"""
    job_id: str
    candidate_id: str
    hiring_manager_id: str
    hiring_manager_email: str


class SendValidationToHMResponse(BaseModel):
    """Response after sending validation form"""
    status: str = Field("success")
    validation_id: str
    job_id: str
    candidate_id: str
    sent_to: str
    sent_at: datetime
    expires_in_hours: int
    dashboard_link: str


class RecordHMResponseRequest(BaseModel):
    """Request to record HM response (internal API)"""
    validation_id: str
    responses: Dict[str, Any]
    decision_comment: Optional[str] = None
    decision_score: Optional[int] = None


class RecordHMResponseResponse(BaseModel):
    """Response after recording HM response"""
    status: str = Field("success")
    validation_id: str
    decision: str
    decision_time: datetime
    next_step: str


class ValidationAuditTrailResponse(BaseModel):
    """Single audit trail entry"""
    question_id: str
    question_text: str
    question_type: str
    response_value: str
    response_at: datetime
    time_to_respond_seconds: Optional[int] = None


class ValidationAuditTrailListResponse(BaseModel):
    """Full audit trail for a validation"""
    validation_id: str
    responses: List[ValidationAuditTrailResponse]
    total_responses: int
    completed_at: Optional[datetime] = None


class SendReminderRequest(BaseModel):
    """Request to send reminder email"""
    validation_id: str
    custom_message: Optional[str] = None


class SendReminderResponse(BaseModel):
    """Response after sending reminder"""
    status: str = Field("reminder_sent")
    reminder_sent_at: datetime
    new_due_at: datetime
    attempts: int


class ValidationTemplateResponse(BaseModel):
    """Job's validation question template"""
    job_id: str
    hm_validation_required: bool
    timeout_hours: int
    auto_schedule_after_approval: bool
    questions: List[ValidationQuestion]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EscalateValidationRequest(BaseModel):
    """Request to escalate validation for manual review"""
    validation_id: str
    escalation_reason: str = Field(..., max_length=500)
    escalate_to_user_id: Optional[str] = None


class EscalateValidationResponse(BaseModel):
    """Response after escalation"""
    status: str = Field("escalated")
    validation_id: str
    escalated_at: datetime
    escalated_to: Optional[str] = None
    escalation_reason: str


class ValidationStatsResponse(BaseModel):
    """Statistics for validation performance"""
    total_validations: int
    pending_count: int
    approved_count: int
    rejected_count: int
    maybe_count: int
    expired_count: int
    average_response_time_hours: float
    approval_rate: float  # percent
    rejection_rate: float  # percent


class BulkCreateValidationsRequest(BaseModel):
    """Request to create validations for multiple candidates"""
    job_id: str
    candidate_ids: List[str] = Field(..., min_items=1, max_items=50)
    hiring_manager_id: str
    hiring_manager_email: str


class BulkCreateValidationsResponse(BaseModel):
    """Response after bulk validation creation"""
    status: str = Field("success")
    job_id: str
    created_validations: int
    failed_validations: int
    validation_ids: List[str]
    created_at: datetime
