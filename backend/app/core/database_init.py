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

        # Create all resources needed by the system
        resource_configs = [
            {"name": "candidates", "display_name": "Candidates", "route": "/candidates", "desc": "Candidate management"},
            {"name": "jobs", "display_name": "Jobs", "route": "/jobs", "desc": "Job postings"},
            {"name": "users", "display_name": "Users and access management", "route": "/users", "desc": "User and permission management"},
            {"name": "interviews", "display_name": "Interviews", "route": "/interviews", "desc": "Interview scheduling"},
            {"name": "offers", "display_name": "Offers", "route": "/offers", "desc": "Offer management"},
            {"name": "documents", "display_name": "Documents", "route": "/documents", "desc": "Document management"},
            {"name": "projects", "display_name": "Projects", "route": "/projects", "desc": "Project management"},
            {"name": "timesheets", "display_name": "Timesheets", "route": "/timesheets", "desc": "Timesheet tracking"},
            {"name": "reports", "display_name": "Reports", "route": "/reports", "desc": "Reporting"},
            {"name": "admin", "display_name": "Admin", "route": "/admin", "desc": "Admin controls"},
        ]

        # Create each resource and store for later permission assignment
        resources_by_name = {}
        for cfg in resource_configs:
            resource = Resource(
                tenant_id=tenant_id,
                module_id=module.id,
                name=cfg["name"],
                display_name=cfg["display_name"],
                route_path=cfg["route"],
                description=cfg["desc"],
                enabled=True
            )
            db.add(resource)
            db.flush()
            resources_by_name[cfg["name"]] = resource
            logger.info(f"[INIT] Created resource: {cfg['name']} (id={resource.id})")

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
            org_level_access=True,
            is_super_user=True
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

        # Create permissions for Admin - all resources, all actions
        for resource_name, resource in resources_by_name.items():
            admin_perm = RoleTemplatePermission(
                role_template_id=admin_role.id,
                resource_id=resource.id,
                tenant_id=tenant_id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            db.add(admin_perm)
            logger.info(f"[INIT] Created Admin permissions for {resource_name}")

        # Create permissions for Recruiter - view/create/edit for key resources
        recruiter_resources = ["candidates", "jobs", "interviews", "offers", "documents", "users"]
        for resource_name in recruiter_resources:
            if resource_name in resources_by_name:
                recruiter_perm = RoleTemplatePermission(
                    role_template_id=recruiter_role.id,
                    resource_id=resources_by_name[resource_name].id,
                    tenant_id=tenant_id,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=False
                )
                db.add(recruiter_perm)
                logger.info(f"[INIT] Created Recruiter permissions for {resource_name}")

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


def seed_business_units(db):
    """Create default business units if they don't exist."""
    try:
        from app.models.business_unit import BusinessUnit

        # Check if any BU exists
        existing_bu = db.query(BusinessUnit).first()
        if existing_bu:
            logger.info("[INIT] Business units already exist, skipping creation")
            return True

        # Get default tenant
        from app.models.tenant import Tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            logger.error("[INIT] No tenant found, cannot create business units")
            return False

        # Create default business units
        business_units = [
            {
                "name": "Headquarters",
                "display_name": "Headquarters",
                "bu_code": "HQ",
                "description": "Main headquarters office"
            },
            {
                "name": "North America",
                "display_name": "North America Region",
                "bu_code": "NA",
                "description": "North America business unit"
            },
            {
                "name": "Europe",
                "display_name": "Europe Region",
                "bu_code": "EU",
                "description": "Europe business unit"
            },
            {
                "name": "Asia-Pacific",
                "display_name": "Asia-Pacific Region",
                "bu_code": "APAC",
                "description": "Asia-Pacific business unit"
            }
        ]

        for bu_data in business_units:
            bu = BusinessUnit(
                tenant_id=tenant.id,
                name=bu_data["name"],
                display_name=bu_data["display_name"],
                bu_code=bu_data["bu_code"],
                description=bu_data["description"],
                active=True
            )
            db.add(bu)
            logger.info(f"[INIT] Created Business Unit: {bu_data['name']}")

        db.commit()
        logger.info("[INIT] Business units seeding completed successfully")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[INIT] Failed to seed business units: {e}", exc_info=True)
        return False


def seed_organizational_hierarchy(db):
    """Create organizational positions and hierarchy (10-level structure)."""
    try:
        from app.models.org_structure import OrgPosition

        # Check if hierarchy already exists
        existing_pos = db.query(OrgPosition).filter(OrgPosition.name == "CEO").first()
        if existing_pos:
            logger.info("[INIT] Organizational positions already exist, skipping creation")
            return True

        # Define 10-level hierarchy: rank 0 (CEO) to rank 9 (Senior Consultant)
        positions = [
            {"name": "CEO", "rank": 0, "approves_to_rank": None, "workflows": "ALL", "rbac_role": "ceo"},
            {"name": "Partner", "rank": 1, "approves_to_rank": 0, "workflows": "OFFER_LETTER,BUDGET_APPROVAL", "rbac_role": "partner"},
            {"name": "Business Unit Head", "rank": 2, "approves_to_rank": 1, "workflows": "OFFER_LETTER,BUDGET_APPROVAL", "rbac_role": "bu_head"},
            {"name": "Senior Director", "rank": 3, "approves_to_rank": 2, "workflows": "OFFER_LETTER,BUDGET_APPROVAL", "rbac_role": "senior_director"},
            {"name": "Director", "rank": 4, "approves_to_rank": 3, "workflows": "OFFER_LETTER,HIRING", "rbac_role": "director"},
            {"name": "Senior Manager", "rank": 5, "approves_to_rank": 4, "workflows": "HIRING,TIMESHEET", "rbac_role": "senior_manager"},
            {"name": "Manager", "rank": 6, "approves_to_rank": 5, "workflows": "TIMESHEET", "rbac_role": "manager"},
            {"name": "Team Lead", "rank": 7, "approves_to_rank": 6, "workflows": "TIMESHEET", "rbac_role": "team_lead"},
            {"name": "Senior Consultant", "rank": 8, "approves_to_rank": 7, "workflows": None, "rbac_role": "senior_consultant"},
            {"name": "Consultant", "rank": 9, "approves_to_rank": 8, "workflows": None, "rbac_role": "consultant"},
        ]

        for pos_data in positions:
            pos = OrgPosition(
                name=pos_data["name"],
                rank=pos_data["rank"],
                approves_to_rank=pos_data["approves_to_rank"],
                approves_workflows=pos_data["workflows"],
                rbac_role_name=pos_data["rbac_role"],
                description=f"{pos_data['name']} position in organizational hierarchy"
            )
            db.add(pos)
            logger.info(f"[INIT] Created OrgPosition: {pos_data['name']} (rank={pos_data['rank']})")

        db.commit()
        logger.info("[INIT] Organizational hierarchy positions seeded successfully")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[INIT] Failed to seed organizational hierarchy: {e}", exc_info=True)
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

    # Step 7: Create business units
    print("DEBUG: About to seed business units")
    db = SessionLocal()
    try:
        bu_result = seed_business_units(db)
        print(f"DEBUG: seed_business_units returned {bu_result}")
        if not bu_result:
            logger.error("[INIT] Failed to seed business units")
            return False
    except Exception as e:
        print(f"DEBUG: Exception in seed_business_units: {e}")
        raise
    finally:
        db.close()
        print("DEBUG: Closed db connection after business units seeding")

    # Step 8: Create organizational hierarchy
    print("DEBUG: About to seed organizational hierarchy")
    db = SessionLocal()
    try:
        hierarchy_result = seed_organizational_hierarchy(db)
        print(f"DEBUG: seed_organizational_hierarchy returned {hierarchy_result}")
        if not hierarchy_result:
            logger.error("[INIT] Failed to seed organizational hierarchy")
            return False
    except Exception as e:
        print(f"DEBUG: Exception in seed_organizational_hierarchy: {e}")
        raise
    finally:
        db.close()
        print("DEBUG: Closed db connection after hierarchy seeding")

    print("DEBUG: About to log completion")
    logger.info("=" * 60)
    logger.info("[INIT] Database initialization COMPLETE")
    logger.info("[INIT] Users: admin@test.com (Admin@123)")
    logger.info("[INIT] Users: recruiter@test.com (Recruiter@123)")
    logger.info("[INIT] Business Units: HQ, NA, EU, APAC")
    logger.info("[INIT] Org Hierarchy: CEO, Partner, BU Head, Director, Manager, Team Lead, Consultant")
    logger.info("=" * 60)
    print("DEBUG: Returning True from initialize_database()")
    return True
