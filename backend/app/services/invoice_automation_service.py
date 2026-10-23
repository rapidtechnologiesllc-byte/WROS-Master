"""Auto-invoicing: last month's approved timesheets become a draft invoice, reviewed and
approved by Finance (Senior Manager or above -- CEO decision 2026-10-10), then emailed to the
client automatically the moment it is approved. No invoice leaves without that approval.

Daily (scheduled job auto_invoicing), for each project with timesheets in last month:
  - waits while any of those timesheets is not yet approved or is disputed (the
    timesheet reminders chase that); nothing is recorded, it is re-checked tomorrow
  - waits while a client that approves its own timesheets has not approved them yet, and gives
    Finance one task saying which weeks wait for the client (re-checked tomorrow)
  - hours dated after the end of the client PO they bill against: no invoice, a Finance task
    to get the PO extended (HELD)
  - generates the DRAFT invoice (approved hours x the allocation's bill rate)
  - flags anything the reviewer must look at:
      * an employee with more than MAX_WEEKLY_HOURS billable hours in a week
      * the total moved more than MAX_CHANGE_PCT against the project's previous invoice
      * the client has no ACCOUNTS contact to send it to
  - gives the review to the most junior Finance approver as a task (PENDING_REVIEW)
  - an employee with billable hours but no bill rate: no invoice, a task to fix it (HELD)
When Finance approves (POST /invoices/{id}/approve), send_after_approval queues the email
(exactly-once; the invoice becomes SENT only once the mail has really gone out).
One decision per project and period (invoice_automation_decisions), so it never drafts
or emails twice. The last AUTO_INVOICE_LOOKBACK_MONTHS months are considered, oldest first,
so a month whose timesheets were approved late is still invoiced; a month still waiting
when it is the oldest in the window is HELD with a Finance task instead of dropping out
unnoticed. Nothing goes to a client without Finance approval, so the lookback cannot
email an old backlog. Approved billable time on an allocation with no project (which can
never be invoiced) raises a Finance task too.
"""
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.models.invoice_automation import InvoiceAutomationDecision
from app.models.project import Project
from app.models.timesheet import Timesheet

logger = logging.getLogger(__name__)

MAX_WEEKLY_HOURS = 60
MAX_CHANGE_PCT = 50
AUTOMATION_ACTOR = "auto-invoicing"


def previous_month(today: date) -> Tuple[date, date]:
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def billing_months(today: date, lookback: Optional[int] = None) -> List[Tuple[date, date]]:
    """The last `lookback` complete months, oldest first."""
    from app.core.config import settings

    months, anchor = [], today
    for _ in range(max(1, lookback or settings.AUTO_INVOICE_LOOKBACK_MONTHS)):
        start, end = previous_month(anchor)
        months.insert(0, (start, end))
        anchor = start
    return months


def _projects_with_time(db: Session, start: date, end: date) -> List[str]:
    rows = db.query(EmployeeAllocation.project_id).join(
        Timesheet, Timesheet.allocation_id == EmployeeAllocation.id).filter(
        Timesheet.week_starting_date >= start - timedelta(days=6), Timesheet.week_starting_date <= end,
        EmployeeAllocation.project_id.isnot(None)).distinct().all()
    return [r[0] for r in rows]


def _flag_time_without_project(db: Session, start: date, end: date) -> int:
    """Approved billable time on an allocation with no project can never be invoiced:
    give Finance a task (once per allocation) instead of letting the revenue leak silently."""
    from app.models.client import Client
    from app.models.employee import Employee

    rows = db.query(EmployeeAllocation).join(Timesheet, Timesheet.allocation_id == EmployeeAllocation.id).filter(
        EmployeeAllocation.project_id.is_(None), Timesheet.status == "APPROVED", Timesheet.billable_hours > 0,
        Timesheet.week_starting_date >= start - timedelta(days=6), Timesheet.week_starting_date <= end,
    ).distinct().all()
    raised = 0
    for allocation in rows:
        employee = db.get(Employee, allocation.employee_id)
        client = db.get(Client, allocation.client_id) if allocation.client_id else None
        who = f"{employee.first_name} {employee.last_name or ''}".strip() if employee else allocation.employee_id
        title = f"Billable time not invoiceable: {who} has no project ({allocation.id[:8]})"
        if _open_task(db, title):
            continue
        _finance_task(db, allocation.tenant_id, title, [
            f"{who} has approved billable hours at {client.company_name if client else 'a client'} on allocation "
            f"{allocation.id}, which is not linked to a project, so it can never be invoiced.",
            "Link the allocation (or its job) to the client's project; auto-invoicing then bills it."])
        raised += 1
    if raised:
        db.commit()
    return raised


def _open_task(db: Session, title: str) -> bool:
    from app.models.task import Task

    return db.query(Task.id).filter(Task.title == title, Task.category == "FINANCE",
                                    Task.status.notin_(("COMPLETED", "CANCELLED"))).first() is not None


def _close_waiting_task(db: Session, title: str) -> None:
    """The client approved since: the 'waiting for the client' task is done."""
    from datetime import datetime

    from app.models.task import Task

    for task in db.query(Task).filter(Task.title == title, Task.category == "FINANCE",
                                      Task.status.notin_(("COMPLETED", "CANCELLED"))).all():
        task.status, task.completed_at = "COMPLETED", datetime.utcnow()


def anomalies(db: Session, invoice: Invoice) -> List[str]:
    from app.models.invoice import InvoiceLineItem

    reasons = []

    for line in db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all():
        if float(line.hours or 0) > MAX_WEEKLY_HOURS:
            reasons.append(f"employee {line.employee_id} billed {float(line.hours):g}h in one week "
                           f"(more than {MAX_WEEKLY_HOURS}h)")
    previous = db.query(Invoice).filter(Invoice.project_id == invoice.project_id, Invoice.id != invoice.id) \
        .order_by(Invoice.billing_period_end.desc()).first()
    if previous is not None and previous.total_usd_cents:
        change = abs(invoice.total_usd_cents - previous.total_usd_cents) * 100 / previous.total_usd_cents
        if change > MAX_CHANGE_PCT:
            reasons.append(f"total changed {change:.0f}% against the previous invoice "
                           f"({previous.total_usd_cents / 100:.2f} -> {invoice.total_usd_cents / 100:.2f})")
    return reasons


def _finance_task(db: Session, tenant_id: Optional[int], title: str, reasons: List[str]) -> None:
    from app.services.invoice_service import invoice_approvers
    from app.services.task_service import create_task

    approvers = invoice_approvers(db, tenant_id)
    assignee = approvers[0].UserID if approvers else None
    create_task(db, title=title, description="\n".join(reasons), priority="HIGH", tenant_id=tenant_id,
                category="FINANCE", assigned_to_user_id=assignee,
                visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if assignee else "ORG_WIDE")


def _decide(db: Session, project: Project, start: date, end: date, decision: str, reasons: List[str],
            invoice: Optional[Invoice] = None) -> InvoiceAutomationDecision:
    row = InvoiceAutomationDecision(tenant_id=project.tenant_id, project_id=project.id, period_start=start,
                                    period_end=end, invoice_id=invoice.id if invoice else None, decision=decision,
                                    reasons=reasons or None)
    db.add(row)
    return row


def invoice_project(db: Session, project: Project, start: date, end: date) -> str:
    """One project, one period. Commits. Returns the outcome."""
    from app.services import invoice_service as invoices

    if db.query(InvoiceAutomationDecision.id).filter(InvoiceAutomationDecision.project_id == project.id,
                                                      InvoiceAutomationDecision.period_start == start).first():
        return "decided"
    try:
        invoice = invoices.generate_invoice(db, project, period_start=start, period_end=end, tenant_id=project.tenant_id)
    except invoices.NothingToInvoice:
        return "nothing"
    except (invoices.UnapprovedTimesheetBlocksInvoice, invoices.OpenDisputeBlocksInvoice) as exc:
        db.rollback()
        return f"waiting: {exc}"
    except invoices.ClientApprovalMissing as exc:
        db.rollback()
        title = f"Waiting for client timesheet approval: {project.name} {start:%b %Y}"
        if not _open_task(db, title):
            _finance_task(db, project.tenant_id, title, [
                str(exc), "", "The invoice is drafted automatically as soon as the client has approved every week."])
            db.commit()
        return f"waiting: {exc}"
    except invoices.AlreadyInvoiced as exc:
        db.rollback()
        _decide(db, project, start, end, "SKIPPED", [str(exc)])
        db.commit()
        return "skipped"
    except (invoices.MissingBillRate, invoices.PurchaseOrderExpired) as exc:
        db.rollback()
        _decide(db, project, start, end, "HELD", [str(exc)])
        _finance_task(db, project.tenant_id, f"Invoice held: {project.name} {start:%b %Y}", [str(exc)])
        db.commit()
        return "held"
    if not invoice.total_usd_cents:
        db.rollback()
        return "nothing"

    flags = anomalies(db, invoice)
    try:
        invoices.billing_contact_email(db, invoice.client_id)
    except invoices.MissingBillingContact as exc:
        flags.append(str(exc))
    _decide(db, project, start, end, "PENDING_REVIEW", flags, invoice)
    _close_waiting_task(db, f"Waiting for client timesheet approval: {project.name} {start:%b %Y}")
    total = f"{(invoice.total_usd_cents or 0) / 100:,.2f} {invoice.currency or 'USD'}"
    lines = [f"Draft invoice {invoice.id} for {project.name}, {start:%d %b} - {end:%d %b %Y}: {total}.",
             "Review it in Invoices and approve it; it is emailed to the client as soon as you approve."]
    if flags:
        lines += ["", "Check before approving:"] + [f"- {f}" for f in flags]
    _finance_task(db, project.tenant_id, f"Approve invoice: {project.name} {start:%b %Y}", lines)
    db.commit()
    logger.info(f"[AutoInvoice] {project.id} {start} draft {invoice.id} awaiting Finance approval; flags={flags}")
    return "awaiting"


def send_after_approval(db: Session, invoice: Invoice, approved_by: str) -> bool:
    """Called once Finance approved an invoice: if auto-invoicing drafted it, email it now.
    A client with no ACCOUNTS contact is left for Finance to send by hand. Returns sent?"""
    from app.services import invoice_service as invoices

    decision = db.query(InvoiceAutomationDecision).filter(InvoiceAutomationDecision.invoice_id == invoice.id,
                                                          InvoiceAutomationDecision.decision == "PENDING_REVIEW").first()
    if decision is None or invoice.status != "APPROVED":
        return False
    try:
        invoices.request_invoice_email(db, invoice, requested_by=approved_by)  # commits; queued exactly once
    except invoices.MissingBillingContact:
        logger.warning(f"[AutoInvoice] {invoice.id} approved but the client has no ACCOUNTS contact; not sent")
        return False
    decision.decision = "SENT"
    db.commit()
    return True


def _hold_overdue(db: Session, project: Project, start: date, end: date, reason: str) -> None:
    """The oldest month in the window is still waiting: stop waiting silently, hand it to Finance."""
    _decide(db, project, start, end, "HELD", [f"still not invoiceable after the lookback window: {reason}"])
    _finance_task(db, project.tenant_id, f"Invoice overdue: {project.name} {start:%b %Y}", [
        f"{project.name} has time in {start:%B %Y} that could not be invoiced automatically: {reason}",
        "Resolve it (approve the timesheets / close the dispute), then generate the invoice in Invoices."])
    db.commit()


def run_auto_invoicing(db: Session, today: Optional[date] = None) -> Dict:
    months = billing_months(today or date.today())
    result = {"period": f"{months[0][0]}..{months[-1][1]}", "awaiting": 0, "held": 0, "waiting": 0, "skipped": 0,
              "failed": 0, "unlinked": 0}
    for start, end in months:
        for project_id in _projects_with_time(db, start, end):
            project = db.query(Project).filter(Project.id == project_id).first()
            if project is None:
                continue
            try:
                outcome = invoice_project(db, project, start, end)
                if outcome.startswith("waiting") and (start, end) == months[0] and len(months) > 1:
                    _hold_overdue(db, project, start, end, outcome.split(":", 1)[1].strip())
                    outcome = "held"
            except Exception as exc:
                db.rollback()
                result["failed"] += 1
                logger.error(f"[AutoInvoice] project {project_id} {start} failed: {exc}", exc_info=True)
                continue
            key = outcome.split(":")[0]
            if key in result:
                result[key] += 1
    result["unlinked"] = _flag_time_without_project(db, months[0][0], months[-1][1])
    logger.info(f"[AutoInvoice] {result}")
    return result


def backlog_guard(db: Session, now) -> int:
    """Nothing to expire: older months are bounded by AUTO_INVOICE_LOOKBACK_MONTHS, and every
    draft waits for Finance approval before anything reaches a client."""
    return 0
