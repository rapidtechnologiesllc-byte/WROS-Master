"""
Candidate Event Bus - Publishes candidate lifecycle events to Thunder and other handlers.

Events published:
- candidate_created: New candidate entered system
- candidate_status_changed: Candidate status changed (Applied → Interview → Offer → Joined, etc.)
- candidate_data_changed: Candidate phone/email/skills/location updated
- candidate_rejected: Candidate rejected (90-day no-contact flag set)
- candidate_archived: Candidate archived (pauses Thunder)
- candidate_reactivated: Candidate reactivated (checks 90-day flag, resumes if clear)

Event format:
{
    "event_type": "candidate_created|candidate_status_changed|...",
    "candidate_id": "uuid",
    "timestamp": "2026-09-08T10:00:00Z",
    "data": {
        "old_status": "Applied",  # (for status_changed events)
        "new_status": "Interview",
        "status_change_reason": "Interview scheduled",
        "phone": "+1-555-0100",  # (for data_changed events)
        "email": "candidate@example.com",
        "skills": ["Python", "SQL"],
        # ... other fields
    }
}

All events route to MessageQueueService.enqueue() for async processing by handlers.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)


class CandidateEventBus:
    """Publishes candidate lifecycle events to message queue for handler processing."""

    # Event types
    EVENT_CANDIDATE_CREATED = "candidate_created"
    EVENT_CANDIDATE_STATUS_CHANGED = "candidate_status_changed"
    EVENT_CANDIDATE_DATA_CHANGED = "candidate_data_changed"
    EVENT_CANDIDATE_REJECTED = "candidate_rejected"
    EVENT_CANDIDATE_ARCHIVED = "candidate_archived"
    EVENT_CANDIDATE_REACTIVATED = "candidate_reactivated"
    EVENT_INTERVIEW_SCHEDULED = "interview_scheduled"

    @staticmethod
    def publish_event(
        event_type: str,
        candidate_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publish a candidate event to the message queue.

        Args:
            event_type: Type of event (from EVENT_* constants)
            candidate_id: ID of candidate that triggered event
            data: Event-specific data (status change reason, new values, etc.)

        Returns:
            Queue result: {"status": "queued", "message_id": "uuid", ...}

        Raises:
            ValueError: If event_type or candidate_id is invalid
            RuntimeError: If message queue enqueue fails
        """
        if not event_type:
            raise ValueError("event_type is required")
        if not candidate_id:
            raise ValueError("candidate_id is required")

        data = data or {}

        # Add common fields
        event_payload = {
            "event_type": event_type,
            "candidate_id": candidate_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }

        try:
            # Route event to message queue based on type
            # Map event to handler function name for discovery
            handler_function_name = CandidateEventBus._get_handler_function(event_type)

            result = MessageQueueService.enqueue(
                task_name=handler_function_name,
                data=event_payload,
                delay_seconds=0  # Immediate processing
            )

            logger.info(
                f"[EVENT BUS] Published {event_type} for candidate {candidate_id}: "
                f"queue_id={result.get('message_id')}"
            )

            return result

        except Exception as e:
            logger.error(
                f"[EVENT BUS] Failed to publish {event_type} for candidate {candidate_id}: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    def _get_handler_function(event_type: str) -> str:
        """Map event type to handler function name for message queue."""
        mapping = {
            CandidateEventBus.EVENT_CANDIDATE_CREATED: "handle_candidate_created",
            CandidateEventBus.EVENT_CANDIDATE_STATUS_CHANGED: "handle_candidate_status_changed",
            CandidateEventBus.EVENT_CANDIDATE_DATA_CHANGED: "handle_candidate_data_changed",
            CandidateEventBus.EVENT_CANDIDATE_REJECTED: "handle_candidate_rejected",
            CandidateEventBus.EVENT_CANDIDATE_ARCHIVED: "handle_candidate_archived",
            CandidateEventBus.EVENT_CANDIDATE_REACTIVATED: "handle_candidate_reactivated",
            CandidateEventBus.EVENT_INTERVIEW_SCHEDULED: "handle_interview_scheduled",
        }

        handler = mapping.get(event_type)
        if not handler:
            raise ValueError(f"Unknown event type: {event_type}")

        return handler

    # Convenience methods for publishing specific events

    @staticmethod
    def publish_created(candidate_id: str, **data) -> Dict[str, Any]:
        """Publish candidate_created event."""
        return CandidateEventBus.publish_event(
            CandidateEventBus.EVENT_CANDIDATE_CREATED,
            candidate_id,
            data
        )

    @staticmethod
    def publish_status_changed(
        candidate_id: str,
        old_status: str,
        new_status: str,
        reason: Optional[str] = None,
        **data
    ) -> Dict[str, Any]:
        """Publish candidate_status_changed event."""
        event_data = {
            "old_status": old_status,
            "new_status": new_status,
            "status_change_reason": reason or f"Status changed from {old_status} to {new_status}",
            **data
        }
        return CandidateEventBus.publish_event(
            CandidateEventBus.EVENT_CANDIDATE_STATUS_CHANGED,
            candidate_id,
            event_data
        )

    @staticmethod
    def publish_data_changed(
        candidate_id: str,
        changed_fields: Optional[Dict[str, Any]] = None,
        **data
    ) -> Dict[str, Any]:
        """
        Publish candidate_data_changed event when contact info or skills change.

        Args:
            candidate_id: ID of candidate
            changed_fields: Fields that were changed (for debugging)
            **data: New values (phone, email, skills, location, etc.)
        """
        event_data = {
            "changed_fields": changed_fields or list(data.keys()),
            **data
        }
        return CandidateEventBus.publish_event(
            CandidateEventBus.EVENT_CANDIDATE_DATA_CHANGED,
            candidate_id,
            event_data
        )

    @staticmethod
    def publish_rejected(
        candidate_id: str,
        reason: Optional[str] = None,
        **data
    ) -> Dict[str, Any]:
        """Publish candidate_rejected event (sets 90-day no-contact flag)."""
        event_data = {
            "rejection_reason": reason,
            **data
        }
        return CandidateEventBus.publish_event(
            CandidateEventBus.EVENT_CANDIDATE_REJECTED,
            candidate_id,
            event_data
        )

    @staticmethod
    def publish_archived(candidate_id: str, **data) -> Dict[str, Any]:
        """Publish candidate_archived event (pauses Thunder)."""
        return CandidateEventBus.publish_event(
            CandidateEventBus.EVENT_CANDIDATE_ARCHIVED,
            candidate_id,
            data
        )

    @staticmethod
    def publish_reactivated(candidate_id: str, **data) -> Dict[str, Any]:
        """Publish candidate_reactivated event (checks 90-day flag, may resume Thunder)."""
        return CandidateEventBus.publish_event(
            CandidateEventBus.EVENT_CANDIDATE_REACTIVATED,
            candidate_id,
            data
        )
