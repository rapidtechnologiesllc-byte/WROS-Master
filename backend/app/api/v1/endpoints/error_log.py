"""
S-215/HRMS-0117 -- Error Logging Framework.
==================================================================
Prefix: /error-log
import logging
Tag:    error-log

Step 4/AC-3: read API for HRMS-1108's filtered queries (integration_name
+ time window) once that agent exists, and the real Admin/Director-only
Error Log Viewer UI. Gated to get_current_internal_user -- no dedicated
Director role exists in this codebase's RBAC yet, same real gap already
flagged for several other stories this session.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.schemas.error_log import ErrorLogListResponse
from app.services.error_log_service import query_error_log

router = APIRouter(prefix="/error-log", tags=["error-log"])


@router.get(
    "",
    response_model=ErrorLogListResponse,
    dependencies=[Depends(get_current_internal_user)],
)
def list_errors(
    integration_name: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    errors = query_error_log(db, integration_name=integration_name, severity=severity, since=since, until=until)
    return ErrorLogListResponse(errors=errors)
