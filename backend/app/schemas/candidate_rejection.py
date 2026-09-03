"""
import logging
Schemas for Candidate Rejection Workflow

Includes request/response models for:
- reject_candidate(): Create rejection record
- send_rejection_email(): Send rejection notification
- archive_candidate(): Archive/soft-delete candidate
"""

import logging
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class CandidateRejectionReasonResponse(BaseModel):
    """Response model for predefined rejection reasons."""
    id: int
    reason_code: str
    reason_label: str
    reason_description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class RejectCandidateRequest(BaseModel):
    """
    Request to reject a candidate.

    Fields:
    - candidate_id: ID of candidate to reject (required)
    - job_id: Job ID this rejection relates to (optional)
    - rejection_reason: Reason code or free-text reason (required)
    - rejection_note: Detailed note about rejection (optional)
    - send_email: Should we send rejection email? (default: True)
    - tenant_id: Tenant context (optional, defaults to 1)
    """
    candidate_id: str
    job_id: Optional[str] = None
    rejection_reason: str
    rejection_note: Optional[str] = None
    send_email: bool = True
    tenant_id: Optional[int] = 1


class RejectCandidateResponse(BaseModel):
    """Response after rejecting a candidate."""
    rejection_id: int
    candidate_id: str
    job_id: Optional[str] = None
    rejection_reason: str
    rejection_status: str  # "ACTIVE"
    rejected_at: datetime
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    message: str

    class Config:
        from_attributes = True


class SendRejectionEmailRequest(BaseModel):
    """
    Request to send rejection email to candidate.

    Fields:
    - rejection_id: ID of rejection record to notify about (required)
    - include_feedback: Include detailed feedback in email? (default: False)
    - include_next_steps: Include what candidate can do next? (default: True)
    """
    rejection_id: int
    include_feedback: bool = False
    include_next_steps: bool = True


class SendRejectionEmailResponse(BaseModel):
    """Response after sending rejection email."""
    rejection_id: int
    candidate_id: str
    candidate_email: str
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    message: str

    class Config:
        from_attributes = True


class ArchiveCandidateRequest(BaseModel):
    """
    Request to archive a rejected candidate.
    Soft-delete: candidate remains in DB for audit trail.

    Fields:
    - candidate_id: ID of candidate to archive (required)
    - archive_reason: Why are we archiving? (optional)
    - archive_note: Additional context (optional)
    """
    candidate_id: str
    archive_reason: Optional[str] = None
    archive_note: Optional[str] = None


class ArchiveCandidateResponse(BaseModel):
    """Response after archiving a candidate."""
    rejection_id: int
    candidate_id: str
    rejection_status: str  # "ARCHIVED"
    archived_at: datetime
    message: str

    class Config:
        from_attributes = True


class CandidateRejectionResponse(BaseModel):
    """Full rejection record response."""
    id: int
    candidate_id: str
    job_id: Optional[str] = None
    rejection_reason: str
    rejection_note: Optional[str] = None
    rejected_by_user_id: Optional[str] = None
    rejected_at: datetime
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    rejection_status: str  # "ACTIVE" or "ARCHIVED"
    archived_at: Optional[datetime] = None
    archived_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ListCandidateRejectionsResponse(BaseModel):
    """Response listing candidate rejections."""
    total: int
    page: int
    page_size: int
    rejections: List[CandidateRejectionResponse]


class CandidateRejectionStatusResponse(BaseModel):
    """Query rejection status for a candidate."""
    candidate_id: str
    is_rejected: bool
    rejection_count: int
    latest_rejection: Optional[CandidateRejectionResponse] = None
    all_rejections: List[CandidateRejectionResponse]
