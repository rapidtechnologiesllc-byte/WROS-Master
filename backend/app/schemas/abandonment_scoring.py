"""Pydantic Schemas -- S-046/HRMS-0446 Candidate Abandonment Prediction."""
from datetime import datetime
import logging
from typing import Dict

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class AbandonmentScoreResponse(BaseModel):
    candidate_id: str
    abandonment_score: int
    score_components: Dict
    is_flagged: bool
    calculated_at: datetime
