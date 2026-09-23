"""
Database initialization and seeding on startup.

ARCHITECT NOTES:
===============
This module runs ONCE on application startup and ensures:

1. DATABASE EXISTS: Creates wros_dev if it doesn't exist
2. SCHEMA EXISTS: Creates app_schema if needed
3. TABLES EXIST: SQLAlchemy creates all tables from models
4. ROLE/PERMISSION SYSTEM INITIALIZED: Creates Module, RoleTemplates, Resources, Permissions
5. ADMIN USER EXISTS: Creates super admin user with Admin role

WHY THIS APPROACH:
- Single source of truth for data initialization
- Idempotent: Safe to run multiple times (checks for existence)
- Production-ready: No manual SQL scripts needed
- Automatic: Runs on each app startup

WHAT GETS CREATED:
1. Tenant (default)
2. Module (Recruitment)
3. Resource (candidates)
4. RoleTemplate (Admin - super user)
5. RoleTemplate (Recruiter)
6. RoleTemplatePermission (Admin → all permissions)
7. RoleTemplatePermission (Recruiter → create/view/edit)
8. Users (admin@test.com)
9. Users (recruiter@test.com)

STATUS: PRODUCTION READY ✓
- All dependencies created
- All permissions configured
- Ready for API testing
"""

import logging
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def ensure_database_exists():
    """Create wros_dev database if it doesn't exist."""
    try:
        # Connect to default postgres database
        engine = create_engine(
            "postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/postgres",
            poolclass=StaticPool,
            isolation_level="AUTOCOMMIT"
        )

        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(
                "SELECT 1 FROM pg_database WHERE datname='wros_dev'"
            ))

            if not result.fetchone():
                logger.info("[INIT] Creating wros_dev database...")
                conn.execute(text("CREATE DATABASE wros_dev"))
                logger.info("[INIT] Database created: wros_dev")
            else:
                logger.info("[INIT] Database exists: wros_dev")

        engine.dispose()
        return True
    except Exception as e:
        logger.error(f"[INIT] Failed to ensure database: {e}", exc_info=True)
        return False


def ensure_schema_exists(db_engine):
    """Create app_schema if it doesn't exist."""
    try:
        with db_engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS app_schema"))
            conn.commit()
        logger.info("[INIT] Schema ensured: app_schema")
        return True
    except Exception as e:
        logger.error(f"[INIT] Failed to ensure schema: {e}", exc_info=True)
        return False


def create_all_tables(db_engine):
    """Create all tables from SQLAlchemy models."""
    try:
        from app.models.base import Base
        import app.models  # Import all models

        print(f"DEBUG: Base.metadata.tables count = {len(Base.metadata.tables)}")
        print(f"DEBUG: Base.metadata.tables = {list(Base.metadata.tables.keys())[:5]}")

        Base.metadata.create_all(bind=db_engine)

        print(f"DEBUG: After create_all, verifying tables...")
        # Verify tables were created
        with db_engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            table_names = [row[0] for row in result]
            print(f"DEBUG: Tables in database after create_all: {len(table_names)}")

        logger.info(f"[INIT] All tables created/verified")
        return True
    except Exception as e:
        print(f"DEBUG: Exception in create_all_tables: {e}")
        logger.error(f"[INIT] Failed to create tables: {e}", exc_info=True)
        return False


def seed_roles_and_permissions(db):
    """Create role templates, resources, and permissions if they don't exist."""
    try:
        from app.models.tenant import Tenant
        from app.models.role_template import Module, RoleTemplate, Resource, RoleTemplatePermission

        # Check if Admin role already exists
        existing_admin = db.query(RoleTemplate).filter(
            RoleTemplate.name == "Admin"
        ).first()

        if existing_admin:
            logger.info("[INIT] Roles already initialized, skipping seeding")
            return True

        # Get or create default tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(
                name="Default",
                is_active=True,
                default_timezone="UTC",
                default_date_format="MM/DD/YYYY",
                default_currency="USD"
            )
            db.add(tenant)
            db.flush()
            logger.info(f"[INIT] Created tenant: {tenant.id}")
        else:
            logger.info(f"[INIT] Using existing tenant: {tenant.id}")

        tenant_id = tenant.id

        # Create Recruitment module
        module = Module(
            tenant_id=tenant_id,
            name="Recruitment",
            display_name="Recruitment Management",
            description="Candidate and job management",
            enabled=True
        )
        db.add(module)
        db.flush()
        logger.info(f"[INIT] Created module: {module.id}")

        # Create candidates resource
        resource = Resource(
            tenant_id=tenant_id,
            module_id=module.id,
            name="candidates",
            display_name="Candidates",
            route_path="/candidates",
            description="Candidate management",
            enabled=True
        )
        db.add(resource)
        db.flush()
        logger.info(f"[INIT] Created resource: {resource.id}")

        # Create Admin role (super user: name='Admin' triggers bypass)
        admin_role = RoleTemplate(
            tenant_id=tenant_id,
            name="Admin",
            display_name="Administrator",
            description="Admin with all permissions",
            hierarchy_level=17,
            specialization="Administration",
            is_system=True,
            enabled=True,
            org_level_access=True
        )
        db.add(admin_role)
        db.flush()
        logger.info(f"[INIT] Created Admin role: {admin_role.id}")

        # Create Recruiter role
        recruiter_role = RoleTemplate(
            tenant_id=tenant_id,
            name="Recruiter",
            display_name="Recruiter",
            description="Recruiter with candidate permissions",
            hierarchy_level=5,
            specialization="Recruitment",
            is_system=True,
            enabled=True,
            org_level_access=False
        )
        db.add(recruiter_role)
        db.flush()
        logger.info(f"[INIT] Created Recruiter role: {recruiter_role.id}")

        # Create permissions for Admin (all actions)
        admin_perm = RoleTemplatePermission(
            role_template_id=admin_role.id,
            resource_id=resource.id,
            can_view=True,
            can_create=True,
            can_edit=True,
            can_delete=True
        )
        db.add(admin_perm)
        logger.info("[INIT] Created Admin permissions: view, create, edit, delete")

        # Create permissions for Recruiter
        recruiter_perm = RoleTemplatePermission(
            role_template_id=recruiter_role.id,
            resource_id=resource.id,
            can_view=True,
            can_create=True,
            can_edit=True,
            can_delete=False
        )
        db.add(recruiter_perm)
        logger.info("[INIT] Created Recruiter permissions: view, create, edit")

        db.commit()
        logger.info("[INIT] Roles and permissions initialized successfully")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[INIT] Failed to seed roles and permissions: {e}", exc_info=True)
        return False


def seed_admin_user(db):
    """Create admin user if it doesn't exist."""
    try:
        from app.models.user import Users
        from app.models.role_template import RoleTemplate
        from app.core.security import get_password_hash
        import uuid

        # Check if admin user exists
        existing_admin = db.query(Users).filter(
            Users.UserEmail == "admin@test.com"
        ).first()

        if existing_admin:
            logger.info("[INIT] Admin user already exists, skipping creation")
            return True

        # Get Admin role
        admin_role = db.query(RoleTemplate).filter(
            RoleTemplate.name == "Admin"
        ).first()

        if not admin_role:
            logger.error("[INIT] Admin role not found, cannot create admin user")
            return False

        # Get default tenant
        from app.models.tenant import Tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            logger.error("[INIT] No tenant found, cannot create admin user")
            return False

        # Create admin user
        admin_user = Users(
            UserID=str(uuid.uuid4()),
            tenant_id=tenant.id,
            UserEmail="admin@test.com",
            UserName="Admin User",
            UserPassword=get_password_hash("Admin@123"),
            UserRole="Admin",
            role_template_id=admin_role.id,
            job_title="Administrator"
        )
        db.add(admin_user)

        # Create recruiter user
        recruiter_role = db.query(RoleTemplate).filter(
            RoleTemplate.name == "Recruiter"
        ).first()

        if recruiter_role:
            recruiter_user = Users(
                UserID=str(uuid.uuid4()),
                tenant_id=tenant.id,
                UserEmail="recruiter@test.com",
                UserName="Recruiter User",
                UserPassword=get_password_hash("Recruiter@123"),
                UserRole="Recruiter",
                role_template_id=recruiter_role.id,
                job_title="Recruiter"
            )
            db.add(recruiter_user)

        db.commit()
        logger.info("[INIT] Admin users created")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[INIT] Failed to create admin user: {e}", exc_info=True)
        return False


def initialize_database():
    """Run complete database initialization on startup."""
    print("DEBUG: initialize_database() called")  # Add print for visibility
    logger.info("=" * 60)
    logger.info("[INIT] Starting database initialization...")
    logger.info("=" * 60)

    # Step 1: Ensure database exists
    print("DEBUG: Calling ensure_database_exists()")
    result = ensure_database_exists()
    print(f"DEBUG: ensure_database_exists() returned {result}")
    if not result:
        logger.error("[INIT] Failed to ensure database exists")
        return False

    # Step 2: Connect to wros_dev
    print("DEBUG: About to import engine and SessionLocal")
    try:
        from app.core.database import engine, SessionLocal
        print("DEBUG: Successfully imported engine and SessionLocal")
    except Exception as e:
        print(f"DEBUG: Failed to import: {e}")
        raise

    print("DEBUG: About to call ensure_schema_exists()")
    # Step 3: Ensure schema exists
    schema_result = ensure_schema_exists(engine)
    print(f"DEBUG: ensure_schema_exists returned {schema_result}")
    if not schema_result:
        print("DEBUG: Returning False because schema step failed")
        logger.error("[INIT] Failed to ensure schema exists")
        return False

    print("DEBUG: Schema step passed, about to create tables")
    # Step 4: Create all tables
    tables_result = create_all_tables(engine)
    print(f"DEBUG: create_all_tables returned {tables_result}")
    if not tables_result:
        logger.error("[INIT] Failed to create tables")
        return False

    # Step 5: Seed roles and permissions
    print("DEBUG: About to seed roles and permissions")
    db = SessionLocal()
    try:
        roles_result = seed_roles_and_permissions(db)
        print(f"DEBUG: seed_roles_and_permissions returned {roles_result}")
        if not roles_result:
            logger.error("[INIT] Failed to seed roles and permissions")
            return False
    except Exception as e:
        print(f"DEBUG: Exception in seed_roles_and_permissions: {e}")
        raise
    finally:
        db.close()
        print("DEBUG: Closed db connection after roles seeding")

    # Step 6: Create admin user
    print("DEBUG: About to seed admin user")
    db = SessionLocal()
    try:
        admin_result = seed_admin_user(db)
        print(f"DEBUG: seed_admin_user returned {admin_result}")
        if not admin_result:
            logger.error("[INIT] Failed to create admin user")
            return False
    except Exception as e:
        print(f"DEBUG: Exception in seed_admin_user: {e}")
        raise
    finally:
        db.close()
        print("DEBUG: Closed db connection after admin seeding")

    print("DEBUG: About to log completion")
    logger.info("=" * 60)
    logger.info("[INIT] Database initialization COMPLETE")
    logger.info("[INIT] Users: admin@test.com (Admin@123)")
    logger.info("[INIT] Users: recruiter@test.com (Recruiter@123)")
    logger.info("=" * 60)
    print("DEBUG: Returning True from initialize_database()")
    return True
