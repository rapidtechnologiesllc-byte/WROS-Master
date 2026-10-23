"""
HRMS-0507 -- allocate/end-allocation, the one write path that moves an
employee off (or back onto) the bench. Per 04-RESOURCE-MANAGEMENT.md's
own framing, this is always a distinct human decision, never automatic
-- there is no agent or ranking logic here (that's Phase 4 Part A).

Reuses app.services.employee_service.transition_employee_status() for
the actual status change rather than setting Employee.status directly,
so the transition-validity + history-logging guarantee stays in the one
place it already lives.

Phase 4 Part B wiring: mark_employee_on_bench()/remove_employee_from_
bench() keep app.models.resource_management.BenchPoolEntry in sync with
every BENCH/ALLOCATED transition this module already makes -- not a
separate scheduled job, so bench_pool can never drift out of sync with
Employee.status. log_allocation_conflict() records a permanent audit
row the moment AllocationOverCapacity is about to be raised.

Edit and margin guard (CEO 2026-10-23): edit_allocation() changes the end date, bill rate,
utilization or billable flag, writing an AllocationChange history row (who, when, old -> new,
reason). Every placement rule runs on the new values (_assert_placement_rules: the client
submission gates of deployment_readiness_service, the employment-type rule, capacity) and the
margin guard (margin_guard_service) -- except for an edit that only reduces the commitment
(earlier end, lower utilization, billable off), which deploys nobody. A placement or edit below
the margin floor waits for approval (PENDING_MARGIN_APPROVAL / a pending AllocationChange) and
the approver decides with decide_margin_change(). A bill-rate change applies from a Monday
on which no submitted, approved or invoiced week sits (RateHistory), so past invoices and P&L
never change.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import HOLDING_STATUSES, AllocationChange, EmployeeAllocation
from app.services import margin_guard_service as margin_guard
from app.services.deployment_readiness_service import EmployeeNotDeployable
from app.services.employee_service import transition_employee_status
from app.services.resource_management_service import (
    log_allocation_conflict,
    mark_employee_on_bench,
    remove_employee_from_bench,
)

logger = logging.getLogger(__name__)

PENDING_MARGIN = "PENDING_MARGIN_APPROVAL"
EDITABLE_FIELDS = ("end_date", "billing_rate_usd_cents", "utilization_pct", "billable")
# timesheet statuses that are past: a rate change never reaches a week in one of these
LOCKED_TIMESHEET_STATUSES = ("SUBMITTED", "APPROVED", "DISPUTED")
MIN_REASON_LENGTH = 5


class EmployeeAlreadyAllocated(Exception):
    pass

class AllocationOverCapacity(Exception):
    """HRMS-0803 BR-0803-01: overlapping allocations summing over 100%
    utilization are blocked, hard -- not just a warning."""

class AllocationNeedsClient(Exception):
    """The job has no client: there is nobody to bill, so nothing to allocate to."""


class ProjectClientMismatch(Exception):
    """The project belongs to a different client than the job."""


class AllocationEditInvalid(ValueError):
    """The edit itself is malformed (no reason, bad dates, a rate change into a billed week)."""


class AllocationNotEditable(Exception):
    """The allocation is not in a state that can be edited or decided (ended, already decided,
    another change awaiting approval)."""


class MarginApprovalForbidden(Exception):
    """The user may not decide this margin approval (level, business unit, or own request)."""


def employment_type_blockers(db: Session, employee: Employee) -> List[dict]:
    """CEO 2026-10-15 employment-type rule at placement: an employee hired from a candidate whose
    type their country never accepts (C2C, 1099, ...) is never placed. UNKNOWN passes here, as at
    interview (it is confirmed before submission); employees not hired through a candidate are on
    payroll by definition."""
    if not employee.candidate_id:
        return []
    from app.models.candidate import Candidate
    from app.services.employment_type_policy import interview_check

    candidate = db.query(Candidate).filter(Candidate.candidateID == employee.candidate_id).first()
    if candidate is None:
        return []
    result = interview_check(candidate)
    if result["allowed"]:
        return []
    return [{"error": result["error"], "message": result["message"], "violation_type": result["error"]}]


def _assert_placement_rules(db: Session, employee: Employee, demand) -> None:
    """The client-submission gates (Buddy graduated, no open escalation, Core-certified for Core)
    and the employment-type rule: every blocker at once."""
    from app.services.deployment_readiness_service import deployment_blockers

    blockers = deployment_blockers(db, employee, demand) + employment_type_blockers(db, employee)
    if blockers:
        logger.info(f"[Allocation] {employee.id} blocked at job {demand.id}: {[b['error'] for b in blockers]}")
        raise EmployeeNotDeployable(blockers)


def _overlaps(allocation: EmployeeAllocation, start: date, end: Optional[date]) -> bool:
    return (allocation.end_date is None or allocation.end_date >= start) and (end is None or allocation.start_date <= end)


def _assert_capacity(db: Session, employee: Employee, *, start: date, end: Optional[date],
                     utilization_pct: Optional[float], allow_concurrent: bool,
                     exclude_id: Optional[str] = None) -> None:
    """One active (or awaiting-approval) allocation at a time unless concurrent; concurrent ones
    whose dates overlap may not sum over 100%."""
    query = db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == employee.id,
                                                EmployeeAllocation.status.in_(HOLDING_STATUSES))
    if exclude_id is not None:
        query = query.filter(EmployeeAllocation.id != exclude_id)
    holding = query.all()
    if not allow_concurrent:
        if holding:
            raise EmployeeAlreadyAllocated(
                f"Employee {employee.id} already has an active allocation ({holding[0].id}) -- "
                f"end it before creating a new one."
            )
        return
    overlapping = [a for a in holding if _overlaps(a, start, end)]
    overlapping_total = sum(float(a.utilization_pct or 100) for a in overlapping)
    new_pct = float(utilization_pct or 100)
    if overlapping_total + new_pct > 100:
        log_allocation_conflict(
            db, employee,
            conflicting_allocation_ids=[a.id for a in overlapping],
            attempted_utilization_pct=new_pct,
            existing_utilization_pct=overlapping_total,
        )
        raise AllocationOverCapacity(
            f"Employee {employee.id} already has {overlapping_total:.0f}% overlapping "
            f"allocation -- adding {new_pct:.0f}% would exceed 100%."
        )


def _jsonable(values: Dict) -> Dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in values.items()}


def _from_json(values: Dict) -> Dict:
    out = dict(values)
    if out.get("end_date"):
        out["end_date"] = date.fromisoformat(out["end_date"])
    return out


def _margin_columns(result: "margin_guard.MarginResult") -> Dict:
    data = result.as_dict()
    return {k: data[k] for k in ("margin_pct", "margin_check", "loaded_hourly_cost_usd_cents", "margin_policy_id",
                                 "min_margin_pct", "hard_floor_pct")}


def _employee_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def approval_link(allocation_id: str) -> str:
    return f"/employees?tab=allocations&allocation={allocation_id}"


def _request_approval(db: Session, allocation: EmployeeAllocation, change: AllocationChange, employee: Employee,
                      demand, result: "margin_guard.MarginResult") -> None:
    """Route the approval to the BU's head or partner and give them a task that opens the allocation."""
    from app.models.client import Client
    from app.services.task_service import create_task

    level = result.approval_level
    bu_id = margin_guard.revenue_business_unit(db, client_id=allocation.client_id, demand=demand, employee=employee)
    approver = margin_guard.route_approver(db, level, bu_id=bu_id, client_id=allocation.client_id,
                                           employee=employee, exclude_user_id=change.changed_by_user_id)
    if approver is None:
        logger.warning(f"[MarginGuard] allocation {allocation.id}: no {level} approver for BU {bu_id}; "
                       "task left unassigned on the org-wide task board")
    client = db.query(Client).filter(Client.id == allocation.client_id).first()
    what = "placement" if change.change_type == "CREATE" else "allocation change"
    keeps = " (the current terms continue meanwhile)" if change.change_type == "EDIT" else ""
    task = create_task(
        db, title=f"Approve margin: {_employee_name(employee)} at {client.company_name if client else allocation.client_id}",
        description=(f"{result.message} The {what} waits for your decision; until then no timesheet or invoice "
                     f"is produced on the new terms{keeps}. Reason given: {change.reason}"),
        priority="HIGH", tenant_id=allocation.tenant_id, assigned_to_user_id=approver,
        created_by_user_id=change.changed_by_user_id, category="MARGIN_APPROVAL",
        visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if approver else "ORG_WIDE",
        due_date=datetime.utcnow() + timedelta(days=settings.MARGIN_APPROVAL_TASK_DUE_DAYS),
        link=approval_link(allocation.id),
    )
    change.approval_level, change.approver_user_id, change.task_id = level, approver, task.id


def _place_employee(db: Session, employee: Employee, demand_id: str, changed_by: Optional[str]) -> None:
    # SPECIALITY_READY is the bench after Buddy graduation: leaving it for a client is the same move
    if employee.status in ("BENCH", "ACTIVE", "SPECIALITY_READY"):
        was_on_bench = employee.status in ("BENCH", "SPECIALITY_READY")
        transition_employee_status(
            db, employee, "ALLOCATED",
            reason=f"Allocated to demand {demand_id}", changed_by=changed_by,
        )
        if was_on_bench:
            remove_employee_from_bench(db, employee)


def apply_margin_guard(db: Session, allocation: EmployeeAllocation, employee: Employee, demand, *,
                       changed_by: Optional[str], reason: str, existing_placement: bool = False) -> bool:
    """The margin guard on a new allocation (status ACTIVE, not yet placed): records the CREATE
    history row with the check and, when the floor needs an approval, holds the allocation
    PENDING_MARGIN_APPROVAL with an approval task. Returns True when held. Every path that
    creates a placement calls this (allocate_employee_to_project, Core Pull)."""
    result = margin_guard.evaluate(db, tenant_id=allocation.tenant_id, employee=employee,
                                   project_id=allocation.project_id, client_id=allocation.client_id,
                                   role=allocation.role, bill_rate_usd_cents=allocation.billing_rate_usd_cents,
                                   billable=bool(allocation.billable), on=allocation.start_date)
    held = result.approval_level is not None and not existing_placement
    allocation.margin_pct, allocation.margin_check = result.as_dict()["margin_pct"], result.check
    if held:
        allocation.status = PENDING_MARGIN
    db.flush()
    values = {"start_date": allocation.start_date, "end_date": allocation.end_date,
              "billing_rate_usd_cents": allocation.billing_rate_usd_cents,
              "utilization_pct": float(allocation.utilization_pct) if allocation.utilization_pct is not None else None,
              "billable": bool(allocation.billable), "demand_id": allocation.demand_id, "role": allocation.role}
    change = AllocationChange(
        tenant_id=allocation.tenant_id, allocation_id=allocation.id, change_type="CREATE",
        status="PENDING_APPROVAL" if held else "APPLIED", new_values=_jsonable(values),
        effective_from=allocation.start_date, reason=reason, changed_by_user_id=changed_by, **_margin_columns(result),
    )
    db.add(change)
    db.flush()
    if held:
        _request_approval(db, allocation, change, employee, demand, result)
        logger.info(f"[MarginGuard] allocation {allocation.id} held for {result.approval_level} approval: {result.check}")
    return held


def allocate_employee_to_project(
    db: Session,
    *,
    tenant_id: Optional[int],
    employee: Employee,
    demand: Demand,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    utilization_pct: Optional[float] = None,
    client_reporting_manager_contact_id: Optional[str] = None,
    timesheet_approver_email: Optional[str] = None,
    billing_rate_usd_cents: Optional[int] = None,
    changed_by: Optional[str] = None,
    project=None,
    role: Optional[str] = None,
    allow_concurrent: bool = False,
    billable: Optional[bool] = None,
    existing_placement: bool = False,
    reason: Optional[str] = None,
) -> EmployeeAllocation:
    """
    allow_concurrent=False (default, unchanged from before HRMS-0803
    existed) preserves the original single-active-allocation-at-a-time
    behavior -- HRMS-0901 itself calls multi-allocation support "future
    scope," so nothing that depended on that invariant breaks.

    allow_concurrent=True is HRMS-0803's real behavior: multiple ACTIVE
    allocations are permitted, but the sum of utilization_pct across
    every ACTIVE allocation whose date range overlaps this one must not
    exceed 100 -- checked here, hard-blocked, not a soft warning.

    Margin guard: a placement below the rate card's floor is created PENDING_MARGIN_APPROVAL
    (the employee stays on the bench, no timesheets) with an approval task. existing_placement=
    True records a placement that already runs (the employee import of existing staff): its
    margin is checked and recorded, never held -- existing placements are not blocked
    retroactively.
    """
    if not demand.client_id:
        raise AllocationNeedsClient(
            f"Job {demand.id} has no client. Set the client on the job before allocating anyone to it."
        )
    # Buddy graduated, no open escalation, Core-certified for a Core client (CEO 2026-10-14), and
    # the employment-type rule: the same gates as a client submission, on every path that deploys someone
    _assert_placement_rules(db, employee, demand)
    if project is None and getattr(demand, "project_id", None):
        # the job's project, so the allocation's time can be invoiced (an allocation with no
        # project never reaches an invoice)
        from app.models.project import Project

        project = db.query(Project).filter(Project.id == demand.project_id).first()
    if project is not None and project.client_id != demand.client_id:
        raise ProjectClientMismatch(
            f"Project {project.id} belongs to a different client than job {demand.id}."
        )

    start = start_date or date.today()
    if end_date is not None and end_date < start:
        raise AllocationEditInvalid("The end date is before the start date.")
    _assert_capacity(db, employee, start=start, end=end_date, utilization_pct=utilization_pct,
                     allow_concurrent=allow_concurrent)

    rate = billing_rate_usd_cents or demand.billing_rate_usd_cents
    is_billable = billable if billable is not None else (bool(project.is_billable) if project is not None else True)
    allocation = EmployeeAllocation(
        tenant_id=tenant_id, employee_id=employee.id, demand_id=demand.id, client_id=demand.client_id,
        project_id=project.id if project else None, role=role,
        start_date=start, end_date=end_date, utilization_pct=utilization_pct,
        client_reporting_manager_contact_id=client_reporting_manager_contact_id,
        timesheet_approver_email=timesheet_approver_email,
        billing_rate_usd_cents=rate,
        # S-358/HRMS-0519: denormalized from the project at allocation-
        # creation time -- "who is at PwC right now" without a join.
        si_partner=project.si_partner if project else None,
        # client projects are billable, internal ones are not, unless the allocation says otherwise
        billable=is_billable,
    )
    db.add(allocation)
    held = apply_margin_guard(
        db, allocation, employee, demand, changed_by=changed_by, existing_placement=existing_placement,
        reason=reason or ("Existing placement recorded by import" if existing_placement else "Placement"))
    if not held:
        _place_employee(db, employee, demand.id, changed_by)
    db.flush()
    from app.services.bench_service import sync_billing_classification

    sync_billing_classification(db, employee)
    return allocation


# --------------------------------------------------------------------------- bill-rate history

class RateHistory:
    """The bill rate of each allocation on a day: applied EDIT changes of billing_rate_usd_cents,
    each from its effective_from (always a Monday). Before the first change, the rate it replaced;
    no change = the allocation's rate. Loaded once for a batch of allocations."""

    def __init__(self, db: Session, allocation_ids):
        self._changes: Dict[str, List[Tuple[date, Optional[int], Optional[int]]]] = {}
        ids = list({a for a in allocation_ids if a})
        if not ids:
            return
        rows = (db.query(AllocationChange)
                .filter(AllocationChange.allocation_id.in_(ids), AllocationChange.change_type == "EDIT",
                        AllocationChange.status == "APPLIED")
                .order_by(AllocationChange.effective_from, AllocationChange.changed_at).all())
        for row in rows:
            if "billing_rate_usd_cents" not in (row.new_values or {}):
                continue
            self._changes.setdefault(row.allocation_id, []).append(
                (row.effective_from, (row.old_values or {}).get("billing_rate_usd_cents"),
                 row.new_values["billing_rate_usd_cents"]))

    def rate(self, allocation: EmployeeAllocation, day: date) -> Optional[int]:
        changes = self._changes.get(allocation.id)
        if not changes:
            return allocation.billing_rate_usd_cents
        rate = changes[0][1]
        for effective_from, _, new in changes:
            if effective_from is not None and effective_from <= day:
                rate = new
        return rate


# --------------------------------------------------------------------------- edit

def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _locked_weeks(db: Session, allocation: EmployeeAllocation) -> List[date]:
    """Week starts of this allocation's submitted, approved, disputed or invoiced timesheets."""
    from app.models.invoice import InvoiceLineItem
    from app.models.timesheet import Timesheet

    locked = {w for (w,) in db.query(Timesheet.week_starting_date).filter(
        Timesheet.allocation_id == allocation.id, Timesheet.status.in_(LOCKED_TIMESHEET_STATUSES))}
    invoiced = {w for (w,) in db.query(Timesheet.week_starting_date)
                .join(InvoiceLineItem, InvoiceLineItem.timesheet_id == Timesheet.id)
                .filter(Timesheet.allocation_id == allocation.id)}
    return sorted(locked | invoiced)


def _last_worked_day(db: Session, allocation: EmployeeAllocation) -> Optional[date]:
    """The latest day with hours on a submitted / approved / disputed timesheet of this allocation."""
    from sqlalchemy import func

    from app.models.timesheet import Timesheet, TimesheetEntry

    return db.query(func.max(TimesheetEntry.entry_date)).join(
        Timesheet, Timesheet.id == TimesheetEntry.timesheet_id).filter(
        Timesheet.allocation_id == allocation.id, Timesheet.status.in_(LOCKED_TIMESHEET_STATUSES),
        TimesheetEntry.hours > 0).scalar()


def default_rate_effective_from(db: Session, allocation: EmployeeAllocation, today: Optional[date] = None) -> date:
    """The first Monday a new rate can apply: this week, or the week after the last billed one."""
    candidate = max(_monday(today or date.today()), _monday(allocation.start_date))
    weeks = _locked_weeks(db, allocation)
    if weeks and weeks[-1] >= candidate:
        candidate = weeks[-1] + timedelta(days=7)
    return candidate


def _is_reduction_only(old: Dict, new: Dict) -> bool:
    """Only an earlier end, a lower utilization or billable turned off: nothing is deployed."""
    for key, value in new.items():
        before = old.get(key)
        if key == "end_date":
            if value is None or before is None or value > before:
                return False
        elif key == "utilization_pct":
            if float(value) > float(before if before is not None else 100):
                return False
        elif key == "billable":
            if value:
                return False
        else:
            return False
    return True


def _validate_edit(db: Session, allocation: EmployeeAllocation, new: Dict,
                   effective_from: Optional[date]) -> Optional[date]:
    """Checks the edit itself; returns the rate's effective Monday when the rate changes."""
    if new.get("end_date") is not None:
        end = new["end_date"]
        if end < allocation.start_date:
            raise AllocationEditInvalid("The end date is before the allocation's start date.")
        worked = _last_worked_day(db, allocation)
        if worked is not None and end < worked:
            raise AllocationEditInvalid(f"Time is already submitted up to {worked}; the end date cannot be before it "
                                        "(past timesheets are never rewritten).")
    if "utilization_pct" in new and not (0 < float(new["utilization_pct"]) <= 100):
        raise AllocationEditInvalid("Utilization must be above 0 and at most 100%.")
    if "billing_rate_usd_cents" not in new:
        return None
    if new["billing_rate_usd_cents"] <= 0:
        raise AllocationEditInvalid("The bill rate must be above zero.")
    effective_from = effective_from or default_rate_effective_from(db, allocation)
    if effective_from.weekday() != 0:
        raise AllocationEditInvalid("A new bill rate starts on a Monday (timesheets are weekly).")
    if effective_from < _monday(allocation.start_date):
        raise AllocationEditInvalid("A new bill rate cannot start before the allocation does.")
    billed = [w for w in _locked_weeks(db, allocation) if w >= effective_from]
    if billed:
        raise AllocationEditInvalid(
            f"The week of {billed[-1]} is already submitted, approved or invoiced at the current rate; "
            f"the new rate can start on {billed[-1] + timedelta(days=7)} at the earliest.")
    return effective_from


def _run_edit_rules(db: Session, allocation: EmployeeAllocation, employee: Employee, demand, proposed: Dict,
                    effective_from: Optional[date]):
    """Placement rules + capacity on the proposed values; returns the margin result."""
    _assert_placement_rules(db, employee, demand)
    _assert_capacity(db, employee, start=allocation.start_date, end=proposed["end_date"],
                     utilization_pct=proposed["utilization_pct"], allow_concurrent=True,
                     exclude_id=allocation.id)
    on = effective_from or max(date.today(), allocation.start_date)
    return margin_guard.evaluate(db, tenant_id=allocation.tenant_id, employee=employee,
                                 project_id=allocation.project_id, client_id=allocation.client_id,
                                 role=allocation.role, bill_rate_usd_cents=proposed["billing_rate_usd_cents"],
                                 billable=bool(proposed["billable"]), on=on)


def _apply(allocation: EmployeeAllocation, new: Dict) -> None:
    extended = "end_date" in new and (new["end_date"] is None or allocation.end_date is None
                                      or new["end_date"] > allocation.end_date)
    for key, value in new.items():
        setattr(allocation, key, value)
    if extended:
        # a new term: its renewal conversation starts over (alerts follow the new end date)
        allocation.renewal_status = "NOT_STARTED"


def _current_terms(allocation: EmployeeAllocation) -> Dict:
    current = {key: getattr(allocation, key) for key in EDITABLE_FIELDS}
    if current["utilization_pct"] is not None:
        current["utilization_pct"] = float(current["utilization_pct"])
    return current


def edit_allocation(
    db: Session, allocation: EmployeeAllocation, *, changes: Dict, reason: str,
    effective_from: Optional[date] = None, changed_by: Optional[str] = None,
) -> AllocationChange:
    """PATCH /allocations/{id}. changes: any of EDITABLE_FIELDS. Returns the history row: APPLIED,
    or PENDING_APPROVAL when the new terms are below the margin floor (the allocation keeps its
    current terms until the approver decides)."""
    if allocation.status != "ACTIVE":
        raise AllocationNotEditable(f"Only an active allocation can be edited (this one is {allocation.status}).")
    if not reason or len(reason.strip()) < MIN_REASON_LENGTH:
        raise AllocationEditInvalid("Give the reason for the change (a sentence: it is kept in the history).")
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise AllocationEditInvalid(f"These fields cannot be edited here: {sorted(unknown)}")
    pending = db.query(AllocationChange.id).filter(AllocationChange.allocation_id == allocation.id,
                                                   AllocationChange.status == "PENDING_APPROVAL").first()
    if pending is not None:
        raise AllocationNotEditable("A change to this allocation is waiting for margin approval; it must be "
                                    "approved or rejected first.")
    current = _current_terms(allocation)
    new = {}
    for key, value in changes.items():
        if key == "utilization_pct" and value is not None:
            value = float(value)
        if key == "billable":
            value = bool(value)
        if value != current[key]:
            new[key] = value
    if not new:
        raise AllocationEditInvalid("Nothing to change: the values are the allocation's current ones.")
    if "utilization_pct" in new and new["utilization_pct"] is None:
        raise AllocationEditInvalid("Utilization cannot be cleared.")
    if "billing_rate_usd_cents" in new and new["billing_rate_usd_cents"] is None:
        raise AllocationEditInvalid("The bill rate cannot be cleared.")
    effective_from = _validate_edit(db, allocation, new, effective_from)
    old = {key: current[key] for key in new}

    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).one()
    demand = db.query(Demand).filter(Demand.id == allocation.demand_id).one()
    result = None
    if not _is_reduction_only(old, new):
        result = _run_edit_rules(db, allocation, employee, demand, {**current, **new}, effective_from)
    held = result is not None and result.approval_level is not None

    change = AllocationChange(
        tenant_id=allocation.tenant_id, allocation_id=allocation.id, change_type="EDIT",
        status="PENDING_APPROVAL" if held else "APPLIED", old_values=_jsonable(old), new_values=_jsonable(new),
        effective_from=effective_from, reason=reason.strip(), changed_by_user_id=changed_by,
        **(_margin_columns(result) if result is not None else {}),
    )
    db.add(change)
    db.flush()
    if held:
        _request_approval(db, allocation, change, employee, demand, result)
    else:
        _apply(allocation, new)
        if result is not None:
            allocation.margin_pct, allocation.margin_check = change.margin_pct, change.margin_check
        if "billable" in new:
            from app.services.bench_service import sync_billing_classification

            sync_billing_classification(db, employee)
    db.flush()
    logger.info(f"[Allocation] {allocation.id} edit {change.status} by {changed_by}: {change.new_values}")
    return change


# --------------------------------------------------------------------------- margin decisions

def decision_guard(db: Session, change: AllocationChange, user) -> EmployeeAllocation:
    """The change's allocation, when the change is pending and the user may decide it."""
    if change.status != "PENDING_APPROVAL":
        raise AllocationNotEditable("This change has already been decided.")
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == change.allocation_id).one()
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).one()
    demand = db.query(Demand).filter(Demand.id == allocation.demand_id).first()
    bu_id = margin_guard.revenue_business_unit(db, client_id=allocation.client_id, demand=demand, employee=employee)
    why_not = margin_guard.may_decide(db, user, approval_level=change.approval_level or margin_guard.BU_HEAD,
                                      bu_id=bu_id, requested_by=change.changed_by_user_id)
    if why_not:
        raise MarginApprovalForbidden(why_not)
    return allocation


def _claim(db: Session, change: AllocationChange, status: str, user, reason: str) -> None:
    """Compare-and-set PENDING_APPROVAL -> status: two approvers cannot both decide."""
    changed = db.execute(
        update(AllocationChange)
        .where(AllocationChange.id == change.id, AllocationChange.status == "PENDING_APPROVAL")
        .values(status=status, decided_by_user_id=user.UserID, decided_at=datetime.utcnow(), decision_reason=reason)
    ).rowcount
    if not changed:
        raise AllocationNotEditable("This change has already been decided.")
    db.refresh(change)


def decide_margin_change(db: Session, change: AllocationChange, user, *, approve: bool,
                         reason: str) -> AllocationChange:
    """The approver's decision. Approving re-runs every placement rule on the held values (time
    has passed: an escalation or another allocation may have appeared) and then applies them:
    a held placement becomes ACTIVE and moves the employee off the bench; a held edit changes
    the allocation. Rejecting leaves an edit's allocation as it was and marks a held placement
    MARGIN_REJECTED. The approval task is completed either way."""
    from app.models.task import Task

    if not reason or len(reason.strip()) < MIN_REASON_LENGTH:
        raise AllocationEditInvalid("Give the reason for the decision (a sentence: it is kept in the history).")
    allocation = decision_guard(db, change, user)
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).one()
    demand = db.query(Demand).filter(Demand.id == allocation.demand_id).one()
    if approve and change.change_type == "CREATE":
        _assert_placement_rules(db, employee, demand)
        _assert_capacity(db, employee, start=allocation.start_date, end=allocation.end_date,
                         utilization_pct=allocation.utilization_pct, allow_concurrent=True,
                         exclude_id=allocation.id)
    elif approve:
        if allocation.status != "ACTIVE":
            raise AllocationNotEditable(f"The allocation is {allocation.status} now; reject this change.")
        if "billing_rate_usd_cents" in change.new_values:
            billed = [w for w in _locked_weeks(db, allocation) if w >= change.effective_from]
            if billed:
                raise AllocationNotEditable(
                    f"The week of {billed[-1]} was billed at the current rate while this change waited; "
                    "reject it and request the change again from a later Monday.")
        _run_edit_rules(db, allocation, employee, demand, {**_current_terms(allocation), **_from_json(change.new_values)},
                        change.effective_from)
    _claim(db, change, "APPLIED" if approve else "REJECTED", user, reason.strip())
    if change.change_type == "CREATE":
        if approve:
            allocation.status = "ACTIVE"
            _place_employee(db, employee, demand.id, user.UserID)
        else:
            allocation.status = "MARGIN_REJECTED"
    elif approve:
        _apply(allocation, _from_json(change.new_values))
        allocation.margin_pct, allocation.margin_check = change.margin_pct, change.margin_check
    if change.task_id:
        db.query(Task).filter(Task.id == change.task_id, Task.status.notin_(("COMPLETED", "CANCELLED"))) \
            .update({Task.status: "COMPLETED", Task.completed_at: datetime.utcnow()}, synchronize_session=False)
    db.flush()
    from app.services.bench_service import sync_billing_classification

    sync_billing_classification(db, employee)
    logger.info(f"[MarginGuard] change {change.id} on {allocation.id} {'approved' if approve else 'rejected'} "
                f"by {user.UserID}")
    return change


def end_allocation(
    db: Session,
    allocation: EmployeeAllocation,
    employee: Employee,
    *,
    end_date: Optional[date] = None,
    changed_by: Optional[str] = None,
) -> EmployeeAllocation:
    """End an active allocation. A placement still awaiting margin approval is decided (approved
    or rejected), never ended; a change waiting on an active allocation is withdrawn with it."""
    from app.models.task import Task

    if allocation.status != "ACTIVE":
        raise AllocationNotEditable(f"Only an active allocation can be ended (this one is {allocation.status}).")
    for change in db.query(AllocationChange).filter(AllocationChange.allocation_id == allocation.id,
                                                    AllocationChange.status == "PENDING_APPROVAL").all():
        change.status, change.decided_by_user_id, change.decided_at = "REJECTED", changed_by, datetime.utcnow()
        change.decision_reason = "Withdrawn: the allocation was ended."
        if change.task_id:
            db.query(Task).filter(Task.id == change.task_id, Task.status.notin_(("COMPLETED", "CANCELLED"))) \
                .update({Task.status: "CANCELLED"}, synchronize_session=False)
    allocation.status = "ENDED"
    allocation.end_date = end_date or date.today()
    db.add(allocation)

    if employee.status == "ALLOCATED":
        # Part B item 1: bench only when there's genuinely no immediate
        # next allocation -- relevant when allow_concurrent=True let this
        # employee hold more than one ACTIVE allocation at once; ending
        # just one of several shouldn't bench them (status OR bench_pool)
        # while another is still live.
        # Exclude this allocation by id: sessions don't autoflush, so the database still has
        # it ACTIVE and it would always count as "another" live allocation.
        still_has_active = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "ACTIVE",
            EmployeeAllocation.id != allocation.id,
        ).first()
        if not still_has_active:
            if employee.is_billable:
                transition_employee_status(
                    db, employee, "BENCH",
                    reason=f"Allocation {allocation.id} ended", changed_by=changed_by,
                )
                mark_employee_on_bench(db, employee)
            else:  # internal staff are never bench
                transition_employee_status(db, employee, "ACTIVE", reason=f"Allocation {allocation.id} ended",
                                           changed_by=changed_by)
    db.flush()
    from app.services.bench_service import sync_billing_classification

    sync_billing_classification(db, employee)
    return allocation
