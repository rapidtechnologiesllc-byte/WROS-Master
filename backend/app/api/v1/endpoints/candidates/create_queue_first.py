"""Queue-first candidate creation endpoint.

New architecture (2026-09-05):
- Endpoint queues candidate creation request only
- CandidateQueueProcessor handles all DB operations
- Clean separation of concerns
- Proper error handling (500 if queue fails, not 200 lie)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.services.message_queue_service import MessageQueueService
from app.core.dependencies import require_resource_permission
from app.schemas.candidate import CandidateCreateRequest, CandidateCreateResponse
from app.utils.uniq_id_generator import generate_password

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


@router.post(
    "/create",
    response_model=CandidateCreateResponse,
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
)
def create_candidate(
    request: CandidateCreateRequest,
    db: Session = Depends(get_db),
):
    """Queue candidate for creation via async processor.

    Flow:
    1. Validate request + generate password
    2. Queue 'create_candidate' message with all candidate data
    3. Return message_id as tracking ID
    4. CandidateQueueProcessor picks up message
    5. CandidateCreationHandler creates candidate in DB
    6. Then queues to THUNDER_QUEUE for processing

    Args:
        request: CandidateCreateRequest with all candidate details
        db: Database session (for validation only)

    Returns:
        CandidateCreateResponse with message_id (queue tracking ID)

    Raises:
        HTTPException(400): If validation fails
        HTTPException(500): If queue fails
    """
    # Validate location is required
    if not request.candidate_current_location or not request.candidate_current_location.strip():
        raise HTTPException(
            status_code=400,
            detail="Location (City, State, Country) is mandatory for candidate creation"
        )

    # Validate email format
    if not request.candidate_email or "@" not in request.candidate_email:
        raise HTTPException(
            status_code=400,
            detail="Valid email address is required"
        )

    # Generate password for candidate (will be sent later)
    password = generate_password()

    # Queue candidate creation request
    # CandidateQueueProcessor will handle:
    # 1. Duplicate detection (email/phone)
    # 2. Candidate record creation in DB
    # 3. Status + info record creation
    # 4. Queueing to Thunder for processing
    try:
        logger.info(f"Queueing candidate creation: {request.candidate_email}")
        result = MessageQueueService.enqueue(
            task_name='create_candidate',
            data={
                'candidate_email': request.candidate_email,
                'candidate_first_name': request.candidate_first_name,
                'candidate_middle_name': request.candidate_middle_name,
                'candidate_last_name': request.candidate_last_name,
                'candidate_mobile': request.candidate_mobile,
                'candidate_current_location': request.candidate_current_location,
                'candidate_gender': request.candidate_gender,
                'candidate_date_of_birth': request.candidate_date_of_birth,
                'candidate_source': request.candidate_source,
                'candidate_experience': request.candidate_experience,
                'candidate_skills': request.candidate_skills,
                'candidate_joining_date': request.candidate_joining_date,
                'candidate_expected_salary': request.candidate_expected_salary,
                'candidate_current_salary': request.candidate_current_salary,
                'candidate_role': request.candidate_role,
                'candidate_employee_type': request.candidate_employee_type,
                'candidate_job_title': request.candidate_job_title,
                'education_records': request.education_records,
                'experience_records': request.experience_records,
                'password': password,
            }
        )

        if not result or result.get('status') != 'queued':
            logger.error(f"Failed to queue candidate creation: {result}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to queue candidate for creation")

        message_id = result.get('message_id')
        logger.info(f"Candidate creation queued successfully: message_id={message_id}, email={request.candidate_email}")

        # Return success with message ID as tracking ID
        # Candidate will be created asynchronously by CandidateQueueProcessor
        return CandidateCreateResponse(
            candidate_id=message_id,
            candidate_is_first_time=True,
            candidate_password=password
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue candidate creation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to queue candidate for creation. Please try again."
        )
