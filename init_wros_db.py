#!/usr/bin/env python3
"""Initialize WROS database with tenants, users, and test data."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users, Jobs
from app.models.candidate import Candidate
from app.core.security import get_password_hash
from app.services.rbac_template_init_service import init_rbac_template_system
from datetime import datetime, timedelta
import uuid
import random



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

        # Initialize RBAC template system (modules, resources, role templates)
        print("\n[2b] Initializing RBAC template system...")
        init_rbac_template_system(db, tenant_id)
        print("    [OK] RBAC templates initialized")

        # Create Business Units
        print("\n[2c] Setting up Business Units...")
        from app.models.business_unit import BusinessUnit

        business_units_data = [
            {"name": "NA", "display_name": "North America", "bu_code": "NA", "description": "North America operations"},
            {"name": "EU", "display_name": "Europe", "bu_code": "EU", "description": "Europe operations"},
            {"name": "APAC", "display_name": "Asia-Pacific", "bu_code": "APAC", "description": "Asia-Pacific operations"},
        ]

        existing_bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).count()
        if existing_bus == 0:
            for bu_data in business_units_data:
                bu = BusinessUnit(
                    tenant_id=tenant_id,
                    name=bu_data["name"],
                    display_name=bu_data["display_name"],
                    bu_code=bu_data["bu_code"],
                    description=bu_data["description"],
                    active=True
                )
                db.add(bu)
            db.commit()
            print(f"    [OK] Created {len(business_units_data)} business units")
        else:
            print(f"    [OK] {existing_bus} business units already exist")

        # Create Delivery Centers
        print("\n[2d] Setting up Delivery Centers...")
        from app.models.delivery_center import DeliveryCenter

        delivery_centers_data = [
            {"name": "Bangalore", "code": "BNG", "location": "Bangalore, India"},
            {"name": "Delhi", "code": "DEL", "location": "Delhi, India"},
            {"name": "Chennai", "code": "CHN", "location": "Chennai, India"},
            {"name": "Hyderabad", "code": "HYD", "location": "Hyderabad, India"},
            {"name": "Remote", "code": "REMOTE", "location": "Remote / Virtual"},
        ]

        existing_delivery_centers = db.query(DeliveryCenter).filter(DeliveryCenter.tenant_id == tenant_id).count()
        if existing_delivery_centers == 0:
            for dc_data in delivery_centers_data:
                dc = DeliveryCenter(
                    tenant_id=tenant_id,
                    name=dc_data["name"],
                    code=dc_data["code"],
                    location=dc_data.get("location"),
                    active=True
                )
                db.add(dc)
            db.commit()
            print(f"    [OK] Created {len(delivery_centers_data)} delivery centers")
        else:
            print(f"    [OK] {existing_delivery_centers} delivery centers already exist")

        # Create users with job titles (role templates will be created via UI)
        print("\n[3] Setting up users...")

        test_users = [
            {"email": "am@blitzenx.com", "password": "Am!123", "name": "Avinash Mukund", "job_title": "CEO"},
            {"email": "admin@blitzenx.com", "password": "Admin!123", "name": "Admin User", "job_title": "Admin"},
            {"email": "test@blitzenx.com", "password": "Test!123", "name": "Test User", "job_title": "HR Manager"},
            {"email": "superuser@blitzenx.com", "password": "Superuser!123", "name": "Super User", "job_title": "Super User"},
            {"email": "recruiter1@blitzenx.com", "password": "Recruiter!123", "name": "John Recruiter", "job_title": "Recruiter"},
            {"email": "recruiter2@blitzenx.com", "password": "Recruiter!123", "name": "Jane Recruiter", "job_title": "Recruiter"},
            {"email": "hr1@blitzenx.com", "password": "HR!123", "name": "HR Manager 1", "job_title": "HR Manager"},
            {"email": "hr2@blitzenx.com", "password": "HR!123", "name": "HR Manager 2", "job_title": "HR Manager"},
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
                    UserRole=user_data["job_title"],  # Keep for backward compatibility
                    job_title=user_data["job_title"],
                    role_template_id=None,  # Will be assigned via UI
                    tenant_id=tenant_id,
                    mfa_enabled=False,
                    digest_enabled=True,
                    thunder_enabled=True,
                    CreatedAt=datetime.utcnow()
                )
                db.add(user)
                created_count += 1
                print(f"    [OK] Created {user_data['email']} (job_title: {user_data['job_title']})")

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
