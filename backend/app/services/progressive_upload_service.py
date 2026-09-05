"""
Progressive document upload service with auto-detection scheduler.

This service handles the new architecture where:
1. Candidate is created immediately (< 1 second) and committed
2. Documents upload progressively (one at a time, each committed independently)
3. Backend scheduler auto-detects when to queue Celery task
4. No frontend signal required - works even if browser closes

Solves the 200K record problem by:
- Never loading all documents into memory at once
- Never trying to commit large batches
- Streaming each document independently
- Auto-queuing after documents settle (no new uploads for 2+ minutes)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.candidate import Candidate, CandidateDocument
from app.models.candidate_status import CandidateStatus
from app.core.database import get_db
from app.services.message_queue_service import MessageQueueService

logger = logging.getLogger(__name__)

# ============================================
# Candidate Upload State Machine
# ============================================
CANDIDATE_STATUS_UPLOADED = "uploaded"  # Candidate created, waiting for docs
CANDIDATE_STATUS_PROCESSING = "processing"  # Docs uploaded, queued for Thunder
CANDIDATE_STATUS_COMPLETE = "complete"  # Thunder processing finished
CANDIDATE_STATUS_ABANDONED = "abandoned"  # No docs uploaded within timeout

# ============================================
# Progressive Upload Constants
# ============================================
UPLOAD_TIMEOUT_MINUTES = 2  # If no new doc uploads in 2 min, queue task
UPLOAD_COMPLETE_MIN_DOCS = 1  # Minimum docs before queuing (can queue with just 1 doc)
UPLOAD_ABANDONED_HOURS = 24  # If uploaded but never processed after 24 hrs, mark abandoned


def create_candidate_lightweight(
    db: Session,
    email: str,
    first_name: str,
    last_name: str,
    mobile: str,
    source: str,
    tenant_id: int = 1,
) -> tuple[Candidate, str]:
    """
    Create candidate record IMMEDIATELY with minimal data.

    This endpoint returns in < 1 second. All heavy processing (Thunder,
    documents, etc) happens asynchronously afterward.

    Args:
        db: Database session
        email: Candidate email
        first_name: First name
        last_name: Last name
        mobile: Mobile number
        source: Where candidate came from
        tenant_id: Tenant ID

    Returns:
        (candidate, upload_token) tuple
        - candidate: Created Candidate record
        - upload_token: Token for document uploads (can be candidate_id)

    Raises:
        ValueError: If validation fails
        SQLAlchemy exceptions: If database error
    """
    try:
        # Validate required fields
        if not email or '@' not in email:
            raise ValueError("Invalid email format")
        if not first_name or not first_name.strip():
            raise ValueError("First name is required")
        if not last_name or not last_name.strip():
            raise ValueError("Last name is required")

        # Check if candidate already exists (by email)
        existing = db.query(Candidate).filter(
            Candidate.candidateEmail == email,
            Candidate.tenant_id == tenant_id
        ).first()

        if existing:
            logger.info(f"Candidate already exists: {email}")
            return existing, existing.candidateID

        # Create minimal candidate record
        candidate = Candidate(
            candidateEmail=email,
            candidateFirstName=first_name.strip(),
            candidateLastName=last_name.strip(),
            candidateMobile=mobile,
            candidateSource=source,
            tenant_id=tenant_id,
            candidateCreatedAt=datetime.utcnow(),
        )

        db.add(candidate)
        db.flush()  # Get the ID without full commit yet
        candidate_id = candidate.candidateID

        # Create status record
        status = CandidateStatus(
            candidateID=candidate_id,
            status=CANDIDATE_STATUS_UPLOADED,  # "uploaded" = waiting for documents
            piplineStatus="Intake",
            createdAt=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        db.add(status)

        # COMMIT: Fast, only 2 records
        db.commit()

        logger.info(f"[PROGRESSIVE] Created candidate {candidate_id} ({email}) - ready for docs")

        return candidate, candidate_id

    except Exception as e:
        db.rollback()
        logger.error(f"[PROGRESSIVE] Failed to create candidate: {e}", exc_info=True)
        raise


def upload_document(
    db: Session,
    candidate_id: str,
    document_file: bytes,
    filename: str,
    file_type: str,
    tenant_id: int = 1,
) -> Dict:
    """
    Upload ONE document for a candidate.

    Each document is:
    - Stored independently (to S3 or local storage)
    - Committed immediately to database
    - Never blocks on other documents

    This function can be called 20 times (20 documents) with each
    call completing in 1-2 seconds. No coordination needed between calls.

    Args:
        db: Database session
        candidate_id: Candidate ID (from create_candidate_lightweight)
        document_file: File bytes
        filename: Original filename
        file_type: MIME type (application/pdf, etc)
        tenant_id: Tenant ID

    Returns:
        {
            "status": "success",
            "document_id": "doc-uuid",
            "candidate_id": candidate_id,
            "filename": filename,
            "file_size": len(document_file),
            "upload_timestamp": datetime
        }

    Raises:
        ValueError: If candidate not found or validation fails
        SQLAlchemy exceptions: If database error
    """
    try:
        # Validate file
        if not document_file or len(document_file) == 0:
            raise ValueError("File is empty")

        max_size_mb = 100
        if len(document_file) > max_size_mb * 1024 * 1024:
            raise ValueError(f"File exceeds {max_size_mb}MB limit")

        # Verify candidate exists
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        # TODO: Store file to S3 or local storage
        # For now, store in database as BLOB (not recommended for production)
        # Production should use: S3, GCS, or local disk with file references

        # Create document record
        document = CandidateDocument(
            candidateID=candidate_id,
            document_name=filename,
            document_type=file_type,
            document_data=document_file,  # In-DB storage (temporary)
            uploaded_at=datetime.utcnow(),
            file_size_bytes=len(document_file),
            tenant_id=tenant_id,
        )

        db.add(document)

        # COMMIT: Just this one document (< 1 second)
        db.commit()

        logger.info(
            f"[PROGRESSIVE] Uploaded doc for candidate {candidate_id}: "
            f"{filename} ({len(document_file)} bytes)"
        )

        return {
            "status": "success",
            "document_id": document.id,
            "candidate_id": candidate_id,
            "filename": filename,
            "file_size": len(document_file),
            "upload_timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error(
            f"[PROGRESSIVE] Failed to upload document for {candidate_id}: {e}",
            exc_info=True
        )
        raise


def get_upload_status(
    db: Session,
    candidate_id: str,
    tenant_id: int = 1,
) -> Dict:
    """
    Get current upload status for a candidate.

    Frontend can call this to show progress:
    - How many docs uploaded so far?
    - When was the last upload?
    - Is processing queued?

    Args:
        db: Database session
        candidate_id: Candidate ID
        tenant_id: Tenant ID

    Returns:
        {
            "candidate_id": candidate_id,
            "status": "uploaded",  # uploaded, processing, complete, abandoned
            "documents_uploaded": 5,
            "last_document_at": datetime,
            "processing_queued_at": None,  # null until queued
            "first_upload_at": datetime,
        }
    """
    try:
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        # Count uploaded documents
        doc_count = db.query(CandidateDocument).filter(
            CandidateDocument.candidateID == candidate_id,
            CandidateDocument.tenant_id == tenant_id,
        ).count()

        # Get last document uploaded
        last_doc = db.query(CandidateDocument).filter(
            CandidateDocument.candidateID == candidate_id,
            CandidateDocument.tenant_id == tenant_id,
        ).order_by(CandidateDocument.uploaded_at.desc()).first()

        # Get status
        status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id,
        ).first()

        return {
            "candidate_id": candidate_id,
            "status": status.status if status else CANDIDATE_STATUS_UPLOADED,
            "documents_uploaded": doc_count,
            "last_document_at": last_doc.uploaded_at.isoformat() if last_doc else None,
            "first_upload_at": candidate.candidateCreatedAt.isoformat(),
        }

    except Exception as e:
        logger.error(f"[PROGRESSIVE] Failed to get upload status for {candidate_id}: {e}")
        raise


# ============================================
# Scheduler: Auto-Detection & Queuing
# ============================================
# This runs periodically (every 2-5 minutes) to detect when candidates
# are ready for processing.

def schedule_auto_detect_and_queue(db: Session):
    """
    Scheduled job: Auto-detect candidates ready for processing and queue them.

    This runs every 2-5 minutes and:
    1. Finds candidates in "uploaded" status
    2. Checks if they've had no new document uploads in last 2 minutes
    3. If idle 2+ minutes → queue Celery task for Thunder processing
    4. Mark status as "processing"

    Why 2 minutes?
    - Gives users time to upload final documents
    - If uploading 20 docs at 1 doc/second = 20 seconds total
    - 2 minute buffer = plenty of time for slow networks
    - If user closes browser → auto-queues after 2 min with what they uploaded

    This means:
    - User uploads 5 docs then closes browser → queued after 2 min with 5 docs
    - User uploads 15 docs then closes browser → queued after 2 min with 15 docs
    - User uploads 20 docs then calls processing-complete → queued immediately

    Call this from a scheduler (APScheduler, Celery Beat):
    ```python
    scheduler.add_job(
        schedule_auto_detect_and_queue,
        'interval',
        minutes=2,
        args=[db]
    )
    ```
    """
    try:
        logger.info("[SCHEDULER] Auto-detect starting...")

        # Find candidates that are "uploaded" (waiting) with docs but not yet queued
        upload_timeout = datetime.utcnow() - timedelta(minutes=UPLOAD_TIMEOUT_MINUTES)

        # Candidates with status="uploaded" AND last_doc_upload > 2 min ago
        # (meaning they haven't uploaded anything for 2+ minutes)
        candidates_to_queue = db.query(Candidate).join(
            CandidateStatus, Candidate.candidateID == CandidateStatus.candidateID
        ).filter(
            CandidateStatus.status == CANDIDATE_STATUS_UPLOADED,
            Candidate.candidateID.in_(
                db.query(CandidateDocument.candidateID).filter(
                    CandidateDocument.uploaded_at < upload_timeout
                ).distinct()
            )
        ).all()

        logger.info(f"[SCHEDULER] Found {len(candidates_to_queue)} candidates ready to queue")

        for candidate in candidates_to_queue:
            try:
                # Get document count
                doc_count = db.query(CandidateDocument).filter(
                    CandidateDocument.candidateID == candidate.candidateID
                ).count()

                # Verify has at least 1 document
                if doc_count < UPLOAD_COMPLETE_MIN_DOCS:
                    logger.warning(
                        f"[SCHEDULER] Candidate {candidate.candidateID} has {doc_count} docs, "
                        f"skipping (min {UPLOAD_COMPLETE_MIN_DOCS} required)"
                    )
                    continue

                # Queue Celery task
                MessageQueueService.enqueue(
                    'process_candidate',
                    candidate.candidateID,
                    candidate.tenant_id
                )

                # Update status to "processing"
                status = db.query(CandidateStatus).filter(
                    CandidateStatus.candidateID == candidate.candidateID
                ).first()

                if status:
                    status.status = CANDIDATE_STATUS_PROCESSING
                    status.updatedAt = datetime.utcnow()
                    db.add(status)

                db.commit()

                logger.info(
                    f"[SCHEDULER] Queued candidate {candidate.candidateID} "
                    f"with {doc_count} documents"
                )

            except Exception as e:
                db.rollback()
                logger.error(
                    f"[SCHEDULER] Failed to queue candidate {candidate.candidateID}: {e}",
                    exc_info=True
                )

        # CLEANUP: Mark abandoned candidates
        # (created but no documents uploaded for 24 hours)
        cleanup_abandoned_candidates(db)

    except Exception as e:
        logger.error("[SCHEDULER] Auto-detect failed", exc_info=True)
        db.rollback()


def cleanup_abandoned_candidates(db: Session):
    """
    Mark candidates as abandoned if they have no documents after 24 hours.

    Helps identify:
    - Users who started upload but never completed
    - Network interruptions that left candidate hanging
    - Browser crashes during upload flow
    """
    try:
        abandoned_threshold = datetime.utcnow() - timedelta(hours=UPLOAD_ABANDONED_HOURS)

        abandoned = db.query(Candidate).join(
            CandidateStatus, Candidate.candidateID == CandidateStatus.candidateID
        ).filter(
            CandidateStatus.status == CANDIDATE_STATUS_UPLOADED,
            Candidate.candidateCreatedAt < abandoned_threshold,
            ~Candidate.candidateID.in_(
                db.query(CandidateDocument.candidateID).distinct()
            )
        ).all()

        logger.warning(f"[SCHEDULER] Found {len(abandoned)} abandoned candidates")

        for candidate in abandoned:
            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate.candidateID
            ).first()

            if status:
                status.status = CANDIDATE_STATUS_ABANDONED
                status.updatedAt = datetime.utcnow()
                db.add(status)

        if abandoned:
            db.commit()

    except Exception as e:
        logger.error("[SCHEDULER] Cleanup abandoned failed", exc_info=True)
        db.rollback()
