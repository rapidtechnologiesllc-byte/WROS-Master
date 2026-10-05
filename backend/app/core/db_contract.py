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
                db.add(RoleTemplatePermission(
                    role_template_id=role_template.id,
                    resource_id=resource.id,
                    tenant_id=role_template.tenant_id,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True
                ))
                permissions_granted += 1

            db.commit()
            if permissions_granted:
                logger.info(f"[Contract] Role {role_template.name}: seeded {permissions_granted} missing permission rows")

    finally:
        db.close()

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
            "clients": [
                ("account_manager_user_id", 'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
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
            ],
            "candidate_conversations": [
                ("next_touch_scheduled_at", "TIMESTAMP NULL"),
            ],
            "candidate_documents": [
                ("document_name", "VARCHAR(512) NULL"),
                ("upload_sequence", "INTEGER NULL"),
            ],
        }
        super_flag_existed = db.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'app_schema' AND table_name = 'role_templates'
              AND column_name = 'is_super_user'
        """)).scalar() is not None
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

        # Flag the existing Super Admin template only when the column was
        # just created, so a later deliberate change is never overwritten.
        if not super_flag_existed:
            try:
                db.execute(text("""
                    UPDATE app_schema.role_templates SET is_super_user = true
                    WHERE name = 'Super Admin'
                """))
                db.commit()
                logger.info("[Contract] Migration: flagged existing Super Admin role template")
            except Exception as e:
                logger.warning(f"[Contract] Migration warning for role_templates.is_super_user backfill: {e}")
                db.rollback()

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

    except Exception as e:
        logger.warning(f"[Contract] Schema migrations failed: {e}")
        # Don't fail startup if migrations can't be run
    finally:
        db.close()


if __name__ == "__main__":
    # Can be run manually to verify/initialize database
    initialize_database()
    print("✅ Database contract initialized")
