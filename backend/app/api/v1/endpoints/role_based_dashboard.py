import logging
"""Role-Based Dashboard API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.role_based_dashboard_service import RoleBasedDashboardService
from app.services.permission_helper import PermissionHelper

router = APIRouter(prefix="/dashboard", tags=["Role-Based Dashboard"])


@router.get("/my-dashboard")
    dependencies=[Depends(require_resource_permission("my-dashboard", "view"))]
def get_my_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get personalized dashboard for current user based on their role.

    Returns:
    - CEO: Strategic view (all agents, KPI, risk, forecast)
    - Recruiter: Recruitment pipeline (Thunder, interviews, offers)
    - HR: Employee lifecycle (retention, onboarding, culture)
    - Finance: Revenue tracking (pipeline, ARR, margins)
    - Manager: Team operations (utilization, deployment, performance)
    - Employee: Personal (timesheet, tasks, performance)
    """

    try:
        dashboard = RoleBasedDashboardService.get_dashboard_for_role(
            db=db,
            user=current_user,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None
        )

        return {
            "status": "success",
            "user_email": current_user.UserEmail,
            "user_role": current_user.UserRole,
            "dashboard": dashboard,
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ceo-strategic")
    dependencies=[Depends(require_resource_permission("ceo-strategic", "view"))]
def get_ceo_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    CEO Strategic Dashboard - All agents, risks, forecast.

    Required: CEO or Admin role
    """

    try:
        # Permission-based check: only users with admin.manage permission can view CEO dashboard
        tenant_id = getattr(current_user, 'TenantID', 1)
        if not PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Only CEO/Admin can view strategic dashboard"
            )

        dashboard = RoleBasedDashboardService._ceo_dashboard(db, None)

        return {
            "status": "success",
            "dashboard_type": "CEO_STRATEGIC",
            "dashboard": dashboard,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recruiter-pipeline")
    dependencies=[Depends(require_resource_permission("recruiter-pipeline", "view"))]
def get_recruiter_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Recruiter Pipeline Dashboard - Thunder, candidates, interviews, offers.

    Required: Recruiter role
    """

    try:
        # Permission-based check: recruiters can create candidates, which is their key permission
        # Also allow admins (admin.manage permission)
        tenant_id = getattr(current_user, 'TenantID', 1)
        can_recruit = (
            PermissionHelper.has_permission(current_user.UserID, "candidate.create", db, tenant_id) or
            PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)
        )
        if not can_recruit:
            raise HTTPException(
                status_code=403,
                detail="Only Recruiters can view pipeline dashboard"
            )

        dashboard = RoleBasedDashboardService._recruiter_dashboard(db, None)

        return {
            "status": "success",
            "dashboard_type": "RECRUITER_PIPELINE",
            "dashboard": dashboard,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr-people")
    dependencies=[Depends(require_resource_permission("hr-people", "view"))]
def get_hr_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    HR People Dashboard - Retention, onboarding, culture, wellbeing.

    Required: HR Manager role
    """

    try:
        # Permission-based check: HR can edit employees, which is their key permission
        # Also allow admins (admin.manage permission)
        tenant_id = getattr(current_user, 'TenantID', 1)
        can_access_hr = (
            PermissionHelper.has_permission(current_user.UserID, "employee.edit", db, tenant_id) or
            PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)
        )
        if not can_access_hr:
            raise HTTPException(
                status_code=403,
                detail="Only HR Managers can view people dashboard"
            )

        dashboard = RoleBasedDashboardService._hr_dashboard(db, None)

        return {
            "status": "success",
            "dashboard_type": "HR_PEOPLE",
            "dashboard": dashboard,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/finance-revenue")
    dependencies=[Depends(require_resource_permission("finance-revenue", "view"))]
def get_finance_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Finance Revenue Dashboard - Pipeline, revenue, margins, cash.

    Required: Finance role
    """

    try:
        # Permission-based check: Finance has revenue.view_pnl permission
        # Also allow admins (admin.manage permission)
        tenant_id = getattr(current_user, 'TenantID', 1)
        can_access_finance = (
            PermissionHelper.has_permission(current_user.UserID, "revenue.view_pnl", db, tenant_id) or
            PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)
        )
        if not can_access_finance:
            raise HTTPException(
                status_code=403,
                detail="Only Finance staff can view revenue dashboard"
            )

        dashboard = RoleBasedDashboardService._finance_dashboard(db, None)

        return {
            "status": "success",
            "dashboard_type": "FINANCE_REVENUE",
            "dashboard": dashboard,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
