"""
Builds a fresh, fully local SQLite dev database (local_dev.sqlite3) and
seeds it with fake-but-realistic data, so local click-through sessions
never need to touch the real production SQL Server again.

2026-08-06 -- built after a production login outage was root-caused to
this exact local-dev-server-connects-to-production-database setup.
Avinash's explicit instruction: never do that again, set up a proper
local DB instead. See app/core/config.py's .env.local override and
CLAUDE.md's session log for the full incident.

Run from the repo root:
    python scripts/setup_local_db.py

Safe to re-run -- deletes and rebuilds local_dev.sqlite3 from scratch
every time, so it never carries stale schema drift the way the real
production DB did (this always matches the ORM models exactly, since
it's built via Base.metadata.create_all() against a brand-new file,
same as every test in this repo, not by replaying migration history).

Local-only fake data -- no real names, emails, or figures from the real
company. LOCAL_DEV_PASSWORD below is a fixed, publicly-known local dev
password, not a real credential.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_dev.sqlite3")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"Removed existing {DB_PATH}")

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.models.base import Base
from app.models.client import Client
from app.models.employee import Employee
from app.models.rbac_template import BusinessUnit, Role
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.rbac_service_template import RBACService
import app.models  # noqa: F401 -- registers every model onto Base.metadata

LOCAL_DEV_PASSWORD = "LocalDev!2026"  # fake, local-only -- not a real credential

engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

RBACService.seed_roles_and_permissions(db)
db.commit()

tenant = Tenant(name="BlitzenX (local dev)")
db.add(tenant)
db.commit()

axion = BusinessUnit(name="Axion", tenant_id=tenant.id)
prism = BusinessUnit(name="Prism", tenant_id=tenant.id)
corporate = BusinessUnit(name="Corporate", tenant_id=tenant.id)
db.add_all([axion, prism, corporate])
db.commit()

hashed = get_password_hash(LOCAL_DEV_PASSWORD)

super_user_role = db.query(Role).filter(Role.name == "Super User").first()
partner_role = db.query(Role).filter(Role.name == "Partner").first()
bu_head_role = db.query(Role).filter(Role.name == "BU Head").first()
hr_role = db.query(Role).filter(Role.name == "HR Manager").first()
finance_role = db.query(Role).filter(Role.name == "Finance").first()

ceo = Users(
    UserID="U-CEO-LOCAL", UserRole="Super User", UserName="Avinash (local dev)",
    UserEmail="am@blitzenx.com", UserPassword=hashed,
    tenant_id=tenant.id, role_id=super_user_role.id if super_user_role else None,
)
troy = Users(
    UserID="U-TROY-LOCAL", UserRole="Partner", UserName="Troy (local dev)",
    UserEmail="troy@blitzenx.com", UserPassword=hashed,
    tenant_id=tenant.id, role_id=partner_role.id if partner_role else None, business_unit_id=axion.id,
)
curtis = Users(
    UserID="U-CURTIS-LOCAL", UserRole="Partner", UserName="Curtis (local dev)",
    UserEmail="curtis@blitzenx.com", UserPassword=hashed,
    tenant_id=tenant.id, role_id=partner_role.id if partner_role else None, business_unit_id=prism.id,
)
hemant = Users(
    UserID="U-HEMANT-LOCAL", UserRole="BU Head", UserName="Hemant (local dev)",
    UserEmail="hemant@blitzenx.com", UserPassword=hashed,
    tenant_id=tenant.id, role_id=bu_head_role.id if bu_head_role else None, business_unit_id=axion.id,
)
hr_manager = Users(
    UserID="U-HR-LOCAL", UserRole="HR Manager", UserName="HR Manager (local dev)",
    UserEmail="hr@blitzenx.com", UserPassword=hashed,
    tenant_id=tenant.id, role_id=hr_role.id if hr_role else None, business_unit_id=axion.id,
)
finance = Users(
    UserID="U-FINANCE-LOCAL", UserRole="Finance", UserName="Finance (local dev)",
    UserEmail="finance@blitzenx.com", UserPassword=hashed,
    tenant_id=tenant.id, role_id=finance_role.id if finance_role else None,
)
db.add_all([ceo, troy, curtis, hemant, hr_manager, finance])
db.commit()

hemant_employee = Employee(
    tenant_id=tenant.id, first_name="Hemant", last_name="(local dev)",
    email="hemant@blitzenx.com", joining_date=date(2024, 1, 1),
)
hr_employee = Employee(
    tenant_id=tenant.id, first_name="HR", last_name="Manager (local dev)",
    email="hr@blitzenx.com", joining_date=date(2024, 1, 1),
)
db.add_all([hemant_employee, hr_employee])
db.commit()

axion.bu_head_employee_id = hemant_employee.id
axion.hr_manager_employee_id = hr_employee.id
db.add(axion)
db.commit()

builders = Client(
    tenant_id=tenant.id, company_name="Builders Insurance (local dev)", business_unit_id=axion.id,
    line_type="CORE", website="builders-local-dev.example.com", country="United States",
    status="ACTIVE", created_by=troy.UserID,
)
goldenbear = Client(
    tenant_id=tenant.id, company_name="Goldenbear Insurance (local dev)", business_unit_id=prism.id,
    line_type="SPECIALITY", website="goldenbear-local-dev.example.com", country="United States",
    status="PROSPECT", created_by=curtis.UserID,
)
# SI Partners are real Client rows now (line_type=SPECIALITY), same
# Client Master concept as any other client -- not a separate hardcoded
# list. Seeded here so the local Projects screen's Client dropdown has
# something Specialty to pick from.
si_partners = [
    Client(
        tenant_id=tenant.id, company_name=name, business_unit_id=axion.id,
        line_type="SPECIALITY", website=f"{name.lower().replace(' ', '')}.example.com",
        status="ACTIVE", created_by=troy.UserID,
    )
    for name in ("PWC", "EY", "Castlebay", "Zensar", "LTI Mindtree")
]
db.add_all([builders, goldenbear, *si_partners])
db.commit()

db.close()

print(f"\nLocal dev database built at {DB_PATH}")
print(f"Login as CEO: am@blitzenx.com / {LOCAL_DEV_PASSWORD}")
print(f"Login as Partner (Troy/Axion): troy@blitzenx.com / {LOCAL_DEV_PASSWORD}")
print(f"Login as Partner (Curtis/Prism): curtis@blitzenx.com / {LOCAL_DEV_PASSWORD}")
print(f"Login as BU Head (Hemant/Axion): hemant@blitzenx.com / {LOCAL_DEV_PASSWORD}")
print(f"Login as HR Manager: hr@blitzenx.com / {LOCAL_DEV_PASSWORD}")
print(f"Login as Finance: finance@blitzenx.com / {LOCAL_DEV_PASSWORD}")
print("Seeded: 3 BUs (Axion/Prism/Corporate), 2 clients, Axion's BU Head + HR Manager resolved.")
