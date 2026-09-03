from app.core.logging import logger
"""Pydantic Schemas -- S-070/HRMS-0470 Candidate Engagement Health Metrics."""
from datetime import datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class EngagementMetricsResponse(BaseModel):
    candidate_id: str
    response_rate: float
    avg_response_time_minutes: Optional[int] = None
    total_messages_exchanged: int
    days_to_qualification: Optional[int] = None
    avg_sentiment_score: Optional[float] = None
    last_inbound_at: Optional[datetime] = None
    metrics_calculated_at: datetime
