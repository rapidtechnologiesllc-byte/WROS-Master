"""
S-434 -- Org-wide Task Dashboard.
==================================================================
Prefix: /tasks
Tag:    tasks

Internal-employees-only surface (any authenticated Users row, not
candidate-restricted, not HR-restricted -- Task serves every
department/function, confirmed 2026-08-04).

GET  /tasks/my-day            -- today's must-do list (Layer 1+2 ranking)
GET  /tasks/my-day/upcoming    -- not-due-today Urgent tasks, heads-up only
POST /tasks                    -- create (Thunder challenges Urgent claims)
POST /tasks/{id}/confirm-urgent
POST /tasks/{id}/complete      -- a repeating task opens its next occurrence
POST /tasks/{id}/stop-repeating
GET  /tasks/options            -- priorities and repeat choices for the New task form
GET  /tasks/candidate/{id}     -- every task about a candidate (Tasks tab on the candidate)
GET  /tasks/my-day/scheduled  -- open follow-ups due in the next 30 days
GET  /tasks/update-options     -- choices for the Log update form
GET  /tasks/{id}/updates       -- updates on this task (and the tasks it follows up)
POST /tasks/{id}/updates       -- log what was done + next action (creates the follow-up task)
GET  /tasks/{id}/comments      -- the task's comment thread (approval notes land here too)
POST /tasks/{id}/comments      -- add a comment (assignee, creator, or anyone who may see the task)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.visibility import is_org_level_user
from app.models.task import TASK_PRIORITIES, TASK_RECURRENCES, Task
from app.models.user import Users
from app.schemas.task import CandidateTaskResponse, TaskCreateRequest, TaskResponse, TaskUpdateRequest
from app.services.task_activity_service import activity_to_dict, list_task_updates, log_task_update, update_options
from app.services.task_service import (
    complete_task, confirm_urgent_task, create_task, get_daily_task_list, get_scheduled_tasks, get_upcoming_urgent_tasks,
    list_candidate_tasks, stop_repeating,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

def _get_task_or_404(db: Session, task_id: int, user: Users) -> Task:
    """A task the caller may act on: one assigned to or created by them; an org-level role
    template (RoleTemplate.org_level_access) may act on any task of the tenant. Anyone else's
    task is 404, the same answer as a task that does not exist."""
    query = db.query(Task).filter(Task.id == task_id, or_(Task.tenant_id.is_(None), Task.tenant_id == user.tenant_id))
    if not is_org_level_user(user):
        query = query.filter(or_(Task.assigned_to_user_id == user.UserID, Task.created_by_user_id == user.UserID))
    task = query.first()
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
    task = _get_task_or_404(db, task_id, current_user)
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
    task = _get_task_or_404(db, task_id, current_user)
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

def _visible_candidate_or_404(db: Session, user: Users, candidate_id: str) -> None:
    """A candidate's tasks are as visible as the candidate (business-unit scope)."""
    from app.core.bu_scope import get_candidate_by_id_with_bu_scope

    if get_candidate_by_id_with_bu_scope(db, candidate_id, user) is None:
        raise HTTPException(status_code=404, detail="Candidate not found")


def _assignee_or_422(db: Session, user: Users, assigned_to_user_id: str) -> str:
    assignee = db.query(Users.UserID).filter(Users.UserID == assigned_to_user_id, Users.tenant_id == user.tenant_id,
                                             Users.terminated_at.is_(None)).first()
    if assignee is None:
        raise HTTPException(status_code=422, detail="Assign the task to an active user of your organization")
    return assigned_to_user_id


@router.get(
    "/options",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def task_options():
    """Choices for the New task form (single source: the model)."""
    label = lambda value: value.replace("_", " ").capitalize()  # noqa: E731
    return {"priorities": [{"value": v, "label": label(v)} for v in TASK_PRIORITIES],
            "recurrences": [{"value": v, "label": label(v)} for v in TASK_RECURRENCES]}


@router.get(
    "/candidate/{candidate_id}",
    response_model=list[CandidateTaskResponse],
    dependencies=[Depends(require_resource_permission("candidates", "view"))]
)
def candidate_tasks(candidate_id: str, current_user: Users = Depends(get_current_internal_user),
                    db: Session = Depends(get_db)):
    _visible_candidate_or_404(db, current_user, candidate_id)
    tasks = list_candidate_tasks(db, candidate_id, current_user.tenant_id)
    people = {u.UserID: u.UserName or u.UserEmail for u in db.query(Users).filter(
        Users.UserID.in_({t.assigned_to_user_id for t in tasks if t.assigned_to_user_id})).all()}
    return [CandidateTaskResponse.model_validate(t).model_copy(
        update={"assigned_to_name": people.get(t.assigned_to_user_id)}) for t in tasks]


@router.post(
    "",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def create_task_endpoint(
    body: TaskCreateRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    if body.candidate_id:
        _visible_candidate_or_404(db, current_user, body.candidate_id)
    assignee = _assignee_or_422(db, current_user, body.assigned_to_user_id) if body.assigned_to_user_id else (
        None if body.department_id else current_user.UserID)  # a department routes it; otherwise the creator
    try:
        return create_task(
            db, title=body.title, description=body.description, priority=body.priority,
            created_by_user_id=current_user.UserID, department_id=body.department_id,
            due_date=body.due_date, is_external=body.is_external, visibility_scope=body.visibility_scope,
            task_type=body.task_type, category=body.category, subcategory=body.subcategory,
            parent_task_id=body.parent_task_id, tenant_id=current_user.tenant_id,
            assigned_to_user_id=assignee, candidate_id=body.candidate_id, recurrence=body.recurrence or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{task_id}/stop-repeating",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def stop_repeating_endpoint(task_id: int, current_user: Users = Depends(get_current_internal_user),
                            db: Session = Depends(get_db)):
    return stop_repeating(db, _get_task_or_404(db, task_id, current_user))

@router.post(
    "/{task_id}/confirm-urgent",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def confirm_urgent(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id, current_user)
    return confirm_urgent_task(db, task)

@router.post(
    "/{task_id}/complete",
    response_model=TaskResponse,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def complete(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id, current_user)
    return complete_task(db, task)



class TaskCommentRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


def _comment_dict(db: Session, comment) -> dict:
    author = db.query(Users).filter(Users.UserID == comment.author_user_id).first() if comment.author_user_id else None
    return {"id": comment.id, "task_id": comment.task_id, "body": comment.body,
            "author_user_id": comment.author_user_id,
            "author_name": (author.UserName or author.UserEmail) if author else "System",
            "created_at": comment.created_at.isoformat() if comment.created_at else None}


@router.get(
    "/{task_id}/comments",
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def get_task_comments(task_id: int, current_user: Users = Depends(get_current_internal_user),
                      db: Session = Depends(get_db)):
    from app.models.task_comment import TaskComment

    task = _get_task_or_404(db, task_id, current_user)
    rows = db.query(TaskComment).filter(TaskComment.task_id == task.id).order_by(TaskComment.created_at, TaskComment.id).all()
    return {"task_id": task.id, "comments": [_comment_dict(db, c) for c in rows]}


@router.post(
    "/{task_id}/comments",
    status_code=201,
    dependencies=[Depends(require_resource_permission("my-tasks", "create"))]
)
def add_task_comment(task_id: int, body: TaskCommentRequest, current_user: Users = Depends(get_current_internal_user),
                     db: Session = Depends(get_db)):
    from app.models.task_comment import TaskComment

    task = _get_task_or_404(db, task_id, current_user)
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=422, detail="A comment cannot be empty.")
    comment = TaskComment(tenant_id=current_user.tenant_id, task_id=task.id, author_user_id=current_user.UserID, body=text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_dict(db, comment)
