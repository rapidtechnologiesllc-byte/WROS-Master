"""
Task 6 (EPIC-03 Revenue-to-Workforce Conversion). Gated at
revenue.view_pnl -- revenue-per-head is a P&L-adjacent figure, same
tier as target-setting and leakage detail elsewhere in EPIC-02/03.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
from app.models.user import Users
from app.schemas.revenue_to_demand import RevenueToDemandProjectionResponse
from app.services.revenue_to_demand_service import get_revenue_to_demand_projection

router = APIRouter(tags=["revenue-to-demand"])


@router.get("/revenue-to-demand/bu/{business_unit_id}", response_model=RevenueToDemandProjectionResponse)
def revenue_to_demand_projection(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return get_revenue_to_demand_projection(db, business_unit_id=business_unit_id, year=year, month=month)
