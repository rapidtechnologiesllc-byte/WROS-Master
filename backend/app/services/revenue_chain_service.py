"""The revenue chain: candidate -> employee -> job -> project -> timesheet ->
invoice -> payment -> P&L, per line, per partner and for the whole org.

One calculation feeds every view, so a line, a partner and the org total can
never disagree:

- A *line* is one timesheet on a client allocation. Its value is the invoice
  line amount once billed (invoice APPROVED/SENT/PAID), else approved hours x
  the allocation's bill rate (earned but not yet billed), else pending.
- *Delivery cost* of a line = billable hours x the employee's hourly loaded
  cost (monthly salary + statutory + overhead from CostRateConfig, divided by
  STANDARD_MONTHLY_HOURS).
- *Bench cost* = the rest of each employee's loaded payroll for the period
  (prorated by days employed) that no billable hour covered.
- *Revenue* in the P&L is earned revenue (billed + approved-unbilled work in
  the period, by timesheet week). Cash collected is reported beside it.
- *Expense cost* = manager-approved expenses dated in the period, attributed through
  the expense's client (else the business unit of whoever logged it).
- *Partner* = the partner of the business unit that owns the client
  (business_units.partner_user_id). Bench cost goes to the partner of the
  employee's own business unit. Anything without a partner is "unassigned",
  so partner rows always add up to the org total.

Unknown cost (no salary on file, no cost-rate config) is reported as missing,
never as zero: cost_data_complete is False and the missing employees are named.
"""
import calendar
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.opportunity import Opportunity
from app.models.partner_incentive import PartnerIncentiveRule
from app.models.project import Project
from app.models.revenue import BUSINESS_TYPES, Revenue
from app.models.timesheet import Timesheet
from app.models.user import Jobs, Users
from app.services.cost_rate_service import calculate_fully_loaded_cost_usd_cents, get_active_cost_rate_config

logger = logging.getLogger(__name__)

BILLED_STATUSES = ("APPROVED", "SENT", "PAID")
UNASSIGNED = "UNASSIGNED"
GROUPS = ("employee", "candidate", "job", "project", "client", "business_unit", "partner")


class CostBook:
    """Hourly and period loaded cost per employee, cached for one report."""

    def __init__(self, db: Session):
        self.db = db
        self._configs: Dict[Optional[int], object] = {}

    def config_for(self, employee: Employee):
        bu_id = employee.bu_id
        if bu_id not in self._configs:
            self._configs[bu_id] = get_active_cost_rate_config(self.db, business_unit_id=bu_id)
        return self._configs[bu_id]

    def monthly(self, employee: Optional[Employee]) -> Optional[int]:
        if employee is None:
            return None
        config = self.config_for(employee)
        if config is None:
            return None
        return calculate_fully_loaded_cost_usd_cents(employee, config)

    def hourly(self, employee: Optional[Employee]) -> Optional[float]:
        monthly = self.monthly(employee)
        if monthly is None or settings.STANDARD_MONTHLY_HOURS <= 0:
            return None
        return monthly / settings.STANDARD_MONTHLY_HOURS

    def period(self, employee: Employee, start: date, end: date) -> Optional[int]:
        """Loaded payroll for the days the employee was employed in [start, end]."""
        monthly = self.monthly(employee)
        if monthly is None:
            return None
        first = max(start, employee.joining_date)
        last = min(end, employee.exit_date) if employee.exit_date else end
        total = 0.0
        day = first
        while day <= last:
            days_in_month = calendar.monthrange(day.year, day.month)[1]
            month_end = date(day.year, day.month, days_in_month)
            span_end = min(last, month_end)
            total += monthly * ((span_end - day).days + 1) / days_in_month
            day = span_end + timedelta(days=1)
        return round(total)


def _by_id(db: Session, model, key, ids: Iterable) -> Dict:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {getattr(row, key.key): row for row in db.query(model).filter(key.in_(ids)).all()}


def _name(employee: Optional[Employee]) -> Optional[str]:
    return f"{employee.first_name} {employee.last_name or ''}".strip() if employee else None


def chain_lines(
    db: Session, *, start: date, end: date, tenant_id: Optional[int] = None,
    client_id: Optional[str] = None, partner_user_id: Optional[str] = None,
    employee_id: Optional[str] = None, costs: Optional[CostBook] = None,
    business_unit_ids: Optional[Set[int]] = None,
) -> List[Dict]:
    """Every client-allocated timesheet whose week starts in [start, end], traced end to end.
    business_unit_ids (None = all) keeps only lines of clients in those business units."""
    costs = costs or CostBook(db)
    query = db.query(Timesheet, EmployeeAllocation).join(
        EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id
    ).filter(Timesheet.week_starting_date >= start, Timesheet.week_starting_date <= end)
    if tenant_id is not None:
        query = query.filter(EmployeeAllocation.tenant_id == tenant_id)
    if client_id:
        query = query.filter(EmployeeAllocation.client_id == client_id)
    if employee_id:
        query = query.filter(Timesheet.employee_id == employee_id)
    rows = query.order_by(Timesheet.week_starting_date, Timesheet.id).all()
    if not rows:
        return []

    timesheet_ids = [ts.id for ts, _ in rows]
    invoice_lines: Dict[str, List[InvoiceLineItem]] = defaultdict(list)
    for item in db.query(InvoiceLineItem).filter(InvoiceLineItem.timesheet_id.in_(timesheet_ids)).all():
        invoice_lines[item.timesheet_id].append(item)
    invoices = _by_id(db, Invoice, Invoice.id, (i.invoice_id for items in invoice_lines.values() for i in items))
    employees = _by_id(db, Employee, Employee.id, (ts.employee_id for ts, _ in rows))
    jobs = _by_id(db, Jobs, Jobs.jobID, (a.demand_id for _, a in rows))
    projects = _by_id(db, Project, Project.id, (a.project_id for _, a in rows))
    clients = _by_id(db, Client, Client.id, (a.client_id for _, a in rows))
    units = _by_id(db, BusinessUnit, BusinessUnit.id, (c.business_unit_id for c in clients.values()))
    partners = _by_id(db, Users, Users.UserID, (u.partner_user_id for u in units.values()))

    lines = []
    for ts, allocation in rows:
        employee = employees.get(ts.employee_id)
        client = clients.get(allocation.client_id)
        unit = units.get(client.business_unit_id) if client else None
        partner_id = unit.partner_user_id if unit and unit.partner_user_id else None
        if partner_user_id and (partner_id or UNASSIGNED) != partner_user_id:
            continue
        if business_unit_ids is not None and (unit is None or unit.id not in business_unit_ids):
            continue
        job = jobs.get(allocation.demand_id)
        project = projects.get(allocation.project_id)
        hours = float(ts.billable_hours or 0)
        rate = allocation.billing_rate_usd_cents

        billed = [i for i in invoice_lines.get(ts.id, [])
                  if invoices.get(i.invoice_id) and invoices[i.invoice_id].status in BILLED_STATUSES]
        drafts = [i for i in invoice_lines.get(ts.id, []) if i not in billed]
        invoice = invoices.get((billed or drafts)[0].invoice_id) if (billed or drafts) else None
        billed_amount = sum(i.amount_usd_cents for i in billed)
        collected = sum(i.amount_usd_cents for i in billed if invoices[i.invoice_id].status == "PAID")
        unbilled = pending = 0
        if not billed and hours > 0 and rate:
            value = round(rate * hours)
            if ts.status == "APPROVED":
                unbilled = value
            elif ts.status != "REJECTED":
                pending = value
        earned = billed_amount or unbilled

        flags = []
        if allocation.project_id is None:
            flags.append("NO_PROJECT_CANNOT_INVOICE")
        if hours > 0 and not rate:
            flags.append("NO_BILL_RATE")
        if len(billed) > 1:
            flags.append("BILLED_MORE_THAN_ONCE")
        hourly = costs.hourly(employee)
        if hourly is None and hours > 0:
            flags.append("NO_COST_DATA")
        cost = round(hourly * hours) if hourly is not None else (0 if hours == 0 else None)

        lines.append({
            "timesheet_id": ts.id, "week_starting_date": ts.week_starting_date.isoformat(),
            "timesheet_status": ts.status, "billable_hours": hours,
            "employee_id": ts.employee_id, "employee_name": _name(employee),
            "candidate_id": employee.candidate_id if employee else None,
            "job_id": allocation.demand_id, "job_title": job.jobTitle if job else None,
            "project_id": allocation.project_id, "project_name": project.name if project else None,
            "client_id": allocation.client_id, "client_name": client.company_name if client else None,
            "business_unit_id": unit.id if unit else None, "business_unit_name": unit.name if unit else None,
            "partner_user_id": partner_id or UNASSIGNED,
            "partner_name": partners[partner_id].UserName if partner_id in partners else None,
            "bill_rate_usd_cents": rate,
            "invoice_id": invoice.id if invoice else None, "invoice_status": invoice.status if invoice else None,
            "billed_usd_cents": billed_amount, "collected_usd_cents": collected,
            "unbilled_usd_cents": unbilled, "pending_approval_usd_cents": pending,
            "earned_usd_cents": earned, "cost_usd_cents": cost,
            "margin_usd_cents": earned - cost if cost is not None else None,
            "flags": flags,
        })
    return lines


AMOUNTS = ("billable_hours", "billed_usd_cents", "collected_usd_cents", "unbilled_usd_cents",
           "pending_approval_usd_cents", "earned_usd_cents")
LABELS = {
    "employee": ("employee_id", "employee_name"), "candidate": ("candidate_id", "employee_name"),
    "job": ("job_id", "job_title"), "project": ("project_id", "project_name"),
    "client": ("client_id", "client_name"), "business_unit": ("business_unit_id", "business_unit_name"),
    "partner": ("partner_user_id", "partner_name"),
}


def _totals(lines: List[Dict]) -> Dict:
    out = {k: 0 for k in AMOUNTS}
    out["cost_usd_cents"], out["cost_data_complete"], out["lines"] = 0, True, len(lines)
    for line in lines:
        for k in AMOUNTS:
            out[k] += line[k]
        if line["cost_usd_cents"] is None:
            out["cost_data_complete"] = False
        else:
            out["cost_usd_cents"] += line["cost_usd_cents"]
    out["billable_hours"] = round(out["billable_hours"], 2)
    return _with_margin(out, out["earned_usd_cents"], out["cost_usd_cents"], out["cost_data_complete"])


def _with_margin(out: Dict, revenue: int, cost: int, complete: bool) -> Dict:
    margin = revenue - cost if complete else None
    out["margin_usd_cents"] = margin
    out["margin_pct"] = round(margin / revenue * 100, 1) if margin is not None and revenue > 0 else None
    return out


def summarize(lines: List[Dict], group_by: str) -> List[Dict]:
    if group_by not in LABELS:
        raise ValueError(f"group_by must be one of {sorted(LABELS)}")
    key, label = LABELS[group_by]
    groups: Dict = defaultdict(list)
    for line in lines:
        groups[line[key]].append(line)
    rows = [{"key": k, "name": items[0][label], **_totals(items)} for k, items in groups.items()]
    return sorted(rows, key=lambda r: r["earned_usd_cents"], reverse=True)


def pnl(db: Session, *, start: date, end: date, tenant_id: Optional[int] = None,
        business_unit_ids: Optional[Set[int]] = None) -> Dict:
    """Org P&L for [start, end] with every partner and business unit underneath it.
    business_unit_ids (None = the whole org) narrows revenue, staff and expenses to those BUs."""
    if end < start:
        raise ValueError("end must be on or after start")
    costs = CostBook(db)
    lines = chain_lines(db, start=start, end=end, tenant_id=tenant_id, costs=costs,
                        business_unit_ids=business_unit_ids)

    delivery_by_employee: Dict[str, int] = defaultdict(int)
    for line in lines:
        if line["cost_usd_cents"] is not None:
            delivery_by_employee[line["employee_id"]] += line["cost_usd_cents"]

    staff = db.query(Employee).filter(
        Employee.joining_date <= end,
        (Employee.exit_date.is_(None)) | (Employee.exit_date >= start),
        Employee.status != "PRE_JOINING",
    )
    if tenant_id is not None:
        staff = staff.filter(Employee.tenant_id == tenant_id)
    if business_unit_ids is not None:
        staff = staff.filter(Employee.bu_id.in_(business_unit_ids or [-1]))
    staff = staff.all()
    units = {u.id: u for u in db.query(BusinessUnit).all()}

    bench_rows: Dict = defaultdict(lambda: {"bench_cost_usd_cents": 0, "missing": []})
    missing_cost = sorted({line["employee_id"] for line in lines if line["cost_usd_cents"] is None})
    for employee in staff:
        unit = units.get(employee.bu_id)
        bucket = (unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED, employee.bu_id)
        payroll = costs.period(employee, start, end)
        if payroll is None:
            bench_rows[bucket]["missing"].append(employee.id)
            if employee.id not in missing_cost:
                missing_cost.append(employee.id)
            continue
        bench_rows[bucket]["bench_cost_usd_cents"] += max(0, payroll - delivery_by_employee.get(employee.id, 0))

    expenses, pending_expenses = _expenses(db, start, end, tenant_id, units, business_unit_ids)

    def expense_for(index: int, key) -> int:
        return sum(e["amount"] for e in expenses if e["key"][index] == key)

    def section(revenue_lines: List[Dict], bench: int, bench_missing: List[str], expense: int) -> Dict:
        totals = _totals(revenue_lines)
        delivery = totals.pop("cost_usd_cents")
        complete = totals.pop("cost_data_complete") and not bench_missing
        totals.pop("margin_usd_cents"), totals.pop("margin_pct")
        out = {
            **totals, "revenue_usd_cents": totals["earned_usd_cents"],
            "delivery_cost_usd_cents": delivery, "bench_cost_usd_cents": bench,
            "expense_cost_usd_cents": expense,
            "total_cost_usd_cents": delivery + bench + expense, "cost_data_complete": complete,
        }
        return _with_margin(out, out["revenue_usd_cents"], out["total_cost_usd_cents"], complete)

    def rollup(line_key: str, index: int, names: Dict) -> List[Dict]:
        keys = {line[line_key] for line in lines} | {b[index] for b in bench_rows} | {e["key"][index] for e in expenses}
        rows = []
        for k in keys:
            bench = [v for b, v in bench_rows.items() if b[index] == k]
            rows.append({"key": k, "name": names.get(k), **section(
                [line for line in lines if line[line_key] == k],
                sum(b["bench_cost_usd_cents"] for b in bench), [m for b in bench for m in b["missing"]],
                expense_for(index, k),
            )})
        return sorted(rows, key=lambda r: r["revenue_usd_cents"], reverse=True)

    partner_names = {line["partner_user_id"]: line["partner_name"] for line in lines}
    partner_ids = ({b[0] for b in bench_rows} | {e["key"][0] for e in expenses}) - {UNASSIGNED}
    for user in db.query(Users).filter(Users.UserID.in_(partner_ids)).all():
        partner_names.setdefault(user.UserID, user.UserName)
    bu_names = {u.id: u.name for u in units.values()}

    by_client = {row["key"]: row for row in summarize(lines, "client")}
    client_ids = {e["key"][2] for e in expenses if e["key"][2]} - set(by_client)
    for client in db.query(Client).filter(Client.id.in_(client_ids)).all():
        by_client[client.id] = {"key": client.id, "name": client.company_name, **_totals([])}
    for key, row in by_client.items():
        row["expense_usd_cents"] = sum(e["amount"] for e in expenses if e["key"][2] == key)
        _with_margin(row, row["earned_usd_cents"], row["cost_usd_cents"] + row["expense_usd_cents"],
                     row["cost_data_complete"])

    org = section(lines, sum(b["bench_cost_usd_cents"] for b in bench_rows.values()),
                  [m for b in bench_rows.values() for m in b["missing"]], sum(e["amount"] for e in expenses))
    return {
        "start": start.isoformat(), "end": end.isoformat(), **org,
        "pending_expenses_usd_cents": pending_expenses,
        "missing_cost_employee_ids": missing_cost,
        "by_partner": rollup("partner_user_id", 0, partner_names),
        "by_business_unit": rollup("business_unit_id", 1, bu_names),
        "by_client": sorted(by_client.values(), key=lambda r: r["earned_usd_cents"], reverse=True),
    }


def _expenses(db: Session, start: date, end: date, tenant_id: Optional[int], units: Dict,
              business_unit_ids: Optional[Set[int]] = None):
    """Manager-approved expenses dated in the period, keyed (partner, business unit, client):
    the client's business unit when the expense is for a client, else the logger's.
    Pending expenses are totalled separately; rejected ones never count."""
    from app.models.expense import ExpenseRecord

    query = db.query(ExpenseRecord).filter(ExpenseRecord.expense_date >= start, ExpenseRecord.expense_date <= end)
    if tenant_id is not None:
        query = query.filter(ExpenseRecord.tenant_id == tenant_id)
    records = query.all()
    clients = _by_id(db, Client, Client.id, (r.client_id for r in records))
    out, pending = [], 0
    for record in records:
        client = clients.get(record.client_id)
        bu_id = client.business_unit_id if client and client.business_unit_id else record.business_unit_id
        if business_unit_ids is not None and bu_id not in business_unit_ids:
            continue
        if record.manager_approval_status == "PENDING":
            pending += record.amount_usd_cents
            continue
        if record.manager_approval_status != "APPROVED":
            continue
        unit = units.get(bu_id)
        partner = unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED
        out.append({"key": (partner, bu_id, record.client_id), "amount": record.amount_usd_cents})
    return out, pending


def month_bounds(year: int, month: int):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


# ---- recognition when an invoice is paid ---------------------------------------------

def invoice_cost(db: Session, invoice: Invoice, costs: Optional[CostBook] = None) -> Optional[int]:
    costs = costs or CostBook(db)
    items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    employees = _by_id(db, Employee, Employee.id, (i.employee_id for i in items))
    total = 0
    for item in items:
        hourly = costs.hourly(employees.get(item.employee_id))
        if hourly is None:
            return None
        total += round(hourly * float(item.hours))
    return total


def recognize_revenue(db: Session, invoice: Invoice, *, recognized_at: Optional[datetime] = None) -> Revenue:
    """Write the Revenue row for a PAID invoice (once; a second call returns it)."""
    if invoice.status != "PAID":
        raise ValueError(f"Revenue is recognised only for PAID invoices; {invoice.id} is {invoice.status}")
    existing = db.query(Revenue).filter(Revenue.invoice_id == invoice.id, Revenue.source == "INVOICE").first()
    if existing is not None:
        return existing

    project = db.query(Project).filter(Project.id == invoice.project_id).first()
    client = db.query(Client).filter(Client.id == invoice.client_id).first()
    unit = db.query(BusinessUnit).filter(BusinessUnit.id == client.business_unit_id).first() \
        if client and client.business_unit_id else None
    opportunity = db.query(Opportunity).filter(Opportunity.id == project.opportunity_id).first() \
        if project and project.opportunity_id else None

    revenue = invoice.total_usd_cents or 0
    cost = invoice_cost(db, invoice)
    margin = revenue - cost if cost is not None else None
    business_type = project.delivery_engine if project and project.delivery_engine in BUSINESS_TYPES else None
    partner_id = unit.partner_user_id if unit else None

    share_pct = share = None
    if partner_id and business_type == "CORE":
        rule = db.query(PartnerIncentiveRule).filter(
            PartnerIncentiveRule.partner_user_id == partner_id, PartnerIncentiveRule.active.is_(True),
            PartnerIncentiveRule.incentive_type == "REVENUE_SHARE",
            PartnerIncentiveRule.revenue_share_pct.isnot(None),
        ).order_by(PartnerIncentiveRule.created_at.desc()).first()
        if rule is not None:
            share_pct = Decimal(rule.revenue_share_pct)
            share = int((Decimal(revenue) * share_pct / 100).quantize(Decimal(1)))

    row = Revenue(
        tenant_id=invoice.tenant_id, invoice_id=invoice.id, project_id=invoice.project_id,
        client_id=invoice.client_id, opportunity_id=opportunity.id if opportunity else None,
        client_owner_id=(opportunity.client_owner_id if opportunity else None)
        or (client.account_manager_user_id if client else None),
        revenue_usd_cents=revenue, currency=invoice.currency or "USD",
        client_type=client.client_type if client else None, business_type=business_type,
        partner_id=partner_id,
        partner_revenue_share_pct=int(share_pct.quantize(Decimal(1))) if share_pct is not None else None,
        partner_revenue_share_usd_cents=share,
        cost_usd_cents=cost, gross_margin_usd_cents=margin,
        gross_margin_pct=round(margin * 100 / revenue) if margin is not None and revenue > 0 else None,
        source="INVOICE", recognized_at=recognized_at or invoice.paid_at or datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    if partner_id is None:
        # revenue is recorded (the money arrived) but nobody is credited: Finance fixes the client's BU/partner
        from app.services.task_service import create_task

        create_task(db, title=f"Revenue without a partner: invoice {invoice.id[:8]}", priority="HIGH",
                    category="FINANCE", tenant_id=invoice.tenant_id, visibility_scope="ORG_WIDE",
                    description=(f"Paid invoice {invoice.id} ({revenue / 100:,.2f} USD) for "
                                 f"{client.company_name if client else invoice.client_id} has no partner: the client "
                                 f"{'has no business unit' if unit is None else 'business unit has no partner'}. "
                                 "Set it, then re-attribute this revenue."))
    logger.info(f"[Revenue] recognised invoice={invoice.id} revenue={revenue} cost={cost} partner={partner_id}")
    return row
