"""
Partner/BU spend tracking, 2026-08-05. Self-service, same ownership
boundary as the existing employee self-service timesheet: whoever is
logged in logs their OWN expense -- `logged_by_user_id` is always
resolved from the authenticated caller, never a caller-supplied field
(Avinash: "the expense is logged by employee so they need to login to
their portal and add their expense").

BU attribution is derived from the logger's own business_unit_id at
creation time, never freely settable, same discipline as
app.services.client_service.create_client().

PRIORITY-3 (2026-08-12): Expense Approval Chain
- Receipt reference is mandatory (NOT NULL)
- Manager approval step before Finance review
- Flow: Employee logs (receipt required) â†’ Manager approves (via Task) â†’ Finance reviews â†’ marks paid
"""
from app.services.task_service import create_task
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.client import Client, ClientHistory
from app.models.expense import (
    CLIENT_DIRECTED_PURPOSES, FULL_SHARE_BPS, SPEND_FOR, ExpenseClientShare, ExpenseEdit, ExpenseRecord,
)
from app.models.invoice import Invoice
from app.models.user import Users
from app.models.org_structure import OrgNode

FINANCE_INBOX_EMAIL = "accounts@blitzenx.com"

class ExpenseValidationError(Exception):
    pass


def notify_approved(db, expense, **kw):
    from app.services.action_emails.expenses import notify_approved as send
    return send(db, expense, **kw)


def notify_rejected(db, expense, **kw):
    from app.services.action_emails.expenses import notify_rejected as send
    return send(db, expense, **kw)


def notify_finance_ready(db, expense):
    from app.services.action_emails.expenses import notify_finance_ready as send
    return send(db, expense)


def notify_finance_approved(db, expense, **kw):
    from app.services.action_emails.expenses import notify_finance_approved as send
    return send(db, expense, **kw)


def notify_paid(db, expense, **kw):
    from app.services.action_emails.expenses import notify_paid as send
    return send(db, expense, **kw)


def notify_escalated(db, expense, **kw):
    from app.services.action_emails.expenses import notify_escalated as send
    return send(db, expense, **kw)

def _client_in_scope(db: Session, user: Users, client_id: str) -> Client:
    """The client, when it is in the caller's tenant and business units (prospects without a BU
    are open to everyone, app.core.data_scope); anything else is "not found"."""
    from app.core.data_scope import client_filter

    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == user.tenant_id,
                                     client_filter(db, user, Client.id)).first()
    if client is None:
        raise ExpenseValidationError(f"Client {client_id!r} not found.")
    return client


def _split_shares(amount_usd_cents: int, client_splits: Sequence[dict]) -> List[Tuple[str, int, int]]:
    """[(client_id, share_bps, amount_usd_cents)] from splits given all by `percent` or all by
    `amount_usd_cents`. Percentages must total 100, amounts the full expense; the last line takes
    the rounding remainder so the shares always add up exactly."""
    if len(client_splits) < 2:
        raise ExpenseValidationError("A split needs at least two clients.")
    client_ids = [str(s.get("client_id") or "") for s in client_splits]
    if not all(client_ids):
        raise ExpenseValidationError("Every split line needs a client.")
    if len(set(client_ids)) != len(client_ids):
        raise ExpenseValidationError("Each client can appear only once in a split.")
    by_percent = all(s.get("percent") is not None for s in client_splits)
    by_amount = all(s.get("amount_usd_cents") is not None for s in client_splits)
    if by_percent == by_amount:
        raise ExpenseValidationError("Split every line by percent, or every line by amount.")
    try:
        if by_percent:
            bps = [int((Decimal(str(s["percent"])) * 100).quantize(Decimal(1))) for s in client_splits]
            if sum(bps) != FULL_SHARE_BPS:
                raise ExpenseValidationError(f"The split must total 100% (it totals {sum(bps) / 100:g}%).")
            cents = [amount_usd_cents * b // FULL_SHARE_BPS for b in bps]
            cents[-1] = amount_usd_cents - sum(cents[:-1])
        else:
            cents = [int(s["amount_usd_cents"]) for s in client_splits]
            if sum(cents) != amount_usd_cents:
                raise ExpenseValidationError(
                    f"The split must total the expense ({amount_usd_cents / 100:,.2f}); "
                    f"it totals {sum(cents) / 100:,.2f}.")
            bps = [c * FULL_SHARE_BPS // amount_usd_cents for c in cents]
            bps[-1] = FULL_SHARE_BPS - sum(bps[:-1])
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ExpenseValidationError(f"Invalid split: {exc}") from exc
    if any(b <= 0 for b in bps) or any(c <= 0 for c in cents):
        raise ExpenseValidationError("Every client in a split needs a share above zero.")
    return list(zip(client_ids, bps, cents))


def resolve_attribution(
    db: Session, user: Users, *, purpose: str, amount_usd_cents: int, spend_for: Optional[str],
    client_id: Optional[str], client_splits: Optional[Sequence[dict]],
) -> Tuple[str, Optional[str], List[Tuple[str, int, int]]]:
    """Who the spend is on (CEO 2026-10-31) -> (spend_for, client_id, shares).

      every purpose                     must say: personal/internal, one client, or a split
                                        (naming the client or the split says it)
      CLIENT_CURRENT / CLIENT_PROSPECT  one client or a split; never internal
      INVESTMENT                        internal only
    Every client must be in the caller's tenant and business units."""
    if spend_for is not None and spend_for not in SPEND_FOR:
        raise ExpenseValidationError(f"spend_for must be one of {', '.join(SPEND_FOR)}.")
    if spend_for is None:
        # every expense says who it is on (CEO 2026-10-31): naming the client(s) says it; nothing
        # else is assumed -- personal/internal spend must be chosen, never defaulted
        if client_splits:
            spend_for = "SPLIT"
        elif client_id:
            spend_for = "CLIENT"
        else:
            raise ExpenseValidationError(
                "Every expense must say who it is on: personal/internal (no client), one client, or several clients.")
    if purpose in CLIENT_DIRECTED_PURPOSES and spend_for == "INTERNAL":
        raise ExpenseValidationError(f"purpose={purpose!r} is spend on a client: pick the client(s).")
    if purpose == "INVESTMENT" and spend_for != "INTERNAL":
        raise ExpenseValidationError("An investment expense is internal; it can't be put on a client.")

    if spend_for == "INTERNAL":
        if client_id or client_splits:
            raise ExpenseValidationError("An internal expense can't name a client.")
        return "INTERNAL", None, []
    if spend_for == "CLIENT":
        if client_splits:
            raise ExpenseValidationError("A single-client expense can't have a split; use SPLIT.")
        if not client_id:
            raise ExpenseValidationError(f"purpose={purpose!r} on one client requires client_id.")
        _client_in_scope(db, user, client_id)
        return "CLIENT", client_id, [(client_id, FULL_SHARE_BPS, amount_usd_cents)]
    # SPLIT
    if client_id:
        raise ExpenseValidationError("A split names its clients in client_splits, not client_id.")
    shares = _split_shares(amount_usd_cents, client_splits or [])
    for share_client_id, _, _ in shares:
        _client_in_scope(db, user, share_client_id)
    return "SPLIT", None, shares


def _resolve_event(db: Session, user: Users, purpose: str, event_id: Optional[str]):
    """The shared event a conference expense belongs to; only conference expenses have one."""
    from app.services.expense_event_service import ExpenseEventError, get_event

    if purpose != "CONFERENCE":
        if event_id:
            raise ExpenseValidationError("Only a conference expense belongs to an event.")
        return None
    if not event_id:
        raise ExpenseValidationError("purpose=CONFERENCE requires the conference (event_id): pick it or add it.")
    try:
        return get_event(db, user.tenant_id, event_id)
    except ExpenseEventError as exc:
        raise ExpenseValidationError(str(exc)) from exc


def _apply_attribution(expense: ExpenseRecord, spend_for: str, client_id: Optional[str],
                       shares: List[Tuple[str, int, int]]) -> None:
    expense.spend_for = spend_for
    expense.client_id = client_id
    expense.client_shares = [ExpenseClientShare(client_id=c, share_bps=b, amount_usd_cents=a) for c, b, a in shares]


def attribution_gaps(expense: ExpenseRecord) -> List[str]:
    """What still stops the expense from counting in the P&L: unsaid who it is on, a conference
    without its event, a client expense without its client(s), or shares that don't add up."""
    gaps = []
    if expense.spend_for not in SPEND_FOR:
        gaps.append("who the spend is on (internal, one client, or several)")
    if expense.purpose == "CONFERENCE" and not expense.event_id:
        gaps.append("the conference it belongs to")
    if expense.spend_for in ("CLIENT", "SPLIT"):
        shares = expense.client_shares or []
        if not shares and not expense.client_id:
            gaps.append("the client(s) it is on")
        elif shares and (sum(s.share_bps for s in shares) != FULL_SHARE_BPS
                         or sum(s.amount_usd_cents for s in shares) != expense.amount_usd_cents):
            gaps.append("a client split that totals 100% of the amount")
    return gaps


def log_expense(
    db: Session,
    *,
    logged_by_user: Users,
    purpose: str,
    expense_category: str,
    amount_usd_cents: int,
    expense_date: date,
    receipt_ref: str,  # PRIORITY-3: Receipt is now mandatory (not optional)
    expense_end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    spend_for: Optional[str] = None,
    client_splits: Optional[Sequence[dict]] = None,
    event_id: Optional[str] = None,
    investment_label: Optional[str] = None,
    travel_type: Optional[str] = None,
    trip_label: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> ExpenseRecord:
    """PRIORITY-3: Create an expense with mandatory receipt reference.

    Flow:
    1. Employee logs expense (receipt_ref required), saying who it is on (resolve_attribution)
       and, for a conference, which shared event (expense_event_service)
    2. Manager approval task created (manager found via org_node_id)
    3. After manager approves task, expense moves to Finance review
    4. Finance approves and marks as reimbursed
    """
    if amount_usd_cents <= 0:
        raise ExpenseValidationError("amount_usd_cents must be positive.")
    expense_end_date = _checked_end_date(expense_date, expense_end_date)

    if not receipt_ref or not receipt_ref.strip():
        raise ExpenseValidationError("receipt_ref is mandatory for all expenses.")

    if purpose == "INVESTMENT" and not investment_label:
        raise ExpenseValidationError("purpose=INVESTMENT requires investment_label.")
    event = _resolve_event(db, logged_by_user, purpose, event_id)
    spend_for, client_id, shares = resolve_attribution(
        db, logged_by_user, purpose=purpose, amount_usd_cents=amount_usd_cents, spend_for=spend_for,
        client_id=client_id, client_splits=client_splits)

    expense = ExpenseRecord(
        tenant_id=logged_by_user.tenant_id,
        business_unit_id=logged_by_user.business_unit_id,
        logged_by_user_id=logged_by_user.UserID,
        purpose=purpose, event_id=event.id if event else None,
        conference_name=event.name if event else None,
        investment_label=investment_label if purpose == "INVESTMENT" else None,
        expense_category=expense_category,
        travel_type=travel_type, trip_label=trip_label, amount_usd_cents=amount_usd_cents,
        location=location, description=description, receipt_ref=receipt_ref,
        expense_date=expense_date, expense_end_date=expense_end_date,
        manager_approval_status="PENDING",  # PRIORITY-3: Start with pending manager approval
    )
    _apply_attribution(expense, spend_for, client_id, shares)
    db.add(expense)
    db.flush()
    record_event(db, expense, logged_by_user.UserID, f"Logged: ${amount_usd_cents / 100:,.2f}, {expense_dates_text(expense)}")

    # PRIORITY-3: Create manager approval task
    _create_manager_approval_task(db, expense, logged_by_user)

    db.commit()
    db.refresh(expense)
    return expense


def _checked_end_date(first: date, last: Optional[date]) -> Optional[date]:
    """The last day of a multi-day expense; the same day as the first counts as one day."""
    if last is None or last == first:
        return None
    if last < first:
        raise ExpenseValidationError("The last date can't be before the first date.")
    return last


def expense_dates_text(expense: ExpenseRecord) -> str:
    if expense.expense_end_date:
        return f"{expense.expense_date} to {expense.expense_end_date}"
    return str(expense.expense_date)


def can_edit_expense(expense: ExpenseRecord, user: Users) -> bool:
    """The person who logged it, until Finance approves it for payment."""
    return user.UserID == expense.logged_by_user_id and expense.payment_status == "PENDING"


def record_event(db: Session, expense: ExpenseRecord, user_id: Optional[str], summary: str) -> None:
    """One line of the expense's history (CEO 2026-11-06: Finance sees the full audit history): who did
    what and when, every step from logging to payment. No user = the system."""
    db.add(ExpenseEdit(expense_id=expense.id, changed_by_user_id=user_id, summary=summary))
    db.flush()
    db.expire(expense, ["edits"])
    logger.info(f"[ExpenseService] {expense.id} by {user_id or 'system'}: {summary}")


def record_edit(db: Session, expense: ExpenseRecord, user: Optional[Users], summary: str) -> None:
    record_event(db, expense, user.UserID if user else None, summary)


def return_to_manager(db: Session, expense: ExpenseRecord, note: Optional[str] = None) -> None:
    """A change after (or before) a decision: the manager decides again, on what it says now. The old
    approval task names the old figures, so a new one replaces it."""
    expense.manager_approval_status = "PENDING"
    expense.manager_approved_by = None
    expense.manager_approved_at = None
    expense.manager_review_note = None
    db.add(expense)
    record_event(db, expense, None, "Returned to the manager for review")
    _close_open_tasks(db, expense)
    logged_by = db.query(Users).filter(Users.UserID == expense.logged_by_user_id).first()
    _create_manager_approval_task(db, expense, logged_by, note=note)


def _readable_values(expense: ExpenseRecord) -> Dict[str, str]:
    """What the person can change, as they read it, money-affecting fields first."""
    return {
        "Amount": f"${expense.amount_usd_cents / 100:,.2f}", "Dates": expense_dates_text(expense),
        "Purpose": expense.purpose, "For": _attribution_line(expense),
        "Split": ", ".join(f"{s.client_id}={s.amount_usd_cents}" for s in expense.client_shares or []),
        "Conference": expense.event_id or "", "Investment": expense.investment_label or "",
        "Category": expense.expense_category, "Travel type": expense.travel_type or "",
        "Trip": expense.trip_label or "", "Location": expense.location or "",
        "Description": expense.description or "", "Receipt ref": expense.receipt_ref or "",
    }


NOTE_ONLY_FIELDS = {"Trip", "Location", "Description", "Receipt ref"}  # don't change what was approved
HIDDEN_FROM_SUMMARY = {"Split", "Conference"}  # "For" and the event's own name say these


def update_expense(
    db: Session, expense: ExpenseRecord, user: Users, *, purpose: str, expense_category: str, amount_usd_cents: int,
    expense_date: date, expense_end_date: Optional[date] = None, spend_for: Optional[str] = None,
    client_id: Optional[str] = None, client_splits: Optional[Sequence[dict]] = None, event_id: Optional[str] = None,
    investment_label: Optional[str] = None, travel_type: Optional[str] = None, trip_label: Optional[str] = None,
    location: Optional[str] = None, description: Optional[str] = None, receipt_ref: Optional[str] = None,
) -> ExpenseRecord:
    """Correct your own expense (CEO 2026-11-06): the same rules as logging it. A change to what it costs
    or who it is on goes back to the manager; every change is recorded for them to see."""
    from app.services.expense_receipt_service import announce_after_check, recheck

    if not can_edit_expense(expense, user):
        raise PermissionError("Finance has approved this expense, so it can't be changed any more.")
    if amount_usd_cents <= 0:
        raise ExpenseValidationError("amount_usd_cents must be positive.")
    expense_end_date = _checked_end_date(expense_date, expense_end_date)
    if purpose == "INVESTMENT" and not investment_label:
        raise ExpenseValidationError("purpose=INVESTMENT requires investment_label.")
    event = _resolve_event(db, user, purpose, event_id)
    spend_for, client_id, shares = resolve_attribution(
        db, user, purpose=purpose, amount_usd_cents=amount_usd_cents, spend_for=spend_for,
        client_id=client_id, client_splits=client_splits)

    before = _readable_values(expense)
    was = expense.manager_approval_status
    expense.purpose, expense.expense_category, expense.amount_usd_cents = purpose, expense_category, amount_usd_cents
    expense.expense_date, expense.expense_end_date = expense_date, expense_end_date
    expense.event_id, expense.conference_name = (event.id, event.name) if event else (None, None)
    expense.investment_label = investment_label if purpose == "INVESTMENT" else None
    expense.travel_type, expense.trip_label = travel_type, trip_label
    expense.location, expense.description = location, description
    if receipt_ref and receipt_ref.strip():
        expense.receipt_ref = receipt_ref
    expense.client_shares = []
    db.flush()  # the old shares go before the new ones (unique per expense and client)
    _apply_attribution(expense, spend_for, client_id, shares)
    db.flush()
    db.refresh(expense, ["client_shares", "client"])

    after = _readable_values(expense)
    changed = [field for field in after if after[field] != before[field]]
    if not changed:
        db.commit()
        return expense
    summary = "; ".join(f"{field}: {before[field] or '(empty)'} -> {after[field] or '(empty)'}"
                        for field in changed if field not in HIDDEN_FROM_SUMMARY)
    record_edit(db, expense, user, summary or "Who it is on changed")
    if set(changed) - NOTE_ONLY_FIELDS or expense.manager_approval_status == "REJECTED":
        return_to_manager(db, expense, note=f"Changed by the person who logged it: {summary}")
        recheck(db, expense)
    db.commit()
    db.refresh(expense)
    announce_after_check(db, expense, was)
    return expense


def can_edit_attribution(db: Session, expense: ExpenseRecord, user: Users) -> bool:
    """The person who logged it until their manager decides; the reviewer until Finance approves."""
    if user.UserID == expense.logged_by_user_id:
        return expense.manager_approval_status == "PENDING"
    return (expense.payment_status == "PENDING" and expense.manager_approval_status != "REJECTED"
            and can_review_as_manager(db, expense, user))


def update_attribution(
    db: Session, expense: ExpenseRecord, user: Users, *, spend_for: Optional[str],
    client_id: Optional[str] = None, client_splits: Optional[Sequence[dict]] = None,
    event_id: Optional[str] = None,
) -> ExpenseRecord:
    """Correct who an expense is on and (for a conference) its event -- same rules as logging it.
    Clients are checked against the editor's business units."""
    if not can_edit_attribution(db, expense, user):
        raise PermissionError("You can't change who this expense is on any more.")
    event = _resolve_event(db, user, expense.purpose, event_id or expense.event_id)  # unchanged unless given
    spend_for, client_id, shares = resolve_attribution(
        db, user, purpose=expense.purpose, amount_usd_cents=expense.amount_usd_cents, spend_for=spend_for,
        client_id=client_id, client_splits=client_splits)
    expense.client_shares = []
    db.flush()  # the old shares go before the new ones (unique per expense and client)
    _apply_attribution(expense, spend_for, client_id, shares)
    if event is not None:
        expense.event_id, expense.conference_name = event.id, event.name
    db.add(expense)
    db.commit()
    db.refresh(expense)
    logger.info(f"[ExpenseService] attribution of {expense.id} set to {spend_for} by {user.UserID}")
    return expense


def expense_shares(expenses: Sequence[ExpenseRecord]) -> Dict[str, List[Tuple[Optional[str], int]]]:
    """{expense id: [(client_id or None for internal, amount_usd_cents)]} -- how each expense's
    amount falls on clients. The P&L, the investment position and the event rollup all read
    this, so a split client expense is counted once, in parts."""
    out: Dict[str, List[Tuple[Optional[str], int]]] = {}
    for expense in expenses:
        shares = list(expense.client_shares or [])
        out[expense.id] = ([(s.client_id, s.amount_usd_cents) for s in shares] if shares
                           else [(expense.client_id, expense.amount_usd_cents)])
    return out


def _attribution_line(expense: ExpenseRecord) -> str:
    if expense.spend_for == "SPLIT":
        return f"Split across {len(expense.client_shares or [])} clients"
    if expense.spend_for == "CLIENT":
        return f"On client {expense.client.company_name if expense.client else expense.client_id}"
    return "Internal (no client)"


def _get_employee_manager(db: Session, employee_user: Users) -> Optional[Users]:
    """Who reviews this person's expenses: the person in the parent seat of the org chart, else their
    reporting manager on their employee record, else the partner of their business unit. Most people
    have no seat yet, and a task with nobody on it is seen by nobody. Never the person themselves."""
    from app.models.business_unit import BusinessUnit
    from app.models.employee import Employee

    org_node = (db.query(OrgNode).filter(OrgNode.id == employee_user.org_node_id).first()
                if employee_user.org_node_id else None)
    candidates = []
    if org_node and org_node.parent_id:
        # the person sitting in the parent seat (Users.org_node_id); OrgNode has no user column
        seat = db.query(Users).filter(Users.org_node_id == org_node.parent_id,
                                      Users.tenant_id == employee_user.tenant_id).first()
        candidates.append(seat.UserID if seat else None)
    employee = db.query(Employee).filter(Employee.wros_user_id == employee_user.UserID).first()
    if employee is not None:
        candidates.append(employee.reporting_manager_user_id)
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first() if employee.manager_id else None
        candidates.append(manager.wros_user_id if manager else None)
    if employee_user.business_unit_id:
        unit = db.query(BusinessUnit).filter(BusinessUnit.id == employee_user.business_unit_id).first()
        candidates.append(unit.partner_user_id if unit else None)
    for user_id in candidates:
        if user_id and user_id != employee_user.UserID:
            return db.query(Users).filter(Users.UserID == user_id).first()
    return None

def _create_manager_approval_task(db: Session, expense: ExpenseRecord, employee_user: Users,
                                  note: Optional[str] = None) -> None:
    """A Task for the manager to review the expense; only their decision closes it. With no manager
    on record it goes to Finance, so it never sits with nobody."""
    from app.models.task import EXPENSE_REVIEW_TASK_CATEGORY
    from app.services.task_service import create_task

    manager = _get_employee_manager(db, employee_user)
    if manager is None:
        finance = _finance_assignee(db, expense.tenant_id)
        manager = finance if finance is not None and finance.UserID != employee_user.UserID else None
    manager_user_id = manager.UserID if manager else None

    task = create_task(
        db,
        title=f"Approve expense: {expense.expense_category} ${expense.amount_usd_cents / 100:,.2f}",
        description=(
            f"{employee_user.UserName or employee_user.UserEmail} has logged an expense for your approval.\n"
            f"{f'{note}{chr(10)}' if note else ''}"
            f"Category: {expense.expense_category}\n"
            f"Amount: ${expense.amount_usd_cents / 100:,.2f}\n"
            f"Date: {expense_dates_text(expense)}\n"
            f"For: {_attribution_line(expense)}"
            f"{f' -- {expense.conference_name}' if expense.conference_name else ''}\n"
            f"Receipt: {expense.receipt_ref}\n"
            f"Please review and approve before it moves to Finance."
        ),
        priority="MEDIUM",
        tenant_id=expense.tenant_id,
        assigned_to_user_id=manager_user_id,
        visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if manager_user_id else "ORG_WIDE",
        due_date=datetime.utcnow() + timedelta(days=settings.EXPENSE_REVIEW_DUE_DAYS),
        expense_id=expense.id,
    )
    task.category = EXPENSE_REVIEW_TASK_CATEGORY
    db.add(task)
    record_event(db, expense, None, f"Sent for review to {(manager.UserName or manager.UserEmail) if manager else 'anyone in Finance'}")
    logger.info(
        f"[ExpenseService] Manager approval task created for expense {expense.id} "
        f"(assigned to {manager_user_id or 'fallback'})"
    )

def _finance_assignee(db: Session, tenant_id: Optional[int]) -> Optional[Users]:
    """The Finance person the "mark as paid" Task goes to: the most junior invoice approver
    (Finance at Senior Manager level or above, by role template -- app.core.authority), the
    same people who approve invoices. None when the firm has no one in that seat yet: the
    task is then visible org-wide (never an administrator bypass -- paying is Finance's call)."""
    from app.services.invoice_service import invoice_approvers

    approvers = invoice_approvers(db, tenant_id)
    return approvers[0] if approvers else None

def can_review_as_manager(db: Session, expense: ExpenseRecord, user: Users) -> bool:
    """The manager the approval task was assigned to, or anyone with finance
    (revenue view) authority. Never the person who logged it."""
    from app.models.task import Task
    from app.services.role_template_permission_service import RoleTemplatePermissionService as perms

    if user.UserID == expense.logged_by_user_id:
        return False
    assigned = db.query(Task).filter(Task.expense_id == expense.id, Task.status != "COMPLETED",
                                     Task.assigned_to_user_id == user.UserID).first()
    return assigned is not None or perms.has_permission(db, user.UserID, "revenue", "view", user.tenant_id)


def _close_open_tasks(db: Session, expense: ExpenseRecord) -> None:
    from app.models.task import Task
    from app.services.task_service import complete_task

    for task in db.query(Task).filter(Task.expense_id == expense.id, Task.status != "COMPLETED").all():
        complete_task(db, task)


def approve_manager_step(db: Session, expense: ExpenseRecord, *, approved_by: str) -> ExpenseRecord:
    """Manager approval: the expense now counts as a cost in the P&L and moves to
    Finance for payment. Closes the manager's approval task."""
    if expense.manager_approval_status != "PENDING":
        raise ExpenseValidationError(
            f"Expense {expense.id} manager approval must be PENDING, not {expense.manager_approval_status}"
        )
    if approved_by == expense.logged_by_user_id:
        raise ExpenseValidationError("You can't approve your own expense.")
    gaps = attribution_gaps(expense)
    if gaps:
        raise ExpenseValidationError("Before it counts in the P&L the expense needs " + "; ".join(gaps) + ".")

    expense.manager_approval_status = "APPROVED"
    expense.manager_approved_by = approved_by
    expense.manager_approved_at = datetime.utcnow()
    db.add(expense)
    record_event(db, expense, approved_by, "Approved by the manager: counts in the P&L from now")
    _close_open_tasks(db, expense)
    create_finance_review_task(db, expense)
    db.commit()
    db.refresh(expense)

    logger.info(
        f"[ExpenseService] Manager approval completed for expense {expense.id} "
        f"(approved by {approved_by}), now ready for Finance review"
    )
    notify_approved(db, expense, approved_by=approved_by)
    notify_finance_ready(db, expense)
    return expense


def reject_manager_step(db: Session, expense: ExpenseRecord, *, rejected_by: str,
                        reason: Optional[str] = None) -> ExpenseRecord:
    """Manager rejection: the expense never counts in the P&L."""
    if expense.manager_approval_status != "PENDING":
        raise ExpenseValidationError(
            f"Expense {expense.id} manager approval must be PENDING, not {expense.manager_approval_status}"
        )
    if rejected_by == expense.logged_by_user_id:
        raise ExpenseValidationError("You can't review your own expense.")
    expense.manager_approval_status = "REJECTED"
    expense.manager_review_note = reason.strip() if reason and reason.strip() else None
    expense.manager_approved_by = rejected_by
    expense.manager_approved_at = datetime.utcnow()
    db.add(expense)
    record_event(db, expense, rejected_by, f"Rejected by the manager{f': {expense.manager_review_note}' if expense.manager_review_note else ''}")
    _close_open_tasks(db, expense)
    db.commit()
    db.refresh(expense)
    notify_rejected(db, expense, rejected_by=rejected_by)
    return expense

def _finance_task(db: Session, expense: ExpenseRecord, *, title: str, description: str, due_days: int) -> None:
    from app.models.task import EXPENSE_FINANCE_TASK_CATEGORY

    assignee = _finance_assignee(db, expense.tenant_id)
    task = create_task(
        db, title=title, description=description, priority="MEDIUM", tenant_id=expense.tenant_id,
        assigned_to_user_id=assignee.UserID if assignee else None,
        visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if assignee else "ORG_WIDE",
        due_date=datetime.utcnow() + timedelta(days=due_days), expense_id=expense.id,
    )
    task.category, task.link = EXPENSE_FINANCE_TASK_CATEGORY, "/pnl?view=operations"
    db.add(task)


def create_finance_review_task(db: Session, expense: ExpenseRecord) -> None:
    """The manager step is done, by a person or by the receipts matching: Finance now has work to do."""
    _finance_task(db, expense, title=f"Approve expense for payment: {expense.expense_category} ${expense.amount_usd_cents / 100:,.2f}",
                  description=f"{expense.logged_by_name or expense.logged_by_user_id}, {expense_dates_text(expense)}. "
                              f"For: {_attribution_line(expense)}. Review it in Finance Operations.",
                  due_days=settings.EXPENSE_FINANCE_DUE_DAYS)


ESCALATING_CATEGORIES = ("EXPENSE_REVIEW", "EXPENSE_FINANCE")


def run_expense_escalations(db: Session, *, now: Optional[datetime] = None) -> Dict[str, int]:
    """Job: a step past its due date goes to the assignee's manager, else to Finance; the person who
    logged it is told. Once per step: the next step has its own task and its own due date."""
    from app.models.task import Task
    from app.services.invoice_service import invoice_approvers
    from app.services.task_assignment_service import resolve_reporting_manager
    from app.services.task_escalation_service import _bump_one_tier_capped

    now = now or datetime.utcnow()
    escalated = 0
    for task in db.query(Task).filter(Task.expense_id.isnot(None), Task.category.in_(ESCALATING_CATEGORIES),
                                      Task.status.in_(("NEW", "IN_PROGRESS", "ON_HOLD")), Task.due_date.isnot(None),
                                      Task.due_date < now, Task.is_escalated.is_(False)).all():
        expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == task.expense_id).first()
        if expense is None:
            logger.error(f"[ExpenseService] task {task.id} points at unknown expense {task.expense_id}")
            continue
        assignee = db.query(Users).filter(Users.UserID == task.assigned_to_user_id).first() if task.assigned_to_user_id else None
        manager = resolve_reporting_manager(db, task.assigned_to_user_id) if task.assigned_to_user_id else None
        targets = [manager] if manager is not None else [
            u for u in invoice_approvers(db, expense.tenant_id)
            if u.UserID not in (task.assigned_to_user_id, expense.logged_by_user_id)]
        task.is_escalated, task.escalated_at = True, now
        task.priority = _bump_one_tier_capped(task.priority)
        db.add(task)
        names = ", ".join(u.UserName or u.UserEmail for u in targets) or "nobody: no one is above them and Finance has no one else"
        record_event(db, expense, None, f"Overdue and escalated to {names}: {task.title}")
        db.commit()
        db.refresh(expense)
        notify_escalated(db, expense, task_title=task.title, assignee=assignee, escalate_to=targets)
        escalated += 1
    return {"escalated": escalated}


def approve_expense(db: Session, expense: ExpenseRecord, *, approved_by: str) -> ExpenseRecord:
    """PRIORITY-3: Finance approval step (only after manager approval).

    Avinash's explicit rule, 2026-08-05: approval isn't the end of
    the flow -- accounts@blitzenx.com gets notified, and a real Task
    tracks "mark it paid once paid" so it doesn't just vanish into an
    approved-but-forgotten state.

    PRIORITY-3: Now requires manager approval first (manager_approval_status == "APPROVED").
    """
    if expense.manager_approval_status != "APPROVED":
        raise ExpenseValidationError(
            f"Cannot approve expense {expense.id} for Finance until manager approves "
            f"(current status: {expense.manager_approval_status})"
        )
    gaps = attribution_gaps(expense)
    if gaps:
        raise ExpenseValidationError("Before it is paid the expense needs " + "; ".join(gaps) + ".")

    expense.payment_status = "APPROVED"
    expense.approved_by = approved_by
    db.add(expense)
    record_event(db, expense, approved_by, "Approved for payment by Finance")
    _close_open_tasks(db, expense)
    db.commit()
    db.refresh(expense)

    _notify_finance_of_approval(db, expense)
    _create_mark_paid_task(db, expense)
    db.commit()
    db.refresh(expense)
    notify_finance_approved(db, expense, approved_by=approved_by)
    return expense

def _notify_finance_of_approval(db: Session, expense: ExpenseRecord) -> None:
    """accounts@blitzenx.com is a shared inbox, not a real Users login
    in this codebase -- goes through EmailService directly (same
    posture as the candidate email-OTP send), not the internal
    Notification Engine, which requires a real Users recipient. Never
    blocks the approval itself on a send failure."""
    from app.services.email_service import EmailService

    try:
        EmailService.send_event_notification(
            to_email=FINANCE_INBOX_EMAIL,
            recipient_name="Finance",
            event_type="action_required",
            heading="Expense approved -- ready to pay",
            message=(
                f"An expense of ${expense.amount_usd_cents / 100:,.2f} "
                f"({expense.expense_category}, {expense.purpose}) logged by "
                f"{expense.logged_by_user_id} has been approved and is ready for payment."
            ),
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[ExpenseService] Could not notify {FINANCE_INBOX_EMAIL} of approval for expense {expense.id}: {exc}")

def _create_mark_paid_task(db: Session, expense: ExpenseRecord) -> None:

    _finance_task(db, expense, title=f"Mark expense as paid: {expense.expense_category} ${expense.amount_usd_cents / 100:,.2f}",
                  description=f"Approved expense {expense.id} (purpose={expense.purpose}) -- mark REIMBURSED once payment is sent.",
                  due_days=settings.EXPENSE_PAYMENT_DUE_DAYS)

def mark_expense_paid(db: Session, expense: ExpenseRecord, *, paid_by: Optional[str] = None) -> ExpenseRecord:
    """Completes the loop: flips the expense to REIMBURSED and closes
    its "mark as paid" Task (if one exists -- older/manually-created
    expenses may not have one)."""
    from app.models.task import Task
    from app.services.task_service import complete_task

    if expense.payment_status != "APPROVED":
        raise ExpenseValidationError(
            f"Expense {expense.id} must be APPROVED before it can be marked paid (currently {expense.payment_status})."
        )

    expense.payment_status = "REIMBURSED"
    db.add(expense)
    record_event(db, expense, paid_by, "Marked paid by Finance")

    task = db.query(Task).filter(Task.expense_id == expense.id, Task.status != "COMPLETED").first()
    if task:
        complete_task(db, task)

    db.commit()
    db.refresh(expense)
    notify_paid(db, expense, paid_by=paid_by)
    return expense

def get_client_investment_position(db: Session, client_id: str) -> dict:
    """The full story: total spend on this client (from its very first
    PROSPECT-era expense, if any) vs. total revenue billed (from
    Invoice), the conversion date (from ClientHistory's STATUS change
    log -- already tracked, not duplicated here), and the date the
    relationship first turned net-positive.

    Prospect-to-active timeline reuses ClientHistory rather than a
    second tracking mechanism: it's already written on every
    set_client_status() call.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ExpenseValidationError(f"Client {client_id!r} not found.")

    # its whole-client expenses and its part of split ones; rejected spend never counts
    split_ids = db.query(ExpenseClientShare.expense_id).filter(ExpenseClientShare.client_id == client_id)
    records: List[ExpenseRecord] = (
        db.query(ExpenseRecord)
        .filter(or_(ExpenseRecord.client_id == client_id, ExpenseRecord.id.in_(split_ids)),
                ExpenseRecord.manager_approval_status != "REJECTED")
        .order_by(ExpenseRecord.expense_date)
        .all()
    )
    shares = expense_shares(records)
    expenses = [(e.expense_date, sum(c for cid, c in shares[e.id] if cid == client_id)) for e in records]
    invoices: List[Invoice] = (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id, Invoice.status.in_(("APPROVED", "SENT", "PAID")))
        .order_by(Invoice.created_at)
        .all()
    )

    total_expense_usd_cents = sum(cents for _, cents in expenses)
    total_revenue_usd_cents = sum(i.total_usd_cents for i in invoices)

    converted_on = None
    activation_history = (
        db.query(ClientHistory)
        .filter(
            ClientHistory.client_id == client_id,
            ClientHistory.change_type == "STATUS",
            ClientHistory.new_value.like('%"ACTIVE"%'),
        )
        .order_by(ClientHistory.changed_at)
        .first()
    )
    if activation_history:
        converted_on = activation_history.changed_at

    # Running balance to find the first date the relationship turned
    # net-positive -- merge expense and revenue events chronologically.
    events = [(spent_on, -cents) for spent_on, cents in expenses]
    events += [(i.created_at.date() if i.created_at else i.created_at, i.total_usd_cents) for i in invoices if i.created_at]
    events.sort(key=lambda ev: ev[0])
    running = 0
    breakeven_date = None
    for event_date, delta in events:
        running += delta
        if breakeven_date is None and running >= 0 and total_expense_usd_cents > 0:
            breakeven_date = event_date

    return {
        "client_id": client_id,
        "company_name": client.company_name,
        "status": client.status,
        "prospect_since": client.created_at,
        "converted_on": converted_on,
        "total_expense_usd_cents": total_expense_usd_cents,
        "total_revenue_usd_cents": total_revenue_usd_cents,
        "net_position_usd_cents": total_revenue_usd_cents - total_expense_usd_cents,
        "breakeven_date": breakeven_date,
        "expense_count": len(expenses),
    }
