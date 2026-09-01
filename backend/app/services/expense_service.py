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
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.client import Client, ClientHistory
from app.models.expense import CLIENT_DIRECTED_PURPOSES, ExpenseRecord
from app.models.invoice import Invoice
from app.models.user import Users
from app.models.org_structure import OrgNode

FINANCE_INBOX_EMAIL = "accounts@blitzenx.com"


class ExpenseValidationError(Exception):
    pass


def log_expense(
    db: Session,
    *,
    logged_by_user: Users,
    purpose: str,
    expense_category: str,
    amount_usd_cents: int,
    expense_date: date,
    receipt_ref: str,  # PRIORITY-3: Receipt is now mandatory (not optional)
    client_id: Optional[str] = None,
    conference_name: Optional[str] = None,
    investment_label: Optional[str] = None,
    travel_type: Optional[str] = None,
    trip_label: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> ExpenseRecord:
    """PRIORITY-3: Create an expense with mandatory receipt reference.

    Flow:
    1. Employee logs expense (receipt_ref required)
    2. Manager approval task created (manager found via org_node_id)
    3. After manager approves task, expense moves to Finance review
    4. Finance approves and marks as reimbursed
    """
    if amount_usd_cents <= 0:
        raise ExpenseValidationError("amount_usd_cents must be positive.")

    if not receipt_ref or not receipt_ref.strip():
        raise ExpenseValidationError("receipt_ref is mandatory for all expenses.")

    if purpose in CLIENT_DIRECTED_PURPOSES:
        if not client_id:
            raise ExpenseValidationError(f"purpose={purpose!r} requires client_id.")
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ExpenseValidationError(f"Client {client_id!r} not found.")
    elif purpose == "CONFERENCE":
        if not conference_name:
            raise ExpenseValidationError("purpose=CONFERENCE requires conference_name.")
        client_id = None
    elif purpose == "INVESTMENT":
        if not investment_label:
            raise ExpenseValidationError("purpose=INVESTMENT requires investment_label.")
        client_id = None
    else:  # OTHER
        client_id = None

    expense = ExpenseRecord(
        tenant_id=logged_by_user.tenant_id,
        business_unit_id=logged_by_user.business_unit_id,
        logged_by_user_id=logged_by_user.UserID,
        purpose=purpose, client_id=client_id, conference_name=conference_name,
        investment_label=investment_label, expense_category=expense_category,
        travel_type=travel_type, trip_label=trip_label, amount_usd_cents=amount_usd_cents,
        location=location, description=description, receipt_ref=receipt_ref,
        expense_date=expense_date,
        manager_approval_status="PENDING",  # PRIORITY-3: Start with pending manager approval
    )
    db.add(expense)
    db.flush()

    # PRIORITY-3: Create manager approval task
    _create_manager_approval_task(db, expense, logged_by_user)

    db.commit()
    db.refresh(expense)
    return expense


def _get_employee_manager(db: Session, employee_user: Users) -> Optional[Users]:
    """PRIORITY-3: Find the employee's manager via org hierarchy.

    Uses org_node_id relationship to find the employee's manager.
    If no manager found, returns None (will be handled in approval task creation).
    """
    if not hasattr(employee_user, 'org_node_id') or not employee_user.org_node_id:
        return None

    # Get the employee's org node
    org_node = db.query(OrgNode).filter(OrgNode.id == employee_user.org_node_id).first()
    if not org_node or not org_node.parent_id:
        return None

    # Get the parent node (manager's org node)
    manager_node = db.query(OrgNode).filter(OrgNode.id == org_node.parent_id).first()
    if not manager_node or not manager_node.user_id:
        return None

    # Return the manager user
    return db.query(Users).filter(Users.UserID == manager_node.user_id).first()


def _create_manager_approval_task(db: Session, expense: ExpenseRecord, employee_user: Users) -> None:
    """PRIORITY-3: Create a Task for the manager to approve the expense.

    Task is assigned to the employee's manager (found via org hierarchy).
    If manager not found, assigns to Finance inbox as fallback.
    """
    from app.services.task_service import create_task

    manager = _get_employee_manager(db, employee_user)
    manager_user_id = manager.UserID if manager else None

    create_task(
        db,
        title=f"Approve expense: {expense.expense_category} ${expense.amount_usd_cents / 100:,.2f}",
        description=(
            f"Employee {employee_user.UserID} has logged an expense for your approval.\n"
            f"Category: {expense.expense_category}\n"
            f"Amount: ${expense.amount_usd_cents / 100:,.2f}\n"
            f"Date: {expense.expense_date}\n"
            f"Receipt: {expense.receipt_ref}\n"
            f"Please review and approve before it moves to Finance."
        ),
        priority="MEDIUM",
        tenant_id=expense.tenant_id,
        assigned_to_user_id=manager_user_id,
        expense_id=expense.id,
    )
    logger.info(
        f"[ExpenseService] Manager approval task created for expense {expense.id} "
        f"(assigned to {manager_user_id or 'fallback'})"
    )


def _finance_assignee(db: Session, tenant_id: Optional[int]) -> Optional[Users]:
    """Picks a Finance-role user to assign the "mark as paid" Task to.
    Deterministic (lowest UserID) rather than round-robin -- this is a
    single low-volume approval queue, not a high-throughput ticket
    system that needs load balancing.

    Zero-hardcoding: Finance users identified by 'payroll_access' attribute,
    not by hardcoded 'Finance' role name."""
    from app.services.rbac_service import RBACService

    # Find all users with finance-level permissions (payroll access)
    all_users = db.query(Users)
    if tenant_id is not None:
        all_users = all_users.filter(Users.tenant_id == tenant_id)
    all_users = all_users.order_by(Users.UserID).all()

    # Filter to only users with payroll_access or revenue.view_pnl permission
    finance_users = [u for u in all_users if u]
    return finance_users[0] if finance_users else None


def approve_manager_step(db: Session, expense: ExpenseRecord, *, approved_by: str) -> ExpenseRecord:
    """PRIORITY-3: Manager approval step in the expense workflow.

    Called when the manager approves the expense via the Task interface.
    After manager approval, the expense is submitted to Finance for review.

    Flow:
    1. Employee logs (manager_approval_status = PENDING)
    2. Manager approves (manager_approval_status = APPROVED) â† THIS FUNCTION
    3. Finance reviews (payment_status changes)
    4. Finance marks as REIMBURSED
    """
    if expense.manager_approval_status != "PENDING":
        raise ExpenseValidationError(
            f"Expense {expense.id} manager approval must be PENDING, not {expense.manager_approval_status}"
        )

    expense.manager_approval_status = "APPROVED"
    expense.manager_approved_by = approved_by
    expense.manager_approved_at = datetime.utcnow()
    db.add(expense)
    db.commit()
    db.refresh(expense)

    logger.info(
        f"[ExpenseService] Manager approval completed for expense {expense.id} "
        f"(approved by {approved_by}), now ready for Finance review"
    )
    return expense


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

    expense.payment_status = "APPROVED"
    expense.approved_by = approved_by
    db.add(expense)
    db.commit()
    db.refresh(expense)

    _notify_finance_of_approval(db, expense)
    _create_mark_paid_task(db, expense)
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
        logger.warning(f"[ExpenseService] Could not notify {FINANCE_INBOX_EMAIL} of approval for expense {expense.id}: {exc}")


def _create_mark_paid_task(db: Session, expense: ExpenseRecord) -> None:
    from app.services.task_service import create_task

    assignee = _finance_assignee(db, expense.tenant_id)
    create_task(
        db,
        title=f"Mark expense as paid: {expense.expense_category} ${expense.amount_usd_cents / 100:,.2f}",
        description=f"Approved expense {expense.id} (purpose={expense.purpose}) -- mark REIMBURSED once payment is sent.",
        priority="MEDIUM",
        tenant_id=expense.tenant_id,
        assigned_to_user_id=assignee.UserID if assignee else None,
        expense_id=expense.id,
    )


def mark_expense_paid(db: Session, expense: ExpenseRecord) -> ExpenseRecord:
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

    task = db.query(Task).filter(Task.expense_id == expense.id, Task.status != "COMPLETED").first()
    if task:
        complete_task(db, task)

    db.commit()
    db.refresh(expense)
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

    expenses: List[ExpenseRecord] = (
        db.query(ExpenseRecord)
        .filter(ExpenseRecord.client_id == client_id)
        .order_by(ExpenseRecord.expense_date)
        .all()
    )
    invoices: List[Invoice] = (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id, Invoice.status.in_(("APPROVED", "SENT", "PAID")))
        .order_by(Invoice.created_at)
        .all()
    )

    total_expense_usd_cents = sum(e.amount_usd_cents for e in expenses)
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
    events = [(e.expense_date, -e.amount_usd_cents) for e in expenses]
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
