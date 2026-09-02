"""
S-356/HRMS-0517 -- Employee Milestone Tracker: Personal, Project & Org
-- API Endpoints
=========================================================================
Prefix: /employee-milestones
import logging
Tag:    employee-milestones

Wires app.services.employee_milestone_service (new this round) to real
HTTP routes. Deliberately a separate prefix/table from the already-
shipped /projects/{id}/milestones (HRMS-0801/0804) -- see app.models.
employee_milestone's module docstring for the real table-name collision
this story's own doc has with that one.

Auth: get_current_internal_user. The doc's own "Not In Scope" note (set
by RM/BU Head/PM only, no employee self-service creation) is naturally
satisfied since this codebase has no employee self-service login role
at all yet -- flagged, not a new gate invented for this story.

Routes:
  POST   /employee-milestones                        Create a milestone.
  GET    /employee-milestones/employee/{employee_id}  List one employee's milestones.
  POST   /employee-milestones/{id}/complete           Complete (completed_date always system-set).
  POST   /employee-milestones/scan-overdue            Idempotent overdue scan + performance-event write.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.employee_milestone import EmployeeMilestone
from app.models.user import Users
from app.schemas.employee_milestone import (
    CompleteEmployeeMilestoneRequest,
    CreateEmployeeMilestoneRequest,
    EmployeeMilestoneItem,
    EmployeeMilestoneListResponse,
    ScanOverdueMilestonesResponse,
)
from app.services.employee_milestone_service import (
    InvalidMilestoneTransition,
    MilestoneValidationError,
    complete_milestone,
    create_milestone,
    get_employee_milestones,
    scan_overdue_milestones,
)

router = APIRouter(prefix="/employee-milestones", tags=["employee-milestones"])


def _to_item(m: EmployeeMilestone) -> EmployeeMilestoneItem:
    return EmployeeMilestoneItem(
        id=m.id, project_id=m.project_id, employee_id=m.employee_id,
        milestone_type=m.milestone_type, title=m.title, description=m.description,
        target_date=m.target_date, completed_date=m.completed_date, status=m.status,
        completion_notes=m.completion_notes, set_by=m.set_by,
    )


@router.post("", response_model=EmployeeMilestoneItem, summary="Create a milestone (PERSONAL/PROJECT/ORG)")
    dependencies=[Depends(require_resource_permission(", response_model=EmployeeMilestoneItem, summary=", "create"))]
def create_milestone_endpoint(
    body: CreateEmployeeMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    try:
        milestone = create_milestone(
            db, milestone_type=body.milestone_type, title=body.title, target_date=body.target_date,
            tenant_id=current_user.tenant_id, project_id=body.project_id, employee_id=body.employee_id,
            description=body.description, set_by=current_user.UserID,
        )
    except MilestoneValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(milestone)
    return _to_item(milestone)


@router.get(
    "/employee/{employee_id}", response_model=EmployeeMilestoneListResponse,
    summary="List one employee's PERSONAL/ORG milestones (and PROJECT ones assigned to them)",
)
def list_employee_milestones(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    milestones = get_employee_milestones(db, employee_id)
    return EmployeeMilestoneListResponse(milestones=[_to_item(m) for m in milestones])


@router.post(
    "/{milestone_id}/complete", response_model=EmployeeMilestoneItem,
    summary="Complete a milestone -- completed_date is always today, never caller-supplied",
)
def complete_milestone_endpoint(
    milestone_id: str,
    body: CompleteEmployeeMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    milestone = db.query(EmployeeMilestone).filter(EmployeeMilestone.id == milestone_id).first()
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    try:
        milestone = complete_milestone(db, milestone, completion_notes=body.completion_notes)
    except InvalidMilestoneTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(milestone)
    return _to_item(milestone)


@router.post(
    "/scan-overdue", response_model=ScanOverdueMilestonesResponse,
    summary="Idempotent scan: flip past-due open milestones to OVERDUE + write a negative performance event",
)
def scan_overdue_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    overdue = scan_overdue_milestones(db, tenant_id=current_user.tenant_id)
    db.commit()
    for m in overdue:
        db.refresh(m)
    return ScanOverdueMilestonesResponse(overdue=[_to_item(m) for m in overdue])
