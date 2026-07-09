"""
Pydantic schemas for the Checklist feature.

Covers:
  - Checklist template CRUD
  - Template item CRUD
  - Candidate checklist assignment and progress
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Template Item Schemas
# ---------------------------------------------------------------------------

class ChecklistItemCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    item_type: str = Field(default="todo", pattern="^(todo|queue)$")
    order_index: int = Field(default=0, ge=0)
    due_days_offset: Optional[int] = Field(default=None, ge=0)


class ChecklistItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    item_type: Optional[str] = Field(default=None, pattern="^(todo|queue)$")
    order_index: Optional[int] = Field(default=None, ge=0)
    due_days_offset: Optional[int] = Field(default=None, ge=0)


class ChecklistItemResponse(BaseModel):
    id: int
    template_id: int
    title: str
    description: Optional[str]
    item_type: str
    order_index: int
    due_days_offset: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Template Schemas
# ---------------------------------------------------------------------------

class ChecklistTemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    items: Optional[List[ChecklistItemCreate]] = []


class ChecklistTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None


class ChecklistTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_by_user_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[ChecklistItemResponse] = []

    class Config:
        from_attributes = True


class ChecklistTemplateSummary(BaseModel):
    """Lightweight template response without items — used in list endpoints."""
    id: int
    name: str
    description: Optional[str]
    created_by_user_id: Optional[str]
    created_at: datetime
    item_count: int = 0

    class Config:
        from_attributes = True


class ChecklistTemplateListResponse(BaseModel):
    total: int
    templates: List[ChecklistTemplateSummary]


# ---------------------------------------------------------------------------
# Candidate Checklist Assignment
# ---------------------------------------------------------------------------

class AssignChecklistRequest(BaseModel):
    candidate_id: str
    template_id: int


# ---------------------------------------------------------------------------
# Candidate Checklist Item Response
# ---------------------------------------------------------------------------

class CandidateChecklistItemResponse(BaseModel):
    id: int
    checklist_id: int
    template_item_id: Optional[int]
    title: str
    description: Optional[str]
    item_type: str           # 'todo' | 'queue'
    order_index: int
    status: str              # 'pending' | 'active' | 'submitted' | 'completed'
    due_date: Optional[datetime]
    activated_at: Optional[datetime]
    submitted_at: Optional[datetime]   # set when candidate marks done
    completed_at: Optional[datetime]   # set when HR verifies

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Candidate Checklist Response
# ---------------------------------------------------------------------------

class CandidateChecklistResponse(BaseModel):
    id: int
    candidate_id: str
    template_id: Optional[int]
    template_name: Optional[str]
    assigned_by_user_id: Optional[str]
    assigned_at: datetime
    status: str              # 'active' | 'completed'
    completed_at: Optional[datetime]
    items: List[CandidateChecklistItemResponse] = []

    # Computed summary fields
    total_items: int = 0
    completed_items: int = 0
    submitted_items: int = 0   # candidate submitted, awaiting HR verification
    todo_items: int = 0
    queue_items: int = 0
    active_queue_item: Optional[CandidateChecklistItemResponse] = None

    class Config:
        from_attributes = True


class CandidateChecklistListResponse(BaseModel):
    candidate_id: str
    total_checklists: int
    checklists: List[CandidateChecklistResponse]


# ---------------------------------------------------------------------------
# Item Completion Responses
# ---------------------------------------------------------------------------

class CompleteItemResponse(BaseModel):
    status: str
    message: str
    completed_item: CandidateChecklistItemResponse
    next_active_item: Optional[CandidateChecklistItemResponse] = None
    checklist_completed: bool = False


# ---------------------------------------------------------------------------
# Generic Response
# ---------------------------------------------------------------------------

class ChecklistActionResponse(BaseModel):
    status: str
    message: str
