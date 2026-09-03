from app.core.logging import logger
"""Pydantic Schemas -- S-059/HRMS-0459 Candidate Journey Dashboard."""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class JourneyStage(BaseModel):
    stage_name: str
    stage_label: str
    status: str  # 'completed' | 'active' | 'pending'
    entered_at: Optional[datetime] = None
    exited_at: Optional[datetime] = None
    metrics: Dict[str, Any] = {}


class CandidateJourneyResponse(BaseModel):
    candidate_id: str
    current_stage: str
    stages: List[JourneyStage]
