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
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(
        Candidate.CandidateID == request.candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")
    
    # Verify user can create employees in target BU
    if current_user.business_unit_id != request.business_unit_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot create employees outside your Business Unit"
        )
    
    # Check if email already exists
    existing = db.query(Users).filter(Users.UserEmail == request.employee_email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Email {request.employee_email} already in use")
    
    # Create employee user
    employee_password = generate_password()
    new_employee = Users(
        UserID=user_id_generator(),
        UserName=request.employee_name,
        UserEmail=request.employee_email,
        UserPassword=get_password_hash(employee_password),
        business_unit_id=request.business_unit_id,
        UserRole="Employee",  # Legacy field
    )
    db.add(new_employee)
    db.flush()
    
    # Assign roles
    roles_assigned = 0
    for role_id in request.role_ids:
        # Verify role exists
        user_role = UserRole(
            id=f"ur_{new_employee.UserID}_{role_id}",
            user_id=new_employee.UserID,
            role_id=role_id,
            business_unit_id=request.business_unit_id
        )
        db.add(user_role)
        roles_assigned += 1
    
    # Update candidate status
    candidate.status = "CONVERTED_TO_EMPLOYEE"
    candidate.candidate_employee_user_id = new_employee.UserID
    if request.joining_date:
        candidate.candidate_joining_date = request.joining_date
    
    db.commit()
    db.refresh(new_employee)
    
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
