"""Invoice emails: drafted (generated), approved, sent, paid. The people on an invoice: its project's
manager and the client's team; a drafted invoice also goes to the invoice approver who would get
auto-invoicing's review task (the most junior Finance approver, invoice_service.invoice_approvers)."""
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.user import Users
from app.services.action_emails.core import Team, add, after_commit, client_team, merge, name_of, send

INVOICES_PATH = "/invoices"


def invoice_team(db: Session, invoice: Invoice) -> Team:
    team: Team = {}
    project = db.get(Project, invoice.project_id)
    if project is not None:
        add(team, project.manager_user_id, "Project Manager")
    merge(team, client_team(db, invoice.client_id))
    return team


def _label(db: Session, invoice: Invoice) -> str:
    client = db.get(Client, invoice.client_id)
    number = invoice.invoice_number or "draft"
    who = client.company_name if client is not None else invoice.client_id
    return f"{who} {number}, {invoice.billing_period_start} to {invoice.billing_period_end}"


def _total(invoice: Invoice) -> str:
    return f"Total: ${(invoice.total_usd_cents or 0) / 100:,.2f} (billed in {invoice.currency})."


def _send(db: Session, invoice: Invoice, team: Team, *, actor: Users, event: str, subject: str, opening: str) -> int:
    return send(db, team, actor_id=actor.UserID, key=f"invoice-{event}-{invoice.id}", subject=subject,
                opening=opening, details=[_total(invoice)], link_path=INVOICES_PATH, link_label="Open Invoices")


@after_commit("invoices")
def notify_invoice_drafted(db: Session, invoice: Invoice, *, actor: Users) -> int:
    from app.services.invoice_service import invoice_approvers

    team = invoice_team(db, invoice)
    approver = next((u for u in invoice_approvers(db, invoice.tenant_id) if u.UserID != actor.UserID), None)
    if approver is not None:
        add(team, approver.UserID, "Invoice Approver")
    label = _label(db, invoice)
    return _send(db, invoice, team, actor=actor, event="drafted", subject=f"Invoice drafted: {label}",
                 opening=f"{name_of(actor)} generated the draft invoice {label}; it needs Finance approval before it is sent.")


@after_commit("invoices")
def notify_invoice_approved(db: Session, invoice: Invoice, *, actor: Users) -> int:
    label = _label(db, invoice)
    return _send(db, invoice, invoice_team(db, invoice), actor=actor, event="approved",
                 subject=f"Invoice approved: {label}", opening=f"{name_of(actor)} approved the invoice {label}.")


@after_commit("invoices")
def notify_invoice_sent(db: Session, invoice: Invoice, *, actor: Users) -> int:
    label = _label(db, invoice)
    return _send(db, invoice, invoice_team(db, invoice), actor=actor, event="sent",
                 subject=f"Invoice sent: {label}", opening=f"{name_of(actor)} recorded the invoice {label} as sent to the client.")


@after_commit("invoices")
def notify_invoice_paid(db: Session, invoice: Invoice, *, actor: Users) -> int:
    label = _label(db, invoice)
    return _send(db, invoice, invoice_team(db, invoice), actor=actor, event="paid",
                 subject=f"Invoice paid: {label}", opening=f"{name_of(actor)} recorded the client's payment of {label}.")
