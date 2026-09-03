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
    dependencies=[Depends(require_resource_permission("convert-candidate", "create"))]
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

@router.post(
    "/create-account",
    response_model=EmployeeAccountResponse,
    dependencies=[Depends(require_resource_permission("create-account", "create"))]
)
def create_employee_account(request: EmployeeAccountRequest, db: Session = Depends(get_db)):
    try:
        user = EmployeeConversionService.create_employee_account(
            db=db,
            employee_name=request.employee_name,
            employee_email=request.employee_email,
            business_unit_id=request.business_unit_id,
            tenant_id=request.tenant_id,
            role_ids=request.role_ids,
            phone=request.phone
        )
        db.commit()
        return EmployeeAccountResponse(
            user_id=user.UserID,
            employee_email=user.UserEmail,
            employee_name=user.UserName,
            roles_assigned=len(request.role_ids or [])
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/send-welcome-email",
    response_model=WelcomeEmailResponse,
    dependencies=[Depends(require_resource_permission("send-welcome-email", "create"))]
)
def send_welcome_email(request: WelcomeEmailRequest, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {request.employee_id} not found")
    
    if not employee.wros_user_id:
        raise HTTPException(status_code=400, detail="Employee has no user account linked")
    
    from app.models.user import Users
    user = db.query(Users).filter(Users.UserID == employee.wros_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
    
    success = EmployeeConversionService.send_welcome_email(
        db=db,
        employee_user=user,
        employee_record=employee,
        temporary_password=request.temporary_password,
        include_onboarding_link=request.include_onboarding_link
    )
    
    return WelcomeEmailResponse(
        status="sent" if success else "failed",
        email_sent=success,
        employee_email=user.UserEmail
    )

@router.get(
    "/status/{employee_id}",
    dependencies=[Depends(require_resource_permission("statu", "view"))]
)
def get_employee_status(employee_id: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    
    return {
        "employee_id": employee.id,
        "status": employee.status,
        "joining_date": employee.joining_date,
        "delivery_engine": employee.delivery_engine
    }

@router.put(
    "/update/{employee_id}",
    dependencies=[Depends(require_resource_permission("update", "update"))]
)
def update_employee(employee_id: str, updates: dict, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    
    for key, value in updates.items():
        if hasattr(employee, key):
            setattr(employee, key, value)
    
    db.commit()
    return {"status": "updated", "employee_id": employee.id}

@router.delete(
    "/delete/{employee_id}",
    dependencies=[Depends(require_resource_permission("delete", "delete"))]
)
def delete_employee(employee_id: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    
    db.delete(employee)
    db.commit()
    return {"status": "deleted", "employee_id": employee_id}
