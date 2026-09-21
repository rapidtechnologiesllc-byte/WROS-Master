"""Processor for CANDIDATE_QUEUE message channels

Routes candidate-related messages to appropriate handlers with retry logic.
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.channel_queue import ChannelQueueItem
from app.services.message_handlers.candidate_creation_unified_handler import CandidateCreationUnifiedHandler
from app.services.message_handlers.candidate_conversion_handler import CandidateConversionHandler

logger = logging.getLogger(__name__)


class CandidateQueueProcessor:
    """Processes candidate-related messages from the queue."""

    @staticmethod
    def process(
        message: ChannelQueueItem,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Process a candidate message based on its type.

        Routes to appropriate handler and implements retry logic.

        Args:
            message: ChannelQueueItem record with message_type and payload
            channel: MessageChannel record indicating this processing attempt
            db: Database session

        Returns:
            {'status': 'success', ...handler-specific fields...}

        Raises:
            RuntimeError: If processing fails (will trigger retry)
            ValueError: If message type unknown
        """
        message_type = message.type
        logger.info(
            f"[CandidateQueueProcessor] Processing {message_type} message {message.id}"
        )

        try:
            if message_type == "create_candidate":
                result = CandidateCreationUnifiedHandler.process(message, db)
                return result

            elif message_type == "convert_candidate_to_employee":
                result = CandidateConversionHandler.process(message, db)
                CandidateConversionHandler.on_success(message, result, db)
                return result

            else:
                raise ValueError(f"Unknown message type: {message_type}")

        except Exception as e:
            # Route to appropriate handler's retry logic
            if message_type == "create_candidate":
                handler_class = CandidateCreationUnifiedHandler
            elif message_type == "convert_candidate_to_employee":
                handler_class = CandidateConversionHandler
            else:
                raise RuntimeError(f"No handler for message type: {message_type}") from e

            # Determine if should retry
            should_retry = handler_class.should_retry(message)

            if should_retry:
                logger.warning(
                    f"[CandidateQueueProcessor] {message_type} processing failed, "
                    f"scheduling retry (attempt {message.retry_count + 1}/"
                    f"{handler_class.MAX_RETRIES}): {str(e)}",
                    exc_info=True,
                )
                try:
                    handler_class.on_retry(message, str(e), db)
                except Exception as retry_error:
                    logger.error(f"Failed to schedule retry: {retry_error}", exc_info=True)
                    raise RuntimeError(f"Failed to schedule retry: {str(retry_error)}") from retry_error
                raise RuntimeError(f"Retryable error: {str(e)}") from e

            else:
                logger.error(
                    f"[CandidateQueueProcessor] {message_type} processing FAILED after "
                    f"max retries ({handler_class.MAX_RETRIES}): {str(e)}",
                    exc_info=True,
                )
                try:
                    handler_class.on_failed(message, str(e), db)
                except Exception as fail_error:
                    logger.error(f"Failed to mark as failed: {fail_error}", exc_info=True)
                    raise RuntimeError(f"Failed to mark as failed: {str(fail_error)}") from fail_error
                raise RuntimeError(f"Max retries exceeded: {str(e)}") from e

    @staticmethod
    def handle_success(
        message: ChannelQueueItem,
        result: Dict[str, Any],
        db: Session,
    ) -> None:
        """
        Mark processing as successful.

        Updates message and channel records.

        Args:
            message: ChannelQueueItem record
            result: Result from handler
            db: Database session
        """
        message.status = "COMPLETED"
        message.result = result

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateQueueProcessor] Failed to commit success for message {message.id}: {e}",
                exc_info=True,
            )
            raise

        logger.info(f"[CandidateQueueProcessor] ✅ Message {message.id} completed successfully")
