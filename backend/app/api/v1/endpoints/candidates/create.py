"""
Candidate Creation Endpoint - Queue-Based Pattern

Uses MessageQueue for idempotent, retryable candidate creation.
- Endpoint queues create_candidate message
- Returns message_id immediately
- Queue processor handles creation with 5 retries at 30-min intervals
- Client polls for candidate_id when creation completes
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.core.dependencies import get_current_user, get_db, require_resource_permission
from app.models.user import Users
from app.services.message_queue_service import MessageQueueService
from app.utils.uniq_id_generator import generate_password
from app.schemas.candidate import CandidateCreateRequest, CandidateCreateResponse

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.post(
    "/create",
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
    summary="Queue candidate creation",
    description="Queue a candidate creation request for processing with retries",
)
def create_candidate(
    request: CandidateCreateRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Queue candidate creation through message queue.

    Uses idempotent queue-based pattern with automatic retries:
    - 5 retry attempts over 30-minute intervals (6 min each)
    - Returns message_id immediately
    - Client polls GET /candidates/create-status/{message_id} for candidate_id

    Args:
        request: Candidate creation request with required fields
        current_user: Authenticated user making the request
        db: Database session

    Returns:
        {'message_id': str, 'status': 'pending', 'password': str}
        Client should poll with message_id to get candidate_id when ready

    Raises:
        HTTPException: If location not provided or request invalid
    """
    # Validate mandatory location field (required for candidate search)
    if not request.candidate_current_location or not request.candidate_current_location.strip():
        raise HTTPException(
            status_code=400,
            detail="Location (City, State, Country) is mandatory for candidate creation"
        )

    # Generate temporary password for candidate
    password = generate_password()
    message_id = str(uuid.uuid4())

    try:
        # Queue candidate creation message for async processing
        # Message goes to CANDIDATE_QUEUE for creation + DB persistence
        # Once complete (marked COMPLETED), Thunder processes candidate for autonomous engagement
        # Returns message_id for polling to get candidate_id when complete
        MessageQueueService.enqueue(
            message_type="create_candidate",
            queue_type="CANDIDATE_QUEUE",
            resource_id=message_id,
            created_by=current_user.UserID,
            db=db,
            payload={
                "message_id": message_id,
                "candidate_email": request.candidate_email,
                "candidate_mobile": request.candidate_mobile,
                "candidate_password": password,
                "candidate_role": request.candidate_role or "Candidate",
                "candidate_employee_type": request.candidate_employee_type,
                "candidate_job_title": request.candidate_job_title,
                "candidate_first_name": request.candidate_first_name,
                "candidate_last_name": request.candidate_last_name,
                "candidate_gender": request.candidate_gender,
                "candidate_date_of_birth": request.candidate_date_of_birth,
                "candidate_current_location": request.candidate_current_location,
                "created_by_user": current_user.UserID,
                "tenant_id": current_user.tenant_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Candidate creation queue error: {str(e)}"
        ) from e

    # Return message_id for client polling
    return {
        "message_id": message_id,
        "status": "pending",
        "password": password,
        "polling_endpoint": f"/candidates/create-status/{message_id}"
    }


@router.get(
    "/create-status/{message_id}",
    summary="Poll candidate creation status",
    description="Check status of queued candidate creation. Returns candidate_id when ready.",
    dependencies=[Depends(get_current_user)],
)
def get_candidate_creation_status(
    message_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Poll for candidate creation result.

    Statuses:
    - 'pending': Message queued, processing not started
    - 'processing': Message being processed, candidate being created
    - 'completed': Candidate created successfully, candidate_id available
    - 'failed': Creation failed after 5 retries, error in response
    - 'retrying': Failed attempt, scheduled for retry

    Args:
        message_id: Message ID from POST /candidates/create response
        db: Database session

    Returns:
        {'status': 'pending|processing|completed|failed|retrying', 'candidate_id'?: str, 'error'?: str}

    HTTP Status:
        - 200: Status retrieved (check response status field)
        - 404: Message not found
        - 500: Database error
    """
    from app.models.message_queue import MessageQueue

    try:
        message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()

        if not message:
            return {
                "status": "not_found",
                "error": f"Message {message_id} not found"
            }

        response = {
            "status": message.status.lower(),
            "message_id": message_id,
            "retry_count": message.retry_count,
        }

        # If completed, include candidate_id
        if message.status == "COMPLETED" and message.result:
            response["candidate_id"] = message.result.get("candidate_id")
            response["is_new"] = message.result.get("is_new")

        # If failed, include error
        if message.status == "FAILED":
            response["error"] = message.error

        # If retrying, include next retry time
        if message.status == "RETRYING" and message.next_retry_at:
            response["next_retry_at"] = message.next_retry_at.isoformat()

        return response

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to retrieve status: {str(e)}"
        }
