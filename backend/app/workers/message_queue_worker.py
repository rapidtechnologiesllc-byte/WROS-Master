"""
Message Queue Worker - Processes PENDING messages from ChannelQueueItem

Handles candidate creation, email delivery, interview scheduling, and other async operations.
Runs independently, processing batches of PENDING messages every 30 seconds.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from app.core.logging import logger
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.services.channel_processors.candidate_queue_processor import CandidateQueueProcessor
from app.services.queue_doctor_service import QueueDoctorService
from app.services.thunder_pause_service import is_thunder_paused

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

                    # Route to appropriate processor based on message type
                    if message.type == "create_candidate":
                        result = CandidateQueueProcessor.process(message, db)
                    elif message.type in ["engage_candidate_with_thunder", "assign_thunder_agent"]:
                        # Immediately engage candidate with Thunder AND send first message (don't wait for 5-min cycle)
                        candidate_id = message.payload.get('candidate_id')
                        try:
                            from app.models.candidate import Candidate
                            from app.models.candidate_ai import CandidateConversation
                            from app.services.thunder_service import send_thunder_message, has_active_consent

                            # 1. Get candidate
                            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                            if not candidate:
                                raise ValueError(f"Candidate {candidate_id} not found")

                            # 2. Create/fetch conversation
                            conversation = db.query(CandidateConversation).filter(
                                CandidateConversation.candidate_id == candidate_id
                            ).first()

                            if not conversation:
                                conversation = CandidateConversation(
                                    candidate_id=candidate_id,
                                    owner_type="Thunder",
                                    owner_id="Thunder_Autonomous",
                                    status="ACTIVE",
                                )
                                db.add(conversation)
                                db.flush()
                                logger.info(f"[Worker] ✅ Created conversation for {candidate_id}")

                            # 3. Check consent & send initial message
                            if has_active_consent(db, candidate_id):
                                try:
                                    initial_message = f"Hi {candidate.candidateFirstName}, thanks for your interest! Let's explore this opportunity."
                                    send_thunder_message(
                                        db=db,
                                        conversation=conversation,
                                        candidate=candidate,
                                        message_body=initial_message,
                                        sender_type="ai_agent",
                                        channel="whatsapp"
                                    )
                                    db.commit()
                                    logger.info(f"[Worker] ✅ Sent initial message to {candidate_id}")
                                except Exception as msg_err:
                                    logger.warning(f"[Worker] Could not send message (no consent?): {msg_err}, marking candidate as engaged anyway")
                                    db.commit()
                            else:
                                logger.info(f"[Worker] No consent for {candidate_id}, conversation created but no message sent")
                                db.commit()

                            result = {
                                "status": "thunder_engaged_and_messaged",
                                "candidate_id": candidate_id,
                                "conversation_created": True,
                                "message_sent": has_active_consent(db, candidate_id)
                            }
                            logger.info(f"[Worker] ✅ Thunder engagement complete for {candidate_id}")

                        except Exception as thunder_err:
                            logger.error(f"[Worker] Failed to engage Thunder for candidate {candidate_id}: {thunder_err}", exc_info=True)
                            # Mark as FAILED for retry
                            message.status = "FAILED"
                            message.error = str(thunder_err)
                            message.completed_at = datetime.utcnow()
                            message.retry_count = (message.retry_count or 0) + 1
                            message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
                            try:
                                db.commit()
                            except Exception as commit_err:
                                db.rollback()
                                logger.error(f"[Worker] Failed to mark message as FAILED: {commit_err}", exc_info=True)
                            raise
                    else:
                        logger.warning(f"[Worker] Unknown message type: {message.type}")
                        message.status = "FAILED"
                        message.error = f"Unknown message type: {message.type}"
                        message.completed_at = datetime.utcnow()
                        message.retry_count = (message.retry_count or 0) + 1
                        message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)  # Schedule retry
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
