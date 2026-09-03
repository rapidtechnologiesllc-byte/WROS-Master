"""
Employee self-service timesheet.
==================================================================
Prefix: /my
import logging
Tag:    my-timesheet

Real gap closed 2026-08-04: the existing timesheet engine (see
app.services.employee_self_service module docstring) was entirely
HR-operated. Every endpoint here resolves the CALLER's own Employee
record and only ever touches their own allocations/timesheets --
never a client-supplied employee_id, unlike the existing HR-facing
/allocations and /timesheets endpoints.

GET  /my/allocations                          -- my active project allocations
GET  /my/timesheet/current?allocation_id=      -- this week's draft (created if missing)
PUT  /my/timesheet/{id}/entries                -- log my own hours
POST /my/timesheet/{id}/submit                 -- submit my own timesheet
GET  /my/timesheet/history
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.schemas.allocation import AllocationItem, AllocationListResponse
from app.schemas.timesheet import TimesheetItem, TimesheetListResponse, UpsertEntriesRequest
from app.services.employee_self_service import (
    NoLinkedEmployeeRecord, NotYourAllocation, NotYourTimesheet, get_my_active_allocations,
    get_my_timesheet_history, get_or_start_my_current_week_timesheet, resolve_current_employee,
    submit_my_entries, submit_my_timesheet,
)

router = APIRouter(prefix="/my", tags=["my-timesheet"])


def _current_employee_or_404(db: Session, current_user: Users):
    try:
        return resolve_current_employee(db, current_user)
    except NoLinkedEmployeeRecord as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/allocations",
    response_model=AllocationListResponse,
    dependencies=[Depends(require_resource_permission("allocation", "view"))]
)
def my_allocations(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    from app.api.v1.endpoints.allocations import _to_item as allocation_to_item

    employee = _current_employee_or_404(db, current_user)
    allocations = get_my_active_allocations(db, employee)
    return AllocationListResponse(allocations=[allocation_to_item(db, a) for a in allocations])


@router.get(
    "/timesheet/current",
    response_model=TimesheetItem,
    dependencies=[Depends(require_resource_permission("timesheet", "view"))]
)
def my_current_timesheet(
    allocation_id: str, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    from app.api.v1.endpoints.timesheets import _to_item as timesheet_to_item

    employee = _current_employee_or_404(db, current_user)
    try:
        timesheet = get_or_start_my_current_week_timesheet(db, employee, allocation_id)
    except NotYourAllocation as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return timesheet_to_item(db, timesheet)


@router.put(
    "/timesheet/{timesheet_id}/entries",
    response_model=TimesheetItem,
    dependencies=[Depends(require_resource_permission("timesheet", "update"))]
)
def log_my_hours(
    timesheet_id: str, body: UpsertEntriesRequest,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    from app.api.v1.endpoints.timesheets import _to_item as timesheet_to_item
    from app.services.timesheet_service import InvalidTimesheetEntry, TimesheetNotEditable

    employee = _current_employee_or_404(db, current_user)
    try:
        timesheet = submit_my_entries(db, employee, timesheet_id, [e.dict() for e in body.entries])
    except NotYourTimesheet as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (InvalidTimesheetEntry, TimesheetNotEditable) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return timesheet_to_item(db, timesheet)


@router.post(
    "/timesheet/{timesheet_id}/submit",
    response_model=TimesheetItem,
    dependencies=[Depends(require_resource_permission("timesheet", "create"))]
)
def submit_my_own_timesheet(
    timesheet_id: str, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    from app.api.v1.endpoints.timesheets import _to_item as timesheet_to_item

    employee = _current_employee_or_404(db, current_user)
    try:
        timesheet = submit_my_timesheet(db, employee, timesheet_id)
    except NotYourTimesheet as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return timesheet_to_item(db, timesheet)


@router.get(
    "/timesheet/history",
    response_model=TimesheetListResponse,
    dependencies=[Depends(require_resource_permission("timesheet", "view"))]
)
def my_timesheet_history(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    from app.api.v1.endpoints.timesheets import _to_item as timesheet_to_item

    employee = _current_employee_or_404(db, current_user)
    history = get_my_timesheet_history(db, employee)
    return TimesheetListResponse(timesheets=[timesheet_to_item(db, t) for t in history])
