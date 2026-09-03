from app.core.logging import logger
"""Pydantic schemas -- Executive Signal & Culture Agent."""
from datetime import datetime
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class FeedbackCycleCreateRequest(BaseModel):
    quarter_label: str


class FeedbackCycleResponse(BaseModel):
    id: str
    quarter_label: str
    status: str
    started_at: Optional[datetime]
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class FeedbackSubmitRequest(BaseModel):
    response_text: str


class RecognitionDraftResponse(BaseModel):
    id: str
    employee_id: str
    occasion: str
    draft_text: str
    status: str
    approved_by: Optional[str]
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConcernSubmitRequest(BaseModel):
    message_text: str


class ConcernResponse(BaseModel):
    id: str
    employee_id: str
    message_text: str
    category: Optional[str]
    resolution_text: Optional[str]
    created_task_id: Optional[int]

    class Config:
        from_attributes = True
