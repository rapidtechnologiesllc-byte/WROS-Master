"""LinkedIn candidate import task - async processing via Celery."""
import logging
from app.celery_app import app
from app.services.linkedin_import_service import (
    import_linkedin_candidate,
    InvalidLinkedInURL,
    ApolloCandidateNotFound,
    CandidateNotOpenToWork,
    DuplicateCandidateExists
)
from app.services.message_queue_service import MessageQueueService
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@app.task(
    name='import_linkedin_candidate',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def import_linkedin_candidate_task(
    self,
    linkedin_url: str,
    tenant_id: int = 1
):
    """
    Process LinkedIn candidate import asynchronously.

    This task:
    1. Validates LinkedIn URL
    2. Calls Apollo API for candidate enrichment
    3. Checks for duplicates
    4. Creates candidate in database
    5. Queues to Thunder for autonomous processing

    Args:
        linkedin_url: Full or short LinkedIn URL
        tenant_id: Tenant ID for multi-tenancy (default: 1)

    Returns:
        dict with status, candidate_id, and queued_to_thunder flag

    Raises:
        InvalidLinkedInURL: If URL format invalid
        ApolloCandidateNotFound: If Apollo can't find candidate
        CandidateNotOpenToWork: If candidate not marked open to work
        DuplicateCandidateExists: If candidate already in system
    """
    db = SessionLocal()

    try:
        logger.info(
            f"[LINKEDIN_IMPORT] Starting import for: {linkedin_url}",
            extra={"task_id": self.request.id}
        )

        # Step 1: Import candidate using LinkedIn/Apollo integration
        # This handles:
        # - URL validation and normalization
        # - Apollo API enrichment
        # - Resume parsing (if available)
        # - Duplicate detection (email/phone)
        # - Candidate record creation in DB
        candidate = import_linkedin_candidate(linkedin_url, db, tenant_id)

        if not candidate:
            raise RuntimeError("Candidate creation returned None")

        logger.info(
            f"[LINKEDIN_IMPORT] Candidate created: {candidate.candidateID}",
            extra={"task_id": self.request.id, "candidate_id": candidate.candidateID}
        )

        # Step 2: Queue to Thunder for autonomous processing
        # Thunder will:
        # - Assign to autonomous flow
        # - Screen candidate
        # - Schedule interviews
        # - Move through hiring pipeline
        try:
            thunder_result = MessageQueueService.enqueue(
                task_name='process_candidate',
                data={
                    'candidate_id': candidate.candidateID,
                    'tenant_id': tenant_id,
                    'source': 'linkedin_import'
                }
            )

            logger.info(
                f"[LINKEDIN_IMPORT] Queued to Thunder: {thunder_result.get('message_id')}",
                extra={"task_id": self.request.id}
            )

        except Exception as thunder_error:
            # Candidate created but Thunder queueing failed
            logger.error(
                f"[LINKEDIN_IMPORT] Failed to queue to Thunder: {thunder_error}",
                exc_info=True,
                extra={"task_id": self.request.id}
            )
            # Don't fail - candidate is created, just not in Thunder queue
            # Thunder will pick it up on next scan

        return {
            'status': 'success',
            'candidate_id': candidate.candidateID,
            'candidate_email': candidate.candidateEmail,
            'candidate_name': f"{candidate.candidateFirstName} {candidate.candidateLastName}".strip(),
            'queued_to_thunder': True,
            'task_id': self.request.id
        }

    except InvalidLinkedInURL as e:
        logger.warning(
            f"[LINKEDIN_IMPORT] Invalid LinkedIn URL: {linkedin_url}",
            extra={"task_id": self.request.id, "error": str(e)}
        )
        raise

    except ApolloCandidateNotFound as e:
        logger.warning(
            f"[LINKEDIN_IMPORT] Apollo couldn't enrich: {linkedin_url}",
            extra={"task_id": self.request.id, "error": str(e)}
        )
        raise

    except CandidateNotOpenToWork as e:
        logger.info(
            f"[LINKEDIN_IMPORT] Candidate not open to work (expected): {linkedin_url}",
            extra={"task_id": self.request.id}
        )
        raise

    except DuplicateCandidateExists as e:
        logger.info(
            f"[LINKEDIN_IMPORT] Duplicate candidate (expected): {linkedin_url}",
            extra={"task_id": self.request.id, "error": str(e)}
        )
        raise

    except Exception as e:
        logger.error(
            f"[LINKEDIN_IMPORT] Failed to import: {str(e)}",
            exc_info=True,
            extra={"task_id": self.request.id}
        )

        # Retry with exponential backoff
        # Retry times: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        logger.warning(
            f"[LINKEDIN_IMPORT] Retrying in {countdown}s (attempt {self.request.retries + 1}/3)",
            extra={"task_id": self.request.id}
        )

        raise self.retry(exc=e, countdown=countdown)

    finally:
        try:
            if db:
                db.close()
        except Exception as close_error:
            logger.warning(
                f"[LINKEDIN_IMPORT] Failed to close database: {close_error}",
                extra={"task_id": self.request.id}
            )
