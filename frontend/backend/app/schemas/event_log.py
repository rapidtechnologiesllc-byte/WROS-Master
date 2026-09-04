"""Pydantic Schemas -- S-078/HRMS-0478 Event Emission Layer."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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
