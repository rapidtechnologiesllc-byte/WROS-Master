"""BU Head Dashboard Endpoints - Real data for business unit leaders."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.dependencies import get_current_user
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
from app.services.bu_head_dashboard_service import BUHeadDashboardService
from app.models.user import Users

router = APIRouter(prefix="/dashboards/bu-head", tags=["BU Head Dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/summary")
async def get_bu_dashboard_summary(
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
    if not current_user.business_unit_id:
        raise HTTPException(status_code=403, detail="User not assigned to a business unit")

    data = BUHeadDashboardService.get_bu_dashboard_data(
        db,
        current_user.business_unit_id
    )

    return {
        "status": "success",
        "data": data
    }


@router.get("/team")
async def get_team_details(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed team member list with current allocations
    """
    if not current_user.business_unit_id:
        raise HTTPException(status_code=403, detail="User not assigned to a business unit")

    team = BUHeadDashboardService.get_team_details(
        db,
        current_user.business_unit_id
    )

    return {
        "status": "success",
        "data": {
            "team_members": team,
            "total_count": len(team)
        }
    }
