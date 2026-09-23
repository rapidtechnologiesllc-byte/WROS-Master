#!/usr/bin/env python
"""
Message Queue Worker Starter
Runs the message queue processor in an infinite loop every 30 seconds.
"""
import sys
import time
import logging
from app.workers.message_queue_worker import process_message_queue

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [WORKER] - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Start the background worker process."""
    logger.info("[WORKER] Starting message queue worker...")
    logger.info("[WORKER] Processing queue every 30 seconds")
    logger.info("[WORKER] Press Ctrl+C to stop")

    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            try:
                logger.debug(f"[WORKER] Cycle {cycle_count}: Processing message queue...")
                result = process_message_queue(batch_size=10, timeout_minutes=30)

                if result.get('messages_processed', 0) > 0:
                    logger.info(f"[WORKER] Cycle {cycle_count}: Processed {result['messages_processed']} messages")
                else:
                    logger.debug(f"[WORKER] Cycle {cycle_count}: No messages to process")

            except Exception as e:
                logger.error(f"[WORKER] Cycle {cycle_count}: Error processing queue: {e}", exc_info=True)

            # Wait 30 seconds before next cycle
            time.sleep(30)

    except KeyboardInterrupt:
        logger.info("[WORKER] Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"[WORKER] Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
