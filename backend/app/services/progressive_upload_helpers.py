"""
Shared helpers to eliminate code duplication in progressive upload service.

Extracts common patterns:
- Database queries
- Error handling
- State validation
- Logging
- Email notifications
"""

import logging
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.candidate import Candidate, CandidateDocument
from app.models.candidate_upload_state import CandidateUploadState, is_valid_transition
from app.services.email_service import send_email

logger = logging.getLogger(__name__)


# ============================================
# DATABASE QUERY HELPERS (eliminate duplication)
# ============================================

def get_candidate(
    db: Session,
    candidate_id: str,
    tenant_id: int,
) -> Optional[Candidate]:
    """Get candidate by ID with tenant filtering."""
    return db.query(Candidate).filter(
        Candidate.candidateID == candidate_id,
        Candidate.tenant_id == tenant_id,
    ).first()


def get_document_count(db: Session, candidate_id: str) -> int:
    """Count documents for candidate."""
    return db.query(CandidateDocument).filter(
        CandidateDocument.candidateID == candidate_id,
    ).count()


def get_total_document_size(db: Session, candidate_id: str) -> int:
    """Get total file size for candidate."""
    return db.query(func.sum(CandidateDocument.file_size_bytes)).filter(
        CandidateDocument.candidateID == candidate_id,
    ).scalar() or 0


def get_last_document(db: Session, candidate_id: str) -> Optional[CandidateDocument]:
    """Get most recent document for candidate."""
    return db.query(CandidateDocument).filter(
        CandidateDocument.candidateID == candidate_id,
    ).order_by(CandidateDocument.uploaded_at.desc()).first()


def get_next_upload_sequence(db: Session, candidate_id: str) -> int:
    """Get next upload sequence number."""
    max_seq = db.query(func.max(CandidateDocument.upload_sequence)).filter(
        CandidateDocument.candidateID == candidate_id,
    ).scalar() or 0
    return max_seq + 1


# ============================================
# STATE VALIDATION HELPERS (eliminate duplication)
# ============================================

def validate_state_transition(
    current_state: CandidateUploadState,
    target_state: CandidateUploadState,
    raise_error: bool = True,
) -> bool:
    """
    Validate state transition is allowed.

    Args:
        current_state: Current state
        target_state: Target state
        raise_error: Raise ValueError if invalid

    Returns:
        True if valid, False otherwise

    Raises:
        ValueError: If invalid and raise_error=True
    """
    if not is_valid_transition(current_state, target_state):
        msg = f"Invalid transition: {current_state.value} → {target_state.value}"
        if raise_error:
            raise ValueError(msg)
        logger.warning(msg)
        return False
    return True


def validate_upload_state(candidate: Candidate) -> Tuple[bool, str]:
    """
    Validate candidate is in valid upload state.

    Returns:
        (is_valid, error_message)
    """
    if not candidate:
        return False, "Candidate not found"

    if candidate.upload_locked:
        return False, "Upload locked. Another process is modifying this candidate."

    current_state = CandidateUploadState(candidate.upload_status)
    if current_state not in [CandidateUploadState.CREATED, CandidateUploadState.UPLOADING]:
        return False, f"Cannot upload in state: {current_state.value}"

    return True, None


# ============================================
# LOGGING HELPERS (eliminate duplication)
# ============================================

def log_upload_event(
    event: str,
    candidate_id: str,
    message: str,
    level: str = "info",
):
    """
    Log upload event with consistent format.

    Args:
        event: Event name (UPLOAD, SCHEDULER, CELERY, CLEANUP)
        candidate_id: Candidate ID
        message: Event message
        level: Log level (info, warning, error)
    """
    formatted = f"[{event}] {candidate_id}: {message}"

    if level == "error":
        logger.error(formatted)
    elif level == "warning":
        logger.warning(formatted)
    else:
        logger.info(formatted)


# ============================================
# EMAIL NOTIFICATION HELPERS (eliminate duplication)
# ============================================

def send_upload_email(
    recipient: str,
    first_name: str,
    template: str,
    context: dict = None,
):
    """
    Send upload-related email with error handling.

    Args:
        recipient: Email address
        first_name: User's first name
        template: Email template name
        context: Additional context variables
    """
    if context is None:
        context = {}

    context["first_name"] = first_name

    try:
        send_email(
            recipient=recipient,
            subject=_get_email_subject(template),
            template=template,
            context=context,
        )
    except Exception as e:
        log_upload_event(
            "EMAIL",
            recipient,
            f"Failed to send {template}: {str(e)}",
            level="error",
        )
        # Don't raise - email failure shouldn't block upload


def _get_email_subject(template: str) -> str:
    """Get email subject for template."""
    subjects = {
        "application_started": "Application Received - Start Upload",
        "upload_complete": "Upload Complete - Processing Started",
        "processing_complete": "Application Processing Complete",
        "processing_failed": "Processing Error - Action Required",
    }
    return subjects.get(template, "Application Update")


# ============================================
# VALIDATION HELPERS (eliminate duplication)
# ============================================

def validate_file(
    file_size_bytes: int,
    max_single_file: int,
    total_size_so_far: int,
    max_total_size: int,
) -> Tuple[bool, str]:
    """
    Validate file size constraints.

    Returns:
        (is_valid, error_message)
    """
    if file_size_bytes == 0:
        return False, "File is empty"

    if file_size_bytes > max_single_file:
        return False, f"File exceeds {max_single_file / 1024 / 1024}MB limit"

    if total_size_so_far + file_size_bytes > max_total_size:
        return False, f"Total upload exceeds {max_total_size / 1024 / 1024}GB limit"

    return True, None


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format."""
    if not email or "@" not in email:
        return False, "Invalid email format"
    return True, None


def validate_name(name: str) -> Tuple[bool, str]:
    """Validate name is not empty."""
    if not name or not name.strip():
        return False, "Name is required"
    return True, None


# ============================================
# STATE UPDATE HELPERS (eliminate duplication)
# ============================================

def update_candidate_state(
    db: Session,
    candidate: Candidate,
    new_state: CandidateUploadState,
    error_message: str = None,
) -> bool:
    """
    Update candidate state with error handling.

    Args:
        db: Database session
        candidate: Candidate to update
        new_state: Target state
        error_message: Error message if state is failure

    Returns:
        True if successful
    """
    try:
        current_state = CandidateUploadState(candidate.upload_status)

        if not validate_state_transition(current_state, new_state, raise_error=True):
            return False

        candidate.upload_status = new_state.value

        if new_state == CandidateUploadState.QUEUED:
            candidate.queued_at = datetime.utcnow()
        elif new_state == CandidateUploadState.PROCESSING:
            pass  # Celery task handles this
        elif new_state == CandidateUploadState.COMPLETE:
            candidate.processing_completed_at = datetime.utcnow()
        elif new_state in [CandidateUploadState.UPLOAD_FAILED, CandidateUploadState.PROCESSING_FAILED]:
            candidate.upload_error = error_message

        db.add(candidate)
        return True

    except Exception as e:
        logger.error(f"Failed to update state: {e}", exc_info=True)
        return False


# ============================================
# DOCUMENT UPDATE HELPERS (eliminate duplication)
# ============================================

def update_candidate_doc_count(
    db: Session,
    candidate: Candidate,
    new_count: int,
):
    """Update actual document count."""
    candidate.actual_document_count = new_count
    candidate.last_document_uploaded_at = datetime.utcnow()
    db.add(candidate)
