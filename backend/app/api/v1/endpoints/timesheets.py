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
  POST   /timesheets/weekly-draft            Create (or return existing) a weekly draft (own time only).
  PUT    /timesheets/{id}/entries             Upsert daily entries (own time only).
  POST   /timesheets/{id}/submit              DRAFT -> SUBMITTED (own time only; routed to the
                                              reporting manager).
  GET    /timesheets/work-items               Bench work items (accelerators, certifications,
                                              BU-head-approved work) time can be logged against.
  POST   /timesheets/work-items               A BU leader adds (= approves) a work item.
  POST   /timesheets/work-items/{id}/close    Close it: no new time.
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
    ApproveTimesheetRequest,
    CreateWeeklyDraftRequest,
    DisputeItem,
    DisputeListResponse,
    RaiseDisputeRequest,
    RejectTimesheetRequest,
    ResolveDisputeRequest,
    WorkItemItem,
    WorkItemListResponse,
    WorkItemRequest,
    SubmitTimesheetRequest,
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
    create_weekly_draft,
    reopen_for_editing,
    upsert_entries,
)

from app.services.timesheet_approval_service import rejection_for_employee

router = APIRouter(prefix="/timesheets", tags=["timesheets"])

def _where_logged(db: Session, timesheet: Timesheet) -> dict:
    """Where the week's time is logged, for the grouping on the screens: a client placement (Staff
    Aug), a project, a bench work item (accelerator, certification, BU-head-approved work) or an
    internal task."""
    from app.models.bench_work_item import WORK_ITEM_CATEGORIES, BenchWorkItem
    from app.models.client import Client
    from app.models.project import Project
    from app.models.task import Task

    if timesheet.work_item_id:
        item = db.get(BenchWorkItem, timesheet.work_item_id)
        category = WORK_ITEM_CATEGORIES.get(item.category, item.category) if item else "Bench work"
        return {"work_type": "BENCH", "work_group": category, "work_label": item.name if item else "Bench work"}
    if timesheet.allocation_id:
        allocation = db.get(EmployeeAllocation, timesheet.allocation_id)
        if allocation is None:
            return {"work_type": "STAFF_AUG", "work_group": "Client work", "work_label": "(allocation removed)"}
        client = db.get(Client, allocation.client_id)
        project = db.get(Project, allocation.project_id) if allocation.project_id else None
        where = [client.company_name if client else None, project.name if project else None, allocation.role]
        label = " · ".join(dict.fromkeys(w for w in where if w))
        if project is not None and not project.is_billable:
            return {"work_type": "PROJECT", "work_group": "Internal project", "work_label": label}
        if project is not None and not allocation.demand_id:
            return {"work_type": "PROJECT", "work_group": "Project", "work_label": label}
        return {"work_type": "STAFF_AUG", "work_group": "Staff Aug", "work_label": label}
    task = db.get(Task, timesheet.task_id) if timesheet.task_id else None
    return {"work_type": "INTERNAL_TASK", "work_group": "Internal task", "work_label": task.title if task else "Internal task"}


def _to_item(db: Session, timesheet: Timesheet, viewer: Optional[Users] = None) -> TimesheetItem:
    from datetime import timedelta

    from app.services.timesheet_approval_service import pipeline

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
        rejection=rejection_for_employee(db, timesheet) if timesheet.status in ("REJECTED", "DRAFT") else None,
        week_ending_date=timesheet.week_starting_date + timedelta(days=6),
        is_own=bool(viewer is not None and employee is not None and employee.wros_user_id == viewer.UserID),
        work_item_id=timesheet.work_item_id,
        pipeline=pipeline(db, timesheet),
        **_where_logged(db, timesheet),
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


def _own_or_403(db: Session, timesheet: Timesheet, user: Users) -> None:
    """Only the employee enters and submits their own time (CEO 2026-11-11): whatever a role may
    see or approve, nobody fills in or submits someone else's week."""
    employee = db.get(Employee, timesheet.employee_id)
    if employee is None or employee.wros_user_id != user.UserID:
        who = f"{employee.first_name} {employee.last_name}".strip() if employee else "the employee"
        raise HTTPException(status_code=403, detail=(
            f"Only {who} can enter and submit this timesheet (My Timesheet). "
            "You can review it, and approve or reject it once it is submitted."))


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
    """The caller's own ACTIVE allocations (the same scope as POST /weekly-draft): only the
    employee starts and fills their own week."""
    from app.api.v1.endpoints.allocations import _to_item as allocation_to_item

    rows = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.tenant_id == current_user.tenant_id, EmployeeAllocation.status == "ACTIVE",
        EmployeeAllocation.employee_id.in_(_own_employee_ids(current_user)),
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


# --------------------------------------------------------------------------- bench work items

def _may_manage_work_items(db: Session, user: Users) -> bool:
    """A BU leader approves bench work: BU Head level and above, a named head of a business unit,
    or an org-level role template (role template driven, never a role name)."""
    from app.core import authority

    return (authority.is_bu_leader(db, user) or authority.heads_a_business_unit(db, user)
            or authority.is_org_level(db, user))


def _work_item(db: Session, item) -> WorkItemItem:
    from app.models.bench_work_item import WORK_ITEM_CATEGORIES
    from app.models.business_unit import BusinessUnit

    unit = db.get(BusinessUnit, item.business_unit_id) if item.business_unit_id else None
    approver = db.get(Users, item.approved_by_user_id) if item.approved_by_user_id else None
    return WorkItemItem(
        id=item.id, name=item.name, category=item.category,
        category_label=WORK_ITEM_CATEGORIES.get(item.category, item.category),
        business_unit_id=item.business_unit_id, business_unit_name=(unit.display_name or unit.name) if unit else None,
        description=item.description, status=item.status,
        approved_by_name=approver.UserName if approver else None, approved_at=item.approved_at)


@router.get(
    "/work-items",
    response_model=WorkItemListResponse,
    summary="Bench work items: accelerators, certifications and BU-head-approved work to log time against",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))]
)
def list_work_items(
    include_closed: bool = False,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.core.data_scope import bu_filter
    from app.models.bench_work_item import WORK_ITEM_CATEGORIES, BenchWorkItem

    query = db.query(BenchWorkItem).filter(
        BenchWorkItem.tenant_id == current_user.tenant_id, bu_filter(db, current_user, BenchWorkItem.business_unit_id))
    if not include_closed:
        query = query.filter(BenchWorkItem.status == "ACTIVE")
    items = query.order_by(BenchWorkItem.category, BenchWorkItem.name).all()
    return WorkItemListResponse(work_items=[_work_item(db, i) for i in items], categories=dict(WORK_ITEM_CATEGORIES),
                                can_manage=_may_manage_work_items(db, current_user))


@router.post(
    "/work-items",
    response_model=WorkItemItem,
    summary="Add a bench work item (a BU leader: adding it is the approval)",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def create_work_item(
    body: WorkItemRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from datetime import datetime

    from app.core.data_scope import bu_filter
    from app.models.bench_work_item import WORK_ITEM_CATEGORIES, BenchWorkItem
    from app.models.business_unit import BusinessUnit

    if not _may_manage_work_items(db, current_user):
        raise HTTPException(status_code=403, detail="Bench work is approved by a BU head: only a BU leader can add a work item.")
    if body.category not in WORK_ITEM_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Category must be one of {list(WORK_ITEM_CATEGORIES)}.")
    if body.business_unit_id is not None and db.query(BusinessUnit.id).filter(
            BusinessUnit.id == body.business_unit_id, BusinessUnit.tenant_id == current_user.tenant_id,
            bu_filter(db, current_user, BusinessUnit.id, unassigned_visible=False)).first() is None:
        raise HTTPException(status_code=404, detail="Business unit not found.")
    name = body.name.strip()
    duplicate = db.query(BenchWorkItem.id).filter(
        BenchWorkItem.tenant_id == current_user.tenant_id, BenchWorkItem.status == "ACTIVE",
        BenchWorkItem.name == name, BenchWorkItem.business_unit_id == body.business_unit_id).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail=f"An active work item named {name!r} already exists there.")
    item = BenchWorkItem(tenant_id=current_user.tenant_id, business_unit_id=body.business_unit_id, name=name,
                         category=body.category, description=(body.description or "").strip() or None,
                         approved_by_user_id=current_user.UserID, approved_at=datetime.utcnow())
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info(f"[BenchWork] {current_user.UserID} approved work item {item.id} ({item.category}: {item.name})")
    return _work_item(db, item)


@router.post(
    "/work-items/{work_item_id}/close",
    response_model=WorkItemItem,
    summary="Close a bench work item: no new time is logged against it (logged time stays)",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def close_work_item(
    work_item_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from datetime import datetime

    from app.core.data_scope import bu_filter
    from app.models.bench_work_item import BenchWorkItem

    if not _may_manage_work_items(db, current_user):
        raise HTTPException(status_code=403, detail="Only a BU leader can close a work item.")
    item = db.query(BenchWorkItem).filter(
        BenchWorkItem.id == work_item_id, BenchWorkItem.tenant_id == current_user.tenant_id,
        bu_filter(db, current_user, BenchWorkItem.business_unit_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found.")
    if item.status != "CLOSED":
        item.status, item.closed_at = "CLOSED", datetime.utcnow()
        db.commit()
        db.refresh(item)
    return _work_item(db, item)


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
    owner = db.get(Employee, allocation.employee_id)
    if owner is None or owner.wros_user_id != current_user.UserID:
        who = f"{owner.first_name} {owner.last_name}".strip() if owner else "the employee"
        raise HTTPException(status_code=403, detail=f"Only {who} can start their own timesheet (My Timesheet).")

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
    return _to_item(db, timesheet, current_user)

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
    _own_or_403(db, timesheet, current_user)
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
        return _to_item(db, timesheet, current_user)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update timesheet entries {timesheet.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (update timesheet); retry or tell support.")

def run_approval_step(db: Session, step):
    """Run one approval-loop step and map its refusals to HTTP; commits, then sends the notices.
    Shared by /timesheets, /my/timesheet and /timesheet-approvals so every path routes the same way."""
    from app.services import timesheet_approval_service as approvals

    try:
        review = step()
    except (approvals.NotTheApprover,) as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except (approvals.NoTimesheetApprover, InvalidTimesheetTransition) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except (approvals.ResubmitNeedsChange, approvals.AddressedNotConfirmed, InvalidTimesheetEntry,
            StaleTimesheetSubmission, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    approvals.send_notices(db, review)
    return review


@router.post(
    "/{timesheet_id}/submit",
    response_model=TimesheetItem,
    summary="Submit a draft timesheet (routed to the employee's approver with a task)",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def submit(
    timesheet_id: str,
    body: Optional[SubmitTimesheetRequest] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.timesheet_approval_service import submit_for_approval

    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    _own_or_403(db, timesheet, current_user)
    run_approval_step(db, lambda: submit_for_approval(db, timesheet, current_user,
                                                      response=body.response if body else None))
    db.refresh(timesheet)
    return _to_item(db, timesheet, current_user)


@router.post(
    "/{timesheet_id}/approve",
    response_model=TimesheetItem,
    summary="Approve a submitted timesheet (the routed approver, or timesheet edit rights on its BU)",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def approve(
    timesheet_id: str,
    body: Optional[ApproveTimesheetRequest] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.timesheet_approval_service import approve as approve_step

    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    body = body or ApproveTimesheetRequest()
    run_approval_step(db, lambda: approve_step(db, timesheet, current_user, comment=body.comment,
                                               addressed=body.addressed))
    db.refresh(timesheet)
    return _to_item(db, timesheet, current_user)


@router.post(
    "/{timesheet_id}/reject",
    response_model=TimesheetItem,
    summary="Reject a submitted timesheet with a reason (the employee gets a resubmit task)",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
def reject(
    timesheet_id: str,
    body: RejectTimesheetRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.timesheet_approval_service import reject as reject_step

    timesheet = _get_timesheet_or_404(db, timesheet_id, current_user)
    run_approval_step(db, lambda: reject_step(db, timesheet, current_user, reason=body.reason,
                                              flagged_dates=body.flagged_dates))
    db.refresh(timesheet)
    return _to_item(db, timesheet, current_user)

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
    _own_or_403(db, timesheet, current_user)
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
        from app.services.action_emails.timesheets import notify_reopened

        notify_reopened(db, timesheet, actor=current_user)
        return _to_item(db, timesheet, current_user)
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
    return TimesheetListResponse(timesheets=[_to_item(db, t, current_user) for t in timesheets])

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
    return _to_item(db, timesheet, current_user)

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
        from app.services.action_emails.timesheets import notify_dispute_raised

        notify_dispute_raised(db, dispute, actor=current_user)
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
        from app.services.action_emails.timesheets import notify_dispute_resolved

        notify_dispute_resolved(db, dispute, actor=current_user)
        return _dispute_to_item(dispute)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to resolve dispute {dispute_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Saved, but the follow-up event could not be queued (resolve dispute); retry or tell support.")

