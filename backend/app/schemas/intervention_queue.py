from app.core.logging import logger
"""Pydantic Schemas -- S-062/HRMS-0462 Recruiter Intervention Queue."""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class QueueItem(BaseModel):
    id: int
    candidate_id: str
    candidate_name: str
    queue_reason: str
    reason_detail: Optional[str] = None
    priority: int
    status: str
    assigned_to_user_id: Optional[str] = None
    added_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


class QueueResponse(BaseModel):
    items: List[QueueItem]


class QueueSummaryResponse(BaseModel):
    critical: int
    high: int
    medium: int
    total: int


class TakeOverResponse(BaseModel):
    id: int
    status: str
    assigned_to_user_id: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution_note: Optional[str] = None


class ResolveResponse(BaseModel):
    id: int
    status: str
    resolved_at: datetime
