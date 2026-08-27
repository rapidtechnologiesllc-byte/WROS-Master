"""Message Queue Worker - Background process for processing queued messages.

Runs periodically (every 5 minutes) to:
1. Fetch PENDING and RETRYING messages
2. Execute message processing based on type
3. Mark as COMPLETED or schedule retry
4. Log all attempts to audit trail
"""

import logging
import time
from datetime import datetime
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.message_queue_service import MessageQueueService, MAX_RETRIES
from app.models.message_queue import MessageQueue

logger = logging.getLogger(__name__)

# Message type handlers registry
MESSAGE_HANDLERS = {}


def register_handler(message_type: str, handler_func):
    """
    Register a handler for a message type.

    Args:
        message_type: Type of message (e.g., 'candidate_added', 'thunder_email')
        handler_func: Async function to handle this message type
    """
    MESSAGE_HANDLERS[message_type] = handler_func
    logger.info(f"Registered handler for message type: {message_type}")


async def process_message(db: Session, message: MessageQueue) -> bool:
    """
    Process a single message.

    Args:
        db: Database session
        message: MessageQueue object to process

    Returns:
        True if successful, False if should retry

    Raises:
        Exception: If processing fails permanently
    """
    message_id = message.id
    message_type = message.type
    payload = message.payload

    start_time = time.time()

    try:
        # Mark as processing
        MessageQueueService.mark_processing(db, message_id)

        logger.info(
            f"Processing message: id={message_id}, type={message_type}, "
            f"resource_id={message.resource_id}"
        )

        # Get handler for this message type
        handler = MESSAGE_HANDLERS.get(message_type)

        if not handler:
            raise Exception(
                f"No handler registered for message type: {message_type}. "
                f"Available handlers: {', '.join(MESSAGE_HANDLERS.keys())}"
            )

        # Execute handler
        result = handler(payload, message.resource_id, db)

        # If result is a coroutine, await it
        if hasattr(result, '__await__'):
            result = await result

        if not result:
            raise Exception(f"Handler returned false/null for message: {message_id}")

        # Mark as completed
        MessageQueueService.mark_completed(db, message_id)

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Message processed successfully: id={message_id}, type={message_type}, "
            f"duration_ms={duration_ms}"
        )

        return True

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"{str(e)}"

        logger.error(
            f"Failed to process message: id={message_id}, type={message_type}, "
            f"error={error_msg}, duration_ms={duration_ms}, retry_count={message.retry_count}",
            exc_info=True
        )

        # Decide whether to retry or fail permanently
        if message.retry_count < MAX_RETRIES:
            try:
                MessageQueueService.schedule_retry(db, message_id, error_msg)
                logger.warning(
                    f"Message scheduled for retry: id={message_id}, "
                    f"next_attempt={message.retry_count + 1}/{MAX_RETRIES}"
                )
                return False  # Will retry

            except Exception as retry_error:
                logger.error(
                    f"Failed to schedule retry for message: id={message_id}, error={retry_error}",
                    exc_info=True
                )
                # Mark as failed since we couldn't schedule retry
                MessageQueueService.mark_failed(db, message_id, f"Retry scheduling failed: {str(retry_error)}")
                return False

        else:
            # Max retries exceeded
            try:
                MessageQueueService.mark_failed(db, message_id, error_msg)
                logger.error(
                    f"Message marked as FAILED (max retries exceeded): id={message_id}, "
                    f"type={message_type}"
                )
                return False

            except Exception as fail_error:
                logger.error(
                    f"Failed to mark message as failed: id={message_id}, error={fail_error}",
                    exc_info=True
                )
                return False


async def run_message_queue_worker(tenant_id: int = 1, batch_size: int = 100):
    """
    Main worker loop - runs periodically to process queued messages.

    Args:
        tenant_id: Tenant ID to process messages for (default: 1)
        batch_size: Maximum messages to process per cycle

    Runs:
        - Fetches pending/retrying messages
        - Processes each message
        - Logs results
        - Continues indefinitely
    """
    db = SessionLocal()

    try:
        logger.info(f"Message queue worker started for tenant_id={tenant_id}")

        while True:
            try:
                # Fetch messages to process
                messages = MessageQueueService.get_pending_messages(
                    db, tenant_id, limit=batch_size
                )

                if not messages:
                    logger.debug(f"No messages to process (tenant_id={tenant_id})")
                else:
                    logger.info(f"Processing {len(messages)} messages (tenant_id={tenant_id})")

                    # Process each message
                    success_count = 0
                    retry_count = 0
                    fail_count = 0

                    for message in messages:
                        try:
                            result = await process_message(db, message)
                            if result:
                                success_count += 1
                            else:
                                retry_count += 1

                        except Exception as e:
                            fail_count += 1
                            logger.error(
                                f"Unexpected error processing message {message.id}: {str(e)}",
                                exc_info=True
                            )

                    logger.info(
                        f"Batch complete: success={success_count}, "
                        f"retry={retry_count}, fail={fail_count}"
                    )

                # Wait 5 minutes before next batch
                logger.debug("Waiting 5 minutes before next message batch...")
                time.sleep(300)

            except Exception as e:
                logger.error(f"Error in message queue worker loop: {str(e)}", exc_info=True)
                # Wait a bit before retrying
                time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Message queue worker interrupted")

    except Exception as e:
        logger.error(f"Unexpected error in message queue worker: {str(e)}", exc_info=True)

    finally:
        db.close()
        logger.info("Message queue worker stopped")


# Example handlers (to be implemented per message type)

def handle_candidate_added(payload: Dict[str, Any], resource_id: Optional[str], db: Session) -> bool:
    """
    Handle 'candidate_added' message type.

    Args:
        payload: Message payload with candidate details
        resource_id: Candidate ID
        db: Database session

    Returns:
        True if successfully processed
    """
    logger.info(f"Processing candidate_added: resource_id={resource_id}")
    # TODO: Implement candidate processing logic
    # Examples:
    # - Send welcome email
    # - Trigger Thunder autonomous recruitment
    # - Create activity log entry
    return True


def handle_thunder_email(payload: Dict[str, Any], resource_id: Optional[str], db: Session) -> bool:
    """
    Handle 'thunder_email' message type.

    Args:
        payload: Message payload with email details
        resource_id: Email ID or candidate ID
        db: Database session

    Returns:
        True if successfully processed
    """
    logger.info(f"Processing thunder_email: resource_id={resource_id}")
    # TODO: Implement email sending logic
    # - Retrieve email details from payload
    # - Send via email service
    # - Update email status
    return True


def handle_flash_agent_action(payload: Dict[str, Any], resource_id: Optional[str], db: Session) -> bool:
    """
    Handle 'flash_agent_action' message type.

    Args:
        payload: Message payload with agent action details
        resource_id: Agent ID or action ID
        db: Database session

    Returns:
        True if successfully processed
    """
    logger.info(f"Processing flash_agent_action: resource_id={resource_id}")
    # TODO: Implement agent action logic
    # - Execute agent command
    # - Track execution
    # - Update agent state
    return True


# Register default handlers
register_handler("candidate_added", handle_candidate_added)
register_handler("thunder_email", handle_thunder_email)
register_handler("flash_agent_action", handle_flash_agent_action)
