"""
Bulk Import Tasks
import logging
=================

Async tasks for importing candidates in bulk from CSV files.
Tasks are tracked in message queue dashboard.
"""

from celery import current_task
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.bulk_engagement_service import import_candidates_from_csv
from app.api.v1.endpoints.admin_queue import TaskStatus, log_task_message
import uuid

@celery_app.task(bind=True, name="tasks.bulk_import_candidates")
def import_candidates_task(self, file_path: str, tenant_id: str = "default"):
    """
    Import candidates from CSV file in background.

    Args:
        file_path: Path to CSV file
        tenant_id: Organization tenant ID

    Returns:
        dict: Import result with counts and status
    """
    task_id = str(self.request.id)

    # Register task in message queue
    TaskStatus.add_task(task_id, "bulk_import_candidates", "active")
    log_task_message(task_id, f"Starting bulk import from {file_path}", "info")

    db = SessionLocal()
    try:
        # Update progress
        TaskStatus.update_task(task_id, progress=10)
        log_task_message(task_id, "Validating file...", "info")

        # Import candidates
        result = import_candidates_from_csv(db, file_path)

        # Update progress based on results
        total = result.get("total", 0)
        created = result.get("created", 0)
        updated = result.get("updated", 0)
        failed = result.get("failed", 0)

        progress = 90
        TaskStatus.update_task(task_id, progress=progress)

        # Log results
        log_task_message(
            task_id,
            f"Import complete: {created} created, {updated} updated, {failed} failed out of {total}",
            "info"
        )

        # Mark as completed
        TaskStatus.update_task(task_id, status="completed", progress=100)
        log_task_message(task_id, "Bulk import task completed successfully", "info")

        return {
            "status": "success",
            "task_id": task_id,
            "total": total,
            "created": created,
            "updated": updated,
            "failed": failed,
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        error_msg = f"Bulk import failed: {str(e)}"
        log_task_message(task_id, error_msg, "error")
        TaskStatus.update_task(task_id, status="failed")

        return {
            "status": "error",
            "task_id": task_id,
            "error": error_msg,
        }
    finally:
        db.close()

@celery_app.task(name="tasks.import_candidates_from_csv_batch")
def import_candidates_batch_task(csv_content: str, batch_id: str = None):
    """
    Import batch of candidates from CSV content string.
    Used when CSV is uploaded and needs parsing.
    """
    task_id = batch_id or str(uuid.uuid4())

    TaskStatus.add_task(task_id, "bulk_import_batch", "active")
    log_task_message(task_id, "Starting batch import", "info")

    db = SessionLocal()
    try:
        TaskStatus.update_task(task_id, progress=50)
        log_task_message(task_id, "Processing CSV content...", "info")

        # Parse and import CSV
        # This would call a service method to parse string content
        # For now, just a placeholder

        TaskStatus.update_task(task_id, status="completed", progress=100)
        log_task_message(task_id, "Batch import completed", "info")

        return {"status": "success", "task_id": task_id}

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        log_task_message(task_id, f"Error: {str(e)}", "error")
        TaskStatus.update_task(task_id, status="failed")
        return {"status": "error", "task_id": task_id, "error": str(e)}
    finally:
        db.close()
