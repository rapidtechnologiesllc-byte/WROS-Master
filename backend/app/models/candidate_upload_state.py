"""
Candidate upload state machine and constants.

Defines all valid states and transitions for the progressive upload flow.
"""

from enum import Enum

# ============================================
# Candidate Upload State Machine
# ============================================

class CandidateUploadState(str, Enum):
    """Valid states for candidate uploads."""

    CREATED = "created"
    """Candidate created, waiting for documents to be uploaded."""

    UPLOADING = "uploading"
    """User is actively uploading documents."""

    UPLOAD_COMPLETE = "upload_complete"
    """All expected documents uploaded, queued for processing."""

    QUEUED = "queued"
    """Waiting in Celery queue for Thunder to process."""

    PROCESSING = "processing"
    """Thunder is actively processing candidate."""

    COMPLETE = "complete"
    """Thunder processing finished successfully."""

    UPLOAD_FAILED = "upload_failed"
    """Upload failed (network, validation, etc). User can retry."""

    PROCESSING_FAILED = "processing_failed"
    """Thunder processing failed. Requires manual review."""

    ABANDONED = "abandoned"
    """No documents uploaded within 24 hour timeout."""

    CANCELLED = "cancelled"
    """User or admin cancelled the upload."""


# ============================================
# Valid State Transitions
# ============================================

VALID_TRANSITIONS = {
    CandidateUploadState.CREATED: [
        CandidateUploadState.UPLOADING,
        CandidateUploadState.CANCELLED,
    ],
    CandidateUploadState.UPLOADING: [
        CandidateUploadState.UPLOAD_COMPLETE,
        CandidateUploadState.UPLOAD_FAILED,
        CandidateUploadState.CANCELLED,
        CandidateUploadState.ABANDONED,  # Timeout
    ],
    CandidateUploadState.UPLOAD_COMPLETE: [
        CandidateUploadState.QUEUED,
        CandidateUploadState.UPLOADING,  # Resume/retry
        CandidateUploadState.CANCELLED,
    ],
    CandidateUploadState.QUEUED: [
        CandidateUploadState.PROCESSING,
        CandidateUploadState.UPLOAD_FAILED,  # If Celery fails to start
    ],
    CandidateUploadState.PROCESSING: [
        CandidateUploadState.COMPLETE,
        CandidateUploadState.PROCESSING_FAILED,
    ],
    CandidateUploadState.COMPLETE: [],  # Terminal state
    CandidateUploadState.UPLOAD_FAILED: [
        CandidateUploadState.UPLOADING,  # Retry
        CandidateUploadState.CANCELLED,
    ],
    CandidateUploadState.PROCESSING_FAILED: [
        CandidateUploadState.QUEUED,  # Manual retry
    ],
    CandidateUploadState.ABANDONED: [
        CandidateUploadState.UPLOADING,  # Resume
    ],
    CandidateUploadState.CANCELLED: [],  # Terminal state
}


def is_valid_transition(from_state: CandidateUploadState, to_state: CandidateUploadState) -> bool:
    """
    Check if transition is valid.

    Args:
        from_state: Current state
        to_state: Target state

    Returns:
        True if transition is allowed, False otherwise
    """
    return to_state in VALID_TRANSITIONS.get(from_state, [])


# ============================================
# Upload Configuration
# ============================================

class UploadConfig:
    """Configuration for progressive uploads."""

    # Timeout when documents are idle (no new uploads)
    UPLOAD_IDLE_TIMEOUT_MINUTES = 2

    # Total timeout from upload start to completion
    UPLOAD_TOTAL_TIMEOUT_HOURS = 24

    # Minimum documents before queueing
    MIN_DOCUMENTS_TO_QUEUE = 1

    # Maximum documents per candidate
    MAX_DOCUMENTS_PER_CANDIDATE = 50

    # Maximum file size (100 MB)
    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

    # Total maximum upload size per candidate (1 GB)
    MAX_TOTAL_SIZE_BYTES = 1024 * 1024 * 1024

    # Scheduler check interval (minutes)
    SCHEDULER_INTERVAL_MINUTES = 2

    # Cleanup: delete uploads older than this
    CLEANUP_STALE_UPLOADS_DAYS = 30

    # Cleanup: delete failed uploads older than this
    CLEANUP_FAILED_UPLOADS_DAYS = 7


# ============================================
# Upload Status Response Schema
# ============================================

class UploadStatusResponse:
    """Schema for upload status responses."""

    def __init__(
        self,
        candidate_id: str,
        status: CandidateUploadState,
        documents_uploaded: int,
        expected_documents: int,
        last_document_at: str = None,
        first_upload_at: str = None,
        processing_queued_at: str = None,
        can_resume: bool = False,
        error_message: str = None,
    ):
        self.candidate_id = candidate_id
        self.status = status
        self.documents_uploaded = documents_uploaded
        self.expected_documents = expected_documents
        self.last_document_at = last_document_at
        self.first_upload_at = first_upload_at
        self.processing_queued_at = processing_queued_at
        self.can_resume = can_resume
        self.error_message = error_message

        # Calculate progress
        if expected_documents > 0:
            self.progress_percent = (documents_uploaded / expected_documents) * 100
        else:
            self.progress_percent = 0

    def to_dict(self):
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "documents_uploaded": self.documents_uploaded,
            "expected_documents": self.expected_documents,
            "progress_percent": self.progress_percent,
            "last_document_at": self.last_document_at,
            "first_upload_at": self.first_upload_at,
            "processing_queued_at": self.processing_queued_at,
            "can_resume": self.can_resume,
            "error_message": self.error_message,
        }
