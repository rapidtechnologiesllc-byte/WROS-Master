"""Pydantic Schemas -- S-021/HRMS-0421 Candidate Memory Store."""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class MemoryFactItem(BaseModel):
    id: int
    category: str
    key: str
    value: str
    confidence: float
    is_low_confidence: bool
    extracted_at: Optional[datetime]

class SignalItem(BaseModel):
    """Desire signal recorded from candidate interactions (emails, messages, etc.)"""
    id: int
    source: str  # EMAIL_MESSAGE, WHATSAPP_MESSAGE, CHAT_MESSAGE, RESPONSE_SPEED
    category: Optional[str]  # desire_category or None if not yet processed
    direction: Optional[str]  # TOWARDS, AWAY_FROM or None
    strength: Optional[float]  # 0.0-1.0 or None
    insight: Optional[str]  # extracted_insight from LLM processing
    created_at: datetime

class CandidateMemoryResponse(BaseModel):
    candidate_id: str
    summary: Optional[str]
    last_updated: Optional[datetime]
    facts: List[MemoryFactItem]
    signals: List[SignalItem] = []  # Intelligence signals from emails/messages

class MemoryFactCorrectionRequest(BaseModel):
    fact_value: str
