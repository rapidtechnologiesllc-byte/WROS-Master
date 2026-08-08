"""Pydantic Schemas -- S-077/HRMS-0477 Tenant AI Configuration."""
from typing import List, Optional

from pydantic import BaseModel, Field


class TenantAIConfigResponse(BaseModel):
    tenant_id: str
    ai_agent_name: Optional[str] = "Thunder"
    ai_agent_persona: Optional[str]
    digest_enabled: bool
    thunder_enabled: bool
    greeting_channel: str
    whatsapp_followup_hours: int
    email_followup_hours: int
    max_followup_count: int
    ghosting_reactivation_days: int
    digest_send_time: str
    sla_first_contact_seconds: int
    sla_no_contact_hours: int
    qualification_field_order: Optional[list] = None
    escalation_keywords: Optional[list] = None
    updated_at: Optional[str]
    updated_by: Optional[str]


class UpdateTenantAIConfigRequest(BaseModel):
    ai_agent_name: Optional[str] = Field(None, min_length=1, max_length=100)
    ai_agent_persona: Optional[str] = Field(None, min_length=1, max_length=2000)
    digest_enabled: Optional[bool] = None
    thunder_enabled: Optional[bool] = None
    greeting_channel: Optional[str] = None
    whatsapp_followup_hours: Optional[int] = Field(None, ge=1, le=168)
    email_followup_hours: Optional[int] = Field(None, ge=1, le=168)
    max_followup_count: Optional[int] = Field(None, ge=1, le=10)
    ghosting_reactivation_days: Optional[int] = Field(None, ge=1)
    digest_send_time: Optional[str] = None
    sla_first_contact_seconds: Optional[int] = Field(None, ge=1)
    sla_no_contact_hours: Optional[int] = Field(None, ge=1)
    qualification_field_order: Optional[List[str]] = None
    escalation_keywords: Optional[List[str]] = None
    # BR-01: required True whenever ai_agent_persona is part of the update.
    ba_approved: bool = False
