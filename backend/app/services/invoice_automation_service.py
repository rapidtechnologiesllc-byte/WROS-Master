"""Auto-invoicing: last month's approved timesheets become a draft invoice, reviewed and
approved by Finance (Senior Manager or above -- CEO decision 2026-10-10), then emailed to the
client automatically the moment it is approved. No invoice leaves without that approval.

Daily (scheduled job auto_invoicing), for each project with timesheets in last month:
  - waits while any of those timesheets is not yet approved or is disputed (the
    timesheet reminders chase that); nothing is recorded, it is re-checked tomorrow
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
or emails twice. Only last month is considered, so enabling it never bills an old backlog.
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


def _projects_with_time(db: Session, start: date, end: date) -> List[str]:
    rows = db.query(EmployeeAllocation.project_id).join(
        Timesheet, Timesheet.allocation_id == EmployeeAllocation.id).filter(
        Timesheet.week_starting_date >= start, Timesheet.week_starting_date <= end,
        EmployeeAllocation.project_id.isnot(None)).distinct().all()
    return [r[0] for r in rows]


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


def _finance_task(db: Session, project: Project, title: str, reasons: List[str]) -> None:
    from app.services.invoice_service import invoice_approvers
    from app.services.task_service import create_task

    approvers = invoice_approvers(db, project.tenant_id)
    assignee = approvers[0].UserID if approvers else None
    create_task(db, title=title, description="\n".join(reasons), priority="HIGH", tenant_id=project.tenant_id,
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
    except invoices.AlreadyInvoiced as exc:
        db.rollback()
        _decide(db, project, start, end, "SKIPPED", [str(exc)])
        db.commit()
        return "skipped"
    except invoices.MissingBillRate as exc:
        db.rollback()
        _decide(db, project, start, end, "HELD", [str(exc)])
        _finance_task(db, project, f"Invoice held: {project.name} {start:%b %Y}", [str(exc)])
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
    total = f"{(invoice.total_usd_cents or 0) / 100:,.2f} {invoice.currency or 'USD'}"
    lines = [f"Draft invoice {invoice.id} for {project.name}, {start:%d %b} - {end:%d %b %Y}: {total}.",
             "Review it in Invoices and approve it; it is emailed to the client as soon as you approve."]
    if flags:
        lines += ["", "Check before approving:"] + [f"- {f}" for f in flags]
    _finance_task(db, project, f"Approve invoice: {project.name} {start:%b %Y}", lines)
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


def run_auto_invoicing(db: Session, today: Optional[date] = None) -> Dict:
    start, end = previous_month(today or date.today())
    result = {"period": f"{start}..{end}", "awaiting": 0, "held": 0, "waiting": 0, "skipped": 0, "failed": 0}
    for project_id in _projects_with_time(db, start, end):
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            continue
        try:
            outcome = invoice_project(db, project, start, end)
        except Exception as exc:
            db.rollback()
            result["failed"] += 1
            logger.error(f"[AutoInvoice] project {project_id} failed: {exc}", exc_info=True)
            continue
        key = outcome.split(":")[0]
        if key in result:
            result[key] += 1
    logger.info(f"[AutoInvoice] {result}")
    return result


def backlog_guard(db: Session, now) -> int:
    """Only the month that just ended is ever invoiced, so there is no backlog to expire."""
    return 0
