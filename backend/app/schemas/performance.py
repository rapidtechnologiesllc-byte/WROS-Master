import logging
from app.core.logging import logger
"""Pydantic schemas -- HRMS-0515 (Employee Performance Intelligence Store) read API."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PerformanceEventItem(BaseModel):
    id: int
    event_type: str
    event_data: Optional[dict] = None
    occurred_at: Optional[datetime] = None

class PerformanceStoreResponse(BaseModel):
    employee_id: str
    events: List[PerformanceEventItem]
    score_averages_by_event_type: Dict[str, float]
