"""S-313 Employee Conversion REST Endpoints

POST /employees/convert-candidate                 candidate -> employee + system user; the employee is
                                                  emailed a single-use link to set their own password
POST /employees/{employee_id}/resend-activation   re-send that link (e.g. it expired)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.employee_conversion import EmployeeConversionRequest, EmployeeConversionResponse
from app.services.account_activation_service import queue_account_email
from app.services.employee_conversion_service import EmployeeConversionService, InvalidCandidateState

logger = logging.getLogger(__name__)

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
    # CEO hiring order: an employee only after interviews, accepted offer, onboarding and BGV
    from app.services.hiring_pipeline_service import PipelineGateBlocked, assert_cleared_for_employment

    try:
        assert_cleared_for_employment(db, request.candidate_id)
    except PipelineGateBlocked as blocked:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "message": "Candidate has not cleared hiring yet.", "stage": blocked.stage, "blockers": blocked.blockers})

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
            company_id=request.company_id,
            org_role=request.org_role,
            parent_node_id=request.parent_node_id,
            require_seat=True,
            changed_by=current_user.UserID if current_user else None
        )
        allocation = employee.conversion_allocation
        db.commit()
    except InvalidCandidateState as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Conversion] {request.candidate_id} failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

    # the employee's login: a set-password link by email (queued; retried until delivered)
    queue_account_email(user, "ACTIVATE")
    from app.services.hiring_pipeline_service import notify

    notify(candidate.candidateID, "converted", employee.id)
    return EmployeeConversionResponse(
        status="success",
        employee_id=employee.id,
        employee_email=user.UserEmail,
        user_id=user.UserID,
        roles_assigned=len(request.role_ids or []),
        business_unit_id=employee.bu_id,
        company_id=employee.company_id,
        allocation_id=allocation.id if allocation else None,
        client_id=allocation.client_id if allocation else None,
    )


@router.post(
    "/{employee_id}/resend-activation",
    dependencies=[Depends(require_resource_permission("employees", "edit"))]
)
def resend_activation(employee_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == employee_id,
                                         Employee.tenant_id == current_user.tenant_id).first()
    if employee is None or not employee.wros_user_id:
        raise HTTPException(status_code=404, detail="Employee or their user account not found.")
    user = db.query(Users).filter(Users.UserID == employee.wros_user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Employee's user account not found.")
    queue_account_email(user, "ACTIVATE" if user.password_reset_required else "RESET")
    return {"status": "queued", "email": user.UserEmail}
