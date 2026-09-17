"""
Message Queue Worker - Processes PENDING messages from ChannelQueueItem

Handles candidate creation, email delivery, interview scheduling, and other async operations.
Runs independently, processing batches of PENDING messages every 30 seconds.
"""
import logging
import signal
from datetime import datetime, timedelta
from typing import Dict, Any
from functools import wraps

from app.core.logging import logger
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.services.channel_processors.candidate_queue_processor import CandidateQueueProcessor
from app.services.queue_doctor_service import QueueDoctorService
from app.services.thunder_pause_service import is_thunder_paused

logger = logging.getLogger(__name__)


class HandlerTimeoutError(Exception):
    """Raised when handler execution exceeds timeout."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise HandlerTimeoutError("Handler execution exceeded 30-second timeout")


def with_timeout(timeout_seconds: int = 30):
    """Decorator to add timeout to handler execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set signal handler and alarm
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)  # Disable alarm
                signal.signal(signal.SIGALRM, old_handler)  # Restore handler
        return wrapper
    return decorator


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
        # Phase 3: Check if Thunder is paused (kill switch)
        if is_thunder_paused(db):
            logger.info("[Worker] Thunder paused, skipping queue processing")
            return {
                "status": "paused",
                "messages_processed": 0,
                "note": "Thunder kill switch active"
            }
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
                    # Phase 2: Start diagnostics tracking
                    doctor_state = QueueDoctorService.start_tracking(message, db)
                    doctor_state.started_at = datetime.utcnow()

                    # Mark as PROCESSING (already in session, no add needed)
                    message.status = "PROCESSING"
                    try:
                        db.commit()
                    except Exception as commit_err:
                        db.rollback()
                        logger.error(f"[Worker] Failed to mark PROCESSING: {commit_err}", exc_info=True)
                        continue

                    logger.info(f"[Worker] Processing {message.type} message {message.id}")

                    # Route to appropriate processor using handler registry
                    from app.services.message_handler_registry import MessageHandlerRegistry

                    handler = MessageHandlerRegistry.get_handler(message.type)
                    if handler:
                        try:
                            # Wrap handler with 30-second timeout guard
                            wrapped_handler = with_timeout(30)(handler)
                            result = wrapped_handler(message, db)
                        except HandlerTimeoutError as e:
                            logger.error(f"[Worker] Handler timeout for message {message.id} (type: {message.type}): {e}")
                            message.status = "FAILED"
                            message.error = f"Handler timeout: exceeded 30 seconds"
                            message.completed_at = datetime.utcnow()
                            message.retry_count = (message.retry_count or 0) + 1
                            message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
                            try:
                                db.commit()
                            except Exception as commit_err:
                                db.rollback()
                                logger.error(f"[Worker] Failed to mark timeout message as FAILED: {commit_err}", exc_info=True)
                            continue
                    else:
                        # Unknown message type - mark as FAILED with retry scheduling
                        logger.warning(f"[Worker] Unknown message type: {message.type}")
                        message.status = "FAILED"
                        message.error = f"Unknown message type: {message.type}"
                        message.completed_at = datetime.utcnow()
                        message.retry_count = (message.retry_count or 0) + 1
                        message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
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

                    # Phase 2: Complete diagnostics tracking
                    QueueDoctorService.complete_tracking(doctor_state, message, db)

                    logger.info(f"[Worker] ✅ Message {message.id} completed successfully")
                    messages_processed += 1

                except Exception as e:
                    # Handle processing error - CRITICAL: set retry_at for automatic retry
                    try:
                        message.status = "FAILED"
                        message.error = str(e)
                        message.completed_at = datetime.utcnow()
                        message.retry_count = (message.retry_count or 0) + 1
                        message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
                        db.commit()
                        logger.error(f"[Worker] ❌ Message {message.id} failed: {str(e)} (retry {message.retry_count}/5)", exc_info=True)
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

        if pending_messages:
            for message in pending_messages:
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
    """Process EMAIL_QUEUE messages - actually send emails."""
    from app.services.email_service import EmailService
    from app.models.message_queue import EmailTracking
    from app.models.candidate import Candidate

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
                payload = message.payload or {}
                candidate_id = payload.get("candidate_id")
                recipient_email = payload.get("recipient_email")
                email_type = payload.get("email_type", "FIRST_ENGAGEMENT")
                subject = payload.get("subject")
                body = payload.get("body")

                if not recipient_email or not subject or not body:
                    logger.warning(f"[EmailQueue] Skipping {message.id} - missing required fields")
                    message.status = "FAILED"
                    message.error = "Missing required email fields"
                    db.commit()
                    continue

                # Send email via EmailService
                result = EmailService.send_email(
                    to=recipient_email,
                    subject=subject,
                    body=body
                )

                if result.get("status") == "success":
                    # Create email tracking record
                    tracking = EmailTracking(
                        candidate_id=candidate_id,
                        email_type=email_type,
                        recipient_email=recipient_email,
                        graph_message_id=result.get("message_id"),
                        status="SENT",
                        sent_at=datetime.utcnow()
                    )
                    db.add(tracking)

                    # Update candidate email tracking fields
                    if candidate_id:
                        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                        if candidate:
                            candidate.first_email_sent_at = datetime.utcnow()
                            candidate.first_email_delivery_status = "SENT"
                            candidate.last_email_sent_at = datetime.utcnow()
                            candidate.last_email_delivery_status = "SENT"

                    message.status = "COMPLETED"
                    logger.info(f"[EmailQueue] Sent {email_type} to {recipient_email}")
                else:
                    # Email send failed
                    message.status = "FAILED"
                    message.error = result.get("error", "Email send failed")
                    if candidate_id:
                        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                        if candidate:
                            candidate.first_email_delivery_status = "FAILED"
                            candidate.email_delivery_failure_reason = message.error
                    logger.error(f"[EmailQueue] Failed to send email: {message.error}")

                message.completed_at = datetime.utcnow()
                db.commit()
                messages_processed += 1

            except Exception as e:
                db.rollback()
                logger.error(f"[EmailQueue] Error processing message {message.id}: {e}", exc_info=True)
                message.status = "FAILED"
                message.error = str(e)
                message.completed_at = datetime.utcnow()
                db.commit()

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
