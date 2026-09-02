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


class CandidateMemoryResponse(BaseModel):
    candidate_id: str
    summary: Optional[str]
    last_updated: Optional[datetime]
    facts: List[MemoryFactItem]


class MemoryFactCorrectionRequest(BaseModel):
    fact_value: str
