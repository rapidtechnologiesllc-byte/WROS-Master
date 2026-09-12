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
import random
import threading
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
    WAITING_FOR_SLM = "WAITING_FOR_SLM"  # NEW: Waiting for SLM to generate content (Phase 2)
    PROCESSING = "PROCESSING"
    READY_TO_SEND = "READY_TO_SEND"  # NEW: SLM completed, ready for delivery (Phase 2)
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"


class QueueProcessorService:
    """Background queue processor - consumes messages and orchestrates handlers + SLM learning"""

    # Configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds (HIGH FIX #3: Reduced from 5s to 1s, exponential: 1s→2s→4s→8s)
    BATCH_SIZE = 50  # HIGH FIX #11: Increased from 10 to 50 (better throughput, less polling)
    POLL_INTERVAL = 2  # seconds
    HANDLER_TIMEOUT_SECONDS = 30  # Max time for any handler to complete before timeout
    MAX_RESULT_SIZE_BYTES = 5 * 1024 * 1024  # 5MB max for result JSON (HIGH FIX #14: Prevent DB truncation)
    MAX_ERROR_SIZE_BYTES = 10 * 1024  # 10KB max for error field (HIGH FIX #7: Prevent JSON corruption)

    # Exponential backoff multiplier
    RETRY_BACKOFF_MULTIPLIER = 2

    @staticmethod
    def _truncate_error_string(error: str, max_size_bytes: int = MAX_ERROR_SIZE_BYTES) -> str:
        """HIGH FIX #7: Safely truncate error strings to prevent JSON corruption"""
        if isinstance(error, str) and len(error.encode('utf-8')) > max_size_bytes:
            # Truncate preserving UTF-8 boundaries
            try:
                truncated = error.encode('utf-8')[:max_size_bytes].decode('utf-8', errors='ignore')
                return truncated + f" ... [truncated, original: {len(error)} chars]"
            except Exception:
                return error[:1000]  # Fallback: basic truncation
        return error

    @staticmethod
    def _calculate_adaptive_batch_size(db: Session, base_batch_size: int = BATCH_SIZE) -> int:
        """HIGH FIX #11: Calculate optimal batch size based on queue depth for adaptive throughput"""
        try:
            # Count pending messages in queue
            pending_count = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.status == QueueStatus.PENDING.value
            ).count()

            if pending_count == 0:
                return 5  # Small batch if queue empty (less polling overhead)
            elif pending_count < 50:
                return 25  # Medium batch
            elif pending_count < 200:
                return 50  # Normal batch
            else:
                return 100  # Large batch for heavy load (2x throughput)

            return base_batch_size
        except Exception as e:
            logger.warning(f"[QueueProcessor] Failed to calculate adaptive batch size: {e}")
            return base_batch_size

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
            # CYCLE 19 + Phase 2: Get messages in various states for processing
            # PENDING: Normal queue items (ready to process)
            # WAITING_FOR_SLM: Need SLM email generation (Phase 2)
            # READY_TO_SEND: SLM completed, ready for Thunder handler (Phase 2)
            # SCHEDULED: Delayed messages where scheduled_for <= now
            pending_messages = db.query(ChannelQueueItem).filter(
                or_(
                    # PENDING messages (ready to process immediately)
                    and_(
                        ChannelQueueItem.status == QueueStatus.PENDING.value,
                        or_(
                            ChannelQueueItem.retry_count == 0,
                            ChannelQueueItem.next_retry_at <= datetime.utcnow()
                        )
                    ),
                    # WAITING_FOR_SLM messages (need email generation)
                    ChannelQueueItem.status == QueueStatus.WAITING_FOR_SLM.value,
                    # READY_TO_SEND messages (SLM done, ready to execute)
                    ChannelQueueItem.status == QueueStatus.READY_TO_SEND.value,
                    # SCHEDULED messages (delayed, now ready)
                    and_(
                        ChannelQueueItem.status == 'SCHEDULED',
                        ChannelQueueItem.scheduled_for <= datetime.utcnow()
                    )
                )
            ).order_by(ChannelQueueItem.created_at.asc()).limit(batch_size).all()

            # HIGH FIX #11: Calculate adaptive batch size and log it
            adaptive_batch_size = QueueProcessorService._calculate_adaptive_batch_size(db, batch_size)
            logger.info(
                f"[QueueProcessor] Processing {len(pending_messages)} messages "
                f"(adaptive batch: {adaptive_batch_size})"
            )

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
                    # SKIP SLM training for simple CRUD operations (create_candidate, etc.)
                    # Those don't need SLM analysis - they just create records
                    skip_slm_training = message.type in ['create_candidate', 'job_created']

                    if result["status"] == QueueStatus.COMPLETED.value and not skip_slm_training:
                        try:
                            QueueProcessorService._train_slm_with_result(
                                db=db,
                                message_type=message.channel_type,
                                task_name=message.type,
                                payload=message.payload,
                                result=result,
                                handler_name=f"{message.type}_handler"  # CYCLE 19: Pass handler name for SLM
                            )
                            stats["slm_updates"] += 1
                        except Exception as slm_err:
                            # CRITICAL FIX #5: Queue alert for ops when SLM training fails
                            logger.error(f"[QueueProcessor] SLM training failed: {slm_err}", exc_info=True)
                            try:
                                from app.services.message_queue_service import MessageQueueService as MQS
                                MQS.enqueue(
                                    task_name='slm_training_alert',
                                    task_id=f"slm_alert_{message.id}",
                                    data={
                                        'message_id': message.id,
                                        'task_type': message.type,
                                        'error': str(slm_err)[:500],
                                        'severity': 'MEDIUM'
                                    }
                                )
                            except Exception as alert_err:
                                logger.warning(f"Failed to queue SLM alert: {alert_err}")

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

    # Circuit breaker state (thread-safe with lock) - HIGH FIX #1: Thread safety
    _consecutive_failures = 0
    _consecutive_failures_lock = threading.Lock()  # Protects concurrent access
    _FAILURE_THRESHOLD = 3  # CRITICAL FIX #4: Lowered from 5 (80s lag) to 3 (40s lag)

    @staticmethod
    def _process_single_message(db: Session, message: ChannelQueueItem) -> Dict[str, Any]:
        """
        Process a single queue message through appropriate handler.

        Handles three workflow paths:
        1. PENDING → Handler execution (normal path)
        2. WAITING_FOR_SLM → SLM email generation handler → READY_TO_SEND
        3. READY_TO_SEND → Direct handler execution (SLM already completed)

        Returns result dict with status and outcome.
        """
        import time
        handler_start_time = time.time()

        try:
            # ========== PHASE 2: Route WAITING_FOR_SLM messages ==========
            if message.status == QueueStatus.WAITING_FOR_SLM.value:
                logger.info(f"[QueueProcessor] Message {message.id} waiting for SLM - routing to slm_generate_email handler")
                try:
                    message.status = QueueStatus.PROCESSING.value
                    message.last_attempted_at = datetime.utcnow()
                    db.commit()

                    # Call SLM handler to generate email content
                    slm_handler = MessageHandlerRegistry.get_handler('slm_generate_email')
                    if not slm_handler:
                        raise ValueError("SLM email generation handler not registered")

                    slm_result = slm_handler(message, db)
                    logger.info(f"[QueueProcessor] SLM generation completed for {message.id}: {slm_result}")
                    # Message status is set to READY_TO_SEND by the SLM handler
                    return {
                        'status': QueueStatus.READY_TO_SEND.value,
                        'message_id': str(message.id),
                        'slm_result': slm_result
                    }
                except Exception as slm_err:
                    logger.error(f"[QueueProcessor] SLM generation failed for {message.id}: {slm_err}", exc_info=True)
                    message.status = QueueStatus.FAILED.value
                    message.error = f"SLM generation failed: {str(slm_err)[:1000]}"
                    db.commit()
                    raise

            # ========== PHASE 2: Route READY_TO_SEND messages directly to handler ==========
            if message.status == QueueStatus.READY_TO_SEND.value:
                logger.info(f"[QueueProcessor] Message {message.id} ready to send - routing to handler {message.type}")
                # Message has SLM-generated content, proceed directly to target handler
                # Don't re-run SLM analysis, just execute

            # ========== NORMAL PATH: PENDING messages ==========
            # Circuit breaker: Stop processing if too many consecutive failures (HIGH FIX #1: Thread-safe)
            with QueueProcessorService._consecutive_failures_lock:
                if QueueProcessorService._consecutive_failures >= QueueProcessorService._FAILURE_THRESHOLD:
                    logger.critical("[QueueProcessor] Circuit breaker triggered - stopping message processing")
                    raise RuntimeError("Circuit breaker triggered - database or system failures detected")

            # Mark as PROCESSING
            message.status = QueueStatus.PROCESSING.value
            message.last_attempted_at = datetime.utcnow()
            db.commit()

            logger.info(f"[QueueProcessor] Processing message {message.id}: {message.type}")

            # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS (ENFORCEMENT) ============
            # Skip PLACE 1 analysis for simple CRUD operations - they don't need pre-flight checks
            skip_place1_analysis = message.type in ['create_candidate', 'job_created', 'job_created_flash', 'job_deleted_flash', 'job_updated_flash']

            slm_analysis = None
            try:
                if not skip_place1_analysis:  # Only analyze complex operations
                    slm_analysis = SLMService.analyze_before_handler(
                        message_id=str(message.id),
                        message_type=message.type,
                        payload=message.payload or {},
                        context={
                            'business_goal': f'Execute {message.type} handler',
                            'risk_level': 'MEDIUM',
                            'queue_retry_count': message.retry_count or 0,
                            'message_age_seconds': (datetime.utcnow() - message.created_at).total_seconds() if message.created_at else 0
                        },
                        db=db,
                        handler_name=f"{message.type}_handler"  # Pass handler name for decision recording
                    )

                # Check if SLM says to escalate
                if not slm_analysis.get('should_proceed'):
                    logger.warning(f"[QueueProcessor] SLM pre-flight escalation for {message.id}: {slm_analysis.get('reasoning')}")
                    message.status = QueueStatus.FAILED.value
                    message.result = json.dumps({
                        'success': False,
                        'error': f"SLM escalation: {slm_analysis.get('reasoning')}",
                        'slm_decision_id': slm_analysis.get('slm_decision_id'),
                        'escalation_reason': slm_analysis.get('reasoning')
                    })
                    db.commit()
                    return {
                        'status': 'escalated',
                        'message_id': str(message.id),
                        'reason': slm_analysis.get('reasoning')
                    }
            except Exception as slm_precheck_err:
                logger.error(f"[QueueProcessor] SLM pre-flight analysis failed: {slm_precheck_err}")
                # Don't block - continue with handler execution
                # SLM service being down shouldn't stop the queue processor
                pass

            # Get handler for this task (type field contains task name like 'job_created_flash')
            handler = MessageHandlerRegistry.get_handler(message.type)
            if not handler:
                raise ValueError(f"No handler registered for {message.type}")

            # Execute handler with timing and TIMEOUT ENFORCEMENT
            try:
                # ARCHITECT FIX #6: Enforce handler timeout (30 seconds max)
                # Prevents handlers from hanging indefinitely and blocking queue processor
                import threading

                handler_result = None
                handler_exception = None

                def _execute_handler_with_timeout():
                    nonlocal handler_result, handler_exception
                    try:
                        handler_result = handler(message, db)
                    except Exception as e:
                        handler_exception = e

                handler_thread = threading.Thread(target=_execute_handler_with_timeout, daemon=True)
                handler_thread.start()
                handler_thread.join(timeout=QueueProcessorService.HANDLER_TIMEOUT_SECONDS)

                handler_duration_ms = int((time.time() - handler_start_time) * 1000)
                message.handler_duration_ms = handler_duration_ms

                # Check if handler timed out (thread still alive after timeout)
                if handler_thread.is_alive():
                    logger.critical(
                        f"[QueueProcessor] ⚠️ HANDLER TIMEOUT: {message.type} exceeded "
                        f"{QueueProcessorService.HANDLER_TIMEOUT_SECONDS}s limit (took {handler_duration_ms}ms)"
                    )
                    raise RuntimeError(
                        f"Handler {message.type} timed out after {QueueProcessorService.HANDLER_TIMEOUT_SECONDS}s"
                    )

                # Check if handler raised exception
                if handler_exception:
                    raise handler_exception

                # Log slow handlers (> 10 seconds)
                if handler_duration_ms > 10000:
                    logger.warning(f"[QueueProcessor] Slow handler {message.type}: {handler_duration_ms}ms")

                # VALIDATION: Verify result contains expected data before marking COMPLETED
                # For job_created_flash: verify job_id exists in result and in database
                if message.type == 'job_created_flash':
                    job_id = handler_result.get('job_id') if isinstance(handler_result, dict) else None
                    if not job_id:
                        raise ValueError(f"Handler did not return job_id in result: {handler_result}")

                    # Verify job actually exists in database (double-check)
                    from app.models.user import Jobs
                    persisted_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
                    if not persisted_job:
                        raise ValueError(f"Job {job_id} not found in database after handler completion")

                    logger.info(f"[QueueProcessor] Verified job {job_id} exists in database")

                    # FLOW STEP 3: Analyze with SLM (job now in DB, ready for analysis)
                    # SLM receives: job_id + JD + hiring_manager requirements
                    try:
                        slm_analysis = SLMService.analyze_job_creation(
                            job_id=job_id,
                            job_title=persisted_job.jobTitle,
                            job_skills=persisted_job.jobSkills or "",
                            no_of_positions=persisted_job.noOfPositions,
                            db=db
                        )
                        logger.info(
                            f"[QueueProcessor] SLM analyzed job {job_id}: "
                            f"urgency={slm_analysis.get('urgency')} "
                            f"strategy={slm_analysis.get('recruitment_strategy')}"
                        )

                        # FLOW STEP 4: Queue flash_recruiter with SLM instructions
                        from app.services.message_queue_service import MessageQueueService as MQS
                        recruiter_msg_id = MQS.enqueue(
                            task_name='flash_recruiter',
                            task_id=f"recruit_{job_id}",
                            data={
                                'job_id': job_id,
                                'job_title': persisted_job.jobTitle,
                                'job_skills': persisted_job.jobSkills or "",
                                'no_of_positions': persisted_job.noOfPositions,
                                'hiring_manager_id': persisted_job.hiringManagerID,
                                'business_unit_id': persisted_job.business_unit_id,
                                'slm_analysis': slm_analysis,
                                'slm_strategy': slm_analysis.get('recruitment_strategy'),
                                'slm_urgency': slm_analysis.get('urgency'),
                            }
                        )
                        logger.info(f"[QueueProcessor] Queued flash_recruiter for job {job_id}: message_id={recruiter_msg_id}")
                    except Exception as slm_err:
                        logger.error(f"[QueueProcessor] SLM analysis failed for job {job_id}: {slm_err}", exc_info=True)
                        # Don't fail - continue without SLM guidance (flash_recruiter will use defaults)

                # CRITICAL FIX #5: Verify delivery was actually confirmed before marking COMPLETED
                # Messages stuck in PROCESSING suggests we're marking COMPLETED without delivery confirmation
                requires_delivery_confirmation = message.type in [
                    'engage_candidate_with_thunder',
                    'send_email_to_candidate',
                    'send_whatsapp_message',
                ]

                if requires_delivery_confirmation:
                    delivery_confirmed = handler_result.get('delivery_confirmed', False) if isinstance(handler_result, dict) else False
                    message_sent = handler_result.get('message_sent', False) if isinstance(handler_result, dict) else False

                    if not (delivery_confirmed or message_sent):
                        # Delivery was not confirmed - mark as FAILED instead of COMPLETED
                        logger.error(
                            f"[QueueProcessor] Message {message.id} ({message.type}) did not confirm delivery. "
                            f"Handler result: {handler_result}. FAILING message instead of completing."
                        )
                        message.status = QueueStatus.FAILED.value
                        message.error = "Handler did not confirm message delivery"
                        message.last_attempted_at = datetime.utcnow()
                        result_data = {
                            "success": False,
                            "error": "Delivery not confirmed by handler",
                            "handler_result": handler_result,
                            "failed_at": datetime.utcnow().isoformat(),
                            "handler_duration_ms": handler_duration_ms
                        }
                        result_json = json.dumps(result_data)
                        message.result = result_json
                        db.commit()

                        return {
                            "status": QueueStatus.FAILED.value,
                            "message": f"Delivery not confirmed: {handler_result}",
                            "duration_ms": handler_duration_ms
                        }

                # Mark COMPLETED only after validation passes
                message.status = QueueStatus.COMPLETED.value
                message.last_attempted_at = datetime.utcnow()  # HIGH FIX #8: Track completion time
                result_data = {
                    "success": True,
                    "data": handler_result,
                    "completed_at": datetime.utcnow().isoformat(),
                    "handler_duration_ms": handler_duration_ms
                }
                result_json = json.dumps(result_data)

                # HIGH FIX #14: Check result size and truncate if necessary
                if len(result_json.encode('utf-8')) > QueueProcessorService.MAX_RESULT_SIZE_BYTES:
                    logger.warning(
                        f"[QueueProcessor] Result too large ({len(result_json) / (1024*1024):.1f}MB), "
                        f"truncating handler_result"
                    )
                    # Remove large data field and keep only success flag + metadata
                    result_data = {
                        "success": True,
                        "data_truncated": True,
                        "data_size_bytes": len(str(handler_result).encode('utf-8')),
                        "completed_at": datetime.utcnow().isoformat(),
                        "handler_duration_ms": handler_duration_ms
                    }
                    result_json = json.dumps(result_data)

                message.result = result_json

                # HIGH FIX #10: Reset retry count to 0 on success (better retry logic)
                message.retry_count = 0
                db.commit()

                # Reset circuit breaker on success (HIGH FIX #1: Thread-safe)
                with QueueProcessorService._consecutive_failures_lock:
                    QueueProcessorService._consecutive_failures = 0

                return {
                    "status": QueueStatus.COMPLETED.value,
                    "message_id": message.id,
                    "task": message.type,
                    "result": handler_result,
                    "handler_duration_ms": handler_duration_ms
                }

            except Exception as handler_err:
                # Handler failed - check retry logic
                logger.error(f"[QueueProcessor] Handler failed for {message.type}: {handler_err}", exc_info=True)

                if message.retry_count < QueueProcessorService.MAX_RETRIES:
                    # Schedule retry with exponential backoff + jitter (HIGH FIX #3: Thundering herd prevention)
                    base_backoff = (
                        QueueProcessorService.INITIAL_RETRY_DELAY *
                        (QueueProcessorService.RETRY_BACKOFF_MULTIPLIER ** message.retry_count)
                    )
                    # Add ±10% jitter to prevent synchronized retries
                    jitter = random.uniform(0, 0.1 * base_backoff)
                    backoff_seconds = base_backoff + jitter
                    message.retry_count += 1
                    message.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                    message.last_attempted_at = datetime.utcnow()  # HIGH FIX #8: Track retry attempt time
                    message.status = QueueStatus.PENDING.value  # CRITICAL FIX #9: Keep PENDING so retry is picked up
                    message.result = json.dumps({
                        "success": False,
                        "error": QueueProcessorService._truncate_error_string(str(handler_err)),
                        "retry_count": message.retry_count,
                        "next_retry_at": message.next_retry_at.isoformat()
                    })
                    db.commit()

                    return {
                        "status": QueueStatus.PENDING.value,  # CRITICAL FIX #9: Return PENDING for retry
                        "message_id": message.id,
                        "retry_count": message.retry_count,
                        "next_retry_at": message.next_retry_at.isoformat(),
                        "error": str(handler_err)
                    }
                else:
                    # Max retries exceeded - send to dead letter
                    message.last_attempted_at = datetime.utcnow()  # HIGH FIX #8: Track final attempt time
                    message.status = QueueStatus.DEAD_LETTER.value
                    message.result = json.dumps({
                        "success": False,
                        "error": QueueProcessorService._truncate_error_string(str(handler_err)),
                        "max_retries_exceeded": True,
                        "final_error_at": datetime.utcnow().isoformat()
                    })
                    db.commit()

                    # CRITICAL FIX #3: Escalate to manual review with robust error handling
                    logger.critical(f"[QueueProcessor] Message {message.id} dead-lettered after {message.retry_count} retries: {handler_err}")
                    try:
                        # Queue escalation alert for ops team
                        from app.services.message_queue_service import MessageQueueService as MQS
                        MQS.enqueue(
                            task_name='dead_letter_escalation',
                            task_id=f"escalation_{message.id}",
                            data={
                                'dead_letter_message_id': message.id,
                                'task_type': message.type,
                                'error': QueueProcessorService._truncate_error_string(str(handler_err)),
                                'retry_count': message.retry_count,
                                'created_at': message.created_at.isoformat() if message.created_at else None
                            }
                        )
                        logger.info(f"[QueueProcessor] Dead letter escalation queued for {message.id}")
                    except Exception as esc_err:
                        # CRITICAL FIX #3: Don't fail if escalation fails - message is already dead-lettered
                        logger.error(f"[QueueProcessor] Escalation failed (non-blocking): {esc_err}")
                        # Continue - don't re-raise

                    return {
                        "status": QueueStatus.DEAD_LETTER.value,
                        "message_id": message.id,
                        "retry_count": message.retry_count,
                        "error": str(handler_err)
                    }

        except Exception as e:
            logger.error(f"[QueueProcessor] Unexpected error processing {message.id}: {e}", exc_info=True)
            message.status = QueueStatus.FAILED.value
            message.last_attempted_at = datetime.utcnow()  # HIGH FIX #8: Track failure time
            message.result = json.dumps({
                "error": QueueProcessorService._truncate_error_string(str(e)),
                "failed_at": datetime.utcnow().isoformat()
            })
            db.commit()

            # Increment circuit breaker counter (HIGH FIX #1: Thread-safe)
            with QueueProcessorService._consecutive_failures_lock:
                QueueProcessorService._consecutive_failures += 1
                logger.warning(
                    f"[QueueProcessor] Consecutive failures: "
                    f"{QueueProcessorService._consecutive_failures}/{QueueProcessorService._FAILURE_THRESHOLD}"
                )

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
        result: Dict[str, Any],
        handler_name: str = None  # CYCLE 19: Handler name for SLM decision recording
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
                db=db,
                handler_name=handler_name  # CYCLE 19: Pass handler name for decision recording
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

                    # HEARTBEAT: Log every batch for monitoring
                    logger.debug(
                        f"[QueueProcessor] Batch {processor_stats['batches_processed']}: "
                        f"processed={batch_result['processed']}, "
                        f"completed={batch_result['completed']}, "
                        f"failed={batch_result['failed']}, "
                        f"retried={batch_result['retried']}"
                    )

                    # Log periodic stats (every 10 batches)
                    if processor_stats["batches_processed"] % 10 == 0:
                        logger.info(
                            f"[QueueProcessor] STATS (batch {processor_stats['batches_processed']}): "
                            f"total_processed={processor_stats['total_messages']}, "
                            f"total_completed={processor_stats['total_completed']}, "
                            f"total_failed={processor_stats['total_failed']}"
                        )

                    # HIGH FIX #12: Adaptive poll interval based on queue depth
                    # If queue empty, wait longer; if queue full, process faster
                    if batch_result["processed"] == 0:
                        # Queue empty - wait longer (up to 10s max)
                        adaptive_interval = min(poll_interval * 5, 10)
                    elif batch_result["processed"] == batch_size:
                        # Queue full - don't wait, process immediately
                        adaptive_interval = 0.1
                    else:
                        # Queue partially full - use normal interval
                        adaptive_interval = poll_interval

                    time.sleep(adaptive_interval)

                except Exception as e:
                    logger.error(f"[QueueProcessor] Batch error: {e}", exc_info=True)
                    time.sleep(poll_interval)  # Sleep on error

                finally:
                    db.close()

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
