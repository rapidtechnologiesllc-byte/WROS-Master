"""
Pydantic Schemas — "Test Thunder" chat mode.
import logging
"""

import logging
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.core.logging import logger

logger = logging.getLogger(__name__)

class TestChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Message to send as if you were the candidate")


class TestChatMessageResponse(BaseModel):
    conversation_id: int
    candidate_message: str
    thunder_reply: str
    mock_send: bool
    delivered: bool
    event_id: int
    created_at: Optional[datetime]


class TestChatHistoryItem(BaseModel):
    sender: str  # 'candidate' | 'thunder' | 'hr'
    body: str
    created_at: Optional[datetime]


class TestChatHistoryResponse(BaseModel):
    conversation_candidate_id: str
    messages: List[TestChatHistoryItem]
