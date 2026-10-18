"""Training, Certification, and Partner-specific dashboards."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.visibility import partner_choices, resolve_dashboard_partner, should_bypass_bu_filter
from app.models.user import Users
from app.core.tenant_context import tenant_id_of
from app.services.training_certification_service import (
    get_buddy_program_overview,
    get_certification_summary,
    get_training_pipeline_status,
    get_open_positions,
    get_core_certified_employees,
)

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

# ============================================================================
# Training & Certification Dashboard
# ============================================================================


# ============================================================================
# Partner Dashboard (Current Demand, Pipeline, Certifications, Buddy, Core Certified)
# ============================================================================

def _heads_label(db, business_unit_id: int):
    """'<head> (BX-US), <head> (BX-IN)' -- the BU's head in each company, or None."""
    from app.models.location import Location
    from app.services.bu_leadership import location_heads

    rows = location_heads(db, business_unit_id)
    if not rows:
        return None
    names = {loc.id: loc.name for loc in db.query(Location).filter(Location.id.in_(list(rows)))}
    return ", ".join(sorted(f"{(r.head.UserName or r.head.UserEmail)} ({names.get(c, c)})" for c, r in rows.items()))


def _partner_scope(db, partner_id: str, tenant_id: int, business_unit_id: Optional[int]):
    """(partner, the partner's BUs in this tenant, the BU ids to report on). A business unit
    outside the partner's own is refused (403): the filter can only narrow, never widen."""
    from app.services.bu_leadership import partnered_business_units

    partner = db.query(Users).filter(Users.UserID == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    bus = partnered_business_units(db, partner_id, tenant_id)
    bu_ids = {bu.id for bu in bus}
    if business_unit_id is not None and business_unit_id not in bu_ids:
        raise HTTPException(status_code=403, detail="That business unit is not owned by this partner")
    return partner, bus, ({business_unit_id} if business_unit_id is not None else bu_ids)


@router.get(
    "/partner/performance",
    dependencies=[Depends(require_resource_permission("partner-dashboard", "view"))]
)
def get_partner_performance(
    partner_user_id: Optional[str] = Query(default=None, description="Org-level users choose a partner"),
    business_unit_id: Optional[int] = Query(default=None, description="One of the partner's BUs (default: all)"),
    year_month: Optional[str] = Query(default=None, description="YYYY-MM (default: current month)"),
    months_back: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Partner Home KPIs: revenue, margin, new logos, utilization and growth for the partner's
    business units -- all of them in total and each BU on its own -- with the monthly trend and
    prioritised actions. Same scope rules as GET /dashboards/partner: a partner sees only their
    own BUs; org-level users pick a partner.
    """
    from app.services.partner_roi_service import get_partner_actions, get_partner_kpis, get_partner_trend

    partner_id = resolve_dashboard_partner(db, current_user, partner_user_id)
    if partner_id is None:
        return {"status": "needs_partner", "data": None, "partners": partner_choices(db)}
    partner, bus, scope = _partner_scope(db, partner_id, tenant_id_of(current_user), business_unit_id)
    if not scope:
        return {"status": "success", "partner": {"user_id": partner.UserID, "name": partner.UserName or partner.UserEmail},
                "business_units": [], "data": None}
    try:
        kpis = get_partner_kpis(db, partner_id, scope, year_month)
        trend = get_partner_trend(db, partner_id, scope, months_back, year_month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    names = {bu.id: bu.display_name or bu.name for bu in bus}
    for row in kpis["by_business_unit"]:
        row["business_unit_name"] = names.get(row["business_unit_id"])
    return {
        "status": "success",
        "partner": {"user_id": partner.UserID, "name": partner.UserName or partner.UserEmail},
        "business_units": [{"id": bu.id, "name": bu.display_name or bu.name} for bu in bus],
        "business_unit_id": business_unit_id,
        "data": {"kpis": kpis, "trend": trend, "actions": get_partner_actions(kpis)},
    }


@router.get(
    "/partner",
    dependencies=[Depends(require_resource_permission("partner-dashboard", "view"))]
)
def get_partner_dashboard(
    partner_user_id: Optional[str] = Query(default=None, description="Org-level users choose a partner"),
    business_unit_id: Optional[int] = Query(default=None, description="Narrow the operational sections to one of the partner's BUs"),
    year: Optional[int] = Query(default=None, description="Fiscal year (default: current)"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Partner dashboard: every business unit the partner owns, across every
    company it operates in (BX-US, BX-IN, ...). Revenue, headcount and new
    logos against the partner's FY targets per company and in total, then
    the operational view (open positions, pre-onboarding, certifications,
    buddy program, core-certified) for all their BUs or one of them.
    """
    from app.services.fiscal_year_service import current_fy, fy_info
    from app.services.goal_tree_service import TREE_METRICS, build_company_tree

    partner_id = resolve_dashboard_partner(db, current_user, partner_user_id)
    if partner_id is None:
        return {"status": "needs_partner", "data": None, "partners": partner_choices(db)}

    tenant_id = tenant_id_of(current_user)
    partner, bus, scope = _partner_scope(db, partner_id, tenant_id, business_unit_id)
    bu_ids = {bu.id for bu in bus}

    year = year or current_fy(db, tenant_id)
    companies, _ = build_company_tree(db, tenant_id, year, partner_user_id=partner_id) if bu_ids else ([], {})
    by_company = []
    for company in companies:
        node = next((p for p in company["children"] if p["partner_user_id"] == partner_id), None)
        if node:
            by_company.append({"company_id": company["entity_id"], "company": company["name"],
                               "metrics": node["metrics"], "business_units": node["children"]})
    totals = {}
    for m in TREE_METRICS:
        targets = [c["metrics"][m]["target"] for c in by_company if c["metrics"][m]["target"]]
        actual = sum(c["metrics"][m]["actual"] for c in by_company)
        target = sum(targets) if targets else None
        totals[m] = {"target": target, "actual": actual,
                     "progress_pct": round(actual / target * 100, 1) if target else None}

    operational = None
    if scope:
        operational = {
            "current_demand": {"open_positions": get_open_positions(db, scope)},
            "pre_onboarding_pipeline": get_training_pipeline_status(db, scope),
            "certifications": get_certification_summary(db, scope),
            "buddy_program": get_buddy_program_overview(db, scope),
            "core_certified_employees": get_core_certified_employees(db, scope),
        }
    return {
        "status": "success",
        "partner": {"user_id": partner.UserID, "name": partner.UserName or partner.UserEmail},
        "partners": partner_choices(db) if should_bypass_bu_filter(current_user) else None,
        "fy_label": fy_info(db, year, tenant_id)["label"],
        # heads are per company: "Name (company), ..." for each BU
        "business_units": [{"id": bu.id, "name": bu.display_name or bu.name, "head": _heads_label(db, bu.id)}
                           for bu in bus],
        "business_unit_id": business_unit_id,
        "totals": totals,
        "by_company": by_company,
        "data": operational,
    }

