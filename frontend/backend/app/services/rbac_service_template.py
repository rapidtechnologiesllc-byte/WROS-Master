"""RBAC Service - Permission checking based on role templates."""

from sqlalchemy.orm import Session
from app.models.rbac_template import RoleTemplate, RoleTemplatePermission, Resource
from app.models.user import Users


class RBACService:
    """Service for RBAC permission checking via role templates."""

    @staticmethod
    def get_user_permissions(db: Session, user_id: str) -> dict:
        """
        Get all permissions for a user based on their role template.
        Returns: {resource_id: {can_view, can_create, can_edit, can_delete}}
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return {}

        permissions = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == user.role_template_id
        ).all()

        result = {}
        for perm in permissions:
            result[perm.resource_id] = {
                "can_view": perm.can_view,
                "can_create": perm.can_create,
                "can_edit": perm.can_edit,
                "can_delete": perm.can_delete,
            }
        return result

    @staticmethod
    def get_user_permissions_flat(db: Session, user_id: str) -> list:
        """
        Get permissions as flat list of strings: [resource_id:can_view, resource_id:can_create, etc.]
        Useful for JWT payload and frontend permission arrays.
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return []

        permissions = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == user.role_template_id
        ).all()

        result = []
        for perm in permissions:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            if resource:
                if perm.can_view:
                    result.append(f"{resource.name}:view")
                if perm.can_create:
                    result.append(f"{resource.name}:create")
                if perm.can_edit:
                    result.append(f"{resource.name}:edit")
                if perm.can_delete:
                    result.append(f"{resource.name}:delete")
        return result

    @staticmethod
    def has_permission(db: Session, user_id: str, resource_name: str, action: str) -> bool:
        """
        Check if user has permission for resource + action.
        action: "view", "create", "edit", "delete"
        Returns: True if user has permission, False otherwise
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return False

        # Get resource by name
        resource = db.query(Resource).filter(Resource.name == resource_name).first()
        if not resource:
            return False

        # Get permission
        perm = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == user.role_template_id,
            RoleTemplatePermission.resource_id == resource.id
        ).first()

        if not perm:
            return False

        # Check action
        if action == "view":
            return perm.can_view
        elif action == "create":
            return perm.can_create
        elif action == "edit":
            return perm.can_edit
        elif action == "delete":
            return perm.can_delete

        return False

    @staticmethod
    def get_user_role_template(db: Session, user_id: str) -> dict:
        """Get user's role template with all permissions."""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return None

        role_template = db.query(RoleTemplate).filter(
            RoleTemplate.id == user.role_template_id
        ).first()

        if not role_template:
            return None

        # Get all permissions for this template
        permissions = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role_template.id
        ).all()

        perm_list = []
        for perm in permissions:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            if resource:
                perm_list.append({
                    "resource_id": perm.resource_id,
                    "resource_name": resource.name,
                    "resource_display": resource.display_name,
                    "can_view": perm.can_view,
                    "can_create": perm.can_create,
                    "can_edit": perm.can_edit,
                    "can_delete": perm.can_delete,
                })

        return {
            "role_template_id": role_template.id,
            "role_template_name": role_template.name,
            "role_template_display": role_template.display_name,
            "permissions": perm_list,
        }
