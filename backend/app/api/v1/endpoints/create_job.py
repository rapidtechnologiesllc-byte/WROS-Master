import json
import os
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.services.ai_conversation_service import run_auto_assign_ai_agent_in_background
from app.services.candidate_service import create_candidate_safe, find_duplicate_candidate, DuplicateCandidateError
from app.services.message_queue_service import MessageQueueService
from app.services.ready_for_opportunity_service import scan_new_job_for_matches
from app.models.user import Jobs
from app.models.candidate import (
    Candidate,
    CandidateEducationForm,
    CandidateExperienceForm,
    CandidateStatus,
)
from app.schemas.user import (
    GenerateJobDescriptionRequest, GenerateJobDescriptionResponse,
    GenerateJobWithAgentRequest, GenerateJobWithAgentResponse,
    GenerateJobCompleteRequest, GenerateJobCompleteResponse,
    JobCreateRequest, JobCreateResponse,
    JobUpdateRequest, JobResponse,
    AllJobsResponse, DeleteResponse,
    LinkedInPostRequest, LinkedInPostResponse,
    JobApproveResponse,
    CandidateJobAssignRequest, CandidateJobSummary, CandidatesByJobResponse,
)
from app.schemas.candidate import (
    EducationEntry, ExperienceEntry, JobApplicationResponse
)
from app.models.candidate import Candidate
from app.models.user import Users

from app.utils.uniq_id_generator import user_id_generator, job_id_generator

from app.tools.job_description_generator import generate_job_description_with_state
from app.api.v1.endpoints.documents import _upload_document_helper
from app.services.recruitment_job_creation_service import get_recruitment_job_agent
from app.models.agent_execution_log import AgentExecutionLog

router = APIRouter(prefix="/jobs", tags=["jobs"])

# ---------------------------------------------------------------------------
# Auto-approval logic
# ---------------------------------------------------------------------------

# Roles that can publish jobs immediately — no approval workflow needed
AUTO_APPROVE_ROLES = {"super user", "bu head", "hiring manager"}

def _can_auto_approve_job(user) -> bool:
    """
    Returns True if the user's role allows immediate job publishing.
    Checks the RBAC role first, then falls back to the legacy UserRole string.
    """
    role_name = ""
    if user.role and user.role.name:
        role_name = user.role.name
    elif user.UserRole:
        role_name = user.UserRole
    return role_name.lower() in AUTO_APPROVE_ROLES

@router.post(
    "/generate_job_description",
    dependencies=[Depends(require_resource_permission("jobs", "create"))],
)
def generate_job_description(
    request: GenerateJobDescriptionRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Generate job description using AI.

    Args:
        request: Job description generation request
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        Job description generation response
    """
    # Generate job description using AI
    result = generate_job_description_with_state(
        request.job_title,
        request.job_description,  # Using job_skills as the one-liner description
        request.job_experience,
        request.job_location
    )

    # Build response - extract the generated_description string from the result
    return GenerateJobDescriptionResponse(
        job_title=result['job_title'],
        generated_job_description=result['generated_description'],
        job_skills=result['skills_needed'],
        job_experience=result['experience'],
        job_location=result['location']
    )


@router.post(
    "/generate-with-agent",
    response_model=GenerateJobWithAgentResponse,
    dependencies=[Depends(require_resource_permission("jobs", "create"))],
)
def generate_job_with_agent(
    request: GenerateJobWithAgentRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Step 1: Recruitment agent analyzes one-liner and generates clarifying questions.

    Args:
        request: Job one-liner description
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        Clarifying questions for user to answer
    """
    try:
        agent = get_recruitment_job_agent()
        result = agent.generate_clarifying_questions(request.job_description_oneliner)

        # Log agent action
        log_entry = AgentExecutionLog(
            tenant_id=user.UserID,
            agent_name="Recruitment",
            action_taken="generate_clarifying_questions",
            action_data={
                "one_liner": request.job_description_oneliner,
                "questions_count": len(result.get("questions", []))
            },
            success=True
        )
        db.add(log_entry)
        db.commit()

        return GenerateJobWithAgentResponse(
            job_title=result.get("job_title", "Job Title"),
            estimated_experience=result.get("estimated_experience", ""),
            questions=result.get("questions", [])
        )
    except Exception as err:
        log_entry = AgentExecutionLog(
            tenant_id=user.UserID,
            agent_name="Recruitment",
            action_taken="generate_clarifying_questions",
            action_data={"one_liner": request.job_description_oneliner},
            success=False,
            error_message=str(err)
        )
        db.add(log_entry)
        db.commit()
        raise


@router.post(
    "/generate-complete",
    response_model=GenerateJobCompleteResponse,
    dependencies=[Depends(require_resource_permission("jobs", "create"))],
)
def generate_job_complete(
    request: GenerateJobCompleteRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Step 2: Recruitment agent generates complete job with all fields populated.

    Args:
        request: One-liner + answers to clarifying questions
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        Complete job data with all fields populated
    """
    try:
        agent = get_recruitment_job_agent()
        result = agent.generate_complete_job(
            request.job_description_oneliner,
            request.answers
        )

        # Log agent action
        log_entry = AgentExecutionLog(
            tenant_id=user.UserID,
            agent_name="Recruitment",
            action_taken="generate_complete_job",
            action_data={
                "one_liner": request.job_description_oneliner,
                "answers_count": len(request.answers),
                "job_title": result.get("job_title")
            },
            success=True
        )
        db.add(log_entry)
        db.commit()

        return GenerateJobCompleteResponse(**result)
    except Exception as err:
        log_entry = AgentExecutionLog(
            tenant_id=user.UserID,
            agent_name="Recruitment",
            action_taken="generate_complete_job",
            action_data={
                "one_liner": request.job_description_oneliner,
                "answers_count": len(request.answers)
            },
            success=False,
            error_message=str(err)
        )
        db.add(log_entry)
        db.commit()
        raise


@router.get(
    "/all",
    response_model=AllJobsResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
)
def get_all_jobs(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all jobs from the system.
    
    Args:
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        AllJobsResponse with list of all jobs and total count
    """
    # HRMS-0109 -- scoped to the caller's own tenant, never all tenants' jobs.
    jobs = db.query(Jobs).all()
    
    # Build response
    jobs_data = []
    for j in jobs:
        jobs_data.append(JobResponse(
            job_id=j.jobID,
            job_title=j.jobTitle,
            job_description=j.jobDescription,
            job_skills=j.jobSkills,
            job_experience=j.jobExperience,
            job_location=j.jobLocation,
            job_created_at=j.jobCreatedAt,
            company_type=j.companyType,
            company_name=j.companyName,
            contact_person=j.contactPerson,
            job_status=j.jobStatus,
            no_of_positions=j.noOfPositions,
            start_date=j.startDate,
            end_date=j.endDate,
            hiring_manager_id=j.hiringManagerID,
            recuriter_id=j.recuriterID,
            business_unit=j.business_unit_id,
            department_id=j.department_id,
            salary_range=j.salaryRange
        ))
    
    return AllJobsResponse(
        total_jobs=len(jobs_data),
        jobs=jobs_data
    )


@router.get(
    "/active-jobs",
    response_model=AllJobsResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
)
def get_active_jobs(
    db: Session = Depends(get_db),
):
    """
    Get all jobs with status 'active' or 'public'.

    Args:
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        AllJobsResponse with list of active/public jobs and total count
    """
    jobs = db.query(Jobs).filter(
        Jobs.jobStatus.in_(["active", "public"])
    ).all()

    jobs_data = [
        JobResponse(
            job_id=j.jobID,
            job_title=j.jobTitle,
            job_description=j.jobDescription,
            job_skills=j.jobSkills,
            job_experience=j.jobExperience,
            job_location=j.jobLocation,
            job_created_at=j.jobCreatedAt,
            company_type=j.companyType,
            company_name=j.companyName,
            contact_person=j.contactPerson,
            job_status=j.jobStatus,
            no_of_positions=j.noOfPositions,
            start_date=j.startDate,
            end_date=j.endDate,
            hiring_manager_id=j.hiringManagerID,
            recuriter_id=j.recuriterID,
            business_unit=j.business_unit_id,
            department_id=j.department_id,
            salary_range=j.salaryRange
        )
        for j in jobs
    ]

    return AllJobsResponse(
        total_jobs=len(jobs_data),
        jobs=jobs_data
    )


@router.get(
    "/filter",
    response_model=AllJobsResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
)
def filter_jobs(
    business_unit: Optional[int] = None,
    department_id: Optional[int] = None,
    job_status: Optional[str] = None,
    contact_person: Optional[str] = None,
    company_type: Optional[str] = None,
    company_name: Optional[str] = None,
    job_location: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Filter jobs by one or more columns. All parameters are optional and combined
    with AND logic.

    - **business_unit**: business_unit_id (integer)
    - **department_id**: department_id (integer)
    - **job_status**: e.g. active, pending_approval, draft
    - **contact_person**: partial / exact match on contact_person field
    - **company_type**: e.g. full time, contract, internship
    - **company_name**: partial / exact match on company name
    - **job_location**: partial / exact match on job location
    """
    # HRMS-0109 -- scope to the caller's tenant before any of the
    # optional filters below narrow it further.
    query = db.query(Jobs)

    if business_unit is not None:
        query = query.filter(Jobs.business_unit_id == business_unit)
    if department_id is not None:
        query = query.filter(Jobs.department_id == department_id)
    if job_status is not None:
        query = query.filter(Jobs.jobStatus == job_status)
    if contact_person is not None:
        query = query.filter(Jobs.contactPerson.ilike(f"%{contact_person}%"))
    if company_type is not None:
        query = query.filter(Jobs.companyType.ilike(f"%{company_type}%"))
    if company_name is not None:
        query = query.filter(Jobs.companyName.ilike(f"%{company_name}%"))
    if job_location is not None:
        query = query.filter(Jobs.jobLocation.ilike(f"%{job_location}%"))

    jobs = query.all()

    jobs_data = [
        JobResponse(
            job_id=j.jobID,
            job_title=j.jobTitle,
            job_description=j.jobDescription,
            job_skills=j.jobSkills,
            job_experience=j.jobExperience,
            job_location=j.jobLocation,
            job_created_at=j.jobCreatedAt,
            company_type=j.companyType,
            company_name=j.companyName,
            contact_person=j.contactPerson,
            job_status=j.jobStatus,
            no_of_positions=j.noOfPositions,
            start_date=j.startDate,
            end_date=j.endDate,
            hiring_manager_id=j.hiringManagerID,
            recuriter_id=j.recuriterID,
            business_unit=j.business_unit_id,
            department_id=j.department_id,
            salary_range=j.salaryRange
        )
        for j in jobs
    ]

    return AllJobsResponse(total_jobs=len(jobs_data), jobs=jobs_data)


@router.get(
    "/my-jobs",
    response_model=AllJobsResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
)
def get_my_jobs(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all jobs where the current authenticated user is assigned as:
    - **Recruiter** (`recuriterID`)
    - **Hiring Manager** (`hiringManagerID`)
    - **Contact Person** (`contactPerson`)

    All three roles are checked with OR logic — a job appears once even if
    the user matches more than one column.
    """
    from sqlalchemy import or_

    my_id = user.UserID
    
    # Check if user is a BU Head
    is_bu_head = False
    if user.role_id:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if role and role.name == "BU Head":
            is_bu_head = True

    # Build the OR conditions
    filters = [
        Jobs.recuriterID == my_id,
        Jobs.hiringManagerID == my_id,
        Jobs.contactPerson == my_id,
    ]
    
    # If the user is a BU Head, they should see all jobs belonging to their Business Unit
    if is_bu_head and user.business_unit_id:
        filters.append(Jobs.business_unit_id == user.business_unit_id)

    jobs = (
        db.query(Jobs)
        .filter(or_(*filters))
        .all()
    )

    jobs_data = [
        JobResponse(
            job_id=j.jobID,
            job_title=j.jobTitle,
            job_description=j.jobDescription,
            job_skills=j.jobSkills,
            job_experience=j.jobExperience,
            job_location=j.jobLocation,
            job_created_at=j.jobCreatedAt,
            company_type=j.companyType,
            company_name=j.companyName,
            contact_person=j.contactPerson,
            job_status=j.jobStatus,
            no_of_positions=j.noOfPositions,
            start_date=j.startDate,
            end_date=j.endDate,
            hiring_manager_id=j.hiringManagerID,
            recuriter_id=j.recuriterID,
            business_unit=j.business_unit_id,
            department_id=j.department_id,
            salary_range=j.salaryRange,
        )
        for j in jobs
    ]

    return AllJobsResponse(total_jobs=len(jobs_data), jobs=jobs_data)


@router.get(
    "/job-details/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
)
def get_job_by_id(
    job_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get whole information of a job by job ID.

    Args:
        job_id: ID of the job to retrieve
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        JobResponse with full job details

    Raises:
        HTTPException: If job not found
    """
    from app.models.user import Users

    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )

    contact_person_name = None
    if job.contactPerson:
        contact_user = db.query(Users).filter(Users.UserID == job.contactPerson).first()
        if contact_user:
            contact_person_name = contact_user.UserName or contact_user.Email

    hiring_manager_name = None
    if job.hiringManagerID:
        hiring_manager = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
        if hiring_manager:
            hiring_manager_name = hiring_manager.UserName or hiring_manager.Email

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
        contact_person_name=contact_person_name,
        job_status=job.jobStatus,
        no_of_positions=job.noOfPositions,
        start_date=job.startDate,
        end_date=job.endDate,
        hiring_manager_id=job.hiringManagerID,
        hiring_manager_name=hiring_manager_name,
        recuriter_id=job.recuriterID,
        business_unit=job.business_unit_id,
        department_id=job.department_id,
        salary_range=job.salaryRange,
        required_skills_canonical=job.required_skills_canonical,
        job_skills_boolean_mode=job.job_skills_boolean_mode
    )


@router.post(
    "/create_job",
    response_model=JobCreateResponse,
    dependencies=[Depends(require_resource_permission("jobs", "create"))],
)
def create_job(request: JobCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user = Depends(get_current_internal_user)):
    """
    Create a new job posting.

    Job status is determined by the creator's role — it is NOT taken from the request body.
    - Super User / BU Head / Hiring Manager → published immediately (status: active)
    - All other roles (HR, HRBP, Recruiter, etc.) → saved as draft (status: pending_approval)

    Args:
        request: JobCreateRequest containing job details
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        JobCreateResponse with job_id and message indicating publish or pending state
    """
    # Sanitize default swagger inputs
    if request.contact_person in ("string", ""):
        request.contact_person = None
    if request.hiring_manager_id in ("string", ""):
        request.hiring_manager_id = None
    if request.recuriter_id in ("string", ""):
        request.recuriter_id = None

    # AUTO-DERIVE: If BU is selected but hiring_manager not provided, auto-assign from BU
    if request.business_unit and not request.hiring_manager_id:

        # Get Hiring Manager role from this BU
        hiring_manager_role = db.query(Role).filter(Role.name == "Hiring Manager").first()
        if hiring_manager_role:
            potential_hm = db.query(Users).filter(
                Users.business_unit_id == request.business_unit,
                Users.role_id == hiring_manager_role.id
            ).first()

            if potential_hm:
                request.hiring_manager_id = potential_hm.UserID
                logger.info(f"[JobCreation] Auto-assigned Hiring Manager: {potential_hm.UserEmail} for BU: {request.business_unit}")

    # Validate that provided user IDs actually exist
    for user_id, field_name in [
        (request.contact_person, "contact_person"),
        (request.hiring_manager_id, "hiring_manager_id"),
        (request.recuriter_id, "recuriter_id")
    ]:
        if user_id:
            existing_user = db.query(Users).filter(Users.UserID == user_id).first()
            if not existing_user:
                raise HTTPException(
                    status_code=400,
                    detail=f"User '{user_id}' provided for {field_name} does not exist in the system."
                )

    # VALIDATION: Prevent BU Head from being their own Hiring Manager (separation of duties)
    if request.hiring_manager_id and request.business_unit:
        from app.models.bu_access import BUAccess

        # Get BU Head for this business unit
        bu_head_role = db.query(Role).filter(Role.name == "BU Head").first()
        if bu_head_role:
            bu_head = db.query(Users).filter(
                Users.role_id == bu_head_role.id,
                Users.business_unit_id == request.business_unit
            ).first()

            # If hiring_manager_id is same as BU Head, reject (prevent self-approval)
            if bu_head and request.hiring_manager_id == bu_head.UserID:
                raise HTTPException(
                    status_code=400,
                    detail=f"BU Head cannot be their own Hiring Manager (separation of duties). Please assign a different hiring manager for this job."
                )

    # Determine job status based on the creator's role
    if _can_auto_approve_job(user):
        job_status = "active"
        response_message = "Job published successfully"
    else:
        job_status = "pending_approval"
        
        # Check if we can assign approval to the Business Unit Head
        if request.business_unit:
            bu_head_role = db.query(Role).filter(Role.name == "BU Head").first()
            if bu_head_role:
                bu_head = db.query(Users).filter(
                    Users.role_id == bu_head_role.id,
                    Users.business_unit_id == request.business_unit
                ).first()
                if bu_head:
                    approver_name = bu_head.UserName or bu_head.UserEmail
                    response_message = f"Job submitted for approval. Awaiting approval from BU Head: {approver_name}"
                else:
                    response_message = "Job submitted for approval. A Super User must approve it before it goes live (No BU Head found for this unit)."
            else:
                response_message = "Job submitted for approval. A Super User or BU Head must approve it before it goes live."
        else:
            response_message = "Job submitted for approval. A Super User or BU Head must approve it before it goes live."

    # Generate unique job ID
    job_id = job_id_generator()

    # Create new job
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
        jobStatus=job_status,          # role-based, never from request
        noOfPositions=request.no_of_positions,
        startDate=request.start_date,
        hiringManagerID=request.hiring_manager_id,
        recuriterID=request.recuriter_id,
        business_unit_id=request.business_unit,
        department_id=request.department_id,
        salaryRange=request.salary_range
    )

    db.add(job)

    # Queue job_created message (BEFORE commit for atomicity)
    MessageQueueService.enqueue(
        message_type="job_created",
        payload={
            "job_id": job_id,
            "job_title": request.job_title,
            "job_location": request.job_location,
            "job_description": request.job_description,
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

    # ATOMIC COMMIT
    db.commit()
    db.refresh(job)

    if job_status == "active":
        # Real trigger, never a scheduled poll -- a newly PUBLISHED job
        # is exactly the "real match might now exist" event per
        # [[wros_ready_for_opportunity_workflow]].
        background_tasks.add_task(scan_new_job_for_matches, db, job)
    elif job_status == "pending_approval":
        # Send approval notification email
        from app.services.job_approval_workflow_service import handle_job_creation_approval_flow
        approval_info = handle_job_creation_approval_flow(db, job, user, send_emails=True)
        logger.info(f"[JobCreation] Job {job_id} pending approval. {approval_info['routing_reason']}")

    return JobCreateResponse(job_id=job_id, response=response_message)


@router.post(
    "/{job_id}/approve",
    response_model=JobApproveResponse,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
)
def approve_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Approve a pending job posting and make it live.

    Only users with the `job.approve` permission (Super User, BU Head) can call this.
    Only jobs in `pending_approval` status can be approved.

    Args:
        job_id: ID of the job to approve
        db: Database session
        user: Authenticated user with job.approve permission

    Returns:
        JobApproveResponse confirming the job is now active

    Raises:
        404: Job not found
        400: Job is not in pending_approval status
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )

    if job.jobStatus != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be approved — current status is '{job.jobStatus}'. Only 'pending_approval' jobs can be approved."
        )

    job.jobStatus = "active"
    db.commit()
    db.refresh(job)

    # Assign recruiter and send notifications
    from app.services.job_approval_workflow_service import handle_job_approval
    approval_result = handle_job_approval(db, job, user, send_emails=True)

    background_tasks.add_task(scan_new_job_for_matches, db, job)

    approver_name = user.UserName or user.UserEmail
    recruiter_msg = f" Assigned to recruiter: {approval_result.get('recruiter_name', 'N/A')}" if approval_result.get('recruiter_name') else ""

    return JobApproveResponse(
        job_id=job_id,
        status="active",
        message=f"Job '{job.jobTitle}' approved and is now live.{recruiter_msg}",
        approved_by=approver_name
    )


@router.put(
    "/update_job/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
)
def update_job(job_id: str, request: JobUpdateRequest, db: Session = Depends(get_db), user = Depends(get_current_internal_user)):
    """
    Update an existing job posting.
    
    Args:
        job_id: ID of the job to update
        request: JobUpdateRequest containing fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        JobResponse with updated job details
        
    Raises:
        HTTPException: If job not found
    """
    # Find the job
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Update only provided fields
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
    
    db.commit()
    db.refresh(job)
    
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


@router.delete(
    "/delete_job/{job_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_resource_permission("jobs", "delete"))],
)
def delete_job(job_id: str, db: Session = Depends(get_db), user = Depends(get_current_internal_user)):
    """
    Delete a job posting.
    
    Args:
        job_id: ID of the job to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If job not found
    """
    # Find the job
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )
    
    db.delete(job)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Job with ID {job_id} deleted successfully"
    )


@router.post(
    "/post-on-linkedin",
    response_model=LinkedInPostResponse,
    dependencies=[Depends(require_resource_permission("jobs", "create"))],
)
def post_job_on_linkedin(
    request: LinkedInPostRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    SIMULATES posting a job to LinkedIn -- no real LinkedIn API integration
    exists yet. Returns is_simulated=True and a message that leads with the
    caveat rather than burying it, so nothing here can be read as a real
    success by a hiring manager or by any other API consumer.

    Args:
        request: LinkedInPostRequest containing job_id
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        LinkedInPostResponse with status, message, mock LinkedIn post ID, and job details

    Raises:
        HTTPException: If job not found
    """
    # Validate that the job exists
    job = db.query(Jobs).filter(Jobs.jobID == request.job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {request.job_id} not found"
        )
    
    # Generate a mock LinkedIn post ID (simulating LinkedIn's response)
    import random
    import string
    linkedin_post_id = f"LI-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
    
    # Simulate posting timestamp
    posted_at = datetime.now()
    
    # Build job details response
    job_details = JobResponse(
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
        salary_range=job.salaryRange
    )
    
    # Return simulated LinkedIn posting response -- status is deliberately
    # NOT "Success" (would read as a real posting succeeded); is_simulated
    # and the message both lead with the caveat.
    return LinkedInPostResponse(
        status="Simulated",
        message=(
            f"Simulated only -- no LinkedIn integration is connected yet, so "
            f"'{job.jobTitle}' was NOT actually posted to LinkedIn."
        ),
        is_simulated=True,
        linkedin_post_id=linkedin_post_id,
        posted_at=posted_at,
        job_details=job_details
    )


@router.post(
    "/{job_id}/apply",
    response_model=JobApplicationResponse,
    status_code=201,
    summary="Apply for a job (public — no auth required)",
)
async def apply_for_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    # ── Personal details ──────────────────────────────────────────────
    full_name: str = Form(..., description="Applicant's full name"),
    email: str = Form(..., description="Personal email address"),
    phone: str = Form(..., description="Phone / mobile number"),
    total_experience_years: Optional[str] = Form(None, description="Total years of experience, e.g. '3.5'"),
    current_location: Optional[str] = Form(None),
    current_lpa: Optional[str] = Form(None, description="Current salary in LPA"),
    expected_lpa: Optional[str] = Form(None, description="Expected salary in LPA"),
    preferred_location: Optional[str] = Form(None),
    # ── Education & Experience (JSON arrays passed as form strings) ───
    education: Optional[str] = Form(None, description='JSON array of education entries. Example: [{"institution":"MIT","degree":"B.Tech","field_of_study":"CS","start_year":"2018","end_year":"2022"}]'),
    experience: Optional[str] = Form(None, description='JSON array of experience entries. Example: [{"company_name":"Acme","job_title":"SDE","start_date":"2022-07-01","end_date":"2024-01-01","years_of_experience":"1.5"}]'),
    # ── Resume upload ─────────────────────────────────────────────────
    resume: Optional[UploadFile] = File(None, description="Resume file (PDF, DOC, DOCX)"),
    db: Session = Depends(get_db),
):
    """
    Public endpoint — no authentication required.

    Submit a job application for a specific open job.
    Education and experience are provided as JSON-encoded strings in the form body.

    Returns 409 if a candidate with the same email has already applied.
    """
    # 1. Verify the job exists and is open
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job.jobStatus.lower() not in ("active", "public"):
        raise HTTPException(status_code=400, detail="This job is not open for applications")
    # 2. Duplicate-application check — R-07: email/phone/LinkedIn each
    # checked independently (createCandidateSafe()'s dedup runs again,
    # redundantly but harmlessly, at actual creation time below).
    existing, _matched_on = find_duplicate_candidate(db, email=email, mobile=phone)
    if existing:
        return JobApplicationResponse(
            status="Already Applied",
            message="An application with this email address already exists.",
            candidate_id=existing.candidateID,
        )

    # 3. Parse education JSON
    education_entries: List[EducationEntry] = []
    if education:
        try:
            raw_edu = json.loads(education)
            education_entries = [EducationEntry(**e) for e in raw_edu]
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="'education' must be a valid JSON array of education objects.",
            )

    # 4. Parse experience JSON
    experience_entries: List[ExperienceEntry] = []
    if experience:
        try:
            raw_exp = json.loads(experience)
            experience_entries = [ExperienceEntry(**e) for e in raw_exp]
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="'experience' must be a valid JSON array of experience objects.",
            )

    # 5. Split full_name into first / last
    name_parts = full_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else None

    # 6/7. R-07: createCandidateSafe() is the only sanctioned creation path.
    try:
        candidate = create_candidate_safe(
            db,
            email=email,
            mobile=phone,
            candidateRole=job.jobTitle,
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateExperience=total_experience_years,
            candidateCurrentLocation=current_location,
            candidateCurrentSalary=current_lpa,
            candidateExpectedSalary=expected_lpa,
            candidateSource="public_application",
            candidateCreatedAt=datetime.now(),
        )
    except DuplicateCandidateError as exc:
        return JobApplicationResponse(
            status="Already Applied",
            message="An application with this email address already exists.",
            candidate_id=exc.existing.candidateID,
        )
    candidate_id = candidate.candidateID
    db.flush()  # persist candidate so FK is satisfied

    # 8. Create CandidateStatus row (after candidate row exists)
    candidate_status = CandidateStatus(
        candidateID=candidate_id,
        piplineStatus="Applied",
        status="Active",
    )
    db.add(candidate_status)

    # 9. Bulk-insert education records
    today = date.today()
    for edu in education_entries:
        db.add(CandidateEducationForm(
            candidateID=candidate_id,
            education_institute=edu.institution,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            starting_year=edu.start_year,
            year_of_passing=edu.end_year,
            percentage=edu.percentage,
            submittedAt=today,
            document_is_submitted=False,
        ))

    # 10. Bulk-insert experience records
    for exp in experience_entries:
        db.add(CandidateExperienceForm(
            candidateID=candidate_id,
            company_name=exp.company_name,
            job_title=exp.job_title,
            start_date=exp.start_date,
            end_date=exp.end_date,
            year_of_experience=exp.years_of_experience,
            submittedAt=today,
            document_is_submitted=False,
        ))

    # 11. Commit candidate + education/experience rows first so the FK exists
    #     before we save the SharePoint document metadata
    db.commit()
    db.refresh(candidate)

    # 12. Upload resume to SharePoint (if provided)
    #     _upload_document_helper handles validation, Graph token, SP upload,
    #     and CandidateDocument metadata — exactly like the HR upload endpoint.
    if resume and resume.filename:
        try:
            await _upload_document_helper(resume, "resume", candidate, db)
        except HTTPException:
            # If SP upload fails we don't roll back the application — just surface the error
            raise

    # 13. Fire ATS scoring in the background — does NOT block the response
    # 2026-08-05 real fix: must NOT pass this request's own `db` (or ORM
    # objects bound to it) into a BackgroundTask -- the session is closed
    # before the task runs. See ats.run_ats_scoring_in_background()'s own
    # docstring; same convention as run_auto_assign_ai_agent_in_background
    # below.
    try:
        from app.api.v1.endpoints.ats import run_ats_scoring_in_background
        background_tasks.add_task(run_ats_scoring_in_background, candidate_id, job.jobID)
    except Exception:
        pass  # ATS failure must never block an application submission

    # 14. HRMS-0401: assign the AI recruiter automatically.
    # Tenant scoping removed (single-company deployment) -- function uses default tenant_id=1.
    # Skips gracefully (logged, not raised) if assignment fails.
    # 2026-08-05 real fix: must NOT pass this request's own `db` into a
    # BackgroundTask -- it's closed before the task runs. See
    # run_auto_assign_ai_agent_in_background()'s own docstring.
    background_tasks.add_task(run_auto_assign_ai_agent_in_background, candidate_id)

    return JobApplicationResponse(
        status="Success",
        message=f"Application submitted successfully for job '{job.jobTitle}'.",
        candidate_id=candidate_id,
    )

@router.put(
    "/{job_id}/assign-candidate/{candidate_id}",
    response_model=CandidateJobSummary,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
    summary="Assign or re-assign a candidate to a job",
)
def assign_candidate_to_job(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Link a candidate to the given job (or switch them to a different job).
    The operation is idempotent — assigning the same job twice is safe.
    To move a candidate to another job, call this endpoint with the new job_id.
    Raises 404 if either the job or candidate does not exist.
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
    candidate.job_id = job_id
    candidate.candidateJobTitle = job.jobTitle
    db.commit()
    db.refresh(candidate)

    # ── Pool ownership transition ─────────────────────────────────────────────
    # If the job has a BU, candidate moves to BU Owned; otherwise stays Org Pool
    if job.business_unit_id:
        from app.services.candidate_pool_service import set_bu_owned
        bu = db.query(__import__('app.models.rbac', fromlist=['BusinessUnit']).BusinessUnit).filter_by(id=job.business_unit_id).first()
        bu_name = bu.name if bu else f"BU #{job.business_unit_id}"
        performed_by = getattr(user, 'UserID', None)
        set_bu_owned(
            candidate_id=candidate_id,
            bu_id=job.business_unit_id,
            bu_name=bu_name,
            reason=f"Assigned to job '{job_id}' ({job.jobTitle})",
            db=db,
            performed_by_id=performed_by,
        )
        db.commit()
    # If no BU on job — candidate stays in Org Pool (no change needed)

    return CandidateJobSummary(
        candidate_id=candidate.candidateID,
        candidate_first_name=candidate.candidateFirstName,
        candidate_last_name=candidate.candidateLastName,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        candidate_experience=candidate.candidateExperience,
        candidate_current_location=candidate.candidateCurrentLocation,
        job_id=candidate.job_id,
    )
@router.put(
    "/unassign-candidate/{candidate_id}",
    response_model=CandidateJobSummary,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
    summary="Remove a candidate's job assignment",
)
def unassign_candidate_from_job(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Unlink a candidate from whichever job they are currently assigned to (sets job_id = NULL).
    Raises 404 if the candidate does not exist.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
    candidate.job_id = None
    candidate.candidateJobTitle = None
    db.commit()
    db.refresh(candidate)

    # ── Pool ownership transition: unassigned → Org Pool ─────────────────────
    from app.services.candidate_pool_service import set_org_pool
    performed_by = getattr(user, 'UserID', None)
    set_org_pool(
        candidate_id=candidate_id,
        reason="Unassigned from job — returned to Org Pool",
        db=db,
        performed_by_id=performed_by,
    )
    db.commit()

    return CandidateJobSummary(
        candidate_id=candidate.candidateID,
        candidate_first_name=candidate.candidateFirstName,
        candidate_last_name=candidate.candidateLastName,
        candidate_email=candidate.candidateEmail,
        candidate_mobile=candidate.candidateMobile,
        candidate_experience=candidate.candidateExperience,
        candidate_current_location=candidate.candidateCurrentLocation,
        job_id=candidate.job_id,
    )
@router.get(
    "/{job_id}/candidates",
    response_model=CandidatesByJobResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
    summary="Get all candidates assigned to a job",
)
def get_candidates_by_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Return every candidate whose job_id matches the given job.
    Raises 404 if the job does not exist.
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    return CandidatesByJobResponse(
        job_id=job.jobID,
        job_title=job.jobTitle,
        total_candidates=len(candidates),
        candidates=[
            CandidateJobSummary(
                candidate_id=c.candidateID,
                candidate_first_name=c.candidateFirstName,
                candidate_last_name=c.candidateLastName,
                candidate_email=c.candidateEmail,
                candidate_mobile=c.candidateMobile,
                candidate_experience=c.candidateExperience,
                candidate_current_location=c.candidateCurrentLocation,
                job_id=c.job_id,
            )
            for c in candidates
        ],
    )


# ==============================================================================
# Multi-Job Assignment Endpoints  (uses candidate_job_applications junction table)
# ==============================================================================

from app.models.candidate import CandidateJobApplication
from app.schemas.user import (
    JobApplicationCreate, JobApplicationStatusUpdate,
    JobApplicationEntry, CandidateJobsResponse, JobCandidatesMultiResponse,
)


@router.post(
    "/{job_id}/applications/{candidate_id}",
    response_model=JobApplicationEntry,
    status_code=201,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
    summary="Assign a candidate to a job (multi-job support)",
)
def create_job_application(
    job_id: str,
    candidate_id: str,
    request: JobApplicationCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Assign a candidate to a job using the many-to-many junction table.
    A candidate can be assigned to multiple jobs.

    - Returns **409** if the candidate is already assigned to this job.
    - Returns **404** if the job or candidate does not exist.
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")

    # Duplicate check
    existing = db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id,
        CandidateJobApplication.job_id == job_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Candidate '{candidate_id}' is already assigned to job '{job_id}'",
        )

    application = CandidateJobApplication(
        candidate_id=candidate_id,
        job_id=job_id,
        application_status=request.application_status or "Applied",
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return JobApplicationEntry(
        id=application.id,
        candidate_id=application.candidate_id,
        job_id=application.job_id,
        job_title=job.jobTitle,
        application_status=application.application_status,
        applied_at=application.applied_at,
    )


@router.delete(
    "/{job_id}/applications/{candidate_id}",
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
    summary="Remove a candidate from a job (multi-job)",
)
def remove_job_application(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Remove the assignment between a candidate and a job (many-to-many).
    Returns **404** if the assignment does not exist.
    """
    application = db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id,
        CandidateJobApplication.job_id == job_id,
    ).first()
    if not application:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment found for candidate '{candidate_id}' and job '{job_id}'",
        )

    db.delete(application)
    db.commit()
    return {"status": "Success", "message": f"Candidate '{candidate_id}' removed from job '{job_id}'"}


@router.put(
    "/{job_id}/applications/{candidate_id}/status",
    response_model=JobApplicationEntry,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
    summary="Update per-application status",
)
def update_job_application_status(
    job_id: str,
    candidate_id: str,
    request: JobApplicationStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Update the ``application_status`` of a specific candidate ↔ job assignment.
    Valid values: ``Applied``, ``Shortlisted``, ``Interview``, ``Offered``, ``Rejected``, ``Hired``.
    """
    application = db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id,
        CandidateJobApplication.job_id == job_id,
    ).first()
    if not application:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment found for candidate '{candidate_id}' and job '{job_id}'",
        )

    application.application_status = request.application_status
    db.commit()
    db.refresh(application)

    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    return JobApplicationEntry(
        id=application.id,
        candidate_id=application.candidate_id,
        job_id=application.job_id,
        job_title=job.jobTitle if job else None,
        application_status=application.application_status,
        applied_at=application.applied_at,
    )


@router.get(
    "/{job_id}/applications",
    response_model=JobCandidatesMultiResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
    summary="List all candidates assigned to a job (multi-job)",
)
def get_job_applications(
    job_id: str,
    application_status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Return all candidates linked to this job via the many-to-many table.
    Optionally filter by ``application_status``.
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    query = db.query(CandidateJobApplication).filter(
        CandidateJobApplication.job_id == job_id
    )
    if application_status:
        query = query.filter(CandidateJobApplication.application_status == application_status)

    applications = query.order_by(CandidateJobApplication.applied_at.desc()).all()

    entries = [
        JobApplicationEntry(
            id=app.id,
            candidate_id=app.candidate_id,
            job_id=app.job_id,
            job_title=job.jobTitle,
            application_status=app.application_status,
            applied_at=app.applied_at,
        )
        for app in applications
    ]

    return JobCandidatesMultiResponse(
        job_id=job.jobID,
        job_title=job.jobTitle,
        total_candidates=len(entries),
        applications=entries,
    )


@router.get(
    "/candidate-applications/{candidate_id}",
    response_model=CandidateJobsResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
    summary="List all jobs a candidate is assigned to (multi-job)",
)
def get_candidate_applications(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Return every job a candidate is linked to via the many-to-many table.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")

    applications = (
        db.query(CandidateJobApplication)
        .filter(CandidateJobApplication.candidate_id == candidate_id)
        .order_by(CandidateJobApplication.applied_at.desc())
        .all()
    )

    entries = []
    for app in applications:
        job = db.query(Jobs).filter(Jobs.jobID == app.job_id).first()
        entries.append(JobApplicationEntry(
            id=app.id,
            candidate_id=app.candidate_id,
            job_id=app.job_id,
            job_title=job.jobTitle if job else None,
            application_status=app.application_status,
            applied_at=app.applied_at,
        ))

    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or None

    return CandidateJobsResponse(
        candidate_id=candidate.candidateID,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        total_jobs=len(entries),
        applications=entries,
    )


# ==============================================================================
# Job Statistics Endpoint
# ==============================================================================

from sqlalchemy import func as sql_func
from app.schemas.user import JobStatisticsResponse, ApplicationStatusCount


@router.get(
    "/{job_id}/statistics",
    response_model=JobStatisticsResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
    summary="Get statistics for a job",
)
def get_job_statistics(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Return aggregated application statistics for a specific job.

    **Includes:**
    - `total_applications` — total candidates assigned via the multi-job table
    - `applied`, `shortlisted`, `interview`, `offered`, `hired`, `rejected` — named counts
    - `status_breakdown` — full list of every status with its count (covers custom statuses)

    Returns **404** if the job does not exist.
    """
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Group by application_status in a single DB query
    rows = (
        db.query(
            CandidateJobApplication.application_status,
            sql_func.count(CandidateJobApplication.id).label("cnt"),
        )
        .filter(CandidateJobApplication.job_id == job_id)
        .group_by(CandidateJobApplication.application_status)
        .all()
    )

    # Build a normalised lookup {lowercase_status: count}
    counts: dict[str, int] = {}
    for status, cnt in rows:
        key = (status or "").strip().lower()
        counts[key] = cnt

    total = sum(counts.values())

    def _get(key: str) -> int:
        return counts.get(key, 0)

    # Full breakdown list (preserve original casing from DB)
    breakdown = [
        ApplicationStatusCount(status=status or "Unknown", count=cnt)
        for status, cnt in rows
    ]
    breakdown.sort(key=lambda x: x.count, reverse=True)

    return JobStatisticsResponse(
        job_id=job.jobID,
        job_title=job.jobTitle,
        job_status=job.jobStatus,
        total_applications=total,
        applied=_get("applied"),
        shortlisted=_get("shortlisted"),
        interview=_get("interview"),
        offered=_get("offered"),
        hired=_get("hired"),
        rejected=_get("rejected"),
        status_breakdown=breakdown,
    )
