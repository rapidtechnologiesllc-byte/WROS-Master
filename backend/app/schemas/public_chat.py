"""
Pydantic Schemas — public (unauthenticated) Thunder chat widget.
import logging
"""

import logging
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

class PublicChatStartRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=300)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    job_id: Optional[str] = Field(None, description="If the visitor arrived from a specific job listing")
    consent: bool = Field(..., description="Must be true -- visitor agreed to be contacted about job opportunities")


class PublicChatStartResponse(BaseModel):
    candidate_id: str
    status: str  # 'started' | 'resumed'
    message: str
    created_at: Optional[datetime]


class PublicChatMessageRequest(BaseModel):
    candidate_id: str
    message: str = Field(..., min_length=1, max_length=4000)


class PublicChatMessageResponse(BaseModel):
    reply: str
    created_at: Optional[datetime]


class PublicChatHistoryItem(BaseModel):
    sender: str  # 'candidate' | 'thunder'
    body: str
    created_at: Optional[datetime]


class PublicChatHistoryResponse(BaseModel):
    candidate_id: str
    messages: List[PublicChatHistoryItem]
