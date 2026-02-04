from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Document upload schemas
class DocumentUploadResponse(BaseModel):
    """Response for document upload"""
    status: str
    message: str
    document_type: str
    file_name: str
    sharepoint_url: Optional[str] = None
    uploaded_at: datetime

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
