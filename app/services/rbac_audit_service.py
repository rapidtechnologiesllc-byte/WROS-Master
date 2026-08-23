"""RBAC Audit Logging Service - Track all permission changes for compliance."""

import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


class RBACauditService:
    """Centralized audit logging for RBAC operations."""

    @staticmethod
    def log_role_template_created(
        db: Session,
        template_id: int,
        template_name: str,
        template_data: dict,
        user_id: str,
        tenant_id: int,
        ip_address: str = None
    ) -> None:
        """Log role template creation."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="role_template",
            entity_id=str(template_id),
            action="create",
            user_id=user_id,
            new_value=json.dumps(template_data),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def log_role_template_updated(
        db: Session,
        template_id: int,
        template_name: str,
        old_data: dict,
        new_data: dict,
        user_id: str,
        tenant_id: int,
        ip_address: str = None
    ) -> None:
        """Log role template update."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="role_template",
            entity_id=str(template_id),
            action="update",
            user_id=user_id,
            old_value=json.dumps(old_data),
            new_value=json.dumps(new_data),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def log_permission_granted(
        db: Session,
        template_id: int,
        resource_name: str,
        action: str,
        user_id: str,
        tenant_id: int,
        ip_address: str = None
    ) -> None:
        """Log permission grant."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="permission",
            entity_id=f"template_{template_id}_{resource_name}_{action}",
            action="grant",
            user_id=user_id,
            new_value=json.dumps({
                "template_id": template_id,
                "resource_name": resource_name,
                "action": action,
                "granted_at": datetime.utcnow().isoformat()
            }),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def log_permission_revoked(
        db: Session,
        template_id: int,
        resource_name: str,
        action: str,
        user_id: str,
        tenant_id: int,
        ip_address: str = None
    ) -> None:
        """Log permission revoke."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="permission",
            entity_id=f"template_{template_id}_{resource_name}_{action}",
            action="revoke",
            user_id=user_id,
            old_value=json.dumps({
                "template_id": template_id,
                "resource_name": resource_name,
                "action": action,
                "revoked_at": datetime.utcnow().isoformat()
            }),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def log_role_template_deleted(
        db: Session,
        template_id: int,
        template_name: str,
        template_data: dict,
        user_id: str,
        tenant_id: int,
        ip_address: str = None
    ) -> None:
        """Log role template deletion."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="role_template",
            entity_id=str(template_id),
            action="delete",
            user_id=user_id,
            old_value=json.dumps(template_data),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def log_user_role_assigned(
        db: Session,
        user_id: str,
        role_template_id: int,
        template_name: str,
        bu_id: str = None,
        assigned_by: str = None,
        tenant_id: int = None,
        ip_address: str = None
    ) -> None:
        """Log user role assignment."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="user_role_assignment",
            entity_id=f"user_{user_id}_role_{role_template_id}",
            action="assign",
            user_id=assigned_by,
            new_value=json.dumps({
                "user_id": user_id,
                "role_template_id": role_template_id,
                "template_name": template_name,
                "bu_id": bu_id,
                "assigned_at": datetime.utcnow().isoformat()
            }),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def log_user_role_removed(
        db: Session,
        user_id: str,
        role_template_id: int,
        template_name: str,
        bu_id: str = None,
        removed_by: str = None,
        tenant_id: int = None,
        ip_address: str = None
    ) -> None:
        """Log user role removal."""
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="user_role_assignment",
            entity_id=f"user_{user_id}_role_{role_template_id}",
            action="remove",
            user_id=removed_by,
            old_value=json.dumps({
                "user_id": user_id,
                "role_template_id": role_template_id,
                "template_name": template_name,
                "bu_id": bu_id,
                "removed_at": datetime.utcnow().isoformat()
            }),
            ip_address=ip_address
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def get_audit_logs(
        db: Session,
        entity_type: str = None,
        entity_id: str = None,
        user_id: str = None,
        action: str = None,
        tenant_id: int = None,
        limit: int = 100
    ) -> list:
        """Retrieve audit logs with optional filtering."""
        query = db.query(AuditLog)

        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if tenant_id:
            query = query.filter(AuditLog.tenant_id == tenant_id)

        logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

        return [
            {
                "id": log.id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "action": log.action,
                "user_id": log.user_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "old_value": log.old_value,
                "new_value": log.new_value
            }
            for log in logs
        ]

    @staticmethod
    def get_audit_trail_for_template(
        db: Session,
        template_id: int,
        tenant_id: int
    ) -> list:
        """Get complete audit trail for a specific role template."""
        logs = db.query(AuditLog).filter(
            AuditLog.entity_type == "role_template",
            AuditLog.entity_id == str(template_id),
            AuditLog.tenant_id == tenant_id
        ).order_by(AuditLog.timestamp.desc()).all()

        return [
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "changes": {
                    "old": json.loads(log.old_value) if log.old_value else None,
                    "new": json.loads(log.new_value) if log.new_value else None
                }
            }
            for log in logs
        ]
