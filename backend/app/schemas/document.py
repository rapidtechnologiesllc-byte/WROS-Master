from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime
from app.core.logging import logger

# Document upload schemas
class DocumentUploadResponse(BaseModel):
    """Response for document upload"""
    status: str
    message: str
    document_id: int           # ID of the created CandidateDocument record
    document_type: str
    file_name: str
    sharepoint_url: Optional[str] = None
    uploaded_at: datetime
logger = logging.getLogger(__name__)

class BulkDocumentUploadResponse(BaseModel):
    """Response for bulk document uploads"""
    status: str
    message: str
    total_uploaded: int
    failed_uploads: int
    documents: list[DocumentUploadResponse]

class DocumentListResponse(BaseModel):
    """Response for listing documents"""
    candidate_id: str
    total_documents: int
    documents: list[dict]
