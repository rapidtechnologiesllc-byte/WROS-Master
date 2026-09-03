"""
Pydantic Schemas — AI Conversation Agent
import logging
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Assign AI Agent
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

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
    summary_generated_at: Optional[str]
    no_contact_breach_hours: Optional[float]
    next_action: Optional[str]
    owner_type: Optional[str]
    escalation_state: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    is_thunder_paused: bool = False
    thunder_resume_at: Optional[str] = None
    events: List[ConversationEventOut]


class ConversationThreadResponse(BaseModel):
    candidate_id: str
    total_conversations: int
    conversations: List[ConversationThreadItem]


# ---------------------------------------------------------------------------
# Manual send / ownership (S-009 / S-010)
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message body to send to the candidate")


class SendMessageResponse(BaseModel):
    conversation_id: int
    event_id: int
    delivered: bool
    owner_type: Optional[str]
    owner_id: Optional[str]


class ConversationOwnershipResponse(BaseModel):
    conversation_id: int
    owner_type: Optional[str]
    owner_id: Optional[str]


# ---------------------------------------------------------------------------
# Pause / resume (S-075/HRMS-0475)
# ---------------------------------------------------------------------------

class PauseThunderRequest(BaseModel):
    resume_at: Optional[str] = Field(
        None, description="ISO datetime to auto-resume at. Omit for 'until manually resumed'.",
    )


class ThunderPauseResponse(BaseModel):
    conversation_id: int
    is_thunder_paused: bool
    thunder_resume_at: Optional[str]
    thunder_paused_by: Optional[str]


# ---------------------------------------------------------------------------
# Audit log (S-076)
# ---------------------------------------------------------------------------

class AuditLogEntryOut(BaseModel):
    id: int
    audit_event_type: str
    audit_event_description: str
    actor_type: str
    actor_id: str
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    created_at: Optional[str]

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    candidate_id: str
    total_count: int
    audit_entries: List[AuditLogEntryOut]


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


# ---------------------------------------------------------------------------
# Inbox message schemas
# ---------------------------------------------------------------------------

class InboxMessageItem(BaseModel):
    id: str
    subject: Optional[str]
    from_email: Optional[str]
    from_name: Optional[str]
    body_preview: Optional[str]
    body_text: Optional[str]
    received_at: Optional[str]
    is_read: bool = False


class InboxResponse(BaseModel):
    mailbox: str
    total_returned: int
    messages: List[InboxMessageItem]
