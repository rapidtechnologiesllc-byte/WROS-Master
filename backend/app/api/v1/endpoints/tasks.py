"""
S-434 -- Org-wide Task Dashboard.
==================================================================
Prefix: /tasks
import logging
Tag:    tasks

Internal-employees-only surface (any authenticated Users row, not
candidate-restricted, not HR-restricted -- Task serves every
department/function, confirmed 2026-08-04).

GET  /tasks/my-day            -- today's must-do list (Layer 1+2 ranking)
GET  /tasks/my-day/upcoming    -- not-due-today Urgent tasks, heads-up only
POST /tasks                    -- create (Thunder challenges Urgent claims)
POST /tasks/{id}/confirm-urgent
POST /tasks/{id}/complete
GET  /tasks/my-day/scheduled  -- open follow-ups due in the next 30 days
GET  /tasks/update-options     -- choices for the Log update form
GET  /tasks/{id}/updates       -- updates on this task (and the tasks it follows up)
POST /tasks/{id}/updates       -- log what was done + next action (creates the follow-up task)
POST /tasks/{id}/reassign-suggest   -- mark self/another user unavailable, suggest today's reassignments
POST /tasks/reassignments/{id}/approve
POST /tasks/reassignments/{id}/reject
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.task import Task, TaskReassignmentRequest
from app.models.user import Users
from app.schemas.task import (
    MarkUnavailableRequest, ReassignmentApproveRequest, TaskCreateRequest, TaskResponse, TaskUpdateRequest,
)
from app.services.task_activity_service import activity_to_dict, list_task_updates, log_task_update, update_options
from app.services.task_assignment_service import (
    approve_reassignment, reject_reassignment, suggest_todays_reassignments,
)
from app.services.task_service import (
    complete_task, confirm_urgent_task, create_task, get_daily_task_list, get_scheduled_tasks, get_upcoming_urgent_tasks,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task #{task_id} not found.")
    return task

@router.get(
    "/my-day",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def my_day(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return get_daily_task_list(db, assigned_to_user_id=current_user.UserID)

@router.get(
    "/my-day/upcoming",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def my_day_upcoming(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return get_upcoming_urgent_tasks(db, assigned_to_user_id=current_user.UserID)

@router.get(
    "/my-day/scheduled",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def my_day_scheduled(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return get_scheduled_tasks(db, assigned_to_user_id=current_user.UserID)

@router.get(
    "/update-options",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def task_update_options():
    return update_options()

@router.get(
    "/{task_id}/updates",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def get_task_updates(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    return {"task_id": task.id, "updates": [activity_to_dict(a) for a in list_task_updates(db, task)]}

@router.post(
    "/{task_id}/updates",
    status_code=201,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def post_task_update(
    task_id: int, body: TaskUpdateRequest,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    task = _get_task_or_404(db, task_id)
    try:
        activity = log_task_update(
            db, task, current_user,
            activity_type=body.activity_type, notes=body.notes, outcome=body.outcome,
            next_action_type=body.next_action_type, next_action_due=body.next_action_due,
            next_action_note=body.next_action_note, complete_task=body.complete_task,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return activity_to_dict(activity)

@router.post(
    "",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def create_task_endpoint(
    body: TaskCreateRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    try:
        return create_task(
            db, title=body.title, description=body.description, priority=body.priority,
            created_by_user_id=current_user.UserID, department_id=body.department_id,
            due_date=body.due_date, is_external=body.is_external, visibility_scope=body.visibility_scope,
            task_type=body.task_type, category=body.category, subcategory=body.subcategory,
            parent_task_id=body.parent_task_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.post(
    "/{task_id}/confirm-urgent",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def confirm_urgent(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    return confirm_urgent_task(db, task)

@router.post(
    "/{task_id}/complete",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def complete(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    return complete_task(db, task)

