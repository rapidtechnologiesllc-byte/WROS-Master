"""
import logging
User Lifecycle Management Service.

Handles:
- User termination with audit logging
- User reinstatement
- Task redistribution via round-robin when user terminates
- User audit trail retrieval (all changes: create, terminate, reinstate, permission changes)
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.user import Users
from app.models.task import Task, TASK_STATUSES
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

class UserLifecycleService:
    """Service for managing user lifecycle operations."""

    @staticmethod
    def terminate_user(
        db: Session,
        user_id: str,
        terminated_by_user_id: str,
        reason: Optional[str] = None,
    ) -> Users:
        """
        Terminate a user and redistribute their active tasks.

        Args:
            db: Database session
            user_id: ID of user to terminate
            terminated_by_user_id: ID of user performing termination
            reason: Optional reason for termination

        Returns:
            Updated Users object

        Raises:
            ValueError: If user not found or already terminated
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        if user.terminated_at is not None:
            raise ValueError(f"User {user_id} is already terminated")

        # Mark as terminated
        user.terminated_at = datetime.utcnow()
        user.terminated_by_user_id = terminated_by_user_id

        # Audit: termination
        audit_entry = AuditLog(
            tenant_id=user.tenant_id,
            entity_type="Users",
            entity_id=user_id,
            action="terminate",
            user_id=terminated_by_user_id,
            new_value=f"terminated_at={user.terminated_at.isoformat()}, reason={reason or 'N/A'}",
            timestamp=datetime.utcnow(),
        )
        db.add(audit_entry)

        db.add(user)
        db.flush()

        # Redistribute active tasks
        UserLifecycleService.redistribute_tasks_round_robin(
            db, user_id, user.department_id
        )

        db.commit()
        return user

    @staticmethod
    def reinstate_user(
        db: Session,
        user_id: str,
        reinstated_by_user_id: str,
    ) -> Users:
        """
        Reinstate a terminated user.

        Args:
            db: Database session
            user_id: ID of user to reinstate
            reinstated_by_user_id: ID of user performing reinstatement

        Returns:
            Updated Users object

        Raises:
            ValueError: If user not found or not terminated
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        if user.terminated_at is None:
            raise ValueError(f"User {user_id} is not terminated")

        # Clear termination
        previous_terminated_at = user.terminated_at
        user.terminated_at = None
        user.terminated_by_user_id = None

        # Audit: reinstatement
        audit_entry = AuditLog(
            tenant_id=user.tenant_id,
            entity_type="Users",
            entity_id=user_id,
            action="reinstate",
            user_id=reinstated_by_user_id,
            old_value=f"terminated_at={previous_terminated_at.isoformat()}",
            new_value="active",
            timestamp=datetime.utcnow(),
        )
        db.add(audit_entry)

        db.add(user)
        db.commit()
        return user

    @staticmethod
    def redistribute_tasks_round_robin(
        db: Session,
        terminated_user_id: str,
        department_id: Optional[int],
    ) -> List[Dict[str, Any]]:
        """
        Redistribute all active tasks from terminated user to team members via round-robin.

        Builds rotation list from:
        1. All active users in the same department
        2. Department manager (if set)

        Assigns tasks in round-robin order and creates audit trail entries.

        Args:
            db: Database session
            terminated_user_id: ID of terminated user
            department_id: Department ID for finding team members

        Returns:
            List of task reassignment records {task_id, old_assignee, new_assignee}
        """
        if not department_id:
            # No department scoping; tasks stay unassigned
            return []

        # Find all active tasks assigned to this user
        active_tasks = db.query(Task).filter(
            and_(
                Task.assigned_to_user_id == terminated_user_id,
                Task.status.in_([s for s in TASK_STATUSES if s not in ("COMPLETED", "CANCELLED")])
            )
        ).all()

        if not active_tasks:
            return []

        # Build rotation list: active users in department + department manager
        from app.models.org_structure import Department

        rotation_list = []
        dept = db.query(Department).filter(Department.id == department_id).first()

        # Add department manager if set and active
        if dept and dept.manager_id:
            manager = db.query(Users).filter(
                and_(
                    Users.UserID == dept.manager_id,
                    Users.terminated_at.is_(None)
                )
            ).first()
            if manager:
                rotation_list.append(manager.UserID)

        # Add all active department members
        dept_users = db.query(Users).filter(
            and_(
                Users.department_id == department_id,
                Users.terminated_at.is_(None),
                Users.UserID != terminated_user_id,  # Exclude the terminated user
            )
        ).all()

        for u in dept_users:
            if u.UserID not in rotation_list:  # Avoid duplicates
                rotation_list.append(u.UserID)

        if not rotation_list:
            # No one to reassign to; leave tasks unassigned
            return []

        # Round-robin assignment
        reassignments = []
        for idx, task in enumerate(active_tasks):
            new_assignee = rotation_list[idx % len(rotation_list)]

            # Audit: task reassignment
            audit_entry = AuditLog(
                tenant_id=task.tenant_id,
                entity_type="Task",
                entity_id=str(task.id),
                action="reassign_on_termination",
                user_id=None,  # System action
                old_value=f"assigned_to={terminated_user_id}",
                new_value=f"assigned_to={new_assignee}",
                timestamp=datetime.utcnow(),
            )
            db.add(audit_entry)

            task.assigned_to_user_id = new_assignee
            db.add(task)

            reassignments.append({
                "task_id": task.id,
                "old_assignee": terminated_user_id,
                "new_assignee": new_assignee,
            })

        db.commit()
        return reassignments

    @staticmethod
    def get_user_audit_trail(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """
        Get complete audit trail for a user.

        Includes:
        - User creation
        - Role/permission changes
        - Termination/reinstatement
        - Task reassignments (when this user was terminated)

        Args:
            db: Database session
            user_id: ID of user

        Returns:
            List of audit records sorted by timestamp (newest first)
        """
        audit_records = db.query(AuditLog).filter(
            or_(
                AuditLog.entity_id == user_id,  # Actions on this user
                and_(
                    AuditLog.entity_type == "Task",
                    AuditLog.action == "reassign_on_termination",
                    AuditLog.old_value.like(f"%{user_id}%"),  # Tasks reassigned from this user
                )
            )
        ).order_by(AuditLog.timestamp.desc()).all()

        result = []
        for record in audit_records:
            # Resolve user names for display
            action_by = None
            if record.user_id:
                action_user = db.query(Users).filter(
                    Users.UserID == record.user_id
                ).first()
                action_by = action_user.UserName if action_user else record.user_id

            result.append({
                "id": record.id,
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "action": record.action,
                "action_by": action_by,
                "old_value": record.old_value,
                "new_value": record.new_value,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            })

        return result

    @staticmethod
    def get_user_status(db: Session, user_id: str) -> str:
        """Get user status: Active or Terminated."""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return "Unknown"
        return "Active" if user.is_active() else "Terminated"

    @staticmethod
    def update_user_permissions(
        db: Session,
        user_id: str,
        role_id: int,
        changed_by_user_id: str,
    ) -> Users:
        """
        Update user's role and log the change.

        Args:
            db: Database session
            user_id: ID of user to update
            role_id: ID of new role
            changed_by_user_id: ID of user making the change

        Returns:
            Updated Users object
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get old and new role names for audit
        old_role = None
        if user.role_id:
            old_role_obj = db.query(Role).filter(Role.id == user.role_id).first()
            if old_role_obj:
                old_role = old_role_obj.name

        new_role = None
        new_role_obj = db.query(Role).filter(Role.id == role_id).first()
        if new_role_obj:
            new_role = new_role_obj.name

        # Update role
        user.role_id = role_id
        old_value = f"role={old_role or 'None'}"
        new_value = f"role={new_role or 'None'}"

        # Audit: permission change
        audit_entry = AuditLog(
            tenant_id=user.tenant_id,
            entity_type="Users",
            entity_id=user_id,
            action="permission_change",
            user_id=changed_by_user_id,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.utcnow(),
        )
        db.add(audit_entry)
        db.add(user)
        db.commit()
        return user
