"""Core certification (CEO 2026-10-14). Employee.core_certified is the one meaning of "Core-
certified" in the system: it gates Core (direct client) jobs (deployment_readiness_service) and
is what reports count. It is set only by the employee's BU Head approving a request:

1. Buddy Program GRADUATED (Employee.buddy_program_status, as deployment_readiness_service);
2. CORE_CERT_BILLABLE_DAYS approved billable days on Staff Aug with no escalation in them: the
   distinct entry dates of BILLABLE entries (hours > 0) on APPROVED timesheets whose allocation's
   delivery line (project engine, else client line type) is SPECIALITY, counted only after the
   latest escalation ever raised: entry_date > raised_at.date(), so an escalation, resolved or
   not, restarts the count and a same-day entry never counts whatever the timezone. Timesheets
   booked to a task with no allocation carry no client, so they never count;
3. the daily sweep (run_daily_sweep) raises one request and an approval task for the BU Head of
   the employee's business unit in their company; the head approves, or rejects through a short
   Flash discussion (reject_chat) that turns the reason into follow-up tasks.

Who decides: the request's BU Head, or anyone who leads that business unit (its Partner or a
head in another company) -- so a request never waits on one absent person. No super-user
bypass (CEO 2026-10-11). An escalation raised after certification does not revoke it (the
rules make none; revoking would also break ck_core_requires_certification for people on Core).
"""
import copy
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.models.core_certification import CoreCertificationRequest
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation
from app.models.project import Project
from app.models.task import Task
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Users
from app.services.deployment_readiness_service import DEPLOYABLE_BUDDY_STATUS

logger = logging.getLogger(__name__)

STAFF_AUG = "SPECIALITY"
NOT_HEADCOUNT = ("EXITED", "PRE_JOINING")
CLOSED_TASK_STATUSES = ("COMPLETED", "CANCELLED")
REVIEW_PATH = "/workforce/core-certification"


class CertificationError(Exception):
    """A decision that cannot be made (not pending, not eligible any more, not the decider)."""

    def __init__(self, message: str, status_code: int = 409):
        self.status_code = status_code
        super().__init__(message)


# --------------------------------------------------------------------------- eligibility

def billable_days(db: Session, employee_ids: List[str]) -> Dict[str, Tuple[int, Optional[date]]]:
    """{employee_id: (qualifying days, counted_from)} in four queries for any number of people."""
    if not employee_ids:
        return {}
    latest = dict(db.query(EmployeeEscalation.employee_id, func.max(EmployeeEscalation.raised_at))
                  .filter(EmployeeEscalation.employee_id.in_(employee_ids))
                  .group_by(EmployeeEscalation.employee_id).all())
    rows = (
        db.query(Timesheet.employee_id, TimesheetEntry.entry_date, EmployeeAllocation.project_id,
                 EmployeeAllocation.client_id)
        .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .join(EmployeeAllocation, EmployeeAllocation.id == Timesheet.allocation_id)
        .filter(Timesheet.employee_id.in_(employee_ids), Timesheet.status == "APPROVED",
                TimesheetEntry.entry_type == "BILLABLE", TimesheetEntry.hours > 0)
        .all()
    )
    project_ids = {r.project_id for r in rows if r.project_id}
    client_ids = {r.client_id for r in rows if r.client_id}
    engines = dict(db.query(Project.id, Project.delivery_engine).filter(Project.id.in_(project_ids)).all()) \
        if project_ids else {}
    lines = dict(db.query(Client.id, Client.line_type).filter(Client.id.in_(client_ids)).all()) if client_ids else {}
    days = defaultdict(set)
    for r in rows:
        line = engines.get(r.project_id) or lines.get(r.client_id)
        cutoff = latest.get(r.employee_id)
        if line == STAFF_AUG and (cutoff is None or r.entry_date > cutoff.date()):
            days[r.employee_id].add(r.entry_date)
    out = {}
    for employee_id in employee_ids:
        cutoff = latest.get(employee_id)
        out[employee_id] = (len(days[employee_id]), cutoff.date() + timedelta(days=1) if cutoff else None)
    return out


def eligibility(db: Session, employee: Employee, counted: Optional[Tuple[int, Optional[date]]] = None) -> Dict:
    """{"eligible", "billable_days", "required_days", "counted_from", "reasons"}."""
    days, counted_from = counted or billable_days(db, [employee.id])[employee.id]
    reasons = []
    if employee.core_certified:
        reasons.append("Already Core-certified.")
    if employee.buddy_program_status != DEPLOYABLE_BUDDY_STATUS:
        reasons.append(f"Buddy Program is {employee.buddy_program_status.replace('_', ' ').lower()}, not graduated.")
    if days < settings.CORE_CERT_BILLABLE_DAYS:
        since = f" since the escalation of {counted_from - timedelta(days=1)}" if counted_from else ""
        reasons.append(f"{days} of {settings.CORE_CERT_BILLABLE_DAYS} approved billable Staff Aug days{since}.")
    return {"eligible": not reasons, "billable_days": days, "required_days": settings.CORE_CERT_BILLABLE_DAYS,
            "counted_from": counted_from, "reasons": reasons}


# --------------------------------------------------------------------------- the daily sweep

def _head_for(db: Session, employee: Employee) -> Optional[str]:
    from app.services.bu_leadership import head_user_id

    return head_user_id(db, employee.bu_id, employee.company_id)


def _employee_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def _follow_ups_done(db: Session, request: CoreCertificationRequest, today: date) -> bool:
    """A rejected request comes back once every follow-up task is closed (completed, cancelled or
    gone) and the longest follow-up period has passed."""
    plan = request.follow_up_plan or []
    longest = max([int(item.get("days") or 0) for item in plan] or [0])
    if request.decided_at and today < request.decided_at.date() + timedelta(days=longest):
        return False
    task_ids = [item["task_id"] for item in plan if item.get("task_id")]
    if not task_ids:
        return True
    still_open = db.query(Task.id).filter(Task.id.in_(task_ids), Task.status.notin_(CLOSED_TASK_STATUSES)).count()
    return still_open == 0


def _approval_task(db: Session, employee: Employee, head_user_id: str, counted: int, tenant_id: int) -> Task:
    from app.services.task_service import create_task

    return create_task(
        db, title=f"Approve Core certification: {_employee_name(employee)}",
        description=(f"{_employee_name(employee)} has graduated the Buddy Program and has {counted} approved "
                     f"billable Staff Aug days with no escalation. Approve or reject at {REVIEW_PATH}."),
        priority="HIGH", tenant_id=tenant_id, assigned_to_user_id=head_user_id,
        due_date=datetime.utcnow() + timedelta(days=settings.CORE_CERT_TASK_DUE_DAYS),
        link=REVIEW_PATH,
    )


def run_daily_sweep(db: Session, today: Optional[date] = None) -> Dict:
    """Raise a request for everyone newly eligible; keep pending requests with the current head.
    Idempotent: a second run the same day finds the pending request (or hits the unique index)."""
    from app.models.tenant import Tenant

    today = today or date.today()
    result = defaultdict(int)
    for (tenant_id,) in db.query(Tenant.id).all():
        _reassign_pending(db, tenant_id, result)
        employees = (db.query(Employee)
                     .filter(Employee.tenant_id == tenant_id, Employee.core_certified.is_(False),
                             Employee.status.notin_(NOT_HEADCOUNT),
                             Employee.buddy_program_status == DEPLOYABLE_BUDDY_STATUS).all())
        counts = billable_days(db, [e.id for e in employees])
        latest_request = {}
        for r in (db.query(CoreCertificationRequest)
                  .filter(CoreCertificationRequest.employee_id.in_([e.id for e in employees]))
                  .order_by(CoreCertificationRequest.created_at).all() if employees else []):
            latest_request[r.employee_id] = r
        for employee in employees:
            check = eligibility(db, employee, counts[employee.id])
            if not check["eligible"]:
                continue
            result["eligible"] += 1
            if employee.core_eligible_from is None:
                employee.core_eligible_from = today
            previous = latest_request.get(employee.id)
            if previous is not None and (previous.status == "PENDING" or (
                    previous.status == "REJECTED" and not _follow_ups_done(db, previous, today))):
                continue
            head = _head_for(db, employee)
            if head is None:
                result["no_bu_head"] += 1
                continue
            try:
                task = _approval_task(db, employee, head, check["billable_days"], tenant_id)
                db.add(CoreCertificationRequest(
                    tenant_id=tenant_id, employee_id=employee.id, bu_head_user_id=head, task_id=task.id,
                    billable_days=check["billable_days"], counted_from=check["counted_from"]))
                db.commit()
                result["requested"] += 1
            except IntegrityError:  # another run raised it first: withdraw this run's task
                db.rollback()
                db.query(Task).filter(Task.id == task.id).update({Task.status: "CANCELLED"})
                db.commit()
                result["already_pending"] += 1
        db.commit()
    logger.info(f"[CoreCertification] sweep {dict(result)}")
    return dict(result)


def _reassign_pending(db: Session, tenant_id: int, result: Dict) -> None:
    """A pending request follows the employee's current BU Head (the head left, or the employee
    moved business unit): the request and its task move to the new head."""
    pending = (db.query(CoreCertificationRequest, Employee)
               .join(Employee, Employee.id == CoreCertificationRequest.employee_id)
               .filter(CoreCertificationRequest.tenant_id == tenant_id,
                       CoreCertificationRequest.status == "PENDING").all())
    for request, employee in pending:
        head = _head_for(db, employee)
        if head is None:
            result["no_bu_head"] += 1
        elif head != request.bu_head_user_id:
            request.bu_head_user_id = head
            if request.task_id:
                db.query(Task).filter(Task.id == request.task_id).update({Task.assigned_to_user_id: head})
            result["reassigned"] += 1
    db.commit()


# --------------------------------------------------------------------------- deciding

def may_decide(db: Session, request: CoreCertificationRequest, user: Users) -> bool:
    if user.UserID == request.bu_head_user_id:
        return True
    from app.services.bu_leadership import led_business_units

    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    return employee is not None and employee.bu_id in led_business_units(db, user)


def _claim(db: Session, request: CoreCertificationRequest, status: str, user: Users, **values) -> None:
    """Compare-and-set PENDING -> status: two clicks or two tabs cannot both decide."""
    changed = db.execute(
        update(CoreCertificationRequest)
        .where(CoreCertificationRequest.id == request.id, CoreCertificationRequest.status == "PENDING")
        .values(status=status, decided_by_user_id=user.UserID, decided_at=datetime.utcnow(), chat_state=None, **values)
    ).rowcount
    if not changed:
        raise CertificationError("This request has already been decided.")
    db.refresh(request)


def _close_task(db: Session, request: CoreCertificationRequest) -> None:
    if request.task_id:
        db.query(Task).filter(Task.id == request.task_id, Task.status.notin_(CLOSED_TASK_STATUSES)) \
            .update({Task.status: "COMPLETED"}, synchronize_session=False)


def _guard(db: Session, request: CoreCertificationRequest, user: Users) -> Employee:
    if request.status != "PENDING":
        raise CertificationError("This request has already been decided.")
    if not may_decide(db, request, user):
        raise CertificationError("Only the BU Head (or another leader of this business unit) can decide.", 403)
    return db.query(Employee).filter(Employee.id == request.employee_id).one()


def approve(db: Session, request: CoreCertificationRequest, user: Users) -> CoreCertificationRequest:
    employee = _guard(db, request, user)
    check = eligibility(db, employee)
    if not check["eligible"]:
        raise CertificationError("No longer eligible: " + " ".join(check["reasons"]))
    _claim(db, request, "APPROVED", user)
    employee.core_certified, employee.core_certified_date = True, date.today()
    _close_task(db, request)
    db.commit()
    logger.info(f"[CoreCertification] {employee.id} certified by {user.UserID} (request {request.id})")
    _notify(db, employee, f"Congratulations: you are now Core-certified (approved by your BU Head on {date.today()}).")
    return request


def close(db: Session, request: CoreCertificationRequest, user: Users) -> CoreCertificationRequest:
    """Close a pending request whose employee is no longer eligible (an escalation, Buddy status)."""
    employee = _guard(db, request, user)
    check = eligibility(db, employee)
    if check["eligible"]:
        raise CertificationError("Still eligible: approve or reject it instead.")
    _claim(db, request, "CLOSED", user, rejection_reason="No longer eligible: " + " ".join(check["reasons"]))
    _close_task(db, request)
    db.commit()
    return request


def _notify(db: Session, employee: Employee, message: str) -> None:
    recipient = db.query(Users).filter(Users.UserID == employee.wros_user_id).first() if employee.wros_user_id else None
    if recipient is None:
        return
    from app.services.notification_service import send_notification

    try:
        send_notification(db, calling_context_tenant_id=employee.tenant_id, recipient=recipient,
                          priority_tier="P2", message=message)
        db.commit()
    except Exception as exc:  # the certification stands; a failed notice is logged, not raised
        db.rollback()
        logger.error(f"[CoreCertification] could not notify {employee.id}: {exc}", exc_info=True)


# --------------------------------------------------------------------------- rejection with Flash

# What Flash offers when asking what to re-check; the BU Head may name anything else.
CRITERIA_SUGGESTIONS = ("client feedback", "technical skills", "Guidewire certification",
                        "communication", "billable consistency", "conduct")
OWNER_WORDS = {"me": "me", "myself": "me", "i": "me", "manager": "manager", "employee": "employee"}
YES = {"yes", "y", "confirm", "ok", "okay", "create", "go", "yes create"}
CANCEL = {"cancel", "stop", "never mind", "nevermind"}


def _parse_items(text: str) -> List[Dict]:
    """'client feedback 30 days, guidewire cert in 45 owner manager' -> criterion, days, owner."""
    items = []
    for part in re.split(r"[;,\n]|\band\b", text):
        part = part.strip(" .")
        if not part:
            continue
        days = re.search(r"(\d+)\s*(?:days?|d)?\b", part)
        owner = re.search(r"\b(me|myself|manager|employee)\b", part, re.IGNORECASE)
        criterion = part
        if days:
            criterion = criterion.replace(days.group(0), " ")
        if owner:
            criterion = re.sub(rf"\b{owner.group(1)}\b", " ", criterion, flags=re.IGNORECASE)
        criterion = re.sub(r"\b(in|within|after|owner|owned by|by|days?)\b|[:=]", " ", criterion, flags=re.IGNORECASE)
        criterion = " ".join(criterion.split())
        if criterion:
            items.append({"criterion": criterion, "days": int(days.group(1)) if days else None,
                          "owner": OWNER_WORDS[owner.group(1).lower()] if owner else None})
    return items


def _owner_user_id(employee: Employee, owner: str, decider: Users) -> Tuple[str, Optional[str]]:
    """(user id, note when falling back to the decider)."""
    if owner == "manager":
        if employee.reporting_manager_user_id:
            return employee.reporting_manager_user_id, None
        return decider.UserID, "no reporting manager is set, so it is yours"
    if owner == "employee":
        if employee.wros_user_id:
            return employee.wros_user_id, None
        return decider.UserID, "the employee has no login, so it is yours"
    return decider.UserID, None


def _next_missing(state: Dict) -> Optional[int]:
    return next((i for i, item in enumerate(state["items"]) if item["days"] is None), None)


def _summary(state: Dict, employee: Employee, decider: Users) -> str:
    lines = []
    for item in state["items"]:
        _, note = _owner_user_id(employee, item["owner"] or "me", decider)
        owner = {"me": "you", "manager": "the reporting manager", "employee": "the employee"}[item["owner"] or "me"]
        lines.append(f"- {item['criterion']}: re-check in {item['days']} days, owner {owner}"
                     + (f" ({note})" if note else ""))
    return ("Here is the plan:\n" + "\n".join(lines) + f"\nReason recorded: \"{state['reason']}\".\n"
            "Create these follow-up tasks? Reply yes, or tell me the criteria again to change them.")


def reject_chat(db: Session, request: CoreCertificationRequest, user: Users, message: Optional[str]) -> Dict:
    """One turn of the rejection discussion. The state lives on the request (server-side); the
    final yes re-checks the request is still pending. Returns {"reply", "done"}."""
    employee = _guard(db, request, user)
    name = _employee_name(employee)
    text = (message or "").strip()
    state = copy.deepcopy(request.chat_state or {})  # a new object, so the JSON change is always saved

    def reply(msg: str, done: bool = False) -> Dict:
        request.chat_state = None if done else state
        db.commit()
        return {"reply": msg, "done": done}

    if text.lower() in CANCEL:
        state = {}
        return reply("Cancelled. The request stays pending.", done=True)
    step = state.get("step")
    if step is not None and not text:  # the page was reloaded: pick up where the discussion stopped
        return reply("Picking up where we left off. " + _current_question(state, name))
    if step is None:
        state = {"step": "reason"}
        return reply(f"Why are you not approving {name}'s Core certification?")
    if step == "reason":
        if len(text) < 5:
            return reply("Please give the reason in a sentence, so it can be acted on.")
        state.update(reason=text, step="criteria")
        return reply("What needs to be checked again before the next review, and in how many days? "
                     f"For example: {CRITERIA_SUGGESTIONS[0]} 30 days, {CRITERIA_SUGGESTIONS[1]} 45 days owner manager. "
                     f"Common ones: {', '.join(CRITERIA_SUGGESTIONS)}. Owners: me (default), manager, employee.")
    if step == "criteria":
        items = _parse_items(text)
        if not items:
            return reply("Name at least one thing to re-check (e.g. client feedback 30 days).")
        state.update(items=items, step="details")
    elif step == "details":
        index = _next_missing(state)
        days = re.search(r"\d+", text)
        owner = re.search(r"\b(me|myself|manager|employee)\b", text, re.IGNORECASE)
        if index is not None:
            if not days:
                return reply(f"How many days until '{state['items'][index]['criterion']}' is re-checked?")
            state["items"][index]["days"] = int(days.group(0))
            if owner and not state["items"][index]["owner"]:
                state["items"][index]["owner"] = OWNER_WORDS[owner.group(1).lower()]
    elif step == "confirm":
        if text.lower() in YES:
            return _finalize(db, request, employee, user, state)
        items = _parse_items(text)
        if not items:
            return reply("Reply yes to create the tasks, or name the criteria again to change them.")
        state.update(items=items, step="details")
    index = _next_missing(state)
    if index is not None:
        return reply(f"In how many days should '{state['items'][index]['criterion']}' be re-checked, "
                     "and who owns it (me, manager or employee)?")
    state["step"] = "confirm"
    return reply(_summary(state, employee, user))


def _current_question(state: Dict, name: str) -> str:
    step = state.get("step")
    if step == "reason":
        return f"Why are you not approving {name}'s Core certification?"
    recap = f"Reason: \"{state['reason']}\". "
    if step == "criteria":
        return recap + ("What needs to be checked again before the next review, and in how many days "
                        "(e.g. client feedback 30 days owner manager)?")
    index = _next_missing(state) if state.get("items") else None
    if step == "details" and index is not None:
        return recap + (f"In how many days should '{state['items'][index]['criterion']}' be re-checked, "
                        "and who owns it (me, manager or employee)?")
    criteria = ", ".join(f"{i['criterion']} ({i['days']} days)" for i in state.get("items", []))
    return recap + f"Planned follow-ups: {criteria}. Reply yes to create them, or name the criteria again to change them."


def _finalize(db: Session, request: CoreCertificationRequest, employee: Employee, user: Users, state: Dict) -> Dict:
    from app.services.task_service import create_task

    _claim(db, request, "REJECTED", user, rejection_reason=state["reason"])
    plan = []
    for item in state["items"]:
        owner_id, _ = _owner_user_id(employee, item["owner"] or "me", user)
        task = create_task(
            db, title=f"Core certification follow-up: {item['criterion']} ({_employee_name(employee)})",
            description=(f"BU Head did not approve {_employee_name(employee)}'s Core certification: {state['reason']}. "
                         f"Re-check '{item['criterion']}' within {item['days']} days. The next review is raised "
                         "automatically once every follow-up is closed."),
            priority="MEDIUM", tenant_id=request.tenant_id, assigned_to_user_id=owner_id,
            created_by_user_id=user.UserID, due_date=datetime.utcnow() + timedelta(days=item["days"]),
        )
        plan.append({"criterion": item["criterion"], "days": item["days"], "owner_user_id": owner_id,
                     "task_id": task.id})
    request.follow_up_plan = plan
    _close_task(db, request)
    db.commit()
    logger.info(f"[CoreCertification] {employee.id} rejected by {user.UserID}: {len(plan)} follow-up task(s)")
    return {"reply": f"Done. {len(plan)} follow-up task(s) created; {_employee_name(employee)} comes back for "
                     "review automatically once they are all closed.", "done": True}
