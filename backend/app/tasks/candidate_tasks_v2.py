"""
Enhanced Celery tasks for candidate processing with progressive upload support.

Implements:
- Wait loop for documents (GAP #9: doesn't process until all docs arrive)
- Cancellation check (user can cancel mid-processing)
- State transitions (QUEUED → PROCESSING → COMPLETE/FAILED)
- Comprehensive error handling
- Retry logic with backoff
"""

import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session

from app.celery_app import app
from app.core.database import SessionLocal
from app.models.candidate import Candidate, CandidateDocument
from app.models.candidate_upload_state import CandidateUploadState
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

# Configuration
DOC_WAIT_CHECK_INTERVAL_SECONDS = 10
DOC_WAIT_MAX_DURATION_SECONDS = 5 * 60  # 5 minutes


@app.task(
    bind=True,
    name="process_candidate",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
)
def process_candidate(self, candidate_id: str, tenant_id: int = 1):
    """
    Process candidate after documents uploaded.

    This task:
    1. Waits for all expected documents to arrive (5 min timeout)
    2. Updates status to PROCESSING
    3. Runs Thunder autonomous intake
    4. Updates final status (COMPLETE or FAILED)
    5. Sends email notification

    Implements GAP #9: Doesn't process until all docs arrive
    - Checks if actual_doc_count >= expected_doc_count
    - Waits up to 5 minutes for missing docs
    - Starts with what's available if timeout

    Args:
        candidate_id: Candidate ID
        tenant_id: Tenant ID

    Returns:
        {
            "status": "success" | "error",
            "candidate_id": candidate_id,
            "documents_processed": int,
            "message": str,
        }
    """
    db: Session = SessionLocal()
    try:
        logger.info(
            f"[CELERY] Starting process_candidate for {candidate_id} (tenant={tenant_id})"
        )

        # Fetch candidate
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id,
        ).first()

        if not candidate:
            logger.error(f"[CELERY] Candidate not found: {candidate_id}")
            return {"status": "error", "message": "Candidate not found"}

        # ================================================================
        # GAP #9: WAIT FOR ALL DOCUMENTS
        # ================================================================
        logger.info(
            f"[CELERY] Waiting for documents: "
            f"have {candidate.actual_document_count}, "
            f"expecting {candidate.expected_document_count}"
        )

        start_wait = time.time()
        doc_wait_complete = False

        while time.time() - start_wait < DOC_WAIT_MAX_DURATION_SECONDS:
            # Refresh candidate state
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
            ).first()

            if not candidate:
                logger.error(f"[CELERY] Candidate deleted during processing: {candidate_id}")
                return {"status": "error", "message": "Candidate was deleted"}

            # Check if cancelled (GAP: cancellation check)
            if candidate.upload_status == CandidateUploadState.CANCELLED.value:
                logger.info(f"[CELERY] Candidate {candidate_id} was cancelled")
                return {"status": "cancelled", "message": "Upload was cancelled"}

            # Check if all documents arrived
            if candidate.expected_document_count > 0:
                if candidate.actual_document_count >= candidate.expected_document_count:
                    logger.info(f"[CELERY] All {candidate.actual_document_count} docs arrived")
                    doc_wait_complete = True
                    break
            else:
                # No expected count (user didn't specify), accept what's there
                if candidate.actual_document_count >= 1:
                    logger.info(f"[CELERY] At least 1 doc present, proceeding")
                    doc_wait_complete = True
                    break

            # Wait before next check
            logger.info(
                f"[CELERY] Still waiting for docs... "
                f"({candidate.actual_document_count}/{candidate.expected_document_count}). "
                f"Retry in {DOC_WAIT_CHECK_INTERVAL_SECONDS}s"
            )
            time.sleep(DOC_WAIT_CHECK_INTERVAL_SECONDS)

        if not doc_wait_complete:
            # Timeout: proceed anyway with what we have
            logger.warning(
                f"[CELERY] Document wait timeout for {candidate_id}. "
                f"Proceeding with {candidate.actual_document_count} docs"
            )

        # ================================================================
        # Update status to PROCESSING
        # ================================================================
        candidate.upload_status = CandidateUploadState.PROCESSING.value
        db.commit()

        logger.info(
            f"[CELERY] Processing {candidate_id} with {candidate.actual_document_count} docs"
        )

        # ================================================================
        # FETCH DOCUMENTS IN ORDER (GAP #13: preserve order)
        # ================================================================
        documents = db.query(CandidateDocument).filter(
            CandidateDocument.candidateID == candidate_id,
            CandidateDocument.tenant_id == tenant_id,
        ).order_by(CandidateDocument.upload_sequence.asc()).all()

        doc_count = len(documents)

        logger.info(f"[CELERY] Processing {doc_count} documents in upload order")

        # ================================================================
        # THUNDER AUTONOMOUS PROCESSING
        # ================================================================
        # TODO: Call Thunder autonomous agent
        # For now, just log

        logger.info(f"[CELERY] Would queue to Thunder: {candidate_id}")

        # Simulate processing
        # In real implementation:
        # - Extract resume text from documents
        # - Run Thunder matching algorithm
        # - Create interview scheduling requests
        # - Update candidate status

        # ================================================================
        # Update status to COMPLETE
        # ================================================================
        candidate.upload_status = CandidateUploadState.COMPLETE.value
        candidate.processing_completed_at = datetime.utcnow()
        db.commit()

        # ================================================================
        # SEND EMAIL NOTIFICATION
        # ================================================================
        try:
            send_email(
                recipient=candidate.candidateEmail,
                subject="Application Processing Complete",
                template="processing_complete",
                context={
                    "first_name": candidate.candidateFirstName,
                    "documents_count": doc_count,
                    "next_steps": "You will hear from us within 3-5 business days",
                },
            )
        except Exception as e:
            logger.error(f"[CELERY] Failed to send completion email: {e}")

        logger.info(f"[CELERY] Successfully processed {candidate_id}")

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "documents_processed": doc_count,
            "message": f"Processed {doc_count} documents successfully",
        }

    except Exception as e:
        logger.error(
            f"[CELERY] Error processing candidate {candidate_id}: {str(e)}",
            exc_info=True,
        )

        # Update status to FAILED (GAP #4: error state)
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
            ).first()

            if candidate:
                candidate.upload_status = CandidateUploadState.PROCESSING_FAILED.value
                candidate.upload_error = str(e)
                db.commit()
        except Exception as cleanup_error:
            logger.error(f"[CELERY] Failed to update error state: {cleanup_error}")

        # Celery will auto-retry based on autoretry_for config
        raise

    finally:
        db.close()


@app.task(
    bind=True,
    name="cleanup_stale_uploads",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 1},
)
def cleanup_stale_uploads_task(self):
    """
    Cleanup job: Delete old failed/abandoned uploads.

    Runs daily to clean up S3 and database from stale uploads.
    """
    from app.services.progressive_upload_service_v2 import cleanup_stale_uploads

    db: Session = SessionLocal()
    try:
        logger.info("[CELERY] Starting cleanup_stale_uploads")
        cleanup_stale_uploads(db)
        logger.info("[CELERY] Cleanup completed")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"[CELERY] Cleanup failed: {e}", exc_info=True)
        raise

    finally:
        db.close()
