"""Pydantic schemas -- Help Desk/IT-HR Ticketing."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TicketCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    impact: str
    urgency: str
    category: str
    subcategory: Optional[str] = None
    is_external: bool = False


class TicketCategoryResponse(BaseModel):
    category: str
    subcategory: Optional[str]
    department_id: int

    class Config:
        from_attributes = True


class TicketCategoryRouteCreateRequest(BaseModel):
    category: str
    subcategory: Optional[str] = None
    department_id: int


class TicketSLAPolicyUpdateRequest(BaseModel):
    response_minutes: int
    resolution_minutes: int


class TicketSLAPolicyResponse(BaseModel):
    priority: str
    response_minutes: int
    resolution_minutes: int

    class Config:
        from_attributes = True


class TicketDetailResponse(BaseModel):
    task_id: int
    impact: str
    urgency: str
    response_due_at: datetime
    resolution_due_at: datetime
    first_response_at: Optional[datetime]
    response_breached: bool
    resolution_breached: bool

    class Config:
        from_attributes = True
