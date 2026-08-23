"""DEPRECATED: SQLite test data loading is no longer supported.

This script was used to load test data into local SQLite databases.
SQLite has been completely replaced with PostgreSQL.

For loading test data into PostgreSQL:

1. Ensure PostgreSQL is running and DATABASE_URL is configured:
   DATABASE_URL=postgresql://postgres:123@localhost:5432/wros_dev

2. Use API endpoints to create test data:
   $ curl -X POST http://localhost:8000/api/v1/... -d '...'

3. Or write a PostgreSQL-compatible data loading script using SQLAlchemy

For details, see DEVELOPER_ONBOARDING.md
"""
import sys

if __name__ == "__main__":
    print("ERROR: This script is deprecated.")
    print()
    print("SQLite is no longer supported. Use PostgreSQL instead.")
    print()
    print("To load test data:")
    print("  1. Ensure DATABASE_URL=postgresql://... in .env.local")
    print("  2. Use API endpoints or write a SQLAlchemy-based data loader")
    print()
    sys.exit(1)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.rbac_template import BusinessUnit
from app.models.resource_management import BenchPoolEntry
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401

random.seed(42)  # deterministic -- same fake dataset every run, easier to reason about while clicking through

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

tenant = db.query(Tenant).first()
axion = db.query(BusinessUnit).filter(BusinessUnit.name == "Axion").first()
prism = db.query(BusinessUnit).filter(BusinessUnit.name == "Prism").first()
troy = db.query(Users).filter(Users.UserID == "U-TROY-LOCAL").first()
curtis = db.query(Users).filter(Users.UserID == "U-CURTIS-LOCAL").first()

if not (tenant and axion and prism and troy and curtis):
    raise SystemExit("Base seed not found -- run scripts/setup_local_db.py first.")

INDUSTRIES_SKILLS = [
    "Guidewire PolicyCenter", "Guidewire BillingCenter", "Guidewire ClaimCenter",
    "Java", "Integration", "Rating Engine", "Cloud Migration",
]

# ---------------------------------------------------------------------------
# 25 clients (mix of CORE/SPECIALITY, both BUs, various statuses)
# ---------------------------------------------------------------------------
client_names = [
    "Acme Insurance", "Northgate Mutual", "Pinecrest Casualty", "Silverlake Assurance",
    "Coastal General", "Redwood Underwriters", "Summit Property & Casualty", "Harborview Insurance",
    "Bluepeak Mutual", "Ironclad Assurance", "Meridian Casualty", "Cascade General",
    "Fairview Underwriters", "Granite State Mutual", "Lakeside Insurance", "Westfield Assurance",
    "Vantage Casualty", "Brightpath Mutual", "Cornerstone Insurance", "Elmwood General",
    "Highpoint Underwriters", "Riverside Mutual", "Stonegate Assurance", "Timberline Casualty",
    "Vista Insurance Group",
]
clients = []
for i, name in enumerate(client_names):
    bu = axion if i % 2 == 0 else prism
    owner = troy if bu is axion else curtis
    line_type = "CORE" if i % 3 != 0 else "SPECIALITY"
    status = random.choice(["ACTIVE", "ACTIVE", "PROSPECT", "ON_HOLD"])
    existing = db.query(Client).filter(Client.company_name == f"{name} (load test)").first()
    if existing:
        clients.append(existing)
        continue
    client = Client(
        tenant_id=tenant.id, company_name=f"{name} (load test)", business_unit_id=bu.id,
        line_type=line_type, website=f"{name.lower().replace(' ', '').replace('&', 'and')}-loadtest.example.com",
        country=random.choice(["United States", "India", "United Kingdom", "Canada"]),
        status=status, created_by=owner.UserID,
    )
    db.add(client)
    clients.append(client)
db.commit()

# ---------------------------------------------------------------------------
# 20+ Opportunities across those clients, mixed stages
# ---------------------------------------------------------------------------
STAGES = ["QUALIFICATION", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
today = date.today()
opportunities_created = 0
for i in range(22):
    client = clients[i % len(clients)]
    stage = STAGES[i % len(STAGES)]
    opp = Opportunity(
        tenant_id=tenant.id, client_id=client.id,
        owner_employee_id=None,
        stage=stage,
        revenue_value_usd_cents=random.randint(50_000, 800_000) * 100,
        probability_pct={"QUALIFICATION": 20, "PROPOSAL": 40, "NEGOTIATION": 65, "WON": 100, "LOST": 0}[stage],
        expected_close_date=today + timedelta(days=random.randint(-60, 90)),
    )
    db.add(opp)
    opportunities_created += 1
db.commit()

# ---------------------------------------------------------------------------
# 40+ open Demands (open roles) across those clients
# ---------------------------------------------------------------------------
JOB_TITLES = [
    "Guidewire PolicyCenter Developer", "Guidewire BillingCenter Developer", "Guidewire ClaimCenter Developer",
    "Integration Developer", "QA Automation Engineer", "Business Analyst", "Solution Architect",
    "Rating Engine Specialist", "Cloud Migration Engineer", "DevOps Engineer",
]
demands_created = 0
for i in range(45):
    client = clients[i % len(clients)]
    bu_id = client.business_unit_id
    headcount = random.choice([1, 1, 1, 2, 3])
    filled = random.choice([0, 0, 0, 1]) if headcount > 1 else 0
    status = random.choice(["OPEN", "OPEN", "IN_PROGRESS", "DRAFT", "ON_HOLD"])
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id,
        job_title=JOB_TITLES[i % len(JOB_TITLES)],
        required_skills=f'["{random.choice(INDUSTRIES_SKILLS)}"]',
        min_experience_years=random.choice([2, 3, 5, 8]),
        work_location=random.choice(["REMOTE", "ONSITE", "HYBRID"]),
        headcount=headcount, positions_filled=filled, status=status,
        required_start_date=today + timedelta(days=random.randint(-30, 60)),
        urgency=random.choice(["IMMEDIATE", "HIGH", "NORMAL", "FLEXIBLE"]),
        assigned_bu_id=bu_id,
        billing_rate_usd_cents=random.randint(60, 150) * 100,
        revenue_potential_usd_cents=random.randint(200_000, 900_000) * 100,
    )
    db.add(demand)
    demands_created += 1
db.commit()

# ---------------------------------------------------------------------------
# A handful of extra Employees (bench + allocated) so the gap-analysis
# and revenue-to-demand screens have real supply/demand to compare.
# ---------------------------------------------------------------------------
employees_created = 0
for i in range(15):
    email = f"loadtest.employee{i}@blitzenx.com"
    existing = db.query(Employee).filter(Employee.email == email).first()
    if existing:
        continue
    on_bench = i % 3 == 0
    # CORE requires core_certified=True (DB CHECK constraint ck_core_requires_certification).
    is_core = (not on_bench) and i % 2 == 0
    emp = Employee(
        tenant_id=tenant.id, first_name=f"LoadTest{i}", last_name="Employee", email=email,
        joining_date=today - timedelta(days=random.randint(30, 900)),
        base_salary_usd_cents=random.randint(4_000, 12_000) * 100,
        current_skills=f'["{random.choice(INDUSTRIES_SKILLS)}"]',
        delivery_engine="CORE" if is_core else "SPECIALITY",
        core_certified=is_core,
        status="BENCH" if on_bench else "ALLOCATED",
        billing_classification="BENCH" if on_bench else "ALLOCATED",
    )
    db.add(emp)
    db.commit()
    employees_created += 1

    if on_bench:
        # On the bench.
        db.add(BenchPoolEntry(
            tenant_id=tenant.id, employee_id=emp.id, available_from=today,
            skill_tags=emp.current_skills,
        ))
    else:
        # Allocated to a real client via a filled demand.
        client = clients[i % len(clients)]
        filled_demand = Demand(
            tenant_id=tenant.id, client_id=client.id, job_title="Allocated Role (load test)",
            required_skills=emp.current_skills, min_experience_years=3, work_location="REMOTE",
            headcount=1, positions_filled=1, status="FILLED", assigned_bu_id=client.business_unit_id,
        )
        db.add(filled_demand)
        db.commit()
        db.add(EmployeeAllocation(
            tenant_id=tenant.id, employee_id=emp.id, demand_id=filled_demand.id, client_id=client.id, status="ACTIVE",
        ))
    db.commit()

# ---------------------------------------------------------------------------
# A few Invoices so Forecast-vs-Actual / P&L / AR aging have real numbers.
# ---------------------------------------------------------------------------
invoices_created = 0
active_clients = [c for c in clients if c.status == "ACTIVE"][:10]
for i, client in enumerate(active_clients):
    project = Project(tenant_id=tenant.id, client_id=client.id, name=f"{client.company_name} Engagement (load test)")
    db.add(project)
    db.commit()
    status = random.choice(["PAID", "PAID", "SENT", "SENT", "APPROVED"])
    sent_at = datetime.utcnow() - timedelta(days=random.randint(5, 75)) if status in ("SENT", "PAID") else None
    invoice = Invoice(
        tenant_id=tenant.id, client_id=client.id, project_id=project.id, status=status,
        total_usd_cents=random.randint(30_000, 200_000) * 100,
        billing_period_start=today.replace(day=1), billing_period_end=today,
        sent_at=sent_at,
        created_at=datetime.utcnow() - timedelta(days=random.randint(1, 20)),
    )
    db.add(invoice)
    invoices_created += 1
db.commit()

db.close()

print(f"Load test data added: {opportunities_created} opportunities, {demands_created} demands, "
      f"{employees_created} employees, {invoices_created} invoices, {len(clients)} clients.")
