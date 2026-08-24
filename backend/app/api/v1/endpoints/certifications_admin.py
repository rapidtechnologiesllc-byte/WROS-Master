"""
Admin endpoints for certification and KPI management.
Prefix: /admin/certifications
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
from app.models.certification import Certification, EmployeeCertification
from app.models.kpi import EmployeeKPITarget, EmployeeKPIScore
from app.models.employee import Employee
from app.core.logging import logger

router = APIRouter(prefix="/admin/certifications", tags=["admin-certifications"])


class CertificationRequest(BaseModel):
    cert_name: str
    cert_code: str
    description: Optional[str] = None
    level: str = "Foundation"
    validity_months: int = 24
    is_core_certification: bool = False


class CertificationResponse(BaseModel):
    id: str
    cert_name: str
    cert_code: str
    level: str
    is_core_certification: bool

    class Config:
        from_attributes = True


class KPITargetRequest(BaseModel):
    employee_id: str
    certification_id: str
    target_date: datetime
    weight: float = 0.1


class KPITargetResponse(BaseModel):
    id: str
    employee_id: str
    certification_id: str
    target_date: datetime
    status: str
    is_achieved: bool

    class Config:
        from_attributes = True


@router.post(
    "/create",
    response_model=CertificationResponse,
    dependencies=[Depends(require_resource_permission("system", "edit"))],
)
def create_certification(
    request: CertificationRequest,
    db: Session = Depends(get_db),
):
    """Create a new certification template."""
    # Check if cert_code already exists
    existing = db.query(Certification).filter(
        Certification.cert_code == request.cert_code
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail=f"Certification code {request.cert_code} already exists")

    cert = Certification(
        cert_name=request.cert_name,
        cert_code=request.cert_code,
        description=request.description,
        level=request.level,
        validity_months=request.validity_months,
        is_core_certification=request.is_core_certification,
        tenant_id=1,  # Default tenant
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)

    logger.info(f"[CERT] Created certification: {cert.cert_code}")
    return cert


@router.get(
    "/list",
    response_model=List[CertificationResponse],
    dependencies=[Depends(require_resource_permission("system", "edit"))],
)
def list_certifications(db: Session = Depends(get_db)):
    """List all certification templates."""
    certs = db.query(Certification).order_by(Certification.cert_name).all()
    return certs


@router.post(
    "/assign-target",
    response_model=KPITargetResponse,
    dependencies=[Depends(require_resource_permission("system", "edit"))],
)
def assign_kpi_target(
    request: KPITargetRequest,
    db: Session = Depends(get_db),
):
    """Assign a certification target to an employee."""
    # Verify employee exists
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {request.employee_id} not found")

    # Verify certification exists
    cert = db.query(Certification).filter(Certification.id == request.certification_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail=f"Certification {request.certification_id} not found")

    # Check if target already exists
    existing = db.query(EmployeeKPITarget).filter(
        EmployeeKPITarget.employee_id == request.employee_id,
        EmployeeKPITarget.certification_id == request.certification_id,
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Target already exists for this employee-certification pair")

    target = EmployeeKPITarget(
        employee_id=request.employee_id,
        certification_id=request.certification_id,
        target_date=request.target_date,
        weight=request.weight,
        status="PENDING",
        tenant_id=1,
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    logger.info(f"[KPI] Assigned target: emp={request.employee_id} cert={request.certification_id}")
    return target


@router.post(
    "/mark-achieved/{target_id}",
    dependencies=[Depends(require_resource_permission("system", "edit"))],
)
def mark_target_achieved(
    target_id: str,
    db: Session = Depends(get_db),
):
    """Mark a KPI target as achieved."""
    target = db.query(EmployeeKPITarget).filter(EmployeeKPITarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.is_achieved = True
    target.achieved_date = datetime.utcnow()
    target.status = "ACHIEVED"
    db.commit()

    # Recalculate employee KPI score
    recalculate_employee_kpi_score(db, target.employee_id, target.business_unit_id)

    logger.info(f"[KPI] Marked achieved: target={target_id}")
    return {"status": "success", "target_id": target_id}


@router.get(
    "/employee/{employee_id}/targets",
    response_model=List[KPITargetResponse],
    dependencies=[Depends(require_resource_permission("employees", "view"))],
)
def get_employee_kpi_targets(
    employee_id: str,
    db: Session = Depends(get_db),
):
    """Get all KPI targets for an employee."""
    targets = db.query(EmployeeKPITarget).filter(
        EmployeeKPITarget.employee_id == employee_id
    ).order_by(EmployeeKPITarget.target_date).all()

    return targets


@router.get(
    "/employee/{employee_id}/score",
    dependencies=[Depends(require_resource_permission("employees", "view"))],
)
def get_employee_kpi_score(
    employee_id: str,
    db: Session = Depends(get_db),
):
    """Get current KPI score for an employee."""
    score = db.query(EmployeeKPIScore).filter(
        EmployeeKPIScore.employee_id == employee_id
    ).first()

    if not score:
        # Initialize score if not exists
        score = EmployeeKPIScore(
            employee_id=employee_id,
            overall_score=0.0,
            certification_score=0.0,
            tenant_id=1,
        )
        db.add(score)
        db.commit()
        db.refresh(score)

    return {
        "employee_id": employee_id,
        "overall_score": score.overall_score,
        "certification_score": score.certification_score,
        "performance_score": score.performance_score,
        "utilization_score": score.utilization_score,
        "last_calculated_at": score.last_calculated_at,
    }


def recalculate_employee_kpi_score(db: Session, employee_id: str, business_unit_id: Optional[int] = None):
    """Recalculate KPI score for an employee based on targets."""
    # Get all targets for employee
    targets = db.query(EmployeeKPITarget).filter(
        EmployeeKPITarget.employee_id == employee_id
    ).all()

    if not targets:
        return

    # Calculate certification score
    total_weight = sum(t.weight for t in targets)
    achieved_weight = sum(t.weight for t in targets if t.is_achieved)

    certification_score = (achieved_weight / total_weight * 100) if total_weight > 0 else 0.0

    # Get or create KPI score record
    score = db.query(EmployeeKPIScore).filter(
        EmployeeKPIScore.employee_id == employee_id
    ).first()

    if not score:
        score = EmployeeKPIScore(
            employee_id=employee_id,
            business_unit_id=business_unit_id,
            tenant_id=1,
        )
        db.add(score)

    score.certification_score = certification_score
    # Overall score = weighted average of components (for now just certification)
    score.overall_score = certification_score
    score.last_calculated_at = datetime.utcnow()

    db.commit()
    logger.info(f"[KPI] Recalculated score: emp={employee_id} cert_score={certification_score}")


# ==== Form Dropdown Data Endpoints ====

@router.get("/business-units")
def list_business_units_for_form(db: Session = Depends(get_db)):
    """List all business units for form dropdown"""
    from app.models.business_unit import BusinessUnit
    units = db.query(BusinessUnit).all()
    return [
        {
            "id": u.id,
            "name": u.display_name or u.name,
            "code": u.bu_code
        }
        for u in units
    ]


@router.get("/roles")
def list_roles_for_form(db: Session = Depends(get_db)):
    """List all roles for form dropdown"""
    from app.models.rbac import Role
    roles = db.query(Role).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description
        }
        for r in roles
    ]
