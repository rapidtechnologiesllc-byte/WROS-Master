"""
Pydantic Schemas — S-014/HRMS-0414 Message Template Engine.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateTemplateRequest(BaseModel):
    template_key: str
    template_name: str = Field(..., min_length=1, max_length=200)
    channel: str
    body: str = Field(..., min_length=1, max_length=50000)
    subject: Optional[str] = Field(None, max_length=500)
    language: str = "en"


class TemplateResponse(BaseModel):
    id: int
    template_key: str
    template_name: str
    channel: str
    language: str
    subject: Optional[str]
    body: str
    version: int
    is_active: bool
    created_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: Optional[datetime]


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]


class TemplatePreviewResponse(BaseModel):
    rendered_body: str
    rendered_subject: Optional[str]
    channel: str
    candidate_name_used: str
