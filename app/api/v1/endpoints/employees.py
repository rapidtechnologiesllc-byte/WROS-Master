"""
Employee management endpoints including candidate-to-employee conversion with multi-role assignment.
"""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.user import Users, UserRole
from app.models.candidate import Candidate
from app.core.security import get_password_hash
from app.utils.uniq_id_generator import user_id_generator, generate_password
from pydantic import BaseModel

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeeConversionRequest(BaseModel):
    """Request to convert candidate to employee with role and BU assignment"""
    candidate_id: str
    employee_name: str
    employee_email: str
    business_unit_id: int
    role_ids: List[int]
    position: Optional[str] = None
    joining_date: Optional[date] = None


class EmployeeConversionResponse(BaseModel):
    status: str
    employee_user_id: str
    employee_email: str
    roles_assigned: int


@router.post(
    "/convert-from-candidate",
    response_model=EmployeeConversionResponse,
    dependencies=[Depends(require_permission("employee.manage"))],
)
def convert_candidate_to_employee(
    request: EmployeeConversionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Convert a candidate to an employee with multi-role and BU assignment.
    Requires permission: employee.manage

    This creates:
    1. New user account for the employee
    2. Assigns multiple roles from the request
    3. Assigns to specified business unit
    4. Updates candidate status to CONVERTED_TO_EMPLOYEE
    """
    from app.core.logging import logger

    logger.info(f"[EMPLOYEE_CONVERSION] START - candidate_id={request.candidate_id}, email={request.employee_email}, bu_id={request.business_unit_id}, role_ids={request.role_ids}")
    logger.info(f"[EMPLOYEE_CONVERSION] Current user: {current_user.UserID} ({current_user.UserEmail}), BU: {current_user.business_unit_id}")

    # Verify candidate exists
    candidate = db.query(Candidate).filter(
        Candidate.CandidateID == request.candidate_id
    ).first()
    logger.info(f"[EMPLOYEE_CONVERSION] Candidate lookup: {candidate.CandidateID if candidate else 'NOT FOUND'}")
    if not candidate:
        logger.error(f"[EMPLOYEE_CONVERSION] FAILED - Candidate {request.candidate_id} not found")
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")
    
    # Verify user can create employees in target BU
    logger.info(f"[EMPLOYEE_CONVERSION] BU validation: user_bu={current_user.business_unit_id}, target_bu={request.business_unit_id}")
    if current_user.business_unit_id != request.business_unit_id:
        logger.error(f"[EMPLOYEE_CONVERSION] FAILED - BU mismatch: user_bu={current_user.business_unit_id}, target_bu={request.business_unit_id}")
        raise HTTPException(
            status_code=403,
            detail="Cannot create employees outside your Business Unit"
        )

    # Check if email already exists
    existing = db.query(Users).filter(Users.UserEmail == request.employee_email).first()
    logger.info(f"[EMPLOYEE_CONVERSION] Email check: {request.employee_email} - {'EXISTS' if existing else 'AVAILABLE'}")
    if existing:
        logger.error(f"[EMPLOYEE_CONVERSION] FAILED - Email already in use: {request.employee_email}")
        raise HTTPException(status_code=400, detail=f"Email {request.employee_email} already in use")
    
    # Create employee user
    employee_password = generate_password()
    new_employee_id = user_id_generator()
    logger.info(f"[EMPLOYEE_CONVERSION] Creating user: id={new_employee_id}, email={request.employee_email}, name={request.employee_name}")
    new_employee = Users(
        UserID=new_employee_id,
        UserName=request.employee_name,
        UserEmail=request.employee_email,
        UserPassword=get_password_hash(employee_password),
        business_unit_id=request.business_unit_id,
        UserRole="Employee",  # Legacy field
    )
    db.add(new_employee)
    db.flush()
    logger.info(f"[EMPLOYEE_CONVERSION] User created and flushed: {new_employee.UserID}")

    # Assign roles
    roles_assigned = 0
    for role_id in request.role_ids:
        try:
            # Verify role exists
            user_role = UserRole(
                id=f"ur_{new_employee.UserID}_{role_id}",
                user_id=new_employee.UserID,
                role_id=role_id,
                business_unit_id=request.business_unit_id
            )
            db.add(user_role)
            roles_assigned += 1
            logger.info(f"[EMPLOYEE_CONVERSION] Role assigned: role_id={role_id} for user={new_employee.UserID}")
        except Exception as e:
            logger.error(f"[EMPLOYEE_CONVERSION] FAILED to assign role {role_id}: {str(e)}")
            raise

    # Update candidate status
    logger.info(f"[EMPLOYEE_CONVERSION] Updating candidate: id={candidate.CandidateID}, status=CONVERTED_TO_EMPLOYEE, linked_user={new_employee.UserID}")
    candidate.status = "CONVERTED_TO_EMPLOYEE"
    candidate.candidate_employee_user_id = new_employee.UserID
    if request.joining_date:
        candidate.candidate_joining_date = request.joining_date

    db.commit()
    db.refresh(new_employee)
    logger.info(f"[EMPLOYEE_CONVERSION] SUCCESS - Created employee {new_employee.UserID} from candidate {request.candidate_id}, roles_assigned={roles_assigned}")
    
    return EmployeeConversionResponse(
        status="success",
        employee_user_id=new_employee.UserID,
        employee_email=new_employee.UserEmail,
        roles_assigned=roles_assigned
    )


@router.get("/roles-for-conversion")
def get_available_roles_for_conversion(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    """Get available roles for employee conversion"""
    from app.models.rbac import Role
    
    roles = db.query(Role).filter(Role.is_active == True).all()
    return [{"id": r.id, "name": r.name} for r in roles]
