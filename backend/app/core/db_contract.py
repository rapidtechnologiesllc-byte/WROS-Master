"""
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

import secrets
import string
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.user import Users
from app.core.security import get_password_hash
from app.core.logging import logger
from app.core.config import settings

def initialize_database():
    """
    Initialize database contract on backend startup.

    Called from app/main.py on startup.
    Ensures:
    - Schema created
    - Tenants initialized
    - RBAC structure created
    - Default admin user exists
    - Channel queue templates initialized
    """
    try:
        # Step 1: Create all tables from models
        logger.info("[Contract] Step 1: Creating database tables...")
        # Import models package - this triggers _auto_import_all_models()
        import app.models
        # Models defined outside app.models must be imported to be created
        import app.services.slm_job_metadata_service  # noqa: F401 -- SLMJobMetadata
        import app.services.slm_feedback_engine  # noqa: F401 -- SLMFeedback, SLMModelVersion
        Base.metadata.create_all(bind=engine)
        logger.info("[OK] Database tables created")

        # Step 1.5: Run schema migrations (alter existing columns, etc.)
        logger.info("[Contract] Step 1.5: Running schema migrations...")
        _run_schema_migrations()
        logger.info("[OK] Schema migrations completed")

        # Step 2: Initialize tenant
        logger.info("[Contract] Step 2: Initializing tenant...")
        _initialize_tenant()
        logger.info("[OK] Tenant initialized")

        # Step 3: Initialize RBAC structure
        logger.info("[Contract] Step 3: Initializing RBAC...")
        _initialize_rbac()
        _initialize_leadership_roles()
        logger.info("[OK] RBAC initialized")

        # Step 4: Initialize admin user
        logger.info("[Contract] Step 4: Initializing admin user...")
        _initialize_admin_user()
        logger.info("[OK] Admin user initialized")

        # Step 5: Initialize channel queue templates
        logger.info("[Contract] Step 5: Initializing channel queue templates...")
        _initialize_channel_templates()
        logger.info("[OK] Channel templates initialized")

        # Step 6: Create database indexes for performance (PHASE 3)
        logger.info("[Contract] Step 6: Creating database indexes...")
        _create_performance_indexes()
        logger.info("[OK] Database indexes created")

        # Step 7: Follow-up tasks for LinkedIn pipeline items queued before
        # task creation existed (idempotent)
        logger.info("[Contract] Step 7: Backfilling LinkedIn outreach tasks...")
        _initialize_linkedin_outreach_tasks()
        logger.info("[OK] LinkedIn outreach tasks backfilled")

        # Step 8: Approved Thunder email copy (idempotent; never overwrites DB edits)
        logger.info("[Contract] Step 8: Seeding Thunder email variants...")
        _initialize_thunder_variants()

        logger.info("[OK] Database contract validated - all systems ready")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[FAILED] Database contract violation: {e}", exc_info=True)
        raise

def _initialize_linkedin_outreach_tasks():
    """Open a follow-up task for in-progress LinkedIn pipeline items that have none."""
    from app.services.linkedin_pipeline_task_service import backfill_outreach_tasks
    db = SessionLocal()
    try:
        backfill_outreach_tasks(db)
    except Exception as e:
        # Optional data backfill: never block backend startup over it
        db.rollback()
        logger.error(f"[Contract] LinkedIn outreach task backfill failed (startup continues): {e}", exc_info=True)
    finally:
        db.close()

def _initialize_thunder_variants():
    """Seed approved Thunder email copy that is missing."""
    from app.services.thunder_mail.seed_variants import seed_thunder_variants
    db = SessionLocal()
    try:
        added = seed_thunder_variants(db)
        logger.info(f"[OK] Thunder email variants seeded ({added} added)")
    except Exception as e:
        # Sends fail closed without variants (choose_variant raises), so startup continues
        db.rollback()
        logger.error(f"[Contract] Thunder variant seeding failed (startup continues): {e}", exc_info=True)
    finally:
        db.close()

def _initialize_tenant():
    """Ensure tenant_id=1 (BlitzenX) exists."""
    from sqlalchemy import text
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

        # Explicit-PK inserts don't advance Postgres's identity sequence, so
        # the next auto-generated tenant would also try to use id=1 and hit
        # a duplicate-key error. Bump the sequence past whatever's actually
        # in the table.
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('app_schema.tenants', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM app_schema.tenants))"
        ))
        db.commit()
    finally:
        db.close()

ROLE_AUTHORITY_SEED_KEY = "role_authority_seeded"
ORG_LEVEL_SEED_ROLES = ("Super Admin", "Admin")
# Resources only the seeded admin roles start with: who may define the firm's job titles
# and levels (org-roles) is an administrator decision, not every system role's.
ADMIN_ONLY_RESOURCES = frozenset({"org-roles"})


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

        # Create all role templates if they don't exist
        role_template_configs = [
            ('Super Admin', 'Super Administrator', 'Super admin role with full system access'),
            ('Admin', 'Administrator', 'Admin role with full access'),
            ('Manager', 'Manager', 'Manager role with team management access'),
            ('User', 'Regular User', 'Regular user role with basic access'),
            ('Ops', 'Operations', 'Operations team - receives system alerts and diagnostics'),
        ]

        for role_name, display_name, description in role_template_configs:
            role_template = db.query(RoleTemplate).filter(RoleTemplate.name == role_name).first()
            if not role_template:
                role_template = RoleTemplate(
                    name=role_name,
                    display_name=display_name,
                    description=description,
                    is_system=True,
                    tenant_id=1
                )
                db.add(role_template)
                db.flush()
                logger.info(f"[Contract] Created role template: {role_name}")

        db.commit()

        # Seed a permission row for any (system role template, resource) pair
        # that has none yet. Existing rows are never touched: they reflect what
        # an admin configured in the Role Templates editor, and rewriting them
        # here would silently undo every revoke on the next restart/deploy.
        # Custom/tenant-created role templates are excluded entirely - a
        # zero-permission custom role must stay zero-permission (see the
        # zero-permission login gate in auth.py).
        resources = db.query(Resource).all()
        role_templates = db.query(RoleTemplate).filter(RoleTemplate.is_system == True).all()

        for role_template in role_templates:
            existing_resource_ids = {
                resource_id for (resource_id,) in db.query(RoleTemplatePermission.resource_id).filter(
                    RoleTemplatePermission.role_template_id == role_template.id
                )
            }
            permissions_granted = 0
            for resource in resources:
                if resource.id in existing_resource_ids:
                    continue
                # Admin-only resources start closed on the other system roles; the Role
                # Templates editor can open them later (the row exists, so it is never re-seeded)
                granted = resource.name not in ADMIN_ONLY_RESOURCES or role_template.name in ORG_LEVEL_SEED_ROLES
                db.add(RoleTemplatePermission(
                    role_template_id=role_template.id,
                    resource_id=resource.id,
                    tenant_id=role_template.tenant_id,
                    can_view=granted,
                    can_create=granted,
                    can_edit=granted,
                    can_delete=granted
                ))
                permissions_granted += 1

            db.commit()
            if permissions_granted:
                logger.info(f"[Contract] Role {role_template.name}: seeded {permissions_granted} missing permission rows")

    finally:
        db.close()

# Partner / BU Head role templates. Not system templates (those are seeded
# with every permission); created once with this starting set, after which
# the Role Templates editor owns them. "v" = view, "vce" = view/create/edit.
LEADERSHIP_ROLES = {
    "Partner": {
        "display_name": "Partner",
        "description": "Owns one or more business units across companies; revenue and headcount targets",
        "hierarchy_level": 16,
        "org_level_access": False,
        "permissions": {
            "vce": ["dashboard", "my-tasks", "my-timesheet", "my-expenses", "my-referrals", "notifications",
                    "activity-feed", "ask-flash", "candidates", "jobs", "submissions", "interviews", "clients",
                    "opportunities", "proposals", "pipeline-management", "demand-confirmation", "goals"],
            "v": ["offer-letters", "employees", "allocations", "utilization-dashboard", "resource-forecast",
                  "employee-in-bench", "projects", "resources", "invoices", "forecasts", "revenue",
                  "executive-revenue-dashboard", "kpi-dashboard", "analytics", "partner-dashboard",
                  "partner-dashboard-view", "bu-head-dashboard", "bu-head-dashboard-view", "business-units",
                  "delivery-centers", "organizational-hierarchy", "ask-thunder"],
        },
    },
    "BU Head": {
        "display_name": "BU Head",
        "description": "Runs one business unit: hiring, delivery, utilization and BU targets",
        "hierarchy_level": 14,
        "org_level_access": False,
        "permissions": {
            "vce": ["dashboard", "my-tasks", "my-timesheet", "my-expenses", "my-referrals", "notifications",
                    "activity-feed", "ask-flash", "candidates", "jobs", "submissions", "interviews",
                    "allocations", "timesheets", "projects", "resources", "opportunities", "demand-confirmation"],
            "v": ["offer-letters", "employees", "onboarding", "utilization-dashboard", "resource-forecast",
                  "employee-in-bench", "clients", "invoices", "forecasts", "revenue", "goals", "kpi-dashboard",
                  "bu-head-dashboard", "bu-head-dashboard-view", "business-units", "delivery-centers",
                  "organizational-hierarchy", "ask-thunder"],
        },
    },
    # Finance at Senior Manager level: reviews and approves invoices (CEO 2026-10-10: only
    # Finance at Senior Manager or above may approve). Assign it (or a more senior Finance
    # role -- Director 11, VP 14, CFO 16) to the people who approve what clients are billed.
    "Finance Manager": {
        "display_name": "Finance Manager",
        "description": "Finance, Senior Manager level: reviews and approves invoices, payments, revenue",
        "hierarchy_level": 9,
        "specialization": "Finance",
        "org_level_access": True,
        "permissions": {
            "vce": ["dashboard", "my-tasks", "my-timesheet", "my-expenses", "my-referrals", "notifications",
                    "activity-feed", "ask-flash", "invoices", "invoice-management", "expenses", "revenue",
                    "finance-operations", "forecasts", "budget-management", "payroll"],
            "v": ["clients", "projects", "allocations", "timesheets", "employees", "reports",
                  "executive-revenue-dashboard", "kpi-dashboard", "analytics", "business-units"],
        },
    },
    # Every converted employee gets this: their own work only. (The system "User" role is
    # seeded with every permission, so it must never be an employee's default.)
    "Employee": {
        "display_name": "Employee",
        "description": "Self-service: own timesheets, expenses, tasks, referrals, notifications",
        "hierarchy_level": 2,
        "org_level_access": False,
        "permissions": {
            "vce": ["dashboard", "my-tasks", "my-timesheet", "my-expenses", "my-referrals", "notifications",
                    "activity-feed", "ask-flash"],
        },
    },
}


def ensure_role(db, name: str, spec: dict) -> bool:
    """Create one LEADERSHIP_ROLES-style role template with its permissions if missing.
    Existing roles are never touched (the Role Templates editor owns them)."""
    if db.query(RoleTemplate).filter(RoleTemplate.name == name).first():
        return False
    resources = {r.name: r for r in db.query(Resource).all()}
    role = RoleTemplate(
        name=name, display_name=spec["display_name"], description=spec["description"],
        hierarchy_level=spec["hierarchy_level"], org_level_access=spec["org_level_access"],
        specialization=spec.get("specialization", "General"), is_system=False, tenant_id=1,
    )
    db.add(role)
    db.flush()
    granted = 0
    for mode, names in spec["permissions"].items():
        for resource_name in names:
            resource = resources.get(resource_name)
            if resource is None:
                raise RuntimeError(f"Role {name}: unknown resource {resource_name!r}")
            db.add(RoleTemplatePermission(
                role_template_id=role.id, resource_id=resource.id, tenant_id=1,
                can_view=True, can_create=mode == "vce", can_edit=mode == "vce", can_delete=False,
            ))
            granted += 1
    db.commit()
    logger.info(f"[Contract] Created role template {name} with {granted} permissions")
    return True


def _initialize_leadership_roles():
    """Create the Partner, BU Head, Finance Manager and Employee role templates if missing (idempotent)."""
    db = SessionLocal()
    try:
        for name, spec in LEADERSHIP_ROLES.items():
            ensure_role(db, name, spec)
        _move_converted_employees_off_user_role(db)
        _initialize_role_authority(db)
        _initialize_bu_location_heads(db)
        _initialize_org_roles(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()




def _initialize_role_authority(db):
    """Who sees every business unit is read from RoleTemplate.org_level_access only
    (app.core.authority). So that switching to the flag never narrows anyone's view, set
    it on the seeded Super Admin and Admin roles ONCE per tenant. A system_config marker
    records that it ran, so a later change in the Role Templates editor is never
    overwritten. (It used to run only while no role carried the flag; the seeded Finance
    Manager role carries it from creation, so Super Admin and Admin never got it.)
    (What any role may DO comes from its permission matrix alone; system roles are seeded
    with every permission by _initialize_rbac.)"""
    from app.models.system_config import SystemConfig

    tenant_ids = [t for (t,) in db.query(RoleTemplate.tenant_id)
                  .filter(RoleTemplate.name.in_(ORG_LEVEL_SEED_ROLES)).distinct().all()]
    for tenant_id in tenant_ids:
        marker = db.query(SystemConfig.id).filter(
            SystemConfig.tenant_id == tenant_id, SystemConfig.business_unit_id.is_(None),
            SystemConfig.config_key == ROLE_AUTHORITY_SEED_KEY).first()
        if marker:
            continue
        updated = db.query(RoleTemplate).filter(
            RoleTemplate.tenant_id == tenant_id, RoleTemplate.name.in_(ORG_LEVEL_SEED_ROLES)) \
            .update({RoleTemplate.org_level_access: True}, synchronize_session=False)
        db.add(SystemConfig(tenant_id=tenant_id, business_unit_id=None, config_category="SYSTEM",
                            config_key=ROLE_AUTHORITY_SEED_KEY, config_value={"org_level_access": list(ORG_LEVEL_SEED_ROLES)}))
        db.commit()
        logger.info(f"[Contract] Set org_level_access on {updated} seeded role template(s) for tenant {tenant_id}")


def _initialize_org_roles(db):
    """Seed the role list once per tenant from the org levels (idempotent: only when the
    tenant has no roles yet, so roles renamed or retired on the screen stay that way)."""
    from app.models.org_structure import OrgRole
    from app.models.tenant import Tenant
    from app.services.org_roles_service import DEFAULT_DESIGNATIONS, DEFAULT_ROLE_TITLES

    for (tenant_id,) in db.query(Tenant.id).all():
        if db.query(OrgRole.id).filter(OrgRole.tenant_id == tenant_id).first():
            continue
        db.add_all(OrgRole(tenant_id=tenant_id, name=name, hierarchy_level=level,
                           designation=DEFAULT_DESIGNATIONS.get(name)) for name, level in DEFAULT_ROLE_TITLES)
        db.commit()
        logger.info(f"[Contract] Seeded {len(DEFAULT_ROLE_TITLES)} org roles for tenant {tenant_id}")


def _initialize_bu_location_heads(db):
    """BU heads are per company (BusinessUnitLocationHead). Carry any old single
    BusinessUnit.manager_id over once (idempotent: it is cleared after the move)."""
    from app.services.bu_leadership import carry_over_single_heads

    moved = carry_over_single_heads(db)
    if moved:
        logger.info(f"[Contract] Carried {moved} BU head(s) over to per-company heads")


def _move_converted_employees_off_user_role(db):
    """Accounts created by candidate conversion (UserRole "Employee") that were given the
    full-access system "User" role move to the Employee role (idempotent)."""
    employee_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Employee").first()
    user_role = db.query(RoleTemplate).filter(RoleTemplate.name == "User").first()
    if employee_role is None or user_role is None:
        return
    moved = db.query(Users).filter(Users.UserRole == "Employee", Users.role_template_id == user_role.id) \
        .update({Users.role_template_id: employee_role.id}, synchronize_session=False)
    db.commit()
    if moved:
        logger.info(f"[Contract] Moved {moved} converted employee account(s) from the User role to Employee")


def _initialize_admin_user():
    """Ensure admin@blitzenx.com and superuser@blitzenx.com users exist with proper configuration and permissions."""
    db = SessionLocal()
    try:
        # Get Admin role template
        admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Admin").first()
        if not admin_role:
            logger.error("[Contract] Admin role template not found - cannot create admin user")
            return

        # Create or verify admin user
        admin_user = db.query(Users).filter(Users.UserEmail == "admin@blitzenx.com").first()
        if not admin_user:
            # Get Admin role template
            admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Admin").first()
            if not admin_role:
                logger.error("[Contract] Admin role template not found - cannot create admin user")
                return

            # Get admin password from environment or generate random one
            admin_password = settings.ADMIN_PASSWORD
            logger.info(f"[Contract] ADMIN_PASSWORD from config: {'SET' if admin_password else 'NOT SET'} (length: {len(admin_password) if admin_password else 0})")
            if not admin_password:
                admin_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
                logger.warning("[Contract] ADMIN_PASSWORD not set - generated temporary password. Set ADMIN_PASSWORD env var for production.")

            # Create admin user
            admin_user = Users(
                UserID="admin@blitzenx.com",
                UserEmail="admin@blitzenx.com",
                UserPassword=get_password_hash(admin_password),
                UserRole="Admin",
                UserName="Admin User",
                role_template_id=admin_role.id,
                tenant_id=1,
                timezone="Asia/Kolkata",
                password_reset_required=True
            )
            db.add(admin_user)
            db.commit()
            logger.info("[Contract] Created admin user: admin@blitzenx.com (password reset required on first login)")
        else:
            updated = False

            if not admin_user.tenant_id:
                admin_user.tenant_id = 1
                updated = True
                logger.info("[Contract] Updated admin user with default tenant_id=1")

            if not admin_user.role_template_id:
                admin_user.role_template_id = admin_role.id
                updated = True
                logger.info("[Contract] Assigned Admin role template to existing admin user")

            if updated:
                db.commit()
            logger.info("[Contract] Admin user verified: admin@blitzenx.com")

        # Create or verify superuser (for testing/initialization)
        superuser = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()
        if not superuser:
            # Create Super Admin role if it doesn't exist
            super_admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Super Admin").first()
            if not super_admin_role:
                super_admin_role = RoleTemplate(
                    name="Super Admin",
                    display_name="Super Administrator",
                    description="Super admin role with full system access",
                    is_system=True,
                    tenant_id=1
                )
                db.add(super_admin_role)
                db.flush()
                logger.info("[Contract] Created Super Admin role template")

            superuser = Users(
                UserID="superuser@blitzenx.com",
                UserEmail="superuser@blitzenx.com",
                UserPassword=get_password_hash("TestUser@123"),
                UserRole="SuperUser",
                UserName="Super User",
                role_template_id=super_admin_role.id,
                tenant_id=1,
                timezone="Asia/Kolkata",
                password_reset_required=False,
                mfa_enabled=False
            )
            db.add(superuser)
            db.commit()
            logger.info("[Contract] Created superuser: superuser@blitzenx.com")
        else:
            # Update existing superuser if missing tenant_id or role_template_id
            updated = False

            if not superuser.tenant_id:
                superuser.tenant_id = 1
                updated = True
                logger.info("[Contract] Updated superuser with default tenant_id=1")

            if not superuser.role_template_id:
                super_admin_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Super Admin").first()
                if super_admin_role:
                    superuser.role_template_id = super_admin_role.id
                    updated = True
                    logger.info("[Contract] Updated superuser with Super Admin role_template_id")

            if updated:
                db.commit()
            logger.info("[Contract] Superuser verified: superuser@blitzenx.com")

        # Verify admin user has all admin screen permissions
        _verify_admin_screen_permissions(db, admin_role)

    finally:
        db.close()

def _verify_admin_screen_permissions(db: Session, admin_role: RoleTemplate):
    """Ensure admin role has all required admin screen permissions."""
    if not admin_role:
        return

    # Admin screen requires these resource permissions
    required_admin_resources = ["users", "admin-settings", "candidates", "jobs", "interviews", "offers"]

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
                tenant_id=admin_role.tenant_id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            db.add(perm)
            db.commit()
            logger.info(f"[Contract] Created admin screen permission for: {resource_name}")

def _initialize_channel_templates():
    """Initialize default email templates and commission rules for channel queue system."""
    db = SessionLocal()
    try:
        from app.models.email_template import EmailTemplate
        from app.models.commission_rule import CommissionRule

        # Create default email templates
        default_templates = [
            {
                "name": "candidate_welcome",
                "display_name": "Candidate Welcome Email",
                "description": "Welcome email sent to new candidates",
                "subject_template": "Welcome to {{company_name}} - {{job_title}} Opportunity",
                "body_template": """Dear {{candidate_name}},

Thank you for your interest in the {{job_title}} position at {{company_name}}.

We are excited to learn more about you. Our team will be in touch shortly with next steps.

Best regards,
{{company_name}} Recruitment Team"""
            },
            {
                "name": "interview_invitation",
                "display_name": "Interview Invitation",
                "description": "Interview invitation email",
                "subject_template": "Interview Invitation - {{job_title}} at {{company_name}}",
                "body_template": """Dear {{candidate_name}},

You are invited to interview for the {{job_title}} position.

Date & Time: {{interview_date}} at {{interview_time}}
Round: {{interview_round}}
Interview Type: {{interview_type}}
Meeting Link: {{meeting_link}}

Please confirm your availability.

Best regards,
{{company_name}} Recruitment Team"""
            },
            {
                "name": "offer_letter",
                "display_name": "Offer Letter",
                "description": "Job offer letter",
                "subject_template": "Job Offer - {{job_title}} at {{company_name}}",
                "body_template": """Dear {{candidate_name}},

We are pleased to offer you the position of {{job_title}} at {{company_name}}.

Offer Details:
- Position: {{job_title}}
- Salary: {{salary}}
- Start Date: {{start_date}}
- Department: {{department}}

Please sign and return this offer by {{offer_expiry_date}}.

Best regards,
{{company_name}} Human Resources Team"""
            }
        ]

        for template_data in default_templates:
            existing = db.query(EmailTemplate).filter(EmailTemplate.name == template_data["name"]).first()
            if not existing:
                template = EmailTemplate(
                    name=template_data["name"],
                    display_name=template_data["display_name"],
                    description=template_data["description"],
                    subject_template=template_data["subject_template"],
                    body_template=template_data["body_template"],
                    version=1,
                    is_active=True,
                    created_by="system"
                )
                db.add(template)
                logger.info(f"[Contract] Created email template: {template_data['name']}")

        db.commit()

        # Create default commission rule (global default: 10%)
        default_rule = db.query(CommissionRule).filter(
            CommissionRule.partner_id == None,
            CommissionRule.deal_type == None
        ).first()

        if not default_rule:
            default_rule = CommissionRule(
                partner_id=None,  # Applies to all partners
                deal_type=None,  # Applies to all deal types
                commission_percent=10.0,
                withholding_percent=0,
                is_active=True,
                description="Default global commission rule"
            )
            db.add(default_rule)
            db.commit()
            logger.info("[Contract] Created default commission rule: 10%")

    except Exception as e:
        logger.warning(f"[Contract] Could not initialize channel templates: {e}")
        # Don't fail the entire startup if templates can't initialize
    finally:
        db.close()


def _create_performance_indexes():
    """PHASE 3: Create database indexes for high-volume audit logging tables.

    These indexes optimize queries on CandidateHistory and ActivityTimeline
    for the new audit logging system (A+C implementation).
    """
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Index for CandidateHistory - query by event_at (DATE range queries)
        try:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_candidate_history_event_at
                ON app_schema.candidate_history(event_at DESC, "candidateID")
            """))
            db.commit()
            logger.info("[Contract] Created index: idx_candidate_history_event_at")
        except Exception as e:
            logger.warning(f"[Contract] Could not create idx_candidate_history_event_at: {e}")
            db.rollback()

        # Index for CandidateHistory - query by candidateID and event_type
        try:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_candidate_history_candidate_type
                ON app_schema.candidate_history("candidateID", event_type)
            """))
            db.commit()
            logger.info("[Contract] Created index: idx_candidate_history_candidate_type")
        except Exception as e:
            logger.warning(f"[Contract] Could not create idx_candidate_history_candidate_type: {e}")
            db.rollback()

        # Index for ActivityTimeline - query by created_at (global feed)
        try:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_activity_timeline_created_at
                ON app_schema.activity_timeline(created_at DESC, entity_id)
            """))
            db.commit()
            logger.info("[Contract] Created index: idx_activity_timeline_created_at")
        except Exception as e:
            logger.warning(f"[Contract] Could not create idx_activity_timeline_created_at: {e}")
            db.rollback()

        # Index for ActivityTimeline - query by entity (candidate/user filters)
        try:
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_activity_timeline_entity
                ON app_schema.activity_timeline(entity_type, entity_id)
            """))
            db.commit()
            logger.info("[Contract] Created index: idx_activity_timeline_entity")
        except Exception as e:
            logger.warning(f"[Contract] Could not create idx_activity_timeline_entity: {e}")
            db.rollback()
    except Exception as e:
        logger.warning(f"[Contract] Could not create performance indexes: {e}")
        # Don't fail startup if indexes can't be created
    finally:
        db.close()

def _run_schema_migrations():
    """Run schema migrations to alter existing columns, add new ones, etc.

    This function handles database schema changes that cannot be automatically
    detected by SQLAlchemy's metadata.create_all() (e.g., column type changes).
    """
    db = SessionLocal()
    try:
        from sqlalchemy import text

        # Migration 1: Change api_keys_config.created_by and updated_by from Integer to String
        # These fields store user IDs (emails), not integer IDs
        try:
            db.execute(text("""
                ALTER TABLE app_schema.api_keys_config
                ALTER COLUMN created_by TYPE VARCHAR(512);
            """))
            db.execute(text("""
                ALTER TABLE app_schema.api_keys_config
                ALTER COLUMN updated_by TYPE VARCHAR(512);
            """))
            db.commit()
            logger.info("[Contract] Migration: Changed api_keys_config.created_by/updated_by to VARCHAR(512)")
        except Exception as e:
            # Column might already be VARCHAR or table doesn't exist yet
            if "column" in str(e).lower() or "does not exist" in str(e).lower():
                logger.debug(f"[Contract] Migration skipped (column already altered or table doesn't exist): {e}")
            else:
                logger.warning(f"[Contract] Migration warning: {e}")
            db.rollback()

        # Migration 2: Add thunder_assigned_at column to candidate_status if missing
        # This column tracks when Thunder was assigned to the candidate
        try:
            db.execute(text("""
                ALTER TABLE app_schema.candidate_status
                ADD COLUMN thunder_assigned_at TIMESTAMP WITH TIME ZONE NULL;
            """))
            db.commit()
            logger.info("[Contract] Migration: Added thunder_assigned_at column to candidate_status")
        except Exception as e:
            # Column might already exist
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.debug(f"[Contract] Migration skipped (column already exists): {e}")
            elif "table" in str(e).lower() and "does not exist" in str(e).lower():
                logger.debug(f"[Contract] Migration skipped (candidate_status table doesn't exist yet): {e}")
            else:
                logger.warning(f"[Contract] Migration warning: {e}")
            db.rollback()

        # Migration 3: Add candidate columns present on the Candidate model but
        # missing from the live table (schema drift from create_all() never
        # altering existing tables).
        candidate_columns = [
            ("tenant_id", "INTEGER NOT NULL DEFAULT 1"),
            ("candidate_notice_period", "INTEGER NULL"),
            ("referral_id", "VARCHAR(512) NULL"),
            ("created_by_user_id", "VARCHAR(512) NULL"),
            ("created_by_name", "VARCHAR(512) NULL"),
            ("recruitment_source", "VARCHAR(512) NULL"),
            ("assigned_recruiter_id", "VARCHAR(512) NULL"),
            ("assigned_recruiter_changed_at", "TIMESTAMP NULL"),
            ("assigned_recruiter_changed_by", "VARCHAR(512) NULL"),
        ]
        for column_name, column_def in candidate_columns:
            try:
                db.execute(text(f"""
                    ALTER TABLE app_schema.candidates
                    ADD COLUMN IF NOT EXISTS {column_name} {column_def};
                """))
                db.commit()
                logger.info(f"[Contract] Migration: Ensured candidates.{column_name} exists")
            except Exception as e:
                if "table" in str(e).lower() and "does not exist" in str(e).lower():
                    logger.debug(f"[Contract] Migration skipped (candidates table doesn't exist yet): {e}")
                else:
                    logger.warning(f"[Contract] Migration warning for candidates.{column_name}: {e}")
                db.rollback()

        # Migration 4: FK integrity + indexes for the candidate columns added
        # above (candidates.referral_id -> employee_referrals.referral_id,
        # plus lookup indexes on the audit/referral columns).
        try:
            db.execute(text("""
                ALTER TABLE app_schema.candidates
                ADD CONSTRAINT fk_candidate_referral
                FOREIGN KEY (referral_id) REFERENCES app_schema.employee_referrals(referral_id)
                ON DELETE SET NULL;
            """))
            db.commit()
            logger.info("[Contract] Migration: Added fk_candidate_referral constraint")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.debug(f"[Contract] Migration skipped (fk_candidate_referral already exists): {e}")
            else:
                logger.warning(f"[Contract] Migration warning for fk_candidate_referral: {e}")
            db.rollback()

        candidate_indexes = [
            ("ix_candidate_referral_id", "referral_id"),
            ("ix_candidate_created_by_user_id", "created_by_user_id"),
            ("ix_candidate_recruitment_source", "recruitment_source"),
        ]
        for index_name, column_name in candidate_indexes:
            try:
                db.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON app_schema.candidates({column_name});
                """))
                db.commit()
                logger.info(f"[Contract] Migration: Ensured index {index_name} exists")
            except Exception as e:
                logger.warning(f"[Contract] Migration warning for index {index_name}: {e}")
                db.rollback()

        # Migration 5: Schema drift on other tables where the model has columns
        # the live table lacks (same create_all()-never-alters-existing-tables
        # gap as Migration 3). Discovered via a full model-vs-DB column scan.
        drifted_tables = {
            "jobs": [
                ("is_deleted", "BOOLEAN NOT NULL DEFAULT false"),
                ("deleted_at", "TIMESTAMP NULL"),
                # Demand merged into Jobs: the client/delivery side of a requisition
                ("client_id", "VARCHAR(512) NULL REFERENCES app_schema.clients(id)"),
                ("project_id", "VARCHAR(512) NULL REFERENCES app_schema.projects(id)"),
                ("opportunity_id", "VARCHAR(512) NULL REFERENCES app_schema.opportunities(id)"),
                ("required_skills", "TEXT NULL"),
                ("nice_to_have_skills", "TEXT NULL"),
                ("max_experience_years", "NUMERIC(4,1) NULL"),
                ("work_location", "VARCHAR(20) NOT NULL DEFAULT 'REMOTE'"),
                ("employment_type", "VARCHAR(50) NOT NULL DEFAULT 'W2_FULLTIME'"),
                ("interview_type_required", "VARCHAR(20) NOT NULL DEFAULT 'L1_AND_L2'"),
                ("positions_filled", "INTEGER NOT NULL DEFAULT 0"),
                ("billing_rate_usd_cents", "INTEGER NULL"),
                ("budget_min_usd_cents", "INTEGER NULL"),
                ("budget_max_usd_cents", "INTEGER NULL"),
                ("demand_status", "VARCHAR(20) NOT NULL DEFAULT 'DRAFT'"),
                ("sourcing_enabled", "BOOLEAN NOT NULL DEFAULT false"),
                ("bench_first_checked", "BOOLEAN NOT NULL DEFAULT false"),
                ("assigned_recruiter_employee_id", "VARCHAR(512) NULL REFERENCES app_schema.employees(id)"),
                ("delivery_engine", "VARCHAR(20) NOT NULL DEFAULT 'SPECIALITY'"),
                ("confirmation_status", "VARCHAR(20) NOT NULL DEFAULT 'POTENTIAL'"),
                ("sow_reference", "VARCHAR(512) NULL"),
                ("sow_received_date", "DATE NULL"),
                ("source_type", "VARCHAR(20) NOT NULL DEFAULT 'DIRECT'"),
                ("duration_hours", "INTEGER NULL"),
                ("revenue_potential_usd_cents", "INTEGER NULL"),
                ("created_by", "VARCHAR(512) NULL"),
                ("updated_at", "TIMESTAMP NULL DEFAULT now()"),
                ("closed_at", "TIMESTAMP NULL"),
            ],
            "conversation_events": [
                ("tenant_id", "VARCHAR(50) NOT NULL DEFAULT '1'"),
            ],
            "linkedin_candidate_pipeline": [
                ("email_collected_at", "TIMESTAMP NULL"),
                ("email_from_recruiter", "VARCHAR(255) NULL"),
                ("phone_verified_by", "VARCHAR(255) NULL"),
                ("task_id", "VARCHAR(36) NULL"),
            ],
            "users": [
                ("org_node_id", "VARCHAR(512) NULL REFERENCES app_schema.org_nodes(id)"),
                ("location_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id)"),
                # Existing users must not be forced into a password reset;
                # the model still defaults new users to True.
                ("password_reset_required", "BOOLEAN NOT NULL DEFAULT false"),
            ],
            # Goal tree Org -> Location (legal entity, e.g. BXUS/BXIN) -> Partner -> BU
            "business_units": [
                ("location_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE SET NULL"),
                ("partner_user_id", 'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
            ],
            "clients": [
                ("account_manager_user_id", 'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
                # Contracting company (BX-US / BX-IN): revenue splits by company
                ("contracting_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE SET NULL"),
            ],
            "locations": [
                ("state", "VARCHAR(512) NULL"),
                ("parent_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE RESTRICT"),
            ],
            "intercompany_settlements": [
                ("business_unit_id", "INTEGER NULL REFERENCES app_schema.business_units(id) ON DELETE SET NULL"),
            ],
            # Production startup crashed on role_templates.hierarchy_level
            # (2026-10-05); the rest were found by the same full scan.
            "role_templates": [
                ("hierarchy_level", "INTEGER NOT NULL DEFAULT 5"),
                ("specialization", "VARCHAR(512) NOT NULL DEFAULT 'General'"),
                ("is_super_user", "BOOLEAN NOT NULL DEFAULT false"),
                ("org_level_access", "BOOLEAN NOT NULL DEFAULT false"),
            ],
            "org_nodes": [
                ("company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE SET NULL"),
                ("hierarchy_level", "INTEGER NOT NULL DEFAULT 5"),
                ("specialization", "VARCHAR(512) NOT NULL DEFAULT 'General'"),
            ],
            "role_template_permissions": [
                ("tenant_id", "INTEGER NOT NULL DEFAULT 1 REFERENCES app_schema.tenants(id)"),
            ],
            "candidates": [
                ("thunder_enabled", "BOOLEAN NOT NULL DEFAULT true"),
                ("status_changed_at", "TIMESTAMP NULL"),
                ("previous_status", "VARCHAR(100) NULL"),
                ("status_change_reason", "VARCHAR(500) NULL"),
                ("upload_status", "VARCHAR(50) NULL"),
                ("expected_document_count", "INTEGER NULL"),
                ("actual_document_count", "INTEGER NULL"),
                ("upload_started_at", "TIMESTAMP NULL"),
                ("last_document_uploaded_at", "TIMESTAMP NULL"),
                ("queued_at", "TIMESTAMP NULL"),
                ("processing_started_at", "TIMESTAMP NULL"),
                ("processing_completed_at", "TIMESTAMP NULL"),
                ("upload_error", "TEXT NULL"),
                ("celery_task_id", "VARCHAR(512) NULL"),
                ('"candidateExpectedSalaryType"', "VARCHAR(50) NULL"),
                ('"candidateCurrentSalaryType"', "VARCHAR(50) NULL"),
            ],
            "candidate_conversations": [
                ("next_touch_scheduled_at", "TIMESTAMP NULL"),
            ],
            "employees": [
                # Employer of record (BX-US / BX-IN): headcount splits by company
                ("company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE SET NULL"),
                ("guidewire_certification_current", "VARCHAR(50) NULL"),
                ("guidewire_certification_expected", "VARCHAR(50) NULL"),
            ],
            "candidate_education_forms": [
                ("education_level", "VARCHAR(100) NULL"),
            ],
            "candidate_experience_forms": [
                ("responsibilities", "TEXT NULL"),
            ],
            "candidate_documents": [
                ("document_name", "VARCHAR(512) NULL"),
                ("upload_sequence", "INTEGER NULL"),
            ],
        }
        for table_name, columns in drifted_tables.items():
            for column_name, column_def in columns:
                try:
                    db.execute(text(f"""
                        ALTER TABLE app_schema.{table_name}
                        ADD COLUMN IF NOT EXISTS {column_name} {column_def};
                    """))
                    db.commit()
                    logger.info(f"[Contract] Migration: Ensured {table_name}.{column_name} exists")
                except Exception as e:
                    if "table" in str(e).lower() and "does not exist" in str(e).lower():
                        logger.debug(f"[Contract] Migration skipped ({table_name} table doesn't exist yet): {e}")
                    else:
                        logger.warning(f"[Contract] Migration warning for {table_name}.{column_name}: {e}")
                    db.rollback()

        # (org_level_access is set once by _initialize_role_authority.)

        # Migration 5b: linkedin_candidate_pipeline was first created with
        # uuid columns for user/candidate ids, but ids in this system are
        # strings ("admin@...", "USER-...", "CAN-..."), so every query by
        # user failed with InvalidTextRepresentation. Convert to text only
        # while still uuid (idempotent; uuid -> text never loses data).
        pipeline_columns = {
            "assigned_to_user_id": "VARCHAR(255)",
            "created_by_user_id": "VARCHAR(255)",
            "candidate_id": "VARCHAR(512)",
        }
        for column_name, column_type in pipeline_columns.items():
            try:
                current_type = db.execute(text("""
                    SELECT data_type FROM information_schema.columns
                    WHERE table_schema = 'app_schema'
                      AND table_name = 'linkedin_candidate_pipeline'
                      AND column_name = :col
                """), {"col": column_name}).scalar()
                if current_type == "uuid":
                    # ALTER TYPE takes an ACCESS EXCLUSIVE lock; never hang startup on it
                    db.execute(text("SET LOCAL lock_timeout = '5s'"))
                    db.execute(text(f"""
                        ALTER TABLE app_schema.linkedin_candidate_pipeline
                        ALTER COLUMN {column_name} TYPE {column_type} USING {column_name}::text;
                    """))
                    db.commit()
                    logger.info(f"[Contract] Migration: linkedin_candidate_pipeline.{column_name} uuid -> {column_type}")
            except Exception as e:
                logger.warning(f"[Contract] Migration warning for linkedin_candidate_pipeline.{column_name}: {e}")
                db.rollback()

        # Migration 5c: agent_configs.tenant_id was created as uuid but
        # tenants are integer ids -> every Agent Config query failed.
        try:
            current_type = db.execute(text("""
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = 'app_schema' AND table_name = 'agent_configs' AND column_name = 'tenant_id'
            """)).scalar()
            if current_type == "uuid":
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                db.execute(text("ALTER TABLE app_schema.agent_configs ALTER COLUMN tenant_id TYPE VARCHAR(512) USING tenant_id::text"))
                db.commit()
                logger.info("[Contract] Migration: agent_configs.tenant_id uuid -> VARCHAR(512)")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning for agent_configs.tenant_id: {e}")
            db.rollback()

        # Migration 5d: SLM learning-metrics tables were created with uuid
        # tenant/candidate/job ids, but tenants are integers and candidate
        # ids are "CAN-..." strings, so nothing could be stored or read.
        uuid_to_text = {
            "slm_metrics": ["tenant_id"],
            "thunder_learning_metrics": ["tenant_id", "candidate_id"],
            "flash_learning_metrics": ["tenant_id", "job_id"],
            "learning_weight_updates": ["tenant_id"],
            "learning_recommendations": ["tenant_id", "target_entity_id", "approved_by_user_id"],
        }
        for table_name, columns in uuid_to_text.items():
            for column_name in columns:
                try:
                    current_type = db.execute(text("""
                        SELECT data_type FROM information_schema.columns
                        WHERE table_schema = 'app_schema' AND table_name = :t AND column_name = :c
                    """), {"t": table_name, "c": column_name}).scalar()
                    if current_type == "uuid":
                        db.execute(text("SET LOCAL lock_timeout = '5s'"))
                        db.execute(text(
                            f"ALTER TABLE app_schema.{table_name} ALTER COLUMN {column_name} "
                            f"TYPE VARCHAR(512) USING {column_name}::text"
                        ))
                        db.commit()
                        logger.info(f"[Contract] Migration: {table_name}.{column_name} uuid -> VARCHAR(512)")
                except Exception as e:
                    logger.warning(f"[Contract] Migration warning for {table_name}.{column_name}: {e}")
                    db.rollback()

        # Migration 6: job_created_flash never set Jobs.tenant_id, so every
        # queue-created job was invisible to the tenant-scoped job list.
        # Single-tenant deployment: attribute orphaned jobs to tenant 1.
        try:
            result = db.execute(text("UPDATE app_schema.jobs SET tenant_id = 1 WHERE tenant_id IS NULL"))
            db.commit()
            if result.rowcount:
                logger.info(f"[Contract] Migration: attributed {result.rowcount} tenant-less jobs to tenant 1")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning for jobs.tenant_id backfill: {e}")
            db.rollback()

        # Migration 7: String columns were widened in the models (mostly to
        # VARCHAR(512)) but create_all() never alters existing tables, so
        # production kept the old lengths; e.g. tasks.candidate_id VARCHAR(36)
        # rejected 40-char "CAN-<uuid>" ids and every candidate creation failed.
        _widen_short_varchar_columns(db)

        # Migration 8: 33 tables were created with tenant_id as a foreign key
        # to users."UserID" (a tenant is not a user), so every write with a
        # real tenant value failed -- e.g. agent seeding/logging with
        # tenant_id="system" crashed the Agent State dashboard. Drop those
        # constraints (removes an invalid rule only; no data changes).
        _drop_tenant_id_user_foreign_keys(db)

        # Migration 9: Org -> Company -> Partner -> BU. Departments are
        # org-wide routing groups (BU optional); a BU operates in several
        # companies; its partner is a user. Carry over the old single
        # location and the org-chart partner (when that seat has a user).
        _migrate_company_partner_structure(db)

        # Migration 10: Demand merged into Jobs -- one requisition record.
        _merge_demands_into_jobs(db)

    except Exception as e:
        logger.warning(f"[Contract] Schema migrations failed: {e}")
        # Don't fail startup if migrations can't be run
    finally:
        db.close()


def _migrate_company_partner_structure(db: Session):
    """Idempotent; each step commits or rolls back on its own."""
    from sqlalchemy import text

    steps = [
        ("departments.business_unit_id nullable",
         "ALTER TABLE app_schema.departments ALTER COLUMN business_unit_id DROP NOT NULL"),
        ("business_unit_companies from business_units.location_id", """
            INSERT INTO app_schema.business_unit_companies (tenant_id, business_unit_id, company_id, created_at)
            SELECT bu.tenant_id, bu.id, bu.location_id, now()
            FROM app_schema.business_units bu
            WHERE bu.location_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM app_schema.business_unit_companies c
                              WHERE c.business_unit_id = bu.id AND c.company_id = bu.location_id)
        """),
        ("business_units.partner_user_id from partner_bu_assignments", """
            UPDATE app_schema.business_units bu SET partner_user_id = u."UserID"
            FROM app_schema.partner_bu_assignments a
            JOIN app_schema.users u ON u.org_node_id = a.partner_org_node_id
            WHERE a.business_unit_id = bu.id AND a.active AND bu.partner_user_id IS NULL
        """),
    ]
    for label, sql in steps:
        try:
            result = db.execute(text(sql))
            db.commit()
            if result.rowcount and result.rowcount > 0:
                logger.info(f"[Contract] Migration: {label} ({result.rowcount} rows)")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning for {label}: {e}")
            db.rollback()


def _merge_demands_into_jobs(db: Session):
    """Idempotent. Copies each demand into jobs under the same id, backfills
    the delivery fields of existing jobs, and repoints every foreign key that
    referenced demands(id) to jobs("jobID"). The demands table is left in
    place (no data dropped) but nothing references it afterwards."""
    from sqlalchemy import text

    demands_exist = db.execute(text("""
        SELECT 1 FROM information_schema.tables WHERE table_schema = 'app_schema' AND table_name = 'demands'
    """)).scalar() is not None
    steps = [
        ("revenue.opportunity_id optional",
         "ALTER TABLE app_schema.revenues ALTER COLUMN opportunity_id DROP NOT NULL"),
        ("candidates.total_experience_months from candidateExperience", """
            UPDATE app_schema.candidates
            SET total_experience_months = round(substring("candidateExperience" from '([0-9]+(?:[.][0-9]+)?)')::numeric * 12)
            WHERE total_experience_months IS NULL
              AND substring("candidateExperience" from '([0-9]+(?:[.][0-9]+)?)') IS NOT NULL
        """),
        ("jobs.min_experience_years numeric",
         "ALTER TABLE app_schema.jobs ALTER COLUMN min_experience_years TYPE NUMERIC(4,1)"),
    ]
    if demands_exist:
        steps.append(("copy demands into jobs", """
            INSERT INTO app_schema.jobs (
                "jobID", "jobTitle", "jobDescription", "jobSkills", "jobExperience", "jobLocation",
                "jobCreatedAt", "jobStatus", "noOfPositions", "startDate", "companyName",
                business_unit_id, tenant_id, client_id, project_id, opportunity_id,
                required_skills, nice_to_have_skills, min_experience_years, max_experience_years,
                work_location, employment_type, interview_type_required, positions_filled,
                billing_rate_usd_cents, budget_min_usd_cents, budget_max_usd_cents, demand_status,
                sourcing_enabled, bench_first_checked, assigned_recruiter_employee_id, delivery_engine,
                confirmation_status, sow_reference, sow_received_date, source_type, duration_hours,
                revenue_potential_usd_cents, created_by, updated_at, closed_at, domain, urgency,
                is_deleted, job_skills_boolean_mode)
            SELECT
                d.id, d.job_title, COALESCE(d.job_description, d.job_title),
                COALESCE((SELECT string_agg(v, ', ') FROM json_array_elements_text(
                    CASE WHEN ltrim(d.required_skills) LIKE '[%' THEN d.required_skills::json ELSE '[]'::json END) AS v), ''),
                CASE WHEN d.max_experience_years IS NOT NULL
                     THEN (d.min_experience_years::float)::text || '-' || (d.max_experience_years::float)::text || ' years'
                     ELSE (d.min_experience_years::float)::text || '+ years' END,
                COALESCE(d.job_location, initcap(d.work_location)),
                d.created_at,
                CASE d.status WHEN 'OPEN' THEN 'active' WHEN 'IN_PROGRESS' THEN 'active'
                              WHEN 'DRAFT' THEN 'draft' WHEN 'ON_HOLD' THEN 'active' ELSE 'closed' END,
                d.headcount, d.required_start_date, c.company_name,
                d.assigned_bu_id, d.tenant_id, d.client_id, d.project_id, d.opportunity_id,
                d.required_skills, d.nice_to_have_skills, d.min_experience_years, d.max_experience_years,
                d.work_location, d.employment_type, d.interview_type_required, d.positions_filled,
                d.billing_rate_usd_cents, d.budget_min_usd_cents, d.budget_max_usd_cents, d.status,
                d.sourcing_enabled, d.bench_first_checked, d.assigned_recruiter_employee_id, d.delivery_engine,
                d.confirmation_status, d.sow_reference, d.sow_received_date, d.source_type, d.duration_hours,
                d.revenue_potential_usd_cents, d.created_by, d.updated_at, d.closed_at, d.domain, d.urgency,
                false, 'AND'
            FROM app_schema.demands d
            LEFT JOIN app_schema.clients c ON c.id = d.client_id
            WHERE NOT EXISTS (SELECT 1 FROM app_schema.jobs j WHERE j."jobID" = d.id)
        """))
    steps += [
        ("jobs.client_id from company name", """
            UPDATE app_schema.jobs j SET client_id = c.id
            FROM app_schema.clients c
            WHERE j.client_id IS NULL AND j."companyName" IS NOT NULL
              AND lower(trim(c.company_name)) = lower(trim(j."companyName"))
              AND (c.tenant_id = j.tenant_id OR c.tenant_id IS NULL OR j.tenant_id IS NULL)
        """),
        ("jobs.demand_status from jobStatus", """
            UPDATE app_schema.jobs SET demand_status = CASE lower(coalesce("jobStatus", ''))
                WHEN 'active' THEN 'OPEN' WHEN 'closed' THEN 'CANCELLED' ELSE 'DRAFT' END
            WHERE required_skills IS NULL AND demand_status = 'DRAFT'
        """),
    ]
    for label, sql in steps:
        try:
            result = db.execute(text(sql))
            db.commit()
            if result.rowcount and result.rowcount > 0:
                logger.info(f"[Contract] Migration: {label} ({result.rowcount} rows)")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning for {label}: {e}")
            db.rollback()

    # Repoint foreign keys demands(id) -> jobs("jobID")
    try:
        fks = db.execute(text("""
            SELECT tc.table_name, tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'app_schema'
              AND ccu.table_name = 'demands'
        """)).fetchall()
    except Exception as e:
        logger.warning(f"[Contract] Migration warning listing demand foreign keys: {e}")
        db.rollback()
        fks = []
    for table, constraint, column in fks:
        try:
            db.execute(text(f'ALTER TABLE app_schema.{table} DROP CONSTRAINT "{constraint}"'))
            db.execute(text(f'ALTER TABLE app_schema.{table} ADD CONSTRAINT "fk_{table}_{column}_jobs" '
                            f'FOREIGN KEY ({column}) REFERENCES app_schema.jobs("jobID")'))
            db.commit()
            logger.info(f"[Contract] Migration: {table}.{column} now references jobs")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning repointing {table}.{column}: {e}")
            db.rollback()


def _drop_tenant_id_user_foreign_keys(db: Session):
    """Drop FK constraints from any tenant_id column to users (idempotent)."""
    from sqlalchemy import text

    rows = db.execute(text("""
        SELECT tc.table_schema, tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = 'tenant_id'
          AND ccu.table_name = 'users'
    """)).fetchall()
    for schema, table, constraint in rows:
        try:
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            db.execute(text(f'ALTER TABLE "{schema}"."{table}" DROP CONSTRAINT IF EXISTS "{constraint}"'))
            db.commit()
            logger.info(f"[Contract] Migration: dropped {table}.{constraint} (tenant_id -> users)")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning dropping {table}.{constraint}: {e}")
            db.rollback()


def _widen_short_varchar_columns(db: Session):
    """Widen live VARCHAR columns that are shorter than their model (idempotent).

    Widen-only: never shrinks a column or changes a type family. Increasing a
    varchar limit is a catalog-only change in PostgreSQL (no table rewrite).
    """
    from sqlalchemy import Enum, String, text

    live = {}
    rows = db.execute(text("""
        SELECT table_schema, table_name, column_name, character_maximum_length
        FROM information_schema.columns
        WHERE data_type = 'character varying' AND character_maximum_length IS NOT NULL
    """))
    for schema, table, column, length in rows:
        live[(schema, table, column)] = length

    for table in Base.metadata.tables.values():
        schema = table.schema or "app_schema"
        widen = []
        for col in table.columns:
            if not isinstance(col.type, String):
                continue
            # Only columns that are VARCHAR in the live DB (native enums are not)
            live_len = live.get((schema, table.name, col.name))
            if live_len is None:
                continue
            if isinstance(col.type, Enum):
                # Non-native enum: varchar sized to its longest value
                model_len = col.type.length or max((len(v) for v in col.type.enums), default=0)
            else:
                model_len = col.type.length
            if model_len is None:
                # Unbounded in the model (Text / String()): TEXT never truncates
                widen.append(f'ALTER COLUMN "{col.name}" TYPE TEXT')
            elif live_len < model_len:
                widen.append(f'ALTER COLUMN "{col.name}" TYPE VARCHAR({model_len})')
        if not widen:
            continue
        try:
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            db.execute(text(f'ALTER TABLE "{schema}"."{table.name}" ' + ", ".join(widen)))
            db.commit()
            logger.info(f"[Contract] Migration: widened {len(widen)} varchar column(s) on {table.name}")
        except Exception as e:
            logger.warning(f"[Contract] Migration warning widening {table.name}: {e}")
            db.rollback()


if __name__ == "__main__":
    # Can be run manually to verify/initialize database
    initialize_database()
    print("✅ Database contract initialized")
