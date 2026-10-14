"""Channel Queue Worker - Process ChannelQueueItem records from database

Wrapper around ChannelProcessors that:
1. Queries pending ChannelQueueItem records
2. Extracts recipient and payload from each item
3. Routes to appropriate processor via dispatcher
4. Marks items COMPLETED or FAILED based on processor result
"""
import logging
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.services.channel_queue_service import ChannelQueueService
from app.workers.channel_processors import ChannelProcessors

logger = logging.getLogger(__name__)


def process_channel_queue(batch_size: int = 10) -> dict:
    """
    Process PENDING channel queue items.

    Extracts recipient/payload from ChannelQueueItem and routes to processors.
    """
    db = SessionLocal()
    processed = 0
    failed = 0

    try:
        # Get pending items
        items = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.status == "PENDING"
        ).limit(batch_size).all()

        logger.info(f"Processing {len(items)} pending channel queue items")

        for item in items:
            try:
                # Mark as processing
                ChannelQueueService.mark_processing(item.id, db)

                # Route to processor with explicit parameters
                success = ChannelProcessors.process_by_channel(
                    channel_type=item.channel_type,
                    item_id=item.id,
                    recipient=item.recipient,
                    payload=item.payload,
                    db=db,
                )

                if success:
                    processed += 1
                    logger.info(f"Processed {item.channel_type}: {item.id}")
                else:
                    failed += 1
                    logger.warning(f"Failed {item.channel_type}: {item.id}")

            except Exception as e:
                failed += 1
                logger.error(f"Error processing {item.id}: {e}", exc_info=True)
                # Mark as failed but retryable
                ChannelQueueService.mark_failed(
                    item.id,
                    str(e),
                    should_retry=True,
                    db=db
                )

        return {
            "processed": processed,
            "failed": failed,
            "total": len(items),
        }

    except Exception as e:
        logger.error(f"Error in channel queue worker: {e}", exc_info=True)
        return {"processed": 0, "failed": batch_size, "error": str(e)}

    finally:
        db.close()


if __name__ == "__main__":
    result = process_channel_queue()
    logger.info(f"Channel queue worker result: {result}")
