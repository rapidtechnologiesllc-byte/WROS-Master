"""Emails along an expense's chain (CEO 2026-11-06: "any and every step where employee should be
notified"): the person who logged it hears of each step, Finance hears when it is ready for them, and
a step left waiting goes up the chain. Each email is keyed on the step's place in the expense's history,
so a step that happens again (corrected, approved again) is sent again."""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.expense import ExpenseRecord
from app.models.user import Users
from app.services.action_emails.core import Team, add, after_commit, send

logger = logging.getLogger(__name__)

MY_EXPENSES = "/my-expenses"
FINANCE_SCREEN = "/pnl?view=operations"


def _what(expense: ExpenseRecord) -> str:
    from app.services.expense_service import expense_dates_text

    return f"{expense.expense_category.lower()} expense of ${expense.amount_usd_cents / 100:,.2f} ({expense_dates_text(expense)})"


def _employee(expense: ExpenseRecord) -> Team:
    team: Team = {}
    add(team, expense.logged_by_user_id, "Logged by")
    return team


def _to_employee(db: Session, expense: ExpenseRecord, step: str, subject: str, opening: str,
                 details: Optional[List[str]] = None, actor_id: Optional[str] = None) -> int:
    return send(db, _employee(expense), actor_id=actor_id, key=f"expense-{step}-{expense.id}-{len(expense.edits)}",
                subject=subject, opening=opening, details=details or [], link_path=MY_EXPENSES,
                link_label="Open My Expenses")


def _check_lines(expense: ExpenseRecord) -> List[str]:
    from app.services.expense_receipt_service import check_notes

    return check_notes(expense)


@after_commit("expenses")
def notify_logged(db: Session, expense: ExpenseRecord) -> int:
    """Once its receipts are checked, so it says what the check found."""
    if expense.manager_approval_status == "APPROVED":
        return notify_auto_approved(db, expense)
    return _to_employee(db, expense, "logged", "Your expense is with your manager",
                        f"Your {_what(expense)} was logged and is waiting for your manager's review.", _check_lines(expense))


@after_commit("expenses")
def notify_auto_approved(db: Session, expense: ExpenseRecord) -> int:
    return _to_employee(db, expense, "auto-approved", "Your expense was approved: the receipts match",
                        f"Your {_what(expense)} was approved automatically because its receipts match. "
                        "It now counts in the P&L and is with Finance for payment.")


@after_commit("expenses")
def notify_approved(db: Session, expense: ExpenseRecord, *, approved_by: Optional[str]) -> int:
    return _to_employee(db, expense, "approved", "Your expense was approved",
                        f"Your manager approved your {_what(expense)}. It is now with Finance for payment.",
                        actor_id=approved_by)


@after_commit("expenses")
def notify_rejected(db: Session, expense: ExpenseRecord, *, rejected_by: Optional[str]) -> int:
    return _to_employee(db, expense, "rejected", "Your expense was rejected",
                        f"Your {_what(expense)} was rejected, so it won't be paid or count in the P&L. "
                        "You can correct it in My Expenses and it will go back for review.",
                        [f"Reason: {expense.manager_review_note}"] if expense.manager_review_note else [],
                        actor_id=rejected_by)


@after_commit("expenses")
def notify_returned(db: Session, expense: ExpenseRecord) -> int:
    return _to_employee(db, expense, "returned", "Your corrected expense is back with your manager",
                        f"Your {_what(expense)} changed, so your manager needs to review it again.", _check_lines(expense))


@after_commit("expenses")
def notify_finance_approved(db: Session, expense: ExpenseRecord, *, approved_by: Optional[str]) -> int:
    return _to_employee(db, expense, "finance-approved", "Finance approved your expense for payment",
                        f"Finance approved your {_what(expense)}. It will be marked paid once the payment is sent.",
                        actor_id=approved_by)


@after_commit("expenses")
def notify_paid(db: Session, expense: ExpenseRecord, *, paid_by: Optional[str]) -> int:
    return _to_employee(db, expense, "paid", "Your expense was paid",
                        f"Your {_what(expense)} has been marked as paid.", actor_id=paid_by)


@after_commit("expenses")
def notify_finance_ready(db: Session, expense: ExpenseRecord) -> int:
    """The people who can act, and the Finance inbox. The task has its own email to its assignee, so
    this is for everyone else in Finance."""
    from app.services.email_service import EmailService
    from app.services.expense_service import FINANCE_INBOX_EMAIL
    from app.services.invoice_service import invoice_approvers

    team: Team = {}
    for user in invoice_approvers(db, expense.tenant_id):
        add(team, user.UserID, "Finance")
    who = expense.logged_by_name or expense.logged_by_user_id
    opening = f"The {_what(expense)} from {who} is approved and waiting for Finance to approve it for payment."
    queued = send(db, team, actor_id=expense.logged_by_user_id, key=f"expense-finance-{expense.id}-{len(expense.edits)}",
                  subject=f"Expense ready for Finance: ${expense.amount_usd_cents / 100:,.2f} from {who}", opening=opening,
                  link_path=FINANCE_SCREEN, link_label="Open Finance Operations")
    EmailService.send_event_notification(to_email=FINANCE_INBOX_EMAIL, recipient_name="Finance", event_type="action_required",
                                         heading="Expense ready for Finance", message=opening)
    return queued


@after_commit("expenses")
def notify_escalated(db: Session, expense: ExpenseRecord, *, task_title: str, assignee: Optional[Users],
                     escalate_to: List[Users]) -> int:
    waiting_on = (assignee.UserName or assignee.UserEmail) if assignee else "nobody yet"
    team: Team = {}
    for user in escalate_to:
        add(team, user.UserID, "Escalation")
    queued = send(db, team, actor_id=None, key=f"expense-escalated-{expense.id}-{len(expense.edits)}",
                  subject=f"Overdue: {task_title}",
                  opening=f"\"{task_title}\" is overdue. It is waiting on {waiting_on}. Please see that it moves.",
                  details=[f"The {_what(expense)} from {expense.logged_by_name or expense.logged_by_user_id}."],
                  link_path=FINANCE_SCREEN)
    return queued + _to_employee(db, expense, "delayed", "Your expense is taking longer than expected",
                                 f"Your {_what(expense)} is waiting on {waiting_on} and has been escalated.")
