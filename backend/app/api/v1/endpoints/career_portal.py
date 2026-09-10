"""CYCLE 15: Career Site Portal API - Public candidate-facing endpoints"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.demand import Demand
from app.models.submission import Submission
from app.models.candidate_job_score import CandidateJobScore
from app.services.career_portal_service import CareerPortalService

router = APIRouter(prefix="/api/v1/careers", tags=["career-portal"])


# Response Models
class JobListResponse(BaseModel):
    id: str
    title: str
    description: str
    location: Optional[str]
    experience_required: float
    skills_required: Optional[list]
    employment_type: str
    urgency: str
    status: str

    class Config:
        from_attributes = True


class JobDetailResponse(JobListResponse):
    client_name: Optional[str]
    domain: Optional[str]
    interview_type: str
    headcount: int
    positions_filled: int
    required_start_date: Optional[str]


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    job_title: str
    status: str
    applied_date: str
    fit_score: Optional[int]
    last_update: Optional[str]
    next_step: Optional[str]

    class Config:
        from_attributes = True


class CandidateProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str]
    current_location: Optional[str]
    current_role: Optional[str]
    experience_years: Optional[int]
    skills: Optional[list]

    class Config:
        from_attributes = True


class ApplyRequestBody(BaseModel):
    job_id: str
    resume_text: Optional[str] = None
    cover_letter: Optional[str] = None
    custom_answers: Optional[dict] = None


class ResumeAnalysisResponse(BaseModel):
    overall_fit_score: int
    technical_match: int
    experience_match: int
    skills_match: int
    gaps_identified: List[str]
    strengths: List[str]
    has_critical_gaps: bool


# ============================================================================
# PUBLIC ENDPOINTS (Candidate-facing via Career Site)
# ============================================================================

@router.get("/jobs", response_model=List[JobListResponse])
def get_open_jobs(
    db: Session = Depends(get_db),
    location: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """Get all open jobs for career site browsing (public endpoint)"""
    try:
        jobs = CareerPortalService.get_open_jobs(
            db=db,
            location=location,
            skip=skip,
            limit=limit
        )
        return jobs
    except Exception as e:
        logger.error(f"Failed to fetch open jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch open jobs"
        )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed view of a specific job"""
    try:
        job = CareerPortalService.get_job_detail(db=db, job_id=job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job details"
        )


@router.post("/apply", response_model=ApplicationResponse)
async def submit_application(
    request: ApplyRequestBody,
    db: Session = Depends(get_db),
    current_user: Candidate = Depends(get_current_user)
):
    """Submit application to a job"""
    try:
        # Check if already applied
        existing = CareerPortalService.get_existing_application(
            db=db,
            candidate_id=current_user.candidateID,
            job_id=request.job_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Already applied to this job"
            )

        # Create application
        application = CareerPortalService.create_application(
            db=db,
            candidate_id=current_user.candidateID,
            job_id=request.job_id,
            resume_text=request.resume_text,
            cover_letter=request.cover_letter,
            custom_answers=request.custom_answers
        )

        if not application:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create application"
            )

        return application

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit application: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit application"
        )


@router.get("/applications", response_model=List[ApplicationResponse])
def get_candidate_applications(
    db: Session = Depends(get_db),
    current_user: Candidate = Depends(get_current_user)
):
    """Get all applications submitted by candidate"""
    try:
        applications = CareerPortalService.get_candidate_applications(
            db=db,
            candidate_id=current_user.candidateID
        )
        return applications
    except Exception as e:
        logger.error(f"Failed to fetch applications: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch applications"
        )


@router.get("/applications/{application_id}/status", response_model=ApplicationResponse)
def get_application_status(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: Candidate = Depends(get_current_user)
):
    """Check status of specific application"""
    try:
        application = CareerPortalService.get_application_status(
            db=db,
            application_id=application_id,
            candidate_id=current_user.candidateID
        )
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        return application
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch application status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch application status"
        )


@router.get("/candidate/me", response_model=CandidateProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: Candidate = Depends(get_current_user)
):
    """Get current candidate's profile"""
    try:
        profile = CareerPortalService.get_candidate_profile(
            db=db,
            candidate_id=current_user.candidateID
        )
        if not profile:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch candidate profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )


@router.post("/resume/analyze", response_model=ResumeAnalysisResponse)
async def analyze_resume(
    job_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Candidate = Depends(get_current_user)
):
    """Analyze resume fit against job requirements"""
    try:
        # Read resume file
        contents = await file.read()
        resume_text = contents.decode('utf-8')

        # Get job and analyze
        analysis = CareerPortalService.analyze_resume_fit(
            db=db,
            candidate_id=current_user.candidateID,
            job_id=job_id,
            resume_text=resume_text
        )

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to analyze resume"
            )

        return analysis

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze resume: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze resume"
        )
