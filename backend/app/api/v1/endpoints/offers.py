"""
HRMS-0312: Offer Management & Approval REST Endpoints
Complete offer lifecycle API endpoints.
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.core.logging import logger
from app.schemas.offer import (
    OfferCreateRequest, OfferApproveRequest, OfferRejectRequest,
    OfferSendRequest, OfferAcceptanceRequest, OfferRetractionRequest,
    OfferResponse, OfferListResponse, OfferStatusResponse,
    OfferApprovalResponse, OfferSendResponse, OfferAcceptanceResponse,
    OfferSummary
)
from app.services.offer_management_service import OfferManagementService
from app.services.message_queue_service import MessageQueueService
from app.models.offer import Offer
from app.models.candidate import Candidate

router = APIRouter(prefix="/offers", tags=["offers"])
offer_service = OfferManagementService()


def _get_tenant_id_from_request(db: Session) -> int:
    """Extract tenant ID from request context (middleware sets this)."""
    return 1  # Default tenant for now; in multi-tenant, comes from middleware


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CREATE OFFER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/create",
    response_model=OfferResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Create a new offer"
)
def create_offer(
    request: OfferCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a new offer for a candidate.

    **Required permission:** `offer.manage`

    **Business Rules:**
    - Candidate must exist
    - Job must exist
    - Offer starts in DRAFT status
    - Creator is automatically set to current user
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        result = offer_service.create_offer(
            db=db,
            candidate_id=request.candidate_id,
            job_id=request.job_id,
            tenant_id=tenant_id,
            base_salary_usd_cents=request.base_salary_usd_cents,
            signing_bonus_usd_cents=request.signing_bonus_usd_cents,
            position_title=request.position_title,
            expected_start_date=request.expected_start_date,
            benefits=request.benefits.dict() if request.benefits else {},
            created_by_user_id=user.UserID,
            approval_notes=request.approval_notes
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        # Fetch the created offer to return full response
        offer = db.query(Offer).filter(Offer.id == result["offer_id"]).first()

        # Queue offer_generated message for approval workflow
        candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
        if offer and candidate:
            MessageQueueService.enqueue(
                message_type="offer_generated",
                payload={
                    "offer_id": offer.id,
                    "candidate_id": request.candidate_id,
                    "candidate_email": candidate.candidateEmail,
                    "candidate_name": f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip(),
                    "position_title": request.position_title,
                    "base_salary_usd_cents": request.base_salary_usd_cents,
                    "signing_bonus_usd_cents": request.signing_bonus_usd_cents,
                    "expected_start_date": str(request.expected_start_date),
                },
                resource_id=offer.id,
                queue_type="APPROVAL_QUEUE",
                created_by=user.UserID,
                db=db,
            )

        return OfferResponse.from_orm(offer)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating offer: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# APPROVE OFFER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/{offer_id}/approve",
    response_model=OfferApprovalResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Approve an offer"
)
def approve_offer(
    offer_id: str,
    request: OfferApproveRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Approve an offer, allowing it to be sent to candidate.

    **Required permission:** `offer.approve`

    **Business Rules:**
    - Offer must be in DRAFT status
    - Approver must be a valid user
    - Offer then moves to APPROVED status
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        result = offer_service.approve_offer(
            db=db,
            offer_id=offer_id,
            tenant_id=tenant_id,
            approved_by_user_id=request.approved_by_user_id or user.UserID,
            approval_notes=request.approval_notes
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return OfferApprovalResponse(
            status="success",
            message=f"Offer {offer_id} approved successfully",
            offer_id=offer_id,
            offer_status=result["offer_status"],
            approved_at=result["approved_at"],
            approved_by_user_id=result["approved_by"],
            timestamp=result.get("approved_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving offer {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to approve offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SEND OFFER TO CANDIDATE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/{offer_id}/send",
    response_model=OfferSendResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Send offer to candidate"
)
def send_offer_to_candidate(
    offer_id: str,
    request: OfferSendRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Send an approved offer to the candidate via email.

    **Required permission:** `offer.manage`

    **Business Rules:**
    - Offer must be in APPROVED status
    - Offer will expire in 7-30 days (configurable)
    - Candidate is notified via email
    - Offer moves to SENT status
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        result = offer_service.send_offer_to_candidate(
            db=db,
            offer_id=offer_id,
            tenant_id=tenant_id,
            candidate_email=request.candidate_email,
            expiration_days=request.expiration_days
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return OfferSendResponse(
            status="success",
            message=f"Offer sent to {request.candidate_email}",
            offer_id=offer_id,
            offer_status=result["offer_status"],
            sent_to_email=result["sent_to"],
            sent_at=result["sent_at"],
            expires_at=result["expires_at"],
            timestamp=result.get("sent_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending offer {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# REJECT OFFER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/{offer_id}/reject",
    response_model=OfferStatusResponse,
    summary="Reject an offer (candidate action)"
)
def reject_offer(
    offer_id: str,
    request: OfferRejectRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Record candidate rejection of an offer.

    **Business Rules:**
    - Offer must be in SENT or REVIEWED status
    - Rejection reason is required
    - Offer moves to REJECTED status
    - Candidate status is updated accordingly
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        result = offer_service.reject_offer(
            db=db,
            offer_id=offer_id,
            tenant_id=tenant_id,
            rejection_reason=request.rejection_reason
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return OfferStatusResponse(
            status="success",
            message=f"Offer rejected",
            offer_id=offer_id,
            offer_status=result["offer_status"],
            timestamp=result.get("rejected_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting offer {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reject offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RETRACT OFFER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/{offer_id}/retract",
    response_model=OfferStatusResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "edit"))],
    summary="Retract an offer (HR action)"
)
def retract_offer(
    offer_id: str,
    request: OfferRetractionRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Retract an offer if candidate hasn't accepted it.

    **Required permission:** `offer.manage`

    **Business Rules:**
    - Cannot retract accepted offers
    - Retraction reason is required
    - Offer moves to RETRACTED status
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        result = offer_service.retract_offer(
            db=db,
            offer_id=offer_id,
            tenant_id=tenant_id,
            retraction_reason=request.retraction_reason
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return OfferStatusResponse(
            status="success",
            message=f"Offer retracted",
            offer_id=offer_id,
            offer_status=result["offer_status"],
            timestamp=result.get("retracted_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retracting offer {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retract offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ACCEPT OFFER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/{offer_id}/accept",
    response_model=OfferAcceptanceResponse,
    summary="Accept an offer (candidate action)"
)
def accept_offer(
    offer_id: str,
    request: OfferAcceptanceRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Record candidate acceptance of an offer.

    **Business Rules:**
    - Offer must be in SENT or REVIEWED status
    - Offer must not be expired
    - Offer moves to ACCEPTED status
    - Candidate status is updated to OFFER_ACCEPTED
    - Triggers onboarding workflow
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        result = offer_service.accept_offer(
            db=db,
            offer_id=offer_id,
            tenant_id=tenant_id,
            candidate_id=request.candidate_id
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return OfferAcceptanceResponse(
            status="success",
            message=f"Offer accepted successfully",
            offer_id=offer_id,
            offer_status=result["offer_status"],
            candidate_id=result["candidate_id"],
            accepted_at=result["accepted_at"],
            start_date=result["start_date"],
            timestamp=result.get("accepted_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting offer {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to accept offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# GET OFFER BY ID
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get(
    "/{offer_id}",
    response_model=OfferResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
    summary="Get offer by ID"
)
def get_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Retrieve a specific offer by ID.

    **Required permission:** `offer.view`
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        offer = db.query(Offer).filter(
            Offer.id == offer_id,
            Offer.tenant_id == tenant_id
        ).first()

        if not offer:
            raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")

        return OfferResponse.from_orm(offer)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching offer {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch offer")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LIST OFFERS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get(
    "",
    response_model=OfferListResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
    summary="List offers with filters"
)
def list_offers(
    status: Optional[str] = Query(None, description="Filter by offer status"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    skip: int = Query(0, ge=0, description="Number of offers to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum offers to return"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    List offers with optional filters.

    **Required permission:** `offer.view`

    **Filter Options:**
    - `status`: DRAFT, APPROVED, SENT, REVIEWED, ACCEPTED, REJECTED, RETRACTED, EXPIRED, SIGNED
    - `candidate_id`: Filter by specific candidate
    - `job_id`: Filter by specific job
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        query = db.query(Offer).filter(Offer.tenant_id == tenant_id)

        if status:
            query = query.filter(Offer.status == status)
        if candidate_id:
            query = query.filter(Offer.candidate_id == candidate_id)
        if job_id:
            query = query.filter(Offer.job_id == job_id)

        total = query.count()
        offers = query.offset(skip).limit(limit).all()

        return OfferListResponse(
            total=total,
            offers=[OfferResponse.from_orm(offer) for offer in offers]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing offers: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list offers")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# OFFER STATUS SUMMARY
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get(
    "/candidate/{candidate_id}",
    response_model=OfferListResponse,
    summary="Get all offers for a candidate"
)
def get_candidate_offers(
    candidate_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get all offers for a specific candidate.

    **Returns offers in any status.**
    """
    try:
        tenant_id = _get_tenant_id_from_request(db)

        offers = db.query(Offer).filter(
            Offer.candidate_id == candidate_id,
            Offer.tenant_id == tenant_id
        ).order_by(Offer.created_at.desc()).all()

        return OfferListResponse(
            total=len(offers),
            offers=[OfferResponse.from_orm(offer) for offer in offers]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching offers for candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch offers")
