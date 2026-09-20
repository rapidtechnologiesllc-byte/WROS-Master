"""Synchronous candidate creation wrapper for services that need immediate response.

For services like public_chat that need a Candidate object immediately
(to create conversation in same request), this module provides sync-wait
functionality that queues creation and polls for completion.
"""

import logging
import time
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.candidate_creation_wrapper import queue_candidate_creation
from app.models.channel_queue import ChannelQueueItem

logger = logging.getLogger(__name__)

SYNC_WAIT_TIMEOUT_SECONDS = 10  # Max wait for candidate creation
SYNC_WAIT_POLL_INTERVAL_SECONDS = 0.5  # Poll every 500ms


def queue_and_wait_for_candidate(
    db: Session,
    email: str,
    first_name: str,
    last_name: str,
    *,
    tenant_id: int = 1,
    source: str = "unknown",
    mobile: Optional[str] = None,
    timeout_seconds: int = SYNC_WAIT_TIMEOUT_SECONDS,
) -> Tuple[Optional[Candidate], str]:
    """
    Queue candidate creation and wait synchronously for completion.

    This is a compromise for services (like public_chat) that need
    a Candidate object immediately to continue processing in the same
    request. The handler processes the queue message and creates the
    candidate, while this function polls for completion.

    Args:
        db: Database session
        email: Candidate email
        first_name: First name
        last_name: Last name
        tenant_id: Tenant context
        source: Creation source
        mobile: Phone number (optional)
        timeout_seconds: Max seconds to wait for completion

    Returns:
        Tuple of (Candidate object or None, message_id)
        - If handler completes: (Candidate, message_id)
        - If timeout: (None, message_id) - caller must handle async polling
    """
    # Queue candidate creation
    queue_result = queue_candidate_creation(
        db=db,
        email=email,
        first_name=first_name,
        last_name=last_name,
        tenant_id=tenant_id,
        source=source,
        mobile=mobile,
    )

    message_id = queue_result.get('message_id')
    logger.info(f"[SyncWait] Queued candidate creation: {email}, message_id={message_id}")

    # Poll for handler completion
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time

        # Check if message is COMPLETED
        queue_item = db.query(ChannelQueueItem).filter(
            ChannelQueueItem.message_id == message_id
        ).first()

        if not queue_item:
            logger.warning(f"[SyncWait] Queue item not found: {message_id}")
            return None, message_id

        if queue_item.status == "COMPLETED":
            # Handler completed - candidate should exist
            result = queue_item.result or {}
            candidate_id = result.get('candidate_id')

            if candidate_id:
                candidate = db.query(Candidate).filter(
                    Candidate.candidateID == candidate_id
                ).first()

                if candidate:
                    logger.info(
                        f"[SyncWait] ✅ Candidate created successfully: {candidate_id} "
                        f"(elapsed: {elapsed:.2f}s)"
                    )
                    return candidate, message_id

            logger.warning(f"[SyncWait] Handler completed but candidate not found")
            return None, message_id

        if queue_item.status == "FAILED":
            error = queue_item.error or "Unknown error"
            logger.error(f"[SyncWait] Handler failed: {error}")
            return None, message_id

        # Timeout check
        if elapsed > timeout_seconds:
            logger.warning(
                f"[SyncWait] Timeout waiting for candidate creation ({elapsed:.2f}s > {timeout_seconds}s). "
                f"Message {message_id} still in status: {queue_item.status}. "
                f"Candidate creation will complete asynchronously."
            )
            return None, message_id

        # Sleep before next poll
        time.sleep(SYNC_WAIT_POLL_INTERVAL_SECONDS)
