"""Agent endpoints for the CFO and CEO agents. (Partner performance: /dashboards/partner/performance.)"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.cfo_agent_service import (
    get_org_financial_snapshot, get_cfo_alerts, get_bu_financial_comparison,
    get_expense_breakdown, get_financial_forecast
)
from app.core.logging import logger
from app.services.ceo_fy_progress_service import get_fy_progress, get_fy_executive_summary

router = APIRouter(prefix="/agents", tags=["Agents"])

# ============================================================================
# CFO Agent Endpoints
# ============================================================================


@router.get("/cfo/financial-snapshot", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_cfo_financial_snapshot(
    year_month: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Org financial snapshot for one month (the CFO screen loads this first)."""
    return {"status": "success", "data": get_org_financial_snapshot(db, year_month, tenant_id=current_user.tenant_id)}


@router.get("/cfo/bu-comparison", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_cfo_bu_comparison(
    year_month: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    return {"status": "success", "data": get_bu_financial_comparison(db, year_month)}


@router.get("/cfo/cost-breakdown", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_cfo_cost_breakdown(
    year_month: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delivery, bench and expense cost for the month, from the P&L."""
    return {"status": "success", "data": get_expense_breakdown(db, year_month, tenant_id=current_user.tenant_id)}


@router.get("/cfo/alerts", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_cfo_critical_alerts(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get critical financial alerts for CFO attention (revenue.view_pnl gated)."""
    try:
        alerts = get_cfo_alerts(db)
        return {"status": "success", "data": alerts}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cfo/forecast", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_cfo_forecast(
    months_ahead: int = 3,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get financial forecast for next N months (revenue.view_pnl gated)."""
    try:
        forecast = get_financial_forecast(db, months_ahead)
        return {"status": "success", "data": forecast}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CEO FY Progress Dashboard Endpoints
# ============================================================================

@router.get("/ceo/fy-progress", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_ceo_fy_progress(
    fy_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get org-wide FY progress against targets (revenue.view_pnl gated).

    Returns: headcount, revenue, new logos, engagement, retention, utilization, margin progress.
    """
    try:
        progress = get_fy_progress(db, fy_year, tenant_id=current_user.tenant_id)
        return {"status": "success", "data": progress}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ceo/fy-summary", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_ceo_fy_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get executive summary of FY progress with top priorities (revenue.view_pnl gated)."""
    try:
        summary = get_fy_executive_summary(db, tenant_id=current_user.tenant_id)
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

