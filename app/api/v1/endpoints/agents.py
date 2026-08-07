"""Agent endpoints for Partner ROI, CFO, and CEO agents."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.partner_roi_service import get_partner_kpis, get_partner_trend, get_partner_actions
from app.services.cfo_agent_service import (
    get_org_financial_snapshot, get_cfo_alerts, get_bu_financial_comparison,
    get_expense_breakdown, get_financial_forecast
)
from app.services.ceo_fy_progress_service import get_fy_progress, get_fy_executive_summary

router = APIRouter(prefix="/agents", tags=["Agents"])


# ============================================================================
# Partner ROI Agent Endpoints
# ============================================================================

@router.get("/partner-roi/{partner_id}/kpis", dependencies=[Depends(require_permission("revenue.view"))])
def get_partner_roi_kpis(
    partner_id: str,
    year_month: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get Partner's ROI and KPIs for a given month.

    Permissions: revenue.view (Finance + Partners can see their own; CEO/Finance see all)
    """
    try:
        kpis = get_partner_kpis(db, partner_id, year_month)

        # Scope check: Partner can only see their own KPIs; Finance/CEO see all
        if current_user.UserRole not in ["Finance", "Super User", "Admin"]:
            if current_user.UserID != partner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only view your own KPIs"
                )

        return {"status": "success", "data": kpis}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/partner-roi/{partner_id}/trend", dependencies=[Depends(require_permission("revenue.view"))])
def get_partner_roi_trend(
    partner_id: str,
    months_back: int = 6,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get Partner's KPI trend over last N months."""
    try:
        # Same scope check as KPIs
        if current_user.UserRole not in ["Finance", "Super User", "Admin"]:
            if current_user.UserID != partner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only view your own trend"
                )

        trend = get_partner_trend(db, partner_id, months_back)
        return {"status": "success", "data": trend}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/partner-roi/{partner_id}/actions", dependencies=[Depends(require_permission("revenue.view"))])
def get_partner_roi_actions(
    partner_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get prioritized action items for Partner based on KPIs."""
    try:
        if current_user.UserRole not in ["Finance", "Super User", "Admin"]:
            if current_user.UserID != partner_id:
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

@router.get("/cfo/financial-snapshot", dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_cfo_snapshot(
    year_month: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get org-wide financial snapshot (revenue.view_pnl gated).

    Permissions: revenue.view_pnl (Finance + CEO only)
    """
    try:
        snapshot = get_org_financial_snapshot(db, year_month)
        return {"status": "success", "data": snapshot}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cfo/alerts", dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_cfo_critical_alerts(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get critical financial alerts for CFO attention (revenue.view_pnl gated)."""
    try:
        alerts = get_cfo_alerts(db)
        return {"status": "success", "data": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cfo/bu-comparison", dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_cfo_bu_comparison(
    year_month: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Compare all BU financials side-by-side (revenue.view_pnl gated)."""
    try:
        comparison = get_bu_financial_comparison(db, year_month)
        return {"status": "success", "data": comparison}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cfo/expense-breakdown", dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_cfo_expenses(
    year_month: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get expense breakdown by category (revenue.view_pnl gated)."""
    try:
        breakdown = get_expense_breakdown(db, year_month)
        return {"status": "success", "data": breakdown}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cfo/forecast", dependencies=[Depends(require_permission("revenue.view_pnl"))])
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
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CEO FY Progress Dashboard Endpoints
# ============================================================================

@router.get("/ceo/fy-progress", dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_ceo_fy_progress(
    fy_year: int = 2026,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get org-wide FY progress against targets (revenue.view_pnl gated).

    Returns: headcount, revenue, new logos, engagement, retention, utilization, margin progress.
    """
    try:
        progress = get_fy_progress(db, fy_year)
        return {"status": "success", "data": progress}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ceo/fy-summary", dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_ceo_fy_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get executive summary of FY progress with top priorities (revenue.view_pnl gated)."""
    try:
        summary = get_fy_executive_summary(db)
        return {"status": "success", "data": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
