"""Queue Processor Service - Background worker that consumes and processes queue messages
CYCLE 19: Queue processor with SLM integration

Responsibilities:
1. Poll ChannelQueueItem table for PENDING messages
2. Route to appropriate handler (Flash, Thunder, Email, etc.)
3. Analyze result with SLMService
4. Train SLM with execution patterns
5. Update message status (COMPLETED/FAILED/RETRY)
6. Implement exponential backoff for retries

Architecture: Works WITH SLMService to create feedback loop
- Message queued → Processed by handler → SLM analyzes outcome → SLM trained
"""
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.services.message_handler_registry import MessageHandlerRegistry
from app.services.slm_service import SLMService
from app.services.architect_codebase_learning import ArchitectKnowledgeTeacher
from app.core.logging import logger

logger = logging.getLogger(__name__)


class QueueStatus(str, Enum):
    """Queue message status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"


class QueueProcessorService:
    """Background queue processor - consumes messages and orchestrates handlers + SLM learning"""

    # Configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 5  # seconds
    BATCH_SIZE = 10
    POLL_INTERVAL = 2  # seconds

    # Exponential backoff multiplier
    RETRY_BACKOFF_MULTIPLIER = 2

    @staticmethod
    def process_queue_batch(db: Session, batch_size: int = BATCH_SIZE) -> Dict[str, Any]:
        """
        Process one batch of pending queue messages.

        Returns:
            {
                "processed": 5,
                "completed": 4,
                "failed": 0,
                "retried": 1,
                "slm_updates": 4,
                "errors": []
            }
        """
        stats = {
            "processed": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
            "slm_updates": 0,
            "errors": []
        }

        try:
            # Get PENDING messages, ordered by created_at (FIFO)
            pending_messages = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.status == QueueStatus.PENDING.value,
                or_(
                    ChannelQueueItem.retry_count == 0,
                    ChannelQueueItem.next_retry_at <= datetime.utcnow()
                )
            ).order_by(ChannelQueueItem.created_at.asc()).limit(batch_size).all()

            logger.info(f"[QueueProcessor] Processing {len(pending_messages)} messages")

            for message in pending_messages:
                try:
                    result = QueueProcessorService._process_single_message(db, message)

                    # Update stats based on result
                    stats["processed"] += 1
                    if result["status"] == QueueStatus.COMPLETED.value:
                        stats["completed"] += 1
                    elif result["status"] == QueueStatus.RETRY.value:
                        stats["retried"] += 1
                    elif result["status"] == QueueStatus.FAILED.value:
                        stats["failed"] += 1

                    # Train SLM with result if message completed
                    if result["status"] == QueueStatus.COMPLETED.value:
                        try:
                            QueueProcessorService._train_slm_with_result(
                                db=db,
                                message_type=message.channel_type,
                                task_name=message.type,
                                payload=message.payload,
                                result=result
                            )
                            stats["slm_updates"] += 1
                        except Exception as slm_err:
                            logger.warning(f"[QueueProcessor] SLM training failed: {slm_err}")

                except Exception as msg_err:
                    logger.error(f"[QueueProcessor] Message {message.id} failed: {msg_err}", exc_info=True)
                    stats["errors"].append(str(msg_err))

            db.commit()
            logger.info(f"[QueueProcessor] Batch complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"[QueueProcessor] Batch processing failed: {e}", exc_info=True)
            db.rollback()
            stats["errors"].append(str(e))
            return stats

    @staticmethod
    def _process_single_message(db: Session, message: ChannelQueueItem) -> Dict[str, Any]:
        """
        Process a single queue message through appropriate handler.

        Returns result dict with status and outcome.
        """
        try:
            # Mark as PROCESSING
            message.status = QueueStatus.PROCESSING.value
            message.last_attempted_at = datetime.utcnow()
            db.commit()

            logger.info(f"[QueueProcessor] Processing message {message.id}: {message.type}")

            # Get handler for this task (type field contains task name like 'job_created_flash')
            handler = MessageHandlerRegistry.get_handler(message.type)
            if not handler:
                raise ValueError(f"No handler registered for {message.type}")

            # Execute handler
            try:
                handler_result = handler(message, db)

                # Mark COMPLETED
                message.status = QueueStatus.COMPLETED.value
                message.result = json.dumps({
                    "success": True,
                    "data": handler_result,
                    "completed_at": datetime.utcnow().isoformat()
                })
                db.commit()

                return {
                    "status": QueueStatus.COMPLETED.value,
                    "message_id": message.id,
                    "task": message.task_name,
                    "result": handler_result
                }

            except Exception as handler_err:
                # Handler failed - check retry logic
                logger.error(f"[QueueProcessor] Handler failed for {message.task_name}: {handler_err}")

                if message.retry_count < QueueProcessorService.MAX_RETRIES:
                    # Schedule retry with exponential backoff
                    backoff_seconds = (
                        QueueProcessorService.INITIAL_RETRY_DELAY *
                        (QueueProcessorService.RETRY_BACKOFF_MULTIPLIER ** message.retry_count)
                    )
                    message.retry_count += 1
                    message.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                    message.status = QueueStatus.RETRY.value
                    message.result = json.dumps({
                        "success": False,
                        "error": str(handler_err),
                        "retry_count": message.retry_count,
                        "next_retry_at": message.next_retry_at.isoformat()
                    })
                    db.commit()

                    return {
                        "status": QueueStatus.RETRY.value,
                        "message_id": message.id,
                        "retry_count": message.retry_count,
                        "next_retry_at": message.next_retry_at.isoformat(),
                        "error": str(handler_err)
                    }
                else:
                    # Max retries exceeded - send to dead letter
                    message.status = QueueStatus.DEAD_LETTER.value
                    message.result = json.dumps({
                        "success": False,
                        "error": str(handler_err),
                        "max_retries_exceeded": True,
                        "final_error_at": datetime.utcnow().isoformat()
                    })
                    db.commit()

                    # Escalate to manual review
                    logger.critical(f"[QueueProcessor] Message {message.id} dead-lettered after {message.retry_count} retries")

                    return {
                        "status": QueueStatus.DEAD_LETTER.value,
                        "message_id": message.id,
                        "retry_count": message.retry_count,
                        "error": str(handler_err)
                    }

        except Exception as e:
            logger.error(f"[QueueProcessor] Unexpected error processing {message.id}: {e}", exc_info=True)
            message.status = QueueStatus.FAILED.value
            message.result = json.dumps({"error": str(e), "failed_at": datetime.utcnow().isoformat()})
            db.commit()

            return {
                "status": QueueStatus.FAILED.value,
                "message_id": message.id,
                "error": str(e)
            }

    @staticmethod
    def _train_slm_with_result(
        db: Session,
        message_type: str,
        task_name: str,
        payload: Dict[str, Any],
        result: Dict[str, Any]
    ):
        """
        Train SLM with successful message result.

        SLM learns:
        - What messages succeed frequently
        - Which handlers are reliable
        - Patterns in successful processing
        """
        try:
            # Analyze result with SLMService
            slm_decision = SLMService.analyze_message_result(
                message_id=result.get("message_id", "unknown"),
                message_type=message_type,
                result=result,
                db=db
            )

            # Record learning pattern
            learning_record = {
                "task": task_name,
                "message_type": message_type,
                "success": result["status"] == QueueStatus.COMPLETED.value,
                "slm_decision": slm_decision,
                "timestamp": datetime.utcnow().isoformat(),
                "payload_summary": {
                    "keys": list(payload.keys()) if isinstance(payload, dict) else []
                }
            }

            # Push to architect learning system
            try:
                teacher = ArchitectKnowledgeTeacher()
                teacher.teach_pattern(
                    pattern_type="queue_processing",
                    pattern_data=learning_record
                )
            except Exception as learn_err:
                logger.warning(f"[QueueProcessor] Failed to record learning pattern: {learn_err}")

            logger.info(f"[QueueProcessor] SLM trained: {task_name} → {slm_decision.get('decision')}")

        except Exception as e:
            logger.error(f"[QueueProcessor] SLM training error: {e}", exc_info=True)
            raise

    @staticmethod
    def start_background_processor(poll_interval: int = POLL_INTERVAL, batch_size: int = BATCH_SIZE):
        """
        Start the background queue processor loop (runs continuously).

        Should be called in a background task/thread.
        """
        logger.info("[QueueProcessor] Starting background queue processor...")

        processor_stats = {
            "batches_processed": 0,
            "total_messages": 0,
            "total_completed": 0,
            "total_retried": 0,
            "total_failed": 0,
            "start_time": datetime.utcnow().isoformat()
        }

        try:
            while True:
                db = SessionLocal()
                try:
                    # Process one batch
                    batch_result = QueueProcessorService.process_queue_batch(db, batch_size)

                    # Update overall stats
                    processor_stats["batches_processed"] += 1
                    processor_stats["total_messages"] += batch_result["processed"]
                    processor_stats["total_completed"] += batch_result["completed"]
                    processor_stats["total_retried"] += batch_result["retried"]
                    processor_stats["total_failed"] += batch_result["failed"]

                    # Log periodic stats
                    if processor_stats["batches_processed"] % 10 == 0:
                        logger.info(f"[QueueProcessor] Processor stats: {processor_stats}")

                except Exception as e:
                    logger.error(f"[QueueProcessor] Batch error: {e}", exc_info=True)

                finally:
                    db.close()
                    time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("[QueueProcessor] Queue processor stopped")
        except Exception as e:
            logger.critical(f"[QueueProcessor] Fatal error: {e}", exc_info=True)
            raise


# For use in background tasks / Celery / APScheduler
def queue_processor_task():
    """Celery/APScheduler task wrapper for queue processing"""
    db = SessionLocal()
    try:
        result = QueueProcessorService.process_queue_batch(db)
        return result
    finally:
        db.close()
