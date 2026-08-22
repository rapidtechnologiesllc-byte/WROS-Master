#!/usr/bin/env python3
"""Add test data to the database for BU Head Dashboard demo."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "OnboardingModule-Backend"))

from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.demand import Demand
from datetime import datetime, timedelta
import uuid

db = SessionLocal()

# Get or create a client for the BU
bu_id = 1
client = db.query(Client).filter(Client.business_unit_id == bu_id).first()
if not client:
    print("Creating test client...")
    client = Client(
        id=str(uuid.uuid4()),
        tenant_id=1,
        business_unit_id=bu_id,
        company_name="Test Client Inc."
    )
    db.add(client)
    db.commit()
    db.refresh(client)
else:
    print(f"Using existing client: {client.company_name}")

# Create a test project
project = db.query(Project).filter(Project.client_id == client.id).first()
if not project:
    print("Creating test project...")
    project = Project(
        id=str(uuid.uuid4()),
        tenant_id=1,
        client_id=client.id,
        name="Test Project Alpha",
        status="ACTIVE",
        billing_type="TIME_AND_MATERIALS",
        currency="USD"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
else:
    print(f"Using existing project: {project.name}")

# Create test employees
employees_data = [
    ("John", "Smith", "john.smith@test.com", 15000),
    ("Sarah", "Johnson", "sarah.johnson@test.com", 17500),
    ("Mike", "Davis", "mike.davis@test.com", 16000),
    ("Emily", "Chen", "emily.chen@test.com", 18000),
]

employees = []
for first, last, email, rate_usd_cents in employees_data:
    existing = db.query(Employee).filter(Employee.email == email).first()
    if existing:
        print(f"Employee {first} {last} already exists")
        employees.append(existing)
    else:
        print(f"Creating employee {first} {last}...")
        emp = Employee(
            id=str(uuid.uuid4()),
            tenant_id=1,
            bu_id=bu_id,
            first_name=first,
            last_name=last,
            email=email,
            current_title="Senior Developer",
            billing_rate_usd_cents=int(rate_usd_cents),
            status="ACTIVE",
            employment_type="PERMANENT",
            joining_date=datetime.utcnow().date()
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        employees.append(emp)

# Create a demand for the project
print(f"\nCreating demand...")
demand = db.query(Demand).filter(Demand.project_id == project.id).first()
if not demand:
    demand = Demand(
        id=str(uuid.uuid4()),
        tenant_id=1,
        client_id=client.id,
        project_id=project.id,
        job_title=f"Senior Developer - {project.name}",
        required_skills='["Python", "JavaScript", "SQL"]',
        work_location="REMOTE",
        min_experience_years=3,
        status="OPEN"
    )
    db.add(demand)
    db.commit()
    db.refresh(demand)
    print(f"Created demand: {demand.job_title}")

# Allocate employees to the project
print(f"Allocating {len(employees)} employees to project...")
for i, emp in enumerate(employees):
    existing_alloc = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == emp.id,
        EmployeeAllocation.project_id == project.id
    ).first()

    if not existing_alloc:
        alloc = EmployeeAllocation(
            id=str(uuid.uuid4()),
            tenant_id=1,
            employee_id=emp.id,
            demand_id=demand.id,
            client_id=client.id,
            project_id=project.id,
            status="ACTIVE",
            utilization_pct=75 + (i % 3) * 10,  # 75%, 85%, 95%, 75%
            start_date=datetime.utcnow().date(),
        )
        db.add(alloc)
        db.commit()
        emp_name = f"{emp.first_name} {emp.last_name}"
        print(f"  - Allocated {emp_name} at {alloc.utilization_pct}% utilization")

# Create invoice and line items for revenue
print(f"\nCreating test revenue data...")
today = datetime.utcnow()
mtd_start = today.replace(day=1)

# Create an invoice for this month
invoice = db.query(Invoice).filter(
    Invoice.business_unit_id == bu_id,
    Invoice.billing_period_start >= mtd_start
).first()

if not invoice:
    invoice = Invoice(
        id=str(uuid.uuid4()),
        tenant_id=1,
        business_unit_id=bu_id,
        client_id=client.id,
        project_id=project.id,
        status="DRAFT",
        billing_period_start=mtd_start,
        billing_period_end=today,
        total_usd_cents=0,  # Will be updated when line items are added
        currency="USD"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    print(f"Created invoice: {invoice.id}")

# Calculate estimated revenue based on allocations and billing rates
total_revenue = 0
for i, emp in enumerate(employees):
    # Estimate: 40 hours/week * 4 weeks/month * rate
    hours_per_month = 40 * 4
    line_amount = int((emp.billing_rate_usd_cents / 100) * hours_per_month * 100)  # in cents
    total_revenue += line_amount
    emp_name = f"{emp.first_name} {emp.last_name}"
    utilization = 75 + (i % 3) * 10
    print(f"  - {emp_name}: ${line_amount / 100:.2f} ({utilization}% utilization)")

# Update invoice total (simplified - just set the total without line items)
invoice.total_usd_cents = int(total_revenue)
db.commit()

print(f"\n✓ Test data created successfully!")
print(f"  - Business Unit: North America (ID: {bu_id})")
print(f"  - Client: {client.name}")
print(f"  - Project: {project.name}")
print(f"  - Employees: {len(employees)}")
print(f"  - Total Monthly Revenue: ${total_revenue / 100:.2f}")
print(f"\nYou can now view the BU Head Dashboard at: http://localhost:3000/bu-head-dashboard")

db.close()
