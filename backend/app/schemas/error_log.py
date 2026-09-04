from app.core.logging import logger
"""Pydantic schemas -- S-215 Error Logging Framework."""
from datetime import datetime
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ErrorLogItem(BaseModel):
    id: str
    error_type: str
    severity: str
    message: str
    stack_trace: Optional[str]
    request_context: Optional[str]
    integration_name: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class ErrorLogListResponse(BaseModel):
    errors: List[ErrorLogItem]
