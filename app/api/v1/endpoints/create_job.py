from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.user import Jobs
from app.schemas.user import (
    GenerateJobDescriptionRequest, GenerateJobDescriptionResponse,
    JobCreateRequest, JobCreateResponse,
    JobUpdateRequest, JobResponse,
    AllJobsResponse, DeleteResponse,
    LinkedInPostRequest, LinkedInPostResponse
)
from app.utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator, job_id_generator

from app.tools.job_description_generator import generate_job_description_with_state

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post(
    "/generate_job_description",
    dependencies=[Depends(require_permission("job.create"))],
)
def generate_job_description(
    request: GenerateJobDescriptionRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
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


@router.get(
    "/all",
    response_model=AllJobsResponse,
    dependencies=[Depends(require_permission("job.view"))],
)
def get_all_jobs(
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Get all jobs from the system.
    
    Args:
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        AllJobsResponse with list of all jobs and total count
    """
    # Query all jobs from the Jobs table
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
            salary_range=j.salaryRange
        ))
    
    return AllJobsResponse(
        total_jobs=len(jobs_data),
        jobs=jobs_data
    )



@router.post(
    "/create_job",
    response_model=JobCreateResponse,
    dependencies=[Depends(require_permission("job.create"))],
)
def create_job(request: JobCreateRequest, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
    """
    Create a new job posting.
    
    Args:
        request: JobCreateRequest containing job details
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        JobCreateResponse with job_id and success message
    """
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
        jobStatus=request.job_status,
        noOfPositions=request.no_of_positions,
        startDate=request.start_date,
        endDate=request.end_date,
        hiringManagerID=request.hiring_manager_id,
        recuriterID=request.recuriter_id,
        business_unit_id=request.business_unit,
        salaryRange=request.salary_range
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return JobCreateResponse(job_id=job_id, response="Job created successfully")


@router.put(
    "/update_job/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(require_permission("job.edit"))],
)
def update_job(job_id: str, request: JobUpdateRequest, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
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
        salary_range=job.salaryRange
    )


@router.delete(
    "/delete_job/{job_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_permission("job.delete"))],
)
def delete_job(job_id: str, db: Session = Depends(get_db), user = Depends(get_current_hr_or_admin)):
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
    dependencies=[Depends(require_permission("job.create"))],
)
def post_job_on_linkedin(
    request: LinkedInPostRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    """
    Post a created job to LinkedIn (Pseudo API - Mock Implementation).
    
    This is a pseudo/mock implementation since LinkedIn API access is not available yet.
    It simulates posting a job to LinkedIn and returns a mock response.
    
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
    
    # Return mock LinkedIn posting response
    return LinkedInPostResponse(
        status="Success",
        message=f"Job '{job.jobTitle}' successfully posted to LinkedIn (Mock)",
        linkedin_post_id=linkedin_post_id,
        posted_at=posted_at,
        job_details=job_details
    )
