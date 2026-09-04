"""Channel Processors - Route messages to channel-specific handlers

Maps message types and queue types to processors that handle async execution.
"""

from app.services.channel_processors.candidate_queue_processor import CandidateQueueProcessor

# Processor mapping: queue_type -> processor class
QUEUE_PROCESSORS = {
    "CANDIDATE_QUEUE": CandidateQueueProcessor,
    # "EMAIL_QUEUE": EmailQueueProcessor,  # Future
    # "SYSTEM_QUEUE": SystemQueueProcessor,  # Future
}


def get_processor(queue_type: str):
    """Get processor for a queue type."""
    return QUEUE_PROCESSORS.get(queue_type)


__all__ = ["CandidateQueueProcessor", "get_processor", "QUEUE_PROCESSORS"]
