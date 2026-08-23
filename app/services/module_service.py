"""Module Service - Database-driven module and permission management."""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.module import Module, ModulePermission


class ModuleService:
    """Service for managing modules and permissions from database."""

    @staticmethod
    def get_all_modules(db: Session, tenant_id: int = 1, active_only: bool = True) -> List[Module]:
        """Get all modules, optionally filtered to active only."""
        query = db.query(Module).filter(Module.tenant_id == tenant_id)
        if active_only:
            query = query.filter(Module.is_active == True)
        return query.order_by(Module.name).all()

    @staticmethod
    def get_module_names(db: Session, tenant_id: int = 1, active_only: bool = True) -> List[str]:
        """Get list of all module names."""
        modules = ModuleService.get_all_modules(db, tenant_id, active_only)
        return [m.name for m in modules]

    @staticmethod
    def get_module_by_name(db: Session, name: str, tenant_id: int = 1) -> Optional[Module]:
        """Get a module by name."""
        return db.query(Module).filter(
            Module.name == name,
            Module.tenant_id == tenant_id
        ).first()

    @staticmethod
    def get_verbs_for_module(db: Session, module_name: str, tenant_id: int = 1) -> List[str]:
        """Get all verbs (actions) available for a module."""
        module = ModuleService.get_module_by_name(db, module_name, tenant_id)
        if not module:
            return []

        perms = db.query(ModulePermission).filter(
            ModulePermission.module_id == module.id,
            ModulePermission.tenant_id == tenant_id,
            ModulePermission.is_active == True
        ).order_by(ModulePermission.verb).all()

        return [p.verb for p in perms]

    @staticmethod
    def get_verb_matrix(db: Session, tenant_id: int = 1) -> Dict[str, List[str]]:
        """Get complete verb matrix: {module_name: [verb1, verb2, ...]}"""
        modules = ModuleService.get_all_modules(db, tenant_id, active_only=True)

        verb_matrix = {}
        for module in modules:
            verb_matrix[module.name] = ModuleService.get_verbs_for_module(db, module.name, tenant_id)

        return verb_matrix

    @staticmethod
    def permission_exists(db: Session, module_name: str, verb: str, tenant_id: int = 1) -> bool:
        """Check if a module.verb permission exists."""
        module = ModuleService.get_module_by_name(db, module_name, tenant_id)
        if not module:
            return False

        perm = db.query(ModulePermission).filter(
            ModulePermission.module_id == module.id,
            ModulePermission.verb == verb,
            ModulePermission.tenant_id == tenant_id
        ).first()

        return perm is not None

    @staticmethod
    def get_permissions_by_module(db: Session, module_name: str, tenant_id: int = 1) -> List[str]:
        """Get all permission names for a module: 'candidates.view', 'candidates.create'"""
        verbs = ModuleService.get_verbs_for_module(db, module_name, tenant_id)
        return [f"{module_name}.{verb}" for verb in verbs]

    @staticmethod
    def get_all_permissions(db: Session, tenant_id: int = 1) -> List[str]:
        """Get all permission names (module.verb) in the system."""
        perms = db.query(ModulePermission).join(Module).filter(
            Module.tenant_id == tenant_id,
            ModulePermission.tenant_id == tenant_id,
            ModulePermission.is_active == True
        ).all()

        return [p.permission_name for p in perms]

    @staticmethod
    def get_modules_by_category(db: Session, category: str, tenant_id: int = 1) -> List[Module]:
        """Get all modules in a specific category."""
        return db.query(Module).filter(
            Module.category == category,
            Module.tenant_id == tenant_id,
            Module.is_active == True
        ).order_by(Module.name).all()

    @staticmethod
    def get_permissions_by_category(db: Session, category: str, tenant_id: int = 1) -> List[str]:
        """Get all permissions for modules in a category."""
        modules = ModuleService.get_modules_by_category(db, category, tenant_id)
        perms = []
        for module in modules:
            perms.extend(ModuleService.get_permissions_by_module(db, module.name, tenant_id))
        return perms

    @staticmethod
    def create_module(db: Session, name: str, display_name: str, category: str,
                     description: Optional[str] = None, tenant_id: int = 1) -> Module:
        """Create a new module."""
        module = Module(
            name=name,
            display_name=display_name,
            category=category,
            description=description,
            is_active=True,
            tenant_id=tenant_id
        )
        db.add(module)
        db.commit()
        db.refresh(module)
        return module

    @staticmethod
    def add_verb_to_module(db: Session, module_name: str, verb: str,
                         description: Optional[str] = None, tenant_id: int = 1) -> ModulePermission:
        """Add a verb (action) to a module."""
        module = ModuleService.get_module_by_name(db, module_name, tenant_id)
        if not module:
            raise ValueError(f"Module '{module_name}' not found")

        # Check if verb already exists
        existing = db.query(ModulePermission).filter(
            ModulePermission.module_id == module.id,
            ModulePermission.verb == verb
        ).first()

        if existing:
            return existing

        perm = ModulePermission(
            module_id=module.id,
            verb=verb,
            description=description,
            is_active=True,
            tenant_id=tenant_id
        )
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm
