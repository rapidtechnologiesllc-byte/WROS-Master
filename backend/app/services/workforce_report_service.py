"""Workforce Overview (CEO 2026-10-14): where every employee stands between the bench, Staff
Aug and Core. Not recruitment: people already employed.

Each employee is in exactly one group, so the groups add up to headcount:

  BENCH_IN_BUDDY            no active allocation, Buddy Program not graduated
  BENCH_READY               no active allocation, graduated, not Core-certified (Staff Aug next)
  BENCH_CORE_READY          no active allocation, graduated and Core-certified (Core now)
  STAFF_AUG                 on a Staff Aug project, not Core-certified (proving themselves)
  STAFF_AUG_CORE_CERTIFIED  on a Staff Aug project and Core-certified (move to Core)
  CORE                      on a Core project (held until released)
  UNCLASSIFIED              allocated, but neither the project nor the client says Core or
                            Staff Aug: fix the data, the report cannot place them

A Core allocation wins over a Staff Aug one. Flags ride along: rolling off (an active
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
    ("BENCH_IN_BUDDY", "Bench: in Buddy Program", "Not allocated; Buddy not graduated, so no client yet."),
    ("BENCH_READY", "Bench: ready for Staff Aug", "Not allocated; graduated, not Core-certified."),
    ("BENCH_CORE_READY", "Bench: ready for Core", "Not allocated; graduated and Core-certified."),
    ("STAFF_AUG", "Staff Aug", "On a Staff Aug project, not Core-certified."),
    ("STAFF_AUG_CORE_CERTIFIED", "Staff Aug, Core-certified", "On Staff Aug and qualified for Core: move to Core."),
    ("CORE", "Core (direct client)", "On a Core project; held until released."),
    ("UNCLASSIFIED", "Allocated, unclassified", "The project and client have no Core / Staff Aug type set."),
)
FLAGS = (
    ("rolling_off", "Rolling off", "An active allocation ends within the roll-off window."),
    ("open_escalations", "Open escalations", "At least one escalation not yet resolved by a Director."),
    ("notice_period", "On notice", "Serving notice."),
)
GROUP_KEYS = tuple(key for key, _, _ in GROUPS)
FLAG_KEYS = tuple(key for key, _, _ in FLAGS)


def _group(employee: Employee, lines: List[Optional[str]]) -> str:
    if CORE in lines:
        return "CORE"
    if STAFF_AUG in lines:
        return "STAFF_AUG_CORE_CERTIFIED" if employee.core_certified else "STAFF_AUG"
    if lines:
        return "UNCLASSIFIED"
    if employee.buddy_program_status != DEPLOYABLE_BUDDY_STATUS:
        return "BENCH_IN_BUDDY"
    return "BENCH_CORE_READY" if employee.core_certified else "BENCH_READY"


def workforce_overview(db: Session, user: Users, *, group: Optional[str] = None,
                       flag: Optional[str] = None) -> Dict:
    """Counts for every group and flag; the people only for the one group or flag asked for
    (the dashboard needs numbers, each number's page needs its people)."""
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == user.tenant_id, bu_filter(db, user, Employee.bu_id),
                Employee.status.notin_(NOT_HEADCOUNT))
        .order_by(Employee.first_name, Employee.last_name)
        .all()
    )
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
