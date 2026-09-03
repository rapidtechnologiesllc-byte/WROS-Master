from app.core.logging import logger
"""Pydantic Schemas -- S-061/HRMS-0461 AI Activity Feed."""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ActivityItem(BaseModel):
    id: int
    candidate_id: Optional[str] = None
    candidate_name: str
    activity_type: str
    activity_summary: str
    severity: str
    is_read: bool
    created_at: datetime

class ActivityFeedResponse(BaseModel):
    activities: List[ActivityItem]
    total_count: int
    unread_count: int
    has_more: bool

class MarkAllReadResponse(BaseModel):
    marked_count: int
