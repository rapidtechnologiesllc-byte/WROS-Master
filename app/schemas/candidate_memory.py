"""Pydantic Schemas -- S-021/HRMS-0421 Candidate Memory Store."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MemoryFactItem(BaseModel):
    category: str
    key: str
    value: str
    confidence: float
    is_low_confidence: bool


class CandidateMemoryResponse(BaseModel):
    candidate_id: str
    summary: Optional[str]
    last_updated: Optional[datetime]
    facts: List[MemoryFactItem]
