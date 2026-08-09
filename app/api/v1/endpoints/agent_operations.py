"""Agent operations endpoints for KPI, HR, and Employee Mental Health agents."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.kpi_agent_service import KPIAgent
# from app.services.hr_agent_service import HRAgent
# from app.services.employee_mental_health_agent_service import EmployeeMentalHealthAgent

router = APIRouter(prefix="/agents", tags=["Agent Operations"])


# ============================================================================
# KPI Agent Endpoints
# ============================================================================

@router.get("/kpi/daily-kpis", dependencies=[Depends(require_permission("admin.view"))])
async def get_daily_kpis(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get daily KPI snapshot and 2030 forecasting.

    Requires: admin.view (CEO, Super User, Finance)
    """
    try:
        kpis = await KPIAgent.calculate_daily_kpis(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return {"status": "success", "data": kpis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/dashboard", dependencies=[Depends(require_permission("admin.view"))])
async def get_kpi_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get formatted KPI dashboard for executive viewing."""
    try:
        dashboard = await KPIAgent.get_kpi_dashboard(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return dashboard
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HR Agent Endpoints
# ============================================================================

@router.get("/hr/employee-overview", dependencies=[Depends(require_permission("hr.view"))])
async def get_employee_overview(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get high-level employee population overview."""
    try:
        overview = await HRAgent.get_employee_overview(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return overview
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr/attrition-risk", dependencies=[Depends(require_permission("hr.view"))])
async def detect_attrition_risk(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Detect employees at risk of attrition."""
    try:
        at_risk = await HRAgent.detect_attrition_risk(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return at_risk
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr/onboarding-status", dependencies=[Depends(require_permission("hr.view"))])
async def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get detailed onboarding pipeline status."""
    try:
        status = await HRAgent.get_onboarding_status(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hr/schedule-reviews", dependencies=[Depends(require_permission("hr.manage"))])
async def schedule_reviews(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Schedule performance reviews based on tenure."""
    try:
        reviews = await HRAgent.schedule_reviews(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return reviews
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Employee Mental Health Agent Endpoints
# ============================================================================

@router.get("/wellness/scan-all", dependencies=[Depends(require_permission("hr.view"))])
async def scan_all_wellness(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Scan all employees for mental health and wellbeing indicators."""
    try:
        scan = await EmployeeMentalHealthAgent.scan_all_employees(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return scan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wellness/assess/{employee_id}", dependencies=[Depends(require_permission("hr.view"))])
async def assess_employee_wellness(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Assess individual employee's wellness and burnout risk."""
    try:
        assessment = await EmployeeMentalHealthAgent.assess_employee_wellness(
            tenant_id=current_user.tenant_id,
            employee_id=employee_id,
            db=db
        )
        return assessment
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wellness/checkin/{employee_id}", dependencies=[Depends(require_permission("hr.manage"))])
async def send_wellness_checkin(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Send wellness check-in survey to employee."""
    try:
        checkin = await EmployeeMentalHealthAgent.send_wellness_checkin(
            tenant_id=current_user.tenant_id,
            employee_id=employee_id,
            db=db
        )
        return {"status": "success", "data": checkin}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
