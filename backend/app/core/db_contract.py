"""
Database Contract - Ensures database is properly initialized on startup.

This module guarantees:
1. All tables exist (schema creation)
2. A primary tenant (parent company) exists
3. RBAC modules and resources exist
4. Default admin role template exists
5. Admin user exists with proper permissions
6. No duplicate/orphaned data

Run on every backend startup to ensure data integrity.
"""

import secrets
import string
from typing import Optional

from sqlalchemy import text
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
        # Import models package - this triggers _auto_import_all_models(). Every table is declared
        # in app.models (tests/test_slm_job_metadata.py asserts no model lives elsewhere)
        import app.models
        Base.metadata.create_all(bind=engine)
        logger.info("[OK] Database tables created")

        # Step 1.5: Run schema migrations (alter existing columns, etc.)
        logger.info("[Contract] Step 1.5: Running schema migrations...")
        _run_schema_migrations()
        logger.info("[OK] Schema migrations completed")

        # Step 1.6: One-time data migrations (each runs once per database, marker-guarded)
        logger.info("[Contract] Step 1.6: Running one-time data migrations...")
        _run_data_migrations()
        logger.info("[OK] Data migrations completed")

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

        # Step 9: the bench pool matches the bench rule (billable, joined, no active allocation),
        # from each person's real first bench day; billing_classification derived (idempotent)
        logger.info("[Contract] Step 9: Reconciling the bench pool...")
        _initialize_bench_pool()

        logger.info("[OK] Database contract validated - all systems ready")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[FAILED] Database contract violation: {e}", exc_info=True)
        raise

def _interview_times_to_utc(db: Session) -> int:
    """Interview start/end were saved as India wall-clock time (every live scheduling screen sent
    local time without an offset; the old invite endpoint assumed Asia/Kolkata). Storage is naive
    UTC since 2026-10-15, so convert the rows saved before that. Interviews created by the new
    scheduling path (it queues `interview-scheduled:{id}`) were already stored as UTC and are left
    alone. Returns the number of interviews converted."""
    return db.execute(text(
        "UPDATE app_schema.interviews i SET "
        "start_time = (i.start_time AT TIME ZONE :zone) AT TIME ZONE 'UTC', "
        "end_time = (i.end_time AT TIME ZONE :zone) AT TIME ZONE 'UTC' "
        "WHERE (i.start_time IS NOT NULL OR i.end_time IS NOT NULL) AND NOT EXISTS ("
        "  SELECT 1 FROM app_schema.channel_queue_item q WHERE q.id = 'interview-scheduled:' || i.id)"),
        {"zone": settings.INTERVIEW_LEGACY_STORAGE_TIMEZONE}).rowcount


# name -> function(db) returning a row count. Append only; never rename or reorder.
def _employee_org_history_backfill(db: Session) -> int:
    """Cost object history (CEO 2026-10-22): every employee without history gets one row -- where
    they sit now, from their joining date -- so the first move after this keeps past months where
    they were. Idempotent by construction (only employees with no rows)."""
    from app.models.employee import Employee
    from app.models.employee_org_history import EmployeeOrgHistory, country_of_company

    have = {row[0] for row in db.query(EmployeeOrgHistory.employee_id).distinct()}
    added = 0
    for employee in db.query(Employee).all():
        if employee.id in have:
            continue
        db.add(EmployeeOrgHistory(tenant_id=employee.tenant_id, employee_id=employee.id, bu_id=employee.bu_id,
                                  company_id=employee.company_id,
                                  country=country_of_company(db, employee.company_id),
                                  effective_from=employee.joining_date))
        added += 1
    return added


def _invoice_numbers_backfill(db: Session) -> int:
    """Invoice compliance (CEO 2026-10-23): every invoice created before numbering existed gets its
    issuing company and the next number of that company's series, in creation order; invoices
    already sent get their due date (sent date + the client's payment terms)."""
    from app.services.invoice_numbering import backfill

    return backfill(db)


def _guidewire_current_level_to_certificates(db: Session) -> int:
    """One truth for certificates (CEO 2026-10-23): the Guidewire level typed into
    employees.guidewire_certification_current becomes a certificate record (EmployeeCertification)
    of a catalog certificate carrying that guidewire_level -- the tenant's own if it has one, else
    "Guidewire <level>" is added to its catalog. The earned date is unknown, so the date the level
    was last saved on the employee is used and the record says so. The typed column is then
    cleared: the current level is derived from certificates from now on. Returns records made."""
    from datetime import datetime

    from app.models.certification import GUIDEWIRE_CERT_LEVELS, Certification, EmployeeCertification
    from app.models.employee import Employee

    made = 0
    rows = db.query(Employee).filter(Employee.guidewire_certification_current.in_(GUIDEWIRE_CERT_LEVELS)).all()
    for employee in rows:
        level = employee.guidewire_certification_current
        cert = db.query(Certification).filter(
            Certification.guidewire_level == level,
            (Certification.tenant_id == employee.tenant_id) | Certification.tenant_id.is_(None),
        ).order_by(Certification.created_at).first()
        if cert is None:
            code = f"GW-{level.upper()}"
            if db.query(Certification.id).filter(Certification.cert_code == code).first() is not None:
                code = f"{code}-T{employee.tenant_id}"
            cert = Certification(tenant_id=employee.tenant_id, cert_name=f"Guidewire {level}", cert_code=code,
                                 level="Foundation", validity_months=None, guidewire_level=level,
                                 description="Created from levels typed on employee records before certificates were tracked")
            db.add(cert)
            db.flush()
        held = db.query(EmployeeCertification.id).filter(
            EmployeeCertification.employee_id == employee.id, EmployeeCertification.certification_id == cert.id,
        ).first()
        if held is None:
            db.add(EmployeeCertification(
                tenant_id=employee.tenant_id, employee_id=employee.id, certification_id=cert.id, status="Active",
                earned_date=employee.updated_at or datetime.utcnow(),
                issuer="Recorded before certificates were tracked (earned date unknown)",
            ))
            made += 1
        employee.guidewire_certification_current = None
    db.flush()
    return made


def _intercompany_company_links(db: Session) -> int:
    """Intercompany entries were free-text entity names matched to companies by name at read time,
    so a typo silently landed in "Group". Link each entry to its companies by EXACT name or company
    code (case and surrounding spaces ignored -- the rule the P&L applied until now, so no figure
    moves). Entries that match no company keep NULL and one Finance task lists them. Returns the
    number of entries linked on both sides."""
    from app.models.intercompany_ledger import IntercompanySettlement
    from app.models.location import Location

    companies: dict = {}
    for company in db.query(Location).all():
        names = companies.setdefault(company.tenant_id, {})
        names.setdefault(company.name.strip().lower(), company.id)
        if company.company_code:
            names.setdefault(company.company_code.lower(), company.id)
    linked, unmatched = 0, []
    for entry in db.query(IntercompanySettlement).all():
        names = companies.get(entry.tenant_id, {}) if entry.tenant_id is not None else \
            {k: v for per_tenant in companies.values() for k, v in per_tenant.items()}
        entry.from_company_id = entry.from_company_id or names.get((entry.from_entity or "").strip().lower())
        entry.to_company_id = entry.to_company_id or names.get((entry.to_entity or "").strip().lower())
        if entry.from_company_id and entry.to_company_id:
            linked += 1
        else:
            unmatched.append(entry)
    db.flush()
    if unmatched:
        from app.services.task_service import create_task

        listing = "; ".join(f"#{e.id} {e.settlement_date} {e.from_entity} -> {e.to_entity} "
                            f"{e.amount_usd_cents / 100:,.2f} USD" for e in unmatched)
        create_task(db, title=f"Link {len(unmatched)} intercompany entr{'y' if len(unmatched) == 1 else 'ies'} to companies",
                    priority="HIGH", category="FINANCE", tenant_id=unmatched[0].tenant_id or 1,
                    visibility_scope="ORG_WIDE", link="/pnl?view=operations",
                    description=("These intercompany settlements name a company that does not exist, so the "
                                 "company P&L counts them in Group: " + listing + ". Link each to its companies "
                                 "(Finance Operations > Intercompany Settlement > Link)."))
    return linked


def _activity_timeline_entity_types_lowercase(db: Session) -> int:
    """Timeline entries are read by lower-case entity type (the screens ask for "candidate"), but the
    candidate activity log wrote "Candidate", so its entries never showed on the candidate's Activity
    panel. write_timeline_entry now lower-cases on write; this brings the existing rows in line."""
    return db.execute(text(
        "UPDATE app_schema.activity_timeline SET entity_type = lower(entity_type) "
        "WHERE entity_type <> lower(entity_type)")).rowcount


def _pay_from_monthly_usd(db: Session) -> int:
    """Pay as agreed (CEO 2026-10-24): every employee with a salary and no pay on record gets their
    existing salary recorded as monthly USD pay, so no cost changes. Returns rows filled."""
    from app.models.employee import Employee

    rows = db.query(Employee).filter(Employee.base_salary_usd_cents.isnot(None),
                                     Employee.pay_amount_cents.is_(None)).all()
    for employee in rows:
        employee.pay_amount_cents = employee.base_salary_usd_cents
        employee.pay_currency, employee.pay_basis = "USD", "MONTHLY"
    db.flush()
    return len(rows)


def _candidate_timezones_from_location(db: Session) -> int:
    """Candidates kept the Asia/Kolkata backfill whatever their location (US candidates were
    emailed at night): every candidate whose location names a timezone gets it. Returns rows changed."""
    from app.models.candidate import Candidate
    from app.services.candidate_timezone import timezone_for_location

    changed = 0
    for candidate in db.query(Candidate).filter(Candidate.candidateCurrentLocation.isnot(None)).all():
        zone = timezone_for_location(candidate.candidateCurrentLocation)
        if zone and zone != candidate.timezone:
            candidate.timezone = zone
            changed += 1
    db.flush()
    return changed


def _expense_attribution_and_events(db: Session) -> int:
    """Who the spend is on + one event per conference (CEO 2026-10-31). Existing expenses keep
    what they already said: a client expense is on that client (one 100% share), everything
    else is internal. Free-text conference names become shared events -- "NAMIC 2026" and
    "Namic-2026" land on the same one (expense_event_service.event_key); the year is the one in
    the name, else the expense date's. Names that are only near each other stay separate events
    for Finance to merge (POST /expense-events/{id}/merge). Returns expenses changed."""
    from app.models.expense import FULL_SHARE_BPS, ExpenseClientShare, ExpenseRecord
    from app.services.expense_event_service import event_key, find_or_create_event

    changed = 0
    for expense in db.query(ExpenseRecord).filter(ExpenseRecord.spend_for.is_(None)).all():
        expense.spend_for = "CLIENT" if expense.client_id else "INTERNAL"
        if expense.client_id and not expense.client_shares:
            expense.client_shares = [ExpenseClientShare(client_id=expense.client_id, share_bps=FULL_SHARE_BPS,
                                                        amount_usd_cents=expense.amount_usd_cents)]
        changed += 1
    db.flush()
    conferences = db.query(ExpenseRecord).filter(ExpenseRecord.purpose == "CONFERENCE",
                                                 ExpenseRecord.event_id.is_(None),
                                                 ExpenseRecord.conference_name.isnot(None)).all()
    for expense in conferences:
        key, named_year = event_key(expense.conference_name)
        if not key:
            logger.warning(f"[Contract] expense {expense.id}: conference name {expense.conference_name!r} "
                           "names no event; its manager picks the conference before approving it")
            continue
        event, _ = find_or_create_event(db, tenant_id=expense.tenant_id or 1, name=expense.conference_name,
                                        year=named_year or expense.expense_date.year,
                                        created_by_user_id=expense.logged_by_user_id, confirm_new=True)
        expense.event_id, expense.conference_name = event.id, event.name
        changed += 1
    db.flush()
    return changed


DATA_MIGRATIONS = (
    ("interview_times_to_utc", _interview_times_to_utc),
    ("employee_org_history_backfill", _employee_org_history_backfill),
    ("invoice_numbers_backfill", _invoice_numbers_backfill),
    ("guidewire_current_level_to_certificates", _guidewire_current_level_to_certificates),
    ("intercompany_company_links", _intercompany_company_links),
    ("activity_timeline_entity_types_lowercase", _activity_timeline_entity_types_lowercase),
    ("pay_from_monthly_usd", _pay_from_monthly_usd),
    ("candidate_timezones_from_location", _candidate_timezones_from_location),
    ("expense_attribution_and_events", _expense_attribution_and_events),
)


def _run_data_migrations():
    db = SessionLocal()
    try:
        run_data_migrations(db)
    finally:
        db.close()


def run_data_migrations(db: Session, migrations=DATA_MIGRATIONS) -> list:
    """Run each one-time data migration exactly once per database; returns the names it ran.
    The marker row in data_migrations is inserted in the same transaction as the migration: a
    second run (or a second instance starting at the same moment, which waits on the primary key)
    finds the marker and skips. A failing migration rolls back with its marker and fails startup."""
    ran = []
    try:
        for name, migrate in migrations:
            claimed = db.execute(text(
                "INSERT INTO app_schema.data_migrations (name, applied_at) VALUES (:name, now()) "
                "ON CONFLICT (name) DO NOTHING RETURNING name"), {"name": name}).first()
            if claimed is None:
                db.rollback()
                continue
            count = migrate(db)
            db.commit()
            ran.append(name)
            logger.info(f"[Contract] Data migration {name}: {count} row(s)")
    except Exception:
        db.rollback()
        raise
    return ran


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

def _initialize_bench_pool():
    from app.services.bench_service import reconcile_bench_pool

    db = SessionLocal()
    try:
        reconcile_bench_pool(db)
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

def primary_tenant_id(db) -> int:
    """The first tenant (parent company) -- owner of the shared module/resource catalog and of
    the bootstrap admin accounts. Looked up, never assumed to be id 1."""
    tenant_id = db.query(Tenant.id).order_by(Tenant.id).limit(1).scalar()
    if tenant_id is None:
        raise RuntimeError("No tenant exists - _initialize_tenant must run first")
    return tenant_id


def _initialize_tenant():
    """Make sure a parent company (tenant) exists: on an empty database create one named
    PRIMARY_TENANT_NAME. Every tenant is a parent company; its sub-companies are Companies
    (locations) inside it and take its tenant id."""
    from sqlalchemy import text
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).order_by(Tenant.id).first()
        if not tenant:
            tenant = Tenant(name=settings.PRIMARY_TENANT_NAME)
            db.add(tenant)
            db.commit()
            logger.info(f"[Contract] Created primary tenant: {tenant.name} (id={tenant.id})")
        else:
            logger.info(f"[Contract] Primary tenant: {tenant.name} (id={tenant.id})")

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
# Resources granted from another permission of the same role template, never wholesale: a role may
# start Flash missions when it may create jobs (CEO 2026-10-15; data-driven, never by role name).
# resource -> (source resource, source action)
DERIVED_GRANTS = {"flash-missions": ("jobs", "create")}


def _initialize_rbac():
    """Ensure all modules, resources, and admin role exist.

    Uses MODULES_AND_RESOURCES from app.contracts as the source of truth.
    This ensures the database always matches the API contract.
    """
    db = SessionLocal()
    try:
        # Import the authoritative API contract
        from app.contracts.api_contract import MODULES_AND_RESOURCES

        catalog_tenant = primary_tenant_id(db)  # one shared module/resource catalog

        # Module display name = its contract name (renamed only through the contract)
        modules_data = {module_name: module_name for module_name in MODULES_AND_RESOURCES.keys()}

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
                    tenant_id=catalog_tenant
                )
                db.add(module)
                db.flush()
                logger.info(f"[Contract] Created module: {module_name}")
            modules[module_name] = module

        db.commit()

        # A resource the contract moved to another module keeps its row (and every grant on it)
        _place_contract_resources(db, modules)

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
                        tenant_id=catalog_tenant
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

        for (tenant_id,) in db.query(Tenant.id).all():  # every parent company gets the system roles
          for role_name, display_name, description in role_template_configs:
            role_template = db.query(RoleTemplate).filter(RoleTemplate.name == role_name,
                                                          RoleTemplate.tenant_id == tenant_id).first()
            if not role_template:
                role_template = RoleTemplate(
                    name=role_name,
                    display_name=display_name,
                    description=description,
                    is_system=True,
                    tenant_id=tenant_id
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
                if resource.id in existing_resource_ids or resource.name in DERIVED_GRANTS:
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

def _place_contract_resources(db, modules) -> int:
    """Regrouping the menu moves resources between modules in the contract. Grants and personal
    overrides live on the Resource row, so a contract resource that has no row in its contract
    module re-parents its existing canonical row (enabled first, then oldest) instead of getting a
    new, grant-less row -- nobody gains or loses a permission because a menu group was renamed.
    Modules no longer in the contract are then disabled (never deleted) by
    _initialize_contract_catalog_only. Idempotent: a placed resource is left alone."""
    from app.contracts.api_contract import MODULES_AND_RESOURCES

    moved = 0
    for module_name, resource_names in MODULES_AND_RESOURCES.items():
        module = modules[module_name]
        for resource_name in resource_names:
            if db.query(Resource.id).filter(Resource.module_id == module.id, Resource.name == resource_name).first():
                continue
            existing = db.query(Resource).filter(Resource.name == resource_name) \
                .order_by(Resource.enabled.desc(), Resource.id).first()
            if existing is None:
                continue  # brand-new resource: _initialize_rbac creates it
            logger.info(f"[Contract] Moved resource {resource_name} (id {existing.id}) to module {module_name}")
            existing.module_id = module.id
            existing.enabled = True
            moved += 1
    if moved:
        db.commit()
        from app.services.role_template_permission_service import invalidate_permissions
        invalidate_permissions()
    return moved


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
                    "opportunities", "pipeline-management", "demand-confirmation", "goals"],
            # LinkedIn Pipeline is a sub-page of the candidates resource (init_resources), not a resource
            "v": ["offer-letters", "employees", "allocations", "utilization-dashboard", "resource-forecast",
                  "workforce-overview", "projects", "resources", "invoices", "forecasts", "revenue",
                  "partner-dashboard",
                  "bu-head-dashboard", "business-units",
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
                    "allocations", "timesheets", "projects", "resources", "opportunities", "demand-confirmation",
                    "pipeline-management", "clients"],
            "v": ["offer-letters", "employees", "utilization-dashboard", "resource-forecast",
                  "workforce-overview", "invoices", "forecasts", "revenue", "goals",
                  "bu-head-dashboard", "business-units", "delivery-centers",
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
                    "activity-feed", "ask-flash", "invoices", "expenses", "revenue",
                    "finance-operations", "forecasts"],
            "v": ["clients", "projects", "allocations", "timesheets", "employees", "business-units",
                  "opportunities", "pipeline-management"],
        },
    },
    # Sells: finds opportunities, owns client relationships, raises role demands for won
    # work. Scoped to their business units; no P&L (revenue) access.
    "Sales": {
        "display_name": "Sales",
        "description": "Opens and works opportunities and client relationships for their business units",
        "hierarchy_level": 8,
        "specialization": "Sales",
        "org_level_access": False,
        "permissions": {
            "vce": ["dashboard", "my-tasks", "my-timesheet", "my-expenses", "my-referrals", "notifications",
                    "activity-feed", "ask-flash", "clients", "opportunities", "pipeline-management"],
            "v": ["demand-confirmation", "projects", "jobs", "business-units"],
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


def ensure_role(db, name: str, spec: dict, tenant_id: int) -> bool:
    """Create one LEADERSHIP_ROLES-style role template with its permissions in the tenant if
    missing. Existing roles are never touched (the Role Templates editor owns them)."""
    if db.query(RoleTemplate).filter(RoleTemplate.name == name, RoleTemplate.tenant_id == tenant_id).first():
        return False
    from app.services.role_template_permission_service import canonical_resource

    module_names = dict(db.query(Module.id, Module.name))
    by_name = {}
    for r in db.query(Resource).all():
        by_name.setdefault(r.name, []).append(r)
    resources = {name: canonical_resource(group, module_names) for name, group in by_name.items()}
    role = RoleTemplate(
        name=name, display_name=spec["display_name"], description=spec["description"],
        hierarchy_level=spec["hierarchy_level"], org_level_access=spec["org_level_access"],
        specialization=spec.get("specialization", "General"), is_system=False, tenant_id=tenant_id,
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
                role_template_id=role.id, resource_id=resource.id, tenant_id=tenant_id,
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
        for (tenant_id,) in db.query(Tenant.id).all():
            for name, spec in LEADERSHIP_ROLES.items():
                ensure_role(db, name, spec, tenant_id)
        _move_converted_employees_off_user_role(db)
        _initialize_role_authority(db)
        _initialize_bu_location_heads(db)
        _initialize_org_positions(db)
        _initialize_org_roles(db)
        _initialize_manage_role_permission_sets(db)
        _initialize_canonical_resources(db)
        _initialize_contract_catalog_only(db)
        _initialize_thunder_conversation_owner(db)
        _initialize_candidate_status_templates(db)
        _initialize_submission_violation_types(db)
        _initialize_client_change_types(db)
        _initialize_allocation_statuses(db)
        _initialize_employment_types(db)
        _initialize_permission_row_tenants(db)
        _initialize_functions(db)
        _initialize_company_codes(db)
        _initialize_partial_unique_indexes(db)
        _initialize_engagement_tenant_keys(db)
        _initialize_thunder_identity_config(db)
        _initialize_user_template_tenants(db)
        _initialize_pipeline_access(db)
        _initialize_derived_grants(db)
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


def _initialize_derived_grants(db):
    """Every role template (any tenant) without a permission row for a DERIVED_GRANTS resource gets
    one: view and create granted exactly when the template holds the source permission (e.g.
    flash-missions from jobs.create). Existing rows are never touched, so a revoke in the Role
    Templates editor sticks. Idempotent."""
    from app.services.role_template_permission_service import canonical_resource

    module_names = dict(db.query(Module.id, Module.name))
    by_name = {}
    for resource in db.query(Resource).all():
        by_name.setdefault(resource.name, []).append(resource)
    for name, (source_name, action) in DERIVED_GRANTS.items():
        if name not in by_name:
            continue
        target = canonical_resource(by_name[name], module_names)
        target_ids = [r.id for r in by_name[name]]
        source_ids = [r.id for r in by_name.get(source_name, [])]
        granted = 0
        for role in db.query(RoleTemplate).all():
            if db.query(RoleTemplatePermission.id).filter(RoleTemplatePermission.role_template_id == role.id,
                                                          RoleTemplatePermission.resource_id.in_(target_ids)).first():
                continue
            holds = bool(source_ids) and db.query(RoleTemplatePermission.id).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.resource_id.in_(source_ids),
                getattr(RoleTemplatePermission, f"can_{action}").is_(True)).first() is not None
            db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=target.id,
                                          tenant_id=role.tenant_id if role.tenant_id is not None else target.tenant_id,
                                          can_view=holds, can_create=holds, can_edit=False, can_delete=False))
            granted += holds
        db.commit()
        if granted:
            logger.info(f"[Contract] {name}: granted to {granted} role template(s) holding {source_name}.{action}")


PIPELINE_ACCESS_SEED_KEY = "pipeline_access_seeded"


def _initialize_pipeline_access(db):
    """Opportunities stopped requiring the P&L permission (revenue). So that nobody loses the
    pipeline and the Kanban opens for everyone who works opportunities, ONCE per tenant (a
    system_config marker; later Role Templates edits are never overwritten), by permission:
    a role that could see revenue may view opportunities, and a role that may view
    opportunities may view the pipeline board."""
    from app.models.system_config import SystemConfig

    resources = {r.name: r.id for r in db.query(Resource).filter(
        Resource.name.in_(("revenue", "opportunities", "pipeline-management")))}
    missing = {"revenue", "opportunities", "pipeline-management"} - set(resources)
    if missing:
        raise RuntimeError(f"Pipeline access seed: resources not seeded: {sorted(missing)}")

    def grant(role, resource_name):
        row = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role.id,
            RoleTemplatePermission.resource_id == resources[resource_name]).first()
        if row is None:
            db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resources[resource_name],
                                          tenant_id=role.tenant_id, can_view=True, can_create=False,
                                          can_edit=False, can_delete=False))
        elif not row.can_view:
            row.can_view = True
        else:
            return 0
        return 1

    def can_view(role, resource_name):
        return db.query(RoleTemplatePermission.id).filter(
            RoleTemplatePermission.role_template_id == role.id,
            RoleTemplatePermission.resource_id == resources[resource_name],
            RoleTemplatePermission.can_view.is_(True)).first() is not None

    tenant_ids = [t for (t,) in db.query(RoleTemplate.tenant_id).distinct().all() if t is not None]
    for tenant_id in tenant_ids:
        if db.query(SystemConfig.id).filter(SystemConfig.tenant_id == tenant_id,
                                            SystemConfig.business_unit_id.is_(None),
                                            SystemConfig.config_key == PIPELINE_ACCESS_SEED_KEY).first():
            continue
        granted = 0
        for role in db.query(RoleTemplate).filter(RoleTemplate.tenant_id == tenant_id).all():
            if can_view(role, "revenue"):
                granted += grant(role, "opportunities")
            db.flush()
            if can_view(role, "opportunities"):
                granted += grant(role, "pipeline-management")
        db.add(SystemConfig(tenant_id=tenant_id, business_unit_id=None, config_category="SYSTEM",
                            config_key=PIPELINE_ACCESS_SEED_KEY, config_value={"granted": granted}))
        db.commit()
        logger.info(f"[Contract] Pipeline access: {granted} permission(s) granted for tenant {tenant_id}")


def _initialize_org_positions(db):
    """The fixed position ladder every org seat points at (CEO, Partner, BU Head ...). Without
    it no seat can be created on a fresh database. Creates missing positions only, never
    rewrites existing ones."""
    from app.models.org_structure import OrgPosition
    from app.services.org_structure_service import DEFAULT_POSITIONS

    existing = {name for (name,) in db.query(OrgPosition.name)}
    missing = [OrgPosition(**spec) for spec in DEFAULT_POSITIONS if spec["name"] not in existing]
    if missing:
        db.add_all(missing)
        db.commit()
        logger.info(f"[Contract] Seeded {len(missing)} org positions")


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


def _initialize_manage_role_permission_sets(db):
    """Every Manage Role owns a permission set (org_roles.role_template_id), created empty
    (org_roles_service.ensure_permission_set) so nobody's access changes when it appears."""
    from app.models.org_structure import OrgRole
    from app.services.org_roles_service import ensure_permission_set

    created = 0
    for role in db.query(OrgRole).all():
        created += role.role_template_id is None
        ensure_permission_set(db, role)
    db.commit()
    if created:
        from app.services.role_template_permission_service import invalidate_permissions
        invalidate_permissions()
        logger.info(f"[Contract] Created {created} empty Manage Role permission set(s)")


def _initialize_canonical_resources(db):
    """One resource per name. Legacy seeds left duplicates (e.g. 'candidates' in module
    Recruitment and again in recruitment_management); checks resolve a name to the canonical
    row (role_template_permission_service.canonical_resource), so grants and personal
    overrides sitting on a duplicate were never honoured. Copy each onto the canonical row
    where that template / user has none there yet (an existing canonical row is what is
    enforced today and is kept), then disable the duplicate (reversible; nothing deleted).
    Idempotent."""
    from app.models.user import UserCustomPermission
    from app.services.role_template_permission_service import FLAGS, canonical_resource, invalidate_permissions

    module_names = dict(db.query(Module.id, Module.name))
    groups = {}
    for resource in db.query(Resource).order_by(Resource.id):
        groups.setdefault((resource.tenant_id, resource.name.lower()), []).append(resource)
    moved = disabled = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        canonical = canonical_resource(group, module_names)
        canonical.enabled = True
        for dup in group:
            if dup.id == canonical.id:
                continue
            for row in db.query(RoleTemplatePermission).filter(RoleTemplatePermission.resource_id == dup.id).all():
                exists = db.query(RoleTemplatePermission.id).filter(
                    RoleTemplatePermission.role_template_id == row.role_template_id,
                    RoleTemplatePermission.resource_id == canonical.id,
                    RoleTemplatePermission.tenant_id == row.tenant_id).first()
                if not exists:
                    db.add(RoleTemplatePermission(role_template_id=row.role_template_id, resource_id=canonical.id,
                                                  tenant_id=row.tenant_id, **{f: bool(getattr(row, f)) for f in FLAGS}))
                    db.flush()
                    moved += 1
            for row in db.query(UserCustomPermission).filter(UserCustomPermission.resource_id == dup.id).all():
                exists = db.query(UserCustomPermission.id).filter(
                    UserCustomPermission.user_id == row.user_id,
                    UserCustomPermission.resource_id == canonical.id).first()
                if not exists:
                    row.resource_id = canonical.id  # one override per user and resource: move it
                    db.flush()
                    moved += 1
            if dup.enabled:
                dup.enabled = False
                disabled += 1
    db.commit()
    if moved or disabled:
        invalidate_permissions()
        logger.info(f"[Contract] Canonical resources: moved {moved} grant(s)/override(s), disabled {disabled} duplicate(s)")


def _initialize_contract_catalog_only(db):
    """The role editor offers exactly the API contract's modules and resources. Anything else
    (legacy seeds, resources retired from the contract because no page or check used them) is
    disabled -- reversible, nothing deleted; re-enabled automatically if it returns to the
    contract. No permission check can rely on a disabled resource: tests/test_authority.py
    guards that every checked permission is in the contract."""
    from app.contracts.api_contract import MODULES_AND_RESOURCES

    changed = 0
    modules = {m.id: m for m in db.query(Module).all()}
    for module in modules.values():
        wanted = module.name in MODULES_AND_RESOURCES
        if bool(module.enabled) != wanted:
            module.enabled = wanted
            changed += 1
    for resource in db.query(Resource).all():
        module = modules.get(resource.module_id)
        wanted = bool(module) and resource.name in MODULES_AND_RESOURCES.get(module.name, ())
        if not wanted and resource.enabled:
            resource.enabled = False
            changed += 1
        elif wanted and not resource.enabled and _is_canonical(db, resource, modules):
            resource.enabled = True
            changed += 1
    db.commit()
    if changed:
        from app.services.role_template_permission_service import invalidate_permissions
        invalidate_permissions()
        logger.info(f"[Contract] Catalog: {changed} module/resource(s) enabled or disabled to match the contract")


def _is_canonical(db, resource, modules) -> bool:
    from app.services.role_template_permission_service import canonical_resource

    group = db.query(Resource).filter(Resource.name == resource.name, Resource.tenant_id == resource.tenant_id).all()
    return canonical_resource(group, {mid: m.name for mid, m in modules.items()}).id == resource.id


def _initialize_thunder_conversation_owner(db):
    """Engagement once created Thunder conversations as owner_type 'Thunder', which every
    Thunder send gate refuses (only 'ai_agent' may send), so those candidates could never be
    messaged. Hand them to the AI agent (idempotent; human-owned conversations untouched)."""
    from app.models.candidate_ai import CandidateConversation
    from app.services.ai_conversation_service import AI_AGENT_NAME

    fixed = db.query(CandidateConversation).filter(CandidateConversation.owner_type == "Thunder") \
        .update({CandidateConversation.owner_type: "ai_agent", CandidateConversation.owner_id: AI_AGENT_NAME},
                synchronize_session=False)
    db.commit()
    if fixed:
        logger.info(f"[Contract] Handed {fixed} Thunder-owned conversation(s) to the AI agent")


def _initialize_candidate_status_templates(db):
    """The template_key CHECK constraint is rebuilt from MessageTemplate's TEMPLATE_KEYS (it
    had fallen behind: EMPLOYEE_WELCOME_EMAIL could not be saved), then every tenant gets the
    candidate status emails seeded once (candidate_status_notifications.seed_templates)."""
    from app.models.message_template import TEMPLATE_KEYS
    from app.services.candidate_status_notifications import seed_templates

    allowed = ", ".join("'" + key + "'" for key in TEMPLATE_KEYS)
    db.execute(text("ALTER TABLE app_schema.message_templates DROP CONSTRAINT IF EXISTS message_template_key"))
    db.execute(text(f"ALTER TABLE app_schema.message_templates ADD CONSTRAINT message_template_key "
                    f"CHECK (template_key IN ({allowed}))"))
    db.commit()
    added = sum(seed_templates(db, tenant_id) for (tenant_id,) in db.query(Tenant.id).all())
    db.commit()
    if added:
        logger.info(f"[Contract] Seeded {added} candidate status email template(s)")


def _initialize_submission_violation_types(db):
    """The violation_type CHECK constraint is rebuilt from VIOLATION_TYPES (create_all never
    alters an existing table: the client-submission gates of 2026-10-14 added types). Idempotent."""
    from app.models.submission import VIOLATION_TYPES

    allowed = ", ".join("'" + kind + "'" for kind in VIOLATION_TYPES)
    db.execute(text("ALTER TABLE app_schema.submission_violations DROP CONSTRAINT IF EXISTS submission_violation_type"))
    db.execute(text(f"ALTER TABLE app_schema.submission_violations ADD CONSTRAINT submission_violation_type "
                    f"CHECK (violation_type IN ({allowed}))"))
    db.commit()


def _initialize_client_change_types(db):
    """The client_history change_type CHECK constraint is rebuilt from CLIENT_CHANGE_TYPES
    (create_all never alters an existing table: CLIENT_OWNER was added 2026-10-30). The Client
    Owner column gets its index. Idempotent."""
    from app.models.client import CLIENT_CHANGE_TYPES

    allowed = ", ".join("'" + kind + "'" for kind in CLIENT_CHANGE_TYPES)
    db.execute(text("ALTER TABLE app_schema.client_history DROP CONSTRAINT IF EXISTS client_change_type"))
    db.execute(text(f"ALTER TABLE app_schema.client_history ADD CONSTRAINT client_change_type "
                    f"CHECK (change_type IN ({allowed}))"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_app_schema_clients_client_owner_user_id "
                    "ON app_schema.clients (client_owner_user_id)"))
    db.commit()


def _initialize_allocation_statuses(db):
    """The status and renewal_status CHECK constraints of employee_allocations are rebuilt from
    ALLOCATION_STATUSES / RENEWAL_STATUSES (create_all never alters an existing table: the margin
    guard added PENDING_MARGIN_APPROVAL and MARGIN_REJECTED, the renewal pipeline its column).
    The renewal owner gets its index. Idempotent."""
    from app.models.employee_allocation import ALLOCATION_STATUSES, RENEWAL_STATUSES

    for constraint, column, values in (("employee_allocation_status", "status", ALLOCATION_STATUSES),
                                       ("employee_allocation_renewal_status", "renewal_status", RENEWAL_STATUSES)):
        allowed = ", ".join("'" + value + "'" for value in values)
        db.execute(text(f"ALTER TABLE app_schema.employee_allocations DROP CONSTRAINT IF EXISTS {constraint}"))
        db.execute(text(f"ALTER TABLE app_schema.employee_allocations ADD CONSTRAINT {constraint} "
                        f"CHECK ({column} IN ({allowed}))"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_app_schema_employee_allocations_renewal_owner_user_id "
                    "ON app_schema.employee_allocations (renewal_owner_user_id)"))
    db.commit()


# Values the previous release writes (gate criterion 24: schema compatible with the old code for
# two deploy cycles). Remove once two releases with the canonical set have shipped.
ROLLBACK_COMPAT_EMPLOYMENT_TYPES = ("W2_FULLTIME",)


def _initialize_employment_types(db):
    """One canonical employment-type set (CEO 2026-10-15): W2_FULLTIME becomes FULLTIME on
    candidates, sub-vendor submissions and jobs, and the CHECK constraints are rebuilt from
    CANDIDATE_EMPLOYMENT_TYPES. A candidate with no country gets the configured country its
    free-text location names ("Pune, Maharashtra, India" -> IN). The policy is loaded first, so
    a misconfigured EMPLOYMENT_TYPE_POLICY_JSON fails startup. Idempotent."""
    from app.models.candidate import CANDIDATE_EMPLOYMENT_TYPES
    from app.services.employment_type_policy import policy

    countries = policy()["countries"]
    # The constraint keeps the legacy W2_FULLTIME value for ROLLBACK_COMPAT_EMPLOYMENT_TYPES' life:
    # if a deploy is rolled back, the previous release still writes W2_FULLTIME and must not fail;
    # the next startup converts any such rows again (the UPDATE below is idempotent).
    allowed = ", ".join("'" + kind + "'" for kind in (*CANDIDATE_EMPLOYMENT_TYPES, *ROLLBACK_COMPAT_EMPLOYMENT_TYPES))
    for table, constraint in (("candidates", "candidate_employment_type"),
                              ("sub_vendor_submissions", "subvendor_submission_employment_type")):
        db.execute(text(f"ALTER TABLE app_schema.{table} DROP CONSTRAINT IF EXISTS {constraint}"))
        db.execute(text(f"UPDATE app_schema.{table} SET employment_type = 'FULLTIME' "
                        f"WHERE employment_type = 'W2_FULLTIME'"))
        db.execute(text(f"ALTER TABLE app_schema.{table} ADD CONSTRAINT {constraint} "
                        f"CHECK (employment_type IN ({allowed}))"))
    db.execute(text("UPDATE app_schema.jobs SET employment_type = 'FULLTIME' WHERE employment_type = 'W2_FULLTIME'"))
    db.execute(text("ALTER TABLE app_schema.jobs ALTER COLUMN employment_type SET DEFAULT 'FULLTIME'"))
    derived = 0
    for code, country in countries.items():
        names = sorted({n.lower() for n in country.get("names") or []} | {(country.get("name") or "").lower()} - {""})
        derived += db.execute(text(
            'UPDATE app_schema.candidates SET country = :code WHERE country IS NULL '
            'AND lower(trim(regexp_replace("candidateCurrentLocation", \'^.*,\', \'\'))) = ANY(:names)'),
            {"code": code, "names": names}).rowcount
    db.commit()
    if derived:
        logger.info(f"[Contract] Candidate country derived from location for {derived} candidate(s)")


def _initialize_permission_row_tenants(db):
    """Permission rows were written without a tenant (default 1) by older editor endpoints, so a
    non-tenant-1 template's rows sat under tenant 1 and were never read. Move each to its
    template's tenant unless that template already has a row for the resource there (that row
    is the one in force; the stray one stays ignored). Idempotent; nothing deleted."""
    moved = db.execute(text("""
        UPDATE app_schema.role_template_permissions p
        SET tenant_id = t.tenant_id
        FROM app_schema.role_templates t
        WHERE t.id = p.role_template_id AND p.tenant_id <> t.tenant_id
          AND NOT EXISTS (SELECT 1 FROM app_schema.role_template_permissions q
                          WHERE q.role_template_id = p.role_template_id AND q.resource_id = p.resource_id
                            AND q.tenant_id = t.tenant_id)
    """)).rowcount
    db.commit()
    if moved:
        from app.services.role_template_permission_service import invalidate_permissions
        invalidate_permissions()
        logger.info(f"[Contract] Filed {moved} permission row(s) under their template's tenant")


def _initialize_company_codes(db):
    """Every company gets its number inside its tenant (code "<tenant>-<n>"), in order of
    creation; numbers are never reused or renumbered. Idempotent."""
    from app.models.location import Location

    numbered = 0
    for (tenant_id,) in db.query(Tenant.id).all():
        companies = db.query(Location).filter(Location.tenant_id == tenant_id).order_by(Location.created_at, Location.id).all()
        top = max((c.company_seq or 0 for c in companies), default=0)
        for company in companies:
            if company.company_seq is None:
                top += 1
                company.company_seq = top
                numbered += 1
    db.commit()
    db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_tenant_company_seq "
                    "ON app_schema.locations (tenant_id, company_seq) WHERE company_seq IS NOT NULL"))
    db.commit()
    if numbered:
        logger.info(f"[Contract] Numbered {numbered} compan(y/ies) inside their tenant")


def _initialize_engagement_tenant_keys(db):
    """Candidate-engagement tables key their tenant as text. That key is the tenant id
    (app.core.tenant_context.conversation_tenant_key); writers had drifted to arbitrary user ids
    (the tenant's first user, the assigned recruiter, even the candidate's own id) while readers
    looked for the tenant, so dashboards saw nothing. Idempotent:
      - drop foreign keys from these tenant_id columns to users (the key is not a user);
      - conversation_events.tenant_id is text with no default (no hard-coded tenant);
      - every text tenant_id on a candidate-scoped table is set to the candidate's tenant,
        except the Test Thunder sandbox (keyed by the tester on purpose). Each table runs in a
        savepoint: a uniqueness clash is logged with the table name and that table is left as is.
    """
    from sqlalchemy import String

    from app.services.thunder_service import TEST_CANDIDATE_ID_PREFIX

    tables = [t for t in Base.metadata.tables.values()
              if "tenant_id" in t.c and isinstance(t.c.tenant_id.type, String)]
    for table in tables:
        for (name,) in db.execute(text(
            "SELECT con.conname FROM pg_constraint con "
            "JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey) "
            "WHERE con.contype = 'f' AND con.conrelid = to_regclass(:tbl) AND att.attname = 'tenant_id' "
            "AND con.confrelid = to_regclass('app_schema.users')"), {"tbl": f"app_schema.{table.name}"}).all():
            db.execute(text(f'ALTER TABLE app_schema."{table.name}" DROP CONSTRAINT "{name}"'))
            logger.info(f"[Contract] Dropped {table.name}.{name}: tenant_id is a tenant key, not a user")
    events_type = db.execute(text(
        "SELECT data_type FROM information_schema.columns WHERE table_schema = 'app_schema' "
        "AND table_name = 'conversation_events' AND column_name = 'tenant_id'")).scalar()
    if events_type and events_type != "character varying":
        db.execute(text("ALTER TABLE app_schema.conversation_events ALTER COLUMN tenant_id TYPE VARCHAR(50) "
                        "USING tenant_id::text"))
    if events_type:
        db.execute(text("ALTER TABLE app_schema.conversation_events ALTER COLUMN tenant_id DROP DEFAULT"))
    db.commit()

    rekeyed = {}
    for table in tables:
        if "candidate_id" not in table.c:
            continue
        savepoint = db.begin_nested()
        try:
            count = db.execute(text(
                f'UPDATE app_schema."{table.name}" AS t SET tenant_id = c.tenant_id::text '
                f'FROM app_schema.candidates AS c WHERE c."candidateID" = t.candidate_id '
                f"AND c.tenant_id IS NOT NULL AND t.tenant_id IS DISTINCT FROM c.tenant_id::text "
                f"AND t.candidate_id NOT LIKE :sandbox"), {"sandbox": f"{TEST_CANDIDATE_ID_PREFIX}%"}).rowcount
            savepoint.commit()
            if count:
                rekeyed[table.name] = count
        except Exception as exc:
            savepoint.rollback()
            logger.error(f"[Contract] Could not re-key {table.name} to the candidate's tenant "
                         f"(left unchanged): {exc}")
    events = db.execute(text(
        "UPDATE app_schema.conversation_events AS e SET tenant_id = c.tenant_id "
        "FROM app_schema.candidate_conversations AS c WHERE c.id = e.conversation_id "
        "AND e.tenant_id IS DISTINCT FROM c.tenant_id")).rowcount
    if events:
        rekeyed["conversation_events"] = events
    db.commit()
    if rekeyed:
        logger.info(f"[Contract] Engagement records keyed by their candidate's tenant: {rekeyed}")


def _initialize_thunder_identity_config(db):
    """Thunder's name and persona are tenant settings (tenant_ai_config_service). A value an
    admin saved before lived on a user row: carry it into the tenant's configuration once, so
    nothing configured is lost. The kill switch is not carried over (it never worked from a user
    row, and Thunder is live). Idempotent: a tenant that already has the setting keeps it."""
    from app.models.system_config import SystemConfig
    from app.services.tenant_ai_config_service import CONFIG_KEY, update_tenant_ai_config

    for (tenant_id,) in db.query(Tenant.id).all():
        row = db.query(SystemConfig).filter(SystemConfig.tenant_id == tenant_id, SystemConfig.config_key == CONFIG_KEY,
                                            SystemConfig.business_unit_id.is_(None)).first()
        saved = (row.config_value or {}) if row else {}
        carry = {}
        for field in ("ai_agent_name", "ai_agent_persona"):
            if saved.get(field):
                continue
            value = db.query(getattr(Users, field)).filter(Users.tenant_id == tenant_id, getattr(Users, field).isnot(None),
                                                           getattr(Users, field) != "").order_by(Users.UserID).limit(1).scalar()
            if value:
                carry[field] = value
        if carry:
            update_tenant_ai_config(db, carry, changed_by=None, tenant_id=tenant_id)
            logger.info(f"[Contract] Tenant {tenant_id}: Thunder {sorted(carry)} carried into the tenant AI configuration")


def _initialize_partial_unique_indexes(db):
    """A partial unique index declared on a model (postgresql_where) must be partial in the
    database too. create_all never alters an existing index, so one created before its WHERE was
    declared stays a full unique index and blocks legitimate rows (a second interview at a level
    after the first was superseded; re-opening a resolved intervention). Rebuild any such index
    from the model. Relaxing a constraint cannot conflict with existing rows. Idempotent."""

    rebuilt = []
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            if index.dialect_options["postgresql"].get("where") is None:
                continue
            row = db.execute(text("SELECT indexdef FROM pg_indexes WHERE schemaname = :s AND indexname = :n"),
                             {"s": table.schema or "app_schema", "n": index.name}).first()
            if row is None or " WHERE " in row[0]:
                continue
            db.execute(text(f'DROP INDEX IF EXISTS "{table.schema or "app_schema"}"."{index.name}"'))
            db.commit()
            index.create(bind=engine)
            rebuilt.append(index.name)
    if rebuilt:
        logger.info(f"[Contract] Rebuilt as partial unique indexes: {', '.join(rebuilt)}")


def _initialize_functions(db):
    """A tenant with no functions yet gets the standard list once (Manage Functions owns it
    afterwards: renames and retirements are never undone)."""
    import uuid as _uuid

    from app.models.org_structure import Department
    from app.services.org_hierarchy_validator import FUNCTION_WORDS

    added = 0
    for (tenant_id,) in db.query(Tenant.id).all():
        if db.query(Department.id).filter(Department.tenant_id == tenant_id).first():
            continue
        for name in FUNCTION_WORDS:
            db.add(Department(id=str(_uuid.uuid4()), tenant_id=tenant_id, name=name, active=True))
            added += 1
    db.commit()
    if added:
        logger.info(f"[Contract] Seeded {added} standard function(s)")


def _initialize_user_template_tenants(db):
    """A user holding another tenant's template (possible before add-ons were validated) has
    no add-on their tenant can show or edit. Move them to the same-named template of their own
    tenant when one exists (same access by construction); otherwise leave and log."""
    moved = 0
    for user in db.query(Users).join(RoleTemplate, RoleTemplate.id == Users.role_template_id) \
            .filter(RoleTemplate.tenant_id != Users.tenant_id).all():
        current = db.get(RoleTemplate, user.role_template_id)
        own = db.query(RoleTemplate).filter(RoleTemplate.tenant_id == user.tenant_id,
                                            RoleTemplate.name == current.name).first()
        if own is None:
            logger.warning(f"[Contract] {user.UserID} holds template {current.id} of tenant {current.tenant_id}; "
                           f"no {current.name!r} template in tenant {user.tenant_id} - fix on the Users screen")
            continue
        user.role_template_id = own.id
        moved += 1
    db.commit()
    if moved:
        from app.services.role_template_permission_service import invalidate_permissions
        invalidate_permissions()
        logger.info(f"[Contract] Moved {moved} user(s) to their own tenant's template")


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
                tenant_id=primary_tenant_id(db),
                timezone="Asia/Kolkata",
                password_reset_required=True
            )
            db.add(admin_user)
            db.commit()
            logger.info("[Contract] Created admin user: admin@blitzenx.com (password reset required on first login)")
        else:
            updated = False

            if not admin_user.tenant_id:
                admin_user.tenant_id = primary_tenant_id(db)
                updated = True
                logger.info("[Contract] Updated admin user with the primary tenant")

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
                    tenant_id=primary_tenant_id(db)
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
                tenant_id=primary_tenant_id(db),
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
                superuser.tenant_id = primary_tenant_id(db)
                updated = True
                logger.info("[Contract] Updated superuser with the primary tenant")

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
        db.rollback()
        logger.error(f"[Contract] Could not initialize channel templates: {e}", exc_info=True)
        raise
    finally:
        db.close()


def _create_performance_indexes():
    """Indexes for the high-volume audit tables (CandidateHistory, ActivityTimeline). Idempotent;
    a failure stops startup (SchemaMigrationError) rather than leaving the audit queries slow."""
    db = SessionLocal()
    try:
        for name, definition in (
            ("idx_candidate_history_event_at", 'app_schema.candidate_history(event_at DESC, "candidateID")'),
            ("idx_candidate_history_candidate_type", 'app_schema.candidate_history("candidateID", event_type)'),
            ("idx_activity_timeline_created_at", "app_schema.activity_timeline(created_at DESC, entity_id)"),
            ("idx_activity_timeline_entity", "app_schema.activity_timeline(entity_type, entity_id)"),
        ):
            _migration_step(db, f"index {name}", f"CREATE INDEX IF NOT EXISTS {name} ON {definition}")
    finally:
        db.close()


class SchemaMigrationError(RuntimeError):
    """A startup schema migration failed. Startup stops: running on a half-migrated schema hides
    the failure until a query hits the missing column (CLAUDE.md: fail fast)."""


def _migration_step(db: Session, label: str, sql: str, params: Optional[dict] = None, *,
                    lock_timeout: bool = False) -> int:
    """Run one idempotent statement and commit it; a failure is logged, rolled back and raised.
    Every statement is written to be a no-op once applied (IF [NOT] EXISTS, catalog checks), so
    a restart on an up-to-date schema runs cleanly and only a real problem stops startup."""
    from sqlalchemy import text

    try:
        if lock_timeout:  # ALTER TYPE takes an ACCESS EXCLUSIVE lock; never hang startup on it
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
        result = db.execute(text(sql), params or {})
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[Contract] Migration failed: {label}: {exc}", exc_info=True)
        raise SchemaMigrationError(f"Schema migration '{label}' failed: {exc}") from exc
    count = result.rowcount if result.rowcount and result.rowcount > 0 else 0
    if count:
        logger.info(f"[Contract] Migration: {label} ({count} rows)")
    return count


def _column_type(db: Session, table: str, column: str) -> Optional[str]:
    """The live data_type of app_schema.<table>.<column>, None when the column (or table) is absent."""
    from sqlalchemy import text

    return db.execute(text("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'app_schema' AND table_name = :t AND column_name = :c
    """), {"t": table, "c": column}).scalar()


def _run_schema_migrations():
    """Bring existing tables up to the models (create_all() never alters an existing table).

    Every statement is idempotent -- IF [NOT] EXISTS, or a catalog check before the change -- so
    it runs on every startup. A statement that still fails is a real problem: it is logged and
    raised (SchemaMigrationError), and startup stops instead of running on a half-migrated schema.
    """
    db = SessionLocal()
    try:
        _apply_schema_migrations(db)
    finally:
        db.close()


def _apply_schema_migrations(db: Session):
    # Migration 1: api_keys_config.created_by/updated_by hold user ids (strings), not integers
    for column in ("created_by", "updated_by"):
        current = _column_type(db, "api_keys_config", column)
        if current is not None and current != "character varying":
            _migration_step(db, f"api_keys_config.{column} -> VARCHAR(512)",
                            f"ALTER TABLE app_schema.api_keys_config ALTER COLUMN {column} TYPE VARCHAR(512)",
                            lock_timeout=True)

    # Employee import + billable (CEO 2026-10-22): every existing employee stays billable until set
    _migration_step(db, "employees.is_billable",
                    "ALTER TABLE IF EXISTS app_schema.employees "
                    "ADD COLUMN IF NOT EXISTS is_billable BOOLEAN NOT NULL DEFAULT TRUE")
    # cost object = BU x location: existing configs stay BU-level defaults (country NULL)
    _migration_step(db, "cost_rate_configs.country",
                    "ALTER TABLE IF EXISTS app_schema.cost_rate_configs ADD COLUMN IF NOT EXISTS country VARCHAR(2) NULL")
    # existing projects and allocations are client work: billable
    _migration_step(db, "projects.is_billable",
                    "ALTER TABLE IF EXISTS app_schema.projects "
                    "ADD COLUMN IF NOT EXISTS is_billable BOOLEAN NOT NULL DEFAULT TRUE")
    _migration_step(db, "employee_allocations.billable",
                    "ALTER TABLE IF EXISTS app_schema.employee_allocations "
                    "ADD COLUMN IF NOT EXISTS billable BOOLEAN NOT NULL DEFAULT TRUE")

    # Migration 2: candidate_status.thunder_assigned_at (when Thunder was assigned)
    _migration_step(db, "candidate_status.thunder_assigned_at",
                    "ALTER TABLE IF EXISTS app_schema.candidate_status "
                    "ADD COLUMN IF NOT EXISTS thunder_assigned_at TIMESTAMP WITH TIME ZONE NULL")

    # Migration 3: candidate columns present on the Candidate model but missing from the live
    # table (schema drift from create_all() never altering existing tables).
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
        ("country", "VARCHAR(2) NULL"),
    ]
    for column_name, column_def in candidate_columns:
        _migration_step(db, f"candidates.{column_name}",
                        f"ALTER TABLE IF EXISTS app_schema.candidates ADD COLUMN IF NOT EXISTS {column_name} {column_def}")

    # Migration 4: candidates.referral_id -> employee_referrals.referral_id, unless a foreign key
    # on that column already exists (create_all names its own), plus lookup indexes.
    referral_fk = db.execute(text("""
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'app_schema'
          AND tc.table_name = 'candidates' AND kcu.column_name = 'referral_id'
    """)).first()
    if referral_fk is None:
        _migration_step(db, "fk_candidate_referral", """
            ALTER TABLE app_schema.candidates ADD CONSTRAINT fk_candidate_referral
            FOREIGN KEY (referral_id) REFERENCES app_schema.employee_referrals(referral_id) ON DELETE SET NULL
        """)
    for index_name, column_name in (("ix_candidate_referral_id", "referral_id"),
                                    ("ix_candidate_created_by_user_id", "created_by_user_id"),
                                    ("ix_candidate_recruitment_source", "recruitment_source")):
        _migration_step(db, f"index {index_name}",
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON app_schema.candidates({column_name})")

    # Migration 5: Schema drift on other tables where the model has columns
    # the live table lacks (same create_all()-never-alters-existing-tables
    # gap as Migration 3). Discovered via a full model-vs-DB column scan.
    drifted_tables = {
        # Renewal pipeline + margin guard (CEO 2026-10-23): existing allocations start NOT_STARTED
        # with no margin check recorded (they were placed before the guard and are never blocked)
        "employee_allocations": [
            ("renewal_status", "VARCHAR(20) NOT NULL DEFAULT 'NOT_STARTED'"),
            ("renewal_owner_user_id",
             'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
            ("renewal_note", "TEXT NULL"),
            ("renewal_updated_at", "TIMESTAMP NULL"),
            ("renewal_updated_by",
             'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
            ("margin_pct", "NUMERIC(7, 2) NULL"),
            ("margin_check", "VARCHAR(40) NULL"),
            # Placement -> client PO / work order (its PO goes on the invoice)
            ("work_order_id", "VARCHAR(512) NULL REFERENCES app_schema.work_orders(id) ON DELETE SET NULL"),
        ],
        # Task deep link: the in-app path My Tasks opens (task_service.create_task)
        "tasks": [
            ("link", "VARCHAR(512) NULL"),
            # Repeating tasks (task_service.complete_task opens the next one)
            ("recurrence", "VARCHAR(20) NULL"),
        ],
        # Expense receipts: attached file + automatic check (expense_receipt_service)
        "expense_records": [
            ("receipt_file_path", "VARCHAR(1024) NULL"),
            ("receipt_content_type", "VARCHAR(100) NULL"),
            ("receipt_check_status", "VARCHAR(20) NOT NULL DEFAULT 'NOT_ATTACHED'"),
            ("receipt_check_detail", "TEXT NULL"),
            # Who the spend is on + the shared conference (CEO 2026-10-31; expense_event_service)
            ("spend_for", "VARCHAR(20) NULL"),
            ("event_id", "VARCHAR(512) NULL REFERENCES app_schema.expense_events(id) ON DELETE SET NULL"),
        ],
        # A Manage Role's permission set (CEO 2026-10-13)
        "org_roles": [
            ("role_template_id", "INTEGER NULL REFERENCES app_schema.role_templates(id)"),
        ],
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
            ("employment_type", "VARCHAR(50) NOT NULL DEFAULT 'FULLTIME'"),
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
            # Client Owner (2026-10-30): who owns the relationship, separate from the account manager
            ("client_owner_user_id", 'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
            # Contracting company (BX-US / BX-IN): revenue splits by company
            ("contracting_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE SET NULL"),
            # Client timesheet approval (CEO 2026-10-23): off for every existing client
            ("requires_client_timesheet_approval", "BOOLEAN NOT NULL DEFAULT false"),
        ],
        "timesheets": [
            ("client_approval_status", "VARCHAR(20) NULL"),
            ("client_approved_at", "TIMESTAMP NULL"),
        ],
        "timesheet_reviews": [
            ("client_decision_email", "VARCHAR(300) NULL"),
        ],
        # Invoice compliance (CEO 2026-10-23): issuer, gapless number per issuer, PO, due date
        "invoices": [
            ("issuing_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE SET NULL"),
            ("invoice_seq", "INTEGER NULL"),
            ("invoice_number", "VARCHAR(64) NULL"),
            ("po_numbers", "VARCHAR(512) NULL"),
            ("due_date", "DATE NULL"),
        ],
        "invoice_line_items": [
            ("po_number", "VARCHAR(512) NULL"),
        ],
        "locations": [
            ("state", "VARCHAR(512) NULL"),
            ("parent_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE RESTRICT"),
            # Company code "<tenant>-<n>" (Location.company_seq)
            ("company_seq", "INTEGER NULL"),
        ],
        "intercompany_settlements": [
            ("business_unit_id", "INTEGER NULL REFERENCES app_schema.business_units(id) ON DELETE SET NULL"),
            # the companies by id, not free-text name (data migration intercompany_company_links)
            ("from_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE RESTRICT"),
            ("to_company_id", "VARCHAR(512) NULL REFERENCES app_schema.locations(id) ON DELETE RESTRICT"),
        ],
        # The Guidewire level a catalog certificate gives (employee_certification_service)
        "certifications": [
            ("guidewire_level", "VARCHAR(20) NULL"),
        ],
        # The project manager who owns delivery (PATCH /projects/{id})
        "projects": [
            ("manager_user_id", 'VARCHAR(512) NULL REFERENCES app_schema.users("UserID") ON DELETE SET NULL'),
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
            # Profile and cover photo (CEO 2026-10-24): stored files under UPLOAD_DIR/employee-photos
            ("photo_path", "TEXT NULL"),
            ("cover_path", "TEXT NULL"),
            # Hire-Train-Deploy end (completed / exited / taken off): the P&L's HTD training cost window
            ("htd_end_date", "DATE NULL"),
            # Pay as agreed (CEO 2026-10-24): amount, currency, basis; base_salary_usd_cents derives from it
            ("pay_amount_cents", "BIGINT NULL"),
            ("pay_currency", "VARCHAR(3) NULL"),
            ("pay_basis", "VARCHAR(10) NULL"),
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
    # No tenant default anywhere: every row names its tenant (it once silently became 1)
    for table_name in ("business_units", "business_unit_companies", "business_unit_location_heads",
                       "candidates", "candidate_rejections", "candidate_rejection_reasons", "locations",
                       "role_templates", "system_modules", "system_module_permissions",
                       "thunder_monthly_highlights"):
        if _column_type(db, table_name, "tenant_id") is not None:
            _migration_step(db, f"{table_name}.tenant_id has no default",
                            f"ALTER TABLE app_schema.{table_name} ALTER COLUMN tenant_id DROP DEFAULT")
    for table_name, columns in drifted_tables.items():
        for column_name, column_def in columns:
            _migration_step(db, f"{table_name}.{column_name}",
                            f"ALTER TABLE IF EXISTS app_schema.{table_name} "
                            f"ADD COLUMN IF NOT EXISTS {column_name} {column_def}")
    # Indexes on the foreign keys added above (create_all makes them on a fresh database)
    for index_name, table_column in (
        ("ix_projects_manager_user_id", "projects(manager_user_id)"),
        ("ix_intercompany_settlements_from_company_id", "intercompany_settlements(from_company_id)"),
        ("ix_intercompany_settlements_to_company_id", "intercompany_settlements(to_company_id)"),
        ("ix_expense_records_event_id", "expense_records(event_id)"),
    ):
        _migration_step(db, f"index {index_name}",
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON app_schema.{table_column}")
    # lookups by these new columns (AR by due date, client approvals pending, allocations by PO)
    for index_name, table_name, column_name in (
            ("ix_invoices_due_date", "invoices", "due_date"),
            ("ix_invoices_issuing_company_id", "invoices", "issuing_company_id"),
            ("ix_timesheets_client_approval_status", "timesheets", "client_approval_status"),
            ("ix_employee_allocations_work_order_id", "employee_allocations", "work_order_id")):
        _migration_step(db, f"index {index_name}",
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON app_schema.{table_name}({column_name})")
    # one invoice number per tenant (NULLs allowed until the backfill numbers older invoices)
    _migration_step(db, "index uq_invoice_number_per_tenant",
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_number_per_tenant "
                    "ON app_schema.invoices(tenant_id, invoice_number)")

    # (org_level_access is set once by _initialize_role_authority.)

    # Migration 5b-5d: columns first created as uuid hold string / integer ids
    # (linkedin_candidate_pipeline user/candidate ids, agent_configs and SLM learning-metrics
    # tenant ids), so every query by them failed. Convert while still uuid (uuid -> text never
    # loses data).
    uuid_to_text = {
        "linkedin_candidate_pipeline": [("assigned_to_user_id", "VARCHAR(255)"), ("created_by_user_id", "VARCHAR(255)"),
                                        ("candidate_id", "VARCHAR(512)")],
        "agent_configs": [("tenant_id", "VARCHAR(512)")],
        "slm_metrics": [("tenant_id", "VARCHAR(512)")],
        "thunder_learning_metrics": [("tenant_id", "VARCHAR(512)"), ("candidate_id", "VARCHAR(512)")],
        "flash_learning_metrics": [("tenant_id", "VARCHAR(512)"), ("job_id", "VARCHAR(512)")],
        "learning_weight_updates": [("tenant_id", "VARCHAR(512)")],
        "learning_recommendations": [("tenant_id", "VARCHAR(512)"), ("target_entity_id", "VARCHAR(512)"),
                                     ("approved_by_user_id", "VARCHAR(512)")],
    }
    for table_name, columns in uuid_to_text.items():
        for column_name, column_type in columns:
            if _column_type(db, table_name, column_name) == "uuid":
                _migration_step(db, f"{table_name}.{column_name} uuid -> {column_type}",
                                f"ALTER TABLE app_schema.{table_name} ALTER COLUMN {column_name} "
                                f"TYPE {column_type} USING {column_name}::text", lock_timeout=True)

    # Migration 6: job_created_flash never set Jobs.tenant_id, so every queue-created job was
    # invisible to the tenant-scoped job list. Single-tenant deployment: attribute orphaned jobs
    # to tenant 1.
    _migration_step(db, "tenant-less jobs attributed to tenant 1",
                    "UPDATE app_schema.jobs SET tenant_id = 1 WHERE tenant_id IS NULL")

    # Migration 7: String columns were widened in the models (mostly to VARCHAR(512)) but
    # create_all() never alters existing tables, so production kept the old lengths; e.g.
    # tasks.candidate_id VARCHAR(36) rejected 40-char "CAN-<uuid>" ids and every candidate
    # creation failed.
    _widen_short_varchar_columns(db)

    # Migration 8: 33 tables were created with tenant_id as a foreign key to users."UserID" (a
    # tenant is not a user), so every write with a real tenant value failed. Drop those
    # constraints (removes an invalid rule only; no data changes).
    _drop_tenant_id_user_foreign_keys(db)

    # Migration 9: Org -> Company -> Partner -> BU. Departments are org-wide routing groups (BU
    # optional); a BU operates in several companies; its partner is a user. Carry over the old
    # single location and the org-chart partner (when that seat has a user).
    _migrate_company_partner_structure(db)

    # Migration 10: Demand merged into Jobs -- one requisition record.
    _merge_demands_into_jobs(db)


def _migrate_company_partner_structure(db: Session):
    """Idempotent; each step commits or rolls back on its own."""
    from sqlalchemy import text

    steps = [
        ("departments.business_unit_id nullable",
         "ALTER TABLE app_schema.departments ALTER COLUMN business_unit_id DROP NOT NULL"),
        # A referral recorded on Add Candidate need not name a job
        ("employee_referrals.job_id nullable",
         "ALTER TABLE app_schema.employee_referrals ALTER COLUMN job_id DROP NOT NULL"),
        # Project work is allocated to the project, not a client job (CEO 2026-10-24): job or project
        ("employee_allocations.demand_id nullable",
         "ALTER TABLE app_schema.employee_allocations ALTER COLUMN demand_id DROP NOT NULL"),
        ("employee_allocations job or project", """
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_allocation_job_or_project') THEN
                ALTER TABLE app_schema.employee_allocations ADD CONSTRAINT ck_allocation_job_or_project
                  CHECK (demand_id IS NOT NULL OR project_id IS NOT NULL);
              END IF;
            END $$"""),
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
        _migration_step(db, label, sql)


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
        _migration_step(db, label, sql)

    # Repoint foreign keys demands(id) -> jobs("jobID")
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
    for table, constraint, column in fks:  # once repointed, a constraint no longer shows up here
        _migration_step(db, f"{table}.{column} references jobs",
                        f'ALTER TABLE app_schema.{table} DROP CONSTRAINT "{constraint}", '
                        f'ADD CONSTRAINT "fk_{table}_{column}_jobs" FOREIGN KEY ({column}) '
                        f'REFERENCES app_schema.jobs("jobID")')


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
        _migration_step(db, f"drop {table}.{constraint} (tenant_id -> users)",
                        f'ALTER TABLE "{schema}"."{table}" DROP CONSTRAINT IF EXISTS "{constraint}"',
                        lock_timeout=True)


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
        _migration_step(db, f"widen {len(widen)} varchar column(s) on {table.name}",
                        f'ALTER TABLE "{schema}"."{table.name}" ' + ", ".join(widen), lock_timeout=True)


if __name__ == "__main__":
    # Can be run manually to verify/initialize database
    initialize_database()
    logger.info("✅ Database contract initialized")
