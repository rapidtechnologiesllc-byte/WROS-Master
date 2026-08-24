"""Pydantic schemas -- S-215 Error Logging Framework."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


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
