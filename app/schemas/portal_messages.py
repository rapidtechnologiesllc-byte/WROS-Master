"""
Pydantic Schemas — S-004/HRMS-0404 Web Portal Chat Messages.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PortalMessageRequest(BaseModel):
    # Real min/max-length business errors (empty / >4000 chars) are
    # raised by the service layer with the spec's exact wording -- this
    # schema only guards against a wildly oversized payload.
    message_body: str = Field(..., max_length=20000)


class PortalMessageResponse(BaseModel):
    message_id: int
    sent_at: Optional[datetime]


class PortalMessageItem(BaseModel):
    id: int
    direction: str
    sender_type: str
    channel: str
    message_body: str
    sent_at: Optional[datetime]
    delivery_status: str


class PortalMessageHistoryResponse(BaseModel):
    messages: List[PortalMessageItem]
    total_count: int
    page: int
    per_page: int
    has_more: bool
