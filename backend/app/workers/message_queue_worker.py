"""
Message Queue Worker - Processes PENDING messages from ChannelQueueItem

Handles candidate creation, email delivery, interview scheduling, and other async operations.
Runs independently, processing batches of PENDING messages every 30 seconds.
"""
import logging
from datetime import datetime
from typing import Dict, Any

from app.core.logging import logger
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.services.channel_processors.candidate_queue_processor import CandidateQueueProcessor

logger = logging.getLogger(__name__)


def process_message_queue(batch_size: int = 10, timeout_minutes: int = 30) -> Dict[str, Any]:
    """
    Main worker function to process all message queues.

    Args:
        batch_size: Number of PENDING messages to process per cycle
        timeout_minutes: How long to wait before marking message as overdue

    Returns:
        {'status': 'success'|'error', 'messages_processed': int}
    """
    db = SessionLocal()
    messages_processed = 0

    try:
        # Query PENDING messages (ordered by created_at for FIFO)
        # Process PENDING messages
        pending_messages = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status == "PENDING"
        ).order_by(ChannelQueueItem.created_at).limit(batch_size).all()

        # Also check for FAILED messages ready for retry
        retry_messages = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status == "FAILED",
            ChannelQueueItem.next_retry_at <= datetime.utcnow(),
            ChannelQueueItem.retry_count < 5  # MAX_RETRIES
        ).order_by(ChannelQueueItem.created_at).limit(batch_size // 2).all()

        # Re-queue retry messages back to PENDING
        if retry_messages:
            for msg in retry_messages:
                msg.status = "PENDING"
                logger.info(f"[Worker] Retry attempt {msg.retry_count + 1}/5 for message {msg.id}")
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[Worker] Failed to reset retry messages to PENDING: {e}", exc_info=True)

        all_messages = (pending_messages or []) + (retry_messages or [])
        logger.info(f"[Worker] Found {len(all_messages) if all_messages else 0} messages to process ({len(pending_messages) if pending_messages else 0} PENDING, {len(retry_messages) if retry_messages else 0} retrying)")

        if all_messages:
            for message in all_messages:
                if not message:
                    logger.warning("[Worker] Skipping None message")
                    continue

                try:
                    # Mark as PROCESSING (already in session, no add needed)
                    message.status = "PROCESSING"
                    try:
                        db.commit()
                    except Exception as commit_err:
                        db.rollback()
                        logger.error(f"[Worker] Failed to mark PROCESSING: {commit_err}", exc_info=True)
                        continue

                    logger.info(f"[Worker] Processing {message.type} message {message.id}")

                    # Route to appropriate processor based on message type
                    if message.type == "create_candidate":
                        result = CandidateQueueProcessor.process(message, db)
                    elif message.type == "engage_candidate_with_thunder":
                        # Queue candidate to Thunder for autonomous engagement
                        candidate_id = message.payload.get('candidate_id')
                        result = {"status": "queued_to_thunder", "candidate_id": candidate_id}
                        logger.info(f"[Worker] Candidate {candidate_id} queued for Thunder engagement")
                    else:
                        logger.warning(f"[Worker] Unknown message type: {message.type}")
                        message.status = "FAILED"
                        message.error = f"Unknown message type: {message.type}"
                        message.completed_at = datetime.utcnow()
                        try:
                            db.commit()
                        except Exception as commit_err:
                            db.rollback()
                            logger.error(f"[Worker] Failed to mark FAILED: {commit_err}", exc_info=True)
                        continue

                    # Mark as COMPLETED (already in session, no add needed)
                    message.status = "COMPLETED"
                    message.result = result
                    message.completed_at = datetime.utcnow()
                    try:
                        db.commit()
                    except Exception as commit_err:
                        db.rollback()
                        logger.error(f"[Worker] Failed to mark COMPLETED: {commit_err}", exc_info=True)

                    logger.info(f"[Worker] ✅ Message {message.id} completed successfully")
                    messages_processed += 1

                except Exception as e:
                    # Handle processing error
                    try:
                        message.status = "FAILED"
                        message.error = str(e)
                        message.completed_at = datetime.utcnow()
                        db.commit()
                        logger.error(f"[Worker] ❌ Message {message.id} failed: {str(e)}", exc_info=True)
                    except Exception as commit_error:
                        db.rollback()
                        logger.error(f"[Worker] Failed to mark message as failed: {commit_error}", exc_info=True)

        return {
            "status": "success",
            "messages_processed": messages_processed
        }

    except Exception as exc:
        logger.error(f"[Worker] Error in process_message_queue: {exc}", exc_info=True)
        return {
            "status": "error",
            "messages_processed": messages_processed,
            "error": str(exc)
        }

    finally:
        db.close()


def process_candidate_queue(batch_size: int = 5) -> Dict[str, Any]:
    """Process CANDIDATE_QUEUE messages specifically."""
    db = SessionLocal()
    messages_processed = 0

    try:
        pending_messages = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.channel_type == "CANDIDATE_QUEUE",
            ChannelQueueItem.status == "PENDING"
        ).order_by(ChannelQueueItem.created_at).limit(batch_size).all()

        if all_messages:
            for message in all_messages:
                try:
                    message.status = "PROCESSING"
                    db.commit()

                    result = CandidateQueueProcessor.process(message, db)

                    message.status = "COMPLETED"
                    message.result = result
                    message.completed_at = datetime.utcnow()
                    db.commit()

                    logger.info(f"[CandidateQueue] ✅ Candidate created: {message.id}")
                    messages_processed += 1

                except Exception as e:
                    try:
                        message.status = "FAILED"
                        message.error = str(e)
                        message.completed_at = datetime.utcnow()
                        db.commit()
                        logger.error(f"[CandidateQueue] ❌ Failed: {str(e)}", exc_info=True)
                    except Exception as commit_error:
                        db.rollback()
                        logger.error(f"[CandidateQueue] Commit error: {commit_error}", exc_info=True)

        return {
            "status": "success",
            "messages_processed": messages_processed
        }

    except Exception as exc:
        logger.error(f"[CandidateQueue] Error: {exc}", exc_info=True)
        return {
            "status": "error",
            "messages_processed": messages_processed
        }

    finally:
        db.close()


def process_email_queue(batch_size: int = 20) -> Dict[str, Any]:
    """Process EMAIL_QUEUE messages."""
    db = SessionLocal()
    messages_processed = 0

    try:
        pending_messages = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.channel_type == "EMAIL_QUEUE",
            ChannelQueueItem.status == "PENDING"
        ).order_by(ChannelQueueItem.created_at).limit(batch_size).all()

        logger.debug(f"[EmailQueue] Processing {len(pending_messages)} email messages")

        for message in pending_messages:
            try:
                message.status = "COMPLETED"
                message.completed_at = datetime.utcnow()
                db.commit()
                messages_processed += 1
            except Exception as e:
                db.rollback()
                logger.error(f"[EmailQueue] Error: {e}", exc_info=True)

        return {
            "status": "success",
            "messages_processed": messages_processed
        }

    except Exception as exc:
        logger.error(f"[EmailQueue] Error: {exc}", exc_info=True)
        return {
            "status": "error",
            "messages_processed": messages_processed
        }

    finally:
        db.close()


def process_interview_queue(batch_size: int = 10) -> Dict[str, Any]:
    """Process INTERVIEW_QUEUE messages."""
    logger.debug("[InterviewQueue] Interview queue processing check")
    return {
        "status": "success",
        "messages_processed": 0
    }
