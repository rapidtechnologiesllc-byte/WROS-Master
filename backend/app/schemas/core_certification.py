"""Pydantic schemas -- Core certification (app.services.core_certification_service)."""
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CoreCertificationRequestItem(BaseModel):
    id: str
    employee_id: str
    candidate_id: Optional[str] = None
    employee_name: str
    status: str
    billable_days: int
    counted_from: Optional[date] = None
    bu_head_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_by_user_id: Optional[str] = None
    decided_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    follow_up_plan: Optional[List[Dict]] = None
    # for a pending request: whether the employee still qualifies and whether the viewer decides
    still_eligible: Optional[bool] = None
    eligibility_reasons: List[str] = []
    can_decide: bool = False
    chat_in_progress: bool = False


class CoreCertificationListResponse(BaseModel):
    requests: List[CoreCertificationRequestItem]


class EligibilityResponse(BaseModel):
    employee_id: str
    eligible: bool
    billable_days: int
    required_days: int
    counted_from: Optional[date] = None
    reasons: List[str]


class RejectChatRequest(BaseModel):
    message: Optional[str] = Field(default=None, max_length=2000)


class RejectChatResponse(BaseModel):
    reply: str
    done: bool
