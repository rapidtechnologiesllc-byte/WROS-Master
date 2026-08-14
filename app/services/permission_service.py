"""Permission system service layer - enforces fine-grained access control"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import (
    DetailedPermission, DetailedRolePermission,
    FieldPermission, DataScopePermission, Users
)

class PermissionService:
    """Core permission checking and data scope enforcement"""

    @staticmethod
    def has_permission(db: Session, user_id: str, permission: str, tenant_id: int) -> bool:
        """Check if user has a specific permission.

        Args:
            db: Database session
            user_id: User's UserID
            permission: Permission name (e.g., 'candidate.create', 'candidate.delete')
            tenant_id: Tenant context

        Returns:
            True if user has permission, False otherwise
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return False

        # SUPER_USER bypass
        if user.permission_role == "SUPER_USER":
            return True

        # Get user's roles via multi-role relationship
        if not user.user_roles:
            return False

        role_ids = [ur.role_id for ur in user.user_roles]
        if not role_ids:
            return False

        # Find the permission
        perm = db.query(DetailedPermission).filter(
            and_(
                DetailedPermission.name == permission,
                DetailedPermission.tenant_id == tenant_id
            )
        ).first()

        if not perm:
            return False

        # Check if any role has this permission
        has_perm = db.query(DetailedRolePermission).filter(
            and_(
                DetailedRolePermission.role_id.in_(role_ids),
                DetailedRolePermission.permission_id == perm.id
            )
        ).first()

        return has_perm is not None

    @staticmethod
    def get_field_access_level(db: Session, user_id: str, table: str, field: str) -> str:
        """Get field-level access control.

        Returns access level: hidden, masked, readonly, or editable.
        Default to hidden for security.
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return "hidden"

        if user.permission_role == "SUPER_USER":
            return "editable"

        if not user.user_roles:
            return "hidden"

        role_ids = [ur.role_id for ur in user.user_roles]
        if not role_ids:
            return "hidden"

        # Get field access from all roles and return highest level
        access_levels = db.query(FieldPermission).filter(
            and_(
                FieldPermission.role_id.in_(role_ids),
                FieldPermission.table_name == table,
                FieldPermission.field_name == field
            )
        ).all()

        if not access_levels:
            return "hidden"

        # Priority: editable > readonly > masked > hidden
        level_priority = {"editable": 4, "readonly": 3, "masked": 2, "hidden": 1}
        max_access = max(
            level_priority.get(access.access_level, 0)
            for access in access_levels
        )

        priority_to_level = {4: "editable", 3: "readonly", 2: "masked", 1: "hidden"}
        return priority_to_level.get(max_access, "hidden")

    @staticmethod
    def get_data_scope(db: Session, user_id: str, module: str) -> dict:
        """Get data scope for a module.

        Returns dict with:
        - scope_type: ORG_WIDE, MULTI_BU, BU_ONLY, TEAM_ONLY, or NONE
        - filter_rule: JSON filter config if applicable
        - user_bu_id: User's business unit
        - user_org_node_id: User's org node (for team filtering)
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return {"scope_type": "NONE"}

        if user.permission_role == "SUPER_USER":
            return {"scope_type": "ORG_WIDE", "user_bu_id": None, "user_org_node_id": None}

        if not user.user_roles:
            return {"scope_type": "NONE"}

        role_ids = [ur.role_id for ur in user.user_roles]
        if not role_ids:
            return {"scope_type": "NONE"}

        # Get data scope from roles
        scope = db.query(DataScopePermission).filter(
            and_(
                DataScopePermission.role_id.in_(role_ids),
                DataScopePermission.module == module
            )
        ).first()

        if not scope:
            return {"scope_type": "NONE"}

        return {
            "scope_type": scope.scope_type,
            "filter_rule": scope.filter_rule,
            "user_bu_id": user.business_unit_id,
            "user_org_node_id": user.org_node_id,
            "user_id": user_id
        }

    @staticmethod
    def apply_data_scope_filter(query, scope: dict, entity_model):
        """Apply data scope filter to a SQLAlchemy query.

        Args:
            query: SQLAlchemy query object
            scope: Scope dict from get_data_scope()
            entity_model: Model class (Candidate, Employee, etc.)

        Returns:
            Filtered query
        """
        if not scope or scope.get("scope_type") == "NONE":
            return query.filter(False)  # Block all access

        if scope.get("scope_type") == "ORG_WIDE":
            return query  # No additional filter

        if scope.get("scope_type") == "MULTI_BU":
            # Filter by multiple business units (Partner assignment)
            if hasattr(entity_model, 'business_unit_id'):
                return query.filter(entity_model.business_unit_id.in_(scope.get("user_bu_ids", [])))
            return query

        if scope.get("scope_type") == "BU_ONLY":
            # Filter by single business unit
            if hasattr(entity_model, 'business_unit_id') and scope.get("user_bu_id"):
                return query.filter(entity_model.business_unit_id == scope.get("user_bu_id"))
            return query

        if scope.get("scope_type") == "TEAM_ONLY":
            # Filter by reporting relationship / org node
            if hasattr(entity_model, 'assigned_to'):
                return query.filter(entity_model.assigned_to == scope.get("user_id"))
            if hasattr(entity_model, 'reporting_manager_id') and scope.get("user_id"):
                return query.filter(entity_model.reporting_manager_id == scope.get("user_id"))
            return query

        return query
