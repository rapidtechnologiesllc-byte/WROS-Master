import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.services.message_queue_service import MessageQueueService

from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.user import Users, Jobs
from app.models.candidate_ai import ConversationEvent

router = APIRouter(prefix="/candidates", tags=["candidates-workflows"])

@router.post(
    "/{candidate_id}/convert-to-employee",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Queue candidate-to-employee conversion"
)
def convert_candidate_to_employee(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Queue candidate-to-employee conversion through message queue.

    Uses idempotent queue pattern with automatic retries (5 attempts, 30-min intervals).

    Prerequisites validation:
    - Candidate status must be "OFFER"
    - Start date must have arrived (candidateJoiningDate <= today)

    Returns: message_id for polling conversion status
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

    # Queue the conversion through message queue (idempotent pattern)
    message_id = str(uuid.uuid4())

    try:
        MessageQueueService.enqueue(
            message_type="convert_candidate_to_employee",
            queue_type="CANDIDATE_QUEUE",
            resource_id=candidate_id,
            created_by=current_user.UserID,
            db=db,
            payload={
                "message_id": message_id,
                "candidate_id": candidate_id,
                "candidate_first_name": candidate.candidateFirstName,
                "candidate_email": candidate.candidateEmail,
                "candidate_mobile": candidate.candidateMobile,
                "candidate_gender": candidate.candidateGender,
                "candidate_dob": candidate.candidateDateOfBirth,
                "candidate_employee_type": candidate.candidateEmployeeType or "Full-Time",
                "candidate_job_title": candidate.candidateJobTitle or "Employee",
                "candidate_location": candidate.candidateCurrentLocation,
                "candidate_joining_date": candidate.candidateJoiningDate,
                "tenant_id": candidate.tenant_id or "default",
                "triggered_by_user": current_user.UserID if current_user else "system",
            }
        )

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to queue conversion: {str(e)}") from e

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion queue error: {str(e)}") from e

    return {
        "message_id": message_id,
        "status": "pending",
        "polling_endpoint": f"/candidates/{candidate_id}/convert-status/{message_id}"
    }

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
