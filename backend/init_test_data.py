#!/usr/bin/env python3
"""Initialize test data for end-to-end referral system testing"""
from sqlalchemy.orm import Session
from app.core.database import engine, get_db
from app.models.base import Base
from app.models.user import Users, Jobs
from app.models.business_unit import BusinessUnit
from app.models.tenant import Tenant
from app.models.candidate import Candidate
from datetime import datetime
import uuid

def init_test_data():
    """Create test data for referral flow testing"""

    with engine.begin() as conn:
        # Create a session
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            print("Initializing test data...")

            # 0. Create Tenant if it doesn't exist
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            if not tenant:
                tenant = Tenant(
                    id=1,
                    name="Test Tenant"
                )
                db.add(tenant)
                db.commit()
                print("OK: Created test tenant")

            # 1. Create Business Unit if it doesn't exist
            bu = db.query(BusinessUnit).filter(BusinessUnit.bu_code == "TEST").first()
            if not bu:
                bu = BusinessUnit(
                    tenant_id=1,
                    bu_code="TEST",
                    name="Test Business Unit",
                    description="Business unit for testing"
                )
                db.add(bu)
                db.commit()
                print("OK: Created test business unit")

            # 2. Create test recruiter user
            recruiter = db.query(Users).filter(Users.UserEmail == "recruiter@test.com").first()
            if not recruiter:
                recruiter = Users(
                    UserID="recruiter-001",
                    UserEmail="recruiter@test.com",
                    UserName="Test Recruiter",
                    UserPassword="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5YmMxSUmGEJey",  # password123 bcrypt
                    UserRole="Recruiter",
                    tenant_id=1
                )
                db.add(recruiter)
                db.commit()
                print("OK: Created test recruiter user")

            # 3. Create test employee user
            employee = db.query(Users).filter(Users.UserEmail == "employee@test.com").first()
            if not employee:
                employee = Users(
                    UserID="employee-001",
                    UserEmail="employee@test.com",
                    UserName="Test Employee",
                    UserPassword="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5YmMxSUmGEJey",  # password123 bcrypt
                    UserRole="Employee",
                    tenant_id=1
                )
                db.add(employee)
                db.commit()
                print("OK: Created test employee user")

            # 3b. Assign Recruiter role template to recruiter user
            from app.models.role_template import RoleTemplate
            recruiter_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Recruiter", RoleTemplate.tenant_id == 1).first()
            if recruiter_role:
                # Check if user already has a role template assigned
                if not recruiter.role_template_id:
                    recruiter.role_template_id = recruiter_role.id
                    db.add(recruiter)
                    db.commit()
                    print("OK: Assigned Recruiter role to recruiter user")

            # 4. Create test job
            job = db.query(Jobs).filter(Jobs.jobTitle == "Test Position").first()
            if not job:
                job = Jobs(
                    jobID=str(uuid.uuid4()),
                    tenant_id=1,
                    jobTitle="Test Position",
                    jobDescription="A test position for referral testing",
                    jobSkills="Python, FastAPI, React",
                    jobExperience="3-5 years",
                    jobLocation="Remote",
                    companyType="Full-time",
                    salaryRange="100000-150000",
                    hiringManagerID=recruiter.UserID,
                    recuriterID=recruiter.UserID,
                    jobStatus="OPEN"
                )
                db.add(job)
                db.commit()
                print("OK: Created test job")

            print("\n[OK] Test data initialization complete!")
            print(f"   Recruiter: recruiter@test.com / password123")
            print(f"   Employee: employee@test.com / password123")
            print(f"   Test Job: {job.jobTitle}")

        except Exception as e:
            print(f"ERROR: {e}")
            db.rollback()
            raise
        finally:
            db.close()

if __name__ == "__main__":
    init_test_data()
