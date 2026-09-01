"""
Candidate Rejection Workflow Endpoints

Routes for rejecting candidates and managing rejection workflow:
  POST   /rejection/reject               — reject candidate
  POST   /rejection/{id}/send-email      — send rejection email
  POST   /rejection/{id}/archive         — archive rejected candidate
  GET    /rejection/reasons              — get available rejection reasons
  GET    /rejection/candidate/{id}       — get rejection status for candidate
  GET    /rejection/{id}                 — get specific rejection record
  GET    /rejection/list                 — list all rejections (paginated)

Story: S-322 (Candidate Rejection Workflow)
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.candidate import Candidate
from app.models.candidate_rejection import CandidateRejection
from app.schemas.candidate_rejection import (
    RejectCandidateRequest,
    RejectCandidateResponse,
    SendRejectionEmailRequest,
    SendRejectionEmailResponse,
    ArchiveCandidateRequest,
    ArchiveCandidateResponse,
    CandidateRejectionReasonResponse,
    CandidateRejectionResponse,
    CandidateRejectionStatusResponse,
    ListCandidateRejectionsResponse,
)
from app.services.candidate_rejection_service import (
    reject_candidate,
    send_rejection_email,
    archive_candidate,
    get_rejection_reasons,
    get_candidate_rejection_status,
    CandidateRejectionError,
    CandidateNotFoundError,
    create_default_rejection_reasons,
)
from app.core.logging import logger

router = APIRouter(prefix="/rejection", tags=["candidate-rejection"])


# ---------------------------------------------------------------------------
# POST /rejection/reject — Reject a candidate
# ---------------------------------------------------------------------------

@router.post("/reject", response_model=RejectCandidateResponse, status_code=201)
def api_reject_candidate(
    request: RejectCandidateRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Reject a candidate and optionally send rejection email.

    Request Body:
    - candidate_id: ID of candidate to reject
    - job_id: Optional job ID
    - rejection_reason: Reason for rejection
    - rejection_note: Optional detailed note
    - send_email: Whether to send rejection email (default: True)

    Returns:
    - rejection_id: ID of created rejection record
    - rejection_status: "ACTIVE"
    - email_sent: Whether email was sent

    Example:
    ```json
    {
      "candidate_id": "C-12345",
      "rejection_reason": "LACK_OF_EXPERIENCE",
      "rejection_note": "Candidate has only 3 years experience, role requires 5+",
      "send_email": true
    }
    ```
    """
    try:
        rejection = reject_candidate(
            db,
            candidate_id=request.candidate_id,
            rejection_reason=request.rejection_reason,
            rejection_note=request.rejection_note,
            job_id=request.job_id,
            rejected_by_user_id=current_user.UserID,
            send_email=request.send_email,
            tenant_id=request.tenant_id or 1,
        )

        return RejectCandidateResponse(
            rejection_id=rejection.id,
            candidate_id=rejection.candidate_id,
            job_id=rejection.job_id,
            rejection_reason=rejection.rejection_reason,
            rejection_status=rejection.rejection_status,
            rejected_at=rejection.rejected_at,
            email_sent=rejection.email_sent,
            email_sent_at=rejection.email_sent_at,
            message="Candidate rejected successfully" + (
                " and email sent" if rejection.email_sent else ""
            ),
        )

    except CandidateNotFoundError as e:
        logger.warning(f"Candidate not found during rejection: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

    except CandidateRejectionError as e:
        logger.error(f"Error rejecting candidate: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error during rejection: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# POST /rejection/{id}/send-email — Send rejection email
# ---------------------------------------------------------------------------

@router.post("/{rejection_id}/send-email", response_model=SendRejectionEmailResponse)
def api_send_rejection_email(
    rejection_id: int,
    request: SendRejectionEmailRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Send rejection email to candidate.

    Path Parameters:
    - rejection_id: ID of rejection record

    Request Body:
    - include_feedback: Include detailed feedback in email
    - include_next_steps: Include next steps candidate can take

    Returns:
    - email_sent: True if email was sent successfully
    - email_sent_at: Timestamp of email send

    Example:
    ```
    POST /rejection/5/send-email
    {
      "include_feedback": true,
      "include_next_steps": true
    }
    ```
    """
    try:
        rejection = send_rejection_email(
            db,
            rejection_id=rejection_id,
            include_feedback=request.include_feedback,
            include_next_steps=request.include_next_steps,
        )

        candidate = db.query(Candidate).filter(
            Candidate.candidateID == rejection.candidate_id
        ).first()

        return SendRejectionEmailResponse(
            rejection_id=rejection.id,
            candidate_id=rejection.candidate_id,
            candidate_email=candidate.candidateEmail if candidate else "unknown",
            email_sent=rejection.email_sent,
            email_sent_at=rejection.email_sent_at,
            message="Rejection email sent successfully",
        )

    except CandidateRejectionError as e:
        logger.error(f"Error sending rejection email: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# POST /rejection/{id}/archive — Archive rejected candidate
# ---------------------------------------------------------------------------

@router.post("/{rejection_id}/archive", response_model=ArchiveCandidateResponse)
def api_archive_candidate(
    rejection_id: int,
    request: ArchiveCandidateRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Archive (soft-delete) a rejected candidate.
    Candidate record preserved in DB for audit trail.

    Path Parameters:
    - rejection_id: ID of rejection record

    Request Body:
    - archive_reason: Why are we archiving?
    - archive_note: Additional context

    Returns:
    - rejection_status: "ARCHIVED"
    - archived_at: Timestamp of archival

    Example:
    ```
    POST /rejection/5/archive
    {
      "archive_reason": "Position filled",
      "archive_note": "Candidate no longer needed for this cycle"
    }
    ```
    """
    try:
        # First, get the rejection record to find the candidate
        rejection = db.query(CandidateRejection).filter(
            CandidateRejection.id == rejection_id
        ).first()

        if not rejection:
            raise CandidateRejectionError(f"Rejection record {rejection_id} not found")

        # Archive the candidate via the service
        updated_rejection = archive_candidate(
            db,
            candidate_id=rejection.candidate_id,
            archive_reason=request.archive_reason,
            archive_note=request.archive_note,
            archived_by_user_id=current_user.UserID,
        )

        return ArchiveCandidateResponse(
            rejection_id=updated_rejection.id,
            candidate_id=updated_rejection.candidate_id,
            rejection_status=updated_rejection.rejection_status,
            archived_at=updated_rejection.archived_at,
            message="Candidate archived successfully",
        )

    except CandidateRejectionError as e:
        logger.error(f"Error archiving candidate: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error archiving candidate: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /rejection/reasons — Get available rejection reasons
# ---------------------------------------------------------------------------

@router.get("/reasons", response_model=list[CandidateRejectionReasonResponse])
def api_get_rejection_reasons(
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Get list of available rejection reasons for dropdown.

    Returns:
    - List of rejection reason objects with code, label, and category

    Example Response:
    ```json
    [
      {
        "id": 1,
        "reason_code": "LACK_OF_EXPERIENCE",
        "reason_label": "Lacks Required Experience",
        "reason_description": "Candidate does not meet minimum experience requirements",
        "category": "Experience",
        "is_active": true
      },
      ...
    ]
    ```
    """
    try:
        # Initialize default reasons if they don't exist
        create_default_rejection_reasons(db)

        reasons = get_rejection_reasons(db, active_only=True)
        return reasons

    except Exception as e:
        logger.error(f"Error fetching rejection reasons: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /rejection/candidate/{candidate_id} — Get candidate rejection status
# ---------------------------------------------------------------------------

@router.get("/candidate/{candidate_id}", response_model=CandidateRejectionStatusResponse)
def api_get_candidate_rejection_status(
    candidate_id: str,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Check if candidate has been rejected and get rejection details.

    Path Parameters:
    - candidate_id: Candidate ID

    Returns:
    - is_rejected: Boolean indicating if candidate is rejected
    - rejection_count: Number of rejections
    - latest_rejection: Most recent rejection record
    - all_rejections: All rejection records

    Example:
    ```
    GET /rejection/candidate/C-12345
    ```
    """
    try:
        is_rejected, latest_rejection, all_rejections = get_candidate_rejection_status(
            db,
            candidate_id=candidate_id,
        )

        return CandidateRejectionStatusResponse(
            candidate_id=candidate_id,
            is_rejected=is_rejected,
            rejection_count=len(all_rejections),
            latest_rejection=latest_rejection,
            all_rejections=all_rejections,
        )

    except Exception as e:
        logger.error(f"Error fetching rejection status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /rejection/{id} — Get specific rejection record
# ---------------------------------------------------------------------------

@router.get("/{rejection_id}", response_model=CandidateRejectionResponse)
def api_get_rejection(
    rejection_id: int,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific rejection record by ID.

    Path Parameters:
    - rejection_id: Rejection record ID

    Returns:
    - Full rejection record with all details

    Example:
    ```
    GET /rejection/5
    ```
    """
    try:
        rejection = db.query(CandidateRejection).filter(
            CandidateRejection.id == rejection_id
        ).first()

        if not rejection:
            raise HTTPException(status_code=404, detail="Rejection record not found")

        return rejection

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error fetching rejection record: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /rejection/list — List all rejections (paginated)
# ---------------------------------------------------------------------------

@router.get("", response_model=ListCandidateRejectionsResponse)
def api_list_rejections(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE or ARCHIVED"),
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    List all candidate rejections (paginated).

    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 10, max: 100)
    - status: Filter by status (ACTIVE or ARCHIVED, optional)

    Returns:
    - total: Total number of rejections
    - page: Current page number
    - page_size: Records per page
    - rejections: List of rejection records

    Example:
    ```
    GET /rejection/list?skip=0&limit=10&status=ACTIVE
    ```
    """
    try:
        query = db.query(CandidateRejection)

        if status:
            query = query.filter(CandidateRejection.rejection_status == status)

        total = query.count()
        rejections = query.order_by(
            CandidateRejection.rejected_at.desc()
        ).offset(skip).limit(limit).all()

        return ListCandidateRejectionsResponse(
            total=total,
            page=skip // limit + 1,
            page_size=limit,
            rejections=rejections,
        )

    except Exception as e:
        logger.error(f"Error listing rejections: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
