"""The bench, defined once (CEO 2026-10-22).

On the bench = a billable employee who is headcount (joined, not exited) and holds no ACTIVE
allocation. Non-billable (internal) staff are never bench: their cost is overhead.

The bench pool table (BenchPoolEntry: who is on the bench now and since when) is the stored form
of that rule, kept in step by every write that changes it -- allocation start/end
(employee_allocation_service), joining (employee_service.place_unallocated_joiner), import,
billable changes (set_billable) -- and reconciled at startup (reconcile_bench_pool, from
db_contract) so a row written before these rules can never leave a surface out of step.
Employee.billing_classification is derived here and nowhere else.
"""
import logging
from datetime import date, timedelta
from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import BenchPeriod, BenchPoolEntry

logger = logging.getLogger(__name__)

NOT_HEADCOUNT = ("EXITED", "PRE_JOINING")


def has_active_allocation(db: Session, employee: Employee) -> bool:
    return db.query(EmployeeAllocation.id).filter(EmployeeAllocation.employee_id == employee.id,
                                                  EmployeeAllocation.status == "ACTIVE").first() is not None


def belongs_on_bench(db: Session, employee: Employee) -> bool:
    return (bool(employee.is_billable) and employee.status not in NOT_HEADCOUNT
            and not has_active_allocation(db, employee))


def classification(db: Session, employee: Employee) -> str:
    if not employee.is_billable:
        return "NON_BILLABLE"
    return "ALLOCATED" if has_active_allocation(db, employee) else "BENCH"


def sync_billing_classification(db: Session, employee: Employee) -> None:
    employee.billing_classification = classification(db, employee)


def bench_start_from_history(db: Session, employee: Employee, today: Optional[date] = None) -> date:
    """The real first bench day: the day after their last allocation ended, else their joining date."""
    last_end = db.query(func.max(EmployeeAllocation.end_date)).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.status != "ACTIVE").scalar()
    start = (last_end + timedelta(days=1)) if last_end else employee.joining_date
    start = max(start, employee.joining_date)
    return min(start, today or date.today())


def set_billable(db: Session, employee: Employee, billable: bool, *, changed_by: Optional[str]) -> None:
    """Reclassify an employee. Becoming non-billable takes them off the bench (BENCH -> ACTIVE);
    becoming billable with no allocation puts them on it from today."""
    from app.services.employee_service import place_unallocated_joiner, transition_employee_status
    from app.services.resource_management_service import remove_employee_from_bench

    if bool(employee.is_billable) == bool(billable):
        return
    employee.is_billable = bool(billable)
    if not billable:
        remove_employee_from_bench(db, employee)
        if employee.status == "BENCH":
            transition_employee_status(db, employee, "ACTIVE", reason="Reclassified as non-billable (internal)",
                                       changed_by=changed_by)
    elif employee.status == "ACTIVE" and not has_active_allocation(db, employee):
        place_unallocated_joiner(db, employee, changed_by=changed_by, bench_since=date.today())
    sync_billing_classification(db, employee)
    db.add(employee)
    logger.info(f"[Bench] {employee.id} billable={billable} by {changed_by}")


def reconcile_bench_pool(db: Session, today: Optional[date] = None) -> Dict[str, int]:
    """Make the bench pool match the rule for every employee: add who belongs (from their real
    first bench day), remove who does not, derive billing_classification. Idempotent; commits."""
    today = today or date.today()
    pool = {e.employee_id: e for e in db.query(BenchPoolEntry).all()}
    active = {row[0] for row in db.query(EmployeeAllocation.employee_id).filter(EmployeeAllocation.status == "ACTIVE")}
    added = removed = reclassified = 0
    for employee in db.query(Employee).all():
        on_bench = bool(employee.is_billable) and employee.status not in NOT_HEADCOUNT and employee.id not in active
        expected = "NON_BILLABLE" if not employee.is_billable else ("ALLOCATED" if employee.id in active else "BENCH")
        if employee.billing_classification != expected:
            employee.billing_classification = expected
            reclassified += 1
        if on_bench and employee.id not in pool:
            start = bench_start_from_history(db, employee, today)
            db.add(BenchPoolEntry(tenant_id=employee.tenant_id, employee_id=employee.id, available_from=start,
                                  skill_tags=employee.current_skills))
            if not db.query(BenchPeriod.id).filter(BenchPeriod.employee_id == employee.id,
                                                   BenchPeriod.bench_end_date.is_(None)).first():
                db.add(BenchPeriod(tenant_id=employee.tenant_id, employee_id=employee.id, bench_start_date=start,
                                   reason_for_bench="OTHER"))
            added += 1
        elif not on_bench and employee.id in pool:
            from app.services.resource_management_service import remove_employee_from_bench

            remove_employee_from_bench(db, employee)
            removed += 1
    db.commit()
    result = {"added": added, "removed": removed, "reclassified": reclassified}
    if added or removed or reclassified:
        logger.info(f"[Bench] pool reconciled: {result}")
    return result


# --------------------------------------------------------------------------- reading the bench

BENCH_GROUPS = ("BENCH_IN_BUDDY", "BENCH_READY", "BENCH_CORE_READY")
BENCH_PATH = "/workforce/bench"


def bench_since(db: Session, employee: Employee, today: Optional[date] = None) -> date:
    """First day of the current bench spell: the bench pool row (kept by every write and the
    startup reconciliation); a missing row is a data fault, logged, and read from history."""
    entry = db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).first()
    if entry is not None:
        return entry.available_from
    logger.error(f"[Bench] {employee.id} is on the bench with no bench pool row; using allocation history")
    return bench_start_from_history(db, employee, today)


def headcount_snapshot(db: Session, *, tenant_id: Optional[int] = None, bu_ids=None,
                       today: Optional[date] = None) -> Dict:
    """Billable headcount, who of them is allocated and who is on the bench (with bench days):
    the numbers every dashboard shows. bu_ids None = every business unit."""
    today = today or date.today()
    query = db.query(Employee).filter(Employee.status.notin_(NOT_HEADCOUNT))
    if tenant_id is not None:
        query = query.filter(Employee.tenant_id == tenant_id)
    if bu_ids is not None:
        query = query.filter(Employee.bu_id.in_(list(bu_ids) or [-1]))
    working = query.all()
    ids = [e.id for e in working]
    active = {row[0] for row in db.query(EmployeeAllocation.employee_id).filter(
        EmployeeAllocation.status == "ACTIVE", EmployeeAllocation.employee_id.in_(ids))} if ids else set()
    billable = [e for e in working if e.is_billable]
    bench = [e for e in billable if e.id not in active]
    pool = {p.employee_id: p.available_from for p in db.query(BenchPoolEntry).filter(
        BenchPoolEntry.employee_id.in_([e.id for e in bench]))} if bench else {}
    days = {e.id: (today - (pool.get(e.id) or bench_since(db, e, today))).days for e in bench}
    return {"working": working, "billable": billable, "allocated": [e for e in billable if e.id in active],
            "non_billable": [e for e in working if not e.is_billable], "bench": bench, "bench_days": days}


def bench_report(db: Session, user, *, group: Optional[str] = None, business_unit_id: Optional[int] = None,
                 today: Optional[date] = None, financials: Optional[bool] = None) -> Dict:
    """The bench screen: everyone in the Workforce Overview bench groups the caller can see, with
    days on bench, the cost of that bench time (loaded payroll from the P&L's CostBook for each
    bench day -- the same figure the P&L books as bench cost), what they earned while allocated
    (revenue minus delivery cost from the revenue chain) and the net. Sorted by bench loss.
    financials None = whether the caller may see P&L figures."""
    from app.core.revenue_visibility_scope import can_view_pnl
    from app.models.business_unit import BusinessUnit
    from app.models.location import Location
    from app.services.revenue_chain_service import CostBook, chain_lines
    from app.services.workforce_report_service import GROUPS, workforce_overview

    today = today or date.today()
    if group is not None and group not in BENCH_GROUPS:
        raise ValueError(f"'{group}' is not a bench group ({', '.join(BENCH_GROUPS)}).")
    show_money = can_view_pnl(db, user) if financials is None else financials
    labels = {key: label for key, label, _ in GROUPS}
    people = []
    for key in ((group,) if group else BENCH_GROUPS):
        for person in workforce_overview(db, user, group=key)["selection"]["people"]:
            people.append((key, person))
    employees = {e.id: e for e in db.query(Employee).filter(Employee.id.in_([p["employee_id"] for _, p in people]))} \
        if people else {}
    if business_unit_id is not None:
        people = [(k, p) for k, p in people if employees[p["employee_id"]].bu_id == business_unit_id]
    units = {u.id: u for u in db.query(BusinessUnit).filter(BusinessUnit.id.in_({e.bu_id for e in employees.values()}))}
    companies = {c.id: c for c in db.query(Location).filter(Location.id.in_({e.company_id for e in employees.values()}))}
    costs = CostBook(db)
    rows, missing = [], []
    for key, person in people:
        employee = employees[person["employee_id"]]
        since = bench_since(db, employee, today)
        unit, company = units.get(employee.bu_id), companies.get(employee.company_id)
        row = {
            "employee_id": employee.id, "name": person["name"], "group": key, "group_label": labels[key],
            "business_unit_id": employee.bu_id, "business_unit": (unit.display_name or unit.name) if unit else None,
            "location": company.name if company else None,
            # the cost object today's bench day is charged to (BU x location)
            "country": costs.object_on(employee, today)[2],
            "cost_object": f"{(unit.display_name or unit.name) if unit else 'No BU'} x {costs.object_on(employee, today)[2] or 'unknown location'}",
            "bench_since": since.isoformat(), "bench_days": (today - since).days,
            "daily_cost_usd_cents": None, "bench_loss_usd_cents": None, "earned_usd_cents": None,
            "delivery_cost_usd_cents": None, "allocated_margin_usd_cents": None, "net_usd_cents": None,
        }
        if show_money:
            loss = costs.period(employee, since, today)
            lines = chain_lines(db, start=employee.joining_date, end=today, employee_id=employee.id, costs=costs)
            earned = sum(line["earned_usd_cents"] or 0 for line in lines)
            line_costs = [line["cost_usd_cents"] for line in lines]
            delivery = None if any(c is None for c in line_costs) else sum(line_costs)
            if loss is None or delivery is None:
                missing.append(employee.id)
            row.update({
                "daily_cost_usd_cents": costs.period(employee, today, today), "bench_loss_usd_cents": loss,
                "earned_usd_cents": earned, "delivery_cost_usd_cents": delivery,
                "allocated_margin_usd_cents": earned - delivery if delivery is not None else None,
                "net_usd_cents": (earned - delivery - loss) if (delivery is not None and loss is not None) else None,
            })
        rows.append(row)
    rows.sort(key=lambda r: (r["bench_loss_usd_cents"] is None, -(r["bench_loss_usd_cents"] or 0), -r["bench_days"]))

    def total(field):
        return sum(r[field] or 0 for r in rows) if show_money else None

    return {
        "as_of": today.isoformat(), "group": group, "business_unit_id": business_unit_id,
        "financials_visible": show_money, "cost_data_complete": not missing, "missing_cost_employee_ids": missing,
        "groups": [{"key": k, "label": labels[k]} for k in BENCH_GROUPS],
        "totals": {"people": len(rows), "bench_days": sum(r["bench_days"] for r in rows),
                   "bench_loss_usd_cents": total("bench_loss_usd_cents"), "earned_usd_cents": total("earned_usd_cents"),
                   "allocated_margin_usd_cents": total("allocated_margin_usd_cents"),
                   "net_usd_cents": total("net_usd_cents"), "daily_cost_usd_cents": total("daily_cost_usd_cents")},
        "employees": rows,
    }
