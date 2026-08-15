"""
S-311: Interview Decision Engine — REST Endpoints
Full CRUD endpoints for interview decision workflow.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.tenant_context import get_current_user, require_auth
from app.services.interview_decision_service import InterviewDecisionService
from app.schemas.interview_decision import (
    GetInterviewStatusRequest,
    GetInterviewStatusResponse,
    CalculatePanelDecisionRequest,
    CalculatePanelDecisionResponse,
    MoveToOfferRequest,
    MoveToOfferResponse,
    RejectCandidateRequest,
    RejectCandidateResponse,
)

router = APIRouter(
    prefix="/api/v1/interview-decisions",
    tags=["interview-decisions"],
)

decision_service = InterviewDecisionService()


@router.post(
    "/status",
    response_model=GetInterviewStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Interview Status",
    description="Retrieve full interview status with all feedback collected."
)
async def get_interview_status(
    request: GetInterviewStatusRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth),
):
    """
    Get the status of an interview including all panel feedback.

    - **interview_id**: The ID of the interview
    - **tenant_id**: Tenant context (optional)

    Returns full interview status with all feedback received.
    """
    try:
        status_data = decision_service.get_interview_status(
            db,
            request.interview_id,
            request.tenant_id or 1  # Default to tenant 1 if not provided
        )

        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )

        return status_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get interview status: {str(e)}"
        )


@router.post(
    "/calculate-decision",
    response_model=CalculatePanelDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Panel Decision",
    description="Aggregate panel feedback into a hiring decision."
)
async def calculate_panel_decision(
    request: CalculatePanelDecisionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth),
):
    """
    Calculate the panel decision by aggregating all interviewer feedback.

    - **interview_id**: The ID of the interview
    - **tenant_id**: Tenant context (optional)

    Returns the aggregated decision (APPROVED, REJECTED, PENDING_REVIEW) with voting breakdown.
    """
    try:
        decision_data = decision_service.calculate_panel_decision(
            db,
            request.interview_id,
            request.tenant_id or 1  # Default to tenant 1 if not provided
        )

        return decision_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate panel decision: {str(e)}"
        )


@router.post(
    "/move-to-offer",
    response_model=MoveToOfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Move to Offer",
    description="Create an offer after interview approval."
)
async def move_to_offer(
    request: MoveToOfferRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth),
):
    """
    Create an offer for a candidate after their interview is approved.

    - **interview_id**: The ID of the completed interview
    - **candidate_id**: The candidate's ID
    - **job_id**: The job ID
    - **approved_salary_usd_cents**: Approved salary in USD cents
    - **position_title**: Title of the position being offered
    - **start_date**: Expected start date
    - **created_by_user_id**: User creating the offer

    Only candidates with APPROVED interviews can receive offers.
    """
    try:
        result = decision_service.move_to_offer(
            db,
            request.interview_id,
            request.candidate_id,
            request.job_id,
            request.tenant_id or 1,  # Default to tenant 1 if not provided
            request.approved_salary_usd_cents,
            request.position_title,
            request.start_date,
            request.created_by_user_id
        )

        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create offer: {str(e)}"
        )


@router.post(
    "/reject-candidate",
    response_model=RejectCandidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Candidate",
    description="Reject a candidate after interview completion."
)
async def reject_candidate(
    request: RejectCandidateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth),
):
    """
    Reject a candidate based on interview feedback.

    - **interview_id**: The ID of the interview
    - **tenant_id**: Tenant context (optional)
    - **rejection_reason**: The reason for rejection
    - **rejected_by_user_id**: User ID of the person rejecting

    Marks the candidate as rejected and creates a decision log.
    """
    try:
        result = decision_service.reject_candidate(
            db,
            request.interview_id,
            request.tenant_id or 1,  # Default to tenant 1 if not provided
            request.rejection_reason,
            request.rejected_by_user_id
        )

        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject candidate: {str(e)}"
        )


# ────────────────────────────────────────────────────────────────────────────
# Health Check Endpoint
# ────────────────────────────────────────────────────────────────────────────

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check for interview decision service."""
    return {
        "status": "healthy",
        "service": "interview_decision",
        "version": "1.0.0"
    }
