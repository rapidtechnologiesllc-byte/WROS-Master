"""Pydantic Schemas -- S-037/HRMS-0437 Technical Qualification Score."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class TechnicalScoreResponse(BaseModel):
    candidate_id: str
    job_id: str
    technical_score: Optional[int]
    compensation_score: Optional[int]
    availability_score: Optional[int]
    overall_score: Optional[int]
    score_breakdown: Optional[Dict]
    calculated_at: Optional[datetime]
