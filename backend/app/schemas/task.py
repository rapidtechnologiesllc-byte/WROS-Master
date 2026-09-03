from app.core.logging import logger
"""Pydantic schemas -- S-434 Task Dashboard."""
from datetime import datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "MEDIUM"
    department_id: Optional[int] = None
    due_date: Optional[datetime] = None
    is_external: bool = False
    visibility_scope: str = "ASSIGNEE_MANAGER_DEPARTMENT"
    task_type: str = "GENERAL"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    parent_task_id: Optional[int] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: str
    priority_challenged: bool
    priority_challenge_note: Optional[str]
    status: str
    department_id: Optional[int]
    assigned_to_user_id: Optional[str]
    created_by_user_id: Optional[str]
    parent_task_id: Optional[int]
    due_date: Optional[datetime]
    is_external: bool
    visibility_scope: str
    is_escalated: bool
    escalated_at: Optional[datetime]
    task_type: str
    category: Optional[str]
    subcategory: Optional[str]
    completed_at: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReassignmentApproveRequest(BaseModel):
    final_to_user_id: str


class MarkUnavailableRequest(BaseModel):
    user_id: str
