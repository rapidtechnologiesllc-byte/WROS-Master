import logging
"""Advanced Permission Composition Rules Service.

Implements complex permission logic including:
- Permission hierarchy (some permissions imply others)
- Conditional permissions (if-then rules)
- Permission composition (combining multiple base permissions)
- Context-aware permissions (depends on BU, tenant, user attributes)
"""

from typing import Set, List, Dict, Optional
from sqlalchemy.orm import Session
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Resource

logger = logging.getLogger(__name__)

class PermissionCompositionService:
    """Advanced permission composition and rule engine."""

    # Permission hierarchy: if you have X, you implicitly have Y
    PERMISSION_HIERARCHY = {
        "admin.manage": [
            "users.view",
            "users.edit",
            "roles.manage",
            "business_unit.manage",
            "candidate.view",
            "candidate.create",
            "candidate.edit",
            "candidate.delete",
            "employee.view",
            "employee.manage",
            "recruitment.view",
            "reports.view"
        ],
        "business_unit.manage": [
            "users.view",
            "employee.manage",
            "recruitment.view",
            "candidate.view",
            "reports.view"
        ],
        "recruitment.manage": [
            "candidate.view",
            "candidate.create",
            "candidate.edit",
            "interview.manage",
            "recruitment.view"
        ],
        "employee.manage": [
            "employee.view",
            "users.view"
        ],
        "reports.financial": [
            "reports.view",
            "invoices.view"
        ],
        "invoices.manage": [
            "invoices.view",
            "reports.view"
        ]
    }

    # Conditional rules: if conditions are met, grant additional permissions
    CONDITIONAL_RULES = {
        # If user is in Finance BU AND has finance role, grant cross-BU visibility
        "finance_cross_bu": {
            "conditions": {
                "role_name": "Finance",
                "resource_name": "reports"
            },
            "grants": ["reports.cross_bu", "invoices.cross_bu"]
        },
        # If user is Super User, grant all permissions
        "super_user": {
            "conditions": {
                "role_name": "Super User"
            },
            "grants": ["*.*"]
        },
        # If user is CEO, grant executive view
        "ceo_access": {
            "conditions": {
                "role_name": "CEO"
            },
            "grants": ["reports.executive", "business_unit.view_all"]
        },
        # If user has candidate.delete, ensure they also have candidate.edit
        "delete_implies_edit": {
            "conditions": {
                "permission": "candidate.delete"
            },
            "grants": ["candidate.edit", "candidate.view"]
        }
    }

    @staticmethod
    def expand_permissions(
        db: Session,
        role_template_id: int,
        user_attributes: Dict = None
    ) -> Set[str]:
        """
        Expand permissions for a role template to include:
        - Direct permissions
        - Implied permissions (hierarchy)
        - Conditional permissions (based on user attributes)

        Args:
            db: Database session
            role_template_id: ID of role template
            user_attributes: Dict with user context (bu_id, department, etc.)

        Returns:
            Set of all applicable permissions (flattened)
        """
        direct_permissions = PermissionCompositionService._get_direct_permissions(
            db, role_template_id
        )

        # Expand with hierarchy
        expanded = PermissionCompositionService._apply_hierarchy(direct_permissions)

        # Expand with conditional rules
        if user_attributes:
            template = db.query(RoleTemplate).filter(
                RoleTemplate.id == role_template_id
            ).first()
            if template:
                conditional = PermissionCompositionService._apply_conditional_rules(
                    expanded,
                    template.name,
                    user_attributes
                )
                expanded.update(conditional)

        return expanded

    @staticmethod
    def _get_direct_permissions(db: Session, role_template_id: int) -> Set[str]:
        """Get direct permissions assigned to role template."""
        perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role_template_id
        ).all()

        permissions = set()
        for perm in perms:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            if resource:
                if perm.can_view:
                    permissions.add(f"{resource.name}.view")
                if perm.can_create:
                    permissions.add(f"{resource.name}.create")
                if perm.can_edit:
                    permissions.add(f"{resource.name}.edit")
                if perm.can_delete:
                    permissions.add(f"{resource.name}.delete")

        return permissions

    @staticmethod
    def _apply_hierarchy(permissions: Set[str]) -> Set[str]:
        """Apply permission hierarchy: if you have X, you implicitly have Y."""
        expanded = set(permissions)

        for perm in permissions:
            if perm in PermissionCompositionService.PERMISSION_HIERARCHY:
                implied = PermissionCompositionService.PERMISSION_HIERARCHY[perm]
                expanded.update(implied)

        return expanded

    @staticmethod
    def _apply_conditional_rules(
        permissions: Set[str],
        role_name: str,
        user_attributes: Dict
    ) -> Set[str]:
        """Apply conditional rules based on user attributes."""
        additional = set()

        for rule_name, rule_config in PermissionCompositionService.CONDITIONAL_RULES.items():
            conditions = rule_config.get("conditions", {})

            # Check role name condition
            if "role_name" in conditions:
                if conditions["role_name"] != role_name:
                    continue

            # Check resource/permission condition
            if "resource_name" in conditions:
                resource = conditions["resource_name"]
                if not any(p.startswith(resource) for p in permissions):
                    continue

            if "permission" in conditions:
                if conditions["permission"] not in permissions:
                    continue

            # Apply grants if all conditions met
            grants = rule_config.get("grants", [])
            additional.update(grants)

        return additional

    @staticmethod
    def has_permission(
        db: Session,
        role_template_id: int,
        required_permission: str,
        user_attributes: Dict = None
    ) -> bool:
        """
        Check if role template has required permission.
        Considers hierarchy and conditional rules.

        Args:
            db: Database session
            role_template_id: ID of role template
            required_permission: Permission to check (e.g., "candidate.edit")
            user_attributes: Optional user context dict

        Returns:
            True if user has permission, False otherwise
        """
        permissions = PermissionCompositionService.expand_permissions(
            db, role_template_id, user_attributes
        )

        # Exact match
        if required_permission in permissions:
            return True

        # Wildcard match (if user has *.*, they have everything)
        if "*.*" in permissions:
            return True

        # Resource wildcard (if user has resource.*, they have all actions on that resource)
        resource = required_permission.split(".")[0]
        if f"{resource}.*" in permissions:
            return True

        return False

    @staticmethod
    def validate_permission_hierarchy(permissions: List[str]) -> Dict[str, any]:
        """
        Validate a permission set for conflicts or redundancies.

        Returns:
            Dict with:
            - valid: bool (no conflicts)
            - redundant_permissions: list (permissions implied by others)
            - conflicts: list (permissions that shouldn't coexist)
            - warnings: list (best practice warnings)
        """
        permission_set = set(permissions)
        redundant = []
        conflicts = []
        warnings = []

        for perm in permissions:
            # Check if this permission is implied by another
            for other_perm in permission_set - {perm}:
                if other_perm in PermissionCompositionService.PERMISSION_HIERARCHY:
                    if perm in PermissionCompositionService.PERMISSION_HIERARCHY[other_perm]:
                        redundant.append({
                            "permission": perm,
                            "implied_by": other_perm
                        })

            # Check for conflicting permissions
            # (e.g., deny and allow same resource)
            if "deny_" in perm:
                resource = perm.replace("deny_", "")
                if resource in permissions:
                    conflicts.append({
                        "conflict": perm,
                        "with": resource
                    })

        # Best practice warnings
        if "candidate.delete" in permissions and "candidate.view" not in permissions:
            warnings.append("Can delete candidates but cannot view them")

        if "admin.manage" in permissions and len(permissions) > 1:
            warnings.append("admin.manage includes all other permissions - consider removing redundant assignments")

        return {
            "valid": len(conflicts) == 0,
            "redundant_permissions": redundant,
            "conflicts": conflicts,
            "warnings": warnings
        }

    @staticmethod
    def get_permission_tree(db: Session, role_template_id: int) -> Dict:
        """Get hierarchical view of all permissions for a role template."""
        direct = PermissionCompositionService._get_direct_permissions(db, role_template_id)
        expanded = PermissionCompositionService._apply_hierarchy(direct)

        # Organize by resource
        by_resource: Dict[str, Set[str]] = {}
        for perm in expanded:
            parts = perm.split(".")
            if len(parts) == 2:
                resource, action = parts
                if resource not in by_resource:
                    by_resource[resource] = set()
                by_resource[resource].add(action)

        return {
            "direct_permissions": sorted(list(direct)),
            "implied_permissions": sorted(list(expanded - direct)),
            "by_resource": {
                resource: sorted(list(actions))
                for resource, actions in by_resource.items()
            },
            "total_permissions": len(expanded)
        }
