import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user, require_resource_permission

from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.user import Users, Jobs
from app.models.candidate_ai import ConversationEvent

router = APIRouter(prefix="/candidates", tags=["candidates-workflows"])


@router.post(
    "/{candidate_id}/convert-to-employee",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Convert candidate to employee (workflow)"
)
def convert_candidate_to_employee(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Convert a candidate to an employee record.

    Workflow operation: Orchestrates candidate → employee transition.
    Prerequisites:
    - Candidate status must be "OFFER"
    - Start date must have arrived (candidateJoiningDate <= today)

    Raises:
        HTTPException: If prerequisites not met or conversion fails
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate_status = db.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate_id
    ).first()

    if not candidate_status or candidate_status.piplineStatus != "OFFER":
        current_status = candidate_status.piplineStatus if candidate_status else "Unknown"
        raise HTTPException(status_code=400, detail=f"Candidate status is {current_status}, not OFFER")

    if not candidate.candidateJoiningDate or candidate.candidateJoiningDate > datetime.now().date():
        raise HTTPException(status_code=400, detail="Joining date has not arrived yet")

    try:
        # Create Employee record
        employee = Employee(
            id=str(uuid.uuid4()),
            tenant_id=candidate.tenant_id or "default",
            first_name=candidate.candidateFirstName,
            last_name=candidate.candidateLastName or "",
            email=candidate.candidateEmail,
            mobile=candidate.candidateMobile,
            gender=candidate.candidateGender,
            date_of_birth=candidate.candidateDateOfBirth,
            status="ACTIVE",
            employment_type=candidate.candidateEmployeeType or "Full-Time",
            designation=candidate.candidateJobTitle or "Employee",
            location=candidate.candidateCurrentLocation,
            joining_date=candidate.candidateJoiningDate,
            created_at=datetime.utcnow(),
        )
        db.add(employee)
        db.flush()

        # Update candidate status
        candidate_status.piplineStatus = "EMPLOYEE"
        candidate_status.status = "EMPLOYEE"
        candidate_status.updatedAt = datetime.utcnow()

        # Log conversion event
        db.add(ConversationEvent(
            event_type="CANDIDATE_CONVERTED_TO_EMPLOYEE",
            triggered_by="HR",
            event_data={
                "candidate_id": candidate_id,
                "employee_id": employee.id,
                "timestamp": datetime.utcnow().isoformat(),
                "triggered_by_user": user.UserID if user else "system"
            }
        ))

        db.commit()
        logger.info(f"✅ Candidate {candidate_id} converted to Employee {employee.id}")

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "employee_id": employee.id,
            "message": f"Candidate {candidate.candidateFirstName} converted to employee successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Conversion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


def _user_info(user: Users | None) -> dict | None:
    """Return compact user info dict, or None if not found."""
    if not user:
        return None
    return {
        "user_id": user.UserID,
        "name": user.UserName,
        "email": user.UserEmail,
        "role": user.UserRole,
    }


@router.get(
    "/{candidate_id}/contacts",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get assigned managers and job contact person (read-only)"
)
def get_candidate_contacts(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Returns full contact details for everyone connected to a candidate.

    **From CandidateAssignment:**
    - assigned_hiring_manager
    - assigned_reporting_manager

    **From candidate's linked Job:**
    - job_contact_person
    - job_hiring_manager
    - job_recruiter

    All fields are null when records do not exist.
    """
    from app.models.candidate import CandidateAssignment

    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # Direct assignment from CandidateAssignment
    assignment = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.candidate_id == candidate_id)
        .first()
    )

    assigned_hiring_manager = None
    assigned_reporting_manager = None

    if assignment:
        if assignment.hiring_manager_id:
            hm = db.query(Users).filter(Users.UserID == assignment.hiring_manager_id).first()
            assigned_hiring_manager = _user_info(hm)
        if assignment.reporting_manager_id:
            rm = db.query(Users).filter(Users.UserID == assignment.reporting_manager_id).first()
            assigned_reporting_manager = _user_info(rm)

    # Job-based contacts
    job_info = None
    job_contact_person = None
    job_hiring_manager = None
    job_recruiter = None

    if candidate.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job:
            job_info = {
                "job_id": job.jobID,
                "job_title": job.jobTitle,
                "job_status": job.jobStatus,
            }
            if job.contactPerson:
                cp = db.query(Users).filter(Users.UserID == job.contactPerson).first()
                job_contact_person = _user_info(cp)
            if job.hiringManagerID:
                hm = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
                job_hiring_manager = _user_info(hm)
            if job.recuriterID:
                rec = db.query(Users).filter(Users.UserID == job.recuriterID).first()
                job_recruiter = _user_info(rec)

    return {
        "candidate_id": candidate_id,
        "candidate_name": " ".join(
            p for p in [
                candidate.candidateFirstName,
                candidate.candidateMiddleName,
                candidate.candidateLastName,
            ] if p
        ).strip() or None,
        "candidate_email": candidate.candidateEmail,
        "job": job_info,
        "assigned_hiring_manager": assigned_hiring_manager,
        "assigned_reporting_manager": assigned_reporting_manager,
        "job_contact_person": job_contact_person,
        "job_hiring_manager": job_hiring_manager,
        "job_recruiter": job_recruiter,
    }
