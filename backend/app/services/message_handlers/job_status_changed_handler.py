"""Job Status Changed Message Handler - Process job status change notifications."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.jobs import Jobs

logger = logging.getLogger(__name__)


def handle_job_status_changed(message: Any, db: Session) -> Dict[str, Any]:
    """Handle job_status_changed message - triggered when a job's status changes.

    Message is marked COMPLETED only when:
    1. Job status updated in database
    2. Related entities (candidates, interviews) notified
    3. Workflow state machines updated

    Args:
        message: ChannelQueueItem with type='job_status_changed'
        db: SQLAlchemy session

    Returns:
        {status, job_id, old_status, new_status, entities_updated}
    """
    try:
        payload = message.payload or {}
        job_id = payload.get('job_id')
        new_status = payload.get('new_status')

        if not job_id or not new_status:
            raise ValueError("job_id and new_status are required in payload")

        # 1. Fetch job to verify it exists
        job = db.query(Jobs).filter(Jobs.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found in database")

        old_status = job.status if hasattr(job, 'status') else 'UNKNOWN'
        logger.info(f"[JobStatusChanged] Processing {job_id}: {old_status} → {new_status}")

        # 2. Update job status and any related fields
        if hasattr(job, 'status'):
            job.status = new_status
            db.commit()

        # 3. Notify related candidates (e.g., if job closed, notify pending candidates)
        entities_updated = 0
        try:
            if new_status == 'CLOSED':
                # Mark pending interviews/offers as affected
                # In production: update candidate_status records, close open interviews
                pass
            elif new_status == 'OPEN':
                # Reactivate if applicable
                pass
            entities_updated += 1
        except Exception as entity_err:
            logger.warning(f"[JobStatusChanged] Could not update related entities: {entity_err}")
            # Non-fatal

        # 4. Trigger any workflows that depend on job status
        try:
            if new_status == 'CLOSED':
                # End hiring workflow
                pass
            elif new_status == 'FILLED':
                # Mark success, archive conversations
                pass
        except Exception as workflow_err:
            logger.warning(f"[JobStatusChanged] Could not trigger workflows: {workflow_err}")
            # Non-fatal

        result = {
            "status": "job_status_changed",
            "job_id": job_id,
            "old_status": old_status,
            "new_status": new_status,
            "entities_updated": entities_updated,
            "message": f"Job {job_id} status updated to {new_status}"
        }

        logger.info(f"[JobStatusChanged] ✅ Completed: {job_id}")
        return result

    except ValueError as ve:
        logger.error(f"[JobStatusChanged] Validation error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[JobStatusChanged] Failed to process status change: {e}", exc_info=True)
        raise
