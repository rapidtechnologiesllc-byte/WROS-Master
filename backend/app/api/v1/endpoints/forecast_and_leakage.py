"""
S-242 (Forecast vs Actual). Revenue leakage lives in revenue.py (/revenue/leakage).

Gated behind forecasts.view + revenue.view, BU-scoped via get_revenue_scoped_client_ids
(app.core.data_scope) -- the one rule every screen uses.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.revenue_visibility_scope import get_revenue_scoped_client_ids
from app.models.user import Users
from app.schemas.forecast_and_leakage import ForecastVsActualResponse, ForecastVsActualTrendResponse
from app.services.forecast_variance_service import get_forecast_vs_actual, get_forecast_vs_actual_trend

router = APIRouter(tags=["forecast-and-leakage"])

@router.get(
    "/forecast-vs-actual",
    response_model=ForecastVsActualResponse,
    dependencies=[Depends(require_resource_permission("forecasts", "view"))]
)
def forecast_vs_actual(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    client_ids = get_revenue_scoped_client_ids(db, current_user)
    return get_forecast_vs_actual(
        db, client_ids=list(client_ids) if client_ids is not None else None, year=year, month=month,
    )


@router.get(
    "/forecast-vs-actual/trend",
    response_model=ForecastVsActualTrendResponse,
    dependencies=[Depends(require_resource_permission("forecasts", "view"))]
)
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

