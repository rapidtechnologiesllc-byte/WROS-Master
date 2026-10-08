"""
Admin Setup Endpoints - Initialize demo data and configuration

Endpoints for admin-level setup tasks (behind permission checks):
- POST /admin/setup/demo-data - Initialize demo data for testing
- GET /admin/setup/status - Check setup status
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users

router = APIRouter(prefix="/admin/setup", tags=["Admin Setup"])
logger = logging.getLogger(__name__)


@router.post(
    "/demo-data",
    dependencies=[Depends(require_resource_permission("system", "manage"))],
    response_model=dict
)
def initialize_demo_data(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Initialize demo data for end-to-end testing.

    Creates:
    - Partners, BU Heads, Business Units
    - Clients, Projects, Jobs with bill rates
    - FY Goals (revenue, headcount)

    Idempotent: Safe to run multiple times.
    Requires: system.manage permission (admin only)
    """
    try:
        from app.core.seed_demo_data import seed_demo_data

        logger.info(f"[AdminSetup] Seeding demo data (initiated by {current_user.UserEmail})")
        result = seed_demo_data(db)

        if result.get("status") == "success":
            logger.info(f"[AdminSetup] Demo data created: {result.get('created')}")
            return {
                "status": "success",
                "message": "Demo data initialized successfully",
                "created": result.get("created", {})
            }
        else:
            logger.error(f"[AdminSetup] Seed failed: {result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to seed data: {result.get('message')}"
            )
    except Exception as e:
        logger.error(f"[AdminSetup] Error seeding demo data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize demo data: {str(e)}"
        )


@router.get(
    "/status",
    dependencies=[Depends(require_resource_permission("system", "manage"))],
    response_model=dict
)
def setup_status(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Check system setup status.

    Returns:
    - Admin users count
    - Partners count
    - Business Units count
    - Clients count
    - Jobs with bill rates count
    - Goals configured
    """
    try:
        from app.models.user import Users as UserModel
        from app.models.org_chart import OrgChart
        from app.models.business_unit import BusinessUnit
        from app.models.client import Client
        from app.models.job import Job
        from app.models.goal_target import GoalTarget

        tenant_id = current_user.tenant_id

        admin_count = db.query(UserModel).filter(
            UserModel.tenant_id == tenant_id,
            UserModel.is_superuser == True
        ).count()

        partner_count = db.query(OrgChart).filter(
            OrgChart.node_type == "Partner/C-Level",
            OrgChart.tenant_id == tenant_id
        ).count()

        bu_count = db.query(BusinessUnit).filter(
            BusinessUnit.tenant_id == tenant_id
        ).count()

        client_count = db.query(Client).filter(
            Client.tenant_id == tenant_id
        ).count()

        job_count = db.query(Job).filter(
            Job.tenant_id == tenant_id,
            Job.bill_rate.isnot(None)
        ).count()

        goal_count = db.query(GoalTarget).filter(
            GoalTarget.tenant_id == tenant_id
        ).count()

        return {
            "status": "ready" if (admin_count > 0 and bu_count > 0) else "needs_setup",
            "admin_users": admin_count,
            "partners": partner_count,
            "business_units": bu_count,
            "clients": client_count,
            "jobs_with_bill_rates": job_count,
            "goals": goal_count,
            "next_steps": [
                "POST /admin/setup/demo-data" if (admin_count > 0 and bu_count == 0) else None,
                "Add users to Business Units" if (bu_count > 0 and admin_count == 0) else None,
            ]
        }
    except Exception as e:
        logger.error(f"[AdminSetup] Error checking status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check setup status: {str(e)}"
        )
