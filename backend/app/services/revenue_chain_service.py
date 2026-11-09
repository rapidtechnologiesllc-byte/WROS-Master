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
- *Bench cost* = the rest of each BILLABLE employee's loaded payroll for the
  period (prorated by days employed) that no billable hour covered.
- *Overhead (non-billable staff)* = the same for non-billable (internal) staff:
  their cost is overhead, never bench loss (CEO 2026-10-22).
- *HTD training cost* = the unbilled payroll of the days someone is in Hire-Train-Deploy
  training (htd_start_date to htd_end_date): a training investment, neither bench nor overhead
  (CEO 2026-10-24). delivery + bench + overhead + HTD = every employee's loaded payroll for the period.
- *Revenue* in the P&L is earned revenue (billed + approved-unbilled work in
  the period, by timesheet week). Cash collected is reported beside it.
- *Contractor cost* (CEO 2026-11-02): a contractor supplied by a sub-vendor (Employee.sub_vendor_id)
  has no payroll; their delivery cost is the vendor's invoice line for the timesheet, else (not yet
  invoiced) billable hours x their vendor rate. They carry no bench or overhead. Lines report
  vendor_cost / vendor_invoiced / vendor_paid, so the P&L shows what is owed to vendors beside cash
  collected from clients (pay-when-paid: vendor_invoice_service).
- *Corporate share* (CEO 2026-11-05: "count the corporate employees and prorate it to the business unit based on employee
  headcount"): the cost of everyone in a Corporate BU (BusinessUnit.is_corporate), and of non-billable people in a shared
  function (Department.is_shared_service) or with org-wide authority, leaves the BU they sit in and is shared across every
  other BU by its employee headcount, billable or not: a BU with no employees pays nothing. Corporate spend follows.
  SHARED_COST_SPLIT_TO_BUS off keeps it in an Org level row. Other non-billable people stay overhead of their BU. A move
  never changes the org total. Company rows keep the real cost with the employer.
- *Expense cost* = manager-approved expenses dated in the period (a multi-day expense on its first
  day), attributed through the expense's client (else the business unit of whoever logged it), and to
  the location of whoever spent it that day. Those still awaiting the manager are not a cost yet; every
  view shows them beside it (pending_expense_usd_cents).
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
    """Loaded cost per employee, per cost object (BU x location) and per day, cached for one report.

    Each day is charged to the business unit and delivery center (and its country) the employee
    sat in THAT day (EmployeeOrgHistory), at the rate in force that day for that BU and country
    (cost_rate_service.get_active_cost_rate_config): moving someone never rewrites a past month."""

    def __init__(self, db: Session):
        self.db = db
        self._configs: Dict = {}
        self._history: Dict[str, List] = {}

    def config_for(self, bu_id: Optional[int], country: Optional[str], on: date):
        key = (bu_id, country, on.year, on.month)
        if key not in self._configs:
            self._configs[key] = get_active_cost_rate_config(self.db, business_unit_id=bu_id, country=country,
                                                             on=on)
        return self._configs[key]

    def history(self, employee: Employee) -> List:
        """[(effective_from, bu_id, company_id, country)] oldest first; no rows = where they sit now."""
        if employee.id not in self._history:
            from app.models.employee_org_history import EmployeeOrgHistory, country_of_company

            rows = (self.db.query(EmployeeOrgHistory).filter(EmployeeOrgHistory.employee_id == employee.id)
                    .order_by(EmployeeOrgHistory.effective_from, EmployeeOrgHistory.id).all())
            spans = [(r.effective_from, r.bu_id, r.company_id, r.country) for r in rows]
            if not spans:
                spans = [(employee.joining_date, employee.bu_id, employee.company_id,
                          country_of_company(self.db, employee.company_id))]
            self._history[employee.id] = spans
        return self._history[employee.id]

    def object_on(self, employee: Employee, day: date):
        """(bu_id, company_id, country) the employee is charged to on this day."""
        spans = self.history(employee)
        current = spans[0]
        for span in spans:
            if span[0] <= day:
                current = span
        return current[1], current[2], current[3]

    def monthly(self, employee: Optional[Employee], on: Optional[date] = None) -> Optional[int]:
        if employee is None:
            return None
        on = on or date.today()
        bu_id, _, country = self.object_on(employee, on)
        config = self.config_for(bu_id, country, on)
        if config is None:
            return None
        return calculate_fully_loaded_cost_usd_cents(employee, config)

    def hourly(self, employee: Optional[Employee], on: Optional[date] = None) -> Optional[float]:
        monthly = self.monthly(employee, on)
        if monthly is None or settings.STANDARD_MONTHLY_HOURS <= 0:
            return None
        return monthly / settings.STANDARD_MONTHLY_HOURS

    def segments(self, employee: Employee, start: date, end: date) -> List[Dict]:
        """The employed days of [start, end] cut at month ends and cost-object changes:
        [{start, end, bu_id, company_id, country, cost}] with cost None when unknown."""
        first = max(start, employee.joining_date)
        last = min(end, employee.exit_date) if employee.exit_date else end
        changes = sorted({span[0] for span in self.history(employee) if first < span[0] <= last})
        out, day = [], first
        while day <= last:
            days_in_month = calendar.monthrange(day.year, day.month)[1]
            span_end = min(last, date(day.year, day.month, days_in_month))
            nxt = next((c for c in changes if day < c <= span_end), None)
            if nxt is not None:
                span_end = nxt - timedelta(days=1)
            bu_id, company_id, country = self.object_on(employee, day)
            monthly = self.monthly(employee, day)
            cost = None if monthly is None else monthly * ((span_end - day).days + 1) / days_in_month
            out.append({"start": day, "end": span_end, "bu_id": bu_id, "company_id": company_id,
                        "country": country, "cost": cost})
            day = span_end + timedelta(days=1)
        return out

    def period(self, employee: Employee, start: date, end: date) -> Optional[int]:
        """Loaded payroll for the days the employee was employed in [start, end]."""
        segments = self.segments(employee, start, end)
        if any(s["cost"] is None for s in segments):
            return None
        return round(sum(s["cost"] for s in segments))

    def by_object(self, employee: Employee, start: date, end: date) -> Dict:
        """{(bu_id, company_id, country): loaded payroll} for [start, end]; a None value means a day
        of that cost object has no salary or rate."""
        out: Dict = {}
        for s in self.segments(employee, start, end):
            key = (s["bu_id"], s["company_id"], s["country"])
            if s["cost"] is None or out.get(key, 0) is None:
                out[key] = None
            else:
                out[key] = out.get(key, 0) + s["cost"]
        return {k: (round(v) if v is not None else None) for k, v in out.items()}


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
    business_unit_ids: Optional[Set[int]] = None, client_ids: Optional[Iterable[str]] = None,
) -> List[Dict]:
    """Every client-allocated timesheet whose week starts in [start, end], traced end to end.
    business_unit_ids (None = all) keeps only lines of clients in those business units;
    client_ids (None = all) only lines of those clients."""
    costs = costs or CostBook(db)
    query = db.query(Timesheet, EmployeeAllocation).join(
        EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id
    ).filter(Timesheet.week_starting_date >= start, Timesheet.week_starting_date <= end)
    if tenant_id is not None:
        query = query.filter(EmployeeAllocation.tenant_id == tenant_id)
    if client_id:
        query = query.filter(EmployeeAllocation.client_id == client_id)
    if client_ids is not None:
        client_ids = list(client_ids)
        if not client_ids:
            return []
        query = query.filter(EmployeeAllocation.client_id.in_(client_ids))
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
    from app.services.vendor_invoice_service import vendor_cost_by_timesheet

    vendor_costs = vendor_cost_by_timesheet(db, timesheet_ids)
    jobs = _by_id(db, Jobs, Jobs.jobID, (a.demand_id for _, a in rows))
    projects = _by_id(db, Project, Project.id, (a.project_id for _, a in rows))
    clients = _by_id(db, Client, Client.id, (a.client_id for _, a in rows))
    units = _by_id(db, BusinessUnit, BusinessUnit.id, (c.business_unit_id for c in clients.values()))
    partners = _by_id(db, Users, Users.UserID, (u.partner_user_id for u in units.values()))
    # the bill rate in force in each week: a rate change never reprices a past week
    from app.services.employee_allocation_service import RateHistory

    rates = RateHistory(db, (a.id for _, a in rows))

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
        rate = rates.rate(allocation, ts.week_starting_date)

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
        cost_bu_id, cost_company_id, cost_country = costs.object_on(employee, ts.week_starting_date)             if employee is not None else (None, None, None)
        vendor_invoiced = vendor_paid = 0
        if employee is not None and employee.sub_vendor_id:  # contractor: the vendor's charge, not payroll
            on_invoice = vendor_costs.get(ts.id)
            if on_invoice is not None:
                cost = vendor_invoiced = on_invoice["amount"]
                vendor_paid = cost if on_invoice["paid"] else 0
            elif employee.vendor_hourly_rate_usd_cents:
                cost = round(employee.vendor_hourly_rate_usd_cents * hours)
            else:
                cost = 0 if hours == 0 else None
                if hours > 0:
                    flags.append("NO_VENDOR_RATE")
        else:
            hourly = costs.hourly(employee, ts.week_starting_date) if employee is not None else None
            if hourly is None and hours > 0:
                flags.append("NO_COST_DATA")
            cost = round(hourly * hours) if hourly is not None else (0 if hours == 0 else None)
        vendor_cost = (cost or 0) if employee is not None and employee.sub_vendor_id else 0

        lines.append({
            "timesheet_id": ts.id, "week_starting_date": ts.week_starting_date.isoformat(),
            "timesheet_status": ts.status, "billable_hours": hours,
            "employee_id": ts.employee_id, "employee_name": _name(employee),
            "candidate_id": employee.candidate_id if employee else None,
            "job_id": allocation.demand_id, "job_title": job.jobTitle if job else allocation.role,
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
            "vendor_cost_usd_cents": vendor_cost, "vendor_invoiced_usd_cents": vendor_invoiced,
            "vendor_paid_usd_cents": vendor_paid, "sub_vendor_id": employee.sub_vendor_id if employee else None,
            "margin_usd_cents": earned - cost if cost is not None else None,
            # the cost object the delivery cost is charged to: where the employee sat that week
            "cost_business_unit_id": cost_bu_id, "cost_company_id": cost_company_id, "country": cost_country,
            "flags": flags,
        })
    return lines


def earned_revenue(db: Session, *, start: date, end: date, tenant_id: Optional[int] = None,
                   client_ids: Optional[Iterable[str]] = None,
                   business_unit_ids: Optional[Set[int]] = None) -> int:
    """THE revenue figure for a period (USD cents): work billed or approved in it, by timesheet
    week -- the P&L's income line. Forecast vs Actual, the BU Head's month to date and the client
    revenue dashboard all read this, so no screen counts a month's revenue differently."""
    lines = chain_lines(db, start=start, end=end, tenant_id=tenant_id, client_ids=client_ids,
                        business_unit_ids=business_unit_ids)
    return sum(line["earned_usd_cents"] for line in lines)


AMOUNTS = ("billable_hours", "billed_usd_cents", "collected_usd_cents", "unbilled_usd_cents",
           "pending_approval_usd_cents", "earned_usd_cents",
           # contractor cost (part of delivery cost), what vendors invoiced, and what we paid them
           "vendor_cost_usd_cents", "vendor_invoiced_usd_cents", "vendor_paid_usd_cents")
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


def prorated_shares(amount: int, weights: Dict[int, int]) -> Dict[int, int]:
    """amount split in proportion to the weights; the cents left over go to the largest remainders, so the
    shares add up exactly."""
    total = sum(weights.values())
    shares = {bu: amount * weight // total for bu, weight in weights.items()}
    left = amount - sum(shares.values())
    by_remainder = sorted(weights, key=lambda bu: (-(amount * weights[bu] % total), bu))
    for bu in by_remainder[:left]:
        shares[bu] += 1
    return shares


def corporate_unit_ids(db: Session, tenant_id: Optional[int] = None) -> Set[int]:
    query = db.query(BusinessUnit.id).filter(BusinessUnit.is_corporate.is_(True))
    if tenant_id is not None:
        query = query.filter(BusinessUnit.tenant_id == tenant_id)
    return {row[0] for row in query}


def headcount_weights(db: Session, *, start: date, end: date, tenant_id: Optional[int], costs: CostBook,
                      corporate: Set[int]) -> Dict[int, int]:
    """{BU: employee-days in the period} for every non-Corporate BU, billable or not, so someone who joined
    mid-month counts for the days they were there. A BU with no employees is absent and pays nothing."""
    staff = db.query(Employee).filter(Employee.joining_date <= end, Employee.status != "PRE_JOINING",
                                      (Employee.exit_date.is_(None)) | (Employee.exit_date >= start))
    if tenant_id is not None:
        staff = staff.filter(Employee.tenant_id == tenant_id)
    weights: Dict[int, int] = defaultdict(int)
    for employee in staff.all():
        if employee.status == "EXITED" and employee.exit_date is None:
            continue
        for segment in costs.segments(employee, start, end):
            if segment["bu_id"] is not None and segment["bu_id"] not in corporate:
                weights[segment["bu_id"]] += (segment["end"] - segment["start"]).days + 1
    return dict(weights)


def shared_service_moves(db: Session, *, start: date, end: date, tenant_id: Optional[int], costs: CostBook):
    """({(home bu, country): cost of Corporate and org-level people who sat there}, {function: cost}). Always
    org-wide, so a partner's view shows the same share as the CEO's."""
    from app.core import authority
    from app.core.config import settings as config
    from app.models.org_structure import Department

    default = {n.strip().lower() for n in config.SHARED_SERVICE_FUNCTIONS.split(",") if n.strip()}
    departments = db.query(Department)
    if tenant_id is not None:
        departments = departments.filter(Department.tenant_id == tenant_id)
    names = {d.id: d.name for d in departments.all()}
    shared = {d.id for d in departments.all()
              if (d.is_shared_service if d.is_shared_service is not None else d.name.strip().lower() in default)}
    corporate = corporate_unit_ids(db, tenant_id)
    pool: Dict = defaultdict(int)
    by_function: Dict = defaultdict(int)
    # outer join: Corporate staff need no login to be Corporate (facilities, for example)
    people = (db.query(Employee, Users).outerjoin(Users, Users.UserID == Employee.wros_user_id)
              .filter(Employee.is_billable.is_(False), Employee.sub_vendor_id.is_(None),
                      Employee.joining_date <= end, (Employee.exit_date.is_(None)) | (Employee.exit_date >= start),
                      Employee.status != "PRE_JOINING").all())
    for employee, user in people:
        in_function = user is not None and user.department_id in shared
        org_level = user is not None and authority.is_org_level(db, user)
        label = names.get(user.department_id) if in_function else "Leadership" if org_level else "Corporate"
        for (bu_id, _, where), payroll in costs.by_object(employee, start, end).items():
            # anyone else is BU-specific: stays overhead of their BU
            if payroll and (in_function or org_level or bu_id in corporate):
                pool[(bu_id, where)] += payroll
                by_function[label] += payroll
    return dict(pool), dict(by_function)


def pnl(db: Session, *, start: date, end: date, tenant_id: Optional[int] = None,
        business_unit_ids: Optional[Set[int]] = None, country: Optional[str] = None) -> Dict:
    """Org P&L for [start, end] with every partner, business unit, location and cost object
    (BU x location) underneath it. business_unit_ids (None = the whole org) narrows revenue, staff
    and expenses to those BUs. country (ISO, None = every location) narrows to work done from that
    location: lines by where the employee sat that week, bench and overhead by where they sat each
    day, expenses by where the person who spent it sat that day."""
    if end < start:
        raise ValueError("end must be on or after start")
    costs = CostBook(db)
    lines = chain_lines(db, start=start, end=end, tenant_id=tenant_id, costs=costs,
                        business_unit_ids=business_unit_ids)
    if country is not None:
        lines = [line for line in lines if line["country"] == country]

    # delivery cost per employee and cost object (where they sat that week)
    delivery_by_object: Dict = defaultdict(int)
    delivery_by_employee: Dict[str, int] = defaultdict(int)
    for line in lines:
        if line["cost_usd_cents"] is not None:
            delivery_by_employee[line["employee_id"]] += line["cost_usd_cents"]
            delivery_by_object[(line["employee_id"], line["cost_business_unit_id"], line["cost_company_id"],
                                line["country"])] += line["cost_usd_cents"]

    staff = db.query(Employee).filter(
        Employee.joining_date <= end,
        (Employee.exit_date.is_(None)) | (Employee.exit_date >= start),
        Employee.status != "PRE_JOINING",
    )
    if tenant_id is not None:
        staff = staff.filter(Employee.tenant_id == tenant_id)
    staff = staff.all()
    units = {u.id: u for u in db.query(BusinessUnit).all()}

    # bench (billable staff) and overhead (internal staff): each day's unbilled payroll goes to the
    # BU, company and country the employee sat in THAT day, never to where they sit now
    bench_rows: Dict = defaultdict(lambda: {"bench_cost_usd_cents": 0, "overhead_cost_usd_cents": 0,
                                            "htd_cost_usd_cents": 0, "shared_cost_usd_cents": 0, "missing": []})
    company_staff_cost: Dict = defaultdict(lambda: {"bench": 0, "overhead": 0, "htd": 0, "complete": True})
    missing_cost = sorted({line["employee_id"] for line in lines if line["cost_usd_cents"] is None})
    for employee in staff:
        if employee.sub_vendor_id:
            continue  # a contractor has no payroll: their cost is on their timesheet lines
        # the part of the period this person was in HTD training, by cost object
        training = {}
        if employee.htd_start_date:
            first, last = max(start, employee.htd_start_date), min(end, employee.htd_end_date or end)
            if first <= last:
                training = costs.by_object(employee, first, last)
        for (bu_id, company_id, where), payroll in costs.by_object(employee, start, end).items():
            if business_unit_ids is not None and bu_id not in business_unit_ids:
                continue
            if country is not None and where != country:
                continue
            unit = units.get(bu_id)
            bucket = (unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED, bu_id, where)
            if payroll is None:
                bench_rows[bucket]["missing"].append(employee.id)
                company_staff_cost[company_id]["complete"] = False
                if employee.id not in missing_cost:
                    missing_cost.append(employee.id)
                continue
            uncovered = max(0, payroll - delivery_by_object.get((employee.id, bu_id, company_id, where), 0))
            htd = min(uncovered, training.get((bu_id, company_id, where)) or 0)
            uncovered -= htd
            bench_rows[bucket]["htd_cost_usd_cents"] += htd
            company_staff_cost[company_id]["htd"] += htd
            bench_rows[bucket]["bench_cost_usd_cents" if employee.is_billable else "overhead_cost_usd_cents"] += uncovered
            company_staff_cost[company_id]["bench" if employee.is_billable else "overhead"] += uncovered

    from app.core.config import settings as config

    pool, by_function = shared_service_moves(db, start=start, end=end, tenant_id=tenant_id, costs=costs)
    corporate = corporate_unit_ids(db, tenant_id)
    weights = headcount_weights(db, start=start, end=end, tenant_id=tenant_id, costs=costs, corporate=corporate)
    split = config.SHARED_COST_SPLIT_TO_BUS and bool(weights)

    def staff_bucket(bu_id, where):
        unit = units.get(bu_id)
        return (unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED, bu_id, where)

    for (home, where), amount in pool.items():
        if country is not None and where != country:
            continue
        if business_unit_ids is None or home in business_unit_ids:
            bench_rows[staff_bucket(home, where)]["overhead_cost_usd_cents"] -= amount
        if split:
            for bu_id, share in prorated_shares(amount, weights).items():
                if business_unit_ids is None or bu_id in business_unit_ids:
                    bench_rows[staff_bucket(bu_id, where)]["shared_cost_usd_cents"] += share
        elif business_unit_ids is None:  # the Org level row is for those who see the whole org
            bench_rows[(UNASSIGNED, None, where)]["shared_cost_usd_cents"] += amount

    # every BU's first: a Corporate expense is shared, including with a BU a partner is looking at
    every_expense, _ = _expenses(db, start, end, tenant_id, units, None, costs, include_pending=True)
    if split:
        every_expense = _share_corporate_expenses(every_expense, corporate, weights, units)
    if business_unit_ids is not None:
        every_expense = [e for e in every_expense if e["key"][1] in business_unit_ids]
    if country is not None:
        every_expense = [e for e in every_expense if e["country"] == country]
    expenses = [e for e in every_expense if not e.get("pending")]
    waiting = [e for e in every_expense if e.get("pending")]
    pending_expenses = sum(e["amount"] for e in waiting)

    def expense_for(index: int, key) -> int:
        return sum(e["amount"] for e in expenses if e["key"][index] == key)

    def waiting_for(index: int, key) -> int:
        return sum(e["amount"] for e in waiting if e["key"][index] == key)

    def section(revenue_lines: List[Dict], bench: int, bench_missing: List[str], expense: int,
                overhead: int = 0, htd: int = 0, shared: int = 0, pending: int = 0) -> Dict:
        totals = _totals(revenue_lines)
        delivery = totals.pop("cost_usd_cents")
        complete = totals.pop("cost_data_complete") and not bench_missing
        totals.pop("margin_usd_cents"), totals.pop("margin_pct")
        out = {
            **totals, "revenue_usd_cents": totals["earned_usd_cents"],
            "delivery_cost_usd_cents": delivery, "bench_cost_usd_cents": bench,
            "overhead_cost_usd_cents": overhead, "shared_cost_usd_cents": shared, "htd_cost_usd_cents": htd,
            "expense_cost_usd_cents": expense, "pending_expense_usd_cents": pending,
            "total_cost_usd_cents": delivery + bench + overhead + shared + htd + expense, "cost_data_complete": complete,
        }
        return _with_margin(out, out["revenue_usd_cents"], out["total_cost_usd_cents"], complete)

    # every business unit in view, and its partner, has a row even in a month with nothing on it
    # (CEO 2026-11-09: a BU with no people yet was missing, and so was its partner)
    listed_units = [u for u in units.values() if getattr(u, "active", True) is not False
                    and (tenant_id is None or u.tenant_id == tenant_id)
                    and (business_unit_ids is None or u.id in business_unit_ids)]

    def rollup(line_key: str, index: int, names: Dict, always=()) -> List[Dict]:
        keys = ({line[line_key] for line in lines} | {b[index] for b in bench_rows}
                | {e["key"][index] for e in every_expense} | set(always))
        rows = []
        for k in keys:
            bench = [v for b, v in bench_rows.items() if b[index] == k]
            rows.append({"key": k, "name": names.get(k), **section(
                [line for line in lines if line[line_key] == k],
                sum(b["bench_cost_usd_cents"] for b in bench), [m for b in bench for m in b["missing"]],
                expense_for(index, k), sum(b["overhead_cost_usd_cents"] for b in bench),
                sum(b["htd_cost_usd_cents"] for b in bench), sum(b["shared_cost_usd_cents"] for b in bench),
                waiting_for(index, k),
            )})
        return sorted(rows, key=lambda r: (-r["revenue_usd_cents"], str(r["name"] or "")))

    unit_partners = {u.partner_user_id for u in listed_units if u.partner_user_id}
    partner_names = {line["partner_user_id"]: line["partner_name"] for line in lines}
    partner_ids = ({b[0] for b in bench_rows} | {e["key"][0] for e in every_expense} | unit_partners) - {UNASSIGNED}
    for user in db.query(Users).filter(Users.UserID.in_(partner_ids)).all():
        partner_names.setdefault(user.UserID, user.UserName)
    bu_names = {u.id: u.name for u in units.values()}
    bu_names[None] = "Org level"

    by_client = {row["key"]: row for row in summarize(lines, "client")}
    client_ids = {e["key"][2] for e in expenses if e["key"][2]} - set(by_client)
    for client in db.query(Client).filter(Client.id.in_(client_ids)).all():
        by_client[client.id] = {"key": client.id, "name": client.company_name, **_totals([])}
    for key, row in by_client.items():
        row["expense_usd_cents"] = sum(e["amount"] for e in expenses if e["key"][2] == key)
        _with_margin(row, row["earned_usd_cents"], row["cost_usd_cents"] + row["expense_usd_cents"],
                     row["cost_data_complete"])

    org = section(lines, sum(b["bench_cost_usd_cents"] for b in bench_rows.values()),
                  [m for b in bench_rows.values() for m in b["missing"]], sum(e["amount"] for e in expenses),
                  sum(b["overhead_cost_usd_cents"] for b in bench_rows.values()),
                  sum(b["htd_cost_usd_cents"] for b in bench_rows.values()),
                  sum(b["shared_cost_usd_cents"] for b in bench_rows.values()), pending_expenses)
    by_company = _company_pnl(db, lines, company_staff_cost, expenses, start, end, tenant_id, pending=waiting)

    def staff_rollup(key_of_line, key_of_bucket, names, key_of_expense) -> List[Dict]:
        """Rows for a staff-side dimension (location; cost object = BU x location): revenue and
        delivery of the work done from there, bench and overhead of the people who sat there,
        expenses of the people who spent it there."""
        keys = ({key_of_line(line) for line in lines} | {key_of_bucket(b) for b in bench_rows}
                | {key_of_expense(e) for e in every_expense})
        rows = []
        for k in keys:
            bench = [v for b, v in bench_rows.items() if key_of_bucket(b) == k]
            rows.append({"key": k, "name": names(k), **section(
                [line for line in lines if key_of_line(line) == k],
                sum(b["bench_cost_usd_cents"] for b in bench), [m for b in bench for m in b["missing"]],
                sum(e["amount"] for e in expenses if key_of_expense(e) == k),
                sum(b["overhead_cost_usd_cents"] for b in bench), sum(b["htd_cost_usd_cents"] for b in bench),
                sum(b["shared_cost_usd_cents"] for b in bench),
                sum(e["amount"] for e in waiting if key_of_expense(e) == k))})
        return sorted(rows, key=lambda r: (-r["total_cost_usd_cents"], str(r["key"])))

    return {
        "start": start.isoformat(), "end": end.isoformat(), "country": country, **org,
        "pending_expenses_usd_cents": pending_expenses,
        "org_staff_by_function": ([{"name": name, "cost_usd_cents": cost} for name, cost in sorted(by_function.items())]
                                  if business_unit_ids is None and country is None else []),
        "missing_cost_employee_ids": missing_cost,
        "by_partner": rollup("partner_user_id", 0, partner_names, unit_partners),
        "by_business_unit": rollup("business_unit_id", 1, bu_names, [u.id for u in listed_units]),
        "by_location": staff_rollup(lambda line: line["country"], lambda b: b[2], lambda k: k or "Unknown location",
                                    lambda e: e["country"]),
        "by_cost_object": [
            {**row, "business_unit_id": row["key"][0], "country": row["key"][1],
             "key": f"{row['key'][0]}:{row['key'][1]}"}
            for row in staff_rollup(lambda line: (line["cost_business_unit_id"], line["country"]),
                                    lambda b: (b[1], b[2]),
                                    lambda k: f"{bu_names.get(k[0]) or 'No BU'} x {k[1] or 'unknown location'}",
                                    lambda e: (e["key"][1], e["country"]))],
        "by_client": sorted(by_client.values(), key=lambda r: r["earned_usd_cents"], reverse=True),
        "group": _group(db, tenant_id),
        "by_company": by_company,
        # the whole picture only: a slice of one BU or country would understate what was lent
        "company_loans": (company_loans(db, by_company, end=end, tenant_id=tenant_id, costs=costs)
                          if business_unit_ids is None and country is None else []),
    }


def _group(db: Session, tenant_id: Optional[int]) -> Optional[Dict]:
    """The parent company the companies report to: the tenant, under its legal name when it has one."""
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, tenant_id) if tenant_id is not None else None
    if tenant is None:
        return None
    return {"name": tenant.parent_company_name or tenant.name, "company_code": str(tenant.id)}


def _company_pnl(db: Session, lines: List[Dict], staff_cost: Dict, expenses: List[Dict], start: date, end: date,
                 tenant_id: Optional[int], pending: Iterable[Dict] = ()) -> List[Dict]:
    """Each company's (legal entity's) own P&L; the parent company (tenant) owns the org-wide one.

      revenue          earned on the clients the company contracts (Client.contracting_company_id)
      delivery cost    hours of the company's own employees (Employee.company_id), on any client
      bench cost       its employees' paid-but-unbilled time (HTD training days are their own line)
      expenses         client expenses on its clients
      intercompany     settlements: revenue for the receiving company, cost for the paying one;
                       they cancel out at org level, so the org P&L is unchanged
      loans            a company funded by a sister (Location.funded_by_company_id) carries its own
                       costs; the lender shows them as money lent, not as its expense
    Every company has a row, in company order, so the group always reads the same way. Work that can't
    be attributed to a company stays with the parent (key None), so the rows add up to the group."""
    from app.models.client import Client
    from app.models.intercompany_ledger import IntercompanySettlement
    from app.models.location import Location

    companies = db.query(Location).all() if tenant_id is None else \
        db.query(Location).filter(Location.tenant_id == tenant_id).all()
    client_company = dict(db.query(Client.id, Client.contracting_company_id))
    rows: Dict = defaultdict(lambda: {"revenue": 0, "delivery": 0, "bench": 0, "overhead": 0, "htd": 0, "expense": 0,
                                      "ic_revenue": 0, "ic_cost": 0, "complete": True, "pending": 0})
    for line in lines:
        rows[client_company.get(line["client_id"])]["revenue"] += line.get("earned_usd_cents") or 0
        owner = rows[line["cost_company_id"]]  # the company the employee worked for that week
        if line["cost_usd_cents"] is None:
            owner["complete"] = False
        else:
            owner["delivery"] += line["cost_usd_cents"]
    for company_id, cost in staff_cost.items():  # bench and overhead by the company of each day
        rows[company_id]["bench"] += cost["bench"]
        rows[company_id]["overhead"] += cost["overhead"]
        rows[company_id]["htd"] += cost["htd"]
        if not cost["complete"]:
            rows[company_id]["complete"] = False
    for e in expenses:  # a client's contracting company; personal spend, the logger's company that day
        rows[e["company_id"]]["expense"] += e["amount"]
    for e in pending:  # not a cost yet: shown beside it
        rows[e["company_id"]]["pending"] += e["amount"]
    settlements = db.query(IntercompanySettlement).filter(
        IntercompanySettlement.settlement_date >= start, IntercompanySettlement.settlement_date <= end)
    if tenant_id is not None:
        settlements = settlements.filter(IntercompanySettlement.tenant_id == tenant_id)
    for s in settlements.all():
        # by company id; an old entry no company matched stays with the parent ("Group")
        rows[s.to_company_id]["ic_revenue"] += s.amount_usd_cents
        rows[s.from_company_id]["ic_cost"] += s.amount_usd_cents

    for company in companies:
        rows[company.id]  # a company with nothing this period still shows
    names = {c.id: (c.name, c.company_code) for c in companies}
    order = {c.id: (c.company_seq or 0, c.name) for c in companies}
    funded = {c.id: c.funded_by_company_id for c in companies if c.funded_by_company_id and c.id in rows}
    for lender in funded.values():
        rows[lender]  # the lender gets a row even with no cost of its own
    out = []
    for key, r in rows.items():
        revenue = r["revenue"] + r["ic_revenue"]
        cost = r["delivery"] + r["bench"] + r["overhead"] + r["htd"] + r["expense"] + r["ic_cost"]
        out.append(_with_margin({
            "key": key, "name": names.get(key, ("Not tagged to a company", None))[0],
            "company_code": names.get(key, (None, None))[1],
            "revenue_usd_cents": revenue, "external_revenue_usd_cents": r["revenue"],
            "intercompany_revenue_usd_cents": r["ic_revenue"], "intercompany_cost_usd_cents": r["ic_cost"],
            "delivery_cost_usd_cents": r["delivery"], "bench_cost_usd_cents": r["bench"],
            "overhead_cost_usd_cents": r["overhead"], "htd_cost_usd_cents": r["htd"],
            "expense_cost_usd_cents": r["expense"], "pending_expense_usd_cents": r["pending"], "total_cost_usd_cents": cost,
            "cost_data_complete": r["complete"], "funded_by": names.get(funded.get(key), (None, None))[0],
            "loaned_out_usd_cents": 0,
        }, revenue, cost, r["complete"]))
    by_key = {row["key"]: row for row in out}
    for borrower, lender in funded.items():
        by_key[lender]["loaned_out_usd_cents"] += by_key[borrower]["total_cost_usd_cents"]
    return sorted(out, key=lambda r: (r["key"] is None, order.get(r["key"], (0, ""))))


def company_loans(db: Session, by_company: List[Dict], *, end: date, tenant_id: Optional[int] = None,
                  costs: Optional["CostBook"] = None) -> List[Dict]:
    """What each lender has paid for a company it funds: in the period (that company's P&L cost) and
    in total up to `end` (every day its people sat in it, plus its people's approved own spend).
    Repayments are not recorded yet, so the total is what was lent, not what is still owed."""
    from app.models.employee_org_history import EmployeeOrgHistory
    from app.models.location import Location

    query = db.query(Location)
    if tenant_id is not None:
        query = query.filter(Location.tenant_id == tenant_id)
    companies = query.all()
    names = {c.id: c.name for c in companies}
    funded = {c.id: c.funded_by_company_id for c in companies if c.funded_by_company_id}
    if not funded:
        return []
    costs = costs or CostBook(db)
    end = min(end, date.today())  # lent so far: a period can run past today
    totals = {company_id: 0 for company_id in funded}
    complete = {company_id: True for company_id in funded}
    ever_there = db.query(EmployeeOrgHistory.employee_id).filter(EmployeeOrgHistory.company_id.in_(funded))
    staff = db.query(Employee).filter(Employee.joining_date <= end, Employee.status != "PRE_JOINING",
                                      Employee.sub_vendor_id.is_(None),
                                      (Employee.id.in_(ever_there)) | (Employee.company_id.in_(funded)))
    for employee in staff.all():
        for segment in costs.segments(employee, employee.joining_date, end):
            if segment["company_id"] in funded:
                if segment["cost"] is None:
                    complete[segment["company_id"]] = False
                else:
                    totals[segment["company_id"]] += segment["cost"]
    units = {u.id: u for u in db.query(BusinessUnit).all()}
    for expense in _expenses(db, date.min, end, tenant_id, units, None, costs)[0]:
        if expense["company_id"] in funded:
            totals[expense["company_id"]] += expense["amount"]
    period = {row["key"]: row["total_cost_usd_cents"] for row in by_company}
    return [{"company_id": company_id, "company": names.get(company_id), "lender_id": lender,
             "lender": names.get(lender), "period_usd_cents": period.get(company_id, 0),
             "to_date_usd_cents": round(totals[company_id]), "cost_data_complete": complete[company_id]}
            for company_id, lender in funded.items()]


def _expenses(db: Session, start: date, end: date, tenant_id: Optional[int], units: Dict,
              business_unit_ids: Optional[Set[int]] = None, costs: Optional["CostBook"] = None,
              include_pending: bool = False):
    """Manager-approved expenses dated in the period, keyed (partner, business unit, client):
    each client's part (expense_service.expense_shares -- a split expense counts on every client
    it names) goes to that client's business unit and contracting company; internal (personal)
    spend stays with the logger's business unit and goes to the company the logger worked for on
    the expense date (CostBook.object_on, the same rule as their salary -- CEO 2026-11-01: an
    attendee's own conference meals and travel count in their company's P&L, not "Group").
    A logger with no employee record stays with the parent ("Group", company None).
    Each carries the country its spender sat in that day. Pending expenses are totalled separately
    (include_pending also returns them, flagged, for the views that show them); rejected ones never count."""
    from app.models.expense import ExpenseRecord
    from app.services.expense_service import expense_shares

    query = db.query(ExpenseRecord).filter(ExpenseRecord.expense_date >= start, ExpenseRecord.expense_date <= end)
    if tenant_id is not None:
        query = query.filter(ExpenseRecord.tenant_id == tenant_id)
    records = [r for r in query.all() if r.manager_approval_status in ("PENDING", "APPROVED")]
    shares = expense_shares(records)
    clients = _by_id(db, Client, Client.id, (c for r in records for c, _ in shares[r.id]))
    costs = costs or CostBook(db)
    loggers = {e.wros_user_id: e for e in db.query(Employee).filter(
        Employee.wros_user_id.in_({r.logged_by_user_id for r in records} or {""}))}

    def logger_object(record):
        employee = loggers.get(record.logged_by_user_id)
        return costs.object_on(employee, record.expense_date) if employee is not None else (None, None, None)

    out, pending = [], 0
    for record in records:
        for client_id, cents in shares[record.id]:
            client = clients.get(client_id)
            bu_id = client.business_unit_id if client and client.business_unit_id else record.business_unit_id
            if business_unit_ids is not None and bu_id not in business_unit_ids:
                continue
            is_pending = record.manager_approval_status == "PENDING"
            if is_pending:
                pending += cents
                if not include_pending:
                    continue
            unit = units.get(bu_id)
            partner = unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED
            _, own_company, where = logger_object(record)
            # the client's contracting company; with none set yet (a prospect), the spender's own
            company_id = (client.contracting_company_id if client is not None else None) or own_company
            out.append({"key": (partner, bu_id, client_id), "amount": cents, "company_id": company_id,
                        "country": where, "pending": is_pending})
    return out, pending


def _share_corporate_expenses(expenses: List[Dict], corporate: Set[int], weights: Dict[int, int], units: Dict) -> List[Dict]:
    """A Corporate BU's own spend goes the way of its people's cost; its company stays the one that paid."""
    out = []
    for expense in expenses:
        partner, bu_id, client_id = expense["key"]
        if bu_id not in corporate:
            out.append(expense)
            continue
        for target, share in prorated_shares(expense["amount"], weights).items():
            unit = units.get(target)
            out.append({"key": (unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED, target, client_id),
                        "amount": share, "company_id": expense["company_id"],
                        "country": expense.get("country"), "pending": expense.get("pending", False)})
    return out


def month_bounds(year: int, month: int):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


# ---- recognition when an invoice is paid ---------------------------------------------

def invoice_cost(db: Session, invoice: Invoice, costs: Optional[CostBook] = None) -> Optional[int]:
    costs = costs or CostBook(db)
    items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    employees = _by_id(db, Employee, Employee.id, (i.employee_id for i in items))
    total = 0
    for item in items:
        hourly = costs.hourly(employees.get(item.employee_id), invoice.billing_period_start)
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
