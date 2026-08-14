"""Training, Certification, and Partner-specific dashboards."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.services.training_certification_service import (
    get_buddy_program_overview,
    get_certification_summary,
    get_employee_training_status,
    get_training_pipeline_status,
    get_next_training_steps,
)

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


# ============================================================================
# Training & Certification Dashboard
# ============================================================================

@router.get("/training-certification")
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
        next_steps = get_next_training_steps(db)

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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-certification/employee/{employee_id}")
def get_employee_training_details(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get detailed training status for specific employee."""
    try:
        status_list = get_employee_training_status(db, employee_id)
        if not status_list or "error" in status_list[0]:
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
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Troy's Partner Dashboard (Current Demand, Pipeline, Certifications, Buddy, Core Certified)
# ============================================================================

@router.get("/troy-partner")
def get_troy_partner_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Troy's Partner-specific dashboard with:
    - Current Demand
    - Pre-Onboarding Pipeline
    - Certifications
    - Buddy Program
    - Core Certified employees
    """
    try:
        business_unit_id = getattr(current_user, 'business_unit_id', None)
        if not business_unit_id:
            raise HTTPException(status_code=403, detail="Partner must have a business unit assigned")

        # Current Demand - open positions in this BU
        from app.models.job import Jobs
        open_jobs = db.query(Jobs).filter(
            Jobs.jobStatus.in_(["Open", "Public"]),
            Jobs.business_unit_id == business_unit_id
        ).count()

        # Pre-Onboarding Pipeline
        pipeline = get_training_pipeline_status(db, business_unit_id)

        # Certifications - by level for this BU
        cert_summary = get_certification_summary(db, business_unit_id)

        # Buddy Program
        buddy_overview = get_buddy_program_overview(db, business_unit_id)

        # Core Certified employees
        from app.models.certification import Certification, EmployeeCertification
        from app.models.employee import Employee

        core_certified = db.query(
            Employee.employee_name,
            Certification.cert_name,
            EmployeeCertification.earned_date
        ).join(EmployeeCertification).join(Certification).filter(
            Employee.business_unit_id == business_unit_id,
            Certification.is_core_certification == True,
            EmployeeCertification.status == "Active"
        ).all()

        return {
            "status": "success",
            "data": {
                "current_demand": {
                    "open_positions": open_jobs,
                },
                "pre_onboarding_pipeline": pipeline,
                "certifications": cert_summary,
                "buddy_program": buddy_overview,
                "core_certified_employees": [
                    {
                        "name": emp[0],
                        "certification": emp[1],
                        "earned_date": emp[2].isoformat() if emp[2] else None,
                    }
                    for emp in core_certified
                ],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
