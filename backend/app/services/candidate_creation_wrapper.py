"""
Unified Candidate Creation Wrapper
===================================
ALL candidate creation must flow through this module.
No direct calls to create_candidate() or database inserts.

Enforces:
- Message queue for async processing
- Idempotency (no duplicates via idempotency_key)
- Tenant context (multi-tenant support)
- Audit trail (created_by tracking)
- Standardized response format
"""

from typing import Dict, Any, Optional
from uuid import uuid4
import logging
from sqlalchemy.orm import Session

from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)


def queue_candidate_creation(
    db: Session,
    email: str,
    first_name: str,
    last_name: str,
    *,
    tenant_id: Optional[int] = None,
    source: str = "unknown",
    mobile: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    job_id: Optional[str] = None,
    resume_data: Optional[dict] = None,
    education: Optional[list] = None,
    experience: Optional[list] = None,
    certifications: Optional[list] = None,
    created_by_user_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    **extra_fields
) -> Dict[str, Any]:
    """
    UNIFIED entry point for ALL candidate creation across all services.

    Queues candidate creation for async processing instead of synchronous creation.
    Returns message_id immediately for polling progress.

    Args:
        db: Database session (required for duplicate checks)
        email: Candidate email (REQUIRED)
        first_name: Candidate first name (REQUIRED)
        last_name: Candidate last name (REQUIRED)
        tenant_id: Tenant context (default: 1 for BlitzenX)
        source: Where creation came from (bulk_csv, linkedin_fast, web_chat, etc.)
        mobile: Phone number (optional)
        linkedin_url: LinkedIn profile URL (optional, for dedup)
        job_id: Job application context (optional)
        resume_data: Parsed resume data (optional)
        education: Education history (optional)
        experience: Work experience (optional)
        certifications: Certifications (optional)
        created_by_user_id: User who initiated (for audit trail)
        candidate_id: Pre-generated candidate ID (optional, usually auto-generated)
        **extra_fields: Additional fields to pass through payload

    Returns:
        {
            'status': 'queued',
            'message_id': str,  # Use for polling: /api/v1/message-queue/tasks/{message_id}/status
            'task_id': str,
            'queue_item_id': str,
            'polling_endpoint': str,
            'polling_interval_seconds': int
        }

    Raises:
        ValueError: Validation errors (missing required fields)
        RuntimeError: Queue service failures
    """
    # Validation
    if not email:
        raise ValueError("Email is required for candidate creation")
    if not first_name:
        raise ValueError("First name is required for candidate creation")
    if not last_name:
        raise ValueError("Last name is required for candidate creation")

    # Generate task_id for this queue operation
    task_id = candidate_id or str(uuid4())

    # Build complete payload for async handler
    payload = {
        # Core fields
        'candidate_email': email.lower().strip(),
        'candidate_first_name': first_name.strip(),
        'candidate_last_name': last_name.strip(),

        # Optional fields
        'candidate_mobile': mobile,
        'candidate_source': source,
        'linkedin_url': linkedin_url,
        'job_id': job_id,
        'tenant_id': tenant_id,
        'created_by_user_id': created_by_user_id,

        # Resume/education data
        'resume_data': resume_data,
        'education': education,
        'experience': experience,
        'certifications': certifications,

        # Any additional fields from caller
        **extra_fields
    }

    # Idempotency key prevents duplicate processing
    # Format: candidate_create:{email}:{tenant_id}:{source}
    idempotency_key = f"candidate_create:{email.lower().strip()}:{tenant_id}:{source}"

    logger.info(
        f"[CandidateCreationWrapper] Queueing candidate: {email} "
        f"({first_name} {last_name}), source={source}, tenant={tenant_id}"
    )

    # Enqueue to MessageQueueService
    try:
        enqueue_result = MessageQueueService.enqueue(
            task_name='create_candidate',
            task_id=task_id,
            data=payload,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
        )
    except Exception as e:
        logger.error(f"[CandidateCreationWrapper] Failed to queue: {e}", exc_info=True)
        raise RuntimeError(f"Failed to queue candidate creation: {str(e)}")

    if not enqueue_result or 'message_id' not in enqueue_result:
        raise RuntimeError("Queue service failed to return message_id")

    message_id = enqueue_result['message_id']

    logger.info(
        f"[CandidateCreationWrapper] ✅ Queued successfully: "
        f"message_id={message_id}, idempotency_key={idempotency_key}"
    )

    return {
        'status': 'queued',
        'message_id': message_id,
        'task_id': task_id,
        'queue_item_id': enqueue_result.get('queue_item_id', message_id),
        'polling_endpoint': f'/api/v1/message-queue/tasks/{message_id}/status',
        'polling_interval_seconds': 2
    }
