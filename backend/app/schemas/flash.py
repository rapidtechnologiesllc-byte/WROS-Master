"""
Pydantic Schemas — Flash (internal query agent) surface.

Renamed 2026-08-06 from "Ask Thunder" -- see app.api.v1.endpoints.flash
module docstring for the Thunder-vs-Flash product split rationale.
Since 2026-10-15 the conversation is kept server-side (one per user), so a
request carries only the new message.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FlashRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class FlashMessageOut(BaseModel):
    id: int
    role: str  # user / flash / event
    body: str
    payload: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class FlashDecisionOut(BaseModel):
    kind: str
    ref: str
    text: str
    link: Optional[str] = None
    workflow: bool = Field(description="True: the chip opens a Flash discussion; false: it opens `link`")


class FlashResponse(BaseModel):
    reply: str
    messages: List[FlashMessageOut]
    active_workflow: Optional[str] = None
    brain_status: Optional[str] = None
    intent: Optional[str] = None
    job_id: Optional[str] = Field(default=None, description="Job ID if a job was created")
    mission_id: Optional[str] = None


class FlashConversationResponse(BaseModel):
    conversation_id: Optional[str] = None
    messages: List[FlashMessageOut]
    active_workflow: Optional[str] = None
    brain_status: str
    pending_decisions: List[FlashDecisionOut]
    unread: int
    poll_seconds: int = Field(description="How often the closed bubble checks for new messages")


class FlashWorkflowOpenRequest(BaseModel):
    kind: str = Field(..., min_length=1, max_length=40)
    ref: str = Field(..., min_length=1, max_length=512)


class FlashReadRequest(BaseModel):
    up_to_id: int = Field(..., ge=0)


class FlashResetResponse(BaseModel):
    archived_conversation_id: Optional[str] = None


class FlashReadResponse(BaseModel):
    last_read_message_id: Optional[int] = None
