#!/usr/bin/env python3
"""Initialize WROS database with tenants, users, and test data."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users, Jobs
from app.models.candidate import Candidate
from app.models.rbac import Role, Permission, RolePermission
from app.core.security import get_password_hash
from datetime import datetime, timedelta
import uuid
import random

def init_roles_and_permissions(db):
    """Initialize RBAC roles and permissions."""
    print("\n[RBAC] Initializing roles and permissions...")

    # All permissions that need to exist
    all_permissions = [
        "users.view", "users.create", "users.edit", "users.delete", "users.manage",
        "candidate.view", "candidate.create", "candidate.edit", "candidate.delete", "candidates.view",
        "recruitment.view", "recruitment.manage",
        "employee.view", "employee.manage", "employee.create",
        "business_unit.view", "business_unit.manage",
        "certifications.view",
        "locale.view", "locale.edit",
        "ai_config.view", "ai_config.edit",
        "message_templates.view", "message_templates.create", "message_templates.edit", "message_templates.delete",
        "ticket_routing.view", "ticket_routing.edit",
        "executive_signal.view",
        "error_log.view",
        "admin_settings.view", "admin_settings.edit",
        "invoice.view", "invoice.manage",
        "reports.view", "reports.financial",
        "interview.manage", "interview.view",
        "system.manage",
        "rbac.view", "rbac.manage",
    ]

    # Create permissions
    created_perms = 0
    for perm_name in all_permissions:
        existing = db.query(Permission).filter(Permission.name == perm_name).first()
        if not existing:
            perm = Permission(name=perm_name)
            db.add(perm)
            created_perms += 1
    if created_perms > 0:
        db.commit()
        print(f"    [OK] Created {created_perms} new permissions")

    # Define roles and their permissions
    role_permissions = {
        "CEO": "all",  # Gets all permissions
        "CFO": "all",  # Gets all permissions
        "Admin": "all",  # Gets all permissions
        "Super User": "all",  # Gets all permissions
        "Partner": [
            "business_unit.manage", "employee.view", "employee.manage",
            "recruitment.view", "candidate.view", "candidate.edit"
        ],
        "BU Head": [
            "business_unit.view", "employee.view", "employee.manage",
            "recruitment.view", "candidate.view",
            "reports.view", "interview.manage"
        ],
        "Recruiter": [
            "candidate.view", "candidate.create", "candidate.edit", "candidates.view",
            "recruitment.view", "interview.manage"
        ],
        "HR Manager": [
            "candidate.view", "candidate.edit", "candidates.view",
            "employee.view", "employee.manage",
            "reports.view", "interview.view"
        ],
    }

    # Create roles and assign permissions
    created_roles = 0
    for role_name, perms in role_permissions.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name)
            db.add(role)
            db.flush()
            created_roles += 1

        # Assign permissions
        if perms == "all":
            # Assign ALL permissions
            all_perms = db.query(Permission).all()
            for perm in all_perms:
                existing_rp = db.query(RolePermission).filter(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id
                ).first()
                if not existing_rp:
                    rp = RolePermission(role_id=role.id, permission_id=perm.id)
                    db.add(rp)
        else:
            # Assign specific permissions
            for perm_name in perms:
                perm = db.query(Permission).filter(Permission.name == perm_name).first()
                if perm:
                    existing_rp = db.query(RolePermission).filter(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == perm.id
                    ).first()
                    if not existing_rp:
                        rp = RolePermission(role_id=role.id, permission_id=perm.id)
                        db.add(rp)

    db.commit()
    if created_roles > 0:
        print(f"    [OK] Created {created_roles} new roles with permissions")
    else:
        print(f"    [OK] All roles already configured")


def init_database():
    """Initialize database schema and seed data."""

    # Create all tables
    print("[1] Creating database schema...")
    Base.metadata.create_all(bind=engine)
    print("    [OK] Schema created")

    db = SessionLocal()

    try:
        # Check if tenant already exists
        print("\n[2] Setting up tenant...")
        tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()
        if not tenant:
            tenant = Tenant(
                name="BlitzenX",
                is_active=True,
                default_timezone="Asia/Kolkata",
                default_date_format="MM/DD/YYYY",
                default_currency="USD"
            )
            db.add(tenant)
            db.commit()
            print("    [OK] Tenant created")
        else:
            print("    [OK] Tenant already exists")

        tenant_id = tenant.id

        # Initialize RBAC system (roles and permissions)
        init_roles_and_permissions(db)

        # Create users
        print("\n[3] Setting up users...")
        test_users = [
            {"email": "am@blitzenx.com", "password": "Am@123", "name": "Avinash Mukund", "role": "Admin"},
            {"email": "admin@blitzenx.com", "password": "Admin@123", "name": "Admin User", "role": "Admin"},
            {"email": "test@blitzenx.com", "password": "Test@123", "name": "Test User", "role": "HR Manager"},
            {"email": "superuser@blitzenx.com", "password": "Superuser!123", "name": "Super User", "role": "Super User"},
            {"email": "recruiter1@blitzenx.com", "password": "Recruiter@123", "name": "John Recruiter", "role": "Recruiter"},
            {"email": "recruiter2@blitzenx.com", "password": "Recruiter@123", "name": "Jane Recruiter", "role": "Recruiter"},
            {"email": "hr1@blitzenx.com", "password": "HR@123", "name": "HR Manager 1", "role": "HR Manager"},
            {"email": "hr2@blitzenx.com", "password": "HR@123", "name": "HR Manager 2", "role": "HR Manager"},
        ]

        created_count = 0
        for user_data in test_users:
            existing = db.query(Users).filter(Users.UserEmail == user_data["email"]).first()
            if not existing:
                user = Users(
                    UserID=str(uuid.uuid4()),
                    UserEmail=user_data["email"],
                    UserPassword=get_password_hash(user_data["password"]),
                    UserName=user_data["name"],
                    UserRole=user_data["role"],
                    tenant_id=tenant_id,
                    mfa_enabled=False,
                    digest_enabled=True,
                    thunder_enabled=True,
                    CreatedAt=datetime.utcnow()
                )
                db.add(user)
                created_count += 1
                print(f"    [OK] Created {user_data['email']}")

        db.commit()
        print(f"    [SUMMARY] {created_count} users created/updated")

        # Create jobs
        print("\n[4] Setting up jobs...")
        job_titles = [
            "Senior Guidewire Developer",
            "Guidewire InsuranceSuite Architect",
            "QA Automation Engineer",
            "Business Analyst - Insurance",
            "Guidewire Admin/Config Specialist",
        ]

        existing_jobs = db.query(Jobs).count()
        if existing_jobs == 0:
            for i, title in enumerate(job_titles):
                job = Jobs(
                    jobID=f"JOB_{i+1:03d}",
                    jobTitle=title,
                    jobDescription=f"Role: {title}. Seeking experienced professional with 5+ years in Guidewire.",
                    jobSkills="Guidewire, Java, SQL, Insurance",
                    jobExperience="5+ years",
                    jobLocation="Remote",
                    jobStatus="OPEN",
                    jobCreatedAt=datetime.utcnow(),
                    noOfPositions=random.randint(1, 3),
                    tenant_id=tenant_id,
                    companyName="BlitzenX",
                    companyType="Full Time"
                )
                db.add(job)
            db.commit()
            print(f"    [OK] Created {len(job_titles)} jobs")
        else:
            print(f"    [OK] {existing_jobs} jobs already exist")

        # Create candidates
        print("\n[5] Setting up candidates...")
        candidate_names = [
            ("Aditya", "Kumar"), ("Priya", "Singh"), ("Rahul", "Patel"), ("Neha", "Gupta"),
            ("Vikram", "Sharma"), ("Anjali", "Rao"), ("Arjun", "Verma"), ("Divya", "Nair"),
            ("Rohan", "Das"), ("Sneha", "Desai"), ("Karan", "Iyer"), ("Pooja", "Menon"),
            ("Sanjay", "Bhat"), ("Isha", "Pillai"), ("Nitin", "Reddy"), ("Richa", "Saxena"),
            ("Amit", "Joshi"), ("Priyanka", "Sharma"), ("Naveen", "Kumar"), ("Shreya", "Bose"),
            ("Harsh", "Malik"), ("Ananya", "Yadav"), ("Deepak", "Singh"), ("Megha", "Kapoor"),
            ("Aryan", "Tiwari"), ("Pooja", "Mishra"), ("Siddharth", "Kulkarni"), ("Diya", "Chatterjee"),
            ("Varun", "Agarwal"), ("Meera", "Pandey"), ("Rajesh", "Nair"), ("Kavya", "Sinha"),
            ("Nikhil", "Srivastava"), ("Ananya", "Verma"), ("Ravi", "Shankar"), ("Priya", "Malhotra"),
            ("Akshay", "Chopra"), ("Nikita", "Bansal"), ("Saurav", "Desai"), ("Sakshi", "Garg"),
            ("Kunal", "Saxena"), ("Aarav", "Sharma"), ("Anya", "Kapoor"), ("Bhavesh", "Joshi"),
            ("Chitra", "Nair"), ("Dhruv", "Rao"), ("Eshita", "Trivedi"), ("Faisal", "Khan"),
            ("Garima", "Pathak"), ("Harsh", "Saxena"), ("Ishangi", "Bhat"), ("Jayesh", "Desai"),
            ("Kavyaa", "Malhotra"), ("Lavanya", "Sharma"), ("Manish", "Patel"), ("Neelam", "Singh"),
            ("Omkar", "Gupta"), ("Pallavi", "Nair"), ("Qasim", "Ahmed"), ("Riya", "Pandey"),
        ]

        existing_candidates = db.query(Candidate).count()
        if existing_candidates == 0:
            for i, (first, last) in enumerate(candidate_names[:60]):  # 60 candidates
                candidate = Candidate(
                    candidateID=f"CAND_{i+1:03d}",
                    candidateFirstName=first,
                    candidateLastName=last,
                    candidateEmail=f"{first.lower()}.{last.lower()}_{i}@example.com",
                    candidatePassword=get_password_hash("Candidate@123"),
                    candidateRole="Candidate",
                    candidateJobTitle=random.choice(job_titles),
                    candidateExperience=f"{random.randint(1, 10)} years",
                    candidateSkills="Guidewire, Java, SQL",
                    candidateCurrentLocation="India",
                    candidateCreatedAt=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
                    candidateIsVerified=True,
                    employment_type="W2_FULLTIME",
                    source_channel="DIRECT"
                )
                db.add(candidate)
            db.commit()
            print(f"    [OK] Created 60 candidates")
        else:
            print(f"    [OK] {existing_candidates} candidates already exist")

        print("\n[SUCCESS] Database initialization complete!")
        print(f"  Tenant: BlitzenX (ID: {tenant_id})")
        print(f"  Users: {len(test_users)} test accounts")
        print(f"  Jobs: {len(job_titles)} open positions")
        print(f"  Candidates: 60 test records")
        print("\nTest Credentials:")
        for user in test_users:
            print(f"  - {user['email']} / {user['password']}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
