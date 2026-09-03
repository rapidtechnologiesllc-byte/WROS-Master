"""
S-256/HRMS-0506 (canonical) — Resource Demand Planning / Future Demand
vs Bench Forecast — API Endpoints
=========================================================================
Prefix: /resource-forecast
import logging
Tag:    resource-forecast

Wires app.services.resource_forecast_service (new this round -- no
existing backend for this story, unlike almost everything else in
EPIC-05) to real HTTP routes. Read-only reporting: BR-01 (source doc)
says allocation end dates are planning estimates, not contractual
commitments -- nothing here writes anything or treats them as actuals.

Auth: get_current_internal_user, same posture as every endpoint this
program.

Routes:
  GET /resource-forecast/expiring        Allocations ending in the next
                                          90 days, bucketed 30/30-60/60-90.
  GET /resource-forecast/gap-analysis    Per-skill projected bench supply
                                          vs open demand.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.schemas.resource_forecast import (
    ExpiringAllocationItem,
    ExpiringAllocationsResponse,
    SkillGapAnalysisResponse,
    SkillGapRow,
)
from app.services.resource_forecast_service import (
    get_expiring_allocations,
    get_skill_gap_analysis,
)

router = APIRouter(prefix="/resource-forecast", tags=["resource-forecast"])


@router.get(
    "/expiring", response_model=ExpiringAllocationsResponse,
    dependencies=[Depends(get_current_user)],
    summary="Employees whose allocation ends within 90 days, bucketed by horizon",
)
def expiring_allocations(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    buckets = get_expiring_allocations(db, tenant_id=current_user.tenant_id)
    return ExpiringAllocationsResponse(
        under_30_days=[ExpiringAllocationItem(**e) for e in buckets["under_30_days"]],
        thirty_to_60_days=[ExpiringAllocationItem(**e) for e in buckets["30_to_60_days"]],
        sixty_to_90_days=[ExpiringAllocationItem(**e) for e in buckets["60_to_90_days"]],
    )


@router.get(
    "/gap-analysis", response_model=SkillGapAnalysisResponse,
    dependencies=[Depends(get_current_user)],
    summary="Per-skill projected bench supply vs open demand, optionally scoped to one Business Unit's own demand",
)
def gap_analysis(
    business_unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    rows = get_skill_gap_analysis(db, tenant_id=current_user.tenant_id, business_unit_id=business_unit_id)
    return SkillGapAnalysisResponse(rows=[SkillGapRow(**r) for r in rows])
