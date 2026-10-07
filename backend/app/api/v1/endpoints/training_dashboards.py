"""Training, Certification, and Partner-specific dashboards."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.visibility import partner_choices, resolve_dashboard_partner, should_bypass_bu_filter
from app.models.user import Users
from app.services.training_certification_service import (
    get_buddy_program_overview,
    get_certification_summary,
    get_employee_training_status,
    get_training_pipeline_status,
    get_next_training_steps,
    get_open_positions,
    get_core_certified_employees,
)

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

# ============================================================================
# Training & Certification Dashboard
# ============================================================================


# ============================================================================
# Troy's Partner Dashboard (Current Demand, Pipeline, Certifications, Buddy, Core Certified)
# ============================================================================

@router.get(
    "/troy-partner",
    dependencies=[Depends(require_resource_permission("partner-dashboard", "view"))]
)
def get_troy_partner_dashboard(
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
    from app.models.business_unit import BusinessUnit
    from app.services.fiscal_year_service import current_fy, fy_info
    from app.services.goal_tree_service import TREE_METRICS, build_company_tree

    partner_id = resolve_dashboard_partner(db, current_user, partner_user_id)
    if partner_id is None:
        return {"status": "needs_partner", "data": None, "partners": partner_choices(db)}

    tenant_id = current_user.tenant_id or 1
    bus = db.query(BusinessUnit).filter(BusinessUnit.partner_user_id == partner_id,
                                        BusinessUnit.tenant_id == tenant_id).order_by(BusinessUnit.name).all()
    partner = db.query(Users).filter(Users.UserID == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    bu_ids = {bu.id for bu in bus}
    if business_unit_id is not None and business_unit_id not in bu_ids:
        raise HTTPException(status_code=403, detail="That business unit is not owned by this partner")
    scope = {business_unit_id} if business_unit_id is not None else bu_ids

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
        "business_units": [{"id": bu.id, "name": bu.display_name or bu.name,
                            "head": (bu.manager.UserName or bu.manager.UserEmail) if bu.manager else None}
                           for bu in bus],
        "business_unit_id": business_unit_id,
        "totals": totals,
        "by_company": by_company,
        "data": operational,
    }
