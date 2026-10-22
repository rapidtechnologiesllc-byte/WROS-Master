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

Auth: the role template's timesheets permission (view / edit) decides
the actions; the business unit decides the records (CEO 2026-10-12,
app.core.data_scope): a timesheet is visible when its employee's BU or
its allocation's client's BU is in the caller's scope, and a user always
sees their own. Org-level role templates see every timesheet.

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
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.data_scope import allocation_filter, timesheet_filter
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_role_template_permission
from app.core.permission_registry import Permissions
import logging

logger = logging.getLogger(__name__)
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_anomaly import TimesheetAnomalyFlag
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Users
from app.schemas.timesheet import (
    AnomalyFlagItem,
    AnomalyFlagsResponse,
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
from app.services.timesheet_service import (
    AllocationNotActive,
    InvalidTimesheetEntry,
    InvalidTimesheetTransition,
    StaleTimesheetSubmission,
    TimesheetNotEditable,
    approve_timesheet,
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

def _own_employee_ids(user: Users):
    """The caller's own employee record(s): a user always sees their own timesheets."""
    return select(Employee.id).where(Employee.wros_user_id == user.UserID)


def _visible_timesheets(db: Session, user: Users):
    """This tenant's timesheets the caller may see: inside their business units (the employee's
    BU or the allocation's client's BU -- app.core.data_scope), or their own."""
    return db.query(Timesheet).filter(
        Timesheet.tenant_id == user.tenant_id,
        or_(timesheet_filter(db, user), Timesheet.employee_id.in_(_own_employee_ids(user))),
    )


def _get_timesheet_or_404(db: Session, timesheet_id: str, user: Users) -> Timesheet:
    """Every /timesheets/{id} route goes through here: another tenant's or another business
    unit's timesheet is 404, the same answer as one that does not exist."""
    timesheet = _visible_timesheets(db, user).filter(Timesheet.id == timesheet_id).first()
    if timesheet is None:
        raise HTTPException(status_code=404, detail="Timesheet not found.")
    return timesheet

@router.get(
    "/allocations",
    summary="Active allocations a timesheet can be started for (the New Weekly Timesheet picker)",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def timesheet_allocations(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Every ACTIVE allocation the caller may start a draft for (the same scope as POST
    /weekly-draft), grouped by employee for an employee -> allocation picker."""
    from app.api.v1.endpoints.allocations import _to_item as allocation_to_item

    rows = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.tenant_id == current_user.tenant_id, EmployeeAllocation.status == "ACTIVE",
        or_(allocation_filter(db, current_user), EmployeeAllocation.employee_id.in_(_own_employee_ids(current_user))),
    ).order_by(EmployeeAllocation.start_date.desc()).all()
    employees = {}
    for allocation in rows:
        item = allocation_to_item(db, allocation)
        entry = employees.setdefault(item.employee_id, {"employee_id": item.employee_id,
                                                        "employee_name": item.employee_name, "allocations": []})
        entry["allocations"].append({
            "id": item.id, "client_name": item.client_name, "demand_job_title": item.demand_job_title,
            "start_date": item.start_date, "end_date": item.end_date,
        })
    return {"employees": sorted(employees.values(), key=lambda e: e["employee_name"].lower())}


@router.post(
    "/weekly-draft",
    response_model=TimesheetItem,
    summary="Create (or return existing) a weekly timesheet draft",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def create_draft(
    body: CreateWeeklyDraftRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    allocation = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.id == body.allocation_id, EmployeeAllocation.tenant_id == current_user.tenant_id,
        or_(allocation_filter(db, current_user), EmployeeAllocation.employee_id.in_(_own_employee_ids(current_user))),
    ).first()
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

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_created",
            data={
                "timesheet_id": timesheet.id,
                "employee_id": timesheet.employee_id,
                "week_starting": str(timesheet.week_starting_date),
                "status": timesheet.status,
            },
        )
        db.refresh(timesheet)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create timesheet {timesheet.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (create timesheet); retry or tell support.")
    return _to_item(db, timesheet)

@router.put(
    "/{timesheet_id}/entries",
    response_model=TimesheetItem,
    summary="Upsert daily entries for a timesheet",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def upsert_timesheet_entries(
    timesheet_id: str,
    body: UpsertEntriesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    entries = [e.model_dump() for e in body.entries]
    try:
        timesheet = upsert_entries(db, timesheet, entries)
    except TimesheetNotEditable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_entries_updated",
            data={
                "timesheet_id": timesheet.id,
                "employee_id": timesheet.employee_id,
                "entries_count": len(entries),
                "status": timesheet.status,
            },
        )
        db.refresh(timesheet)
        return _to_item(db, timesheet)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update timesheet entries {timesheet.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (update timesheet); retry or tell support.")

@router.post(
    "/{timesheet_id}/submit",
    response_model=TimesheetItem,
    summary="Submit a draft timesheet",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def submit(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    try:
        timesheet = submit_timesheet(db, timesheet)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StaleTimesheetSubmission as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        # Queue timesheet_submitted for manager dashboard & commission recalculation
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_submitted",
            data={
                "timesheet_id": timesheet_id,
                "employee_id": timesheet.employee_id,
                "week_of": str(timesheet.week_starting_date),
                "total_hours": float(timesheet.total_hours or 0),
                "submitted_by": current_user.UserID,
            },
        )
        db.refresh(timesheet)
        return _to_item(db, timesheet)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to submit timesheet {timesheet_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (submit timesheet); retry or tell support.")

@router.post(
    "/{timesheet_id}/approve",
    response_model=TimesheetItem,
    summary="Approve a submitted timesheet",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def approve(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    try:
        timesheet = approve_timesheet(db, timesheet, approved_by=current_user.UserID)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_approved",
            data={
                "timesheet_id": timesheet_id,
                "employee_id": timesheet.employee_id,
                "approved_by": current_user.UserID,
            },
        )
        db.refresh(timesheet)
        return _to_item(db, timesheet)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to approve timesheet {timesheet_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (approve timesheet); retry or tell support.")

@router.post(
    "/{timesheet_id}/reject",
    response_model=TimesheetItem,
    summary="Reject a submitted timesheet",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def reject(
    timesheet_id: str,
    body: RejectTimesheetRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    try:
        timesheet = reject_timesheet(db, timesheet, body.reason)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTimesheetEntry as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_rejected",
            data={
                "timesheet_id": timesheet_id,
                "employee_id": timesheet.employee_id,
                "rejection_reason": body.reason,
                "rejected_by": current_user.UserID,
            },
        )
        db.refresh(timesheet)
        return _to_item(db, timesheet)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reject timesheet {timesheet_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (reject timesheet); retry or tell support.")

@router.post(
    "/{timesheet_id}/reopen",
    response_model=TimesheetItem,
    summary="Reopen a rejected timesheet for editing",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def reopen(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    try:
        timesheet = reopen_for_editing(db, timesheet)
    except InvalidTimesheetTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_reopened",
            data={
                "timesheet_id": timesheet_id,
                "employee_id": timesheet.employee_id,
                "reopened_by": current_user.UserID,
            },
        )
        db.refresh(timesheet)
        return _to_item(db, timesheet)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reopen timesheet {timesheet_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (reopen timesheet); retry or tell support.")


@router.get(
    "",
    response_model=TimesheetListResponse,
    summary="List timesheets",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))]
)
def list_timesheets(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = _visible_timesheets(db, current_user)
    if employee_id:
        query = query.filter(Timesheet.employee_id == employee_id)
    if status:
        query = query.filter(Timesheet.status == status)
    timesheets = query.order_by(Timesheet.week_starting_date.desc()).all()
    return TimesheetListResponse(timesheets=[_to_item(db, t) for t in timesheets])

@router.get(
    "/{timesheet_id}",
    response_model=TimesheetItem,
    summary="Get one timesheet with entries",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))]
)
def get_timesheet(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
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
    "/{timesheet_id}/scan-anomalies",
    response_model=AnomalyFlagsResponse,
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))],
    summary="Run anomaly detection for a timesheet (advisory only, idempotent)",
)
def scan_anomalies(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    flags = scan_timesheet_anomalies(db, timesheet)

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="timesheet_anomalies_scanned",
            data={
                "timesheet_id": timesheet_id,
                "employee_id": timesheet.employee_id,
                "flags_count": len(flags),
            },
        )
        return AnomalyFlagsResponse(flags=[_flag_to_item(f) for f in flags])
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to scan timesheet anomalies {timesheet_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (scan anomalies); retry or tell support.")

@router.get(
    "/{timesheet_id}/anomalies",
    response_model=AnomalyFlagsResponse,
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))],
    summary="Get existing anomaly flags for a timesheet",
)
def get_anomalies(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
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
    "/{timesheet_id}/disputes",
    response_model=DisputeItem,
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))],
    summary="Raise a dispute against an approved timesheet",
)
def create_dispute(
    timesheet_id: str,
    body: RaiseDisputeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    try:
        dispute = raise_dispute(
            db, timesheet, raised_by=body.raised_by, reason=body.reason,
            raised_by_user_id=current_user.UserID, disputed_date=body.disputed_date,
            disputed_hours=body.disputed_hours, tenant_id=current_user.tenant_id,
        )
    except DisputeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=timesheet.tenant_id,
            task_name="dispute_raised",
            data={
                "dispute_id": dispute.id,
                "timesheet_id": timesheet_id,
                "raised_by": body.raised_by,
                "reason": body.reason,
                "disputed_hours": float(body.disputed_hours) if body.disputed_hours else None,
            },
        )
        db.refresh(dispute)
        return _dispute_to_item(dispute)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create dispute for timesheet {timesheet_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (raise dispute); retry or tell support.")

@router.get(
    "/{timesheet_id}/disputes",
    response_model=DisputeListResponse,
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))],
    summary="List disputes for a timesheet",
)
def list_disputes(
    timesheet_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    _get_timesheet_or_404(db, timesheet_id, current_user)
    disputes = (
        db.query(TimesheetDispute)
        .filter(TimesheetDispute.timesheet_id == timesheet_id)
        .order_by(TimesheetDispute.created_at.desc())
        .all()
    )
    return DisputeListResponse(disputes=[_dispute_to_item(d) for d in disputes])

@router.post(
    "/disputes/{dispute_id}/resolve",
    response_model=DisputeItem,
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))],
    summary="Resolve a dispute (ADJUSTED or CONFIRMED) -- never mutates the original timesheet",
)
def resolve_dispute_endpoint(
    dispute_id: str,
    body: ResolveDisputeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    dispute = db.query(TimesheetDispute).filter(TimesheetDispute.id == dispute_id).first()
    # a dispute on a timesheet outside the caller's tenant/business units does not exist for them
    if dispute is None or _visible_timesheets(db, current_user).filter(Timesheet.id == dispute.timesheet_id).first() is None:
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

    # Persist the change first; the queued event refers to saved rows
    db.commit()
    try:
        MessageQueueService.enqueue(
            tenant_id=current_user.tenant_id,
            task_name="dispute_resolved",
            data={
                "dispute_id": dispute_id,
                "timesheet_id": dispute.timesheet_id,
                "resolution": body.resolution,
                "resolution_notes": body.resolution_notes,
                "adjusted_hours": float(body.adjusted_hours) if body.adjusted_hours else None,
            },
        )
        db.refresh(dispute)
        return _dispute_to_item(dispute)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to resolve dispute {dispute_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (resolve dispute); retry or tell support.")

