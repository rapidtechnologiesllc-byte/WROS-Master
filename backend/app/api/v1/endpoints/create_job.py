import json
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.bu_scope import candidate_scope_filter, ensure_candidate_visible
from app.core.data_scope import bu_filter, ensure_assignable, job_filter, visible_job_or_404
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.core.rate_limiter import rate_limit
from app.services.candidate_service import find_duplicate_candidate
from app.services.message_queue_service import MessageQueueService
from app.models.user import Jobs
from app.models.candidate import (
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
)
from app.schemas.candidate import (
    EducationEntry, ExperienceEntry, JobApplicationResponse
)
from app.models.user import Users

from app.services.job_creation_service import resolve_job_client, submit_job, validate_job_project

from app.tools.job_description_generator import generate_job_description_with_state
from app.api.v1.endpoints.documents import _upload_document_helper
from app.services.recruitment_job_creation_service import get_recruitment_job_agent
from app.models.agent_execution_log import AgentExecutionLog

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _jobs_in_scope(db: Session, user):
    """Jobs the caller may see: their own tenant, and -- unless their role template is
    org-level -- only their business units' jobs plus jobs not yet assigned to a BU
    (CEO 2026-10-12, app.core.data_scope)."""
    return db.query(Jobs).filter(
        (Jobs.tenant_id == user.tenant_id) | Jobs.tenant_id.is_(None),
        bu_filter(db, user, Jobs.business_unit_id),
    )


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
        logger.error(f"Error: {str(err)}", exc_info=True)
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

def _known_skill_names(db: Session) -> list:
    """Skill names already used on jobs and candidate profiles -- the
    vocabulary the one-liner is matched against when no AI is configured."""
    from app.models.candidate_profile_extras import CandidateProfileSkill
    names = {row[0] for row in db.query(CandidateProfileSkill.name).distinct().limit(2000).all() if row[0]}
    for (job_skills,) in db.query(Jobs.jobSkills).limit(2000).all():
        names.update(part.strip() for part in (job_skills or "").split(",") if part.strip())
    return sorted(n for n in names if 1 < len(n) <= 60)


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
            request.answers,
            known_skills=_known_skill_names(db),
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
        logger.error(f"Error: {str(err)}", exc_info=True)
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
    # HRMS-0109 -- scoped to the caller's own tenant and business units, never all jobs.
    # Filter out soft-deleted jobs
    jobs = _jobs_in_scope(db, user).filter(
        (Jobs.is_deleted == False) | (Jobs.is_deleted.is_(None)),  # noqa: E712
        (Jobs.deleted_at.is_(None))
    ).all()
    
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
        client_id=j.client_id,
        project_id=j.project_id,
        billing_rate_usd_cents=j.billing_rate_usd_cents,
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
    user = Depends(get_current_internal_user),
):
    """
    Get all jobs with status 'active' or 'public'.

    Args:
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        AllJobsResponse with list of active/public jobs and total count
    """
    jobs = _jobs_in_scope(db, user).filter(
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
        client_id=j.client_id,
        project_id=j.project_id,
        billing_rate_usd_cents=j.billing_rate_usd_cents,
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
    department_id: Optional[str] = None,
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
    - **department_id**: department_id (UUID string)
    - **job_status**: e.g. active, pending_approval, draft
    - **contact_person**: partial / exact match on contact_person field
    - **company_type**: e.g. full time, contract, internship
    - **company_name**: partial / exact match on company name
    - **job_location**: partial / exact match on job location
    """
    # HRMS-0109 -- scope to the caller's tenant and business units before any of the
    # optional filters below narrow it further: picking another BU yields nothing.
    query = _jobs_in_scope(db, user)

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
        client_id=j.client_id,
        project_id=j.project_id,
        billing_rate_usd_cents=j.billing_rate_usd_cents,
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

    All three roles are checked with OR logic - a job appears once even if
    the user matches more than one column.
    """
    from sqlalchemy import or_

    my_id = user.UserID
    
    # BU leaders (role template hierarchy level) see every job in the business units they
    # partner, head (in any company) or belong to -- by business unit, never by location
    from app.core import authority
    from app.services.bu_leadership import led_business_units

    # Build the OR conditions
    filters = [
        Jobs.recuriterID == my_id,
        Jobs.hiringManagerID == my_id,
        Jobs.contactPerson == my_id,
    ]

    if authority.is_bu_leader(db, user):
        my_bu_ids = led_business_units(db, user)
        if user.business_unit_id is not None:
            my_bu_ids.add(user.business_unit_id)
        if my_bu_ids:
            filters.append(Jobs.business_unit_id.in_(my_bu_ids))

    # still only jobs the caller may see at all (a job-details link for any of them works)
    jobs = _jobs_in_scope(db, user).filter(or_(*filters)).all()

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
        client_id=j.client_id,
        project_id=j.project_id,
        billing_rate_usd_cents=j.billing_rate_usd_cents,
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

    job = visible_job_or_404(db, user, job_id, f"Job with ID {job_id}")

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
        client_id=job.client_id,
        project_id=job.project_id,
        billing_rate_usd_cents=job.billing_rate_usd_cents,
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
@rate_limit(500)  # FIX #17: 500 requests/min for job creation
def create_job(request: JobCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user = Depends(get_current_internal_user)):
    """Create (queue) a job posting through app.services.job_creation_service.submit_job, the
    one creation path shared with Flash. Every job is published immediately."""
    job_id = submit_job(db, user, request)
    return JobCreateResponse(job_id=job_id, response="Job published successfully")

@router.post(
    "/{job_id}/approve",
    response_model=JobApproveResponse,
    dependencies=[Depends(require_resource_permission("jobs", "edit"))],
)
def approve_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user),
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

    No CSRF token: WROS authenticates with a bearer header the browser never attaches
    cross-site (credentials: 'omit', no cookies), so CSRF does not apply.
    """

    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")

    if job.jobStatus != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be approved - current status is '{job.jobStatus}'. Only 'pending_approval' jobs can be approved."
        )

    job.jobStatus = "active"
    db.commit()
    db.refresh(job)

    # Queue job approval event for FLASH orchestrator
    MessageQueueService.enqueue(
        task_name='job_approved_flash',
        data={
            'job_id': job_id,
            'job_title': job.jobTitle,
            'business_unit_id': job.business_unit_id,
            'approver_id': user.UserID,
            'approved_at': datetime.now().isoformat()
        }
    )

    # Assign recruiter and send notifications
    from app.services.job_approval_workflow_service import handle_job_approval
    approval_result = handle_job_approval(db, job, user, send_emails=True)

    from app.services.recruiting_service import start_recruiting

    start_recruiting(job, "approved")  # the recruiter run nudges watchers and sources the pool

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
    # Find the job -- another business unit's job is "not found" (CEO 2026-10-12)
    job = visible_job_or_404(db, user, job_id, f"Job with ID {job_id}")

    # ...and it cannot be moved into a BU, or onto a client of a BU, outside the caller's
    # scope. Checked before any field changes.
    if request.business_unit is not None:
        ensure_assignable(db, user, request.business_unit, "job")
    new_client = None
    if request.client_id:
        new_client = resolve_job_client(db, user.tenant_id, request.client_id, None)
    elif request.client_id is None and request.company_name is not None:
        new_client = resolve_job_client(db, user.tenant_id, None, request.company_name)
    if new_client is not None:
        ensure_assignable(db, user, new_client.business_unit_id, "job")

    # Status is never edited directly: it is set at creation (approval flow
    # is currently disabled, so new jobs are active) and by POST /approve_job.
    # Echoing the current status back is allowed so full-form saves work.
    if request.job_status is not None and request.job_status != job.jobStatus:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Job status cannot be changed here (current: '{job.jobStatus}'). "
                "Job status is set by the system and cannot be edited."
            ),
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
    if request.client_id is None and request.company_name is not None:
        # Renamed without an explicit client pick: re-match the name (resolved above)
        job.client_id = new_client.id if new_client else None
    if request.client_id is not None:
        client = new_client if request.client_id else None
        job.client_id = client.id if client else None
        if client:
            job.companyName = client.company_name
            if job.business_unit_id is None:
                job.business_unit_id = client.business_unit_id
    if request.billing_rate_usd_cents is not None:
        job.billing_rate_usd_cents = request.billing_rate_usd_cents or None
    if request.project_id is not None:
        if request.project_id:
            validate_job_project(db, request.project_id, job.client)
        job.project_id = request.project_id or None
    elif job.project_id and (request.client_id is not None or request.company_name is not None):
        # the client changed but the project did not: it must still be this client's project
        from app.models.client import Client

        validate_job_project(db, job.project_id,
                             db.query(Client).filter(Client.id == job.client_id).first() if job.client_id else None)
    if request.contact_person is not None:
        job.contactPerson = request.contact_person
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

    # Queue job update event for FLASH orchestrator. No task_id: it is the
    # queue row's primary key, and job_created_flash already used job_id, so
    # reusing it made every update after creation fail with a duplicate key.
    MessageQueueService.enqueue(
        task_name='job_updated_flash',
        data={
            'job_id': job_id,
            'job_title': job.jobTitle,
            'business_unit_id': job.business_unit_id,
            'job_status': job.jobStatus,
            'updated_by': user.UserID,
            'updated_at': datetime.now().isoformat()
        }
    )

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
        client_id=job.client_id,
        project_id=job.project_id,
        billing_rate_usd_cents=job.billing_rate_usd_cents,
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
    # Find the job -- another business unit's job is "not found" (CEO 2026-10-12)
    job = visible_job_or_404(db, user, job_id, f"Job with ID {job_id}")

    from app.services.job_lifecycle_service import JobHasHistory, assert_deletable

    try:
        assert_deletable(db, job_id)
    except JobHasHistory as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.delete(job)
    db.commit()

    # Queue job deletion event for FLASH orchestrator
    MessageQueueService.enqueue(
        task_name='job_deleted_flash',
        data={
            'job_id': job_id,
            'job_title': job.jobTitle,
            'business_unit_id': job.business_unit_id,
            'deleted_by': user.UserID,
            'deleted_at': datetime.now().isoformat()
        }
    )

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
    # Validate that the job exists and is in the caller's business-unit scope
    job = visible_job_or_404(db, user, request.job_id, f"Job with ID {request.job_id}")

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
        client_id=job.client_id,
        project_id=job.project_id,
        billing_rate_usd_cents=job.billing_rate_usd_cents,
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
    summary="Apply for a job (public - no auth required)",
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
    Public endpoint - no authentication required.

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
    # 2. Duplicate-application check - R-07: email/phone/LinkedIn each
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

    # 6/7. R-07: Queue candidate creation via unified queue-driven path
    from app.services.candidate_creation_sync_wait import queue_and_wait_for_candidate

    try:
        candidate, message_id = queue_and_wait_for_candidate(
            db=db,
            email=email,
            tenant_id=job.tenant_id,
            first_name=first_name,
            last_name=last_name,
            mobile=phone,
            source="public_application",
            timeout_seconds=10,
        )
    except Exception as exc:
        logger.error(f"[JOB_APPLY] Failed to queue candidate: {exc}", exc_info=True)
        return JobApplicationResponse(
            status="Error",
            message=f"Failed to process application: {str(exc)}",
            candidate_id=None,
        )

    if not candidate:
        # Handler didn't complete in time, return error
        logger.warning(f"[JOB_APPLY] Candidate creation timed out for {email}")
        return JobApplicationResponse(
            status="Error",
            message="Application processing in progress. Please try again in a few moments.",
            candidate_id=None,
        )

    candidate_id = candidate.candidateID

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

    # Queue candidate job application event for FLASH orchestrator
    MessageQueueService.enqueue(
        task_name='candidate_job_application_created',
        data={
            'candidate_id': candidate_id,
            'candidate_email': candidate.candidateEmail,
            'candidate_name': f"{candidate.candidateFirstName} {candidate.candidateLastName}".strip(),
            'job_id': job_id,
            'job_title': job.jobTitle,
            'applied_at': datetime.now().isoformat()
        }
    )

    # 12. Upload resume to SharePoint (if provided)
    #     _upload_document_helper handles validation, Graph token, SP upload,
    #     and CandidateDocument metadata - exactly like the HR upload endpoint.
    if resume and resume.filename:
        try:
            await _upload_document_helper(resume, "resume", candidate, db)
        except HTTPException:
            # If SP upload fails we don't roll back the application - just surface the error
            raise

    # 13. Fire ATS scoring in the background - does NOT block the response
    # 2026-08-05 real fix: must NOT pass this request's own `db` (or ORM
    # objects bound to it) into a BackgroundTask -- the session is closed
    # before the task runs. See ats.run_ats_scoring_in_background()'s own
    # docstring.
    try:
        from app.api.v1.endpoints.ats import run_ats_scoring_in_background
        background_tasks.add_task(run_ats_scoring_in_background, candidate_id, job.jobID)
    except Exception as exc:
        # ATS failure must never block an application submission -- but it is logged
        logger.error(f"[JOB_APPLY] Could not schedule ATS scoring for {candidate_id}: {exc}", exc_info=True)

    return JobApplicationResponse(
        status="Success",
        message=f"Application submitted successfully for job '{job.jobTitle}'.",
        candidate_id=candidate_id,
    )


# ==============================================================================
# Multi-Job Assignment Endpoints  (uses candidate_job_applications junction table)
# ==============================================================================

from app.models.candidate import CandidateJobApplication
from app.schemas.user import (
    JobApplicationCreate, JobApplicationEntry,
    CandidateJobsResponse, JobCandidatesMultiResponse,
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
    # both records must be in the caller's business-unit scope (404 otherwise)
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    candidate = ensure_candidate_visible(db, candidate_id, user)
    # the 5-year rule applies at every step, the way into a job pipeline included (CEO)
    from app.services.submission_service import ExperienceIneligible, assert_experience_eligible

    from app.services.employment_type_policy import EmploymentTypeNotAccepted, assert_may_interview

    try:
        assert_experience_eligible(candidate, "submit the candidate to a job")
        assert_may_interview(candidate, "submit the candidate to a job")
    except (ExperienceIneligible, EmploymentTypeNotAccepted) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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

    # Queue job application event for FLASH orchestrator
    MessageQueueService.enqueue(
        task_name='job_application_created',
        data={
            'application_id': application.id,
            'candidate_id': candidate_id,
            'job_id': job_id,
            'application_status': application.application_status,
            'created_at': datetime.now().isoformat()
        }
    )

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
    Returns **404** if the assignment does not exist (or the job is another BU's).
    """
    visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    application = db.query(CandidateJobApplication).filter(
        CandidateJobApplication.candidate_id == candidate_id,
        CandidateJobApplication.job_id == job_id,
    ).first()
    if not application:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment found for candidate '{candidate_id}' and job '{job_id}'",
        )

    app_id = application.id  # Capture for queue event
    db.delete(application)
    db.commit()

    # Queue job application removal event for FLASH orchestrator
    MessageQueueService.enqueue(
        task_name='job_application_removed',
        data={
            'application_id': app_id,
            'candidate_id': candidate_id,
            'job_id': job_id,
            'removed_at': datetime.now().isoformat()
        }
    )

    return {"status": "Success", "message": f"Candidate '{candidate_id}' removed from job '{job_id}'"}


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
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")

    query = db.query(CandidateJobApplication).filter(
        CandidateJobApplication.job_id == job_id,
        candidate_scope_filter(db, user, CandidateJobApplication.candidate_id),
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
    candidate = ensure_candidate_visible(db, candidate_id, user)

    applications = (
        db.query(CandidateJobApplication)
        .filter(CandidateJobApplication.candidate_id == candidate_id,
                job_filter(db, user, CandidateJobApplication.job_id))
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


