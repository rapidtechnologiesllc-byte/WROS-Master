from app.core.logging import logger
"""Agent operations endpoints for KPI, HR, and Employee Mental Health agents."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
import logging
from app.services import kpi_agent_service, hr_agent_service, employee_mental_health_agent_service

router = APIRouter(prefix="/agents", tags=["Agent Operations"])


# ============================================================================
# KPI Agent Endpoints
# ============================================================================

@router.get("/kpi/daily-kpis", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_daily_kpis(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get daily KPI snapshot and 2030 forecasting.

    Requires: admin.view (CEO, Super User, Finance)
    """
    try:
        kpis = kpi_agent_service.calculate_daily_kpis(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": kpis}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/alerts", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_kpi_alerts(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get KPI alerts for off-track metrics."""
    try:
        alerts = kpi_agent_service.get_kpi_alerts(db=db)
        return {"status": "success", "data": alerts}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HR Agent Endpoints
# ============================================================================

@router.get("/hr/dashboard", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_hr_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get comprehensive HR dashboard."""
    try:
        dashboard = hr_agent_service.get_hr_dashboard(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": dashboard}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr/attrition-risks", dependencies=[Depends(require_resource_permission("hr", "view"))])
def detect_attrition_risks(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Detect employees at risk of attrition."""
    try:
        at_risk = hr_agent_service.get_attrition_risks(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": at_risk}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr/development-needs", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_development_needs(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get employees ready for development or promotion."""
    try:
        needs = hr_agent_service.get_development_needs(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": needs}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr/engagement-metrics", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_engagement_metrics(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get org-wide engagement metrics."""
    try:
        metrics = hr_agent_service.get_engagement_metrics(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": metrics}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Employee Mental Health Agent Endpoints
# ============================================================================

@router.get("/wellness/dashboard", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_wellness_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get comprehensive mental health and wellbeing dashboard."""
    try:
        dashboard = employee_mental_health_agent_service.get_mental_health_dashboard(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": dashboard}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wellness/team-snapshot", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_team_wellbeing(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get team wellbeing snapshot."""
    try:
        snapshot = employee_mental_health_agent_service.get_team_wellbeing_snapshot(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": snapshot}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wellness/burnout-risks", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_burnout_risks(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Identify employees at burnout risk."""
    try:
        risks = employee_mental_health_agent_service.get_burnout_risks(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": risks}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wellness/employee/{employee_id}", dependencies=[Depends(require_resource_permission("hr", "view"))])
def get_employee_wellness(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get individual employee wellness assessment."""
    try:
        indicators = employee_mental_health_agent_service.get_stress_indicators(
            db=db,
            employee_id=employee_id
        )
        recommendations = employee_mental_health_agent_service.get_wellness_recommendations(
            db=db,
            employee_id=employee_id
        )
        return {
            "status": "success",
            "data": {
                "indicators": indicators,
                "recommendations": recommendations
            }
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
