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
POST /tasks/{id}/reassign-suggest   -- mark self/another user unavailable, suggest today's reassignments
POST /tasks/reassignments/{id}/approve
POST /tasks/reassignments/{id}/reject
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.task import Task, TaskReassignmentRequest
from app.models.user import Users
from app.schemas.task import (
    MarkUnavailableRequest, ReassignmentApproveRequest, TaskCreateRequest, TaskResponse,
)
from app.services.task_assignment_service import (
    approve_reassignment, reject_reassignment, suggest_todays_reassignments,
)
from app.services.task_service import complete_task, confirm_urgent_task, create_task, get_daily_task_list, get_upcoming_urgent_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task #{task_id} not found.")
    return task


@router.get(
    "/my-day",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_resource_permission("my-day", "view"))]
)
def my_day(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return get_daily_task_list(db, assigned_to_user_id=current_user.UserID)


@router.get(
    "/my-day/upcoming",
    response_model=list[TaskResponse],
    dependencies=[Depends(require_resource_permission("my-day", "view"))]
)
def my_day_upcoming(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return get_upcoming_urgent_tasks(db, assigned_to_user_id=current_user.UserID)


@router.post(
    "",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("unknown", "create"))]
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
    dependencies=[Depends(require_resource_permission("{task_id}", "create"))]
)
def confirm_urgent(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    return confirm_urgent_task(db, task)


@router.post(
    "/{task_id}/complete",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("{task_id}", "create"))]
)
def complete(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    return complete_task(db, task)


@router.post(
    "/reassign-suggest",
    dependencies=[Depends(require_resource_permission("reassign-suggest", "create"))]
)
def reassign_suggest(
    body: MarkUnavailableRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    """Raises PENDING TaskReassignmentRequest rows for every task due
    today assigned to body.user_id -- never applies anything itself, a
    manager must approve each one."""
    requests = suggest_todays_reassignments(db, unavailable_user_id=body.user_id)
    return {"requests_created": len(requests), "request_ids": [r.id for r in requests]}


@router.post(
    "/reassignments/{request_id}/approve",
    dependencies=[Depends(require_resource_permission("reassignment", "create"))]
)
def approve(
    request_id: str, body: ReassignmentApproveRequest,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    req = db.query(TaskReassignmentRequest).filter(TaskReassignmentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Reassignment request {request_id!r} not found.")
    return approve_reassignment(db, req, approved_by_user_id=current_user.UserID, final_to_user_id=body.final_to_user_id)


@router.post(
    "/reassignments/{request_id}/reject",
    dependencies=[Depends(require_resource_permission("reassignment", "create"))]
)
def reject(request_id: str, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    req = db.query(TaskReassignmentRequest).filter(TaskReassignmentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Reassignment request {request_id!r} not found.")
    return reject_reassignment(db, req, approved_by_user_id=current_user.UserID)
