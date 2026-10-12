"""BU Head Dashboard Endpoints - Real data for business unit leaders."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.core.visibility import resolve_dashboard_head_bu
from app.models.user import Users
from app.services.bu_head_dashboard_service import BUHeadDashboardService

router = APIRouter(prefix="/dashboards/bu-head", tags=["BU Head Dashboard"])


def _bu_targets_by_company(db: Session, user: Users, bu_id: int) -> list:
    """This BU's FY revenue / headcount / new-logo targets vs actuals in each company it operates in."""
    from app.services.fiscal_year_service import current_fy
    from app.services.goal_tree_service import build_company_tree

    tenant_id = user.tenant_id or 1
    tree, _ = build_company_tree(db, tenant_id, current_fy(db, tenant_id), bu_ids={bu_id})
    return [
        {"company_id": c["entity_id"], "company": c["name"], "metrics": bu["metrics"]}
        for c in tree for p in c["children"] for bu in p["children"]
    ]


@router.get(
    "/summary",
    dependencies=[Depends(require_resource_permission("bu-head-dashboard", "view"))]
)
async def get_bu_dashboard_summary(
    business_unit_id: Optional[int] = Query(default=None, description="Org-level users / users without a BU choose one"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get BU Head dashboard summary with real data:
    - Team utilization metrics
    - Revenue (MTD and ARN)
    - Bench cost
    - Active projects

    Scoped to user's business_unit_id
    """
    bu_id, allowed = resolve_dashboard_head_bu(db, current_user, business_unit_id)
    if bu_id is None:
        return {"status": "needs_business_unit", "data": None, "business_units": allowed}

    data = BUHeadDashboardService.get_bu_dashboard_data(db, bu_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Business unit {bu_id} not found")

    return {
        "status": "success",
        "business_unit_id": bu_id,
        # The BUs this viewer may switch between (more than one for a partner or admin)
        "business_units": allowed,
        "targets_by_company": _bu_targets_by_company(db, current_user, bu_id),
        "data": data
    }

@router.get(
    "/team",
    dependencies=[Depends(require_resource_permission("bu-head-dashboard", "view"))]
)
async def get_team_details(
    business_unit_id: Optional[int] = Query(default=None, description="Org-level users / users without a BU choose one"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed team member list with current allocations
    """
    bu_id, allowed = resolve_dashboard_head_bu(db, current_user, business_unit_id)
    if bu_id is None:
        return {"status": "needs_business_unit", "data": None, "business_units": allowed}

    team = BUHeadDashboardService.get_team_details(db, bu_id)

    return {
        "status": "success",
        "data": {
            "team_members": team,
            "total_count": len(team)
        }
    }
