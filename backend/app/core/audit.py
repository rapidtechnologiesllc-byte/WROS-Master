"""
import logging
HRMS-0110 — the one sanctioned way to write an audit row.

Critical usage rule: call write_audit_log() and let the CALLER commit,
in the same db.commit() that saves the actual change being audited.
This function itself never calls db.commit() or db.flush() -- if it
did, a hard-rule override could succeed while its audit row silently
rolled back on a later failure in the same request, which is exactly
the "best-effort logging call that can silently fail" gap the
Development & Review Standard calls out.

Usage:
    write_audit_log(
        db, tenant_id=user.tenant_id, entity_type="candidate",
        entity_id=candidate.candidateID, action="hard_rule_override",
        user_id=user.UserID, old_value="experience=2yrs",
        new_value="R-01 override approved by BU Head",
    )
    db.add(candidate)  # the actual change
    db.commit()        # both land together, or neither does
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    tenant_id: Optional[int] = None,
    user_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    row = AuditLog(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
    db.add(row)
    return row
