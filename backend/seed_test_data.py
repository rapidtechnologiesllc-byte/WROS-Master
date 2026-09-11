#!/usr/bin/env python
"""Seed test data: users and test candidate."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime
import bcrypt

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("\n=== SEEDING TEST DATA ===\n")

with engine.connect() as conn:
    # Hash password for testing
    password = "TestUser@123"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Create test users
    test_users = [
        ("superuser@blitzenx.com", "Super User", hashed),
        ("recruiter@blitzenx.com", "Test Recruiter", hashed),
        ("admin@blitzenx.com", "Admin User", hashed),
    ]

    print("Creating test users:")
    for email, name, pwd_hash in test_users:
        try:
            conn.execute(text("""
                INSERT INTO users (UserID, UserEmail, UserName, UserPassword, UserRole, tenant_id)
                VALUES (:user_id, :email, :name, :pwd, :role, :tenant_id)
                ON CONFLICT DO NOTHING
            """), {
                "user_id": email.split("@")[0],
                "email": email,
                "name": name,
                "pwd": pwd_hash,
                "role": "SuperUser" if "super" in email else "Recruiter",
                "tenant_id": 1,
            })
            print(f"  ✓ {email} (password: {password})")
        except Exception as e:
            print(f"  ⚠ {email}: {str(e)[:50]}")

    conn.commit()

    # Create test candidate
    print(f"\nCreating test candidate:")
    try:
        test_candidate = {
            "candidateID": "test_cand_001",
            "candidateEmail": "john.doe@example.com",
            "candidateFirstName": "John",
            "candidateLastName": "Doe",
            "candidateCurrentLocation": "San Francisco, CA",
            "candidateExperience": "5",
            "candidateSkills": "Python, JavaScript, React",
            "candidateJobTitle": "Senior Software Engineer",
            "upload_status": "completed",
            "thunder_enabled": True,
        }

        conn.execute(text("""
            INSERT INTO candidates
            (candidateID, candidateEmail, candidatePassword, candidateFirstName,
             candidateLastName, candidateCurrentLocation, candidateExperience,
             candidateSkills, candidateJobTitle, upload_status, thunder_enabled, tenant_id)
            VALUES (:cid, :email, :pwd, :fname, :lname, :loc, :exp, :skills, :title,
                    :status, :thunder, :tenant)
            ON CONFLICT DO NOTHING
        """), {
            "cid": test_candidate["candidateID"],
            "email": test_candidate["candidateEmail"],
            "pwd": "temp_password",  # Temp password
            "fname": test_candidate["candidateFirstName"],
            "lname": test_candidate["candidateLastName"],
            "loc": test_candidate["candidateCurrentLocation"],
            "exp": test_candidate["candidateExperience"],
            "skills": test_candidate["candidateSkills"],
            "title": test_candidate["candidateJobTitle"],
            "status": test_candidate["upload_status"],
            "thunder": test_candidate["thunder_enabled"],
            "tenant": 1,
        })
        conn.commit()
        print(f"  ✓ Test candidate created: {test_candidate['candidateEmail']}")
        print(f"    Location: {test_candidate['candidateCurrentLocation']}")
        print(f"    Experience: {test_candidate['candidateExperience']} years")
    except Exception as e:
        print(f"  ⚠ Candidate creation failed: {str(e)[:100]}")

    # Verify
    print(f"\n=== VERIFICATION ===")
    result = conn.execute(text("SELECT COUNT(*) FROM users"))
    user_count = result.fetchone()[0]

    result = conn.execute(text("SELECT COUNT(*) FROM candidates"))
    cand_count = result.fetchone()[0]

    print(f"Users in DB: {user_count}")
    print(f"Candidates in DB: {cand_count}")
    print(f"\n✓ Test data seeded successfully!\n")
