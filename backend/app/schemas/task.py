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
    department_id: Optional[str] = None
    due_date: Optional[datetime] = None
    is_external: bool = False
    visibility_scope: str = "ASSIGNEE_MANAGER_DEPARTMENT"
    task_type: str = "GENERAL"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    parent_task_id: Optional[int] = None
    # Who does it (default: the creator, so a task never belongs to nobody) and the candidate it is
    # about (Tasks tab on the candidate); repeat is one of TASK_RECURRENCES
    assigned_to_user_id: Optional[str] = None
    candidate_id: Optional[str] = None
    recurrence: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: str
    priority_challenged: bool
    priority_challenge_note: Optional[str]
    status: str
    department_id: Optional[str]
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
    # Lets My Tasks open the record a task is about (candidate profile, its interview tab)
    candidate_id: Optional[str] = None
    interview_id: Optional[int] = None
    # Doing this is what closes the task (My Tasks shows it instead of Log update and Mark complete)
    system_action: Optional[str] = None
    expense_id: Optional[str] = None  # the expense a review task opens
    recurrence: Optional[str] = None
    # In-app path the task opens; My Tasks follows it first
    link: Optional[str] = None
    # What the task is about (My Tasks "Related to"): Candidate / Interview / Expense / Invoice
    related_kind: Optional[str] = None
    related_name: Optional[str] = None
    related_link: Optional[str] = None

    class Config:
        from_attributes = True

class CandidateTaskResponse(TaskResponse):
    assigned_to_name: Optional[str] = None

class ReassignmentApproveRequest(BaseModel):
    final_to_user_id: str

class MarkUnavailableRequest(BaseModel):
    user_id: str


class TaskUpdateRequest(BaseModel):
    """Log what was done on a task and, optionally, the next action."""
    activity_type: str
    notes: str
    outcome: Optional[str] = None
    next_action_type: Optional[str] = None
    next_action_due: Optional[datetime] = None
    next_action_note: Optional[str] = None
    complete_task: bool = False


class TaskReplyDraftResponse(BaseModel):
    """The reply the system drafted for this task's candidate email, for a person to approve."""
    id: int
    status: str
    subject: str
    text: str              # the editable paragraphs (greeting, sign-off and footer are added on send)
    composed_by: str       # "claude" / "rules"
    intent: Optional[str] = None
    their_email: Optional[str] = None  # the candidate's email it answers
    candidate_id: str


class TaskReplyApproveRequest(BaseModel):
    text: Optional[str] = None  # edited text; omitted = send the draft as written
