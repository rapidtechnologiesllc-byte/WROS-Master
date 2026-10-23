"""Timesheet approval loop (CEO 2026-10-22).

submit   -> a TimesheetReview (revision n, entries snapshotted) routed to the employee's approver:
            reporting manager, else their manager employee's login, else the BU head of their BU in
            their company, else the BU partner. An approval task ("Approve timesheet: <employee>
            week of <date> (<hours>h)") links to the approval view; the approver gets an email,
            a Flash event and a Flash decision chip (flash_brain.decisions).
approve  -> APPROVED (locked; the approved hours flow to invoicing and the P&L as before); the
            approval task COMPLETED with the approver's comment; the employee is told by email
            and Flash. On a resubmission the approver must confirm the earlier rejection is
            addressed (recorded on the review).
reject   -> a reason is required; specific days may be flagged. REJECTED with the reason; the
            approval task COMPLETED with the reason as its comment; a new task for the employee
            ("Resubmit timesheet week of <date>") with the reason and flagged days, linked to
            My Timesheet for that week; email + Flash.
resubmit -> only after a change: the entries differ from the rejected version, or the employee
            answers the rejection in a response comment. Closes their resubmit task and opens a new
            review for the same approver, whose view shows the previous reason, the response and
            the diff against the rejected entries.

Who decides: the routed approver, or someone whose role template grants timesheets edit and
whose business units include the timesheet (app.core.data_scope.timesheet_filter).

Emails and decision chips go out after the caller commits (send_notices)."""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_review import TimesheetReview
from app.models.user import Users

logger = logging.getLogger(__name__)

CLOSED = ("COMPLETED", "CANCELLED")
APPROVAL_PATH = "/timesheet-approvals/{timesheet_id}"
MY_TIMESHEET_PATH = "/my-timesheet?week={week}&allocation={allocation}"


class NoTimesheetApprover(Exception):
    """Nobody to route the timesheet to: set the employee's reporting manager or the BU head."""


class NotTheApprover(Exception):
    pass


class ResubmitNeedsChange(Exception):
    """A rejected timesheet comes back only changed, or with the employee's answer to the reason."""


class AddressedNotConfirmed(Exception):
    """Approving a resubmission needs the approver's confirmation that the rejection is addressed."""


def _name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def resolve_approver(db: Session, employee: Employee) -> Users:
    """Their manager in the org chart -> BU head (their company) -> BU partner."""
    from app.models.business_unit import BusinessUnit
    from app.services.bu_leadership import head_user_id
    from app.services.org_structure_service import manager_user_for

    manager = manager_user_for(db, employee)
    candidates = [manager.UserID if manager else None]
    candidates.append(head_user_id(db, employee.bu_id, employee.company_id))
    unit = db.get(BusinessUnit, employee.bu_id) if employee.bu_id else None
    candidates.append(unit.partner_user_id if unit else None)
    for user_id in candidates:
        if user_id and user_id != employee.wros_user_id:
            user = db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()
            if user is not None:
                return user
    raise NoTimesheetApprover(
        f"Nobody can approve {_name(employee)}'s timesheet: seat them under their reporting manager in the org chart "
        "(Organizational Hierarchy, or the manager on the Employees screen), or seat a BU head for their business unit.")


def snapshot(db: Session, timesheet: Timesheet) -> List[Dict]:
    rows = db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id) \
        .order_by(TimesheetEntry.entry_date).all()
    return [{"entry_date": e.entry_date.isoformat(), "hours": float(e.hours), "entry_type": e.entry_type,
             "notes": e.notes or ""} for e in rows]


def diff(before: List[Dict], after: List[Dict]) -> List[Dict]:
    """Per day: what changed between two snapshots (added, removed, changed hours/type/notes)."""
    old, new = {e["entry_date"]: e for e in before}, {e["entry_date"]: e for e in after}
    out = []
    for day in sorted(set(old) | set(new)):
        a, b = old.get(day), new.get(day)
        if a == b:
            continue
        out.append({"entry_date": day, "before": a, "after": b,
                    "change": "added" if a is None else "removed" if b is None else "changed"})
    return out


def latest_review(db: Session, timesheet: Timesheet) -> Optional[TimesheetReview]:
    return db.query(TimesheetReview).filter(TimesheetReview.timesheet_id == timesheet.id) \
        .order_by(TimesheetReview.revision.desc()).first()


def may_decide(db: Session, review: TimesheetReview, user: Users) -> bool:
    if user.UserID == review.approver_user_id:
        return True
    from app.core import authority
    from app.core.data_scope import timesheet_filter

    if not authority.has_permission(db, user, "timesheets.edit"):
        return False
    return db.query(Timesheet.id).filter(Timesheet.id == review.timesheet_id, Timesheet.tenant_id == user.tenant_id,
                                         timesheet_filter(db, user)).first() is not None


def _comment(db: Session, task_id: Optional[int], author: Users, body: str) -> None:
    if task_id and body:
        db.add(TaskComment(tenant_id=author.tenant_id, task_id=task_id, author_user_id=author.UserID, body=body))


def _close_task(db: Session, task_id: Optional[int]) -> None:
    if task_id:
        task = db.get(Task, task_id)
        if task is not None and task.status not in CLOSED:
            task.status, task.completed_at = "COMPLETED", datetime.utcnow()


def submit_for_approval(db: Session, timesheet: Timesheet, submitted_by: Users, *,
                        response: Optional[str] = None) -> TimesheetReview:
    """Submit (timesheet_service rules) and route it. Raises before any change when it cannot be
    routed or a resubmission has nothing new. The caller commits, then calls send_notices()."""
    from app.services.task_service import create_task
    from app.services.timesheet_service import submit_timesheet

    employee = db.get(Employee, timesheet.employee_id)
    previous = latest_review(db, timesheet)
    current = snapshot(db, timesheet)
    response = (response or "").strip() or None
    if previous is not None and previous.decision == "REJECTED" and current == previous.entries_snapshot and not response:
        raise ResubmitNeedsChange(
            "Nothing changed since the rejection: change the entries, or explain in a response why they are right.")
    approver = resolve_approver(db, employee)
    if timesheet.status == "REJECTED":  # answered without changes: back to DRAFT, reason kept
        from app.services.timesheet_service import reopen_for_editing

        reopen_for_editing(db, timesheet)
    submit_timesheet(db, timesheet)
    revision = (previous.revision + 1) if previous else 1
    hours = float(timesheet.total_hours or 0)
    lines = [f"{_name(employee)} submitted {hours:g} hours for the week of {timesheet.week_starting_date}."]
    if previous is not None and previous.decision == "REJECTED":
        lines.append(f"Revision {revision}. Previously rejected: {previous.decision_note}")
        if response:
            lines.append(f"{_name(employee)}'s response: {response}")
        _close_task(db, previous.resubmit_task_id)
        _comment(db, previous.resubmit_task_id, submitted_by, response or "Resubmitted with changes.")
    task = create_task(
        db, title=f"Approve timesheet: {_name(employee)} week of {timesheet.week_starting_date} ({hours:g}h)",
        description="\n".join(lines), priority="MEDIUM", tenant_id=timesheet.tenant_id,
        assigned_to_user_id=approver.UserID, created_by_user_id=submitted_by.UserID, category="TIMESHEET_APPROVAL",
        due_date=datetime.utcnow() + timedelta(days=2), link=APPROVAL_PATH.format(timesheet_id=timesheet.id))
    review = TimesheetReview(tenant_id=timesheet.tenant_id, timesheet_id=timesheet.id, revision=revision,
                             approver_user_id=approver.UserID, approval_task_id=task.id,
                             submitted_by_user_id=submitted_by.UserID, entries_snapshot=current,
                             employee_response=response)
    db.add(review)
    db.flush()
    _flash(db, approver, f"{task.title}. Open it to approve or reject.", task.link)
    logger.info(f"[TimesheetApproval] {timesheet.id} rev {revision} routed to {approver.UserID} (task {task.id})")
    return review


def approve(db: Session, timesheet: Timesheet, user: Users, *, comment: Optional[str] = None,
            addressed: bool = False) -> TimesheetReview:
    from app.services.timesheet_service import approve_timesheet

    review = _pending_review(db, timesheet, user)
    if review.revision > 1 and not addressed:
        raise AddressedNotConfirmed("Confirm that the earlier rejection is addressed before approving this resubmission.")
    approve_timesheet(db, timesheet, approved_by=user.UserID)
    review.decision, review.decided_by_user_id, review.decided_at = "APPROVED", user.UserID, datetime.utcnow()
    review.decision_note, review.addressed_confirmed = (comment or "").strip() or None, bool(addressed)
    _comment(db, review.approval_task_id, user, f"Approved. {review.decision_note or ''}".strip())
    _close_task(db, review.approval_task_id)
    employee = db.get(Employee, timesheet.employee_id)
    login = db.get(Users, employee.wros_user_id) if employee.wros_user_id else None
    if login is not None:
        _flash(db, login, f"Your timesheet for the week of {timesheet.week_starting_date} was approved by "
                          f"{user.UserName or user.UserEmail}.", "/my-timesheet")
    return review


def reject(db: Session, timesheet: Timesheet, user: Users, *, reason: str,
           flagged_dates: Optional[List[date]] = None) -> TimesheetReview:
    from app.services.task_service import create_task
    from app.services.timesheet_service import reject_timesheet

    review = _pending_review(db, timesheet, user)
    week_end = timesheet.week_starting_date + timedelta(days=6)
    flagged = sorted({d for d in (flagged_dates or [])})
    outside = [d for d in flagged if not timesheet.week_starting_date <= d <= week_end]
    if outside:
        raise ValueError(f"Flagged days {', '.join(map(str, outside))} are outside this week.")
    reject_timesheet(db, timesheet, reason)  # requires the reason (InvalidTimesheetEntry otherwise)
    reason = reason.strip()
    review.decision, review.decided_by_user_id, review.decided_at = "REJECTED", user.UserID, datetime.utcnow()
    review.decision_note, review.flagged_dates = reason, [d.isoformat() for d in flagged]
    _comment(db, review.approval_task_id, user, f"Rejected: {reason}")
    _close_task(db, review.approval_task_id)
    employee = db.get(Employee, timesheet.employee_id)
    flagged_text = f" Days to fix: {', '.join(review.flagged_dates)}." if flagged else ""
    if employee.wros_user_id:
        task = create_task(
            db, title=f"Resubmit timesheet week of {timesheet.week_starting_date}",
            description=f"Rejected by {user.UserName or user.UserEmail}: {reason}.{flagged_text} Change the entries, "
                        "or answer the reason in your response, then submit again.",
            priority="HIGH", tenant_id=timesheet.tenant_id, assigned_to_user_id=employee.wros_user_id,
            created_by_user_id=user.UserID, category="TIMESHEET_RESUBMIT",
            due_date=datetime.utcnow() + timedelta(days=2),
            link=MY_TIMESHEET_PATH.format(week=timesheet.week_starting_date, allocation=timesheet.allocation_id))
        review.resubmit_task_id = task.id
        _flash(db, db.get(Users, employee.wros_user_id),
               f"Your timesheet for the week of {timesheet.week_starting_date} was rejected: {reason}.{flagged_text}",
               task.link)
    else:
        logger.error(f"[TimesheetApproval] {timesheet.id} rejected but employee {employee.id} has no login to tell")
    return review


def _pending_review(db: Session, timesheet: Timesheet, user: Users) -> TimesheetReview:
    review = latest_review(db, timesheet)
    if review is None or review.decision != "PENDING":
        # submitted before routing existed: route it now so the decision is recorded the same way
        from app.services.timesheet_service import InvalidTimesheetTransition

        if timesheet.status != "SUBMITTED":
            raise InvalidTimesheetTransition(f"Cannot decide a timesheet in status '{timesheet.status}'.")
        employee = db.get(Employee, timesheet.employee_id)
        review = TimesheetReview(tenant_id=timesheet.tenant_id, timesheet_id=timesheet.id,
                                 revision=(review.revision + 1) if review else 1,
                                 approver_user_id=resolve_approver(db, employee).UserID,
                                 entries_snapshot=snapshot(db, timesheet))
        db.add(review)
        db.flush()
    if not may_decide(db, review, user):
        raise NotTheApprover("Only the routed approver, or someone with timesheet edit rights on this business "
                             "unit, can decide this timesheet.")
    return review


def _flash(db: Session, user: Users, text: str, link: Optional[str]) -> None:
    from app.services.flash_conversation_service import post_event

    post_event(db, user.UserID, user.tenant_id, text, {"kind": "timesheet_approval", "link": link})


def send_notices(db: Session, review: TimesheetReview) -> None:
    """After commit: the email for what just happened to this review (idempotent per review and
    decision). A failure to queue is raised: the person must hear about it."""
    from app.services.staff_mail_service import queue_staff_email

    timesheet = db.get(Timesheet, review.timesheet_id)
    employee = db.get(Employee, timesheet.employee_id)
    week = timesheet.week_starting_date
    if review.decision == "PENDING":
        approver = db.get(Users, review.approver_user_id)
        paragraphs = [f"{_name(employee)} submitted {float(timesheet.total_hours or 0):g} hours for the week of {week} "
                      "and it is waiting for your approval."]
        if review.revision > 1:
            previous = db.query(TimesheetReview).filter(TimesheetReview.timesheet_id == timesheet.id,
                                                        TimesheetReview.revision == review.revision - 1).first()
            paragraphs.append(f"This is revision {review.revision}. You rejected it before: {previous.decision_note}")
            if review.employee_response:
                paragraphs.append(f"Their response: {review.employee_response}")
        queue_staff_email(approver, key=f"ts-review-{review.id}-pending", subject=f"Approve timesheet: {_name(employee)} week of {week}",
                          paragraphs=paragraphs, link_path=APPROVAL_PATH.format(timesheet_id=timesheet.id),
                          link_label="Review the timesheet")
        return
    login = db.get(Users, employee.wros_user_id) if employee.wros_user_id else None
    if login is None:
        return  # logged at the decision; there is nobody to email
    decider = db.get(Users, review.decided_by_user_id)
    by = decider.UserName or decider.UserEmail
    if review.decision == "APPROVED":
        queue_staff_email(login, key=f"ts-review-{review.id}-approved", subject=f"Timesheet approved: week of {week}",
                          paragraphs=[f"Your timesheet for the week of {week} was approved by {by}."]
                          + ([f"Comment: {review.decision_note}"] if review.decision_note else []),
                          link_path="/my-timesheet", link_label="Open My Timesheet")
    else:
        flagged = f"Days to fix: {', '.join(review.flagged_dates)}." if review.flagged_dates else ""
        queue_staff_email(login, key=f"ts-review-{review.id}-rejected", subject=f"Timesheet rejected: week of {week}",
                          paragraphs=[f"Your timesheet for the week of {week} was rejected by {by}.",
                                      f"Reason: {review.decision_note}", flagged,
                                      "Change the entries, or answer the reason in your response, then submit again."],
                          link_path=MY_TIMESHEET_PATH.format(week=week, allocation=timesheet.allocation_id),
                          link_label="Fix and resubmit")


def review_view(db: Session, timesheet: Timesheet, user: Users) -> Dict:
    """What the approver sees: the entries, this revision, the previous rejection, the employee's
    response and the diff against the rejected version."""
    employee = db.get(Employee, timesheet.employee_id)
    reviews = db.query(TimesheetReview).filter(TimesheetReview.timesheet_id == timesheet.id) \
        .order_by(TimesheetReview.revision).all()
    current = reviews[-1] if reviews else None
    previous = reviews[-2] if len(reviews) > 1 else None
    rejected = previous if previous is not None and previous.decision == "REJECTED" else None
    entries = snapshot(db, timesheet)
    return {
        "timesheet_id": timesheet.id, "employee_id": employee.id, "employee_name": _name(employee),
        "week_starting_date": timesheet.week_starting_date.isoformat(), "status": timesheet.status,
        "total_hours": float(timesheet.total_hours or 0), "entries": entries,
        "revision": current.revision if current else None,
        "decision": current.decision if current else None,
        "approver_user_id": current.approver_user_id if current else None,
        "may_decide": bool(current and current.decision == "PENDING" and may_decide(db, current, user)),
        "requires_addressed_confirmation": bool(current and current.revision > 1),
        "previous_rejection": ({"reason": rejected.decision_note, "flagged_dates": rejected.flagged_dates or [],
                                "decided_at": rejected.decided_at.isoformat() if rejected.decided_at else None}
                               if rejected else None),
        "employee_response": current.employee_response if current else None,
        "changes_since_rejection": diff(rejected.entries_snapshot, entries) if rejected else [],
        "history": [{"revision": r.revision, "decision": r.decision, "note": r.decision_note,
                     "flagged_dates": r.flagged_dates or [], "addressed_confirmed": r.addressed_confirmed,
                     "decided_at": r.decided_at.isoformat() if r.decided_at else None} for r in reviews],
    }


def pending_for(db: Session, user: Users) -> List[Tuple[TimesheetReview, Timesheet, Employee]]:
    return (db.query(TimesheetReview, Timesheet, Employee)
            .join(Timesheet, Timesheet.id == TimesheetReview.timesheet_id)
            .join(Employee, Employee.id == Timesheet.employee_id)
            .filter(TimesheetReview.approver_user_id == user.UserID, TimesheetReview.decision == "PENDING",
                    Timesheet.status == "SUBMITTED")
            .order_by(TimesheetReview.submitted_at).all())


def rejection_for_employee(db: Session, timesheet: Timesheet) -> Optional[Dict]:
    """My Timesheet on a rejected week: the reason and the flagged days."""
    review = latest_review(db, timesheet)
    if review is None or review.decision != "REJECTED":
        return None
    return {"reason": review.decision_note, "flagged_dates": review.flagged_dates or [], "revision": review.revision}
