"""
EPIC-16 -- AR Follow-Up. Real, derived aging report over the already-
real Invoice table (no new "receivables" table -- an unpaid SENT
invoice already IS the receivable). trigger_ar_follow_up() reuses the
exact Task+notify pattern already proven live for expense approvals
(Task.invoice_id, same polymorphic-lite posture as Task.expense_id) --
not a new mechanism.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.task import Task
from app.models.user import Users
from app.services.notification_service import ChannelNotConfigured, send_notification
from app.services.task_service import create_task

DEFAULT_AR_GRACE_DAYS = 30


def scan_overdue_invoices(
    db: Session, *, grace_days: int = DEFAULT_AR_GRACE_DAYS, tenant_id: Optional[int] = None, now: Optional[datetime] = None,
) -> List[dict]:
    """SENT invoices whose sent_at is older than grace_days and still
    haven't moved to PAID -- the real aging list, sorted oldest first
    (the ones most overdue need attention first)."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=grace_days)

    query = db.query(Invoice).filter(Invoice.status == "SENT", Invoice.sent_at.isnot(None), Invoice.sent_at <= cutoff)
    if tenant_id is not None:
        query = query.filter(Invoice.tenant_id == tenant_id)

    rows = []
    for invoice in query.order_by(Invoice.sent_at.asc()).all():
        days_overdue = (now - invoice.sent_at).days
        rows.append({
            "invoice_id": invoice.id, "client_id": invoice.client_id,
            "total_usd_cents": invoice.total_usd_cents, "sent_at": invoice.sent_at, "days_overdue": days_overdue,
        })
    return rows


def trigger_ar_follow_up(db: Session, invoice: Invoice) -> Task:
    """Idempotent -- one open (not COMPLETED/CANCELLED) Task per
    invoice; re-scanning never creates duplicates. Assigned to the
    client's account manager when one is on file (resolved Employee ->
    Users by email, the only shared key between those two tables, same
    resolution already used for BU Head/HR Manager auto-assignment);
    left unassigned (still created, still visible on the org-wide Task
    Dashboard) when no account manager is set, rather than silently
    skipping the follow-up."""
    existing = (
        db.query(Task)
        .filter(Task.invoice_id == invoice.id, Task.status.notin_(("COMPLETED", "CANCELLED")))
        .first()
    )
    if existing:
        return existing

    client = db.query(Client).filter(Client.id == invoice.client_id).first()
    assigned_to_user_id = None
    if client and client.account_manager_employee_id:
        employee = db.query(Employee).filter(Employee.id == client.account_manager_employee_id).first()
        if employee:
            user = db.query(Users).filter(Users.UserEmail == employee.email).first()
            assigned_to_user_id = user.UserID if user else None

    days_overdue = (datetime.utcnow() - invoice.sent_at).days if invoice.sent_at else None
    client_name = client.company_name if client else invoice.client_id
    task = create_task(
        db, title=f"AR follow-up: {client_name} invoice overdue ({days_overdue}d)",
        description=f"Invoice {invoice.id} for {client_name}, ${invoice.total_usd_cents / 100:,.2f}, sent {invoice.sent_at}, still unpaid.",
        priority="HIGH" if days_overdue and days_overdue >= 60 else "MEDIUM",
        category="AR_FOLLOW_UP", assigned_to_user_id=assigned_to_user_id, invoice_id=invoice.id,
        tenant_id=invoice.tenant_id,
    )

    if assigned_to_user_id:
        user = db.query(Users).filter(Users.UserID == assigned_to_user_id).first()
        if user:
            try:
                send_notification(
                    db, calling_context_tenant_id=invoice.tenant_id, recipient=user, priority_tier="P2",
                    message=f"Invoice for {client_name} (${invoice.total_usd_cents / 100:,.2f}) is {days_overdue} days overdue -- follow up.",
                )
            except ChannelNotConfigured:
                pass

    return task


def run_ar_follow_up_job(db: Session) -> dict:
    """Scheduler wrapper, 2026-08-06 -- this logic existed and was fully
    tested (scan_overdue_invoices/trigger_ar_follow_up) but was never
    actually registered in app.core.scheduler, so it only ever ran when
    someone manually hit the /invoices/ar/aging + /invoices/{id}/ar/
    follow-up endpoints. Runs org-wide -- scan_overdue_invoices with no
    tenant_id filter, trigger_ar_follow_up already stamps each Task with
    the invoice's own tenant_id. Idempotent (trigger_ar_follow_up returns
    the existing open Task rather than duplicating), safe to re-run on
    every scheduler tick."""
    processed = 0
    for row in scan_overdue_invoices(db):
        invoice = db.query(Invoice).filter(Invoice.id == row["invoice_id"]).first()
        if invoice:
            trigger_ar_follow_up(db, invoice)
            processed += 1
    return {"processed": processed}
