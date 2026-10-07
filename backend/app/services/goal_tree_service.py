"""FY goal tree: Org -> Location (legal entity, e.g. BXUS/BXIN) -> Partner -> BU.

Structure comes from real records:
- Location: Delivery Centers (app.models.location.Location); a BU's
  location is BusinessUnit.location_id.
- Partner: an org-chart node at the "Partner" hierarchy level; a BU's
  partner is its active PartnerBUAssignment.
- BU: BusinessUnit.

Targets live in goal_targets (one row per level/entity/metric/year). The
ORG level carries every FY metric (the CEO Dashboard reads it); lower
levels carry the metrics that add up across the tree (revenue,
headcount, new logos). A PARTNER target is per partner *within a
location* (entity_id "<location_id>:<partner_node_id>"), since a partner
can own BUs in more than one entity.

Actuals are computed per BU and summed upward, so every node shows
target, actual, and how much of its target is allocated to its children.
"""
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.location import Location
from app.models.org_structure import OrgNode, PartnerBUAssignment
from app.models.strategic_goal import GOAL_LEVELS, GoalTarget
from app.models.user import Users
from app.services.ceo_fy_progress_service import FY_METRICS, WORKING_STATUSES_EXCLUDED, billable_employee_ids, get_fy_progress

logger = logging.getLogger(__name__)

ORG_ENTITY = "org"
NO_LOCATION = "unassigned"
NO_PARTNER = "unassigned"
# Metrics that add up across the tree (rates like margin % don't)
TREE_METRICS = ("revenue", "headcount", "new_logos")


def partner_hierarchy_level() -> int:
    """The org-chart level that holds partners (named in the validator's level table)."""
    from app.services.org_hierarchy_validator import HIERARCHY_LEVELS
    for level, name in HIERARCHY_LEVELS.items():
        if name.lower().startswith("partner"):
            return level
    raise RuntimeError("No Partner level in HIERARCHY_LEVELS")


def _targets(db: Session, tenant_id: int, year: int) -> Dict[tuple, float]:
    rows = db.query(GoalTarget).filter(GoalTarget.tenant_id == tenant_id, GoalTarget.year == year).all()
    return {(r.level, r.entity_id, r.metric): r.target for r in rows}


def _bu_actuals(db: Session, tenant_id: int, year: int) -> Dict[int, Dict[str, float]]:
    start, end = datetime(year, 1, 1), datetime(year + 1, 1, 1)
    actuals: Dict[int, Dict[str, float]] = defaultdict(lambda: {m: 0 for m in TREE_METRICS})

    for bu_id, cents in (
        db.query(Client.business_unit_id, func.sum(Invoice.total_usd_cents))
        .join(Client, Client.id == Invoice.client_id)
        .filter(Client.business_unit_id.isnot(None), Invoice.status.in_(("APPROVED", "SENT", "PAID")),
                Invoice.created_at >= start, Invoice.created_at < end)
        .group_by(Client.business_unit_id).all()
    ):
        actuals[bu_id]["revenue"] = (cents or 0) / 100

    for bu_id, count in (
        db.query(Employee.bu_id, func.count(Employee.id))
        .filter(Employee.bu_id.isnot(None), Employee.status.notin_(WORKING_STATUSES_EXCLUDED),
                Employee.id.in_(billable_employee_ids()))
        .group_by(Employee.bu_id).all()
    ):
        actuals[bu_id]["headcount"] = count

    for bu_id, count in (
        db.query(Client.business_unit_id, func.count(Client.id))
        .filter(Client.business_unit_id.isnot(None), Client.status == "ACTIVE",
                Client.created_at >= start, Client.created_at < end)
        .group_by(Client.business_unit_id).all()
    ):
        actuals[bu_id]["new_logos"] = count
    return actuals


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


def get_goal_tree(db: Session, tenant_id: int, year: Optional[int] = None) -> dict:
    year = year or datetime.utcnow().year
    targets = _targets(db, tenant_id, year)
    bu_actuals = _bu_actuals(db, tenant_id, year)

    locations = {l.id: l for l in db.query(Location).filter(Location.tenant_id == tenant_id).all()}
    bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id, BusinessUnit.active.is_(True)).all()
    partner_of = {
        a.business_unit_id: a.partner_org_node_id
        for a in db.query(PartnerBUAssignment).filter(
            PartnerBUAssignment.tenant_id == tenant_id, PartnerBUAssignment.active.is_(True)
        ).order_by(PartnerBUAssignment.id).all()
    }
    partner_nodes = {
        n.id: n for n in db.query(OrgNode).filter(
            OrgNode.tenant_id == tenant_id, OrgNode.hierarchy_level == partner_hierarchy_level()
        ).all()
    }

    # location -> partner -> [bu]
    grouped: Dict[str, Dict[str, List[BusinessUnit]]] = defaultdict(lambda: defaultdict(list))
    for bu in bus:
        loc = bu.location_id if bu.location_id in locations else NO_LOCATION
        partner = partner_of.get(bu.id) if partner_of.get(bu.id) in partner_nodes else NO_PARTNER
        grouped[loc][partner].append(bu)

    location_nodes = []
    for loc_id in list(locations) + ([NO_LOCATION] if NO_LOCATION in grouped else []):
        partner_list = []
        for partner_id, partner_bus in sorted(
            grouped.get(loc_id, {}).items(),
            key=lambda kv: (kv[0] == NO_PARTNER, partner_nodes[kv[0]].name if kv[0] in partner_nodes else ""),
        ):
            bu_list = [
                {
                    "level": "BU", "entity_id": str(bu.id), "name": bu.display_name or bu.name,
                    "editable": True,
                    "metrics": _metric_cells("BU", str(bu.id), TREE_METRICS, targets, bu_actuals[bu.id]),
                }
                for bu in sorted(partner_bus, key=lambda b: b.name)
            ]
            entity = f"{loc_id}:{partner_id}"
            editable = loc_id != NO_LOCATION and partner_id != NO_PARTNER
            partner_list.append({
                "level": "PARTNER", "entity_id": entity,
                "name": partner_nodes[partner_id].name if partner_id in partner_nodes else "No partner assigned",
                "editable": editable,
                "metrics": _metric_cells("PARTNER", entity, TREE_METRICS, targets, _sum(bu_list), bu_list),
                "children": bu_list,
            })
        location = locations.get(loc_id)
        location_nodes.append({
            "level": "LOCATION", "entity_id": loc_id,
            "name": location.name if location else "No location assigned",
            "editable": location is not None,
            "metrics": _metric_cells("LOCATION", loc_id, TREE_METRICS, targets, _sum(partner_list), partner_list),
            "children": partner_list,
        })

    progress = get_fy_progress(db, year, tenant_id=tenant_id)
    org_actuals = {m["key"]: m["current"] for m in progress["metrics"]}
    org = {
        "level": "ORG", "entity_id": ORG_ENTITY, "name": "Organization", "editable": True,
        "metrics": _metric_cells("ORG", ORG_ENTITY, list(FY_METRICS), targets, org_actuals, location_nodes),
        "children": location_nodes,
    }
    for key, m in ((m["key"], m) for m in progress["metrics"]):
        org["metrics"][key]["status"] = m["status"]

    return {
        "year": year,
        "fy_progress_pct": progress["fy_progress_pct"],
        "metrics": [{"key": k, "label": v[0], "unit": v[1], "detail": v[2], "rolls_up": k in TREE_METRICS}
                    for k, v in FY_METRICS.items()],
        "tree": org,
        "setup": {
            "locations": len(locations),
            "business_units": len(bus),
            "partners": len(partner_nodes),
            "bus_without_location": sum(1 for b in bus if b.location_id not in locations),
            "bus_without_partner": sum(1 for b in bus if partner_of.get(b.id) not in partner_nodes),
        },
    }


def _validate_entity(db: Session, tenant_id: int, level: str, entity_id: str) -> None:
    if level == "ORG":
        if entity_id != ORG_ENTITY:
            raise ValueError("ORG targets use entity_id 'org'")
    elif level == "LOCATION":
        if not db.query(Location).filter(Location.id == entity_id, Location.tenant_id == tenant_id).first():
            raise ValueError("Unknown location")
    elif level == "PARTNER":
        loc_id, _, partner_id = entity_id.partition(":")
        if not db.query(Location).filter(Location.id == loc_id, Location.tenant_id == tenant_id).first():
            raise ValueError("Unknown location for this partner target")
        if not db.query(OrgNode).filter(OrgNode.id == partner_id, OrgNode.tenant_id == tenant_id,
                                        OrgNode.hierarchy_level == partner_hierarchy_level()).first():
            raise ValueError("Unknown partner")
    elif level == "BU":
        if not entity_id.isdigit() or not db.query(BusinessUnit).filter(
            BusinessUnit.id == int(entity_id), BusinessUnit.tenant_id == tenant_id
        ).first():
            raise ValueError("Unknown business unit")


def set_goal_target(db: Session, user: Users, *, level: str, entity_id: str, metric: str,
                    target: Optional[float], year: Optional[int] = None) -> Optional[GoalTarget]:
    """Create/update a target, or clear it with target=None. Raises ValueError on bad input."""
    year = year or datetime.utcnow().year
    if level not in GOAL_LEVELS:
        raise ValueError(f"level must be one of {GOAL_LEVELS}")
    allowed = list(FY_METRICS) if level == "ORG" else list(TREE_METRICS)
    if metric not in allowed:
        raise ValueError(f"{metric!r} is not a {level.lower()} metric; allowed: {allowed}")
    if target is not None and target <= 0:
        raise ValueError("Target must be positive")
    tenant_id = user.tenant_id
    _validate_entity(db, tenant_id, level, entity_id)

    row = db.query(GoalTarget).filter(
        GoalTarget.tenant_id == tenant_id, GoalTarget.year == year, GoalTarget.level == level,
        GoalTarget.entity_id == entity_id, GoalTarget.metric == metric,
    ).first()
    if target is None:
        if row:
            db.delete(row)
            db.commit()
        return None
    if row is None:
        row = GoalTarget(tenant_id=tenant_id, year=year, level=level, entity_id=entity_id, metric=metric)
        db.add(row)
    row.target = target
    row.updated_by = user.UserID

    if level == "BU" and metric == "revenue":
        # Keep the BU revenue-target history (revenue target vs actual
        # endpoints) in step: append-only, latest row wins.
        from app.models.revenue_target import BURevenueTarget
        db.add(BURevenueTarget(
            tenant_id=tenant_id, business_unit_id=int(entity_id), target_period="ANNUAL", fiscal_year=year,
            target_amount_usd_cents=int(round(target * 100)), created_by=user.UserID,
            notes="Set on the Goals screen",
        ))
    db.commit()
    db.refresh(row)
    logger.info(f"[GoalTree] {user.UserID} set {level}/{entity_id}/{metric}/{year} = {target}")
    return row
