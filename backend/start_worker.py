#!/usr/bin/env python
"""
Message Queue Worker Starter
Runs the message queue processor in an infinite loop every 30 seconds.
"""
import sys
import time
import signal
import logging
from app.workers.message_queue_worker import process_message_queue

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [WORKER] - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

_shutdown_requested = False

def _handle_shutdown_signal(signum, frame):
    """SIGTERM (systemctl stop / container stop) and SIGINT both request a
    clean exit after the current cycle finishes, instead of being killed
    mid-cycle."""
    global _shutdown_requested
    logger.info(f"[WORKER] Received signal {signum}, will stop after current cycle...")
    _shutdown_requested = True

def main():
    """Start the background worker process."""
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    logger.info("[WORKER] Starting message queue worker...")
    logger.info("[WORKER] Processing queue every 30 seconds")
    logger.info("[WORKER] Press Ctrl+C to stop")

    cycle_count = 0

    try:
        while not _shutdown_requested:
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

            # Wait up to 30 seconds before the next cycle, but wake immediately on shutdown
            for _ in range(30):
                if _shutdown_requested:
                    break
                time.sleep(1)

        logger.info("[WORKER] Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"[WORKER] Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
