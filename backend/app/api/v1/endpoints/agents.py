"""Agent endpoints for Partner ROI, CFO, and CEO agents."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.partner_roi_service import get_partner_kpis, get_partner_trend, get_partner_actions
from app.services.cfo_agent_service import (
    get_org_financial_snapshot, get_cfo_alerts, get_bu_financial_comparison,
    get_expense_breakdown, get_financial_forecast
)
from app.core.logging import logger
from app.services.ceo_fy_progress_service import get_fy_progress, get_fy_executive_summary
from app.services.permission_helper import PermissionHelper

router = APIRouter(prefix="/agents", tags=["Agents"])

# ============================================================================
# Partner ROI Agent Endpoints
# ============================================================================


def _can_see_all_partners(db: Session, current_user: Users) -> bool:
    from app.services.role_template_permission_service import RoleTemplatePermissionService

    return RoleTemplatePermissionService.is_super_user(db, current_user.UserID, current_user.tenant_id) \
        or PermissionHelper.has_any_permission(current_user.UserID, ["admin.manage", "revenue.manage"], db,
                                               current_user.tenant_id)


def _own_partner_or_403(db: Session, current_user: Users, partner_id: str) -> None:
    can_see_all = _can_see_all_partners(db, current_user)
    if not can_see_all and current_user.UserID != partner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only view your own figures")


@router.get("/partner-roi/{partner_id}/kpis", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_partner_roi_kpis(
    partner_id: str,
    year_month: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Partner KPIs for one month (the Partner ROI screen loads this first)."""
    _own_partner_or_403(db, current_user, partner_id)
    try:
        return {"status": "success", "data": get_partner_kpis(db, partner_id, year_month)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/partner-roi/{partner_id}/trend", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_partner_roi_trend(
    partner_id: str,
    months_back: int = 6,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get Partner's KPI trend over last N months."""
    try:
        # Scope check: Partner can only see their own; Finance/CEO see all
        can_see_all = _can_see_all_partners(db, current_user)
        if not can_see_all and current_user.UserID != partner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only view your own trend"
            )

        trend = get_partner_trend(db, partner_id, months_back)
        return {"status": "success", "data": trend}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/partner-roi/{partner_id}/actions", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_partner_roi_actions(
    partner_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get prioritized action items for Partner based on KPIs."""
    try:
        can_see_all = _can_see_all_partners(db, current_user)
        if not can_see_all and current_user.UserID != partner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only view your own actions"
            )

        actions = get_partner_actions(db, partner_id)
        return {"status": "success", "data": actions}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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

