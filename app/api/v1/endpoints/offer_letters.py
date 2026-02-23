from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate, get_current_user
from app.models.offer_letter import OfferLetter
from app.models.candidate import Candidate
from app.models.user import Users
from app.schemas.user import (
    OfferLetterCreateRequest,
    OfferLetterUpdateRequest,
    OfferLetterResponse,
    OfferAcceptanceRequest,
    OfferAcceptanceResponse,
    OfferCancelRequest,
    AllOffersResponse,
    DeleteResponse
)

router = APIRouter(prefix="/offer-letter", tags=["offer-letter"])


# ============================================
# CANDIDATE ENDPOINTS
# ============================================

@router.post("/respond", response_model=OfferAcceptanceResponse)
def respond_to_offer(
    request: OfferAcceptanceRequest,
    db: Session = Depends(get_db),
    candidate = Depends(get_current_candidate)
):
    """
    Candidate responds to an offer letter (accept or reject).
    
    Args:
        request: OfferAcceptanceRequest with offer_id, action, and optional response_message
        db: Database session
        candidate: Authenticated candidate
        
    Returns:
        OfferAcceptanceResponse with status and updated offer details
        
    Raises:
        HTTPException: If offer not found, doesn't belong to candidate, or invalid action
    """
    # Validate action
    if request.action.lower() not in ["accept", "reject"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be 'accept' or 'reject'"
        )
    
    # Get offer letter
    offer = db.query(OfferLetter).filter(OfferLetter.id == request.offer_id).first()
    
    if not offer:
        raise HTTPException(
            status_code=404,
            detail=f"Offer letter with ID {request.offer_id} not found"
        )
    
    # Verify offer belongs to authenticated candidate
    if offer.candidate_id != candidate.candidateID:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to respond to this offer"
        )
    
    # Check if offer is still pending
    if offer.offer_status != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond to offer with status '{offer.offer_status}'. Only pending offers can be responded to."
        )
    
    # Update offer status
    offer.offer_status = "Accepted" if request.action.lower() == "accept" else "Rejected"
    offer.candidate_response = request.response_message
    offer.responded_at = datetime.now()
    
    db.commit()
    db.refresh(offer)
    
    return OfferAcceptanceResponse(
        status="Success",
        message=f"Offer {offer.offer_status.lower()} successfully",
        offer_id=offer.id,
        offer_status=offer.offer_status,
        responded_at=offer.responded_at
    )


@router.get("/my-offers", response_model=AllOffersResponse)
def get_my_offers(
    db: Session = Depends(get_db),
    candidate = Depends(get_current_candidate)
):
    """
    Get all offer letters for the authenticated candidate.
    
    Args:
        db: Database session
        candidate: Authenticated candidate
        
    Returns:
        AllOffersResponse with list of offer letters
    """
    offers = db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate.candidateID
    ).all()
    
    offer_responses = []
    for offer in offers:
        # Get candidate details
        candidate_obj = db.query(Candidate).filter(
            Candidate.candidateID == offer.candidate_id
        ).first()
        
        candidate_name = None
        if candidate_obj:
            name_parts = []
            if candidate_obj.candidateFirstName:
                name_parts.append(candidate_obj.candidateFirstName)
            if candidate_obj.candidateMiddleName:
                name_parts.append(candidate_obj.candidateMiddleName)
            if candidate_obj.candidateLastName:
                name_parts.append(candidate_obj.candidateLastName)
            candidate_name = " ".join(name_parts) if name_parts else None
        
        offer_responses.append(OfferLetterResponse(
            id=offer.id,
            candidate_id=offer.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_obj.candidateEmail if candidate_obj else None,
            job_id=offer.job_id,
            hiring_manager_id=offer.hiring_manager_id,
            reporting_manager_id=offer.reporting_manager_id,
            position=offer.position,
            salary=offer.salary,
            joining_date=offer.joining_date,
            offer_status=offer.offer_status,
            candidate_response=offer.candidate_response,
            responded_at=offer.responded_at,
            created_at=offer.created_at,
            created_by=offer.created_by,
            cancelled_at=offer.cancelled_at,
            cancelled_by=offer.cancelled_by
        ))
    
    return AllOffersResponse(
        total_offers=len(offer_responses),
        offers=offer_responses
    )


# ============================================
# RECRUITER/HR ENDPOINTS
# ============================================

@router.post("/create", response_model=OfferLetterResponse)
def create_offer_letter(
    request: OfferLetterCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a new offer letter for a candidate (HR/Recruiter only).
    
    Args:
        request: OfferLetterCreateRequest with offer details
        db: Database session
        user: Authenticated user (HR/Recruiter)
        
    Returns:
        OfferLetterResponse with created offer details
        
    Raises:
        HTTPException: If candidate or managers not found
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == request.candidate_id
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )
    
    # Verify hiring manager exists
    hiring_manager = db.query(Users).filter(
        Users.UserID == request.hiring_manager_id
    ).first()
    
    if not hiring_manager:
        raise HTTPException(
            status_code=404,
            detail=f"Hiring manager with ID {request.hiring_manager_id} not found"
        )
    
    # Verify reporting manager exists
    reporting_manager = db.query(Users).filter(
        Users.UserID == request.reporting_manager_id
    ).first()
    
    if not reporting_manager:
        raise HTTPException(
            status_code=404,
            detail=f"Reporting manager with ID {request.reporting_manager_id} not found"
        )
    
    # Create new offer letter
    new_offer = OfferLetter(
        candidate_id=request.candidate_id,
        job_id=request.job_id,
        hiring_manager_id=request.hiring_manager_id,
        reporting_manager_id=request.reporting_manager_id,
        position=request.position,
        salary=request.salary,
        joining_date=request.joining_date,
        offer_status="Pending",
        created_by=user.UserID
    )
    
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)
    
    # Get candidate name
    name_parts = []
    if candidate.candidateFirstName:
        name_parts.append(candidate.candidateFirstName)
    if candidate.candidateMiddleName:
        name_parts.append(candidate.candidateMiddleName)
    if candidate.candidateLastName:
        name_parts.append(candidate.candidateLastName)
    candidate_name = " ".join(name_parts) if name_parts else None
    
    return OfferLetterResponse(
        id=new_offer.id,
        candidate_id=new_offer.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        job_id=new_offer.job_id,
        hiring_manager_id=new_offer.hiring_manager_id,
        reporting_manager_id=new_offer.reporting_manager_id,
        position=new_offer.position,
        salary=new_offer.salary,
        joining_date=new_offer.joining_date,
        offer_status=new_offer.offer_status,
        candidate_response=new_offer.candidate_response,
        responded_at=new_offer.responded_at,
        created_at=new_offer.created_at,
        created_by=new_offer.created_by,
        cancelled_at=new_offer.cancelled_at,
        cancelled_by=new_offer.cancelled_by
    )


@router.post("/cancel/{offer_id}", response_model=DeleteResponse)
def cancel_offer_letter(
    offer_id: int,
    request: OfferCancelRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Cancel an offer letter (HR/Recruiter only).
    
    Args:
        offer_id: ID of the offer letter to cancel
        request: OfferCancelRequest with optional reason
        db: Database session
        user: Authenticated user (HR/Recruiter)
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If offer not found or already processed
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    
    if not offer:
        raise HTTPException(
            status_code=404,
            detail=f"Offer letter with ID {offer_id} not found"
        )
    
    # Check if offer can be cancelled
    if offer.offer_status in ["Accepted", "Rejected", "Cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel offer with status '{offer.offer_status}'"
        )
    
    # Update offer status
    offer.offer_status = "Cancelled"
    offer.cancelled_at = datetime.now()
    offer.cancelled_by = user.UserID
    if request.reason:
        offer.candidate_response = f"Cancellation reason: {request.reason}"
    
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Offer letter {offer_id} cancelled successfully"
    )


@router.put("/update/{offer_id}", response_model=OfferLetterResponse)
def update_offer_letter(
    offer_id: int,
    request: OfferLetterUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Update an offer letter (HR/Recruiter only).
    
    Args:
        offer_id: ID of the offer letter to update
        request: OfferLetterUpdateRequest with fields to update
        db: Database session
        user: Authenticated user (HR/Recruiter)
        
    Returns:
        OfferLetterResponse with updated offer details
        
    Raises:
        HTTPException: If offer not found or already processed
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    
    if not offer:
        raise HTTPException(
            status_code=404,
            detail=f"Offer letter with ID {offer_id} not found"
        )
    
    # Check if offer can be updated (only pending offers)
    if offer.offer_status != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update offer with status '{offer.offer_status}'. Only pending offers can be updated."
        )
    
    # Update fields if provided
    if request.job_id is not None:
        offer.job_id = request.job_id
    
    if request.hiring_manager_id is not None:
        # Verify hiring manager exists
        hiring_manager = db.query(Users).filter(
            Users.UserID == request.hiring_manager_id
        ).first()
        if not hiring_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Hiring manager with ID {request.hiring_manager_id} not found"
            )
        offer.hiring_manager_id = request.hiring_manager_id
    
    if request.reporting_manager_id is not None:
        # Verify reporting manager exists
        reporting_manager = db.query(Users).filter(
            Users.UserID == request.reporting_manager_id
        ).first()
        if not reporting_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Reporting manager with ID {request.reporting_manager_id} not found"
            )
        offer.reporting_manager_id = request.reporting_manager_id
    
    if request.position is not None:
        offer.position = request.position
    
    if request.salary is not None:
        offer.salary = request.salary
    
    if request.joining_date is not None:
        offer.joining_date = request.joining_date
    
    db.commit()
    db.refresh(offer)
    
    # Get candidate details
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == offer.candidate_id
    ).first()
    
    candidate_name = None
    candidate_email = None
    if candidate:
        name_parts = []
        if candidate.candidateFirstName:
            name_parts.append(candidate.candidateFirstName)
        if candidate.candidateMiddleName:
            name_parts.append(candidate.candidateMiddleName)
        if candidate.candidateLastName:
            name_parts.append(candidate.candidateLastName)
        candidate_name = " ".join(name_parts) if name_parts else None
        candidate_email = candidate.candidateEmail
    
    return OfferLetterResponse(
        id=offer.id,
        candidate_id=offer.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        job_id=offer.job_id,
        hiring_manager_id=offer.hiring_manager_id,
        reporting_manager_id=offer.reporting_manager_id,
        position=offer.position,
        salary=offer.salary,
        joining_date=offer.joining_date,
        offer_status=offer.offer_status,
        candidate_response=offer.candidate_response,
        responded_at=offer.responded_at,
        created_at=offer.created_at,
        created_by=offer.created_by,
        cancelled_at=offer.cancelled_at,
        cancelled_by=offer.cancelled_by
    )


@router.get("/all", response_model=AllOffersResponse)
def get_all_offers(
    status: Optional[str] = Query(None, description="Filter by offer status"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get all offer letters with optional filters (HR/Recruiter only).
    
    Args:
        status: Optional filter by offer_status
        candidate_id: Optional filter by candidate_id
        db: Database session
        user: Authenticated user (HR/Recruiter)
        
    Returns:
        AllOffersResponse with list of offer letters
    """
    query = db.query(OfferLetter)
    
    # Apply filters
    if status:
        query = query.filter(OfferLetter.offer_status == status)
    if candidate_id:
        query = query.filter(OfferLetter.candidate_id == candidate_id)
    
    offers = query.all()
    
    offer_responses = []
    for offer in offers:
        # Get candidate details
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == offer.candidate_id
        ).first()
        
        candidate_name = None
        candidate_email = None
        if candidate:
            name_parts = []
            if candidate.candidateFirstName:
                name_parts.append(candidate.candidateFirstName)
            if candidate.candidateMiddleName:
                name_parts.append(candidate.candidateMiddleName)
            if candidate.candidateLastName:
                name_parts.append(candidate.candidateLastName)
            candidate_name = " ".join(name_parts) if name_parts else None
            candidate_email = candidate.candidateEmail
        
        offer_responses.append(OfferLetterResponse(
            id=offer.id,
            candidate_id=offer.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            job_id=offer.job_id,
            hiring_manager_id=offer.hiring_manager_id,
            reporting_manager_id=offer.reporting_manager_id,
            position=offer.position,
            salary=offer.salary,
            joining_date=offer.joining_date,
            offer_status=offer.offer_status,
            candidate_response=offer.candidate_response,
            responded_at=offer.responded_at,
            created_at=offer.created_at,
            created_by=offer.created_by,
            cancelled_at=offer.cancelled_at,
            cancelled_by=offer.cancelled_by
        ))
    
    return AllOffersResponse(
        total_offers=len(offer_responses),
        offers=offer_responses
    )


@router.get("/{offer_id}", response_model=OfferLetterResponse)
def get_offer_by_id(
    offer_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get a specific offer letter by ID (HR/Recruiter only).
    
    Args:
        offer_id: ID of the offer letter
        db: Database session
        user: Authenticated user (HR/Recruiter)
        
    Returns:
        OfferLetterResponse with offer details
        
    Raises:
        HTTPException: If offer not found
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    
    if not offer:
        raise HTTPException(
            status_code=404,
            detail=f"Offer letter with ID {offer_id} not found"
        )
    
    # Get candidate details
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == offer.candidate_id
    ).first()
    
    candidate_name = None
    candidate_email = None
    if candidate:
        name_parts = []
        if candidate.candidateFirstName:
            name_parts.append(candidate.candidateFirstName)
        if candidate.candidateMiddleName:
            name_parts.append(candidate.candidateMiddleName)
        if candidate.candidateLastName:
            name_parts.append(candidate.candidateLastName)
        candidate_name = " ".join(name_parts) if name_parts else None
        candidate_email = candidate.candidateEmail
    
    return OfferLetterResponse(
        id=offer.id,
        candidate_id=offer.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        job_id=offer.job_id,
        hiring_manager_id=offer.hiring_manager_id,
        reporting_manager_id=offer.reporting_manager_id,
        position=offer.position,
        salary=offer.salary,
        joining_date=offer.joining_date,
        offer_status=offer.offer_status,
        candidate_response=offer.candidate_response,
        responded_at=offer.responded_at,
        created_at=offer.created_at,
        created_by=offer.created_by,
        cancelled_at=offer.cancelled_at,
        cancelled_by=offer.cancelled_by
    )
