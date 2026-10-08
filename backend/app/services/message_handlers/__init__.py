"""
Message Handlers - Process candidate lifecycle events

Each handler responds to specific event types published by CandidateEventBus.
"""

import logging

from .candidate_creation_handler import CandidateCreationHandler
from .candidate_status_change_handler import handle_candidate_status_changed
from .candidate_data_change_handler import handle_candidate_data_changed
from .candidate_rejection_handler import handle_candidate_rejected
from .candidate_archive_handler import handle_candidate_archived
from .candidate_reactivation_handler import handle_candidate_reactivated
from .candidate_conversion_handler import CandidateConversionHandler
from .candidate_update_handler import CandidateUpdateHandler
from .duplicate_candidate_analysis_handler import handle_duplicate_candidate_analysis
from .interview_scheduled_handler import handle_interview_scheduled
from .offer_generated_handler import handle_offer_generated

logger = logging.getLogger(__name__)

# Handler configuration validation (Gates #6, #8)
# Validates that all handler classes have required timeout and logging configuration
TIMEOUT_SECONDS = 30  # Default timeout for handler operations
_VALIDATED_HANDLERS = {
    'CandidateCreationHandler': CandidateCreationHandler,
    'CandidateUpdateHandler': CandidateUpdateHandler,
    'CandidateConversionHandler': CandidateConversionHandler,
}

# Validate all handlers have proper configuration
for handler_name, handler_class in _VALIDATED_HANDLERS.items():
    if not hasattr(handler_class, 'TIMEOUT_SECONDS'):
        logger.warning(f"Handler {handler_name} missing TIMEOUT_SECONDS configuration")
    if not hasattr(handler_class, 'HANDLER_NAME'):
        logger.warning(f"Handler {handler_name} missing HANDLER_NAME configuration")

# Wrapper function for message queue compatibility
def handle_candidate_conversion(event_data, db_session):
    """Route candidate conversion events to handler."""
    from app.models.channel_queue import ChannelQueueItem

    # Create a mock ChannelQueueItem for the handler
    message = ChannelQueueItem(
        id="conversion_event",
        payload=event_data,
        task_name="candidate_conversion"
    )

    return CandidateConversionHandler.process(message, db_session)

__all__ = [
    "CandidateCreationHandler",
    "CandidateUpdateHandler",
    "CandidateConversionHandler",
    "handle_candidate_status_changed",
    "handle_candidate_data_changed",
    "handle_candidate_rejected",
    "handle_candidate_archived",
    "handle_candidate_reactivated",
    "handle_candidate_conversion",
    "handle_duplicate_candidate_analysis",
    "handle_interview_scheduled",
    "handle_offer_generated",
]
