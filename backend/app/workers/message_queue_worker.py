"""Message Queue Worker - Orchestrates message processing through SLM to channels

Worker runs every 2 minutes and:
1. Fetches PENDING messages
2. Marks as SLM_PROCESSING
3. Calls SLM orchestration to decide which channels to trigger
4. SLM creates channel queue items for each channel
5. Updates message status to CHANNEL_QUEUED
6. Logs everything

Then a separate channel processor worker:
1. Fetches channel queue items by channel type
2. Processes items (sends emails, creates approvals, etc.)
3. Marks items as COMPLETED/FAILED
"""
import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import DATABASE_URL
from app.services.message_queue_service import MessageQueueService
from app.services.slm_orchestration_service import SLMOrchestrationService

logger = logging.getLogger(__name__)

# Set up database connection for worker
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def process_message_queue() -> None:
    """
    Main worker function - orchestrates message processing through SLM to channels.

    Called every 2 minutes via scheduler.
    Processes PENDING messages in FIFO order (oldest first).
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

        logger.info(f"Processing {len(pending_messages)} pending messages...")

        processed_count = 0
        failed_count = 0

        for message in pending_messages:
            message_id = message["id"]
            message_type = message["type"]
            payload = message["payload"]
            resource_id = message["resource_id"]

            try:
                # Mark as SLM_PROCESSING
                logger.debug(f"Marking message as SLM_PROCESSING: {message_id}")
                MessageQueueService.mark_processing(message_id, db)

                # Call SLM orchestration to create channel queue items
                logger.info(
                    f"Orchestrating message: {message_id} type={message_type} "
                    f"resource_id={resource_id}"
                )

                result = SLMOrchestrationService.orchestrate_message(
                    message_id=message_id,
                    queue_type=message_type,
                    payload=payload,
                    resource_id=resource_id,
                    db=db,
                )

                channels_created = result.get("channel_count", 0)
                logger.info(
                    f"Message orchestrated successfully: {message_id} "
                    f"created {channels_created} channel queue items"
                )

                # Mark as CHANNEL_QUEUED (SLM decided what channels to trigger)
                # Update message status to indicate it's queued in channels
                from app.models.message_queue import MessageQueue

                msg = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
                if msg:
                    msg.status = "CHANNEL_QUEUED"
                    msg.updated_at = datetime.utcnow()
                    db.commit()

                processed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to orchestrate message: {message_id} error: {e}",
                    exc_info=True,
                )

                # Mark message as failed (will retry next cycle)
                try:
                    MessageQueueService.mark_failed(
                        message_id,
                        f"SLM orchestration failed: {str(e)}",
                        should_retry=True,
                        db=db,
                    )
                except Exception as retry_error:
                    logger.error(
                        f"Failed to mark message as failed: {retry_error}",
                        exc_info=True,
                    )

        elapsed_time = time.time() - start_time

        logger.info(
            f"Message queue worker completed: "
            f"processed={processed_count} failed={failed_count} "
            f"elapsed_time={elapsed_time:.2f}s"
        )

    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
    finally:
        db.close()


def process_channel_queues() -> None:
    """
    Channel processor worker - processes channel queue items.

    Called every 1 minute.
    Processes pending items for all channel types.
    """
    from app.services.channel_queue_service import ChannelQueueService
    from app.workers.channel_processors import ChannelProcessors

    db = SessionLocal()
    start_time = time.time()

    try:
        logger.info("Channel queue processor starting...")

        # List of all channels to process
        channels = [
            ChannelQueueService.CHANNEL_EMAIL,
            ChannelQueueService.CHANNEL_WHATSAPP,
            ChannelQueueService.CHANNEL_SMS,
            ChannelQueueService.CHANNEL_SLACK,
            ChannelQueueService.CHANNEL_THUNDER,
            ChannelQueueService.CHANNEL_APPROVAL,
            ChannelQueueService.CHANNEL_COMMISSION,
            ChannelQueueService.CHANNEL_CRM,
            ChannelQueueService.CHANNEL_DASHBOARD,
            ChannelQueueService.CHANNEL_CALENDAR,
            ChannelQueueService.CHANNEL_SIGNATURE,
        ]

        total_processed = 0
        total_failed = 0

        for channel_type in channels:
            try:
                # Fetch pending items for this channel
                items = ChannelQueueService.get_pending_by_channel(
                    channel_type=channel_type,
                    limit=50,
                    db=db,
                )

                if not items:
                    continue

                logger.info(f"Processing {len(items)} items for channel: {channel_type}")

                for item in items:
                    item_id = item["id"]

                    try:
                        # Mark as processing
                        ChannelQueueService.mark_processing(item_id, db)

                        # Dispatch to appropriate processor
                        success = ChannelProcessors.process_by_channel(
                            channel_type=channel_type,
                            item_id=item_id,
                            item_data=item,
                            db=db,
                        )

                        if success:
                            total_processed += 1
                        else:
                            total_failed += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to process channel item: {item_id} error: {e}",
                            exc_info=True,
                        )
                        total_failed += 1

                        # Mark as failed
                        try:
                            ChannelQueueService.mark_failed(
                                item_id,
                                str(e),
                                should_retry=True,
                                db=db,
                            )
                        except Exception as mark_error:
                            logger.error(f"Failed to mark item as failed: {mark_error}")

            except Exception as e:
                logger.error(f"Failed to process channel {channel_type}: {e}", exc_info=True)

        elapsed_time = time.time() - start_time

        logger.info(
            f"Channel queue processor completed: "
            f"processed={total_processed} failed={total_failed} "
            f"elapsed_time={elapsed_time:.2f}s"
        )

    except Exception as e:
        logger.error(f"Channel processor worker failed: {e}", exc_info=True)
    finally:
        db.close()


# ==================== ENTRY POINTS ====================

if __name__ == "__main__":
    # Test: Process one cycle of messages
    logger.info("Starting message queue worker...")
    process_message_queue()
    logger.info("Message queue worker finished.")

    logger.info("Starting channel processor worker...")
    process_channel_queues()
    logger.info("Channel processor worker finished.")
