"""
Employee self-service timesheet.
==================================================================
Prefix: /my
Tag:    my-timesheet

Real gap closed 2026-08-04: the existing timesheet engine (see
app.services.employee_self_service module docstring) was entirely
HR-operated. Every endpoint here resolves the CALLER's own Employee
record and only ever touches their own allocations/timesheets --
never a client-supplied employee_id, unlike the existing HR-facing
/allocations and /timesheets endpoints.

GET  /my/allocations                          -- my active project allocations
GET  /my/work-items                           -- the bench work items I may log time against
GET  /my/timesheet/weeks                       -- the weeks I may fill (this week + the back-dating window)
GET  /my/timesheet/current?allocation_id=&week_starting=
                                               -- that week's draft, this week by default (created if missing)
PUT  /my/timesheet/{id}/entries                -- log my own hours
POST /my/timesheet/{id}/submit                 -- submit my own timesheet
GET  /my/timesheet/history
"""
from datetime import date
from typing import Optional

from app.api.v1.endpoints.timesheets import _to_item as timesheet_to_item
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.allocation import AllocationListResponse
from app.schemas.timesheet import SubmitTimesheetRequest, TimesheetItem, TimesheetListResponse, UpsertEntriesRequest
from app.services.employee_self_service import (
    NoLinkedEmployeeRecord, NotYourAllocation, NotYourTimesheet, WeekOutsideWindow, allowed_weeks,
    get_my_active_allocations, get_my_timesheet_history, get_or_start_my_week_timesheet,
    get_or_start_my_work_item_timesheet, my_work_items, own_timesheet, resolve_current_employee, self_service_back_weeks, submit_my_entries,
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
    dependencies=[Depends(require_resource_permission("my-timesheet", "view"))]  # own allocations only
)
def my_allocations(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    from app.api.v1.endpoints.allocations import _to_item as allocation_to_item

    employee = _current_employee_or_404(db, current_user)
    allocations = get_my_active_allocations(db, employee)
    return AllocationListResponse(allocations=[allocation_to_item(db, a) for a in allocations])

@router.get(
    "/work-items",
    dependencies=[Depends(require_resource_permission("my-timesheet", "view"))]
)
def my_bench_work_items(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    """Bench work I may log time against: the accelerators, certifications and BU-head-approved
    work of my business unit (and those open to everyone)."""
    from app.models.bench_work_item import WORK_ITEM_CATEGORIES

    employee = _current_employee_or_404(db, current_user)
    return {"work_items": [
        {"id": i.id, "name": i.name, "category": i.category,
         "category_label": WORK_ITEM_CATEGORIES.get(i.category, i.category), "description": i.description}
        for i in my_work_items(db, employee)]}


class MyTimesheetWeeksResponse(BaseModel):
    weeks: list
    back_weeks: int


@router.get(
    "/timesheet/weeks",
    response_model=MyTimesheetWeeksResponse,
    dependencies=[Depends(require_resource_permission("my-timesheet", "view"))]
)
def my_timesheet_weeks(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    """The weeks the caller may open: this week first, then the earlier weeks of the window."""
    _current_employee_or_404(db, current_user)
    return MyTimesheetWeeksResponse(weeks=[w.isoformat() for w in allowed_weeks()], back_weeks=self_service_back_weeks())


@router.get(
    "/timesheet/current",
    response_model=TimesheetItem,
    dependencies=[Depends(require_resource_permission("my-timesheet", "view"))]
)
def my_current_timesheet(
    allocation_id: Optional[str] = None, week_starting: Optional[date] = None, work_item_id: Optional[str] = None,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    """The week's draft for one of my allocations, or (work_item_id) for a bench work item."""
    from app.services.timesheet_service import AllocationNotActive

    employee = _current_employee_or_404(db, current_user)
    if not allocation_id and not work_item_id:
        raise HTTPException(status_code=422, detail="Pick what the time is for: your allocation or a bench work item.")
    try:
        if work_item_id:
            timesheet = get_or_start_my_work_item_timesheet(db, employee, work_item_id, week_starting=week_starting)
        else:
            timesheet = get_or_start_my_week_timesheet(db, employee, allocation_id, week_starting=week_starting)
    except NotYourAllocation as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except WeekOutsideWindow as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except AllocationNotActive as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return timesheet_to_item(db, timesheet, current_user)

@router.put(
    "/timesheet/{timesheet_id}/entries",
    response_model=TimesheetItem,
    dependencies=[Depends(require_resource_permission("my-timesheet", "edit"))]
)
def log_my_hours(
    timesheet_id: str, body: UpsertEntriesRequest,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    from app.services.timesheet_service import InvalidTimesheetEntry, TimesheetNotEditable

    employee = _current_employee_or_404(db, current_user)
    try:
        timesheet = submit_my_entries(db, employee, timesheet_id, [e.dict() for e in body.entries])
    except NotYourTimesheet as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (InvalidTimesheetEntry, TimesheetNotEditable) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return timesheet_to_item(db, timesheet, current_user)

@router.post(
    "/timesheet/{timesheet_id}/submit",
    response_model=TimesheetItem,
    dependencies=[Depends(require_resource_permission("my-timesheet", "create"))]
)
def submit_my_own_timesheet(
    timesheet_id: str, body: Optional[SubmitTimesheetRequest] = None,
    current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    """Submit my week: routed to my approver with an approval task. A rejected week comes back only
    changed, or with my response to the reason (body.response)."""
    from app.api.v1.endpoints.timesheets import run_approval_step
    from app.services.timesheet_approval_service import submit_for_approval

    employee = _current_employee_or_404(db, current_user)
    try:
        timesheet = own_timesheet(db, employee, timesheet_id)
    except NotYourTimesheet as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    run_approval_step(db, lambda: submit_for_approval(db, timesheet, current_user,
                                                      response=body.response if body else None))
    db.refresh(timesheet)
    return timesheet_to_item(db, timesheet, current_user)

@router.get(
    "/timesheet/history",
    response_model=TimesheetListResponse,
    dependencies=[Depends(require_resource_permission("my-timesheet", "view"))]
)
def my_timesheet_history(week_starting: Optional[date] = None,
                         current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    """My recent timesheets; with week_starting, every one of that week (the rows of the week's
    time card: one per placement or bench work item)."""
    employee = _current_employee_or_404(db, current_user)
    history = get_my_timesheet_history(db, employee, week_starting=week_starting)
    return TimesheetListResponse(timesheets=[timesheet_to_item(db, t, current_user) for t in history])
