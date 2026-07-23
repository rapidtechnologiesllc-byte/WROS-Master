"""
S-220 (Create Weekly Timesheet) + S-221 (Timesheet Validation &
Submission Lock) + S-222 (Manager Approval) — API Endpoints
=========================================================================
Prefix: /timesheets
Tag:    timesheets

Wires app.services.timesheet_service (HRMS-0901/HRMS-0902 -- real,
tested backend, pre-existing this codebase) to real HTTP routes. No
REST layer previously existed at all. Also the "time tracking" link in
Avinash's stated MVP chain (candidate -> ... -> assign project -> time
tracking -> resource management) -- without this, an allocated employee
had no way to log hours through the app.

Auth: get_current_hr_or_admin, same posture as every endpoint this
program. Role-gating note, carried over honestly from timesheet_
service.py's own module docstring rather than silently invented: HRMS-
0902 BR-01 says "only RM/Admin may approve" a timesheet, but no "RM"
role exists in this codebase's RBAC (app/services/rbac_service.py's
role list has BU Head, HR Manager, Recruitment Manager, etc. -- no
clean match), so approve/reject/bulk-approve are NOT restricted beyond
"any internal user" here. Flagged, not guessed at.

Routes:
  POST   /timesheets/weekly-draft            Create (or return existing) a weekly draft.
  PUT    /timesheets/{id}/entries             Upsert daily entries.
  POST   /timesheets/{id}/submit              DRAFT -> SUBMITTED.
  POST   /timesheets/{id}/approve             SUBMITTED -> APPROVED.
  POST   /timesheets/{id}/reject              SUBMITTED -> REJECTED (20+ char reason).
  POST   /timesheets/{id}/reopen              REJECTED -> DRAFT.
  POST   /timesheets/bulk-approve             Approve many at once.
  GET    /timesheets                          List (optional employee_id/status filter).
  GET    /timesheets/{id}                     One timesheet with entries.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Users
from app.schemas.timesheet import (
    BulkApproveFailure,
    BulkApproveRequest,
    BulkApproveResponse,
    CreateWeeklyDraftRequest,
    RejectTimesheetRequest,
    TimesheetEntryItem,
    TimesheetItem,
    TimesheetListResponse,
    UpsertEntriesRequest,
)
from app.services.timesheet_service import (
    AllocationNotActive,
    InvalidTimesheetEntry,
    InvalidTimesheetTransition,
    StaleTimesheetSubmission,
    TimesheetNotEditable,
    approve_timesheet,
    bulk_approve,
    create_weekly_draft,
    reject_timesheet,
    reopen_for_editing,
    submit_timesheet,
    upsert_entries,
)

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


def _to_item(db: Session, timesheet: Timesheet) -> TimesheetItem:
    employee = db.query(Employee).filter(Employee.id == timesheet.employee_id).first()
    employee_name = (
        f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown employee)"
    )
    entries = (
        db.query(TimesheetEntry)
        .filter(TimesheetEntry.timesheet_id == timesheet.id)
        .order_by(TimesheetEntry.entry_date.asc())
        .all()
    )
    return TimesheetItem(
        id=timesheet.id,
        employee_id=timesheet.employee_id,
        employee_name=employee_name,
        allocation_id=timesheet.allocation_id,
        week_starting_date=timesheet.week_starting_date,
        total_hours=float(timesheet.total_hours),
        billable_hours=float(timesheet.billable_hours),
        non_billable_hours=float(timesheet.non_billable_hours),
        status=timesheet.status,
        submitted_at=timesheet.submitted_at,
        approved_by=timesheet.approved_by,
        approved_at=timesheet.approved_at,
        rejection_reason=timesheet.rejection_reason,
        entries=[
            TimesheetEntryItem(
                id=e.id, entry_date=e.entry_date, hours=float(e.hours),
                entry_type=e.entry_type, notes=e.notes,
            )
            for e in entries
        ],
    )


def _get_timesheet_or_404(db: Session, timesheet_id: str) -> Timesheet:
    timesheet = db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
    if timesheet is None:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    return timesheet


@router.post("/weekly-draft", response_model=TimesheetItem, summary="Create (or return existing) a weekly timesheet draft")
def create_draft(
    body: CreateWeeklyDraftRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == body.allocation_id).first()
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found.")

    try:
        timesheet = create_weekly_draft(
            db, allocation, body.week_starting_date, tenant_id=current_user.tenant_id,
        )
    except AllocationNotActive as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.put("/{timesheet_id}/entries", response_model=TimesheetItem, summary="Upsert daily entries for a timesheet")
def upsert_timesheet_entries(
    timesheet_id: str,
    body: UpsertEntriesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    entries = [e.model_dump() for e in body.entries]
    try:
        timesheet = upsert_entries(db, timesheet, entries)
    except TimesheetNotEditable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.post("/{timesheet_id}/submit", response_model=TimesheetItem, summary="Submit a draft timesheet")
def submit(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    try:
        timesheet = submit_timesheet(db, timesheet)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StaleTimesheetSubmission as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.post("/{timesheet_id}/approve", response_model=TimesheetItem, summary="Approve a submitted timesheet")
def approve(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    try:
        timesheet = approve_timesheet(db, timesheet, approved_by=current_user.UserID)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.post("/{timesheet_id}/reject", response_model=TimesheetItem, summary="Reject a submitted timesheet")
def reject(
    timesheet_id: str,
    body: RejectTimesheetRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    try:
        timesheet = reject_timesheet(db, timesheet, body.reason)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.post("/{timesheet_id}/reopen", response_model=TimesheetItem, summary="Reopen a rejected timesheet for editing")
def reopen(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    try:
        timesheet = reopen_for_editing(db, timesheet)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.post("/bulk-approve", response_model=BulkApproveResponse, summary="Approve multiple submitted timesheets at once")
def bulk_approve_endpoint(
    body: BulkApproveRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheets = db.query(Timesheet).filter(Timesheet.id.in_(body.timesheet_ids)).all()
    result = bulk_approve(db, timesheets, approved_by=current_user.UserID)
    db.commit()
    return BulkApproveResponse(
        approved=result["approved"],
        failed=[BulkApproveFailure(**f) for f in result["failed"]],
    )


@router.get("", response_model=TimesheetListResponse, summary="List timesheets")
def list_timesheets(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    query = db.query(Timesheet).filter(Timesheet.tenant_id == current_user.tenant_id)
    if employee_id:
        query = query.filter(Timesheet.employee_id == employee_id)
    if status:
        query = query.filter(Timesheet.status == status)
    timesheets = query.order_by(Timesheet.week_starting_date.desc()).all()
    return TimesheetListResponse(timesheets=[_to_item(db, t) for t in timesheets])


@router.get("/{timesheet_id}", response_model=TimesheetItem, summary="Get one timesheet with entries")
def get_timesheet(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    return _to_item(db, timesheet)
