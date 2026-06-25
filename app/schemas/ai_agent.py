"""
Pydantic Schemas — AI Conversation Agent
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Assign AI Agent
# ---------------------------------------------------------------------------

class AIAgentAssignRequest(BaseModel):
    candidate_id: str = Field(..., description="The candidate to assign the AI agent to")


class AIAgentAssignResponse(BaseModel):
    assignment_id: int
    conversation_id: int
    candidate_id: str
    missing_fields_count: int
    missing_fields: List[Dict[str, str]]
    email_sent: bool
    conversation_status: str


# ---------------------------------------------------------------------------
# Missing Fields Preview
# ---------------------------------------------------------------------------

class MissingFieldItem(BaseModel):
    field: str
    label: str
    source: str   # 'candidate' | 'info_form'


class MissingFieldsResponse(BaseModel):
    candidate_id: str
    total_missing: int
    missing_fields: List[MissingFieldItem]


# ---------------------------------------------------------------------------
# Webhook / Poll reply
# ---------------------------------------------------------------------------

class EmailReplyWebhookRequest(BaseModel):
    candidate_id: str = Field(..., description="Candidate whose reply was received")
    raw_reply_text: Optional[str] = Field(
        None,
        description=(
            "Plain-text body of the reply. "
            "If omitted, the agent will poll the Graph inbox automatically."
        ),
    )
    message_id: Optional[str] = Field(
        None,
        description="Microsoft Graph message ID (for deduplication).",
    )


class ProcessReplyResponse(BaseModel):
    conversation_id: int
    status: str        # completed | partial | no_reply_found | all_fields_complete
    updated_fields: Optional[List[str]] = None
    skipped_fields: Optional[List[str]] = None
    still_missing: Optional[List[str]] = None
    followup_email_sent: Optional[bool] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversation thread (for UI)
# ---------------------------------------------------------------------------

class ConversationEventOut(BaseModel):
    id: int
    event_type: str
    event_data: Optional[Dict[str, Any]]
    triggered_by: str
    created_at: Optional[str]

    class Config:
        from_attributes = True


class ConversationThreadItem(BaseModel):
    conversation_id: int
    status: str
    ai_agent_name: Optional[str]
    channel_preference: Optional[str]
    summary: Optional[str]
    next_action: Optional[str]
    owner_type: Optional[str]
    escalation_state: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    events: List[ConversationEventOut]


class ConversationThreadResponse(BaseModel):
    candidate_id: str
    total_conversations: int
    conversations: List[ConversationThreadItem]


# ---------------------------------------------------------------------------
# AI Assignment list
# ---------------------------------------------------------------------------

class AIAssignmentOut(BaseModel):
    id: int
    tenant_id: str
    candidate_id: str
    ai_agent_name: str
    ai_agent_persona: Optional[str]
    assigned_at: Optional[datetime]
    assigned_by: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True
