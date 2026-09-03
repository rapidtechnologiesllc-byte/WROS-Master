"""
import logging
S-215/HRMS-0117 -- Error Logging Framework.

log_error() is the one function that writes a real, DB-queryable
error_log row -- additive to the existing file-based structured
logger (app.core.logging), never a replacement for it. BR-0117-01:
CRITICAL severity pages on-call synchronously, as part of the same
call, not batched. No dedicated on-call role/config exists in this
codebase yet (same real gap already flagged for HR/Buddy/RM roles
elsewhere this session) -- pages the first Super User, same
resolve_default_tenant_id()-style convention already established.
"""
import json
import traceback
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.error_log import ERROR_SEVERITIES, ErrorLog
from app.services.permission_helper import PermissionHelper

MAX_STACK_TRACE_CHARS = 8000

logger = logging.getLogger(__name__)

class UnknownSeverity(Exception):
    pass

def _page_on_call(db: Session, error: ErrorLog) -> None:
    from app.core.logging import logger
    from app.models.user import Users
    from app.services.notification_service import send_notification

    # Zero-hardcoding: Find admin via permission check, not hardcoded role name
    all_users = db.query(Users).order_by(Users.UserID.asc()).all()
    on_call = None
    for user in all_users:
        tenant_id = getattr(user, 'TenantID', 1)
        if PermissionHelper.has_permission(user.UserID, "admin-settings.edit", db, tenant_id):
            on_call = user
            break

    if not on_call:
        logger.warning(f"[ErrorLog] CRITICAL error {error.id} could not page on-call -- no admin found.")
        return

    send_notification(
        db, calling_context_tenant_id=on_call.tenant_id, recipient=on_call,
        priority_tier="P0",
        message=f"CRITICAL error: {error.error_type} -- {error.message[:200]}",
    )

def log_error(
    db: Session,
    *,
    error_type: str,
    severity: str,
    message: str,
    exc: Optional[BaseException] = None,
    request_context: Optional[dict] = None,
    tenant_id: Optional[int] = None,
    integration_name: Optional[str] = None,
) -> ErrorLog:
    if severity not in ERROR_SEVERITIES:
        raise UnknownSeverity(f"severity must be one of {ERROR_SEVERITIES}, got {severity!r}.")

    stack_trace = None
    if exc is not None:
        stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[:MAX_STACK_TRACE_CHARS]

    row = ErrorLog(
        tenant_id=tenant_id, error_type=error_type, severity=severity, message=message,
        stack_trace=stack_trace,
        request_context=json.dumps(request_context) if request_context else None,
        integration_name=integration_name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if severity == "CRITICAL":
        _page_on_call(db, row)

    return row

def query_error_log(
    db: Session, *, integration_name: Optional[str] = None, severity: Optional[str] = None,
    since=None, until=None, limit: int = 200,
) -> List[ErrorLog]:
    query = db.query(ErrorLog)
    if integration_name:
        query = query.filter(ErrorLog.integration_name == integration_name)
    if severity:
        query = query.filter(ErrorLog.severity == severity)
    if since:
        query = query.filter(ErrorLog.created_at >= since)
    if until:
        query = query.filter(ErrorLog.created_at <= until)
    return query.order_by(ErrorLog.created_at.desc()).limit(limit).all()
