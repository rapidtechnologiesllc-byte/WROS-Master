"""
Pydantic Schemas — S-004/HRMS-0404 Web Portal Chat Messages.
"""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class PortalMessageRequest(BaseModel):
    # Real min/max-length business errors (empty / >4000 chars) are
    # raised by the service layer with the spec's exact wording -- this
    # schema only guards against a wildly oversized payload.
    message_body: str = Field(..., max_length=20000)


class PortalMessageResponse(BaseModel):
    message_id: int
    sent_at: Optional[datetime]
    # S-346 -- Thunder's synchronous reply to this message, when one was
    # generated. None when a human owns the conversation, Thunder is
    # paused, the message was escalated, or reply generation failed
    # (the candidate's own message is still safely stored either way).
    reply: Optional[str] = None
    reply_sent_at: Optional[datetime] = None
    escalated: bool = False
    suppressed: bool = False


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
