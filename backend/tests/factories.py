"""Valid rows for the core models, for tests that need a world to act on.

Each factory fills every required column with a working value; pass keyword arguments to
override any field. Everything lives in tenant 1 unless told otherwise, and nothing is
committed except what the caller's session commits (each factory flushes so ids exist).
"""
import uuid
from datetime import date

from app.models.business_unit import BusinessUnit
from app.models.candidate import Candidate
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Jobs, Users


def uid() -> str:
    return uuid.uuid4().hex[:8]


def tenant(db, tenant_id: int = 1) -> Tenant:
    row = db.get(Tenant, tenant_id)
    if row is None:
        row = Tenant(id=tenant_id, name=f"Tenant {tenant_id}", is_active=True)
        db.add(row)
        db.flush()
    return row


def role(db, tenant_id: int = 1, **fields) -> RoleTemplate:
    tenant(db, tenant_id)
    values = dict(name=f"role-{uid()}", display_name="Test Role", hierarchy_level=1,
                  specialization="General", tenant_id=tenant_id, enabled=True)
    values.update(fields)
    row = RoleTemplate(**values)
    db.add(row)
    db.flush()
    return row


def user(db, tenant_id: int = 1, **fields) -> Users:
    if "role_template_id" not in fields:
        fields["role_template_id"] = role(db, tenant_id).id
    tenant(db, tenant_id)
    values = dict(UserID=f"USR-{uid()}", UserName="Test User", UserEmail=f"user-{uid()}@test.local",
                  UserPassword="x", UserRole="Employee", tenant_id=tenant_id, mfa_enabled=False,
                  password_reset_required=False)
    values.update(fields)
    row = Users(**values)
    db.add(row)
    db.flush()
    return row


def candidate(db, tenant_id: int = 1, **fields) -> Candidate:
    tenant(db, tenant_id)
    values = dict(candidateID=f"CAN-{uid()}", candidateEmail=f"cand-{uid()}@test.local", candidatePassword="x",
                  candidateFirstName="Test", candidateLastName="Candidate", tenant_id=tenant_id)
    values.update(fields)
    row = Candidate(**values)
    db.add(row)
    db.flush()
    return row


def job(db, tenant_id: int = 1, **fields) -> Jobs:
    tenant(db, tenant_id)
    values = dict(jobID=f"JOB-{uid()}", jobTitle="Engineer", jobDescription="Test job", jobSkills="Python",
                  jobExperience="5", jobLocation="Remote", tenant_id=tenant_id, is_deleted=False)
    values.update(fields)
    row = Jobs(**values)
    db.add(row)
    db.flush()
    return row


def business_unit(db, tenant_id: int = 1, **fields) -> BusinessUnit:
    tenant(db, tenant_id)
    values = dict(name=f"bu-{uid()}", display_name="Test BU", tenant_id=tenant_id, active=True)
    values.update(fields)
    row = BusinessUnit(**values)
    db.add(row)
    db.flush()
    return row


def employee(db, tenant_id: int = 1, **fields):
    from app.models.employee import Employee

    tenant(db, tenant_id)
    values = dict(tenant_id=tenant_id, first_name="Test", last_name="Employee", email=f"emp-{uid()}@test.local",
                  joining_date=date(2025, 1, 1))
    values.update(fields)
    row = Employee(**values)
    db.add(row)
    db.flush()
    return row
