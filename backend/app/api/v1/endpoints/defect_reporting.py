from app.core.logging import logger
"""Defect reporting endpoint - logs user-reported issues for QA review."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import os

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.defect import DefectReportRequest, DefectReportResponse

router = APIRouter(tags=["Defect Reporting"])

DEFECT_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "DEFECTS_LOG.md")

def ensure_defect_log_exists():
    """Create DEFECTS_LOG.md if it doesn't exist."""
    if not os.path.exists(DEFECT_LOG_FILE):
        with open(DEFECT_LOG_FILE, "w") as f:
            f.write("# Defect Reports - Production\n\n")

@router.post(
    "/defects/report",
    response_model=DefectReportResponse,
    dependencies=[Depends(require_resource_permission("defect", "create"))]
)
def report_defect(
    report: DefectReportRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Report a defect/issue found in production.

    Logs to DEFECTS_LOG.md for QA review and fixing.

    Args:
        report: DefectReportRequest with description, affected_screen, severity
        current_user: Authenticated user reporting the issue

    Returns:
        DefectReportResponse with defect_id and timestamp
    """
    try:
        ensure_defect_log_exists()

        timestamp = datetime.utcnow().isoformat()
        user_name = (current_user.UserName or current_user.UserID) if current_user else "Unknown"
        defect_id = f"DEFECT-{timestamp.replace(':', '').replace('.', '')[:-4]}"

        # A defect blocking a live production function is always CRITICAL,
        # regardless of whatever severity the reporter happened to pick --
        # enforced here, not just defaulted client-side, since that's the
        # one severity value this actually gates on downstream.
        severity = "CRITICAL" if report.blocking_production else report.severity

        # Format defect entry for markdown log
        defect_entry = f"""
## [{defect_id}] {severity.upper()} - {report.affected_screen}

**Reporter:** {user_name} ({current_user.UserEmail if current_user else "unknown"})
**Timestamp:** {timestamp}
**Severity:** {severity}
**Blocking Production Function:** {"Yes" if report.blocking_production else "No"}
**Screen:** {report.affected_screen}

**Description:**
{report.description}

**Status:** OPEN
**Resolution:** Pending review

---
"""

        # Append to defects log
        with open(DEFECT_LOG_FILE, "a") as f:
            f.write(defect_entry)

        return DefectReportResponse(
            defect_id=defect_id,
            timestamp=timestamp,
            message="Defect reported successfully and logged for QA review."
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to log defect: {str(e)}"
        )
