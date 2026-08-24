"""Pydantic Schemas -- S-064/HRMS-0464 AI Explainability Panel."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MessageExplanationResponse(BaseModel):
    explanation_text: str
    prompt_type: str
    prompt_type_label: str
    context_snapshot: Dict[str, Any]
    generated_at: Optional[str] = None
    model_used: str


class ExplanationLogEntry(BaseModel):
    message_id: int
    explanation_text: str
    prompt_type: str
    context_snapshot: Dict[str, Any]
    generated_at: Optional[str] = None
    created_at: datetime


class ExplanationLogResponse(BaseModel):
    entries: List[ExplanationLogEntry]
