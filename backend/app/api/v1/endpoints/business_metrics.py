import logging
from app.core.logging import logger
"""Business Metrics Endpoints - Daily standup business outcomes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.business_metrics_service import compile_daily_business_standup
from app.services.permission_helper import PermissionHelper

router = APIRouter(prefix="/business-metrics", tags=["Business Metrics"])

@router.get("/daily-standup", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_daily_business_standup(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get daily business standup metrics - what agents actually accomplished.

    Shows:
    - Recruitment: candidates in pipeline, conversion rates, interviews scheduled
    - Offers: acceptance rates, progress toward hiring targets
    - Onboarding: new employees, current headcount, progress toward 2000 target
    - Allocation: resource utilization, project assignments
    - Revenue: daily revenue, paid invoices, outstanding AR

    Required: admin.view
    """
    try:
        tenant_id = getattr(current_user, 'TenantID', 1)
        if not PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Only CEO/Admin can view business metrics"
            )

        metrics = compile_daily_business_standup(db, tenant_id=current_user.tenant_id)

        return {
            "status": "success",
            "viewer_role": current_user.UserRole,
            "data": metrics
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recruitment/{days_back}", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_recruitment_metrics_period(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get recruitment metrics for a specific number of days."""
    try:
        from app.services.business_metrics_service import get_recruitment_metrics

        metrics = get_recruitment_metrics(db, days_back=days_back, tenant_id=current_user.tenant_id)

        return {
            "status": "success",
            "period_days": days_back,
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/interviews/{days_back}", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_interview_metrics_period(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get interview metrics for a specific number of days."""
    try:
        from app.services.business_metrics_service import get_interview_metrics

        metrics = get_interview_metrics(db, days_back=days_back, tenant_id=current_user.tenant_id)

        return {
            "status": "success",
            "period_days": days_back,
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/offers/{days_back}", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_offer_metrics_period(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get offer metrics for a specific number of days."""
    try:
        from app.services.business_metrics_service import get_offer_metrics

        metrics = get_offer_metrics(db, days_back=days_back, tenant_id=current_user.tenant_id)

        return {
            "status": "success",
            "period_days": days_back,
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/revenue/{days_back}", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_revenue_metrics_period(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get revenue metrics for a specific number of days."""
    try:
        from app.services.business_metrics_service import get_revenue_metrics

        metrics = get_revenue_metrics(db, days_back=days_back, tenant_id=current_user.tenant_id)

        return {
            "status": "success",
            "period_days": days_back,
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
