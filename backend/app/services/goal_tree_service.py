"""FY goal tree: Org -> Company (legal entity, e.g. BX-US / BX-IN) -> Partner -> BU.

Structure comes from real records:
- Company: app.models.location.Location (the Companies tab).
- BU: BusinessUnit; the companies it operates in are BusinessUnitCompany
  rows, so one BU (e.g. AxION) appears under every company it runs in,
  with its own target in each.
- Partner: BusinessUnit.partner_user_id, a user with the Partner role. One
  partner owns many BUs, in every company each BU operates in.
- BU head: per company (BusinessUnitLocationHead) -- AXION has one partner but its
  own head in BX-US and in BX-IN; shown on each company's BU row.

Targets live in goal_targets (one row per level/entity/metric/year):
- ORG      entity "org"                    every FY metric (CEO Dashboard)
- LOCATION entity "<company_id>"           (the stored level name for Company)
- PARTNER  entity "<company_id>:<user_id>" a partner within one company
- BU       entity "<company_id>:<bu_id>"   a BU within one company

Actuals are computed per (company, BU) and summed upward:
- revenue: approved/sent/paid invoices, attributed to the client's
  contracting company and BU, plus intercompany billing received (the
  Intercompany Ledger, e.g. BX-IN billing BX-US) for the receiving company.
  The org total counts external client revenue only, so intercompany
  billing shows on the company but is not added again at org level.
- headcount: billable working employees, by employer company and BU.
- new_logos: clients added this FY, by contracting company and BU.
Rows without a company or partner land in "unassigned" buckets so nothing
silently disappears from the totals.

Visibility (app.core.data_scope): an org-level role template sees and sets the whole tree.
Anyone else sees only the branches of the business units they partner, head or belong to
(the firm-wide FY figures stay on the Organization node, read-only), and may set targets
only on those BUs' rows.
"""
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit, BusinessUnitCompany, BusinessUnitLocationHead
from app.models.client import Client
from app.models.employee import Employee
from app.models.intercompany_ledger import IntercompanySettlement
from app.models.invoice import Invoice
from app.models.location import Location
from app.models.strategic_goal import GOAL_LEVELS, GoalTarget
from app.models.user import Users
from app.services.ceo_fy_progress_service import FY_METRICS, WORKING_STATUSES_EXCLUDED, billable_employee_ids, get_fy_progress

logger = logging.getLogger(__name__)

ORG_ENTITY = "org"
UNASSIGNED = "unassigned"
# Metrics that add up across the tree (rates like margin % don't)
TREE_METRICS = ("revenue", "headcount", "new_logos")
REVENUE_STATUSES = ("APPROVED", "SENT", "PAID")

CellKey = Tuple[str, Optional[int]]  # (company_id or UNASSIGNED, bu_id)


def _targets(db: Session, tenant_id: int, year: int) -> Dict[tuple, float]:
    rows = db.query(GoalTarget).filter(GoalTarget.tenant_id == tenant_id, GoalTarget.year == year).all()
    return {(r.level, r.entity_id, r.metric): r.target for r in rows}


def company_bu_actuals(db: Session, tenant_id: int, year: int) -> Tuple[Dict[CellKey, Dict[str, float]], float]:
    """Actuals per (company, BU) for the FY, and the intercompany revenue included in them."""
    from app.services.fiscal_year_service import fy_window
    start, end = fy_window(db, year, tenant_id)
    companies = {l.id: l for l in db.query(Location).filter(Location.tenant_id == tenant_id).all()}
    actuals: Dict[CellKey, Dict[str, float]] = defaultdict(lambda: {m: 0 for m in TREE_METRICS})

    def key(company_id, bu_id) -> CellKey:
        return (company_id if company_id in companies else UNASSIGNED, bu_id)

    for company_id, bu_id, cents in (
        db.query(Client.contracting_company_id, Client.business_unit_id, func.sum(Invoice.total_usd_cents))
        .join(Client, Client.id == Invoice.client_id)
        .filter(Invoice.status.in_(REVENUE_STATUSES), Invoice.created_at >= start, Invoice.created_at < end)
        .group_by(Client.contracting_company_id, Client.business_unit_id).all()
    ):
        actuals[key(company_id, bu_id)]["revenue"] += (cents or 0) / 100

    intercompany = 0.0
    for to_company_id, bu_id, cents in (
        db.query(IntercompanySettlement.to_company_id, IntercompanySettlement.business_unit_id,
                 func.sum(IntercompanySettlement.amount_usd_cents))
        .filter((IntercompanySettlement.tenant_id == tenant_id) | IntercompanySettlement.tenant_id.is_(None),
                IntercompanySettlement.settlement_date >= start.date(), IntercompanySettlement.settlement_date < end.date())
        .group_by(IntercompanySettlement.to_company_id, IntercompanySettlement.business_unit_id).all()
    ):
        amount = (cents or 0) / 100
        actuals[key(to_company_id, bu_id)]["revenue"] += amount
        intercompany += amount

    for company_id, bu_id, count in (
        db.query(Employee.company_id, Employee.bu_id, func.count(Employee.id))
        .filter(Employee.status.notin_(WORKING_STATUSES_EXCLUDED), Employee.id.in_(billable_employee_ids()))
        .group_by(Employee.company_id, Employee.bu_id).all()
    ):
        actuals[key(company_id, bu_id)]["headcount"] += count

    for company_id, bu_id, count in (
        db.query(Client.contracting_company_id, Client.business_unit_id, func.count(Client.id))
        .filter(Client.status == "ACTIVE", Client.created_at >= start, Client.created_at < end)
        .group_by(Client.contracting_company_id, Client.business_unit_id).all()
    ):
        actuals[key(company_id, bu_id)]["new_logos"] += count
    return actuals, intercompany


def _metric_cells(level: str, entity_id: str, metrics, targets, actuals, children: Optional[List[dict]] = None) -> dict:
    cells = {}
    for m in metrics:
        target = targets.get((level, entity_id, m))
        cell = {"target": target, "actual": actuals.get(m, 0)}
        if target:
            cell["progress_pct"] = round(cell["actual"] / target * 100, 1)
        if children is not None and m in TREE_METRICS:
            allocated = [c["metrics"][m]["target"] for c in children if c["metrics"][m]["target"]]
            cell["allocated"] = sum(allocated) if allocated else None
        cells[m] = cell
    return cells


def _sum(children: List[dict]) -> Dict[str, float]:
    return {m: sum(c["metrics"][m]["actual"] for c in children) for m in TREE_METRICS}


def build_company_tree(db: Session, tenant_id: int, year: int, partner_user_id: Optional[str] = None,
                       bu_ids: Optional[set] = None) -> Tuple[List[dict], dict]:
    """Company -> Partner -> BU nodes. partner_user_id / bu_ids narrow the
    tree to one partner's or some BUs' slice (Partner / BU Head dashboards)."""
    targets = _targets(db, tenant_id, year)
    actuals, intercompany = company_bu_actuals(db, tenant_id, year)
    companies = {l.id: l for l in db.query(Location).filter(Location.tenant_id == tenant_id).order_by(Location.name).all()}
    bus = {b.id: b for b in db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).all()}

    # (company, bu) cells to show: every BU in every company it operates in,
    # plus any cell that has actuals (e.g. a client/employee with no company)
    cells = {(c.company_id, c.business_unit_id) for c in db.query(BusinessUnitCompany).filter(
        BusinessUnitCompany.tenant_id == tenant_id) if c.company_id in companies and c.business_unit_id in bus}
    cells |= {(cid, bu_id) for (cid, bu_id), vals in actuals.items() if bu_id in bus and any(vals.values())}
    cells |= {(UNASSIGNED, bu_id) for bu_id, b in bus.items()
              if b.active and not any(bid == bu_id for _, bid in cells)}

    def keep(bu_id):
        bu = bus[bu_id]
        if partner_user_id is not None and bu.partner_user_id != partner_user_id:
            return False
        return bu_ids is None or bu_id in bu_ids
    cells = {c for c in cells if keep(c[1])}

    grouped: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    for company_id, bu_id in cells:
        grouped[company_id][bus[bu_id].partner_user_id or UNASSIGNED].append(bu_id)
    # BU heads are per company (BusinessUnitLocationHead): (company_id, bu_id) -> name
    heads = {
        (row.company_id, row.business_unit_id): (user.UserName or user.UserEmail)
        for row, user in db.query(BusinessUnitLocationHead, Users)
        .join(Users, Users.UserID == BusinessUnitLocationHead.head_user_id)
        .filter(BusinessUnitLocationHead.tenant_id == tenant_id)
    }
    partner_users = {u.UserID: u for u in db.query(Users).filter(
        Users.UserID.in_({b.partner_user_id for b in bus.values() if b.partner_user_id})).all()}

    company_nodes = []
    for company_id in list(companies) + ([UNASSIGNED] if UNASSIGNED in grouped else []):
        if company_id not in grouped and (partner_user_id is not None or bu_ids is not None):
            continue
        partner_list = []
        for pid, partner_bus in sorted(
            grouped.get(company_id, {}).items(),
            key=lambda kv: (kv[0] == UNASSIGNED, (partner_users[kv[0]].UserName or "") if kv[0] in partner_users else ""),
        ):
            bu_list = []
            for bu_id in sorted(partner_bus, key=lambda i: bus[i].name):
                entity = f"{company_id}:{bu_id}"
                bu_list.append({
                    "level": "BU", "entity_id": entity, "bu_id": bu_id, "company_id": company_id,
                    "name": bus[bu_id].display_name or bus[bu_id].name,
                    "head": heads.get((company_id, bu_id)),
                    "editable": company_id != UNASSIGNED,
                    "metrics": _metric_cells("BU", entity, TREE_METRICS, targets, actuals.get((company_id, bu_id), {})),
                })
            entity = f"{company_id}:{pid}"
            partner = partner_users.get(pid)
            partner_list.append({
                "level": "PARTNER", "entity_id": entity, "partner_user_id": None if pid == UNASSIGNED else pid,
                "name": (partner.UserName or partner.UserEmail) if partner else "No partner assigned",
                "editable": company_id != UNASSIGNED and partner is not None,
                "metrics": _metric_cells("PARTNER", entity, TREE_METRICS, targets, _sum(bu_list), bu_list),
                "children": bu_list,
            })
        company = companies.get(company_id)
        company_nodes.append({
            "level": "LOCATION", "entity_id": company_id,
            "name": company.name if company else "No company assigned",
            "editable": company is not None,
            "metrics": _metric_cells("LOCATION", company_id, TREE_METRICS, targets, _sum(partner_list), partner_list),
            "children": partner_list,
        })

    setup = {
        "companies": len(companies),
        "business_units": sum(1 for b in bus.values() if b.active),
        "partners": len(partner_users),
        "bus_without_company": sum(1 for c, _ in cells if c == UNASSIGNED),
        "bus_without_partner": sum(1 for b in bus.values() if b.active and not b.partner_user_id),
        "intercompany_revenue": intercompany,
    }
    return company_nodes, setup


def get_goal_tree(db: Session, tenant_id: int, year: Optional[int] = None,
                  bu_ids: Optional[set] = None) -> dict:
    """bu_ids (None = everything, editable) narrows the tree to those BUs; only their BU
    rows stay editable."""
    from app.services.fiscal_year_service import current_fy, fy_info
    year = year or current_fy(db, tenant_id)
    targets = _targets(db, tenant_id, year)
    company_nodes, setup = build_company_tree(db, tenant_id, year, bu_ids=bu_ids)
    if bu_ids is not None:
        for company in company_nodes:
            company["editable"] = False
            for partner in company["children"]:
                partner["editable"] = False

    progress = get_fy_progress(db, year, tenant_id=tenant_id)
    org_actuals = {m["key"]: m["current"] for m in progress["metrics"]}
    org = {
        "level": "ORG", "entity_id": ORG_ENTITY, "name": "Organization", "editable": bu_ids is None,
        "metrics": _metric_cells("ORG", ORG_ENTITY, list(FY_METRICS), targets, org_actuals, company_nodes),
        "children": company_nodes,
    }
    for key, m in ((m["key"], m) for m in progress["metrics"]):
        org["metrics"][key]["status"] = m["status"]

    info = fy_info(db, year, tenant_id)
    return {
        "year": year,
        "fy_label": info["label"],
        "fy_start": info["start"],
        "fy_end": info["end"],
        "fy_start_month": info["start_month"],
        "current_fy": info["current_fy"],
        "fy_progress_pct": progress["fy_progress_pct"],
        "metrics": [{"key": k, "label": v[0], "unit": v[1], "detail": v[2], "rolls_up": k in TREE_METRICS}
                    for k, v in FY_METRICS.items()],
        "tree": org,
        "setup": setup,
    }


def _company(db: Session, tenant_id: int, company_id: str) -> Location:
    company = db.query(Location).filter(Location.id == company_id, Location.tenant_id == tenant_id).first()
    if not company:
        raise ValueError("Unknown company")
    return company


def _validate_entity(db: Session, tenant_id: int, level: str, entity_id: str) -> None:
    if level == "ORG":
        if entity_id != ORG_ENTITY:
            raise ValueError("ORG targets use entity_id 'org'")
    elif level == "LOCATION":
        _company(db, tenant_id, entity_id)
    elif level == "PARTNER":
        company_id, _, user_id = entity_id.partition(":")
        _company(db, tenant_id, company_id)
        if not db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id,
                                             BusinessUnit.partner_user_id == user_id).first():
            raise ValueError("Not a partner of any business unit")
    elif level == "BU":
        company_id, _, bu_id = entity_id.partition(":")
        _company(db, tenant_id, company_id)
        if not bu_id.isdigit() or not db.query(BusinessUnit).filter(
            BusinessUnit.id == int(bu_id), BusinessUnit.tenant_id == tenant_id
        ).first():
            raise ValueError("Unknown business unit")


def _ensure_can_set(db: Session, user: Users, level: str, entity_id: str) -> None:
    """Org-level role templates set any target; anyone else only their own BUs' rows."""
    from app.core.data_scope import visible_bu_ids

    visible = visible_bu_ids(db, user)
    if visible is None:
        return
    bu_id = entity_id.partition(":")[2]
    if level != "BU" or not bu_id.isdigit() or int(bu_id) not in visible:
        raise PermissionError("You can only set targets for your own business units")


def set_goal_target(db: Session, user: Users, *, level: str, entity_id: str, metric: str,
                    target: Optional[float], year: Optional[int] = None) -> Optional[GoalTarget]:
    """Create/update a target, or clear it with target=None. Raises ValueError on bad input,
    PermissionError when the row is outside the user's business units."""
    from app.services.fiscal_year_service import current_fy
    year = year or current_fy(db, user.tenant_id)
    if level not in GOAL_LEVELS:
        raise ValueError(f"level must be one of {GOAL_LEVELS}")
    allowed = list(FY_METRICS) if level == "ORG" else list(TREE_METRICS)
    if metric not in allowed:
        raise ValueError(f"{metric!r} is not a {level.lower()} metric; allowed: {allowed}")
    if target is not None and target <= 0:
        raise ValueError("Target must be positive")
    tenant_id = user.tenant_id
    _ensure_can_set(db, user, level, entity_id)
    _validate_entity(db, tenant_id, level, entity_id)

    row = db.query(GoalTarget).filter(
        GoalTarget.tenant_id == tenant_id, GoalTarget.year == year, GoalTarget.level == level,
        GoalTarget.entity_id == entity_id, GoalTarget.metric == metric,
    ).first()
    if target is None:
        if row:
            db.delete(row)
    else:
        if row is None:
            row = GoalTarget(tenant_id=tenant_id, year=year, level=level, entity_id=entity_id, metric=metric)
            db.add(row)
        row.target = target
        row.updated_by = user.UserID
    db.flush()

    if level == "BU" and metric == "revenue":
        # Keep the BU revenue-target history (revenue target vs actual
        # endpoints) in step with the BU's total across companies:
        # append-only, latest row wins.
        from app.models.revenue_target import BURevenueTarget
        bu_id = int(entity_id.partition(":")[2])
        total = sum(
            r.target for r in db.query(GoalTarget).filter(
                GoalTarget.tenant_id == tenant_id, GoalTarget.year == year, GoalTarget.level == "BU",
                GoalTarget.metric == "revenue", GoalTarget.entity_id.like(f"%:{bu_id}"),
            )
        )
        db.add(BURevenueTarget(
            tenant_id=tenant_id, business_unit_id=bu_id, target_period="ANNUAL", fiscal_year=year,
            target_amount_usd_cents=int(round(total * 100)), created_by=user.UserID,
            notes="Set on the Goals screen (sum across companies)",
        ))
    db.commit()
    if row is not None and target is not None:
        db.refresh(row)
    logger.info(f"[GoalTree] {user.UserID} set {level}/{entity_id}/{metric}/{year} = {target}")
    return row if target is not None else None
