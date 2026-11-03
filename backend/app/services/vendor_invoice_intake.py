"""Sub-vendor invoices arrive by email and are recorded by themselves (CEO 2026-11-03: "Sub vendor invoices
BlitzenX ... once payment is received it validates with the sub vendor invoice and maps the payment and asks
me to initiate payment via task").

An email from a sub-vendor (its accounts address, or any address at that address's domain) with an invoice
attached, in the HRMS mailbox or a person's connected Outlook, is read by rules (no model):
- invoice number ("Invoice #/No./Number"), total ("Total / Amount due / Balance due") and the work period
  (a "period / from ... to ..." pair of dates; else the calendar month before the invoice date);
- mapped to the employee it is for (CEO 2026-11-03: "system should map it to an employee"): the contractor
  named on it, else the vendor's only contractor, else the one whose approved hours x vendor rate equal the
  total; ambiguous -> a Finance task naming the candidates;
- recorded against that employee's approved timesheets in the period (vendor_invoice_service);
- validated: the total equals approved hours x vendor rate -> approved by the system; otherwise Finance
  gets one task with the difference to approve or reject;
- an invoice that cannot be read or matched -> one Finance task saying exactly what is missing.
One vendor invoice number is recorded once (the vendor's numbers are unique).
"""
import calendar
import logging
import re
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.sub_vendor import SubVendorAccount
from app.models.user import Users
from app.models.vendor_invoice import VendorInvoice

logger = logging.getLogger(__name__)

NUMBER_PATTERN = re.compile(r"invoice\s*(?:no\.?|number|num\.?|#)\s*[:#.]?\s*([A-Z0-9][A-Z0-9\-/_.]{1,40})", re.I)
TOTAL_PATTERN = re.compile(r"(?:grand\s+total|total\s+due|amount\s+due|balance\s+due|invoice\s+total|total)"
                           r"[^\d$\n]{0,30}\$?\s*([\d,]+\.\d{2})", re.I)
DATE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})"
PERIOD_PATTERN = re.compile(rf"{DATE}\s*(?:to|through|-|–)\s*{DATE}", re.I)
GENERIC_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"}


def vendor_for_sender(db: Session, sender: str) -> Optional[SubVendorAccount]:
    """The approved sub-vendor this address belongs to: its accounts address, or another address at that
    address's company domain (never a public mail domain)."""
    sender = (sender or "").lower()
    if "@" not in sender:
        return None
    domain = sender.split("@", 1)[1]
    exact = db.query(SubVendorAccount).filter(func.lower(SubVendorAccount.contact_email) == sender,
                                              SubVendorAccount.status == "APPROVED").first()
    if exact is not None or domain in GENERIC_DOMAINS:
        return exact
    return db.query(SubVendorAccount).filter(func.lower(SubVendorAccount.contact_email).like(f"%@{domain}"),
                                             SubVendorAccount.status == "APPROVED").first()


def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y", "%b. %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def read_invoice(text: str, received: date) -> Dict:
    """{number, amount_cents, period_start, period_end, problems} from an invoice's text (rules only)."""
    problems = []
    number = NUMBER_PATTERN.search(text or "")
    totals = [int(round(float(m.replace(",", "")) * 100)) for m in TOTAL_PATTERN.findall(text or "")]
    period = PERIOD_PATTERN.search(text or "")
    start = _parse_date(period.group(1)) if period else None
    end = _parse_date(period.group(2)) if period else None
    if not (start and end and start <= end):
        last_month_end = received.replace(day=1) - timedelta(days=1)
        start, end = last_month_end.replace(day=1), last_month_end  # the usual monthly invoice
    if not number:
        problems.append("no invoice number")
    if not totals:
        problems.append("no total")
    return {"number": number.group(1).strip(".") if number else None, "amount_cents": max(totals) if totals else None,
            "period_start": start, "period_end": end, "problems": problems}


def map_employees(db: Session, vendor: SubVendorAccount, text: str, amount_cents: int, start: date,
                  end: date) -> Tuple[Optional[List[str]], str]:
    """(employee ids the invoice is for, how they were found) -- None when it cannot be told."""
    from app.models.employee import Employee
    from app.services.vendor_invoice_service import billable_timesheets

    contractors = db.query(Employee).filter(Employee.sub_vendor_id == vendor.id, Employee.status != "EXITED").all()
    flat = " ".join((text or "").lower().split())
    named = [e for e in contractors if e.first_name and e.last_name
             and f"{e.first_name} {e.last_name}".lower() in flat]
    if named:
        return [e.id for e in named], "named on the invoice"
    if len(contractors) == 1:
        return [contractors[0].id], "the vendor's only contractor"
    matches = [e for e in contractors
               if sum(l["amount_usd_cents"] for l in billable_timesheets(db, vendor.id, start, end, [e.id])) == amount_cents]
    if len(matches) == 1:
        return [matches[0].id], "the only contractor whose approved hours x rate equal the total"
    return None, ", ".join(f"{e.first_name} {e.last_name}" for e in (matches or contractors)) or "no contractors"


def _finance_task(db: Session, vendor: SubVendorAccount, title: str, description: str) -> None:
    """One task for Finance: the person who leads the Finance function, else the CEO."""
    from app.models.task import Task
    from app.services.task_service import create_task

    if db.query(Task.id).filter(Task.title == title[:300], Task.status.in_(("NEW", "IN_PROGRESS"))).first():
        return
    create_task(db, title=title[:300], description=description[:8000], priority="HIGH", tenant_id=vendor.tenant_id,
                assigned_to_user_id=finance_owner(db, vendor.tenant_id), category="FINANCE",
                link="/invoices?tab=vendor", due_date=datetime.utcnow())


def finance_owner(db: Session, tenant_id: Optional[int]) -> Optional[str]:
    """The most senior person in the Finance function, else the CEO (vendor_payer)."""
    from app.models.org_structure import Department

    finance = db.query(Department).filter(Department.tenant_id == tenant_id, Department.active.is_(True),
                                          func.lower(Department.name) == "finance").first()
    if finance is not None:
        people = db.query(Users).filter(Users.department_id == finance.id, Users.terminated_at.is_(None)).all()
        if people:
            from app.core import authority

            return max(people, key=lambda u: authority.level(db, u)).UserID
    return vendor_payer(db, tenant_id)


def vendor_payer(db: Session, tenant_id: Optional[int]) -> Optional[str]:
    """Who initiates vendor payments (CEO 2026-11-03: "asks me to initiate payment via task"): the holder of
    the CEO-designated job title."""
    from app.models.org_structure import OrgRole

    role = db.query(OrgRole).filter(OrgRole.tenant_id == tenant_id, OrgRole.designation == "ceo",
                                    OrgRole.active.is_(True)).first()
    if role is None:
        return None
    holder = db.query(Users).filter(Users.tenant_id == tenant_id, func.lower(Users.job_title) == role.name.lower(),
                                    Users.terminated_at.is_(None)).first()
    return holder.UserID if holder else None


def receive(db: Session, vendor: SubVendorAccount, message: Dict, attachments: List, received: datetime) -> Optional[str]:
    """Record one emailed vendor invoice. Returns the vendor invoice id, or None (not an invoice, already
    recorded, or a Finance task explains what is missing). Commits."""
    from app.services import vendor_invoice_service as service

    invoice_file = next((a for a in attachments if (a.text or "").strip() and re.search(r"invoice", f"{a.name} {a.text}", re.I)),
                        None)
    if invoice_file is None:
        return None  # an email from the vendor without an invoice: their client email, logged elsewhere
    reading = read_invoice(invoice_file.text, received.date())
    subject = message.get("subject") or "(no subject)"
    if reading["problems"]:
        _finance_task(db, vendor, f"Vendor invoice from {vendor.company_name} could not be read: {subject}",
                      f"{invoice_file.name}: {', '.join(reading['problems'])}. Record it on Invoices > Sub-vendor invoices.")
        db.commit()
        return None
    if db.query(VendorInvoice.id).filter(VendorInvoice.sub_vendor_id == vendor.id,
                                         VendorInvoice.vendor_invoice_number == reading["number"]).first():
        return None
    employee_ids, how = map_employees(db, vendor, invoice_file.text, reading["amount_cents"],
                                      reading["period_start"], reading["period_end"])
    if employee_ids is None:
        _finance_task(db, vendor, f"Vendor invoice {reading['number']} from {vendor.company_name}: which employee?",
                      f"No contractor is named on it and the total ${reading['amount_cents'] / 100:,.2f} does not "
                      f"single one out. It could be: {how}. Record it on Invoices > Sub-vendor invoices.")
        db.commit()
        return None
    system = SimpleNamespace(tenant_id=vendor.tenant_id, UserID=None)
    try:
        invoice = service.create_vendor_invoice(
            db, system, sub_vendor_id=vendor.id, vendor_invoice_number=reading["number"],
            invoice_date=min(received.date(), date.today()), period_start=reading["period_start"],
            period_end=reading["period_end"], amount_usd_cents=reading["amount_cents"], employee_ids=employee_ids,
            note=f"Read from {vendor.company_name}'s email \"{subject}\" ({invoice_file.name}); employee {how}.")
    except service.VendorInvoiceError as exc:
        db.rollback()
        _finance_task(db, vendor, f"Vendor invoice {reading['number']} from {vendor.company_name} needs you",
                      f"{exc} Total ${reading['amount_cents'] / 100:,.2f}, period {reading['period_start']} to "
                      f"{reading['period_end']} ({invoice_file.name}).")
        db.commit()
        return None
    if invoice.amount_usd_cents == invoice.expected_usd_cents:
        service.approve_vendor_invoice(db, system, invoice)  # matches approved hours x vendor rate
    else:
        difference = invoice.amount_usd_cents - invoice.expected_usd_cents
        _finance_task(db, vendor, f"Vendor invoice {invoice.vendor_invoice_number} from {vendor.company_name} differs "
                                  f"by ${difference / 100:,.2f}",
                      f"Billed ${invoice.amount_usd_cents / 100:,.2f}; approved hours x vendor rate come to "
                      f"${invoice.expected_usd_cents / 100:,.2f}. Approve it with a note, or reject it.")
    db.commit()
    logger.info(f"[VendorInvoiceIntake] {vendor.company_name} invoice {invoice.vendor_invoice_number}: "
                f"{invoice.status} (${invoice.amount_usd_cents / 100:,.2f} vs ${invoice.expected_usd_cents / 100:,.2f})")
    return invoice.id
