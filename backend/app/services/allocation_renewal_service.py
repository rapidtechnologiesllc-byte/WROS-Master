"""Extension / renewal pipeline for placements (CEO 2026-10-23, gap 1).

Every ACTIVE allocation with an end date has a renewal state for its current term:
NOT_STARTED -> IN_DISCUSSION -> EXTENDED (agreed; the new end date follows as an edit) or
ROLLING_OFF (the person comes back to the bench on the end date). Extending the end date
(employee_allocation_service.edit_allocation) starts a new term at NOT_STARTED.

Owner (CEO decision, defaulted to the recommendation): the person set on the allocation; else
the client's account manager (Client.account_manager_user_id, or the account-manager employee's
login); else the BU Head of the BU that owns the revenue (the client's BU, else the job's, else
the employee's), resolved by bu_leadership.head_for_client -- a role-template authority seat,
never a name. effective_owner() reports which of these applied.

The daily job (run_renewal_alerts) gives the owner one task when the end date is
settings.RENEWAL_ALERT_DAYS (60/30/15) days away; never twice for the same allocation, term and
threshold (AllocationRenewalAlert's unique key), and not at all once the renewal is EXTENDED or
ROLLING_OFF. The task opens the allocation's row on Demand vs Bench > Renewals.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import (
    RENEWAL_STATUSES, AllocationChange, AllocationRenewalAlert, EmployeeAllocation,
)
from app.models.user import Users

logger = logging.getLogger(__name__)

SETTLED = ("EXTENDED", "ROLLING_OFF")
RENEWALS_PATH = "/demand-vs-bench"


class RenewalUpdateInvalid(ValueError):
    pass


def alert_thresholds() -> List[int]:
    """settings.RENEWAL_ALERT_DAYS as positive ints, largest first. Misconfigured = fail fast."""
    raw = settings.RENEWAL_ALERT_DAYS or ""
    try:
        days = sorted({int(part) for part in raw.split(",") if part.strip()}, reverse=True)
    except ValueError as exc:
        raise ValueError(f"RENEWAL_ALERT_DAYS must be a comma list of whole days (e.g. 60,30,15), got {raw!r}") from exc
    if not days or any(d <= 0 for d in days):
        raise ValueError(f"RENEWAL_ALERT_DAYS must list positive days (e.g. 60,30,15), got {raw!r}")
    return days


def renewal_link(allocation_id: str) -> str:
    return f"{RENEWALS_PATH}?view=renewals&allocation={allocation_id}"


def _account_manager(db: Session, client: Optional[Client]) -> Optional[str]:
    if client is None:
        return None
    if client.account_manager_user_id:
        return client.account_manager_user_id
    if client.account_manager_employee_id:
        employee = db.query(Employee).filter(Employee.id == client.account_manager_employee_id).first()
        if employee is not None and employee.wros_user_id:
            return employee.wros_user_id
    return None


def effective_owner(db: Session, allocation: EmployeeAllocation, *, client: Optional[Client] = None,
                    employee: Optional[Employee] = None) -> Tuple[Optional[str], Optional[str]]:
    """(user id, source) -- source is SET, ACCOUNT_MANAGER, BU_HEAD or None when nobody resolves."""
    from app.models.demand import Demand
    from app.services.bu_leadership import head_for_client, head_user_id
    from app.services.margin_guard_service import revenue_business_unit

    if allocation.renewal_owner_user_id:
        return allocation.renewal_owner_user_id, "SET"
    client = client or db.query(Client).filter(Client.id == allocation.client_id).first()
    manager = _account_manager(db, client)
    if manager:
        return manager, "ACCOUNT_MANAGER"
    employee = employee or db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    demand = db.query(Demand).filter(Demand.id == allocation.demand_id).first()
    bu_id = revenue_business_unit(db, client_id=allocation.client_id, demand=demand, employee=employee)
    head = head_for_client(db, bu_id, allocation.client_id) or head_user_id(
        db, bu_id, employee.company_id if employee is not None else None)
    if head:
        return head, "BU_HEAD"
    return None, None


def renewal_rows(db: Session, allocations: List[EmployeeAllocation], today: Optional[date] = None) -> List[Dict]:
    """The Renewals tab rows for these allocations."""
    from app.models.demand import Demand

    today = today or date.today()
    employees = {e.id: e for e in db.query(Employee).filter(Employee.id.in_({a.employee_id for a in allocations}))}
    clients = {c.id: c for c in db.query(Client).filter(Client.id.in_({a.client_id for a in allocations}))}
    jobs = {d.id: d for d in db.query(Demand).filter(Demand.id.in_({a.demand_id for a in allocations}))}
    pending = {a for (a,) in db.query(AllocationChange.allocation_id).filter(
        AllocationChange.allocation_id.in_([a.id for a in allocations]),
        AllocationChange.status == "PENDING_APPROVAL")} if allocations else set()
    owners = {}
    rows = []
    for allocation in allocations:
        employee, client = employees.get(allocation.employee_id), clients.get(allocation.client_id)
        owner_id, source = effective_owner(db, allocation, client=client, employee=employee)
        if owner_id and owner_id not in owners:
            user = db.query(Users).filter(Users.UserID == owner_id).first()
            owners[owner_id] = user.UserName if user else None
        job = jobs.get(allocation.demand_id)
        rows.append({
            "allocation_id": allocation.id, "employee_id": allocation.employee_id,
            "employee_name": f"{employee.first_name} {employee.last_name}".strip() if employee else None,
            "client_id": allocation.client_id, "client_name": client.company_name if client else None,
            "job_title": job.job_title if job else allocation.role, "role": allocation.role,
            "start_date": allocation.start_date, "end_date": allocation.end_date,
            "days_left": (allocation.end_date - today).days if allocation.end_date else None,
            "billing_rate_usd_cents": allocation.billing_rate_usd_cents,
            "utilization_pct": float(allocation.utilization_pct) if allocation.utilization_pct is not None else None,
            "renewal_status": allocation.renewal_status, "renewal_note": allocation.renewal_note,
            "renewal_owner_user_id": owner_id, "renewal_owner_name": owners.get(owner_id),
            "renewal_owner_source": source, "renewal_updated_at": allocation.renewal_updated_at,
            "margin_pct": float(allocation.margin_pct) if allocation.margin_pct is not None else None,
            "margin_check": allocation.margin_check, "change_pending_approval": allocation.id in pending,
        })
    return rows


def ending_within(query, days: int, today: Optional[date] = None):
    """ACTIVE allocations whose end date is at most `days` away (already past included: an
    allocation past its end date and still active needs a decision most of all)."""
    today = today or date.today()
    return query.filter(EmployeeAllocation.status == "ACTIVE", EmployeeAllocation.end_date.isnot(None),
                        EmployeeAllocation.end_date <= today + timedelta(days=days)) \
        .order_by(EmployeeAllocation.end_date, EmployeeAllocation.id)


def update_renewal(db: Session, allocation: EmployeeAllocation, *, user: Users, status: Optional[str] = None,
                   owner_user_id: Optional[str] = None, clear_owner: bool = False, note: Optional[str] = None,
                   reason: Optional[str] = None) -> AllocationChange:
    """Set the renewal status / owner / note; one RENEWAL history row with old -> new."""
    if allocation.status != "ACTIVE":
        raise RenewalUpdateInvalid(f"Only an active allocation has a renewal (this one is {allocation.status}).")
    new = {}
    if status is not None:
        if status not in RENEWAL_STATUSES:
            raise RenewalUpdateInvalid(f"Unknown renewal status {status!r}; one of {list(RENEWAL_STATUSES)}.")
        if status != allocation.renewal_status:
            new["renewal_status"] = status
    if clear_owner:
        if allocation.renewal_owner_user_id is not None:
            new["renewal_owner_user_id"] = None
    elif owner_user_id is not None and owner_user_id != allocation.renewal_owner_user_id:
        owner = db.query(Users).filter(Users.UserID == owner_user_id, Users.tenant_id == allocation.tenant_id).first()
        if owner is None:
            raise RenewalUpdateInvalid("The renewal owner must be a user of this organisation.")
        new["renewal_owner_user_id"] = owner.UserID
    if note is not None and note.strip() != (allocation.renewal_note or ""):
        new["renewal_note"] = note.strip() or None
    if not new:
        raise RenewalUpdateInvalid("Nothing to change.")
    old = {key: getattr(allocation, key) for key in new}
    for key, value in new.items():
        setattr(allocation, key, value)
    allocation.renewal_updated_at, allocation.renewal_updated_by = datetime.utcnow(), user.UserID
    change = AllocationChange(
        tenant_id=allocation.tenant_id, allocation_id=allocation.id, change_type="RENEWAL", status="APPLIED",
        old_values=old, new_values=new, changed_by_user_id=user.UserID,
        reason=(reason or "").strip() or new.get("renewal_note") or "Renewal update",
    )
    db.add(change)
    db.flush()
    return change


def _raise_alert(db: Session, allocation: EmployeeAllocation, crossed: List[int], days_left: int) -> Optional[int]:
    """One task for the most urgent threshold crossed; every crossed threshold is marked so none
    of them alerts again for this term. Returns the task id (None if another run got there first)."""
    from app.services.task_service import create_task

    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    client = db.query(Client).filter(Client.id == allocation.client_id).first()
    owner_id, source = effective_owner(db, allocation, client=client, employee=employee)
    name = f"{employee.first_name} {employee.last_name}".strip() if employee else allocation.employee_id
    client_name = client.company_name if client else allocation.client_id
    closest = min(crossed)
    rate = f"${allocation.billing_rate_usd_cents / 100:,.2f}/h" if allocation.billing_rate_usd_cents else "no bill rate"
    try:
        # claim the thresholds first (the unique key): a concurrent run cannot raise the same alert
        with db.begin_nested():
            marks = [AllocationRenewalAlert(tenant_id=allocation.tenant_id, allocation_id=allocation.id,
                                            end_date=allocation.end_date, threshold_days=threshold)
                     for threshold in crossed]
            db.add_all(marks)
            db.flush()
    except IntegrityError:  # another run claimed it first: its task stands
        logger.info(f"[Renewals] allocation {allocation.id}: alert already raised")
        return None
    task = create_task(
        db, title=f"Renewal: {name} at {client_name} ends in {days_left} days",
        description=(f"{name}'s placement at {client_name} ({rate}) ends on {allocation.end_date}. "
                     "Talk to the client: extend (new end date and rate), or mark it rolling off so the "
                     f"bench can plan. Renewal status: {allocation.renewal_status.replace('_', ' ').lower()}."
                     + ("" if owner_id else " No account manager or BU Head is set for this client: "
                                           "set the renewal owner.")),
        priority="HIGH" if closest == min(alert_thresholds()) else "MEDIUM",
        tenant_id=allocation.tenant_id, assigned_to_user_id=owner_id, category="RENEWAL",
        visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if owner_id else "ORG_WIDE",
        due_date=datetime.combine(min(date.today() + timedelta(days=settings.RENEWAL_TASK_DUE_DAYS),
                                      allocation.end_date), datetime.min.time()),
        link=renewal_link(allocation.id),
    )
    for mark in marks:
        if mark.threshold_days == closest:
            mark.task_id = task.id
    db.flush()
    if owner_id is None:
        logger.warning(f"[Renewals] allocation {allocation.id}: no renewal owner (source {source}); task unassigned")
    return task.id


def run_renewal_alerts(db: Session, today: Optional[date] = None) -> Dict:
    """Daily (scheduled job renewal_alerts). Idempotent: thresholds already alerted for an
    allocation's current end date are skipped; a run that misses a day still alerts (the most
    urgent threshold crossed, once)."""
    today = today or date.today()
    thresholds = alert_thresholds()
    horizon = today + timedelta(days=max(thresholds))
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.status == "ACTIVE", EmployeeAllocation.end_date.isnot(None),
        EmployeeAllocation.end_date >= today, EmployeeAllocation.end_date <= horizon,
        EmployeeAllocation.renewal_status.notin_(SETTLED)).all()
    result = {"checked": len(allocations), "alerted": 0, "failed": 0}
    for allocation in allocations:
        days_left = (allocation.end_date - today).days
        done = {t for (t,) in db.query(AllocationRenewalAlert.threshold_days).filter(
            AllocationRenewalAlert.allocation_id == allocation.id,
            AllocationRenewalAlert.end_date == allocation.end_date)}
        crossed = [t for t in thresholds if days_left <= t and t not in done]
        if not crossed:
            continue
        try:
            if _raise_alert(db, allocation, crossed, days_left) is not None:
                result["alerted"] += 1
            db.commit()
        except Exception as exc:  # one bad row must not stop the others; logged and counted
            db.rollback()
            logger.error(f"[Renewals] allocation {allocation.id} failed: {exc}", exc_info=True)
            result["failed"] += 1
    logger.info(f"[Renewals] alerts {result}")
    return result
