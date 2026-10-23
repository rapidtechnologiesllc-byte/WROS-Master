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
