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
import logging
import uuid

logger = logging.getLogger(__name__)

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
                    display_name="Test BU",
                    description="Business unit for testing"
                )
                db.add(bu)
                db.commit()
                print("OK: Created test business unit")

            # 2. Get or create role templates
            from app.models.role_template import RoleTemplate

            # Ensure Recruiter role exists
            recruiter_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Recruiter", RoleTemplate.tenant_id == 1).first()
            if not recruiter_role:
                recruiter_role = RoleTemplate(
                    name="Recruiter",
                    display_name="Recruiter",
                    description="Recruiter role for test",
                    is_system=False,
                    tenant_id=1
                )
                db.add(recruiter_role)
                db.commit()
                print("OK: Created Recruiter role template")

            # Ensure HR Manager role exists
            hr_role = db.query(RoleTemplate).filter(RoleTemplate.name == "HR Manager", RoleTemplate.tenant_id == 1).first()
            if not hr_role:
                hr_role = RoleTemplate(
                    name="HR Manager",
                    display_name="HR Manager",
                    description="HR Manager role for test",
                    is_system=False,
                    tenant_id=1
                )
                db.add(hr_role)
                db.commit()
                print("OK: Created HR Manager role template")

            # 3. Create test recruiter user with role_template_id
            recruiter = db.query(Users).filter(Users.UserEmail == "recruiter@test.com").first()
            if not recruiter:
                recruiter = Users(
                    UserID="recruiter-001",
                    UserEmail="recruiter@test.com",
                    UserName="Test Recruiter",
                    UserPassword="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5YmMxSUmGEJey",  # password123 bcrypt
                    UserRole="Recruiter",
                    role_template_id=recruiter_role.id,
                    tenant_id=1
                )
                db.add(recruiter)
                db.commit()
                print("OK: Created test recruiter user with role_template_id")
            elif not recruiter.role_template_id:
                # Assign role_template_id if missing
                recruiter.role_template_id = recruiter_role.id
                db.commit()
                print("OK: Assigned role_template_id to existing recruiter user")

            # 4. Create test employee user with role_template_id
            employee = db.query(Users).filter(Users.UserEmail == "employee@test.com").first()
            if not employee:
                employee = Users(
                    UserID="employee-001",
                    UserEmail="employee@test.com",
                    UserName="Test Employee",
                    UserPassword="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5YmMxSUmGEJey",  # password123 bcrypt
                    UserRole="Employee",
                    role_template_id=hr_role.id,
                    tenant_id=1
                )
                db.add(employee)
                db.commit()
                print("OK: Created test employee user with role_template_id")
            elif not employee.role_template_id:
                # Assign role_template_id if missing
                employee.role_template_id = hr_role.id
                db.commit()
                print("OK: Assigned role_template_id to existing employee user")

            # 5. Create test job
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
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error: {str(e)}", exc_info=True)
            print(f"ERROR: {e}")
            db.rollback()
            raise
        finally:
            db.close()

if __name__ == "__main__":
    init_test_data()
