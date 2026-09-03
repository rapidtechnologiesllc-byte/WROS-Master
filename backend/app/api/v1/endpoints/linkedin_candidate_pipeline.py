"""
LinkedIn Candidate Pipeline Endpoints

Manages candidate queuing from LinkedIn URLs with deduplication.
"""
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.candidate import Candidate
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.models.consent import ConsentRecord
from fastapi import Request

router = APIRouter(prefix="/linkedin-candidate-pipeline", tags=["LinkedIn Pipeline"])

class LinkedInQueueRequest(BaseModel):
    linkedin_url: str

class LinkedInImportRequest(BaseModel):
    linkedin_url: str
    phone_number: Optional[str] = None

class LinkedInPipelineItemResponse(BaseModel):
    id: str
    linkedin_url: str
    linkedin_profile_slug: str
    status: str
    phone_number: Optional[str]
    candidate_id: Optional[str]
    created_at: str
    updated_at: str
    notes: Optional[str]

    class Config:
        from_attributes = True

def parse_linkedin_url(linkedin_url: str) -> str:
    """Extract profile slug from LinkedIn URL."""
    # Match /in/profile-slug pattern
    match = re.search(r'/in/([a-z0-9-]+)', linkedin_url.lower())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LinkedIn URL format. Expected: https://linkedin.com/in/profile-slug"
        )
    return match.group(1)

@router.post("/queue")
async def queue_linkedin_candidate(
    request: LinkedInQueueRequest,
    db: Session = Depends(get_db),
    current_user_id: str = "system"  # In production, get from auth
):
    """
    Queue a LinkedIn candidate for manual outreach.

    Deduplication:
    1. Check if candidate already exists in candidates table
    2. Check if already in linkedin_candidate_pipeline queue
    3. Only create new record if both checks pass
    """
    linkedin_url = request.linkedin_url
    profile_slug = parse_linkedin_url(linkedin_url)

    # Query 1: Check if candidate already exists
    existing_candidate = db.query(Candidate).filter(
        Candidate.candidate_linkedin_url == linkedin_url
    ).first()

    if existing_candidate:
        return {
            "status": "ALREADY_EXISTS",
            "message": f"Candidate already in system",
            "candidate": {
                "id": str(existing_candidate.candidateID),
                "name": existing_candidate.candidateName,
                "email": existing_candidate.candidateEmail,
                "phone": existing_candidate.candidateMobileNumber,
                "status": existing_candidate.candidateStatus,
                "source": existing_candidate.candidate_source,
                "linkedin_url": existing_candidate.candidate_linkedin_url
            }
        }

    # Query 2: Check if already in pipeline
    existing_pipeline = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.linkedin_url == linkedin_url
    ).first()

    if existing_pipeline:
        return {
            "status": "ALREADY_QUEUED",
            "message": f"Already in your LinkedIn queue",
            "pipeline_item": {
                "id": str(existing_pipeline.id),
                "status": existing_pipeline.status,
                "created_at": existing_pipeline.created_at.isoformat(),
                "updated_at": existing_pipeline.updated_at.isoformat(),
                "notes": existing_pipeline.notes
            }
        }

    # Query 3: All checks passed - create new pipeline record
    pipeline_item = LinkedInCandidatePipeline(
        linkedin_url=linkedin_url,
        linkedin_profile_slug=profile_slug,
        status=LinkedInPipelineStatus.PENDING_CONNECTION,
        assigned_to_user_id=current_user_id,
        created_by_user_id=current_user_id
    )
    db.add(pipeline_item)
    db.commit()
    db.refresh(pipeline_item)

    return {
        "status": "QUEUED",
        "message": "Added to your LinkedIn pipeline",
        "pipeline_item_id": str(pipeline_item.id),
        "profile_slug": profile_slug
    }

@router.get("/list")
async def list_pipeline_items(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user_id: str = "system"
):
    """List LinkedIn pipeline items for current user."""
    query = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.assigned_to_user_id == current_user_id
    )

    if status_filter:
        query = query.filter(LinkedInCandidatePipeline.status == status_filter)

    items = query.order_by(LinkedInCandidatePipeline.created_at.desc()).all()

    return {
        "count": len(items),
        "items": [
            {
                "id": str(item.id),
                "linkedin_url": item.linkedin_url,
                "linkedin_profile_slug": item.linkedin_profile_slug,
                "status": item.status.value,
                "phone_number": item.phone_number,
                "candidate_id": str(item.candidate_id) if item.candidate_id else None,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "notes": item.notes
            }
            for item in items
        ]
    }

@router.post("/{pipeline_id}/complete-import")
async def complete_linkedin_import(
    pipeline_id: str,
    request: LinkedInImportRequest,
    db: Session = Depends(get_db),
    current_user_id: str = "system"
):
    """
    Complete LinkedIn import: Add phone number and create candidate.

    Workflow:
    1. Get pipeline record
    2. Create Candidate record with phone + linkedin_url
    3. Record WhatsApp consent
    4. Update pipeline status to IMPORTED_TO_THUNDER
    """
    # Get pipeline record
    pipeline_item = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.id == pipeline_id
    ).first()

    if not pipeline_item:
        raise HTTPException(status_code=404, detail="Pipeline item not found")

    # Parse URL to get profile info
    profile_slug = parse_linkedin_url(request.linkedin_url)

    # Create Candidate record
    candidate = Candidate(
        candidateID=str(uuid4()),
        candidateName=profile_slug.replace("-", " ").title(),  # Convert slug to name
        candidateMobileNumber=request.phone_number,
        candidate_linkedin_url=request.linkedin_url,
        candidate_source="linkedin_import",
        candidateStatus="NEW"
    )
    db.add(candidate)
    db.flush()  # Get the ID before commit

    # Record WhatsApp consent
    consent = ConsentRecord(
        subject_id=candidate.candidateID,
        consent_type="whatsapp_outreach",
        consent_given=True,
        created_at=datetime.utcnow()
    )
    db.add(consent)

    # Update pipeline
    pipeline_item.status = LinkedInPipelineStatus.IMPORTED_TO_THUNDER
    pipeline_item.phone_number = request.phone_number
    pipeline_item.candidate_id = candidate.candidateID
    pipeline_item.imported_at = datetime.utcnow()
    pipeline_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(candidate)

    return {
        "status": "SUCCESS",
        "message": "Candidate imported and ready for Thunder autonomous outreach",
        "candidate_id": str(candidate.candidateID),
        "phone": request.phone_number,
        "linkedin_url": request.linkedin_url,
        "pipeline_id": str(pipeline_item.id)
    }

@router.get("/dashboard/activity")
async def get_linkedin_activity_for_dashboard(
    db: Session = Depends(get_db),
    current_user_id: str = "system"
):
    """
    Get LinkedIn activity for dashboard display.

    Returns detailed view with all pipeline candidates and their status.
    Includes: candidate name, URL, assigned recruiter, days in pipeline,
    status, and pending actions.
    """

    query = db.query(LinkedInCandidatePipeline).order_by(
        LinkedInCandidatePipeline.created_at.desc()
    ).all()

    items = []
    for item in query:
        days_in_pipeline = (datetime.utcnow() - item.created_at).days if item.created_at else 0

        # Determine pending action based on status
        pending_action = {
            "PENDING_CONNECTION": "Send LinkedIn Connection Request",
            "CONNECTED": "Collect Phone Number",
            "PHONE_COLLECTED": "Import to Thunder",
            "IMPORTED_TO_THUNDER": "Monitor Engagement"
        }.get(item.status, "Unknown")

        items.append({
            "id": str(item.id),
            "candidate_name": item.linkedin_profile_slug.replace("-", " ").title(),
            "linkedin_url": item.linkedin_url,
            "assigned_to": "Unassigned" if not item.assigned_to_user_id else str(item.assigned_to_user_id),
            "days_in_pipeline": days_in_pipeline,
            "status": item.status.value if item.status else "Unknown",
            "phone_number": item.phone_number,
            "pending_action": pending_action,
            "notes": item.notes,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None
        })

    return {
        "count": len(items),
        "items": items
    }

@router.put("/{pipeline_id}/status")
async def update_pipeline_status(
    pipeline_id: str,
    status: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update pipeline item status and notes."""
    pipeline_item = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.id == pipeline_id
    ).first()

    if not pipeline_item:
        raise HTTPException(status_code=404, detail="Pipeline item not found")

    pipeline_item.status = status
    if notes:
        pipeline_item.notes = notes
    pipeline_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pipeline_item)

    return {
        "id": str(pipeline_item.id),
        "status": pipeline_item.status.value,
        "updated_at": pipeline_item.updated_at.isoformat()
    }
