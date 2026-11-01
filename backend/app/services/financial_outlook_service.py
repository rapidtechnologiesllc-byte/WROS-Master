"""Projected vs actual revenue, anticipated vs actual expense -- for the CEO, CFO, partner
and BU dashboards (CEO 2026-10-11).

How money moves through the business, and what each figure means:
  hire an employee      -> EXPENSE: their loaded payroll runs from the joining date,
                           on the bench or deployed alike
  deploy them (allocate)-> PROJECTED REVENUE: allocation bill rate x planned hours
                           (business days x STANDARD_DAILY_HOURS x utilization)
  they work, time approved -> EARNED revenue (approved timesheet hours x rate)
  invoice approved      -> BILLED
  client pays into our account -> ACTUAL revenue (cash received, by bank transaction date)

Expense:
  ANTICIPATED = the full period's loaded payroll of everyone employed in it (including
                people joining in it) + every expense logged for it that is not rejected
  ACTUAL      = payroll incurred so far (days elapsed up to today) + expenses reimbursed.
                There is no payroll-payment record in the system yet, so payroll is
                counted as incurred, not as paid out.

Every figure is attributed to a business unit in a company (clients by contracting
company, employees by employer company), rolled up to BU, partner
(BusinessUnit.partner_user_id) and org from the same rows, so the four dashboards can never
disagree. business_unit_ids keeps only the BUs the viewer may see (visibility by business
unit, never by location -- CEO 2026-10-12). Unknown inputs (an
allocation without a bill rate, an employee without salary or cost-rate config) are listed,
never counted as zero.
"""
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bank_reconciliation import BankTransaction
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.services.revenue_chain_service import UNASSIGNED, CostBook, chain_lines

logger = logging.getLogger(__name__)

NO_BU = None
FIGURES = ("projected_revenue", "earned_revenue", "billed_revenue", "actual_revenue",
           "anticipated_expense", "anticipated_bench_cost", "anticipated_deployed_cost", "anticipated_overhead_cost",
           "anticipated_other_expense",
           "actual_expense", "actual_payroll", "actual_other_expense")


def business_days(start: date, end: date) -> int:
    if end < start:
        return 0
    days, day = 0, start
    while day <= end:
        if day.weekday() < 5:
            days += 1
        day += timedelta(days=1)
    return days


def _overlap(a_start: date, a_end: Optional[date], start: date, end: date):
    first, last = max(a_start, start), min(a_end or end, end)
    return (first, last) if first <= last else None


def _empty() -> Dict[str, int]:
    return {k: 0 for k in FIGURES}


Cell = Tuple[Optional[int], Optional[str]]  # (business_unit_id, company_id)


def outlook(db: Session, *, start: date, end: date, today: Optional[date] = None,
            business_unit_ids: Optional[Iterable[int]] = None, tenant_id: Optional[int] = None) -> Dict:
    """Projected vs actual for [start, end]. business_unit_ids=None means the whole org."""
    scope = set(business_unit_ids) if business_unit_ids is not None else None

    def in_scope(bu_id, _company_id=None) -> bool:
        return scope is None or bu_id in scope

    if end < start:
        raise ValueError("end must be on or after start")
    today = today or date.today()
    rows: Dict[Cell, Dict[str, int]] = defaultdict(_empty)
    gaps = {"allocations_without_bill_rate": [], "employees_without_cost": []}
    costs = CostBook(db)
    units = {u.id: u for u in db.query(BusinessUnit).all()}
    clients: Dict[str, Client] = {}

    def client_cell(client_id) -> Cell:
        if client_id not in clients:
            clients[client_id] = db.query(Client).filter(Client.id == client_id).first()
        client = clients[client_id]
        return (client.business_unit_id, client.contracting_company_id) if client else (NO_BU, None)

    # projected revenue: deployed people x bill rate x planned hours
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.start_date <= end,
        (EmployeeAllocation.end_date.is_(None)) | (EmployeeAllocation.end_date >= start),
        EmployeeAllocation.status.in_(("ACTIVE", "ENDED", "CORE_PULLED")))
    if tenant_id is not None:
        allocations = allocations.filter(EmployeeAllocation.tenant_id == tenant_id)
    deployed_days: Dict[str, List] = defaultdict(list)
    for allocation in allocations.all():
        span = _overlap(allocation.start_date, allocation.end_date, start, end)
        if span is None:
            continue
        deployed_days[allocation.employee_id].append(span)
        if not allocation.billing_rate_usd_cents:
            if in_scope(*client_cell(allocation.client_id)):
                gaps["allocations_without_bill_rate"].append(allocation.id)
            continue
        hours = business_days(*span) * settings.STANDARD_DAILY_HOURS * float(allocation.utilization_pct or 100) / 100
        rows[client_cell(allocation.client_id)]["projected_revenue"] += round(hours * allocation.billing_rate_usd_cents)

    # earned and billed: the revenue chain's own timesheet lines (same figures as the P&L)
    for line in chain_lines(db, start=start, end=end, tenant_id=tenant_id, costs=costs):
        cell = client_cell(line["client_id"])
        rows[cell]["earned_revenue"] += line["earned_usd_cents"]
        rows[cell]["billed_revenue"] += line["billed_usd_cents"]

    # actual revenue: money received into the account in the period
    receipts = db.query(BankTransaction, Invoice).join(Invoice, Invoice.id == BankTransaction.matched_invoice_id).filter(
        BankTransaction.reconciled.is_(True), BankTransaction.transaction_date >= start,
        BankTransaction.transaction_date <= end)
    if tenant_id is not None:
        receipts = receipts.filter(BankTransaction.tenant_id == tenant_id)
    for transaction, invoice in receipts.all():
        rows[client_cell(invoice.client_id)]["actual_revenue"] += transaction.amount_usd_cents

    # payroll: anticipated for the whole period, actual as incurred up to today
    staff = db.query(Employee).filter(Employee.joining_date <= end,
                                      (Employee.exit_date.is_(None)) | (Employee.exit_date >= start))
    if tenant_id is not None:
        staff = staff.filter(Employee.tenant_id == tenant_id)
    incurred_end = min(end, today)
    for employee in staff.all():
        if employee.status == "EXITED" and employee.exit_date is None:
            continue
        period_cost = costs.period(employee, start, end)
        if period_cost is None:
            if in_scope(employee.bu_id):
                gaps["employees_without_cost"].append(employee.id)
            continue
        row = rows[(employee.bu_id, employee.company_id)]
        row["anticipated_expense"] += period_cost
        employed_from = max(start, employee.joining_date)
        employed_to = min(end, employee.exit_date) if employee.exit_date else end
        employed_days = (employed_to - employed_from).days + 1
        deployed = sum((min(s[1], employed_to) - max(s[0], employed_from)).days + 1
                       for s in deployed_days.get(employee.id, []) if max(s[0], employed_from) <= min(s[1], employed_to))
        deployed_share = min(1.0, deployed / employed_days) if employed_days > 0 else 0.0
        row["anticipated_deployed_cost"] += round(period_cost * deployed_share)
        # undeployed time of internal (non-billable) staff is overhead, never bench
        row["anticipated_bench_cost" if employee.is_billable else "anticipated_overhead_cost"] += \
            period_cost - round(period_cost * deployed_share)
        if employee.status != "PRE_JOINING" and incurred_end >= start:
            incurred = costs.period(employee, start, incurred_end)
            row["actual_payroll"] += incurred or 0
            row["actual_expense"] += incurred or 0

    # other expenses: anticipated = everything logged for the period that is not rejected;
    # actual = what has been reimbursed
    from app.models.expense import ExpenseRecord
    from app.services.expense_service import expense_shares

    expenses = db.query(ExpenseRecord).filter(ExpenseRecord.expense_date >= start, ExpenseRecord.expense_date <= end,
                                              ExpenseRecord.manager_approval_status != "REJECTED")
    if tenant_id is not None:
        expenses = expenses.filter(ExpenseRecord.tenant_id == tenant_id)
    records = expenses.all()
    shares = expense_shares(records)
    loggers = {e.wros_user_id: e for e in db.query(Employee).filter(
        Employee.wros_user_id.in_({r.logged_by_user_id for r in records} or {""}))}
    for record in records:
        # each client's part follows that client (a split expense lands on every client it names);
        # internal (personal) spend stays with the logging BU and goes to the company the logger
        # worked for on the expense date, like their salary (no employee record: company unknown)
        logger = loggers.get(record.logged_by_user_id)
        own_company = costs.object_on(logger, record.expense_date)[1] if logger is not None else None
        for client_id, cents in shares[record.id]:
            cell = client_cell(client_id) if client_id else (record.business_unit_id, own_company)
            row = rows[cell if cell[0] is not None else (record.business_unit_id, None)]
            row["anticipated_other_expense"] += cents
            row["anticipated_expense"] += cents
            if record.payment_status == "REIMBURSED":
                row["actual_other_expense"] += cents
                row["actual_expense"] += cents

    by_unit: Dict[Optional[int], Dict[str, int]] = defaultdict(_empty)
    for (bu_id, company_id), figures in rows.items():
        if not in_scope(bu_id):
            continue
        for k in FIGURES:
            by_unit[bu_id][k] += figures[k]
    if scope is not None:
        for bu_id in scope:
            by_unit[bu_id]  # every BU in scope gets a row, even with no activity
    rows = by_unit

    def section(figures: Dict[str, int]) -> Dict:
        out = dict(figures)
        out["revenue_variance"] = out["actual_revenue"] - out["projected_revenue"]  # cash vs plan
        out["expense_variance"] = out["actual_expense"] - out["anticipated_expense"]
        out["projected_net"] = out["projected_revenue"] - out["anticipated_expense"]
        out["actual_net"] = out["actual_revenue"] - out["actual_expense"]
        out["receivable"] = max(0, out["billed_revenue"] - out["actual_revenue"])  # billed, not yet paid
        out["unbilled"] = max(0, out["earned_revenue"] - out["billed_revenue"])   # worked, not yet invoiced
        return out

    by_bu, partners = [], defaultdict(_empty)
    for bu_id, figures in rows.items():
        unit = units.get(bu_id)
        partner = unit.partner_user_id if unit and unit.partner_user_id else UNASSIGNED
        by_bu.append({"key": bu_id, "name": unit.name if unit else "No business unit", "partner_user_id": partner,
                      **section(figures)})
        for k in FIGURES:
            partners[partner][k] += figures[k]
    org = _empty()
    for figures in rows.values():
        for k in FIGURES:
            org[k] += figures[k]

    from app.models.user import Users

    names = {u.UserID: u.UserName for u in db.query(Users).filter(Users.UserID.in_(set(partners) - {UNASSIGNED})).all()}
    return {
        "start": start.isoformat(), "end": end.isoformat(), "as_of": today.isoformat(),
        "currency": "USD", "fx_inr_per_usd": settings.FX_INR_PER_USD,
        **section(org),
        "by_business_unit": sorted(by_bu, key=lambda r: r["projected_revenue"], reverse=True),
        "by_partner": sorted(({"key": k, "name": names.get(k, "Unassigned" if k == UNASSIGNED else k), **section(v)}
                              for k, v in partners.items()), key=lambda r: r["projected_revenue"], reverse=True),
        "data_complete": not gaps["allocations_without_bill_rate"] and not gaps["employees_without_cost"],
        "gaps": gaps,
    }
