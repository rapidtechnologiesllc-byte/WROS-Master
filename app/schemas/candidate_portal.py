"""
Pydantic Schemas -- S-017/HRMS-0417 Candidate Self-Service Web Portal.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PortalStageBadge(BaseModel):
    label: str
    color: str


class PortalThreadMessage(BaseModel):
    id: int
    direction: str
    sender_type: str
    channel: str
    message_body: str
    sent_at: Optional[datetime]


class PortalHomeResponse(BaseModel):
    candidate_name: str
    stage: PortalStageBadge
    pending_actions: List[str]
    recent_messages: List[PortalThreadMessage]
    conversation_id: Optional[int]


class PortalThreadResponse(BaseModel):
    conversation_id: Optional[int]
    messages: List[PortalThreadMessage]


class PortalMissingFieldItem(BaseModel):
    field: str
    label: str
    source: str


class PortalProfileFieldsResponse(BaseModel):
    total_missing: int
    missing_fields: List[PortalMissingFieldItem]


class PortalProfileUpdateRequest(BaseModel):
    fields: Dict[str, Any] = Field(..., description="field_name -> value, only real candidate/info-form fields accepted")


class PortalProfileUpdateResponse(BaseModel):
    updated: List[str]
    skipped: List[str]
    total_missing: int
    missing_fields: List[PortalMissingFieldItem]


class PortalInterviewItem(BaseModel):
    id: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    format: str
    meeting_link: Optional[str]
    prep_tip: str


class PortalInterviewsResponse(BaseModel):
    interviews: List[PortalInterviewItem]


class PortalRescheduleRequest(BaseModel):
    note: str = Field("", max_length=1000)


class PortalRescheduleResponse(BaseModel):
    request_id: int
    submitted_at: Optional[datetime]


class PortalTrackRequest(BaseModel):
    """S-346 Step 4 / S-347 Step 4 -- a portal page view. page is a free
    label (home|messages|profile|interviews|...), not FK'd to anything --
    matches whatever route the frontend is actually on."""
    page: str = Field(..., max_length=50)
    time_on_page_seconds: int = Field(..., ge=0)
    scroll_depth_pct: Optional[int] = Field(None, ge=0, le=100)


class PortalTrackResponse(BaseModel):
    recorded: bool
