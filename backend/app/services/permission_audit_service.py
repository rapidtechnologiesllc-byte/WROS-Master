"""
import logging
Permission Audit Service - Tracks all permission checks and denials.

This service logs:
- Permission granted/denied events
- Who checked what permission and when
- Why permission was denied (for denied permissions)
- Context of the check (endpoint, component, etc.)

Used for:
- Security auditing (track unauthorized access attempts)
- User access pattern analysis
- Permission violation investigation
- Compliance reporting
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.logging import logger
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

class PermissionAuditService:
    """Service for logging permission checks and access attempts."""

    @staticmethod
    def log_permission_check(
        db: Session,
        user_id: str,
        permission: str,
        granted: bool,
        check_type: str = "endpoint",
        context: str = "",
        details: Optional[dict] = None,
        tenant_id: int = 1
    ) -> AuditLog:
        """
        Log a permission check event.

        Args:
            db: Database session
            user_id: User ID performing the action
            permission: Permission string being checked (e.g., 'administration.view')
            granted: Whether permission was granted (True) or denied (False)
            check_type: Type of check - 'endpoint', 'component', 'api', 'inline'
            context: Context of the check (function name, component name, etc.)
            details: Additional details as dict
            tenant_id: Tenant ID

        Returns:
            Created AuditLog record
        """
        try:
            audit_log = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action_type="PERMISSION_CHECK",
                resource_type="PERMISSION",
                resource_id=permission,
                action_status="GRANTED" if granted else "DENIED",
                details={
                    "permission": permission,
                    "check_type": check_type,
                    "context": context,
                    "granted": granted,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(details or {})
                }
            )
            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)

            return audit_log
        except Exception as e:
            logger.error(f"Failed to log permission check: {str(e)}")
            raise

    @staticmethod
    def log_permission_denied(
        db: Session,
        user_id: str,
        permission: str,
        check_type: str = "endpoint",
        context: str = "",
        reason: str = "",
        tenant_id: int = 1
    ):
        """
        Log a permission denial event (convenience method).

        Args:
            db: Database session
            user_id: User ID
            permission: Permission being denied
            check_type: Type of check
            context: Context
            reason: Reason for denial
            tenant_id: Tenant ID
        """
        return PermissionAuditService.log_permission_check(
            db=db,
            user_id=user_id,
            permission=permission,
            granted=False,
            check_type=check_type,
            context=context,
            details={"reason": reason} if reason else None,
            tenant_id=tenant_id
        )

    @staticmethod
    def get_permission_audit_trail(
        db: Session,
        user_id: str = None,
        permission: str = None,
        granted: Optional[bool] = None,
        days: int = 30,
        limit: int = 1000,
        tenant_id: int = 1
    ) -> list:
        """
        Get audit trail for permission checks.

        Args:
            db: Database session
            user_id: Filter by user ID (optional)
            permission: Filter by permission (optional)
            granted: Filter by granted/denied status (optional)
            days: Look back N days
            limit: Maximum records to return
            tenant_id: Tenant ID

        Returns:
            List of audit log records
        """
        query = db.query(AuditLog).filter(
            AuditLog.action_type == "PERMISSION_CHECK",
            AuditLog.tenant_id == tenant_id
        )

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if permission:
            query = query.filter(AuditLog.resource_id == permission)

        if granted is not None:
            status = "GRANTED" if granted else "DENIED"
            query = query.filter(AuditLog.action_status == status)

        # Filter by date range
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.created_at >= cutoff_date)

        # Order by most recent first and limit
        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        return query.all()

    @staticmethod
    def get_denied_permissions_for_user(
        db: Session,
        user_id: str,
        days: int = 7,
        limit: int = 100,
        tenant_id: int = 1
    ) -> list:
        """
        Get all permission denials for a specific user.

        Useful for:
        - Identifying permission issues
        - Investigating unauthorized access attempts
        - Finding gaps in user's role assignments

        Args:
            db: Database session
            user_id: User ID
            days: Look back N days
            limit: Maximum records
            tenant_id: Tenant ID

        Returns:
            List of permission denial records
        """
        return PermissionAuditService.get_permission_audit_trail(
            db=db,
            user_id=user_id,
            granted=False,
            days=days,
            limit=limit,
            tenant_id=tenant_id
        )

    @staticmethod
    def get_permission_denial_summary(
        db: Session,
        user_id: str,
        days: int = 7,
        tenant_id: int = 1
    ) -> dict:
        """
        Get summary of permission denials for a user.

        Returns:
            {
                "total_denials": 42,
                "unique_permissions_denied": ["candidates.create", "projects.delete"],
                "most_common_denial": "candidates.create",
                "denial_count_by_permission": {"candidates.create": 30, "projects.delete": 12}
            }
        """
        denials = PermissionAuditService.get_denied_permissions_for_user(
            db=db,
            user_id=user_id,
            days=days,
            limit=1000,
            tenant_id=tenant_id
        )

        if not denials:
            return {
                "total_denials": 0,
                "unique_permissions_denied": [],
                "most_common_denial": None,
                "denial_count_by_permission": {}
            }

        # Count denials by permission
        denial_counts = {}
        for denial in denials:
            perm = denial.resource_id
            denial_counts[perm] = denial_counts.get(perm, 0) + 1

        # Find most common
        most_common = max(denial_counts.items(), key=lambda x: x[1])[0] if denial_counts else None

        return {
            "total_denials": len(denials),
            "unique_permissions_denied": sorted(list(denial_counts.keys())),
            "most_common_denial": most_common,
            "denial_count_by_permission": denial_counts
        }

    @staticmethod
    def get_most_denied_permissions(
        db: Session,
        days: int = 30,
        limit: int = 10,
        tenant_id: int = 1
    ) -> dict:
        """
        Get the most commonly denied permissions across all users.

        Useful for identifying permission misconfigurations.

        Args:
            db: Database session
            days: Look back N days
            limit: Number of permissions to return
            tenant_id: Tenant ID

        Returns:
            {
                "candidates.create": 256,
                "projects.delete": 134,
                ...
            }
        """

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        results = db.query(
            AuditLog.resource_id,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.action_type == "PERMISSION_CHECK",
            AuditLog.action_status == "DENIED",
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff_date
        ).group_by(
            AuditLog.resource_id
        ).order_by(
            func.count(AuditLog.id).desc()
        ).limit(limit).all()

        return {
            resource_id: count
            for resource_id, count in results
        }

    @staticmethod
    def check_for_unauthorized_access_attempts(
        db: Session,
        user_id: str,
        threshold: int = 10,
        minutes: int = 5,
        tenant_id: int = 1
    ) -> bool:
        """
        Check if user has had multiple permission denials recently.

        Indicates potential unauthorized access attempts.

        Args:
            db: Database session
            user_id: User ID to check
            threshold: Number of denials to consider "suspicious"
            minutes: Time window to check
            tenant_id: Tenant ID

        Returns:
            True if user has >= threshold denials in the time window
        """

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        denial_count = db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.action_type == "PERMISSION_CHECK",
            AuditLog.action_status == "DENIED",
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff_time
        ).count()

        return denial_count >= threshold
