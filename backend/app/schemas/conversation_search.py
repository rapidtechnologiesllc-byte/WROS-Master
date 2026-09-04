"""
Pydantic Schemas — S-015/HRMS-0415 Conversation Search.
"""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class SearchResultItem(BaseModel):
    candidate_id: Optional[str]
    candidate_name: str
    conversation_id: int
    message_snippet: str
    channel: str
    sent_at: Optional[datetime]
    direction: str

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total_count: int
    page: int
    per_page: int
    has_more: bool
