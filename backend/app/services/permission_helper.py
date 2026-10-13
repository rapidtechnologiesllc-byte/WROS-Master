"""Permission checks by user id: a thin adapter over app.core.authority, where every
authority rule lives (role template flags, hierarchy level, permission matrix)."""

from typing import List
from sqlalchemy.orm import Session

from app.models.user import Users
import logging

logger = logging.getLogger(__name__)

class PermissionHelper:
    """Permission checks by user id (see app.core.authority)."""

    @staticmethod
    def _user(user_id: str, db: Session, tenant_id: int):
        return db.query(Users).filter(Users.UserID == user_id, Users.tenant_id == tenant_id).first()

    @staticmethod
    def has_permission(user_id: str, permission: str, db: Session, tenant_id: int = 1) -> bool:
        """permission: '<resource>.<view|create|edit|delete>' on a seeded resource (e.g.
        'candidates.view'). Super users (role template flag) pass. A malformed string raises."""
        from app.core import authority

        return authority.has_permission(db, PermissionHelper._user(user_id, db, tenant_id), permission)

    @staticmethod
    def has_any_permission(user_id: str, permissions: List[str], db: Session, tenant_id: int = 1) -> bool:
        from app.core import authority

        return authority.has_any_permission(db, PermissionHelper._user(user_id, db, tenant_id), permissions)

    @staticmethod
    def has_all_permissions(user_id: str, permissions: List[str], db: Session, tenant_id: int = 1) -> bool:
        from app.core import authority

        user = PermissionHelper._user(user_id, db, tenant_id)
        return all(authority.has_permission(db, user, p) for p in permissions)
