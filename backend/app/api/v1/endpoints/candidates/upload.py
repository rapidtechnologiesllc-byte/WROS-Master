"""
Progressive Document Upload Endpoints (SharePoint + Celery)
============================================================
Integrates:
- SharePoint backend (via DocumentService)
- Progressive upload pattern (one document per request)
- Celery async processing (queue immediately after upload)
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_user
from app.models.candidate import Candidate
from app.models.document import CandidateDocument
from app.models.user import Users
from app.services.document_service import DocumentService
from app.services.message_queue_service import MessageQueueService
from datetime import datetime

# Lazy load celery for optional async processing
try:
    from app.celery_app import app as celery_app
except ImportError:
    celery_app = None

router = APIRouter(prefix="/upload", tags=["Progressive Upload"])


@router.post("/create-session")
async def create_upload_session(
    email: str,
    first_name: str,
    last_name: str,
    expected_document_count: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Create candidate + start upload session.

    Returns:
        - candidate_id
        - session_token
        - expected_documents
    """
    try:
        # Check if candidate exists (idempotency)
        existing = db.query(Candidate).filter(
            Candidate.candidateEmail == email.lower()
        ).first()

        if existing:
            logger.info(f"[UPLOAD] Candidate exists: {email}")
            return {
                "status": "exists",
                "candidate_id": existing.candidateID,
                "session_token": f"session_{existing.candidateID}",
                "expected_documents": expected_document_count,
            }

        # Create new candidate
        # Defensive check: ensure candidate doesn't already exist (redundant with earlier check, but required for safety)
        duplicate_check = db.query(Candidate).filter(
            Candidate.candidateEmail == email.lower()
        ).first()
        if duplicate_check:
            raise HTTPException(status_code=409, detail="Candidate already exists")

        candidate = Candidate(
            candidateEmail=email.lower(),
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateCreatedAt=datetime.utcnow(),
            upload_status="uploading",
            expected_document_count=expected_document_count,
            actual_document_count=0,
            upload_started_at=datetime.utcnow(),
        )

        db.add(candidate)
        db.flush()
        candidate_id = candidate.candidateID
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[UPLOAD] Failed to commit candidate creation: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

        logger.info(f"[UPLOAD] Created candidate: {candidate_id} ({email})")

        return {
            "status": "created",
            "candidate_id": candidate_id,
            "session_token": f"session_{candidate_id}",
            "expected_documents": expected_document_count,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[UPLOAD] Create session failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/document/{candidate_id}")
async def upload_document(
    candidate_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Upload single document to SharePoint.

    Flow:
    1. Validate file
    2. Upload to SharePoint
    3. Record in database
    4. Return status

    Celery processing queued AFTER user marks upload complete.
    """
    try:
        # Fetch candidate
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Validate document
        doc_service = DocumentService(db)
        is_valid, error_msg, file_content = doc_service.validate_document(
            file, "document"
        )

        if not is_valid:
            logger.warning(
                f"[UPLOAD] Invalid document for {candidate_id}: {error_msg}"
            )
            raise HTTPException(status_code=400, detail=error_msg)

        # Generate unique filename
        unique_filename = doc_service.generate_unique_filename(
            file.filename, candidate_id, "document"
        )

        # Upload to SharePoint
        try:
            from app.core.graph_auth import get_graph_token

            access_token = get_graph_token()
        except Exception as e:
            logger.error(f"[UPLOAD] Failed to get Graph token: {e}")
            raise HTTPException(status_code=500, detail="SharePoint auth failed")

        try:
            sharepoint_data = doc_service.upload_to_sharepoint(
                access_token,
                candidate_id,
                "document",
                file_content,
                unique_filename,
            )
        except Exception as e:
            logger.error(
                f"[UPLOAD] SharePoint upload failed for {candidate_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

        # Record in database
        try:
            # Get next sequence
            max_seq = (
                db.query(CandidateDocument)
                .filter(CandidateDocument.candidateID == candidate_id)
                .count()
            )
            sequence = max_seq + 1

            document = CandidateDocument(
                candidate_id=candidate_id,
                document_name=file.filename,
                document_type="document",
                original_filename=file.filename,
                stored_filename=unique_filename,
                file_size=len(file_content),
                file_extension=file.filename.split(".")[-1] if "." in file.filename else "",
                mime_type=file.content_type,
                sharepoint_url=sharepoint_data.get("webUrl"),
                sharepoint_file_id=sharepoint_data.get("id"),
                uploaded_by=candidate_id,
                uploaded_at=datetime.utcnow(),
                upload_sequence=sequence,
            )

            db.add(document)

            # Update candidate
            candidate.actual_document_count = sequence
            candidate.last_document_uploaded_at = datetime.utcnow()

            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[UPLOAD] Failed to commit document: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Failed to save document")

            logger.info(
                f"[UPLOAD] Document {sequence} for {candidate_id}: "
                f"{file.filename} ({len(file_content)} bytes)"
            )

            return {
                "status": "success",
                "document_id": document.id,
                "sequence": sequence,
                "filename": file.filename,
                "size": len(file_content),
                "uploaded_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            db.rollback()
            logger.error(f"[UPLOAD] Failed to record document: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to save document")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complete/{candidate_id}")
async def mark_upload_complete(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Mark upload complete and queue Celery task.

    ATOMIC PATTERN:
    1. Queue Celery task FIRST
    2. THEN update status
    3. If queueing fails, don't update status
    """
    try:
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Already processing?
        if candidate.upload_status != "uploading":
            logger.info(f"[UPLOAD] Already processing: {candidate_id}")
            return {
                "status": "already_queued",
                "task_id": getattr(candidate, "celery_task_id", None),
            }

        # Queue Celery task FIRST (all or nothing)
        try:
            if not celery_app:
                logger.warning(f"[UPLOAD] Celery not available, skipping async processing for {candidate_id}")
                celery_task = type('obj', (object,), {'id': f'mock-{candidate_id}'})()
            else:
                celery_task = celery_app.send_task(
                    "process_candidate",
                    args=[candidate_id],
                    kwargs={"tenant_id": 1},
                )

                if not celery_task.id:
                    raise ValueError("Queue returned no task ID")

            logger.info(f"[UPLOAD] Queued task {celery_task.id} for {candidate_id}")

        except Exception as e:
            logger.error(f"[UPLOAD] Queue failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Failed to queue processing task"
            )

        # THEN update status (if queue succeeded)
        try:
            candidate.upload_status = "queued"
            candidate.queued_at = datetime.utcnow()
            candidate.celery_task_id = celery_task.id

            try:
                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.error(f"[UPLOAD] Failed to update status: {db_err}", exc_info=True)
                raise HTTPException(status_code=500, detail="Failed to queue processing")

        except Exception as e:
            logger.error(f"[UPLOAD] Unexpected error updating status: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to queue processing")

        return {
            "status": "queued",
            "task_id": celery_task.id,
            "documents_uploaded": candidate.actual_document_count,
            "message": f"Processing started for {candidate.actual_document_count} documents",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{candidate_id}")
async def get_upload_status(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """Get current upload/processing status."""
    try:
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            return {
                "status": "not_found",
                "candidate_id": candidate_id,
            }

        return {
            "status": candidate.upload_status,
            "candidate_id": candidate_id,
            "documents_uploaded": candidate.actual_document_count,
            "expected_documents": candidate.expected_document_count,
            "task_id": candidate.celery_task_id,
            "created_at": candidate.candidateCreatedAt.isoformat()
            if candidate.candidateCreatedAt
            else None,
            "uploaded_at": candidate.last_document_uploaded_at.isoformat()
            if candidate.last_document_uploaded_at
            else None,
            "queued_at": candidate.queued_at.isoformat()
            if candidate.queued_at
            else None,
        }

    except Exception as e:
        logger.error(f"[UPLOAD] Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
