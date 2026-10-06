"""Training, Certification, and Partner-specific dashboards."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.visibility import business_unit_choices, resolve_dashboard_bu
from app.models.user import Users
from app.services.training_certification_service import (
    get_buddy_program_overview,
    get_certification_summary,
    get_employee_training_status,
    get_training_pipeline_status,
    get_next_training_steps,
    get_open_positions,
    get_core_certified_employees,
)

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

# ============================================================================
# Training & Certification Dashboard
# ============================================================================

@router.get(
    "/training-certification",
    dependencies=[Depends(require_resource_permission("certifications", "view"))]
)
def get_training_certification_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get unified training and certification dashboard."""
    try:
        business_unit_id = getattr(current_user, 'business_unit_id', None)

        buddy_overview = get_buddy_program_overview(db, business_unit_id)
        cert_summary = get_certification_summary(db, business_unit_id)
        employee_status = get_employee_training_status(db, None, business_unit_id)
        pipeline_status = get_training_pipeline_status(db, business_unit_id)
        next_steps = get_next_training_steps(db, business_unit_id=business_unit_id)

        return {
            "status": "success",
            "data": {
                "buddy_program": buddy_overview,
                "certifications": cert_summary,
                "employees": employee_status[:20],  # Top 20
                "pipeline": pipeline_status,
                "recommended_actions": next_steps,
            }
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/training-certification/employee/{employee_id}",
    dependencies=[Depends(require_resource_permission("certifications", "view"))]
)
def get_employee_training_details(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get detailed training status for specific employee."""
    try:
        status_list = get_employee_training_status(db, employee_id)
        if not status_list:
            raise HTTPException(status_code=404, detail="Employee not found")

        next_steps = get_next_training_steps(db, employee_id)

        return {
            "status": "success",
            "data": {
                "employee": status_list[0],
                "recommended_next_steps": next_steps,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Troy's Partner Dashboard (Current Demand, Pipeline, Certifications, Buddy, Core Certified)
# ============================================================================

@router.get(
    "/troy-partner",
    dependencies=[Depends(require_resource_permission("partner-dashboard", "view"))]
)
def get_troy_partner_dashboard(
    business_unit_id: Optional[int] = Query(default=None, description="Org-level users / users without a BU choose one"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Partner dashboard for one business unit: open positions, pre-onboarding,
    certifications, buddy program and core-certified employees. All real
    counts scoped to the BU's employees/jobs.
    """
    bu_id = resolve_dashboard_bu(current_user, business_unit_id)
    if bu_id is None:
        return {"status": "needs_business_unit", "data": None, "business_units": business_unit_choices(db)}

    return {
        "status": "success",
        "business_unit_id": bu_id,
        "data": {
            "current_demand": {"open_positions": get_open_positions(db, bu_id)},
            "pre_onboarding_pipeline": get_training_pipeline_status(db, bu_id),
            "certifications": get_certification_summary(db, bu_id),
            "buddy_program": get_buddy_program_overview(db, bu_id),
            "core_certified_employees": get_core_certified_employees(db, bu_id),
        },
    }
