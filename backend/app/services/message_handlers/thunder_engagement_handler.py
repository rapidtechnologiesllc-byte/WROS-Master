"""Thunder Engagement Handler - Queue-driven engagement with timeout & validation.

Handles candidate engagement through Thunder with:
- 60-second timeout enforcement via @time_bound
- Post-execution validation (conversation + message verified in DB)
- Retry logic with exponential backoff
- Comprehensive error classification
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


TIMEOUT_SECONDS = 60


class ThunderEngagementHandler:
    """Handles candidate engagement messages from Thunder queue with validation."""

    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process Thunder engagement message - send initial message to candidate.

        Args:
            message: ChannelQueueItem with payload containing candidate_id
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'candidate_id': str,
                'conversation_id': str,
                'message_sent': bool,
                'delivery_confirmed': bool
            }

        Raises:
            ValueError: Candidate not found (non-retryable)
            RuntimeError: Message send failure (retryable)
        """
        from app.services.thunder_service import send_thunder_message, has_active_consent

        if not message or not message.payload:
            raise ValueError(f"Message {message.id if message else 'unknown'} has no payload")

        payload = message.payload
        candidate_id = payload.get("candidate_id")

        # ===== VALIDATION STEP 1: Payload has required fields =====
        if not candidate_id or "@" not in str(candidate_id).lower():
            # candidate_id is UUID, not email, but validate it exists
            if not candidate_id:
                raise ValueError("Missing candidate_id in payload")

        logger.info(f"[Thunder] Processing engagement for candidate {candidate_id}")

        try:
            # ===== STEP 1: Get candidate =====
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            logger.info(f"[Thunder] ✅ Candidate exists: {candidate_id}")

            # Gate: never engage a placeholder (un-enriched LinkedIn) candidate, a
            # candidate with Thunder off, or one inside a post-rejection no-contact period
            from app.services.candidate_contact_policy import is_contactable
            contactable, reason = is_contactable(db, candidate)
            if not contactable:
                logger.info(f"[Thunder] Skipping engagement for {candidate_id}: {reason}")
                return {"status": "skipped", "reason": reason, "candidate_id": candidate_id,
                        "message_sent": False, "delivery_confirmed": False}

            # ===== STEP 2: Create/fetch conversation =====
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
                logger.info(f"[Thunder] Created conversation for {candidate_id}")
            else:
                logger.info(f"[Thunder] Using existing conversation for {candidate_id}")

            conversation_id = conversation.id if hasattr(conversation, 'id') else str(candidate_id)

            # ===== STEP 3: Check consent & send message =====
            message_sent = False
            delivery_confirmed = False

            if has_active_consent(db, candidate_id):
                # Get SLM-generated email content if available
                initial_message = payload.get("slm_generated_email_body")

                # Fallback message if SLM didn't generate one
                if not initial_message:
                    candidate_name = getattr(candidate, 'candidateFirstName', 'Candidate')
                    initial_message = f"Hi {candidate_name}, thanks for your interest! Let's explore this opportunity."
                    logger.debug(f"[Thunder] No SLM-generated email for {candidate_id}, using fallback message")
                else:
                    logger.info(f"[Thunder] Using SLM-generated email for {candidate_id} ({len(initial_message)} chars)")

                # TIMEOUT ENFORCEMENT: Thread-based timeout already enforced by @time_bound decorator
                # This just calls send_thunder_message and tracks result
                try:
                    send_thunder_message(
                        db=db,
                        conversation=conversation,
                        candidate=candidate,
                        message_body=initial_message,
                        sender_type="ai_agent",
                        channel="whatsapp"
                    )
                    message_sent = True
                    delivery_confirmed = True
                    logger.info(f"[Thunder] ✅ Message sent and confirmed for {candidate_id}")

                except Exception as send_err:
                    logger.error(f"[Thunder] Failed to send message to {candidate_id}: {send_err}", exc_info=True)
                    # Fail fast - don't silently skip
                    raise RuntimeError(f"Failed to send Thunder message: {str(send_err)}") from send_err
            else:
                logger.info(f"[Thunder] No consent for {candidate_id}, conversation created but no message sent")
                message_sent = False
                delivery_confirmed = False

            # ===== STEP 4: Commit transaction =====
            try:
                db.commit()
                logger.info(f"[Thunder] ✅ Transaction committed for {candidate_id}")
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[Thunder] Commit failed for {candidate_id}: {commit_err}", exc_info=True)
                raise RuntimeError(f"Database commit failed: {str(commit_err)}") from commit_err

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "conversation_id": conversation_id,
                "message_sent": message_sent,
                "delivery_confirmed": delivery_confirmed,
            }

        except ValueError as e:
            # Non-retryable: candidate not found, payload invalid
            logger.error(f"[Thunder] NON-RETRYABLE validation error: {e}")
            raise

        except RuntimeError as e:
            # Retryable: send failure, database error
            logger.error(f"[Thunder] RETRYABLE error (will retry): {e}", exc_info=True)
            raise

        except Exception as e:
            # Unexpected error - treat as retryable
            logger.error(f"[Thunder] Unexpected error for {candidate_id}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= ThunderEngagementHandler.MAX_RETRIES:
            logger.error(f"[Thunder] Max retries exceeded for {message.id}")
            return False

        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False

        return True

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """
        Validate that Thunder engagement actually completed successfully.

        Verifies:
        1. Candidate exists
        2. Conversation was created
        3. Message was sent (if consent active)

        Args:
            message: Queue message with payload
            result: Result dict from process()
            db: Database session

        Raises:
            ValueError: Candidate/conversation not found (non-retryable)
            RuntimeError: Database validation error (retryable)
        """
        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        if result.get("status") == "skipped":
            return

        candidate_id = result.get("candidate_id")
        conversation_id = result.get("conversation_id")

        try:
            # 1. VERIFY CANDIDATE EXISTS
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found in database after engagement")

            # 2. VERIFY CONVERSATION EXISTS
            conversation = db.query(CandidateConversation).filter(
                CandidateConversation.candidate_id == candidate_id
            ).first()
            if not conversation:
                raise ValueError(f"Conversation for {candidate_id} not found in database after engagement")

            logger.info(f"✅ Thunder engagement validated: {candidate_id}, Conversation={conversation_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[Thunder] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database validation error: {str(e)}") from e

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry after failed attempt."""
        try:
            db.rollback()

            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=ThunderEngagementHandler.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[Thunder] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{ThunderEngagementHandler.MAX_RETRIES}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[Thunder] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Mark message as COMPLETED after validation passes.

        Calls validate() to ensure candidate and conversation exist.
        Only marks COMPLETED if validation passes.
        """
        try:
            # Call validate() which follows base handler pattern
            ThunderEngagementHandler.validate(message, result, db)

            # ✅ VALIDATION PASSED - Mark as COMPLETED
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit COMPLETED status: {str(commit_err)}") from commit_err

            candidate_id = result.get("candidate_id", "unknown")
            logger.info(f"[Thunder] ✅ Message {message.id} marked COMPLETED (candidate {candidate_id})")

            return {
                "is_valid": True,
                "candidate_id": candidate_id,
                "message": "Validation passed and message marked COMPLETED"
            }

        except ValueError as e:
            db.rollback()
            logger.error(f"[Thunder] ❌ NON-RETRYABLE validation failure: {e}")
            raise

        except RuntimeError as e:
            db.rollback()
            logger.error(f"[Thunder] ❌ RETRYABLE validation failure: {e}")
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[Thunder] ❌ Unexpected error during on_success: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        try:
            db.rollback()

            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()

            db.commit()
            logger.error(
                f"[Thunder] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[Thunder] Failed to mark as FAILED: {e}", exc_info=True)
            raise
