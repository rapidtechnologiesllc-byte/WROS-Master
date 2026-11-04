"""Sub-vendor invoices and pay-when-paid (CEO 2026-11-02: "we need to make sure we got the payment
from the client and then initiate the payment to the sub vendor"; "make sure it is connected to the
full P&L"; contractors "will still be filling timesheet but only have limited access").

The chain: a contractor (employment type CONTRACT, Employee.sub_vendor_id, an hourly vendor rate)
fills timesheets -> approved -> billed to the client (InvoiceLineItem per timesheet) -> the vendor
invoices us for the same timesheets (VendorInvoiceLine per timesheet) -> Finance approves -> the
client pays -> only then can the vendor be paid. The vendor invoice lines are the contractor's
delivery cost in the P&L (revenue_chain_service); payroll never is (a contractor has none).

Rules (rules only, no model):
- Every line is an APPROVED timesheet of one of the vendor's contractors in the invoice period,
  not on another live (not rejected) vendor invoice; the line is hours x the vendor rate.
- The vendor's amount may differ from the expected amount (hours x rate): it is kept and the
  difference is shown; approving a difference needs a note.
- Pay: only APPROVED invoices, and only when every timesheet on it is on a PAID client invoice.
  When a client payment makes a vendor invoice payable, its approver (else its creator) gets a task.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.sub_vendor import SubVendorAccount
from app.models.timesheet import Timesheet
from app.models.user import Users
from app.models.vendor_invoice import VendorInvoice, VendorInvoiceLine

logger = logging.getLogger(__name__)

LIVE_STATUSES = ("RECEIVED", "APPROVED", "PAID")
CONTRACTOR_ROLE = "Contractor"


class VendorInvoiceError(ValueError):
    """A vendor-invoice rule was not met; the message says which and what to do."""


def create_sub_vendor(db: Session, user: Users, *, company_name: str, contact_email: str,
                      contact_phone: Optional[str] = None, tax_id: Optional[str] = None) -> SubVendorAccount:
    """A supplier added by Finance is approved at once (they vetted it). Flushes."""
    from app.services.sub_vendor_service import approve_sub_vendor, register_sub_vendor

    name, email = (company_name or "").strip(), (contact_email or "").strip().lower()
    if not name or "@" not in email:
        raise VendorInvoiceError("A sub-vendor needs a company name and a contact email.")
    if db.query(SubVendorAccount.id).filter(SubVendorAccount.tenant_id == user.tenant_id,
                                            SubVendorAccount.company_name.ilike(name)).first():
        raise VendorInvoiceError(f"A sub-vendor named {name} already exists.")
    account = register_sub_vendor(db, tenant_id=user.tenant_id, company_name=name, contact_email=email,
                                  contact_phone=contact_phone, tax_id=tax_id)
    db.flush()
    approve_sub_vendor(db, account, approved_by=user.UserID)
    db.flush()
    return account


def set_contractor(db: Session, user: Users, employee: Employee, *, sub_vendor_id: str,
                   hourly_rate_usd_cents: int) -> Employee:
    """Make the employee a contractor supplied by this vendor at this hourly rate. Their login (if
    any) moves to the Contractor role, so their access is that role's set only. Flushes."""
    from app.models.org_structure import OrgRole
    from app.models.role_template import RoleTemplate
    from app.services.role_template_permission_service import invalidate_permissions

    vendor = db.query(SubVendorAccount).filter(SubVendorAccount.id == sub_vendor_id,
                                               SubVendorAccount.tenant_id == employee.tenant_id).first()
    if vendor is None:
        raise VendorInvoiceError("Choose a sub-vendor of this organisation.")
    if vendor.status != "APPROVED":
        raise VendorInvoiceError(f"{vendor.company_name} is {vendor.status.lower()}: approve it first.")
    if not hourly_rate_usd_cents or hourly_rate_usd_cents <= 0:
        raise VendorInvoiceError("Enter the hourly rate paid to the vendor.")
    employee.employment_type, employee.sub_vendor_id = "CONTRACT", vendor.id
    employee.vendor_hourly_rate_usd_cents = hourly_rate_usd_cents
    if employee.wros_user_id:
        login = db.query(Users).filter(Users.UserID == employee.wros_user_id).first()
        role = db.query(OrgRole).filter(OrgRole.tenant_id == employee.tenant_id, OrgRole.name == CONTRACTOR_ROLE).first()
        template = db.get(RoleTemplate, role.role_template_id) if role and role.role_template_id else None
        if template is None:
            raise VendorInvoiceError("The Contractor role is missing; restart the backend to create it.")
        if login is not None:
            login.job_title, login.role_template_id = role.name, template.id
            invalidate_permissions()
    db.flush()
    logger.info(f"[VendorInvoice] {employee.id} is a contractor of {vendor.company_name} at {hourly_rate_usd_cents}c/h")
    return employee


def _invoiced_timesheets(db: Session, timesheet_ids: Iterable[str], *, exclude: Optional[str] = None) -> set:
    query = db.query(VendorInvoiceLine.timesheet_id).join(VendorInvoice).filter(
        VendorInvoiceLine.timesheet_id.in_(list(timesheet_ids)), VendorInvoice.status.in_(LIVE_STATUSES))
    if exclude:
        query = query.filter(VendorInvoice.id != exclude)
    return {t for (t,) in query}


def billable_timesheets(db: Session, sub_vendor_id: str, start: date, end: date,
                        employee_ids: Optional[List[str]] = None) -> List[Dict]:
    """Approved timesheets of the vendor's contractors (employee_ids: only these) with a week in
    [start, end] that no live vendor invoice covers yet, each with the amount it should be invoiced at."""
    query = (db.query(Timesheet, Employee).join(Employee, Employee.id == Timesheet.employee_id)
             .filter(Employee.sub_vendor_id == sub_vendor_id, Timesheet.status == "APPROVED",
                     Timesheet.week_starting_date >= start, Timesheet.week_starting_date <= end))
    if employee_ids is not None:
        query = query.filter(Employee.id.in_(employee_ids))
    rows = query.order_by(Timesheet.week_starting_date).all()
    taken = _invoiced_timesheets(db, (t.id for t, _ in rows))
    out = []
    for ts, employee in rows:
        if ts.id in taken or not ts.billable_hours:
            continue
        rate = employee.vendor_hourly_rate_usd_cents
        if not rate:
            raise VendorInvoiceError(f"{employee.first_name} {employee.last_name} has no vendor rate: set it first.")
        out.append({"timesheet_id": ts.id, "employee_id": employee.id,
                    "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
                    "week_starting_date": ts.week_starting_date.isoformat(), "hours": float(ts.billable_hours),
                    "rate_usd_cents": rate, "amount_usd_cents": round(Decimal(ts.billable_hours) * rate)})
    return out


def create_vendor_invoice(db: Session, user: Users, *, sub_vendor_id: str, vendor_invoice_number: str,
                          invoice_date: date, period_start: date, period_end: date, amount_usd_cents: int,
                          note: Optional[str] = None, employee_ids: Optional[List[str]] = None) -> VendorInvoice:
    """Record the vendor's invoice against the approved timesheets it covers. Flushes."""
    vendor = db.query(SubVendorAccount).filter(SubVendorAccount.id == sub_vendor_id,
                                               SubVendorAccount.tenant_id == user.tenant_id).first()
    if vendor is None:
        raise VendorInvoiceError("Choose a sub-vendor of this organisation.")
    number = (vendor_invoice_number or "").strip()
    if not number:
        raise VendorInvoiceError("Enter the vendor's invoice number.")
    if period_end < period_start:
        raise VendorInvoiceError("The period ends before it starts.")
    if invoice_date > date.today():
        raise VendorInvoiceError("The invoice date cannot be in the future.")
    if amount_usd_cents is None or amount_usd_cents <= 0:
        raise VendorInvoiceError("Enter the invoice amount.")
    if db.query(VendorInvoice.id).filter(VendorInvoice.sub_vendor_id == vendor.id,
                                         VendorInvoice.vendor_invoice_number == number).first():
        raise VendorInvoiceError(f"{vendor.company_name} invoice {number} is already recorded.")
    lines = billable_timesheets(db, vendor.id, period_start, period_end, employee_ids)
    if not lines:
        raise VendorInvoiceError(f"No approved, not yet invoiced timesheets of {vendor.company_name}'s contractors "
                                 f"between {period_start:%d %b %Y} and {period_end:%d %b %Y}.")
    invoice = VendorInvoice(tenant_id=user.tenant_id, sub_vendor_id=vendor.id, vendor_invoice_number=number,
                            invoice_date=invoice_date, period_start=period_start, period_end=period_end,
                            amount_usd_cents=amount_usd_cents, expected_usd_cents=sum(l["amount_usd_cents"] for l in lines),
                            note=(note or "").strip() or None, created_by=user.UserID, status="RECEIVED")
    db.add(invoice)
    db.flush()
    db.add_all(VendorInvoiceLine(vendor_invoice_id=invoice.id, employee_id=l["employee_id"],
                                 timesheet_id=l["timesheet_id"], hours=l["hours"], rate_usd_cents=l["rate_usd_cents"],
                                 amount_usd_cents=l["amount_usd_cents"]) for l in lines)
    db.flush()
    return invoice


def payment_readiness(db: Session, invoice: VendorInvoice) -> Dict:
    """{ready, blockers}: every timesheet on the vendor invoice must be on a PAID client invoice."""
    lines = db.query(VendorInvoiceLine).filter(VendorInvoiceLine.vendor_invoice_id == invoice.id).all()
    billed = defaultdict(list)
    for item, client_invoice in (db.query(InvoiceLineItem, Invoice).join(Invoice, Invoice.id == InvoiceLineItem.invoice_id)
                                 .filter(InvoiceLineItem.timesheet_id.in_([l.timesheet_id for l in lines])).all()):
        billed[item.timesheet_id].append(client_invoice)
    not_invoiced, unpaid = 0, {}
    for line in lines:
        invoices = billed.get(line.timesheet_id, [])
        if not invoices:
            not_invoiced += 1
        elif not any(i.status == "PAID" for i in invoices):
            current = invoices[0]
            unpaid[current.id] = f"{current.invoice_number or current.id[:8]} ({current.status.lower()})"
    blockers = []
    if not_invoiced:
        blockers.append(f"{not_invoiced} timesheet(s) not yet invoiced to the client")
    if unpaid:
        blockers.append("client invoice(s) not yet paid: " + ", ".join(sorted(unpaid.values())))
    return {"ready": bool(lines) and not blockers, "blockers": blockers}


def approve_vendor_invoice(db: Session, user: Users, invoice: VendorInvoice, *, note: Optional[str] = None) -> VendorInvoice:
    if invoice.status != "RECEIVED":
        raise VendorInvoiceError(f"Only a received invoice can be approved; this one is {invoice.status.lower()}.")
    if invoice.amount_usd_cents != invoice.expected_usd_cents and not (note or invoice.note or "").strip():
        raise VendorInvoiceError("The vendor's amount differs from approved hours x rate: add a note explaining why.")
    if note and note.strip():
        invoice.note = note.strip()
    invoice.status, invoice.approved_by, invoice.approved_at = "APPROVED", user.UserID, datetime.utcnow()
    db.flush()
    return invoice


def reject_vendor_invoice(db: Session, user: Users, invoice: VendorInvoice, *, reason: str) -> VendorInvoice:
    """Rejected invoices free their timesheets for a corrected invoice."""
    if invoice.status not in ("RECEIVED", "APPROVED"):
        raise VendorInvoiceError(f"A {invoice.status.lower()} invoice cannot be rejected.")
    if not (reason or "").strip():
        raise VendorInvoiceError("Say why the invoice is rejected.")
    invoice.status, invoice.rejected_reason = "REJECTED", reason.strip()
    db.flush()
    return invoice


def pay_vendor_invoice(db: Session, user: Users, invoice: VendorInvoice, *, paid_on: date,
                       reference: str) -> VendorInvoice:
    """Pay-when-paid: refused until the client has paid for every timesheet on it."""
    if invoice.status != "APPROVED":
        raise VendorInvoiceError(f"Only an approved invoice can be paid; this one is {invoice.status.lower()}.")
    if not (reference or "").strip():
        raise VendorInvoiceError("Enter the payment reference (bank transfer id).")
    if paid_on > date.today():
        raise VendorInvoiceError("The payment date cannot be in the future.")
    readiness = payment_readiness(db, invoice)
    if not readiness["ready"]:
        raise VendorInvoiceError("Not payable yet -- the client has not paid for this work: "
                                 + "; ".join(readiness["blockers"]) + ".")
    invoice.status, invoice.paid_by = "PAID", user.UserID
    invoice.paid_at, invoice.payment_reference = datetime.combine(paid_on, datetime.min.time()), reference.strip()
    db.flush()
    return invoice


def on_client_invoice_paid(db: Session, client_invoice: Invoice) -> List[int]:
    """A client payment can make vendor invoices payable: each one that now is gets one task for
    its approver (else its creator). Called in the transaction that marks the invoice PAID."""
    from app.services.task_service import create_task

    timesheet_ids = [t for (t,) in db.query(InvoiceLineItem.timesheet_id)
                     .filter(InvoiceLineItem.invoice_id == client_invoice.id)]
    if not timesheet_ids:
        return []
    candidates = (db.query(VendorInvoice).join(VendorInvoiceLine)
                  .filter(VendorInvoiceLine.timesheet_id.in_(timesheet_ids),
                          VendorInvoice.status.in_(("RECEIVED", "APPROVED"))).distinct().all())
    task_ids = []
    for invoice in candidates:
        if not payment_readiness(db, invoice)["ready"]:
            continue
        vendor = db.get(SubVendorAccount, invoice.sub_vendor_id)
        action = "Pay" if invoice.status == "APPROVED" else "Approve and pay"
        # CEO 2026-11-03: "asks me to initiate payment via task" -- the CEO pays an approved invoice; one
        # still waiting for approval goes to Finance first
        from app.services.vendor_invoice_intake import finance_owner, vendor_payer

        owner = vendor_payer(db, invoice.tenant_id) if invoice.status == "APPROVED" else finance_owner(db, invoice.tenant_id)
        task = create_task(
            db, title=f"{action} {vendor.company_name} invoice {invoice.vendor_invoice_number}: the client has paid"[:300],
            description=(f"The client paid {client_invoice.invoice_number or 'their invoice'} for every timesheet on "
                         f"{vendor.company_name}'s invoice {invoice.vendor_invoice_number}. Matched: "
                         f"${invoice.amount_usd_cents / 100:,.2f} billed vs ${invoice.expected_usd_cents / 100:,.2f} "
                         "approved hours x vendor rate. Initiate the payment, then record its reference on "
                         "Invoices > Sub-vendor invoices."),
            priority="HIGH", tenant_id=invoice.tenant_id,
            assigned_to_user_id=owner or invoice.approved_by or invoice.created_by, category="FINANCE",
            link="/sub-vendors?view=bills", due_date=datetime.utcnow())
        task_ids.append(task.id)
    return task_ids


def vendor_cost_by_timesheet(db: Session, timesheet_ids: Iterable[str]) -> Dict[str, Dict]:
    """{timesheet_id: {amount, paid}} from live vendor invoices: the P&L's actual contractor cost."""
    out = {}
    ids = list(timesheet_ids)
    if not ids:
        return out
    for line, status in (db.query(VendorInvoiceLine, VendorInvoice.status).join(VendorInvoice)
                         .filter(VendorInvoiceLine.timesheet_id.in_(ids), VendorInvoice.status.in_(LIVE_STATUSES))):
        out[line.timesheet_id] = {"amount": line.amount_usd_cents, "paid": status == "PAID"}
    return out


def vendor_summaries(db: Session, tenant_id: Optional[int]) -> Dict[str, Dict]:
    """Per vendor: last payment, unpaid bills, open balance, and paid this calendar year (for the 1099)."""
    out: Dict[str, Dict] = {}
    year = date.today().year
    for invoice in db.query(VendorInvoice).filter(VendorInvoice.tenant_id == tenant_id).all():
        row = out.setdefault(invoice.sub_vendor_id, {"last_paid_on": None, "unpaid_bills": 0, "open_balance_usd_cents": 0,
                                                     "paid_this_year_usd_cents": 0})
        if invoice.status in ("RECEIVED", "APPROVED"):
            row["unpaid_bills"] += 1
            row["open_balance_usd_cents"] += invoice.amount_usd_cents
        elif invoice.status == "PAID" and invoice.paid_at:
            paid = invoice.paid_at.date().isoformat()
            row["last_paid_on"] = max(row["last_paid_on"] or paid, paid)
            if invoice.paid_at.year == year:
                row["paid_this_year_usd_cents"] += invoice.amount_usd_cents
    return out


def to_item(db: Session, invoice: VendorInvoice) -> Dict:
    vendor = db.get(SubVendorAccount, invoice.sub_vendor_id)
    lines = (db.query(VendorInvoiceLine, Employee, Timesheet)
             .join(Employee, Employee.id == VendorInvoiceLine.employee_id)
             .join(Timesheet, Timesheet.id == VendorInvoiceLine.timesheet_id)
             .filter(VendorInvoiceLine.vendor_invoice_id == invoice.id)
             .order_by(Timesheet.week_starting_date).all())
    readiness = payment_readiness(db, invoice) if invoice.status in ("RECEIVED", "APPROVED") else None
    return {
        "id": invoice.id, "sub_vendor_id": invoice.sub_vendor_id, "sub_vendor_name": vendor.company_name if vendor else None,
        "vendor_invoice_number": invoice.vendor_invoice_number, "invoice_date": invoice.invoice_date.isoformat(),
        "period_start": invoice.period_start.isoformat(), "period_end": invoice.period_end.isoformat(),
        "status": invoice.status, "amount_usd_cents": invoice.amount_usd_cents,
        "due_date": (invoice.invoice_date + timedelta(days=vendor.payment_terms_days or 0)).isoformat() if vendor else None,
        "expected_usd_cents": invoice.expected_usd_cents,
        "variance_usd_cents": invoice.amount_usd_cents - invoice.expected_usd_cents, "note": invoice.note,
        "approved_at": invoice.approved_at.isoformat() if invoice.approved_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "payment_reference": invoice.payment_reference, "rejected_reason": invoice.rejected_reason,
        "client_paid": readiness["ready"] if readiness else invoice.status == "PAID",
        "payment_blockers": readiness["blockers"] if readiness else [],
        "lines": [{"employee_name": f"{e.first_name} {e.last_name}".strip(), "week_starting_date": t.week_starting_date.isoformat(),
                   "hours": float(l.hours), "rate_usd_cents": l.rate_usd_cents, "amount_usd_cents": l.amount_usd_cents}
                  for l, e, t in lines],
    }
