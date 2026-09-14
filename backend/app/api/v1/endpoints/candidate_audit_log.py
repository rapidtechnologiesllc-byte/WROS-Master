"""Candidate Audit Log Endpoint - Get audit history for any candidate

Returns chronological audit trail showing who changed what when.
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.models.audit_log import AuditLog
from app.models.user import Users
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates-audit"])


# ============================================================================
# Schemas
# ============================================================================

class AuditLogResponse(BaseModel):
    """Single audit log entry"""
    id: int
    entity_type: str
    entity_id: str
    action: str  # create, update, delete
    user_id: Optional[str]
    user_name: Optional[str]  # Display name from Users table
    old_value: Optional[str]
    new_value: Optional[str]
    timestamp: datetime
    ip_address: Optional[str]

    class Config:
        from_attributes = True


class CandidateAuditHistoryResponse(BaseModel):
    """Audit history for a candidate"""
    candidate_id: str
    total_entries: int
    entries: List[AuditLogResponse]


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/{candidate_id}/audit",
    response_model=CandidateAuditHistoryResponse,
    dependencies=[Depends(require_resource_permission("candidates", "can_view"))],
)
def get_candidate_audit_log(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Get audit trail for a candidate.

    Shows all changes to candidate record with timestamp and user attribution.

    Args:
        candidate_id: ID of candidate to get audit history for
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip (for pagination)
        limit: Number of records to return

    Returns:
        {
            'candidate_id': str,
            'total_entries': int,
            'entries': [
                {
                    'id': int,
                    'entity_type': 'candidate',
                    'entity_id': str,
                    'action': 'create|update|delete',
                    'user_id': str,
                    'user_name': str,
                    'old_value': str,
                    'new_value': str,
                    'timestamp': datetime,
                    'ip_address': str
                },
                ...
            ]
        }
    """
    try:
        # Get total count
        total_count = db.query(AuditLog).filter(
            AuditLog.entity_type == "candidate",
            AuditLog.entity_id == candidate_id
        ).count()

        # Get paginated entries, ordered by timestamp DESC (newest first)
        audit_entries = db.query(AuditLog).filter(
            AuditLog.entity_type == "candidate",
            AuditLog.entity_id == candidate_id
        ).order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()

        # Build response with user names
        entries = []
        for entry in audit_entries:
            user_name = "System"
            if entry.user_id:
                user = db.query(Users).filter(Users.UserID == entry.user_id).first()
                if user:
                    user_name = user.UserName or user.UserEmail or entry.user_id

            entries.append(AuditLogResponse(
                id=entry.id,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                action=entry.action,
                user_id=entry.user_id,
                user_name=user_name,
                old_value=entry.old_value,
                new_value=entry.new_value,
                timestamp=entry.timestamp,
                ip_address=entry.ip_address
            ))

        return CandidateAuditHistoryResponse(
            candidate_id=candidate_id,
            total_entries=total_count,
            entries=entries
        )

    except Exception as e:
        logger.error(f"Error fetching audit log for candidate {candidate_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audit history: {str(e)}"
        )


@router.get(
    "/{candidate_id}/audit/summary",
    response_model=dict,
    dependencies=[Depends(require_resource_permission("candidates", "can_view"))],
)
def get_candidate_audit_summary(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get summary of candidate audit history.

    Returns counts by action type (create, update, delete).

    Args:
        candidate_id: ID of candidate
        db: Database session
        current_user: Authenticated user

    Returns:
        {
            'candidate_id': str,
            'total_changes': int,
            'created_at': datetime,
            'last_modified_at': datetime,
            'changes_by_type': {
                'create': int,
                'update': int,
                'delete': int
            },
            'changed_by_users': [str]
        }
    """
    try:
        # Get all audit entries for this candidate
        entries = db.query(AuditLog).filter(
            AuditLog.entity_type == "candidate",
            AuditLog.entity_id == candidate_id
        ).order_by(AuditLog.timestamp).all()

        if not entries:
            return {
                'candidate_id': candidate_id,
                'total_changes': 0,
                'created_at': None,
                'last_modified_at': None,
                'changes_by_type': {'create': 0, 'update': 0, 'delete': 0},
                'changed_by_users': []
            }

        # Count by action type
        changes_by_type = {'create': 0, 'update': 0, 'delete': 0}
        changed_by_users = set()

        for entry in entries:
            changes_by_type[entry.action] = changes_by_type.get(entry.action, 0) + 1
            if entry.user_id:
                user = db.query(Users).filter(Users.UserID == entry.user_id).first()
                if user:
                    changed_by_users.add(user.UserName or user.UserEmail or entry.user_id)

        return {
            'candidate_id': candidate_id,
            'total_changes': len(entries),
            'created_at': entries[0].timestamp,
            'last_modified_at': entries[-1].timestamp,
            'changes_by_type': changes_by_type,
            'changed_by_users': sorted(list(changed_by_users))
        }

    except Exception as e:
        logger.error(f"Error fetching audit summary for candidate {candidate_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audit summary: {str(e)}"
        )
