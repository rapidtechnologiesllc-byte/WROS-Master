"""
S-242 (Forecast vs Actual) + S-243 (Revenue Leakage Detection).

Gated behind revenue.view / revenue.view_pnl same as every other
EPIC-02 screen, BU-scoped via the same get_revenue_scoped_client_ids()/
apply_revenue_bu_scope_to_client_query() mechanism revenue_targets.py
already established -- not a second scoping implementation.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission, require_resource_permission
from app.core.revenue_visibility_scope import (
    apply_revenue_bu_scope_to_client_query, get_revenue_scoped_client_ids, is_revenue_bu_scoped,
)
from app.models.client import Client
from app.models.pipeline_leakage import PipelineLeakageFlag
from app.models.user import Users
from app.schemas.forecast_and_leakage import (
    ForecastVsActualResponse, ForecastVsActualTrendResponse, PipelineLeakageFlagItem,
    PipelineLeakageScanResponse, ResolveLeakageFlagRequest,
)
from app.services.forecast_variance_service import (
    get_forecast_vs_actual, get_forecast_vs_actual_by_bu, get_forecast_vs_actual_trend,
)
from app.services.pipeline_leakage_service import (
    get_active_leakage_flags, resolve_leakage_flag, scan_all_leakage,
)

router = APIRouter(tags=["forecast-and-leakage"])


def _caller_business_unit_ids(db: Session, current_user: Users) -> Optional[List[int]]:
    """None = org-wide (Super User/Finance/HR Manager). A real list =
    scoped to whichever BU(s) the caller's own client-visibility
    resolves to (Partner/BU Head) -- reuses the same client-scoping
    query rather than a second BU-membership lookup."""
    if not is_revenue_bu_scoped(db, current_user):
        return None
    query = apply_revenue_bu_scope_to_client_query(db, db.query(Client.business_unit_id).distinct(), current_user)
    return [row[0] for row in query.all() if row[0] is not None]


@router.get("/forecast-vs-actual", response_model=ForecastVsActualResponse)
def forecast_vs_actual(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    client_ids = get_revenue_scoped_client_ids(db, current_user)
    return get_forecast_vs_actual(
        db, client_ids=list(client_ids) if client_ids is not None else None, year=year, month=month,
    )


@router.get("/forecast-vs-actual/bu/{business_unit_id}", response_model=ForecastVsActualResponse)
def forecast_vs_actual_by_bu(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    scoped_bu_ids = _caller_business_unit_ids(db, current_user)
    if scoped_bu_ids is not None and business_unit_id not in scoped_bu_ids:
        raise HTTPException(status_code=403, detail="Not authorized to view this Business Unit's revenue.")
    return get_forecast_vs_actual_by_bu(db, business_unit_id=business_unit_id, year=year, month=month)


@router.get("/forecast-vs-actual/trend", response_model=ForecastVsActualTrendResponse)
def forecast_vs_actual_trend(
    year: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    client_ids = get_revenue_scoped_client_ids(db, current_user)
    months = get_forecast_vs_actual_trend(
        db, client_ids=list(client_ids) if client_ids is not None else None, year=year,
    )
    return ForecastVsActualTrendResponse(business_unit_id=None, year=year, months=months)


@router.post("/revenue-leakage/scan", response_model=PipelineLeakageScanResponse)
def scan_leakage(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """Leakage detail (which opportunity, which demand) is P&L-adjacent
    -- gated at revenue.view_pnl same tier as target-setting, not the
    broader revenue.view."""
    flags = scan_all_leakage(db, tenant_id=current_user.tenant_id)
    db.commit()
    for flag in flags:
        db.refresh(flag)
    total_impact = sum(f.estimated_impact_usd_cents or 0 for f in flags)
    return PipelineLeakageScanResponse(flags=flags, total_estimated_impact_usd_cents=total_impact)


@router.get("/revenue-leakage/active", response_model=PipelineLeakageScanResponse)
def active_leakage(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    scoped_bu_ids = _caller_business_unit_ids(db, current_user)
    flags = get_active_leakage_flags(db, business_unit_ids=scoped_bu_ids, tenant_id=current_user.tenant_id)
    total_impact = sum(f.estimated_impact_usd_cents or 0 for f in flags)
    return PipelineLeakageScanResponse(flags=flags, total_estimated_impact_usd_cents=total_impact)


@router.post("/revenue-leakage/{flag_id}/resolve", response_model=PipelineLeakageFlagItem)
def resolve_flag(
    flag_id: str, body: ResolveLeakageFlagRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    flag = db.query(PipelineLeakageFlag).filter(PipelineLeakageFlag.id == flag_id).first()
    if flag is None:
        raise HTTPException(status_code=404, detail="Leakage flag not found.")
    resolve_leakage_flag(db, flag, resolution_note=body.resolution_note)
    db.commit()
    db.refresh(flag)
    return flag
