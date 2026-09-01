"""
S-215/HRMS-0117 -- Error Logging Framework.

Additive to the existing file-based structured logging
(app.core.logging + log_redaction.py's RedactingFilter, already real
and CI-lint-enforced -- BR-0117-02's "no raw console logging" is
already satisfied there). What was actually missing: a DB-queryable
error_log table (Step 1/AC-3, needed for HRMS-1108's filtered reads --
files aren't queryable by integration_name/time_window) and CRITICAL
paging (Step 3/AC-1). This table is the real, additive DB sink; not a
replacement for the file logger.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base

ERROR_SEVERITIES = ("INFO", "WARN", "ERROR", "CRITICAL")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # nullable -- some errors are pre-auth

    error_type = Column(String(256), nullable=False, index=True)
    severity = Column(String(10), nullable=False, index=True)  # one of ERROR_SEVERITIES
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    request_context = Column(Text, nullable=True)  # JSON-encoded: method/path/user_id, redacted before storage
    # HRMS-1108 Integration Health Agent's own filter dimension -- not
    # built yet, this table is Step 4's real read surface for it once
    # it exists. Nullable: most errors aren't integration-specific.
    integration_name = Column(String(256), nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now(), index=True)
