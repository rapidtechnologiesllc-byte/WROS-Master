import logging
from app.core.database import get_db
"""BU Head Dashboard Endpoints - Real data for business unit leaders."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.dependencies import get_current_user, require_resource_permission
from app.core.visibility import business_unit_choices, resolve_dashboard_bu
from app.services.bu_head_dashboard_service import BUHeadDashboardService
from app.models.user import Users

router = APIRouter(prefix="/dashboards/bu-head", tags=["BU Head Dashboard"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
    bu_id = resolve_dashboard_bu(current_user, business_unit_id)
    if bu_id is None:
        return {"status": "needs_business_unit", "data": None, "business_units": business_unit_choices(db)}

    data = BUHeadDashboardService.get_bu_dashboard_data(db, bu_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Business unit {bu_id} not found")

    return {
        "status": "success",
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
    bu_id = resolve_dashboard_bu(current_user, business_unit_id)
    if bu_id is None:
        return {"status": "needs_business_unit", "data": None, "business_units": business_unit_choices(db)}

    team = BUHeadDashboardService.get_team_details(db, bu_id)

    return {
        "status": "success",
        "data": {
            "team_members": team,
            "total_count": len(team)
        }
    }
