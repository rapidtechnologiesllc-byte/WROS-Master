from app.core.logging import logger
"""Pydantic Schemas -- S-078/HRMS-0478 Event Emission Layer."""
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class EventLogEntry(BaseModel):
    id: int
    tenant_id: str
    candidate_id: Optional[str]
    event_type: str
    event_version: str
    payload: Optional[Dict[str, Any]]
    emitted_at: Optional[str]

class EventLogResponse(BaseModel):
    total: int
    events: List[EventLogEntry]
