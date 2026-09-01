"""Queue Routing - Role-template driven message routing (STRICT API CONTRACT)

All message queue assignments must be determined by role templates,
NOT hardcoded. Uses STRICT API CONTRACT definitions from api_contract.py.
No deviation from contract allowed.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Import from contract - single source of truth
from app.contracts.api_contract import (
    QUEUE_ROUTING_CONFIG,
    MessageType,
    QueueType,
    validate_queue_routing_config,
    get_default_queue
)


class QueueRouter:
    """Routes messages to queues based on STRICT API CONTRACT and role templates."""

    @staticmethod
    def get_queue_for_message(
        message_type: str,
        db: Optional[Session] = None,
    ) -> str:
        """
        Determine queue type for a message based on STRICT API CONTRACT.

        Args:
            message_type: Type of message (e.g., 'candidate_created')
            db: Database session (optional, for future role-template integration)

        Returns:
            Queue type string (THUNDER_QUEUE, EMAIL_QUEUE, etc.)

        Raises:
            ValueError: If message type not in contract
        """
        try:
            # Get routing config from contract (strict validation)
            config = validate_queue_routing_config(message_type)

            # Use default queue from contract
            # Future: Can integrate with role templates to allow per-role queue routing
            logger.info(f"Queue routing for {message_type}: {config.default_queue.value}")
            return config.default_queue.value

        except ValueError as e:
            logger.error(f"Queue routing validation failed for {message_type}: {e}")
            raise  # Fail fast - per FAIL FAST principle in CLAUDE.md
        except Exception as e:
            logger.error(f"Unexpected error in queue routing: {e}", exc_info=True)
            raise  # Fail fast
