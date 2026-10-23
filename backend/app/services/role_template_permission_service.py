"""
Role Template Permission Service -- the one place that decides what a person may do.

Access model (CEO 2026-10-13):
    their Manage Role's permission set   (org_roles.role_template_id; the role is the one their
                                          Job Title names -- app.services.org_roles_service)
  U their function add-on                 (users.role_template_id)
  then personal overrides                 (user_custom_permissions: grant OR restrict, per resource)

Every layer reads this service: API permission checks (has_permission), the menu and
/hr/me (get_user_permissions). Both use the same templates and the same canonical
resource per name, so a screen the menu shows is a screen the API allows.

Tenants (CEO 2026-10-13): a tenant is a parent company; its sub-companies are Companies
(locations) inside it. Modules and resources are ONE catalog shared by every tenant (seeded once,
under tenant 1); what a tenant's people may do is its own templates' permission rows, read under
the template's tenant. (Filtering the catalog by the user's tenant locked every tenant but the
first out of everything.)

Resources: a name can exist more than once (legacy seeds). The canonical one is the row
in a module of the API contract (app.contracts.api_contract) that lists that name; else
the lowest id. Grants on legacy duplicates are moved onto the canonical row at startup
(db_contract._initialize_canonical_resources).
"""
import logging
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.user import UserCustomPermission, Users

logger = logging.getLogger(__name__)

ACTION_FIELDS = {"view": "can_view", "create": "can_create", "edit": "can_edit", "delete": "can_delete"}
FLAGS = tuple(ACTION_FIELDS.values())


def canonical_resource(candidates: List[Resource], module_names: Dict[int, str]) -> Optional[Resource]:
    """Pick the canonical row among resources that share a name (see module docstring)."""
    from app.contracts.api_contract import MODULES_AND_RESOURCES

    if not candidates:
        return None

    def in_contract(r: Resource) -> bool:
        return r.name in MODULES_AND_RESOURCES.get(module_names.get(r.module_id), ())

    return sorted(candidates, key=lambda r: (not in_contract(r), r.id))[0]


def validate_addon_template(db: Session, template_id, tenant_id) -> RoleTemplate:
    """A person's function add-on (users.role_template_id) must be an enabled template of their
    tenant, and not a Manage Role's permission set (that comes with the Job Title).
    Raises ValueError otherwise."""
    from app.services.org_roles_service import owning_role

    template = db.query(RoleTemplate).filter(RoleTemplate.id == template_id).first() if template_id else None
    if template is None or template.tenant_id != tenant_id:
        raise ValueError("Role template not found")
    if not template.enabled:
        raise ValueError(f"Role template {template.display_name or template.name!r} is disabled")
    role = owning_role(db, template.id)
    if role is not None:
        raise ValueError(f"{template.display_name or template.name!r} is the {role.name} role's permission set; "
                         "give the person that Job Title instead and pick a function add-on here")
    return template


def invalidate_permissions() -> None:
    """Call after any change to templates, grants, Manage Roles, titles or overrides."""
    from app.services.permission_cache import get_permission_cache

    get_permission_cache().invalidate()


class RoleTemplatePermissionService:

    @staticmethod
    def get_user_role(db: Session, user_id: str, tenant_id: Optional[int] = None) -> RoleTemplate | None:
        """The user's function add-on template (users.role_template_id), enabled, in the tenant."""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return None
        return db.query(RoleTemplate).filter(
            RoleTemplate.id == user.role_template_id,
            RoleTemplate.tenant_id == tenant_id,
            RoleTemplate.enabled.is_(True),
        ).first()

    @staticmethod
    def get_manage_role_template(db: Session, user: Users, tenant_id: int) -> RoleTemplate | None:
        """The permission set of the Manage Role the user's Job Title names, enabled, in the tenant."""
        from app.services.org_roles_service import role_for_title

        role = role_for_title(db, tenant_id, user.job_title)
        if role is None or not role.role_template_id:
            return None
        return db.query(RoleTemplate).filter(
            RoleTemplate.id == role.role_template_id,
            RoleTemplate.tenant_id == tenant_id,
            RoleTemplate.enabled.is_(True),
        ).first()

    @staticmethod
    def templates_for(db: Session, user_id: str, tenant_id: Optional[int] = None) -> List[RoleTemplate]:
        """[Manage Role permission set, function add-on] -- whichever exist."""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is None:
            return []
        out = []
        role_template = RoleTemplatePermissionService.get_manage_role_template(db, user, tenant_id)
        if role_template is not None:
            out.append(role_template)
        addon = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
        if addon is not None and all(t.id != addon.id for t in out):
            out.append(addon)
        return out

    @staticmethod
    def get_resource_by_name(db: Session, resource_name: str, tenant_id: Optional[int] = None) -> Resource | None:
        """The canonical enabled resource with this name (case-insensitive) in the shared catalog.
        tenant_id is accepted for older callers; the catalog is the same for every tenant."""
        if not resource_name:
            return None
        candidates = db.query(Resource).filter(
            func.lower(Resource.name) == resource_name.lower(),
            Resource.enabled.is_(True),
        ).all()
        module_names = dict(db.query(Module.id, Module.name).filter(
            Module.id.in_({r.module_id for r in candidates}))) if candidates else {}
        return canonical_resource(candidates, module_names)

    @staticmethod
    def has_permission(db: Session, user_id: str, resource_name: str, action: str, tenant_id: Optional[int] = None) -> bool:
        """May the user perform action ('view' | 'create' | 'edit' | 'delete') on the resource?

        A personal override on the resource decides outright; otherwise any of the user's
        templates granting it is enough. Fails closed: any error (missing role, missing
        resource, bad input) denies."""
        try:
            field = ACTION_FIELDS.get(action)
            if not user_id or not resource_name or field is None:
                return False
            resource = RoleTemplatePermissionService.get_resource_by_name(db, resource_name, tenant_id)
            if resource is None:
                return False
            override = db.query(UserCustomPermission).filter(
                UserCustomPermission.user_id == user_id,
                UserCustomPermission.resource_id == resource.id,
            ).first()
            if override is not None:
                return bool(getattr(override, field))
            template_ids = [t.id for t in RoleTemplatePermissionService.templates_for(db, user_id, tenant_id)]
            if not template_ids:
                return False
            # rows under the template's own tenant (stale rows filed under another tenant are ignored)
            return db.query(RoleTemplatePermission.id).join(
                RoleTemplate, RoleTemplate.id == RoleTemplatePermission.role_template_id).filter(
                RoleTemplatePermission.role_template_id.in_(template_ids),
                RoleTemplatePermission.resource_id == resource.id,
                RoleTemplatePermission.tenant_id == RoleTemplate.tenant_id,
                getattr(RoleTemplatePermission, field).is_(True),
            ).first() is not None
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"has_permission({user_id}, {resource_name}, {action}, tenant={tenant_id}): {e}", exc_info=True)
            return False

    @staticmethod
    def can_view(db: Session, user_id: str, resource_name: str, tenant_id: Optional[int] = None) -> bool:
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, "view", tenant_id)

    @staticmethod
    def can_create(db: Session, user_id: str, resource_name: str, tenant_id: Optional[int] = None) -> bool:
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, "create", tenant_id)

    @staticmethod
    def can_edit(db: Session, user_id: str, resource_name: str, tenant_id: Optional[int] = None) -> bool:
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, "edit", tenant_id)

    @staticmethod
    def can_delete(db: Session, user_id: str, resource_name: str, tenant_id: Optional[int] = None) -> bool:
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, "delete", tenant_id)

    @staticmethod
    def get_user_permissions(db: Session, user_id: str, tenant_id: Optional[int] = None) -> dict:
        """{resource_name: {can_view, can_create, can_edit, can_delete, display_name, overridden}}
        for every resource the user has any right on. Same rules as has_permission.
        Cached in-process (permission_cache, 5-min TTL); a circuit breaker returns {} if the
        database keeps failing (the menu degrades to empty rather than erroring)."""
        from app.services.permission_cache import get_permission_cache
        from app.services.permission_circuit_breaker import get_permission_breaker

        cache = get_permission_cache()
        cache_key = f"{user_id}:{tenant_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            permissions = get_permission_breaker().call(
                lambda: RoleTemplatePermissionService._fetch_user_permissions_internal(db, user_id, tenant_id),
                fallback_value={},
            )
        except Exception as e:
            logger.error(f"get_user_permissions({user_id}, tenant={tenant_id}): {e} - RETURNING EMPTY FALLBACK", exc_info=True)
            return {}
        cache.set(cache_key, permissions)
        return permissions

    @staticmethod
    def _fetch_user_permissions_internal(db: Session, user_id: str, tenant_id: Optional[int] = None) -> dict:
        if not user_id:
            raise ValueError("Cannot get user permissions: user_id is required")
        templates = RoleTemplatePermissionService.templates_for(db, user_id, tenant_id)
        overrides = {o.resource_id: o for o in db.query(UserCustomPermission).filter(
            UserCustomPermission.user_id == user_id)}
        if not templates and not overrides:
            raise ValueError(f"Cannot get user permissions: no role template found for user_id={user_id}")

        # Canonical resource per name, so this agrees with has_permission
        resources = db.query(Resource).filter(Resource.enabled.is_(True)).all()  # shared catalog
        module_names = dict(db.query(Module.id, Module.name))
        by_name: Dict[str, List[Resource]] = {}
        for r in resources:
            by_name.setdefault(r.name.lower(), []).append(r)
        canonical = {c.id: c for c in (canonical_resource(group, module_names) for group in by_name.values())}

        flags: Dict[int, Dict[str, bool]] = {}
        if templates:
            for row in db.query(RoleTemplatePermission).join(
                    RoleTemplate, RoleTemplate.id == RoleTemplatePermission.role_template_id).filter(
                    RoleTemplatePermission.role_template_id.in_([t.id for t in templates]),
                    RoleTemplatePermission.tenant_id == RoleTemplate.tenant_id):
                if row.resource_id not in canonical:
                    continue
                merged = flags.setdefault(row.resource_id, {f: False for f in FLAGS})
                for f in FLAGS:
                    merged[f] = merged[f] or bool(getattr(row, f))

        permissions = {}
        for rid in set(flags) | (set(overrides) & set(canonical)):
            resource = canonical[rid]
            overridden = rid in overrides
            perms = ({f: bool(getattr(overrides[rid], f)) for f in FLAGS} if overridden
                     else flags[rid])
            if not overridden and not any(perms.values()):
                continue
            permissions[resource.name] = {**perms, "display_name": resource.display_name, "overridden": overridden}
        logger.info(f"get_user_permissions({user_id}): {len(permissions)} resources, "
                    f"{sum(1 for p in permissions.values() if p['overridden'])} overridden")
        return permissions
