"""Bulk employee import (CEO 2026-10-22): a dry run stores the parsed file here under its token
(sha256 of tenant + uploader + the parsed rows); apply only runs for the same uploader, before
expires_at, on a file whose rows hash to the same token -- so what is applied is exactly what was
previewed. results keeps the last apply's per-row outcome for audit."""
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base


class EmployeeImportBatch(Base):
    __tablename__ = "employee_import_batches"

    id = Column(String(64), primary_key=True)  # the import token
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    uploaded_by = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    file_name = Column(String(512), nullable=True)
    rows = Column(JSON, nullable=False)  # the parsed rows, as previewed
    row_count = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    applied_at = Column(DateTime, nullable=True)
    results = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
