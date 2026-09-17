"""
Create Candidate Endpoint - Queue-Driven (Async via Thunder)
=============================================================
This endpoint is registered FIRST in routes.py so the POST /create route 
matches before the general candidates/{id} route.

Workflow:
1. Validate candidate data
2. Queue async task to Thunder
3. Return message_id for polling task status
4. Thunder handler processes: SLM analysis → email delivery
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.services.message_queue_service import MessageQueueService
from app.utils.uniq_id_generator import candidate_id_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])


class CreateCandidateRequest(BaseModel):
    """Request to create a new candidate (queued for async processing)"""
    email: Optional[str] = None
    candidate_email: Optional[str] = None
    first_name: Optional[str] = None
    candidate_first_name: Optional[str] = None
    last_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    mobile: Optional[str] = None
    candidate_mobile: Optional[str] = None
    gender: Optional[str] = None
    candidate_gender: Optional[str] = None
    current_location: Optional[str] = None
    candidate_current_location: Optional[str] = None
    source: Optional[str] = "form_submission"
    candidate_source: Optional[str] = None
    resume_data: Optional[dict] = None
    education: Optional[list] = None
    experience: Optional[list] = None
    certifications: Optional[list] = None

    class Config:
        populate_by_name = True

    def get_email(self):
        return self.email or self.candidate_email

    def get_first_name(self):
        return self.first_name or self.candidate_first_name

    def get_last_name(self):
        return self.last_name or self.candidate_last_name

    def get_mobile(self):
        return self.mobile or self.candidate_mobile

    def get_gender(self):
        return self.gender or self.candidate_gender

    def get_current_location(self):
        return self.current_location or self.candidate_current_location

    def get_source(self):
        return self.candidate_source or self.source or "form_submission"


class CreateCandidateResponse(BaseModel):
    """Response for candidate creation request"""
    status: str
    message_id: str
    polling_endpoint: str
    polling_interval_seconds: int


@router.post(
    "",
    response_model=CreateCandidateResponse,
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
)
async def create_candidate(
    request: CreateCandidateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Queue candidate creation for async processing via Thunder.

    This endpoint does NOT create the candidate synchronously.
    It queues the request and returns a polling endpoint to check status.

    Workflow:
    1. Validate required fields (email, first_name, last_name)
    2. Generate candidate ID
    3. Queue 'create_candidate' task to Thunder
    4. Return message_id for polling

    Thunder async task will:
    1. Create Candidate record in database
    2. Trigger SLM for candidate analysis
    3. SLM instructs Thunder on email delivery
    4. Thunder sends welcome email

    Args:
        request: CreateCandidateRequest with candidate data
        db: Database session
        current_user: Authenticated user making the request

    Returns:
        CreateCandidateResponse with:
        - status: 'queued'
        - message_id: UUID for polling
        - polling_endpoint: URL to check status
        - polling_interval_seconds: Recommended interval

    Raises:
        HTTPException 400: Missing required fields (email, first_name, last_name)
        HTTPException 500: Failed to queue task
    """
    try:
        email = request.get_email()
        first_name = request.get_first_name()
        last_name = request.get_last_name()
        mobile = request.get_mobile()
        gender = request.get_gender()
        current_location = request.get_current_location()
        source = request.get_source()

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        if not first_name:
            raise HTTPException(status_code=400, detail="First name is required")
        if not last_name:
            raise HTTPException(status_code=400, detail="Last name is required")

        logger.info(f"[CANDIDATE_CREATE] Queueing candidate: {email} ({first_name} {last_name})")

        candidate_id = candidate_id_generator()

        payload = {
            "candidate_id": candidate_id,
            "candidate_email": email,
            "candidate_first_name": first_name,
            "candidate_last_name": last_name,
            "candidate_mobile": mobile,
            "candidate_gender": gender,
            "candidate_current_location": current_location,
            "candidate_source": source,
            "resume_data": request.resume_data,
            "education": request.education,
            "experience": request.experience,
            "certifications": request.certifications,
            "created_by_user_id": getattr(current_user, 'UserID', None),
            "tenant_id": getattr(current_user, 'tenant_id', 1),
        }

        enqueue_result = MessageQueueService.enqueue(
            task_name='create_candidate',
            task_id=candidate_id,
            data=payload,
        )

        message_id = enqueue_result.get('message_id', candidate_id)
        logger.info(f"[CANDIDATE_CREATE] Queued: candidate_id={candidate_id}, message_id={message_id}")

        return CreateCandidateResponse(
            status="queued",
            message_id=message_id,
            polling_endpoint=f"/api/v1/message-queue/status/{message_id}",
            polling_interval_seconds=2,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CANDIDATE_CREATE] Error queuing candidate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue candidate creation: {str(e)}")
