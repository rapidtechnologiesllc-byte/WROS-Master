"""
HRMS-0312: Offer Management Schemas
Pydantic schemas for offer request/response validation.
"""
from datetime import datetime, date
from typing import Optional, Dict, List, Any
import logging
from pydantic import BaseModel, Field, EmailStr, validator
from app.core.logging import logger

logger = logging.getLogger(__name__)

class BenefitsSchema(BaseModel):
    """Benefits package included with offer."""
    health_insurance: Optional[str] = None
    retirement_401k: Optional[bool] = False
    paid_time_off_days: Optional[int] = 20
    bonus_percentage: Optional[float] = 0.0
    stock_options: Optional[bool] = False
    additional: Optional[Dict[str, Any]] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "health_insurance": "PPO Plan",
                "retirement_401k": True,
                "paid_time_off_days": 20,
                "bonus_percentage": 10.0,
                "stock_options": False
            }
        }

class OfferCreateRequest(BaseModel):
    """Request to create a new offer."""
    candidate_id: str = Field(..., description="Unique candidate identifier")
    job_id: str = Field(..., description="Job position ID")
    position_title: str = Field(..., min_length=1, description="Job title for the offer")
    base_salary_usd_cents: int = Field(..., ge=0, description="Annual salary in USD cents")
    signing_bonus_usd_cents: int = Field(default=0, ge=0, description="One-time signing bonus in USD cents")
    expected_start_date: date = Field(..., description="Expected start date")
    benefits: Optional[BenefitsSchema] = Field(default=None, description="Benefits package")
    approval_notes: Optional[str] = Field(None, description="Internal notes for approvers")

    @validator("base_salary_usd_cents")
    def validate_salary(cls, v):
        if v <= 0:
            raise ValueError("Salary must be greater than 0")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "candidate_id": "cand_123",
                "job_id": "job_456",
                "position_title": "Senior Software Engineer",
                "base_salary_usd_cents": 15000000,
                "signing_bonus_usd_cents": 100000,
                "expected_start_date": "2026-09-01",
                "benefits": {
                    "health_insurance": "PPO Plan",
                    "retirement_401k": True,
                    "paid_time_off_days": 20
                }
            }
        }

class OfferApproveRequest(BaseModel):
    """Request to approve an offer."""
    approved_by_user_id: str = Field(..., description="User ID of approver")
    approval_notes: Optional[str] = Field(None, description="Approval notes")

    class Config:
        json_schema_extra = {
            "example": {
                "approved_by_user_id": "user_789",
                "approval_notes": "Approved - competitive salary for market"
            }
        }

class OfferRejectRequest(BaseModel):
    """Request to reject an offer."""
    rejection_reason: str = Field(..., min_length=1, description="Reason for rejection")

    class Config:
        json_schema_extra = {
            "example": {
                "rejection_reason": "Candidate overqualified for this position"
            }
        }

class OfferSendRequest(BaseModel):
    """Request to send offer to candidate."""
    candidate_email: EmailStr = Field(..., description="Candidate email address")
    expiration_days: int = Field(default=7, ge=1, le=30, description="Days until offer expires")

    class Config:
        json_schema_extra = {
            "example": {
                "candidate_email": "jane.doe@example.com",
                "expiration_days": 7
            }
        }

class OfferAcceptanceRequest(BaseModel):
    """Request to accept an offer (candidate action)."""
    offer_id: str = Field(..., description="Offer ID to accept")
    candidate_id: str = Field(..., description="Candidate accepting the offer")
    start_date: Optional[date] = Field(None, description="Confirmed start date")

    class Config:
        json_schema_extra = {
            "example": {
                "offer_id": "offer_123",
                "candidate_id": "cand_123",
                "start_date": "2026-09-01"
            }
        }

class OfferRetractionRequest(BaseModel):
    """Request to retract an offer."""
    retraction_reason: str = Field(..., min_length=1, description="Reason for retraction")

    class Config:
        json_schema_extra = {
            "example": {
                "retraction_reason": "Position filled by another candidate"
            }
        }

class OfferResponse(BaseModel):
    """Complete offer details response."""
    id: str = Field(..., description="Offer ID")
    candidate_id: str = Field(..., description="Candidate ID")
    job_id: str = Field(..., description="Job ID")
    position_title: str = Field(..., description="Position title")
    base_salary_usd_cents: int = Field(..., description="Base salary in USD cents")
    signing_bonus_usd_cents: int = Field(..., description="Signing bonus in USD cents")
    expected_start_date: date = Field(..., description="Expected start date")
    benefits: Dict[str, Any] = Field(default_factory=dict, description="Benefits package")
    status: str = Field(..., description="Current offer status")
    created_at: datetime = Field(..., description="Creation timestamp")
    sent_at: Optional[datetime] = Field(None, description="Send timestamp")
    sent_to_email: Optional[str] = Field(None, description="Email offer was sent to")
    expiration_date: Optional[datetime] = Field(None, description="Offer expiration date")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    approved_by_user_id: Optional[str] = Field(None, description="Approver user ID")
    approval_notes: Optional[str] = Field(None, description="Approval notes")
    accepted_at: Optional[datetime] = Field(None, description="Acceptance timestamp")
    rejected_at: Optional[datetime] = Field(None, description="Rejection timestamp")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")
    retracted_at: Optional[datetime] = Field(None, description="Retraction timestamp")
    retraction_reason: Optional[str] = Field(None, description="Retraction reason")
    signed_at: Optional[datetime] = Field(None, description="Signing timestamp")
    document_url: Optional[str] = Field(None, description="Offer document URL")
    signed_document_url: Optional[str] = Field(None, description="Signed document URL")
    created_by_user_id: str = Field(..., description="Creator user ID")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "offer_123",
                "candidate_id": "cand_123",
                "job_id": "job_456",
                "position_title": "Senior Software Engineer",
                "base_salary_usd_cents": 15000000,
                "signing_bonus_usd_cents": 100000,
                "expected_start_date": "2026-09-01",
                "benefits": {"health_insurance": "PPO Plan"},
                "status": "SENT",
                "created_at": "2026-08-15T10:00:00",
                "sent_at": "2026-08-15T14:30:00",
                "created_by_user_id": "user_789"
            }
        }

class OfferListResponse(BaseModel):
    """List of offers response."""
    total: int = Field(..., description="Total offers returned")
    offers: List[OfferResponse] = Field(default_factory=list, description="Offers list")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 2,
                "offers": [
                    {
                        "id": "offer_123",
                        "candidate_id": "cand_123",
                        "status": "SENT"
                    }
                ]
            }
        }

class OfferStatusResponse(BaseModel):
    """Response after status change."""
    status: str = Field("success", description="Operation status")
    message: str = Field(..., description="Status message")
    offer_id: str = Field(..., description="Offer ID")
    offer_status: str = Field(..., description="New offer status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Offer approved successfully",
                "offer_id": "offer_123",
                "offer_status": "APPROVED",
                "timestamp": "2026-08-15T14:30:00"
            }
        }

class OfferApprovalResponse(OfferStatusResponse):
    """Response after offer approval."""
    approved_at: datetime = Field(..., description="Approval timestamp")
    approved_by_user_id: str = Field(..., description="Approver ID")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Offer approved successfully",
                "offer_id": "offer_123",
                "offer_status": "APPROVED",
                "approved_at": "2026-08-15T14:30:00",
                "approved_by_user_id": "user_789"
            }
        }

class OfferSendResponse(OfferStatusResponse):
    """Response after sending offer."""
    sent_to_email: str = Field(..., description="Email offer was sent to")
    sent_at: datetime = Field(..., description="Send timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Offer sent to candidate",
                "offer_id": "offer_123",
                "offer_status": "SENT",
                "sent_to_email": "jane@example.com",
                "sent_at": "2026-08-15T14:30:00",
                "expires_at": "2026-08-22T14:30:00"
            }
        }

class OfferAcceptanceResponse(OfferStatusResponse):
    """Response after offer acceptance."""
    accepted_at: datetime = Field(..., description="Acceptance timestamp")
    candidate_id: str = Field(..., description="Candidate ID")
    start_date: date = Field(..., description="Confirmed start date")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Offer accepted successfully",
                "offer_id": "offer_123",
                "offer_status": "ACCEPTED",
                "accepted_at": "2026-08-20T10:00:00",
                "candidate_id": "cand_123",
                "start_date": "2026-09-01"
            }
        }

class OfferSummary(BaseModel):
    """Quick summary of offer for list views."""
    id: str = Field(..., description="Offer ID")
    candidate_id: str = Field(..., description="Candidate ID")
    candidate_name: Optional[str] = Field(None, description="Candidate name")
    position_title: str = Field(..., description="Position title")
    status: str = Field(..., description="Offer status")
    base_salary_usd_cents: int = Field(..., description="Base salary in USD cents")
    expected_start_date: date = Field(..., description="Start date")
    created_at: datetime = Field(..., description="Creation timestamp")
    sent_at: Optional[datetime] = Field(None, description="Send timestamp")
    expiration_date: Optional[datetime] = Field(None, description="Expiration timestamp")

    class Config:
        from_attributes = True
