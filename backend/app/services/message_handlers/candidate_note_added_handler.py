"""Message Handler: Candidate Note Added

Triggers: candidate_note_added message (HR note created)
Purpose: Process notes and update Thunder Memory & Intelligence signals
Output: Note data propagated to Thunder for learning
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CandidateNoteAddedHandler:
    """Handle candidate notes and update Thunder Memory."""

    TIMEOUT_SECONDS = 10
    MAX_RETRIES = 2
    RETRY_DELAY_MINUTES = 5

    @staticmethod
    @time_bound(timeout_seconds=10)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process candidate note and update Thunder Memory.

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Candidate the note is for
                - note_id: ID of the note
                - content: Note content
                - category: Note category
                - created_by_id: User who created the note
                - created_by_name: Name of note creator
            db: Database session

        Returns:
            {
                'candidate_id': str,
                'note_id': str,
                'status': 'processed',
                'memory_updated': bool
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            candidate_id = payload.get('candidate_id')
            note_id = payload.get('note_id')
            content = payload.get('content', '')
            category = payload.get('category', 'General')
            created_by_name = payload.get('created_by_name', 'HR User')

            if not candidate_id:
                raise ValueError("Missing required field: candidate_id")
            if not note_id:
                raise ValueError("Missing required field: note_id")
            if not content:
                raise ValueError("Missing required field: content")

            # Log the note for Thunder Memory processing
            logger.info(
                f"[CandidateNoteAdded] Note #{note_id} for candidate {candidate_id} "
                f"category='{category}' by {created_by_name}"
            )

            # Queue update to Thunder Memory/Intelligence
            # Thunder will learn from this note in the next analysis cycle
            try:
                from app.services.message_queue_service import MessageQueueService
                MessageQueueService.enqueue(
                    task_name="thunder_memory_update",
                    data={
                        "candidate_id": candidate_id,
                        "signal_type": "note_added",
                        "content": content,
                        "category": category,
                        "source": "HR_NOTE",
                    }
                )
                memory_updated = True
            except Exception as e:
                logger.warning(f"Failed to queue Thunder memory update: {e}")
                memory_updated = False

            return {
                'candidate_id': candidate_id,
                'note_id': note_id,
                'status': 'processed',
                'memory_updated': memory_updated,
                'content_preview': content[:100] + '...' if len(content) > 100 else content,
            }

        except ValueError as e:
            logger.error(f"Invalid note payload: {e}")
            raise  # Non-retryable
        except Exception as e:
            logger.error(f"Failed to process note: {e}", exc_info=True)
            raise RuntimeError(f"Database error processing note: {e}")  # Retryable
