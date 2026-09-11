#!/usr/bin/env python
"""Create test user and candidate for E2E testing."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import hashlib

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("\n=== CREATING TEST DATA ===\n")

with engine.connect() as conn:
    # Create test user
    print("Creating test user:")
    user_id = "superuser_test"
    email = "superuser@blitzenx.com"
    password_hash = hashlib.sha256("TestUser@123".encode()).hexdigest()

    try:
        conn.execute(text("""
            INSERT INTO users ("UserID", "UserEmail", "UserName", "UserPassword", "UserRole", "tenant_id")
            VALUES (:uid, :email, :name, :pwd, :role, :tenant)
        """), {
            "uid": user_id,
            "email": email,
            "name": "Super User Test",
            "pwd": password_hash,
            "role": "SuperUser",
            "tenant": 1,
        })
        conn.commit()
        print(f"  ✓ User created: {email}")
    except Exception as e:
        print(f"  ⚠ Error: {str(e)[:100]}")
        conn.rollback()

    # Create test candidate
    print("\nCreating test candidate:")
    try:
        conn.execute(text("""
            INSERT INTO candidates
            ("candidateID", "candidateEmail", "candidatePassword", "candidateFirstName",
             "candidateLastName", "candidateCurrentLocation", "candidateExperience",
             "candidateSkills", "candidateJobTitle", "upload_status", "thunder_enabled", "tenant_id")
            VALUES (:cid, :email, :pwd, :fname, :lname, :loc, :exp, :skills, :title, :status, :thunder, :tenant)
        """), {
            "cid": "test_candidate_001",
            "email": "john.doe@example.com",
            "pwd": password_hash,
            "fname": "John",
            "lname": "Doe",
            "loc": "San Francisco, CA",
            "exp": 5,
            "skills": "Python,JavaScript,React",
            "title": "Senior Software Engineer",
            "status": "completed",
            "thunder": True,
            "tenant": 1,
        })
        conn.commit()
        print(f"  ✓ Candidate created: john.doe@example.com")
        print(f"    Location: San Francisco, CA")
        print(f"    Experience: 5 years")
    except Exception as e:
        print(f"  ⚠ Error: {str(e)[:100]}")
        conn.rollback()

    # Verify counts
    print(f"\n=== VERIFICATION ===")
    result = conn.execute(text("SELECT COUNT(*) FROM users"))
    user_count = result.fetchone()[0]

    result = conn.execute(text("SELECT COUNT(*) FROM candidates"))
    cand_count = result.fetchone()[0]

    print(f"Users in DB: {user_count}")
    print(f"Candidates in DB: {cand_count}")
    print(f"\n✓ Test data ready for E2E testing!\n")
    print(f"Login credentials:")
    print(f"  Email: superuser@blitzenx.com")
    print(f"  Password: TestUser@123\n")
