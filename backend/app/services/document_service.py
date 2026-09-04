"""
Document Service Layer
Handles all document upload, validation, and management operations.
Provides secure and scalable document handling with SharePoint integration.
Uses service account authentication for SharePoint access.
import logging
"""

import logging
import os
import hashlib
import mimetypes
from datetime import datetime
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
import requests

from app.models.document import CandidateDocument
from app.core.logging import logger
from app.core.graph_auth import get_graph_token

# SharePoint configuration
SHAREPOINT_SITE_ID = os.getenv("SHAREPOINT_SITE_ID", "")
SHAREPOINT_DRIVE_ID = os.getenv("SHAREPOINT_DRIVE_ID", "")
SHAREPOINT_BASE_FOLDER = os.getenv("SHAREPOINT_BASE_FOLDER", "CandidateDocuments")

# Document type configuration
DOCUMENT_TYPES = {
    "resume": {"folder": "Resumes", "max_size": 10 * 1024 * 1024, "extensions": [".pdf", ".doc", ".docx"]},
    "pan": {"folder": "PAN_Cards", "max_size": 5 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
    "aadhar": {"folder": "Aadhar_Cards", "max_size": 5 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
    "education": {"folder": "Education_Certificates", "max_size": 10 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
    "experience": {"folder": "Experience_Letters", "max_size": 10 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
    "salary_slip": {"folder": "Salary_Slips", "max_size": 10 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
    "bank_statement": {"folder": "Bank_Statements", "max_size": 10 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
    "uan_pf": {"folder": "UAN_PF", "max_size": 10 * 1024 * 1024, "extensions": [".pdf", ".jpg", ".jpeg", ".png"]},
}

# Document types that allow multiple independent uploads (each file is a separate record).
# For all other types only ONE active document (is_latest=True) is kept per candidate.
MULTI_UPLOAD_TYPES = {"education", "experience","pan","aadhar","salary_slip","bank_statement","uan_pf"}

logger = logging.getLogger(__name__)

class DocumentService:
    """Service class for handling document operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_document(
        self, 
        file: UploadFile, 
        document_type: str
    ) -> Tuple[bool, Optional[str], Optional[bytes]]:
        """
        Validate uploaded document.
        
        Args:
            file: Uploaded file
            document_type: Type of document
            
        Returns:
            Tuple of (is_valid, error_message, file_content)
        """
        # Check document type
        if document_type not in DOCUMENT_TYPES:
            return False, f"Invalid document type. Allowed types: {', '.join(DOCUMENT_TYPES.keys())}", None
        
        config = DOCUMENT_TYPES[document_type]
        
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in config["extensions"]:
            return False, f"Invalid file extension. Allowed: {', '.join(config['extensions'])}", None
        
        # Read and check file size
        try:
            file_content = file.file.read()
            file.file.seek(0)  # Reset file pointer
            
            if len(file_content) > config["max_size"]:
                max_mb = config["max_size"] / (1024 * 1024)
                return False, f"File size exceeds maximum allowed size of {max_mb}MB", None
            
            if len(file_content) == 0:
                return False, "File is empty", None
                
            return True, None, file_content
            
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error reading file: {str(e)}")
            return False, f"Error reading file: {str(e)}", None
    
    def generate_unique_filename(
        self, 
        original_filename: str, 
        candidate_id: str,
        document_type: str
    ) -> str:
        """
        Generate unique filename with timestamp and hash.
        
        Args:
            original_filename: Original file name
            candidate_id: Candidate ID
            document_type: Type of document
            
        Returns:
            Unique filename
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(original_filename)[1]
        
        # Create hash from candidate_id + timestamp + original filename
        hash_input = f"{candidate_id}{timestamp}{original_filename}".encode()
        file_hash = hashlib.md5(hash_input).hexdigest()[:8]
        
        return f"{document_type}_{timestamp}_{file_hash}{file_ext}"
    
    def upload_to_sharepoint(
        self,
        access_token: str,
        candidate_id: str,
        document_type: str,
        file_content: bytes,
        unique_filename: str
    ) -> dict:
        """
        Upload file to SharePoint using Microsoft Graph API.
        
        Args:
            access_token: Microsoft Graph access token
            candidate_id: Candidate ID
            document_type: Type of document
            file_content: File content bytes
            unique_filename: Unique filename
            
        Returns:
            SharePoint file metadata
            
        Raises:
            HTTPException: If upload fails
        """
        folder_name = DOCUMENT_TYPES[document_type]["folder"]
        folder_path = f"{SHAREPOINT_BASE_FOLDER}/{candidate_id}/{folder_name}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream"
        }
        
        try:
            # Upload file using simple upload (< 4MB) or resumable upload (>= 4MB)
            if len(file_content) < 4 * 1024 * 1024:  # 4MB
                # Simple upload
                upload_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}/drives/{SHAREPOINT_DRIVE_ID}/root:/{folder_path}/{unique_filename}:/content"
                response = requests.put(upload_url, headers=headers, data=file_content, timeout=60)
                response.raise_for_status()
                return response.json()
            else:
                # Resumable upload for larger files
                session_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}/drives/{SHAREPOINT_DRIVE_ID}/root:/{folder_path}/{unique_filename}:/createUploadSession"
                session_response = requests.post(
                    session_url, 
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30
                )
                session_response.raise_for_status()
                upload_url = session_response.json()["uploadUrl"]
                
                # Upload file
                response = requests.put(
                    upload_url,
                    headers={"Content-Length": str(len(file_content))},
                    data=file_content,
                    timeout=120
                )
                response.raise_for_status()
                return response.json()
                
        except requests.exceptions.Timeout:
            logger.error(f"SharePoint upload timeout for {unique_filename}")
            raise HTTPException(status_code=504, detail="Upload timeout. Please try again.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"SharePoint upload failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload to SharePoint: {str(e)}")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Unexpected error during upload: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    def save_document_metadata(
        self,
        candidate_id: str,
        document_type: str,
        original_filename: str,
        unique_filename: str,
        file_size: int,
        file_extension: str,
        sharepoint_data: dict,
        uploaded_by: str
    ) -> CandidateDocument:
        """
        Save document metadata to database.
        
        Args:
            candidate_id: Candidate ID
            document_type: Type of document
            original_filename: Original filename
            unique_filename: Unique filename in SharePoint
            file_size: File size in bytes
            file_extension: File extension
            sharepoint_data: SharePoint response data
            uploaded_by: User who uploaded the document
            
        Returns:
            CandidateDocument instance
        """
        # ── Versioning logic ────────────────────────────────────────────────
        # For multi-upload types (education, experience) every file is an
        # independent record that stays visible — we never mark an earlier
        # upload as "not latest".  For all other types only one record is
        # the active latest version at a time.
        version = 1
        if document_type not in MULTI_UPLOAD_TYPES:
            existing_doc = self.db.query(CandidateDocument).filter(
                CandidateDocument.candidate_id == candidate_id,
                CandidateDocument.document_type == document_type,
                CandidateDocument.is_latest == True,
                CandidateDocument.is_deleted == False
            ).first()
            if existing_doc:
                existing_doc.is_latest = False
                version = existing_doc.version + 1
        else:
            # For multi-upload types count how many already exist so version
            # numbers are still meaningful (v1, v2, …) even though all stay
            # is_latest=True.
            count = self.db.query(CandidateDocument).filter(
                CandidateDocument.candidate_id == candidate_id,
                CandidateDocument.document_type == document_type,
                CandidateDocument.is_deleted == False
            ).count()
            version = count + 1
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        
        # Create new document record
        document = CandidateDocument(
            candidate_id=candidate_id,
            document_type=document_type,
            original_filename=original_filename,
            stored_filename=unique_filename,
            file_size=file_size,
            file_extension=file_extension,
            mime_type=mime_type,
            sharepoint_url=sharepoint_data.get("webUrl"),
            sharepoint_file_id=sharepoint_data.get("id"),
            sharepoint_folder_path=f"{SHAREPOINT_BASE_FOLDER}/{candidate_id}/{DOCUMENT_TYPES[document_type]['folder']}",
            version=version,
            is_latest=True,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.utcnow()
        )
        
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        logger.info(f"Document metadata saved: {document.id} - {document_type} for candidate {candidate_id}")
        
        return document
    
    def get_candidate_documents(
        self,
        candidate_id: str,
        document_type: Optional[str] = None,
        include_deleted: bool = False
    ) -> list[CandidateDocument]:
        """
        Get all documents for a candidate.
        
        Args:
            candidate_id: Candidate ID
            document_type: Optional filter by document type
            include_deleted: Include soft-deleted documents
            
        Returns:
            List of CandidateDocument instances
        """
        query = self.db.query(CandidateDocument).filter(
            CandidateDocument.candidate_id == candidate_id
        )
        
        if document_type:
            query = query.filter(CandidateDocument.document_type == document_type)
        
        if not include_deleted:
            query = query.filter(CandidateDocument.is_deleted == False)
        
        return query.order_by(CandidateDocument.uploaded_at.desc()).all()
    
    def soft_delete_document(self, document_id: int) -> bool:
        """
        Soft delete a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            True if successful
        """
        document = self.db.query(CandidateDocument).filter(
            CandidateDocument.id == document_id
        ).first()
        
        if not document:
            return False
        
        document.is_deleted = True
        document.deleted_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Document soft deleted: {document_id}")
        return True
    
    def verify_document(self, document_id: int, verifier_id: str) -> bool:
        """
        Mark document as verified by HR.
        
        Args:
            document_id: Document ID
            verifier_id: User ID of verifier
            
        Returns:
            True if successful
        """
        document = self.db.query(CandidateDocument).filter(
            CandidateDocument.id == document_id
        ).first()
        
        if not document:
            return False
        
        document.is_verified = True
        document.verified_by = verifier_id
        document.verified_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Document verified: {document_id} by {verifier_id}")
        return True
