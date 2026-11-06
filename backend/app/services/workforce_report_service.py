"""Workforce Overview (CEO 2026-10-14): where every employee stands between the bench, Staff
Aug and Direct. Not recruitment: people already employed.

Each employee is in exactly one group, so the groups add up to headcount:

  NON_BILLABLE              internal staff (not billable): never bench, their cost is overhead
  BENCH_IN_BUDDY            no active allocation, Buddy Program not graduated
  BENCH_READY               no active allocation, graduated, not Direct-certified (Staff Aug next)
  BENCH_CORE_READY          no active allocation, graduated and Direct-certified (Direct now)
  STAFF_AUG                 on a Staff Aug project, not Direct-certified (proving themselves)
  STAFF_AUG_CORE_CERTIFIED  on a Staff Aug project and Direct-certified (move to Direct)
  CORE                      on a Direct project (held until released)
  UNCLASSIFIED              allocated, but neither the project nor the client says Direct or
                            Staff Aug: fix the data, the report cannot place them

A Direct allocation wins over a Staff Aug one. Flags ride along: rolling off (an active
allocation ending within ROLL_OFF_WINDOW_DAYS), open escalations, notice period. Former
(EXITED) and not-yet-joined (PRE_JOINING) employees are not headcount.

Batched: employees, their active allocations, the allocations' projects and clients, and open
escalations are four queries whatever the headcount (no per-employee lookups)."""
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.data_scope import bu_filter
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation
from app.models.project import Project
from app.models.user import Users
from app.services.deployment_readiness_service import CORE, DEPLOYABLE_BUDDY_STATUS, is_rolling_off

logger = logging.getLogger(__name__)

STAFF_AUG = "SPECIALITY"
NOT_HEADCOUNT = ("EXITED", "PRE_JOINING")

GROUPS = (
    ("NON_BILLABLE", "Non-billable (internal)", "Internal staff: never bench; their cost is overhead in the P&L."),
    ("BENCH_IN_BUDDY", "Bench: in Buddy Program", "Not allocated; Buddy not graduated, so no client yet."),
    ("BENCH_READY", "Bench: ready for Staff Aug", "Not allocated; graduated, not Direct-certified."),
    ("BENCH_CORE_READY", "Bench: ready for Direct", "Not allocated; graduated and Direct-certified."),
    ("STAFF_AUG", "Staff Aug", "On a Staff Aug project, not Direct-certified."),
    ("STAFF_AUG_CORE_CERTIFIED", "Staff Aug, Direct-certified", "On Staff Aug and qualified for Direct: move to Direct."),
    ("CORE", "Direct (to the client)", "On a Direct project; held until released."),
    ("UNCLASSIFIED", "Allocated, unclassified", "The project and client have no Direct / Staff Aug type set."),
)
FLAGS = (
    ("rolling_off", "Rolling off", "An active allocation ends within the roll-off window."),
    ("open_escalations", "Open escalations", "At least one escalation not yet resolved by a Director."),
    ("notice_period", "On notice", "Serving notice."),
)
GROUP_KEYS = tuple(key for key, _, _ in GROUPS)
FLAG_KEYS = tuple(key for key, _, _ in FLAGS)


def _group(employee: Employee, lines: List[Optional[str]]) -> str:
    if not employee.is_billable:
        return "NON_BILLABLE"
    if CORE in lines:
        return "CORE"
    if STAFF_AUG in lines:
        return "STAFF_AUG_CORE_CERTIFIED" if employee.core_certified else "STAFF_AUG"
    if lines:
        return "UNCLASSIFIED"
    if employee.buddy_program_status != DEPLOYABLE_BUDDY_STATUS:
        return "BENCH_IN_BUDDY"
    return "BENCH_CORE_READY" if employee.core_certified else "BENCH_READY"


def workforce_filters(db: Session, user: Users) -> Dict:
    """The choices for the overview's filters: only what exists among the people this user may see."""
    from app.models.location import Location
    from app.models.org_structure import Department
    from app.models.employee_org_history import country_of_company

    rows = (db.query(Employee.bu_id, Employee.company_id, Users.department_id)
            .outerjoin(Users, Users.UserID == Employee.wros_user_id)
            .filter(Employee.tenant_id == user.tenant_id, bu_filter(db, user, Employee.bu_id),
                    Employee.status.notin_(NOT_HEADCOUNT)).all())
    bu_ids, company_ids, function_ids = {r[0] for r in rows} - {None}, {r[1] for r in rows} - {None}, {r[2] for r in rows} - {None}
    units = db.query(BusinessUnit).filter(BusinessUnit.id.in_(bu_ids)).order_by(BusinessUnit.name).all()
    companies = db.query(Location).filter(Location.id.in_(company_ids)).order_by(Location.name).all()
    functions = db.query(Department).filter(Department.id.in_(function_ids)).order_by(Department.name).all()
    countries = sorted({c for c in (country_of_company(db, cid) for cid in company_ids) if c})
    return {"functions": [{"id": f.id, "name": f.name} for f in functions],
            "business_units": [{"id": u.id, "name": u.display_name or u.name} for u in units],
            "companies": [{"id": c.id, "name": c.name} for c in companies], "locations": countries}


def workforce_overview(db: Session, user: Users, *, group: Optional[str] = None, flag: Optional[str] = None,
                       function_id: Optional[str] = None, business_unit_id: Optional[int] = None,
                       company_id: Optional[str] = None, location: Optional[str] = None) -> Dict:
    """Counts for every group and flag; the people only for the one group or flag asked for
    (the dashboard needs numbers, each number's page needs its people). The filters narrow everyone
    counted, inside what this user may see."""
    query = db.query(Employee).filter(Employee.tenant_id == user.tenant_id, bu_filter(db, user, Employee.bu_id),
                                      Employee.status.notin_(NOT_HEADCOUNT))
    if function_id:
        query = query.join(Users, Users.UserID == Employee.wros_user_id).filter(Users.department_id == function_id)
    if business_unit_id:
        query = query.filter(Employee.bu_id == business_unit_id)
    if company_id:
        query = query.filter(Employee.company_id == company_id)
    employees = query.order_by(Employee.first_name, Employee.last_name).all()
    if location:
        from app.models.employee_org_history import country_of_company

        employees = [e for e in employees if country_of_company(db, e.company_id) == location]
    ids = [e.id for e in employees]
    allocations = defaultdict(list)
    for a in (db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id.in_(ids),
                                                  EmployeeAllocation.status == "ACTIVE").all() if ids else []):
        allocations[a.employee_id].append(a)
    flat = [a for rows in allocations.values() for a in rows]
    project_ids = {a.project_id for a in flat if a.project_id}
    client_ids = {a.client_id for a in flat if a.client_id}
    projects = {p.id: p for p in db.query(Project).filter(Project.id.in_(project_ids)).all()} if project_ids else {}
    clients = {c.id: c for c in db.query(Client).filter(Client.id.in_(client_ids)).all()} if client_ids else {}
    escalations = dict(
        db.query(EmployeeEscalation.employee_id, func.count(EmployeeEscalation.id))
        .filter(EmployeeEscalation.employee_id.in_(ids), EmployeeEscalation.status == "OPEN")
        .group_by(EmployeeEscalation.employee_id).all()
    ) if ids else {}
    unit_ids = {e.bu_id for e in employees if e.bu_id}
    units = dict(db.query(BusinessUnit.id, BusinessUnit.display_name).filter(BusinessUnit.id.in_(unit_ids)).all()) \
        if unit_ids else {}

    def line_of(a: EmployeeAllocation) -> Optional[str]:
        project = projects.get(a.project_id)
        if project is not None and project.delivery_engine:
            return project.delivery_engine
        client = clients.get(a.client_id)
        return client.line_type if client is not None else None

    people = defaultdict(list)
    for employee in employees:
        rows = allocations.get(employee.id, [])
        lines = [line_of(a) for a in rows]
        placed_in = _group(employee, lines)
        # the allocation that placed them in the group (Core first), shown on the row
        shown = next((a for a, line in zip(rows, lines) if line == CORE), None) or (rows[0] if rows else None)
        people[placed_in].append({
            "employee_id": employee.id,
            "candidate_id": employee.candidate_id,
            "name": f"{employee.first_name} {employee.last_name}".strip(),
            "business_unit": units.get(employee.bu_id),
            "status": employee.status,
            "buddy_program_status": employee.buddy_program_status,
            "core_certified": bool(employee.core_certified),
            "project": projects[shown.project_id].name if shown and shown.project_id in projects else None,
            "client": clients[shown.client_id].company_name if shown and shown.client_id in clients else None,
            "allocation_end_date": shown.end_date if shown else None,
            "rolling_off": any(is_rolling_off(a) for a in rows),
            "open_escalations": escalations.get(employee.id, 0),
            "notice_period": employee.status == "NOTICE_PERIOD",
        })

    flagged = {key: [] for key in FLAG_KEYS}
    for key, label, _ in GROUPS:
        for p in people[key]:
            row = {**p, "group": key, "group_label": label}
            for flag_key in FLAG_KEYS:
                if p[flag_key]:
                    flagged[flag_key].append(row)

    groups = [{"key": key, "label": label, "description": description, "count": len(people[key])}
              for key, label, description in GROUPS]
    flags = [{"key": key, "label": label, "description": description, "count": len(flagged[key])}
             for key, label, description in FLAGS]
    selection = None
    if group:
        meta = next(g for g in groups if g["key"] == group)
        selection = {**meta, "kind": "group",
                     "people": [{**p, "group": group, "group_label": meta["label"]} for p in people[group]]}
    elif flag:
        meta = next(f for f in flags if f["key"] == flag)
        selection = {**meta, "kind": "flag", "people": flagged[flag]}
    return {"headcount": len(employees), "roll_off_window_days": settings.ROLL_OFF_WINDOW_DAYS,
            "groups": groups, "flags": flags, "selection": selection}
