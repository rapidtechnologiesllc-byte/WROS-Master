"""
Pydantic Schemas — S-011/HRMS-0411 AI Recruiter Assignment Engine.
"""
from datetime import datetime
import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AIAssignmentResponse(BaseModel):
    ai_agent_name: str
    ai_agent_persona: Optional[str]
    assigned_at: Optional[datetime]
    is_active: bool


class TenantAIConfigResponse(BaseModel):
    ai_agent_name: str
    ai_agent_persona: str


class TenantAIConfigUpdateRequest(BaseModel):
    ai_agent_name: str = Field(..., min_length=1, max_length=100)
    ai_agent_persona: str = Field(..., min_length=1, max_length=2000)


# S-075/HRMS-0475 Step 2/6A -- global tenant Thunder kill switch.
class TenantThunderEnabledResponse(BaseModel):
    thunder_enabled: bool


class TenantThunderEnabledUpdateRequest(BaseModel):
    enabled: bool
