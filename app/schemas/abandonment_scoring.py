"""Pydantic Schemas -- S-046/HRMS-0446 Candidate Abandonment Prediction."""
from datetime import datetime
from typing import Dict

from pydantic import BaseModel


class AbandonmentScoreResponse(BaseModel):
    candidate_id: str
    abandonment_score: int
    score_components: Dict
    is_flagged: bool
    calculated_at: datetime
