from app.core.logging import logger
"""Pydantic Schemas -- S-020/HRMS-0420 Engagement SLA Monitoring."""
from datetime import datetime
import logging
from typing import List

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SLABreachItem(BaseModel):
    candidate_id: str
    candidate_name: str
    conversation_id: int
    sla_type: str
    breached_at: datetime
    hours_since_breach: float


class SLABreachListResponse(BaseModel):
    total_count: int
    breaches: List[SLABreachItem]
