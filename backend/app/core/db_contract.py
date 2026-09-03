"""
import logging
Database Contract - Ensures database is properly initialized on startup.

This module guarantees:
1. All tables exist (schema creation)
2. Required tenants exist (tenant_id=1)
3. RBAC modules and resources exist
4. Default admin role template exists
5. Admin user exists with proper permissions
6. No duplicate/orphaned data

Run on every backend startup to ensure data integrity.
"""

import os
import uuid
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.user import Users
from app.core.security import get_password_hash
from app.core.logging import logger


def initialize_database():
    """
    Initialize database contract on backend startup.

    Called from app/main.py on startup.
    Ensures:
    - Schema created
    - Tenants initialized
    - RBAC structure created
    - Default admin user exists
    """
    try:
        # Step 1: Create all tables from models
        logger.info("[Contract] Step 1: Creating database tables...")
        from app import models  # Import all models to register with Base
        Base.metadata.create_all(bind=engine)
        logger.info("[OK] Database tables created")

        # Step 2: Initialize tenant
        logger.info("[Contract] Step 2: Initializing tenant...")
        _initialize_tenant()
        logger.info("[OK] Tenant initialized")

        # Step 3: Initialize RBAC structure
        logger.info("[Contract] Step 3: Initializing RBAC...")
        _initialize_rbac()
        logger.info("[OK] RBAC initialized")

        # Step 4: Initialize admin user
        logger.info("[Contract] Step 4: Initializing admin user...")
        _initialize_admin_user()
        logger.info("[OK] Admin user initialized")

        logger.info("[OK] Database contract validated - all systems ready")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[FAILED] Database contract violation: {e}", exc_info=True)
        raise


def _initialize_tenant():
    """Ensure tenant_id=1 (BlitzenX) exists."""
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            tenant = Tenant(id=1, name="BlitzenX")
            db.add(tenant)
            db.commit()
            logger.info("[Contract] Created tenant: BlitzenX (id=1)")
        else:
            logger.info("[Contract] Tenant exists: BlitzenX (id=1)")
    finally:
        db.close()


def _initialize_rbac():
    """Ensure all modules, resources, and admin role exist.

    Uses MODULES_AND_RESOURCES from app.contracts as the source of truth.
    This ensures the database always matches the API contract.
    """
    db = SessionLocal()
    try:
        # Import the authoritative API contract
        from app.contracts.api_contract import MODULES_AND_RESOURCES

        # Define display names for modules (can enhance as needed)
        module_display_names = {
            "Personal": "Personal",
            "Recruitment": "Recruitment",
            "Workforce": "Workforce",
            "Sales": "Sales",
            "Project Management": "Project Management",
            "Finance": "Finance",
            "Reporting": "Reporting",
            "System": "System",
            "Executive": "Executive",
            "Executive Dashboards": "Executive Dashboards",
            "AI & Automation": "AI & Automation",
            "Admin": "Admin",
        }

        # Use the authoritative contract structure
        modules_data = {
            module_name: module_display_names.get(module_name, module_name)
            for module_name in MODULES_AND_RESOURCES.keys()
        }

        resources_data = MODULES_AND_RESOURCES

        # Create modules
        modules = {}
        for module_name, display_name in modules_data.items():
            module = db.query(Module).filter(Module.name == module_name).first()
            if not module:
                module = Module(
                    name=module_name,
                    display_name=display_name,
                    enabled=True,
                    tenant_id=1
                )
                db.add(module)
                db.flush()
                logger.info(f"[Contract] Created module: {module_name}")
            modules[module_name] = module

        db.commit()

        # Create resources
        for module_name, resource_names in resources_data.items():
            module = modules[module_name]
            for resource_name in resource_names:
                resource = db.query(Resource).filter(
                    Resource.module_id == module.id,
                    Resource.name == resource_name
                ).first()

                if not resource:
                    resource = Resource(
                        module_id=module.id,
                        name=resource_name,
                        display_name=resource_name.replace("_", " ").title(),
                        enabled=True,
                        tenant_id=1
                    )
                    db.add(resource)
                    logger.info(f"[Contract] Created resource: {module_name}/{resource_name}")

        db.commit()

        # Create/verify Admin role template
        admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Admin").first()
        if not admin_role:
            admin_role = RoleTemplate(
                name="Admin",
                display_name="Administrator",
                description="Admin role with full access",
                is_system=True,
                tenant_id=1
            )
            db.add(admin_role)
            db.flush()
            logger.info("[Contract] Created Admin role template")

        # Grant all permissions to Admin role
        resources = db.query(Resource).all()
        for resource in resources:
            perm = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == admin_role.id,
                RoleTemplatePermission.resource_id == resource.id
            ).first()

            if not perm:
                perm = RoleTemplatePermission(
                    role_template_id=admin_role.id,
                    resource_id=resource.id,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True
                )
                db.add(perm)

        db.commit()
        logger.info(f"[Contract] Granted {len(resources)} permissions to Admin role")

    finally:
        db.close()


def _initialize_admin_user():
    """Ensure admin@blitzenx.com user exists with proper configuration and permissions."""
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin_user = db.query(Users).filter(Users.UserEmail == "admin@blitzenx.com").first()

        if not admin_user:
            # Get Admin role template
            admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Admin").first()
            if not admin_role:
                logger.error("[Contract] Admin role template not found - cannot create admin user")
                return

            # Create admin user
            admin_user = Users(
                UserID=str(uuid.uuid4()),
                UserEmail="admin@blitzenx.com",
                UserPassword=get_password_hash("Admin@123"),
                UserRole="Admin",
                UserName="Admin User",
                role_template_id=admin_role.id,
                tenant_id=1,
                timezone="Asia/Kolkata"
            )
            db.add(admin_user)
            db.commit()
            logger.info("[Contract] Created admin user: admin@blitzenx.com (password: Admin@123)")
        else:
            # Verify admin user has role template
            admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Admin").first()
            if not admin_user.role_template_id and admin_role:
                admin_user.role_template_id = admin_role.id
                db.commit()
                logger.info("[Contract] Assigned Admin role template to existing admin user")
            elif admin_user.role_template_id:
                logger.info("[Contract] Admin user verified: admin@blitzenx.com")
            else:
                logger.warning("[Contract] Admin user exists but has no role template")

        # Verify admin user has all admin screen permissions
        _verify_admin_screen_permissions(db, admin_role if admin_role else db.query(RoleTemplate).filter(RoleTemplate.name == "Admin").first())

    finally:
        db.close()


def _verify_admin_screen_permissions(db: Session, admin_role: RoleTemplate):
    """Ensure admin role has all required admin screen permissions."""
    if not admin_role:
        return

    # Admin screen requires these resource permissions
    required_admin_resources = ["users", "settings"]

    for resource_name in required_admin_resources:
        resource = db.query(Resource).filter(Resource.name == resource_name).first()
        if not resource:
            logger.warning(f"[Contract] Admin resource '{resource_name}' not found")
            continue

        # Verify permission exists and is fully enabled
        perm = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == admin_role.id,
            RoleTemplatePermission.resource_id == resource.id
        ).first()

        if perm:
            # Ensure all permissions are enabled
            if not (perm.can_view and perm.can_create and perm.can_edit and perm.can_delete):
                perm.can_view = True
                perm.can_create = True
                perm.can_edit = True
                perm.can_delete = True
                db.commit()
                logger.info(f"[Contract] Fixed admin screen permissions for: {resource_name}")
        else:
            # Create missing permission
            perm = RoleTemplatePermission(
                role_template_id=admin_role.id,
                resource_id=resource.id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            db.add(perm)
            db.commit()
            logger.info(f"[Contract] Created admin screen permission for: {resource_name}")


if __name__ == "__main__":
    # Can be run manually to verify/initialize database
    initialize_database()
    print("✅ Database contract initialized")
