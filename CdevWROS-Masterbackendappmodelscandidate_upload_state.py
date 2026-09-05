from enum import Enum


class CandidateUploadState(str, Enum):
    """
    State machine for candidate document upload lifecycle.

    States:
    - UPLOADING: Initial state, documents being uploaded
    - QUEUED: All documents uploaded, waiting for processing
    - PROCESSING: Celery task actively processing documents
    - COMPLETE: Processing finished successfully
    - ERROR: Processing failed
    - CANCELLED: User cancelled the upload
    - ABANDONED: No activity for 7+ days (scheduled cleanup candidate)
    """
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"
