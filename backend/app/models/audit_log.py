import logging
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, event, func
from sqlalchemy.orm import Mapper

from app.models.base import Base

logger = logging.getLogger(__name__)

class AppendOnlyViolation(Exception):
    """Raised when code tries to UPDATE or DELETE an audit_log row via the ORM."""

class AuditLog(Base):
    """
    HRMS-0110 — append-only audit trail.

    Real append-only enforcement is a database-grant-level guarantee (see
    the migration for this table: UPDATE/DELETE are revoked at the SQL
    Server login level, so not even the Admin role's DB login can modify a
    row once written). The ORM-level guard below is defense-in-depth on
    top of that, not a substitute for it -- it only stops this codebase's
    own ORM calls, not a raw SQL client connecting directly to the DB.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    entity_type = Column(String(512), nullable=False)
    entity_id = Column(String(512), nullable=False, index=True)
    action = Column(String(512), nullable=False)  # e.g. "hard_rule_override", "create", "update", "delete"
    user_id = Column(String(512), nullable=True, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=False), server_default=func.now())
    ip_address = Column(String(64), nullable=True)

@event.listens_for(AuditLog, "before_update")
def _block_update(mapper: Mapper, connection, target: AuditLog) -> None:
    raise AppendOnlyViolation("audit_log rows cannot be updated -- this table is append-only.")

@event.listens_for(AuditLog, "before_delete")
def _block_delete(mapper: Mapper, connection, target: AuditLog) -> None:
    raise AppendOnlyViolation("audit_log rows cannot be deleted -- this table is append-only.")
