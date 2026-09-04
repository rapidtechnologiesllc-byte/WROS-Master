"""
Candidate Creation Endpoint - Clean Implementation

This module handles candidate creation with proper error handling,
authentication, and background task integration.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.dependencies import get_current_user, get_db
from app.models.user import Users
from app.services.candidate_service import (
    create_candidate_safe,
    parse_experience_to_months,
    DuplicateCandidateError,
)
from app.services.ai_conversation_service import run_auto_assign_ai_agent_in_background
from app.utils.uniq_id_generator import generate_password
from app.schemas.candidate import CandidateCreateRequest, CandidateCreateResponse

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.post(
    "/create",
    summary="Create a new candidate",
    description="Create a candidate profile and auto-assign to Thunder AI recruiter",
)
def create_candidate(
    request: CandidateCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Create a new candidate and assign to Thunder AI recruiter.

    Args:
        request: Candidate creation request with required fields
        current_user: Authenticated user making the request
        db: Database session
        background_tasks: FastAPI background tasks queue

    Returns:
        CandidateCreateResponse with candidate_id, is_first_time flag, and generated password

    Raises:
        HTTPException: If location not provided or validation fails
    """
    # Validate mandatory location field (required for candidate search)
    if not request.candidate_current_location or not request.candidate_current_location.strip():
        raise HTTPException(
            status_code=400,
            detail="Location (City, State, Country) is mandatory for candidate creation"
        )

    # Generate temporary password for new candidate
    password = generate_password()

    try:
        # Create candidate using the sanctioned R-07 path with dedup checking
        candidate, is_new = create_candidate_safe(
            db,
            email=request.candidate_email,
            mobile=request.candidate_mobile,
            plain_password=password,
            tenant_id=current_user.tenant_id,
            candidateRole=request.candidate_role or "Candidate",
            candidateEmployeeType=request.candidate_employee_type,
            candidateJobTitle=request.candidate_job_title,
            candidateFirstName=request.candidate_first_name,
            candidateCurrentLocation=request.candidate_current_location,
            candidateCreatedAt=datetime.now(),
        )

    except DuplicateCandidateError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Account already exists with email {request.candidate_email}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create candidate: {str(e)}"
        ) from e

    # Commit the candidate to database
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error while creating candidate: {str(e)}"
        ) from e

    # Extract candidate ID for background task
    candidate_id = candidate.candidateID

    # Auto-assign candidate to Thunder AI recruiter in background
    # This creates conversation and queues initial email message
    background_tasks.add_task(
        run_auto_assign_ai_agent_in_background,
        candidate_id
    )

    # Return response with generated password for candidate notification
    return {
        "candidate_id": candidate_id,
        "candidate_is_first_time": True,
        "candidate_password": password
    }
