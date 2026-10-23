"""
EPIC-16 -- AR Follow-Up. Real, derived aging report over the already-
real Invoice table (no new "receivables" table -- an unpaid SENT
invoice already IS the receivable). trigger_ar_follow_up() reuses the
exact Task+notify pattern already proven live for expense approvals
(Task.invoice_id, same polymorphic-lite posture as Task.expense_id) --
not a new mechanism.
"""
from datetime import date, datetime
import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.task import Task
from app.models.user import Users
from app.services.notification_service import ChannelNotConfigured, send_notification
from app.services.task_service import create_task

logger = logging.getLogger(__name__)

def scan_overdue_invoices(
    db: Session, *, tenant_id: Optional[int] = None, now: Optional[datetime] = None,
) -> List[dict]:
    """SENT invoices past their due date (sent date + the client's payment terms, stored on the
    invoice when it was sent) and still not PAID -- the real aging list, most overdue first. A net-60
    client is not chased on day 31, a net-15 client is chased on day 16."""
    today = (now or datetime.utcnow()).date()
    query = db.query(Invoice).filter(Invoice.status == "SENT", Invoice.due_date.isnot(None), Invoice.due_date < today)
    if tenant_id is not None:
        query = query.filter(Invoice.tenant_id == tenant_id)

    rows = []
    for invoice in query.order_by(Invoice.due_date.asc()).all():
        rows.append({
            "invoice_id": invoice.id, "invoice_number": invoice.invoice_number, "client_id": invoice.client_id,
            "total_usd_cents": invoice.total_usd_cents, "sent_at": invoice.sent_at, "due_date": invoice.due_date,
            "days_overdue": (today - invoice.due_date).days,
        })
    return rows


def aging_buckets() -> List[Tuple[str, int, Optional[int]]]:
    """[(label, from_days, to_days)] past due, from settings.AR_AGING_BUCKET_DAYS ("30,60,90" ->
    current, 1-30, 31-60, 61-90, 90+)."""
    from app.core.config import settings

    edges = sorted({int(x) for x in settings.AR_AGING_BUCKET_DAYS.split(",") if x.strip()})
    if not edges or edges[0] <= 0:
        raise ValueError(f"AR_AGING_BUCKET_DAYS must be positive day counts, got {settings.AR_AGING_BUCKET_DAYS!r}")
    buckets, low = [("current", None, 0)], 1
    for edge in edges:
        buckets.append((f"{low}-{edge}", low, edge))
        low = edge + 1
    buckets.append((f"{edges[-1]}+", low, None))
    return buckets


def _bucket_for(days_past_due: int, buckets) -> str:
    for label, low, high in buckets:
        if low is None:
            if days_past_due <= high:
                return label
        elif days_past_due >= low and (high is None or days_past_due <= high):
            return label
    raise ValueError(f"No AR aging bucket for {days_past_due} days past due")


def ar_aging(db: Session, invoices: List[Invoice], *, today: Optional[date] = None) -> Dict:
    """Unpaid SENT invoices aged by due date, per client: bucket totals (USD cents) and the
    invoices in each. `invoices` is the caller's already-scoped list of SENT invoices."""
    today = today or datetime.utcnow().date()
    buckets = aging_buckets()
    labels = [b[0] for b in buckets]
    clients = {c.id: c for c in db.query(Client).filter(Client.id.in_({i.client_id for i in invoices}))} if invoices else {}
    by_client: Dict[str, Dict] = {}
    totals = {label: 0 for label in labels}
    for invoice in invoices:
        if invoice.status != "SENT":
            continue
        if invoice.due_date is None:
            raise ValueError(f"Sent invoice {invoice.id} has no due date")
        days = (today - invoice.due_date).days
        label = _bucket_for(days, buckets)
        client = clients.get(invoice.client_id)
        row = by_client.setdefault(invoice.client_id, {
            "client_id": invoice.client_id, "client_name": client.company_name if client else invoice.client_id,
            "payment_terms_days": client.payment_terms_days if client else None,
            "buckets": {lb: 0 for lb in labels}, "total_usd_cents": 0, "invoices": []})
        amount = invoice.total_usd_cents or 0
        row["buckets"][label] += amount
        row["total_usd_cents"] += amount
        totals[label] += amount
        row["invoices"].append({"invoice_id": invoice.id, "invoice_number": invoice.invoice_number,
                                "project_id": invoice.project_id, "total_usd_cents": amount,
                                "sent_at": invoice.sent_at.isoformat() if invoice.sent_at else None,
                                "due_date": invoice.due_date.isoformat(), "days_past_due": max(days, 0),
                                "bucket": label})
    clients_out = sorted(by_client.values(), key=lambda r: (-r["total_usd_cents"], r["client_name"]))
    return {"as_of": today.isoformat(), "buckets": labels, "totals": totals,
            "total_usd_cents": sum(totals.values()), "clients": clients_out}


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
    if client and client.account_manager_user_id:
        assigned_to_user_id = client.account_manager_user_id
    elif client and client.account_manager_employee_id:
        employee = db.query(Employee).filter(Employee.id == client.account_manager_employee_id).first()
        if employee:
            user = db.query(Users).filter(Users.UserEmail == employee.email).first()
            assigned_to_user_id = user.UserID if user else None

    days_overdue = (datetime.utcnow().date() - invoice.due_date).days if invoice.due_date else None
    client_name = client.company_name if client else invoice.client_id
    number = invoice.invoice_number or invoice.id
    task = create_task(
        db, title=f"AR follow-up: {client_name} invoice {number} overdue ({days_overdue}d)",
        description=f"Invoice {number} for {client_name}, ${invoice.total_usd_cents / 100:,.2f}, sent {invoice.sent_at}, "
                    f"due {invoice.due_date} ({client.payment_terms_days if client else '?'}-day terms), still unpaid.",
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
                    message=f"Invoice {number} for {client_name} (${invoice.total_usd_cents / 100:,.2f}) is {days_overdue} days past its due date -- follow up.",
                )
            except ChannelNotConfigured as exc:
                # the task is the follow-up; the extra notification is optional and its channel is off
                logger.warning(f"[ARFollowUp] invoice {invoice.id}: no notification channel for {user.UserID}: {exc}")

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
    processed, failed = 0, []
    for row in scan_overdue_invoices(db):
        invoice = db.query(Invoice).filter(Invoice.id == row["invoice_id"]).first()
        if invoice is None:
            continue
        try:
            trigger_ar_follow_up(db, invoice)
            db.commit()
            processed += 1
        except Exception as exc:
            # One invoice (e.g. NULL tenant -> cross-tenant notification refusal) must not abort the run
            db.rollback()
            logger.error(f"[ARFollowUp] invoice {row['invoice_id']} failed: {exc}", exc_info=True)
            failed.append(row["invoice_id"])
    return {"processed": processed, "failed": len(failed), "failed_invoice_ids": failed[:50]}
