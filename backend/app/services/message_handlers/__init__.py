"""
Message Handlers - Process candidate lifecycle events

Each handler responds to specific event types published by CandidateEventBus.
"""

import logging

from .candidate_status_change_handler import handle_candidate_status_changed
from .candidate_data_change_handler import handle_candidate_data_changed
from .candidate_rejection_handler import handle_candidate_rejected
from .candidate_archive_handler import handle_candidate_archived
from .candidate_reactivation_handler import handle_candidate_reactivated
from .candidate_conversion_handler import CandidateConversionHandler
from .candidate_update_handler import CandidateUpdateHandler
from .duplicate_candidate_analysis_handler import handle_duplicate_candidate_analysis
from .offer_generated_handler import handle_offer_generated

logger = logging.getLogger(__name__)

# Handler configuration validation (Gates #6, #8)
# Validates that all handler classes have required timeout and logging configuration
TIMEOUT_SECONDS = 30  # Default timeout for handler operations
_VALIDATED_HANDLERS = {
    'CandidateUpdateHandler': CandidateUpdateHandler,
    'CandidateConversionHandler': CandidateConversionHandler,
}

# Every handler declares its timeout and name; a missing one fails at import, not in production
for handler_name, handler_class in _VALIDATED_HANDLERS.items():
    missing = [attr for attr in ("TIMEOUT_SECONDS", "HANDLER_NAME") if not hasattr(handler_class, attr)]
    if missing:
        raise RuntimeError(f"Handler {handler_name} missing {', '.join(missing)} configuration")

__all__ = [
    "CandidateUpdateHandler",
    "CandidateConversionHandler",
    "handle_candidate_status_changed",
    "handle_candidate_data_changed",
    "handle_candidate_rejected",
    "handle_candidate_archived",
    "handle_candidate_reactivated",
    "handle_duplicate_candidate_analysis",
    "handle_offer_generated",
]
