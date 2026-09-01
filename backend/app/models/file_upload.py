"""
S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.

Polymorphic (entity_type, entity_id) file table -- the second half of
BR-0118-01's sanctioned pattern.

Real architecture adaptation, decided with Avinash 2026-08-05: the spec
assumes S3-backed storage with multi-region-by-continent bucket
selection. This codebase's real, already-working, already-proven file
storage is SharePoint via MS Graph (app.services.document_service --
used today for resume uploads, S-027), not S3; no AWS credentials exist
anywhere in this codebase. Building a second, fake S3 integration with
no real credentials would be exactly the kind of prod-breaking
placeholder the production-readiness bar rules out. So: SharePoint is
the real backend here too (sharepoint_url, not an S3 key), and there is
no storage_region column -- Tenant has no `continent` field either, so
BR-0118-03's region-by-continent rule has no real data to key off yet.
Flagged, not silently faked.

Virus scanning: app.services.virus_scan_service is tightly coupled to
CandidateDocument (its scan_document_content() takes a CandidateDocument
instance and mutates two of its specific columns) -- not reusable
as-is for a polymorphic table. app.services.file_upload_service below
reuses the exact same fail-closed PHILOSOPHY and exception type
(VirusScanUnavailable) with its own scan_status column matching this
story's own spec vocabulary (PENDING/CLEAN/QUARANTINED, not
virus_scan_service's clean/infected/error) -- same posture, not
duplicated logic on a shared field.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base

FILE_SCAN_STATUSES = ("PENDING", "CLEAN", "QUARANTINED")


class FileUpload(Base):
    __tablename__ = "file_uploads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    entity_type = Column(String(256), nullable=False, index=True)
    entity_id = Column(String(256), nullable=False, index=True)

    # Drives future size/type limits via system_config (S-213) -- not
    # wired yet, same honest "real column, not yet a live consumer"
    # posture as several fields on TenantAIConfig.
    file_category = Column(String(256), nullable=False, default="GENERIC", server_default="GENERIC")

    original_filename = Column(String(256), nullable=False)
    unique_filename = Column(String(256), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_extension = Column(String(20), nullable=True)
    sharepoint_url = Column(String(1000), nullable=True)

    # BR-0118-02 -- fails closed. PENDING and everything except CLEAN
    # blocks access; a scan-service failure (BR-0118-03/AC-3) also
    # lands here, never auto-approved.
    scan_status = Column(String(20), nullable=False, default="PENDING", server_default="PENDING")

    uploaded_by = Column(String(256), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
