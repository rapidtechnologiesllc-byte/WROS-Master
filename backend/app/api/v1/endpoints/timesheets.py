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

Auth: get_current_internal_user, same posture as every endpoint this
program. Role-gating note, carried over honestly from timesheet_
service.py's own module docstring rather than silently invented: HRMS-
0902 BR-01 says "only RM/Admin may approve" a timesheet, but no "RM"
role exists in this codebase's RBAC (app/services/rbac_service.py's
role list has BU Head, HR Manager, Recruitment Manager, etc. -- no
clean match), so approve/reject/bulk-approve are NOT restricted beyond
"any internal user" here. Flagged, not guessed at.

Also wires two closely-related domains into the same file, since both
operate on a Timesheet and have no REST layer of their own yet:
  - S-229/HRMS-0910 AI Time Entry Anomaly Detection (timesheet_anomaly_
    service.py) -- advisory-only flags, never blocks submission/approval.
  - Timesheet Dispute Resolution (timesheet_dispute_service.py). NOTE:
    that service's own docstring cites "HRMS-0904" for itself, but the
    canonical sheet's real HRMS-0904/S-223 is "Employee Utilization
    Calculation" -- a genuine ID collision (same drift pattern already
    documented elsewhere in this codebase, e.g. BenchPeriod's
    docstring), flagged here rather than silently resolved. Built and
    exposed regardless of the exact canonical number, since the feature
    itself is real and invoice_service.py already depends on it
    (has_open_dispute() gates invoice generation).

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
  POST   /timesheets/{id}/scan-anomalies       Run anomaly detection (idempotent).
  GET    /timesheets/{id}/anomalies            Existing anomaly flags.
  POST   /timesheets/{id}/disputes             Raise a dispute (APPROVED timesheets only).
  GET    /timesheets/{id}/disputes             List disputes for a timesheet.
  POST   /timesheets/disputes/{dispute_id}/resolve   Resolve a dispute.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.core.permission_enforcement import require_permission
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_anomaly import TimesheetAnomalyFlag
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Users
from app.schemas.timesheet import (
    AnomalyFlagItem,
    AnomalyFlagsResponse,
    BulkApproveFailure,
    BulkApproveRequest,
    BulkApproveResponse,
    CreateWeeklyDraftRequest,
    DisputeItem,
    DisputeListResponse,
    RaiseDisputeRequest,
    RejectTimesheetRequest,
    ResolveDisputeRequest,
    TimesheetEntryItem,
    TimesheetItem,
    TimesheetListResponse,
    UpsertEntriesRequest,
)
from app.services.message_queue_service import MessageQueueService
from app.services.timesheet_anomaly_service import (
    get_anomaly_flags_for_timesheet,
    scan_timesheet_anomalies,
)
from app.services.timesheet_dispute_service import (
    DisputeValidationError,
    InvalidDisputeTransition,
    raise_dispute,
    resolve_dispute,
)
from app.services.timesheet_nag_service import scan_missing_timesheets, trigger_timesheet_nag
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
@require_permission("employee.create")
def create_draft(
    body: CreateWeeklyDraftRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
@require_permission("employee.edit")
def upsert_timesheet_entries(
    timesheet_id: str,
    body: UpsertEntriesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
@require_permission("employee.view")
def submit(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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

    # Queue timesheet_submitted for manager dashboard & commission recalculation
    MessageQueueService.enqueue(
        message_type="timesheet_submitted",
        payload={
            "timesheet_id": timesheet_id,
            "employee_id": timesheet.employee_id,
            "week_of": str(timesheet.week_of),
            "total_hours": sum(e.hours_logged or 0 for e in timesheet.entries) if timesheet.entries else 0,
            "submitted_by": current_user.UserID,
        },
        resource_id=timesheet_id,
        queue_type="DASHBOARD_QUEUE",
        created_by=current_user.UserID,
        db=db,
    )

    db.commit()
    db.refresh(timesheet)
    return _to_item(db, timesheet)


@router.post("/{timesheet_id}/approve", response_model=TimesheetItem, summary="Approve a submitted timesheet")
@require_permission("employee.edit")
def approve(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
@require_permission("employee.edit")
def reject(
    timesheet_id: str,
    body: RejectTimesheetRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
@require_permission("employee.edit")
def reopen(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
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
@require_permission("employee.edit")
def bulk_approve_endpoint(
    body: BulkApproveRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheets = db.query(Timesheet).filter(Timesheet.id.in_(body.timesheet_ids)).all()
    result = bulk_approve(db, timesheets, approved_by=current_user.UserID)
    db.commit()
    return BulkApproveResponse(
        approved=result["approved"],
        failed=[BulkApproveFailure(**f) for f in result["failed"]],
    )


@router.get("", response_model=TimesheetListResponse, summary="List timesheets")
@require_permission("employee.view")
def list_timesheets(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = db.query(Timesheet).filter(Timesheet.tenant_id == current_user.tenant_id)
    if employee_id:
        query = query.filter(Timesheet.employee_id == employee_id)
    if status:
        query = query.filter(Timesheet.status == status)
    timesheets = query.order_by(Timesheet.week_starting_date.desc()).all()
    return TimesheetListResponse(timesheets=[_to_item(db, t) for t in timesheets])


@router.get("/{timesheet_id}", response_model=TimesheetItem, summary="Get one timesheet with entries")
@require_permission("employee.view")
def get_timesheet(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    return _to_item(db, timesheet)


# ---------------------------------------------------------------------------
# S-229/HRMS-0910 -- Anomaly Detection (advisory only, never blocks anything)
# ---------------------------------------------------------------------------

def _flag_to_item(flag: TimesheetAnomalyFlag) -> AnomalyFlagItem:
    return AnomalyFlagItem(
        id=flag.id, timesheet_entry_id=flag.timesheet_entry_id,
        anomaly_type=flag.anomaly_type, detected_at=flag.detected_at,
    )


@router.post(
    "/{timesheet_id}/scan-anomalies", response_model=AnomalyFlagsResponse,
    summary="Run anomaly detection for a timesheet (advisory only, idempotent)",
)
def scan_anomalies(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    flags = scan_timesheet_anomalies(db, timesheet)
    db.commit()
    return AnomalyFlagsResponse(flags=[_flag_to_item(f) for f in flags])


@router.get(
    "/{timesheet_id}/anomalies", response_model=AnomalyFlagsResponse,
    summary="Get existing anomaly flags for a timesheet",
)
def get_anomalies(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    flags = get_anomaly_flags_for_timesheet(db, timesheet)
    return AnomalyFlagsResponse(flags=[_flag_to_item(f) for f in flags])


# ---------------------------------------------------------------------------
# Timesheet Dispute Resolution (canonical ID collision -- see module docstring)
# ---------------------------------------------------------------------------

def _dispute_to_item(dispute: TimesheetDispute) -> DisputeItem:
    return DisputeItem(
        id=dispute.id, timesheet_id=dispute.timesheet_id, raised_by=dispute.raised_by,
        raised_by_user_id=dispute.raised_by_user_id, disputed_date=dispute.disputed_date,
        disputed_hours=float(dispute.disputed_hours) if dispute.disputed_hours is not None else None,
        original_hours=float(dispute.original_hours), reason=dispute.reason, status=dispute.status,
        resolved_by=dispute.resolved_by, resolved_at=dispute.resolved_at,
        resolution_notes=dispute.resolution_notes,
        adjusted_hours=float(dispute.adjusted_hours) if dispute.adjusted_hours is not None else None,
    )


@router.post(
    "/{timesheet_id}/disputes", response_model=DisputeItem,
    summary="Raise a dispute against an approved timesheet",
)
def create_dispute(
    timesheet_id: str,
    body: RaiseDisputeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id)
    try:
        dispute = raise_dispute(
            db, timesheet, raised_by=body.raised_by, reason=body.reason,
            raised_by_user_id=current_user.UserID, disputed_date=body.disputed_date,
            disputed_hours=body.disputed_hours, tenant_id=current_user.tenant_id,
        )
    except DisputeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(dispute)
    return _dispute_to_item(dispute)


@router.get(
    "/{timesheet_id}/disputes", response_model=DisputeListResponse,
    summary="List disputes for a timesheet",
)
def list_disputes(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_timesheet_or_404(db, timesheet_id)
    disputes = (
        db.query(TimesheetDispute)
        .filter(TimesheetDispute.timesheet_id == timesheet_id)
        .order_by(TimesheetDispute.created_at.desc())
        .all()
    )
    return DisputeListResponse(disputes=[_dispute_to_item(d) for d in disputes])


@router.post(
    "/disputes/{dispute_id}/resolve", response_model=DisputeItem,
    summary="Resolve a dispute (ADJUSTED or CONFIRMED) -- never mutates the original timesheet",
)
def resolve_dispute_endpoint(
    dispute_id: str,
    body: ResolveDisputeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    dispute = db.query(TimesheetDispute).filter(TimesheetDispute.id == dispute_id).first()
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found.")
    try:
        dispute = resolve_dispute(
            db, dispute, resolution=body.resolution, resolved_by=current_user.UserID,
            resolution_notes=body.resolution_notes, adjusted_hours=body.adjusted_hours,
        )
    except InvalidDisputeTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except DisputeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(dispute)
    return _dispute_to_item(dispute)


@router.post("/nag-cascade/run", summary="EPIC-16 Timesheet Nag Cascade: scan + nag for one week")
def run_timesheet_nag_cascade(
    week_starting_date: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Not wired to a scheduler -- same posture as every other
    scheduled-job function in this codebase (a cron would call this
    per-week; the idempotent function itself is what's real and
    tested)."""
    from datetime import date as date_cls

    week = date_cls.fromisoformat(week_starting_date)
    missing = scan_missing_timesheets(db, week_starting_date=week, tenant_id=current_user.tenant_id)
    results = []
    for employee in missing:
        log = trigger_timesheet_nag(db, employee, week_starting_date=week, tenant_id=current_user.tenant_id)
        if log:
            results.append({"employee_id": employee.id, "escalation_level": log.escalation_level})
    return {"nagged": results}
