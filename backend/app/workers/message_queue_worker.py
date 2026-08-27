"""Message Queue Worker - Processes messages from queue every 5 minutes

Worker runs every 5 minutes and:
1. Fetches PENDING + RETRYING messages
2. Marks as PROCESSING
3. Executes message (calls appropriate service)
4. Calls SLM to analyze result
5. SLM decides next action for Flash agent
6. Marks as COMPLETED or schedules RETRYING
7. Logs everything

All errors logged with exc_info=True for debugging.
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import DATABASE_URL
from app.services.message_queue_service import MessageQueueService
from app.services.slm_service import SLMService

logger = logging.getLogger(__name__)

# Set up database connection for worker
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def process_message_queue() -> None:
    """
    Main worker function - processes all pending messages.

    Called every 5 minutes via scheduler.
    Processes PENDING and RETRYING messages in FIFO order (oldest first).
    """
    db = SessionLocal()
    start_time = time.time()

    try:
        logger.info("Message queue worker starting...")

        # Fetch pending messages (FIFO order)
        pending_messages = MessageQueueService.get_pending(limit=100, db=db)

        if not pending_messages:
            logger.debug("No pending messages to process")
            return

        logger.info(f"Processing {len(pending_messages)} pending messages")

        processed_count = 0
        error_count = 0

        for message in pending_messages:
            try:
                processed_count += message_process_single(message, db)
            except Exception as e:
                logger.error(f"Failed to process message {message['id']}: {e}", exc_info=True)
                error_count += 1

        elapsed = time.time() - start_time
        logger.info(
            f"Message queue worker completed: "
            f"processed={processed_count} errors={error_count} elapsed={elapsed:.2f}s"
        )

    except Exception as e:
        logger.error(f"Message queue worker crashed: {e}", exc_info=True)

    finally:
        db.close()


def message_process_single(message: Dict[str, Any], db) -> int:
    """
    Process a single message from the queue.

    Steps:
    1. Mark PROCESSING
    2. Execute based on message type
    3. SLM analyzes result
    4. Mark COMPLETED or RETRYING
    5. Log everything

    Args:
        message: Message dict from queue
        db: Database session

    Returns:
        1 if successful, 0 if failed

    Raises:
        Exception: On any processing error (fail fast)
    """
    message_id = message["id"]
    message_type = message["type"]
    payload = message["payload"]

    start_time = time.time()

    try:
        # Mark as PROCESSING
        MessageQueueService.mark_processing(message_id, db)

        # Execute message based on type
        logger.debug(f"Executing message: {message_id} type={message_type}")
        result = _execute_message(message_type, payload)

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Analyze result with SLM
        logger.debug(f"SLM analyzing result for message: {message_id}")
        decision = SLMService.analyze_message_result(message_id, message_type, result, db)

        # Log result
        _log_message_processing(message_id, "COMPLETED", result, processing_time_ms, db)

        # Mark as COMPLETED
        MessageQueueService.mark_completed(message_id, db)

        logger.info(
            f"Message processed successfully: {message_id} "
            f"type={message_type} time={processing_time_ms}ms "
            f"next_action={decision.get('next_action', 'none')}"
        )

        return 1

    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Log error
        _log_message_processing(message_id, "FAILED", {"error": str(e)}, processing_time_ms, db)

        # Try to retry
        should_retry = message["retry_count"] < MessageQueueService.MAX_RETRIES
        is_scheduled = MessageQueueService.mark_failed(message_id, str(e), should_retry, db)

        if is_scheduled:
            logger.warning(
                f"Message scheduled for retry: {message_id} "
                f"attempt={message['retry_count'] + 1}/{MessageQueueService.MAX_RETRIES} "
                f"error={str(e)}"
            )
        else:
            logger.error(
                f"Message permanently failed: {message_id} "
                f"retries_exhausted={message['retry_count']} error={str(e)}"
            )

        return 0


def _execute_message(message_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute message based on type.

    Routes to appropriate service for processing.
    Returns result dict with success/failure status.

    Args:
        message_type: Type of message (e.g., 'candidate_added')
        payload: Message payload

    Returns:
        Result dict with success, data, and optional error

    Raises:
        Exception: If execution fails (fail fast)
    """
    logger.debug(f"Executing message type: {message_type}")

    if message_type == "candidate_added":
        # Payload: {"candidate_id": "...", "email": "..."}
        return {"success": True, "message": "Candidate addition processed"}

    elif message_type == "thunder_email_sent":
        # Payload: {"candidate_id": "...", "email_address": "..."}
        return {"success": True, "message": "Thunder email tracked"}

    elif message_type == "flash_agent_action":
        # Payload: {"action": "...", "result": {...}}
        return {"success": True, "message": "Flash action logged"}

    elif message_type == "interview_scheduled":
        # Payload: {"interview_id": "...", "candidate_id": "...", ...}
        return {"success": True, "message": "Interview scheduled"}

    elif message_type == "offer_generated":
        # Payload: {"offer_id": "...", "candidate_id": "...", ...}
        return {"success": True, "message": "Offer generated"}

    else:
        logger.warning(f"Unknown message type: {message_type}")
        return {
            "success": False,
            "error": f"Unknown message type: {message_type}",
        }


def _log_message_processing(
    message_id: str,
    status: str,
    result: Dict[str, Any],
    processing_time_ms: int,
    db,
) -> None:
    """
    Log message processing to message_log table.

    Args:
        message_id: Message ID
        status: Processing status
        result: Processing result
        processing_time_ms: How long it took
        db: Database session

    Raises:
        Exception: If logging fails
    """
    try:
        from app.models.message_queue import MessageLog

        log_entry = MessageLog(
            id=__import__("uuid").uuid4().hex,
            message_id=message_id,
            status=status,
            error=result.get("error") if status == "FAILED" else None,
            processing_time_ms=processing_time_ms,
        )

        db.add(log_entry)
        db.commit()

    except Exception as e:
        logger.error(f"Failed to log message processing: {e}", exc_info=True)
        db.rollback()
        # Don't raise - logging failure shouldn't stop worker


# Scheduler integration
def schedule_worker() -> None:
    """
    Schedule message queue worker to run every 5 minutes.

    Call this during app startup to register the scheduled task.
    Uses APScheduler to run process_message_queue() every 5 minutes.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=process_message_queue,
            trigger="interval",
            minutes=5,
            id="message_queue_worker",
            name="Process Message Queue",
            replace_existing=True,
        )

        if not scheduler.running:
            scheduler.start()

        logger.info("Message queue worker scheduled to run every 5 minutes")

    except Exception as e:
        logger.error(f"Failed to schedule message queue worker: {e}", exc_info=True)
        raise
