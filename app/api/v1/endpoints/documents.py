"""
Secure Document Upload Endpoints
Uses service layer for better separation of concerns and scalability.
Uses service account authentication - candidates don't need Microsoft accounts.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate, get_current_hr_or_admin, require_permission
from app.core.graph_auth import get_graph_token
from app.schemas.document import DocumentUploadResponse
from app.services.document_service import DocumentService
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
        
        logger.info(f"Document uploaded successfully: {document.id} - {document_type} for {user.candidateID}")
        
        return DocumentUploadResponse(
            status="Success",
            message=f"{document_type.replace('_', ' ').title()} uploaded successfully",
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
    dependencies=[Depends(require_permission("document.upload"))],
)
async def upload_resume(
    candidate_id: str,
    file: UploadFile = File(..., description="Resume file (PDF, DOC, DOCX)"),
    user = Depends(get_current_hr_or_admin),
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


@router.post("/upload/pan", response_model=DocumentUploadResponse)
async def upload_pan(
    file: UploadFile = File(..., description="PAN card file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload PAN card document to SharePoint with database tracking."""
    return await _upload_document_helper(file, "pan", user, db)


@router.post("/upload/aadhar", response_model=DocumentUploadResponse)
async def upload_aadhar(
    file: UploadFile = File(..., description="Aadhar card file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload Aadhar card document to SharePoint with database tracking."""
    return await _upload_document_helper(file, "aadhar", user, db)


@router.post("/upload/education", response_model=DocumentUploadResponse)
async def upload_education_certificate(
    file: UploadFile = File(..., description="Education certificate file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload education certificate to SharePoint with database tracking."""
    return await _upload_document_helper(file, "education", user, db)


@router.post("/upload/experience", response_model=DocumentUploadResponse)
async def upload_experience_letter(
    file: UploadFile = File(..., description="Experience letter file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload experience letter to SharePoint with database tracking."""
    return await _upload_document_helper(file, "experience", user, db)


@router.post("/upload/salary-slip", response_model=DocumentUploadResponse)
async def upload_salary_slip(
    file: UploadFile = File(..., description="Salary slip file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload salary slip to SharePoint with database tracking."""
    return await _upload_document_helper(file, "salary_slip", user, db)


@router.post("/upload/bank-statement", response_model=DocumentUploadResponse)
async def upload_bank_statement(
    file: UploadFile = File(..., description="Bank statement file (PDF, JPG, PNG)"),
    user = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    """Upload bank statement to SharePoint with database tracking."""
    return await _upload_document_helper(file, "bank_statement", user, db)


# ============================================
# HR/Admin Document Management Endpoints
# ============================================

@router.get(
    "/candidate/{candidate_id}",
    dependencies=[Depends(require_permission("document.view"))],
)
async def get_candidate_documents(
    candidate_id: str,
    current_user = Depends(get_current_hr_or_admin),
    db: Session = Depends(get_db)
):
    """
    Get all documents for a specific candidate.
    Only accessible by HR and Admin users.
    
    Args:
        candidate_id: Candidate ID to fetch documents for
        current_user: Authenticated HR/Admin user
        db: Database session
        
    Returns:
        List of all documents for the candidate with verification status
    """
    from app.models.document import CandidateDocument
    from app.models.candidate import Candidate
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    
    # Get all documents for the candidate (including soft-deleted ones)
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.is_latest == True  # Only get latest versions
    ).order_by(CandidateDocument.uploaded_at.desc()).all()
    
    # Format response
    candidate_full_name = f"{candidate.candidateFirstName or ''} {candidate.candidateMiddleName or ''} {candidate.candidateLastName or ''}".strip()
    
    result = {
        "candidate_id": candidate_id,
        "candidate_name": candidate_full_name,
        "candidate_email": candidate.candidateEmail,
        "total_documents": len(documents),
        "verified_count": sum(1 for doc in documents if doc.is_verified),
        "pending_count": sum(1 for doc in documents if not doc.is_verified),
        "documents": [
            {
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
                "version": doc.version
            }
            for doc in documents
        ]
    }
    
    logger.info(f"HR user {current_user.UserEmail} accessed documents for candidate {candidate_id}")
    return result


@router.patch(
    "/verify/{candidate_id}/{document_type}",
    dependencies=[Depends(require_permission("document.verify"))],
)
async def update_document_verification(
    candidate_id: str,
    document_type: str,
    is_verified: bool,
    notes: str = None,
    current_user = Depends(get_current_hr_or_admin),
    db: Session = Depends(get_db)
):
    """
    Update document verification status by candidate ID and document type.
    Only accessible by HR and Admin users.
    
    Args:
        candidate_id: Candidate ID
        document_type: Type of document (pan, aadhar, education, experience, salary_slip, bank_statement, resume)
        is_verified: Verification status (True/False)
        notes: Optional notes about the verification
        current_user: Authenticated HR/Admin user
        db: Database session
        
    Returns:
        Updated document details
    """
    from app.models.document import CandidateDocument
    from app.models.candidate import Candidate
    from datetime import datetime
    
    # Valid document types
    valid_types = ["pan", "aadhar", "education", "experience", "salary_slip", "bank_statement", "resume"]
    
    if document_type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid document type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    
    # Get the latest document of this type for the candidate
    document = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.document_type == document_type,
        CandidateDocument.is_latest == True,
        CandidateDocument.is_deleted == False
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=404, 
            detail=f"No {document_type} document found for candidate {candidate_id}"
        )
    
    # Update verification status
    document.is_verified = is_verified
    document.verified_by = current_user.UserID
    document.verified_at = datetime.utcnow()
    
    # Update notes if provided
    if notes:
        document.notes = notes
    
    # Commit changes
    db.commit()
    db.refresh(document)
    
    logger.info(
        f"HR user {current_user.UserEmail} {'verified' if is_verified else 'rejected'} "
        f"{document_type} document for candidate {candidate_id}"
    )
    
    return {
        "status": "success",
        "message": f"Document '{document_type}' {'verified' if is_verified else 'marked as unverified'} successfully",
        "document": {
            "id": document.id,
            "candidate_id": document.candidate_id,
            "document_type": document.document_type,
            "original_filename": document.original_filename,
            "is_verified": document.is_verified,
            "verified_by": document.verified_by,
            "verified_at": document.verified_at.isoformat() if document.verified_at else None,
            "notes": document.notes
        }
    }
