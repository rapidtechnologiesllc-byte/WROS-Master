from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Jobs, Users
from app.services.message_queue_service import MessageQueueService
from app.services.ready_for_opportunity_service import scan_new_job_for_matches
from app.schemas.user import (
    JobCreateRequest, JobCreateResponse, JobUpdateRequest, JobResponse,
    AllJobsResponse, DeleteResponse
)
from app.utils.uniq_id_generator import job_id_generator

router = APIRouter(prefix="/jobs", tags=["jobs-crud"])

AUTO_APPROVE_ROLES = {"super user", "bu head", "hiring manager"}

def _can_auto_approve_job(user) -> bool:
    role_name = ""
    if user.role and user.role.name:
        role_name = user.role.name
    elif user.UserRole:
        role_name = user.UserRole
    return role_name.lower() in AUTO_APPROVE_ROLES

def _build_job_response(job):
    return JobResponse(
        job_id=job.jobID,
        job_title=job.jobTitle,
        job_description=job.jobDescription,
        job_skills=job.jobSkills,
        job_experience=job.jobExperience,
        job_location=job.jobLocation,
        job_created_at=job.jobCreatedAt,
        company_type=job.companyType,
        company_name=job.companyName,
        contact_person=job.contactPerson,
        job_status=job.jobStatus,
        no_of_positions=job.noOfPositions,
        start_date=job.startDate,
        end_date=job.endDate,
        hiring_manager_id=job.hiringManagerID,
        recuriter_id=job.recuriterID,
        business_unit=job.business_unit_id,
        department_id=job.department_id,
        salary_range=job.salaryRange
    )

@router.post(
    "/create",
    response_model=JobCreateResponse,
    summary="Create job (CRUD operation)",
    dependencies=[Depends(require_resource_permission("jobs", "create"))]
)
def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user)
):
    """Create new job with queue integration (THUNDER_QUEUE)."""
    if request.contact_person in ("string", ""):
        request.contact_person = None
    if request.hiring_manager_id in ("string", ""):
        request.hiring_manager_id = None
    if request.recuriter_id in ("string", ""):
        request.recuriter_id = None

    # AUTO-DERIVE: If BU selected but hiring_manager not provided, auto-assign from BU
    if request.business_unit and not request.hiring_manager_id:
        hiring_manager_role = db.query(Role).filter(Role.name == "Hiring Manager").first()
        if hiring_manager_role:
            potential_hm = db.query(Users).filter(
                Users.business_unit_id == request.business_unit,
                Users.role_id == hiring_manager_role.id
            ).first()
            if potential_hm:
                request.hiring_manager_id = potential_hm.UserID
                logger.info(f"[JobCreation] Auto-assigned HM: {potential_hm.UserEmail}")

    # Validate user IDs exist
    for user_id, field_name in [
        (request.contact_person, "contact_person"),
        (request.hiring_manager_id, "hiring_manager_id"),
        (request.recuriter_id, "recuriter_id")
    ]:
        if user_id:
            if not db.query(Users).filter(Users.UserID == user_id).first():
                raise HTTPException(status_code=400, detail=f"User '{user_id}' not found for {field_name}")

    # VALIDATION: Prevent BU Head from being own Hiring Manager
    if request.hiring_manager_id and request.business_unit:
        bu_head_role = db.query(Role).filter(Role.name == "BU Head").first()
        if bu_head_role:
            bu_head = db.query(Users).filter(
                Users.role_id == bu_head_role.id,
                Users.business_unit_id == request.business_unit
            ).first()
            if bu_head and request.hiring_manager_id == bu_head.UserID:
                raise HTTPException(
                    status_code=400,
                    detail="BU Head cannot be their own Hiring Manager (separation of duties)"
                )

    # Determine job status based on creator's role
    if _can_auto_approve_job(user):
        job_status = "active"
        response_message = "Job published successfully"
    else:
        job_status = "pending_approval"
        if request.business_unit:
            bu_head_role = db.query(Role).filter(Role.name == "BU Head").first()
            if bu_head_role:
                bu_head = db.query(Users).filter(
                    Users.role_id == bu_head_role.id,
                    Users.business_unit_id == request.business_unit
                ).first()
                if bu_head:
                    approver_name = bu_head.UserName or bu_head.UserEmail
                    response_message = f"Job submitted for approval from BU Head: {approver_name}"
        else:
            response_message = "Job submitted for approval"

    job_id = job_id_generator()

    # Build job object
    job = Jobs(
        jobID=job_id,
        jobTitle=request.job_title,
        jobDescription=request.job_description,
        jobSkills=request.job_skills,
        jobExperience=request.job_experience,
        jobLocation=request.job_location,
        jobCreatedAt=datetime.now(),
        companyType=request.company_type,
        companyName=request.company_name,
        contactPerson=request.contact_person,
        jobStatus=job_status,
        noOfPositions=request.no_of_positions,
        startDate=request.start_date,
        hiringManagerID=request.hiring_manager_id,
        recuriterID=request.recuriter_id,
        business_unit_id=request.business_unit,
        department_id=request.department_id,
        salaryRange=request.salary_range
    )

    try:
        # Verify job doesn't already exist (idempotency check)
        existing_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if existing_job:
            raise HTTPException(status_code=409, detail=f"Job {job_id} already exists")

        db.add(job)

        # Queue BEFORE commit (atomicity) - enqueue() commits the transaction
        msg_id = MessageQueueService.enqueue(
            message_type="job_created",
            payload={
                "job_id": job_id,
                "job_title": request.job_title,
                "job_location": request.job_location,
                "job_skills": request.job_skills,
                "no_of_positions": request.no_of_positions,
                "hiring_manager_id": request.hiring_manager_id,
                "business_unit_id": request.business_unit,
                "job_status": job_status,
            },
            resource_id=job_id,
            queue_type="THUNDER_QUEUE",
            created_by=user.UserID,
            db=db,
        )
        db.refresh(job)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

    if job_status == "active":
        background_tasks.add_task(scan_new_job_for_matches, db, job)
    else:
        from app.services.job_approval_workflow_service import handle_job_creation_approval_flow
        handle_job_creation_approval_flow(db, job, user, send_emails=True)

    return JobCreateResponse(job_id=job_id, response=response_message)

@router.get(
    "/all",
    response_model=AllJobsResponse,
    summary="List all jobs (CRUD operation)",
    dependencies=[Depends(require_resource_permission("jobs", "view"))]
)
def get_all_jobs(db: Session = Depends(get_db), user=Depends(get_current_internal_user)):
    """Get all jobs."""
    jobs = db.query(Jobs).all()
    jobs_data = [_build_job_response(j) for j in jobs]
    return AllJobsResponse(total_jobs=len(jobs_data), jobs=jobs_data)

@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job by ID (CRUD operation)",
    dependencies=[Depends(require_resource_permission("jobs", "view"))]
)
def get_job_by_id(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user)
):
    """Get job details by ID."""
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return _build_job_response(job)

@router.put(
    "/{job_id}",
    response_model=JobResponse,
    summary="Update job (CRUD operation)",
    dependencies=[Depends(require_resource_permission("jobs", "edit"))]
)
def update_job(
    job_id: str,
    request: JobUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user)
):
    """Update job details."""
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if request.job_title is not None:
        job.jobTitle = request.job_title
    if request.job_description is not None:
        job.jobDescription = request.job_description
    if request.job_skills is not None:
        job.jobSkills = request.job_skills
    if request.job_experience is not None:
        job.jobExperience = request.job_experience
    if request.job_location is not None:
        job.jobLocation = request.job_location
    if request.company_type is not None:
        job.companyType = request.company_type
    if request.company_name is not None:
        job.companyName = request.company_name
    if request.contact_person is not None:
        job.contactPerson = request.contact_person
    if request.job_status is not None:
        job.jobStatus = request.job_status
    if request.no_of_positions is not None:
        job.noOfPositions = request.no_of_positions
    if request.start_date is not None:
        job.startDate = request.start_date
    if request.end_date is not None:
        job.endDate = request.end_date
    if request.hiring_manager_id is not None:
        job.hiringManagerID = request.hiring_manager_id
    if request.recuriter_id is not None:
        job.recuriterID = request.recuriter_id
    if request.business_unit is not None:
        job.business_unit_id = request.business_unit
    if request.department_id is not None:
        job.department_id = request.department_id
    if request.salary_range is not None:
        job.salaryRange = request.salary_range

    try:
        # Queue BEFORE commit (atomicity) - enqueue() commits the transaction
        msg_id = MessageQueueService.enqueue(
            message_type="job_updated",
            payload={
                "job_id": job_id,
                "job_title": job.jobTitle,
                "job_location": job.jobLocation,
                "job_skills": job.jobSkills,
                "job_status": job.jobStatus,
                "hiring_manager_id": job.hiringManagerID,
                "business_unit_id": job.business_unit_id,
            },
            resource_id=job_id,
            queue_type="THUNDER_QUEUE",
            created_by=user.UserID,
            db=db,
        )
        db.refresh(job)
        return _build_job_response(job)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update job: {str(e)}")

@router.delete(
    "/{job_id}",
    response_model=DeleteResponse,
    summary="Delete job (CRUD operation)",
    dependencies=[Depends(require_resource_permission("jobs", "delete"))]
)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user)
):
    """Delete job."""
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Queue BEFORE deletion (atomicity) - enqueue() commits the transaction
    try:
        msg_id = MessageQueueService.enqueue(
            message_type="job_deleted",
            payload={
                "job_id": job_id,
                "job_title": job.jobTitle,
                "business_unit_id": job.business_unit_id,
            },
            resource_id=job_id,
            queue_type="THUNDER_QUEUE",
            created_by=user.UserID,
            db=db,
        )
    except Exception as e:
        logger.error(f"Failed to queue job deletion: {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue job deletion: {str(e)}")

    try:
        db.delete(job)
        db.commit()
        return DeleteResponse(status="Success", message=f"Job {job_id} deleted successfully")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")
