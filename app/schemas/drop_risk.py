"""Pydantic Schemas -- S-060/HRMS-0460 Drop Risk Prediction."""
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel


class DropRiskResponse(BaseModel):
    candidate_id: str
    drop_risk_score: int
    risk_level: str
    is_flagged: bool
    risk_signals: Dict[str, Any]
    calculated_at: datetime
