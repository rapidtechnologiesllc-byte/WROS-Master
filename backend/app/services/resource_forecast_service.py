"""
S-256/HRMS-0506 (canonical -- content-matched against `Requirements/
S-171_HRMS-0506.docx`; that filename's own "S-171" label is the same
class of ID drift already documented elsewhere in this codebase, e.g.
BenchPeriod's docstring) -- Resource Demand Planning / Future Demand vs
import logging
Bench Forecast.

Turns resource management from reactive to proactive: (1) which
employees are coming off allocation soon (30/60/90-day horizons), and
(2) per-skill, is projected bench supply (current bench + soon-expiring
allocations) ahead of or behind open demand.

BR-01 (source doc): expected end dates are planning estimates, not
contractual commitments -- this module only ever reads
EmployeeAllocation.end_date, never treats it as authoritative actuals.
"WHAT NOT TO BUILD" (source doc): no ML-based forecasting, no automated
re-allocation recommendations -- this is a read-only reporting layer
over existing data, nothing writes anything.
"""
import json
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import BenchPoolEntry

EXPIRY_HORIZON_DAYS = 90  # source doc's own default

def _parse_skills(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Operation failed")
    if not isinstance(parsed, list):
        raise ValueError("Operation failed")
    return [str(s).strip() for s in parsed if str(s).strip()]

def get_expiring_allocations(
    db: Session, *, tenant_id: Optional[int] = None, horizon_days: int = EXPIRY_HORIZON_DAYS,
) -> Dict[str, List[Dict]]:
    """Step 1: ACTIVE allocations with a planning end_date within the
    next horizon_days, bucketed into <30 / 30-60 / 60-90 day horizons
    (the doc's own three buckets -- horizon_days beyond 90 doesn't
    change the bucket boundaries, only how far out allocations are
    considered at all)."""
    today = date.today()
    cutoff = today + timedelta(days=horizon_days)

    query = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.status == "ACTIVE",
        EmployeeAllocation.end_date.isnot(None),
        EmployeeAllocation.end_date >= today,
        EmployeeAllocation.end_date <= cutoff,
    )
    if tenant_id is not None:
        query = query.filter(EmployeeAllocation.tenant_id == tenant_id)

    buckets = {"under_30_days": [], "30_to_60_days": [], "60_to_90_days": []}
    for allocation in query.all():
        employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
        if employee is None:
            continue
        days_out = (allocation.end_date - today).days
        entry = {
            "employee_id": employee.id,
            "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
            "skills": _parse_skills(employee.current_skills),
            "allocation_id": allocation.id,
            "demand_id": allocation.demand_id,
            "client_id": allocation.client_id,
            "end_date": allocation.end_date,
            "days_out": days_out,
        }
        if days_out < 30:
            buckets["under_30_days"].append(entry)
        elif days_out < 60:
            buckets["30_to_60_days"].append(entry)
        else:
            buckets["60_to_90_days"].append(entry)

    return buckets

def get_skill_gap_analysis(
    db: Session, *, tenant_id: Optional[int] = None, business_unit_id: Optional[int] = None,
) -> List[Dict]:
    """Step 2: per skill (union of every skill on a currently-benched
    employee and every skill required by an open/in-progress demand),
    current_bench_count + expiring_30d_count vs open_demand_count.
    Negative gap = shortage, positive = excess supply -- exactly the
    doc's own definition, not reinterpreted.

    business_unit_id, when given, filters the DEMAND side only
    (Demand.assigned_bu_id is real) -- bench supply stays org-wide.
    Neither Employee nor BenchPoolEntry carries a business_unit_id
    anywhere in this codebase (the exact gap the BlitzenX Operating
    Model entry in this file flags: "confirm employees are BU-scoped...
    before extending this system further") -- filtering bench counts by
    a BU that doesn't exist on the row would fabricate data, not narrow
    it. A BU Head reading this sees their own open demand against the
    real, full bench -- directionally correct, not silently wrong."""
    bench_query = db.query(BenchPoolEntry)
    if tenant_id is not None:
        bench_query = bench_query.filter(BenchPoolEntry.tenant_id == tenant_id)
    bench_entries = bench_query.all()

    bench_skill_counts: Dict[str, int] = {}
    for entry in bench_entries:
        for skill in _parse_skills(entry.skill_tags):
            bench_skill_counts[skill] = bench_skill_counts.get(skill, 0) + 1

    expiring = get_expiring_allocations(db, tenant_id=tenant_id, horizon_days=30)
    expiring_skill_counts: Dict[str, int] = {}
    for entry in expiring["under_30_days"]:
        for skill in entry["skills"]:
            expiring_skill_counts[skill] = expiring_skill_counts.get(skill, 0) + 1

    demand_query = db.query(Demand).filter(Demand.status.in_(("OPEN", "IN_PROGRESS")))
    if tenant_id is not None:
        demand_query = demand_query.filter(Demand.tenant_id == tenant_id)
    if business_unit_id is not None:
        demand_query = demand_query.filter(Demand.assigned_bu_id == business_unit_id)
    demand_skill_counts: Dict[str, int] = {}
    for demand in demand_query.all():
        for skill in _parse_skills(demand.required_skills):
            demand_skill_counts[skill] = demand_skill_counts.get(skill, 0) + 1

    all_skills = set(bench_skill_counts) | set(expiring_skill_counts) | set(demand_skill_counts)

    rows = []
    for skill in sorted(all_skills):
        current_bench = bench_skill_counts.get(skill, 0)
        expiring_30d = expiring_skill_counts.get(skill, 0)
        total_supply = current_bench + expiring_30d
        open_demand = demand_skill_counts.get(skill, 0)
        rows.append({
            "skill": skill,
            "current_bench_count": current_bench,
            "expiring_allocations_count_30d": expiring_30d,
            "total_projected_supply": total_supply,
            "open_demand_count": open_demand,
            "gap": total_supply - open_demand,
        })
    return rows
