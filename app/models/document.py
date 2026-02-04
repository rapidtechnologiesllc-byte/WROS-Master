from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class CandidateDocument(Base):
    """
    Model for tracking candidate documents uploaded to SharePoint.
    Provides audit trail and metadata for all uploaded documents.
    """
    __tablename__ = "candidate_documents"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key to candidate
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    
    # Document information
    document_type = Column(String(50), nullable=False, index=True)  # resume, pan, aadhar, etc.
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)  # Unique filename in SharePoint
    file_size = Column(Integer, nullable=False)  # Size in bytes
    file_extension = Column(String(10), nullable=False)
    mime_type = Column(String(100), nullable=True)
    
    # SharePoint information
    sharepoint_url = Column(Text, nullable=True)
    sharepoint_file_id = Column(String(255), nullable=True)
    sharepoint_folder_path = Column(String(500), nullable=True)
    
    # Security and validation
    is_virus_scanned = Column(Boolean, default=False)
    virus_scan_result = Column(String(50), nullable=True)  # clean, infected, error
    is_verified = Column(Boolean, default=False)  # HR verification status
    verified_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Versioning
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    replaced_by = Column(Integer, ForeignKey("candidate_documents.id"), nullable=True)
    
    # Audit trail
    uploaded_by = Column(String(50), nullable=False)  # candidate_id or user_id
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    is_deleted = Column(Boolean, default=False)
    
    # Additional metadata
    notes = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)  # Comma-separated tags
    
    # Relationships
    candidate = relationship("Candidate", back_populates="documents", foreign_keys=[candidate_id])
    verifier = relationship("Users", foreign_keys=[verified_by])
    
    def __repr__(self):
        return f"<CandidateDocument(id={self.id}, candidate_id={self.candidate_id}, type={self.document_type})>"
