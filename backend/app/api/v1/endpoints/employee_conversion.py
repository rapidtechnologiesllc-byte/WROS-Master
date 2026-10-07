from app.core.logging import logger
"""S-313 Employee Conversion REST Endpoints"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.schemas.employee_conversion import (
    EmployeeConversionRequest, EmployeeConversionResponse,
    EmployeeAccountRequest, EmployeeAccountResponse,
    WelcomeEmailRequest, WelcomeEmailResponse
)
import logging
from app.services.employee_conversion_service import EmployeeConversionService, InvalidCandidateState

router = APIRouter(prefix="/employees", tags=["employees"])

@router.post(
    "/convert-candidate",
    response_model=EmployeeConversionResponse,
    dependencies=[Depends(require_resource_permission("convert-to-employee", "create"))]
)
def convert_candidate(request: EmployeeConversionRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")
    
    try:
        user, employee = EmployeeConversionService.convert_candidate_to_employee(
            db=db,
            candidate=candidate,
            joining_date=request.joining_date,
            business_unit_id=request.business_unit_id,
            role_ids=request.role_ids,
            employee_email=request.employee_email,
            first_name=request.first_name,
            last_name=request.last_name,
            employment_type=request.employment_type,
            job_title=request.job_title,
            changed_by=current_user.UserID if current_user else None
        )
        db.commit()
        return EmployeeConversionResponse(
            status="success",
            employee_id=employee.id,
            employee_email=user.UserEmail,
            user_id=user.UserID,
            roles_assigned=len(request.role_ids or [])
        )
    except InvalidCandidateState as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

