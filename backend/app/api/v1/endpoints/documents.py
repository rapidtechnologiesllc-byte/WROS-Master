"""
Secure Document Upload Endpoints
Uses service layer for better separation of concerns and scalability.
Uses service account authentication - candidates don't need Microsoft accounts.
import logging
"""

from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate, get_current_internal_user, require_resource_permission
from app.core.graph_auth import get_graph_token
from app.core.dependencies import get_current_internal_user
from app.models.candidate import Candidate

# Alias for backward compatibility
get_current_user = get_current_internal_user
from app.schemas.document import DocumentUploadResponse
from app.services.document_service import DocumentService, SHAREPOINT_SITE_ID, SHAREPOINT_DRIVE_ID, MULTI_UPLOAD_TYPES
from app.services.virus_scan_service import document_is_accessible, scan_document_content
from app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["Documents uploads"])

async def _upload_document_helper(
    file: UploadFile,
    document_type: str,
    user,
    db: Session
) -> DocumentUploadResponse:
    """
    Helper function for document upload.
    Centralizes upload logic for all document types.
    Uses service account authentication (no user Microsoft login required).
    
    Args:
        file: Uploaded file
        document_type: Type of document
        user: Authenticated candidate
        db: Database session
        
    Returns:
        DocumentUploadResponse
    """
    # Initialize document service
    doc_service = DocumentService(db)
    
    # Validate document
    is_valid, error_msg, file_content = doc_service.validate_document(file, document_type)
    if not is_valid:
        logger.warning(f"Document validation failed for {user.candidateID}: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Get Microsoft Graph access token using service account
    try:
        access_token = get_graph_token()
    except Exception as e:
        logger.error(f"Failed to get Graph token: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to authenticate with SharePoint. Please contact administrator."
        )
    
    # Generate unique filename
    unique_filename = doc_service.generate_unique_filename(
        file.filename,
        user.candidateID,
        document_type
    )
    
    # Upload to SharePoint
    try:
        sharepoint_data = doc_service.upload_to_sharepoint(
            access_token,
            user.candidateID,
            document_type,
            file_content,
            unique_filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"SharePoint upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Save metadata to database
    try:
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else ''
        document = doc_service.save_document_metadata(
            candidate_id=user.candidateID,
            document_type=document_type,
            original_filename=file.filename,
            unique_filename=unique_filename,
            file_size=len(file_content),
            file_extension=f".{file_ext}",
            sharepoint_data=sharepoint_data,
            uploaded_by=user.candidateID
        )
        
        # HRMS-0118: the scan gate -- runs once, right after the file is
        # actually stored, so is_virus_scanned/virus_scan_result reflect
        # this specific upload's content rather than staying permanently
        # declared-but-unset (the exact gap this schema had before).
        scan_document_content(document, file_content)
        db.commit()

        logger.info(
            f"Document uploaded successfully: {document.id} - {document_type} for {user.candidateID} "
            f"(virus_scan_result={document.virus_scan_result})"
        )

        return DocumentUploadResponse(
            status="Success",
            message=f"{document_type.replace('_', ' ').title()} uploaded successfully",
            document_id=document.id,
            document_type=document_type,
            file_name=file.filename,
            sharepoint_url=sharepoint_data.get("webUrl"),
            uploaded_at=document.uploaded_at
        )
        
    except Exception as e:
        logger.error(f"Failed to save document metadata: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save document metadata")

@router.post(
    "/upload/resume",
    response_model=DocumentUploadResponse,
    dependencies=[Depends(require_resource_permission("documents", "create"))],
)
async def upload_resume(
    candidate_id: str,
    file: UploadFile = File(..., description="Resume file (PDF, DOC, DOCX)"),
    user = Depends(get_current_internal_user),
    db: Session = Depends(get_db)
):
    """
    Upload candidate resume/CV to SharePoint with database tracking.
    HR/Admin uploads resume for a specific candidate.
    
    Args:
        candidate_id: ID of the candidate for whom the resume is being uploaded
        file: Resume file (PDF, DOC, DOCX)
        user: Authenticated HR/Admin user
        db: Database session
    """
    # Verify candidate exists
    from app.models.candidate import Candidate
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    
    # Use candidate object for upload (not the HR user)
    return await _upload_document_helper(file, "resume", candidate, db)

@router.post("/upload/pan", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_pan(
    file: UploadFile = File(..., description="PAN card file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload PAN card document to SharePoint with database tracking."""
    return await _upload_document_helper(file, "pan", user, db)

@router.post("/upload/aadhar", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_aadhar(
    file: UploadFile = File(..., description="Aadhar card file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload Aadhar card document to SharePoint with database tracking."""
    return await _upload_document_helper(file, "aadhar", user, db)

@router.post("/upload/education", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_education_certificate(
    file: UploadFile = File(..., description="Education certificate file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload education certificate to SharePoint with database tracking."""
    return await _upload_document_helper(file, "education", user, db)

@router.post("/upload/experience", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_experience_letter(
    file: UploadFile = File(..., description="Experience letter file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload experience letter to SharePoint with database tracking."""
    return await _upload_document_helper(file, "experience", user, db)

@router.post("/upload/salary-slip", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_salary_slip(
    file: UploadFile = File(..., description="Salary slip file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload salary slip to SharePoint with database tracking."""
    return await _upload_document_helper(file, "salary_slip", user, db)

@router.post("/upload/bank-statement", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_bank_statement(
    file: UploadFile = File(..., description="Bank statement file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload bank statement to SharePoint with database tracking."""
    return await _upload_document_helper(file, "bank_statement", user, db)

@router.post("/upload/uan-pf", response_model=DocumentUploadResponse, dependencies=[Depends(require_resource_permission("upload", "create"))])
async def upload_uan_pf(
    file: UploadFile = File(..., description="UAN-PF file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload UAN-PF to SharePoint with database tracking."""
    return await _upload_document_helper(file, "uan_pf", user, db)

# ============================================
# Candidate Self-Service Document Endpoint
# ============================================

@router.get(
    "/my-documents",
    summary="Get all documents uploaded by the currently authenticated candidate",
    dependencies=[Depends(get_current_internal_user)]
)
async def get_my_documents(
    current_user=Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """
    Retrieve all documents belonging to the currently authenticated candidate.
    Candidates can only view their own documents.

    Returns:
        List of all documents for the authenticated candidate with verification status.
    """
    from app.models.document import CandidateDocument

    candidate_id = current_user.candidateID

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    # Fetch ALL non-deleted documents (we sort per-type below)
    all_docs = (
        db.query(CandidateDocument)
        .filter(
            CandidateDocument.candidate_id == candidate_id,
            CandidateDocument.is_deleted == False,
        )
        .order_by(CandidateDocument.document_type, CandidateDocument.uploaded_at.desc())
        .all()
    )

    # For single-upload types keep only the is_latest record;
    # for multi-upload types keep every record.
    visible_docs = [
        doc for doc in all_docs
        if doc.document_type in MULTI_UPLOAD_TYPES or doc.is_latest
    ]

    candidate_full_name = f"{candidate.candidateFirstName or ''} {candidate.candidateMiddleName or ''} {candidate.candidateLastName or ''}".strip()

    def _doc_dict(doc):
        return {
            "id": doc.id,
            "document_type": doc.document_type,
            "original_filename": doc.original_filename,
            "file_size": doc.file_size,
            "file_extension": doc.file_extension,
            "sharepoint_url": doc.sharepoint_url,
            "is_verified": doc.is_verified,
            "verified_by": doc.verified_by,
            "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "notes": doc.notes,
            "version": doc.version,
            # HRMS-0118: expose the scan gate's actual state -- the
            # frontend uses this to disable "View" until it's "clean",
            # matching document_is_accessible()'s fail-closed check.
            "is_virus_scanned": doc.is_virus_scanned,
            "virus_scan_result": doc.virus_scan_result,
        }

    # Build a grouped structure: single-upload types as flat entries,
    # multi-upload types under a "files" list.
    grouped: dict = {}
    for doc in visible_docs:
        dtype = doc.document_type
        if dtype in MULTI_UPLOAD_TYPES:
            grouped.setdefault(dtype, {"document_type": dtype, "files": []})["files"].append(_doc_dict(doc))
        else:
            grouped[dtype] = _doc_dict(doc)

    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_full_name,
        "candidate_email": candidate.candidateEmail,
        "total_documents": len(visible_docs),
        "verified_count": sum(1 for doc in visible_docs if doc.is_verified == "Verified"),
        "pending_count": sum(1 for doc in visible_docs if doc.is_verified == "Pending"),
        "rejected_count": sum(1 for doc in visible_docs if doc.is_verified == "Rejected"),
        "documents": list(grouped.values()),
    }

# ============================================
# HR/Admin Document Management Endpoints
# ============================================

@router.get(
    "/candidate/{candidate_id}",
    dependencies=[Depends(require_resource_permission("documents", "view"))],
)
async def get_candidate_documents(
    candidate_id: str,
    verification_status: Optional[str] = Query(
        default=None,
        description="Filter by verification status. Accepted values: Pending, Verified, Rejected",
    ),
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db)
):
    """
    Get all documents for a specific candidate.
    Only accessible by HR and Admin users.

    Args:
        candidate_id: Candidate ID to fetch documents for
        verification_status: Optional filter — one of Pending, Verified, Rejected
        current_user: Authenticated HR/Admin user
        db: Database session

    Returns:
        List of all documents for the candidate with verification status
    """

    VALID_STATUSES = {"Pending", "Verified", "Rejected"}
    if verification_status and verification_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verification_status '{verification_status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")

    # Fetch ALL non-deleted documents for this candidate
    all_docs = (
        db.query(CandidateDocument)
        .filter(
            CandidateDocument.candidate_id == candidate_id,
            CandidateDocument.is_deleted == False,
        )
        .order_by(CandidateDocument.document_type, CandidateDocument.uploaded_at.desc())
        .all()
    )

    # For single-upload types keep only the is_latest record;
    # for multi-upload types keep every record.
    visible_docs = [
        doc for doc in all_docs
        if doc.document_type in MULTI_UPLOAD_TYPES or doc.is_latest
    ]

    # Summary counts are always over ALL visible documents (before filtering)
    verified_count  = sum(1 for doc in visible_docs if doc.is_verified == "Verified")
    pending_count   = sum(1 for doc in visible_docs if doc.is_verified == "Pending")
    rejected_count  = sum(1 for doc in visible_docs if doc.is_verified == "Rejected")

    # Apply optional verification_status filter AFTER counting
    if verification_status:
        visible_docs = [doc for doc in visible_docs if doc.is_verified == verification_status]

    candidate_full_name = f"{candidate.candidateFirstName or ''} {candidate.candidateMiddleName or ''} {candidate.candidateLastName or ''}".strip()

    def _doc_dict(doc):
        return {
            "id": doc.id,
            "document_type": doc.document_type,
            "original_filename": doc.original_filename,
            "file_size": doc.file_size,
            "file_extension": doc.file_extension,
            "sharepoint_url": doc.sharepoint_url,
            "is_verified": doc.is_verified,
            "verified_by": doc.verified_by,
            "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "uploaded_by": doc.uploaded_by,
            "is_deleted": doc.is_deleted,
            "notes": doc.notes,
            "version": doc.version,
            "is_virus_scanned": doc.is_virus_scanned,
            "virus_scan_result": doc.virus_scan_result,
        }

    # Group: multi-upload types get a "files" list; single-upload types are flat.
    grouped: dict = {}
    for doc in visible_docs:
        dtype = doc.document_type
        if dtype in MULTI_UPLOAD_TYPES:
            grouped.setdefault(dtype, {"document_type": dtype, "files": []})["files"].append(_doc_dict(doc))
        else:
            grouped[dtype] = _doc_dict(doc)

    logger.info(
        f"HR user {current_user.UserEmail} accessed documents for candidate {candidate_id}"
        + (f" [filter: {verification_status}]" if verification_status else "")
    )
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_full_name,
        "candidate_email": candidate.candidateEmail,
        "total_documents": len(visible_docs),
        "verified_count": verified_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "applied_filter": verification_status,
        "documents": list(grouped.values()),
    }

@router.get(
    "/{document_id}",
    summary="Get a single document's metadata by its ID",
    dependencies=[Depends(get_current_internal_user)]
)
async def get_document_by_id(
    document_id: int,
    current_user=Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve the full metadata record for a specific document by its **document_id**.

    Returns SharePoint URL, verification status, upload details, and all other
    stored metadata.  The actual file content is served separately via
    `GET /documents/{document_id}/view`.

    Only accessible by HR/Admin users.
    """

    doc = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.is_deleted == False,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    logger.info(
        f"HR user {current_user.UserEmail} fetched metadata for document {document_id} "
        f"({doc.document_type}) of candidate {doc.candidate_id}."
    )

    return {
        "id": doc.id,
        "candidate_id": doc.candidate_id,
        "document_type": doc.document_type,
        "original_filename": doc.original_filename,
        "stored_filename": doc.stored_filename,
        "file_size": doc.file_size,
        "file_extension": doc.file_extension,
        "mime_type": doc.mime_type,
        "sharepoint_url": doc.sharepoint_url,
        "sharepoint_file_id": doc.sharepoint_file_id,
        "is_virus_scanned": doc.is_virus_scanned,
        "virus_scan_result": doc.virus_scan_result,
        "is_verified": doc.is_verified,
        "verified_by": doc.verified_by,
        "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
        "version": doc.version,
        "is_latest": doc.is_latest,
        "uploaded_by": doc.uploaded_by,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "notes": doc.notes,
        "tags": doc.tags,
    }

@router.get(
    "/{document_id}/view",
    dependencies=[Depends(require_resource_permission("documents", "view"))],
    summary="Stream a document from SharePoint for inline viewing",
)
async def view_document(
    document_id: int,
    current_user=Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Proxy a document stored in SharePoint back to the frontend.
    Uses the service account token — HR does not need a Microsoft login.
    The response includes Content-Disposition: inline so browsers open
    the file in a tab/iframe instead of downloading it.
    """
    from fastapi.responses import StreamingResponse
    import requests as req
    import io

    # Fetch document record
    doc = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.sharepoint_file_id:
        raise HTTPException(status_code=404, detail="No SharePoint file ID stored for this document")

    # HRMS-0118: fail closed -- anything other than an explicit "clean"
    # result blocks viewing, including "no scan has run yet" (legacy
    # rows uploaded before this gate existed) and "the scanner errored."
    if not document_is_accessible(doc):
        raise HTTPException(
            status_code=403,
            detail=(
                f"This document has not passed virus scanning "
                f"(status: {doc.virus_scan_result or 'not scanned'}) and cannot be viewed."
            ),
        )

    # Get a fresh service account token
    try:
        access_token = get_graph_token()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Failed to get Graph token for document view: {exc}")
        raise HTTPException(status_code=500, detail="Failed to authenticate with SharePoint")

    # Download file content from SharePoint via Graph API
    download_url = (
        f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}"
        f"/drives/{SHAREPOINT_DRIVE_ID}/items/{doc.sharepoint_file_id}/content"
    )
    try:
        sp_response = req.get(
            download_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=60,
            stream=True,
        )
        sp_response.raise_for_status()
    except req.exceptions.HTTPError as exc:
        logger.error(f"SharePoint download failed for doc {document_id}: {exc}")
        raise HTTPException(status_code=502, detail="Failed to fetch file from SharePoint")

    # Determine content type for browser rendering
    content_type = doc.mime_type or "application/octet-stream"

    # Stream file bytes back to client
    file_bytes = io.BytesIO(sp_response.content)

    logger.info(
        f"HR user {current_user.UserEmail} viewed document {document_id} "
        f"({doc.document_type}) for candidate {doc.candidate_id}"
    )

    return StreamingResponse(
        file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{doc.original_filename}"',
            "Content-Length": str(len(sp_response.content)),
        },
    )

@router.patch(
    "/verify/{document_id}",
    dependencies=[Depends(require_resource_permission("documents", "edit"))],
)
async def update_document_verification(
    document_id: int,
    verification_status: str,
    notes: str = None,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db)
):
    """
    Update verification status of a single document by its **document_id**.

    This works for all document types including education and experience,
    where multiple independent files exist per candidate.  To get the
    document IDs, call `GET /documents/candidate/{candidate_id}`.

    Args:
        document_id: ID of the specific document record to verify
        verification_status: Verification status — must be one of: Pending, Verified, Rejected
        notes: Optional HR notes about the verification decision
    """
    from datetime import datetime

    VALID_STATUSES = {"Pending", "Verified", "Rejected"}
    if verification_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verification_status '{verification_status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.is_deleted == False,
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found."
        )

    document.is_verified = verification_status
    if verification_status in ("Verified", "Rejected"):
        document.verified_by = current_user.UserID
        document.verified_at = datetime.utcnow()
    else:
        # Reset auditing fields when re-setting to Pending
        document.verified_by = None
        document.verified_at = None
    if notes:
        document.notes = notes

    db.commit()
    db.refresh(document)

    logger.info(
        f"HR user {current_user.UserEmail} set document {document_id} "
        f"({document.document_type}) for candidate {document.candidate_id} "
        f"to '{verification_status}'."
    )

    # 2026-08-05 -- rejecting a document reopens (or creates) a real
    # Task so it shows as pending work; approving closes it. Never
    # raises -- see document_task_service's own module docstring.
    from app.services.document_task_service import sync_task_for_document_decision
    sync_task_for_document_decision(
        db, document, verification_status, current_user.UserID, reason=notes,
    )

    return {
        "status": "success",
        "message": f"Document marked as '{verification_status}' successfully",
        "document": {
            "id": document.id,
            "candidate_id": document.candidate_id,
            "document_type": document.document_type,
            "original_filename": document.original_filename,
            "verification_status": document.is_verified,
            "verified_by": document.verified_by,
            "verified_at": document.verified_at.isoformat() if document.verified_at else None,
            "notes": document.notes,
        }
    }

# ============================================
# Delete All Candidate Documents
# ============================================

@router.delete(
    "/candidate/{candidate_id}/all",
    dependencies=[Depends(require_resource_permission("documents", "edit"))],
    summary="Delete ALL documents for a candidate (DB + SharePoint)",
)
async def delete_all_candidate_documents(
    candidate_id: str,
    current_user=Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete **every** document belonging to a candidate.

    Steps:
    1. Fetch all document records for the candidate (including soft-deleted ones).
    2. For each record that has a SharePoint file ID, delete the file via the
       Microsoft Graph API using the service account token.
    3. Hard-delete all document rows from the database.

    SharePoint deletion failures are collected and returned in the response but
    do **not** block the database cleanup — the DB records are always removed.

    Only accessible by HR/Admin users with the `document.manage` permission.
    """
    import requests as req

    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found",
        )

    # Fetch ALL document records (including soft-deleted) so nothing is left behind
    docs = (
        db.query(CandidateDocument)
        .filter(CandidateDocument.candidate_id == candidate_id)
        .all()
    )

    if not docs:
        return {
            "status": "success",
            "message": "No documents found for this candidate — nothing to delete.",
            "candidate_id": candidate_id,
            "deleted_count": 0,
            "sharepoint_failures": [],
        }

    # Get a fresh service-account token for SharePoint calls
    try:
        access_token = get_graph_token()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[DeleteAllDocs] Failed to get Graph token: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to authenticate with SharePoint. DB records were NOT deleted.",
        )

    # ── Delete each file from SharePoint ────────────────────────────────────
    sharepoint_failures: list[dict] = []

    for doc in docs:
        if not doc.sharepoint_file_id:
            # No SharePoint record — nothing to delete remotely
            continue

        delete_url = (
            f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}"
            f"/drives/{SHAREPOINT_DRIVE_ID}/items/{doc.sharepoint_file_id}"
        )
        try:
            sp_resp = req.delete(
                delete_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
            if sp_resp.status_code == 404:
                # Already gone — treat as success
                logger.info(
                    f"[DeleteAllDocs] SharePoint item {doc.sharepoint_file_id} "
                    f"already absent (doc id={doc.id})."
                )
            elif not sp_resp.ok:
                raise RuntimeError(f"HTTP {sp_resp.status_code}: {sp_resp.text[:200]}")
            else:
                logger.info(
                    f"[DeleteAllDocs] Deleted SharePoint item {doc.sharepoint_file_id} "
                    f"(doc id={doc.id}, type={doc.document_type})."
                )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(
                f"[DeleteAllDocs] Could not delete SharePoint item "
                f"{doc.sharepoint_file_id} (doc id={doc.id}): {exc}"
            )
            sharepoint_failures.append({
                "document_id": doc.id,
                "document_type": doc.document_type,
                "sharepoint_file_id": doc.sharepoint_file_id,
                "error": str(exc),
            })

    # ── Hard-delete all DB records ───────────────────────────────────────────
    deleted_count = (
        db.query(CandidateDocument)
        .filter(CandidateDocument.candidate_id == candidate_id)
        .delete(synchronize_session=False)
    )
    db.commit()

    logger.info(
        f"[DeleteAllDocs] HR user {current_user.UserEmail} deleted "
        f"{deleted_count} document record(s) for candidate {candidate_id}. "
        f"SharePoint failures: {len(sharepoint_failures)}."
    )

    return {
        "status": "success" if not sharepoint_failures else "partial",
        "message": (
            f"Deleted {deleted_count} document record(s) from the database. "
            + (
                f"{len(sharepoint_failures)} SharePoint file(s) could not be removed — see 'sharepoint_failures'."
                if sharepoint_failures
                else "All SharePoint files removed successfully."
            )
        ),
        "candidate_id": candidate_id,
        "deleted_count": deleted_count,
        "sharepoint_failures": sharepoint_failures,
    }
