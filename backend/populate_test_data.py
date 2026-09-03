#!/usr/bin/env python3
"""
Populate test database with realistic data for all pages.
Supports testing without breaking working systems.
import logging
"""

import sys
import os
from datetime import datetime, timedelta
import uuid

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import (
    Users, Candidate, Job, JobApplication, Interview, OfferLetter,
    RoleTemplate, BusinessUnit, Department
)
from app.core.database import Base, DATABASE_URL

def get_db_session():
    """Create database session."""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def create_test_candidates(db, count=20):
    """Create test candidates for Candidates page."""
    print(f"Creating {count} test candidates...")

    candidates = []
    statuses = ["Applied", "Rejected", "Interview", "Offer", "Joined"]

    for i in range(count):
        candidate = Candidate(
            id=str(uuid.uuid4()),
            candidate_name=f"Test Candidate {i+1}",
            candidate_email=f"candidate{i+1}@test.com",
            candidate_mobile=f"+1234567890{i:02d}",
            current_location="Remote",
            notice_period=30,
            status=statuses[i % len(statuses)],
            is_active=True,
            business_unit_id=1,
            tenant_id=1,
            experience=f"{2 + (i % 5)} years"
        )
        candidates.append(candidate)
        db.add(candidate)

    db.commit()
    print(f"✅ Created {count} candidates")
    return candidates

def create_test_jobs(db, count=10):
    """Create test jobs for Jobs page."""
    print(f"Creating {count} test jobs...")

    jobs = []
    statuses = ["Open", "Closed", "On Hold"]
    locations = ["Remote", "New York", "San Francisco", "London", "Singapore"]

    for i in range(count):
        job = Jobs(
            job_id=str(uuid.uuid4()),
            job_title=f"Senior {['Engineer', 'Designer', 'Manager', 'Analyst'][i % 4]}",
            job_description=f"Test job description for position {i+1}",
            job_skills="Python, React, AWS",
            job_experience=f"{3 + (i % 5)} years",
            job_location=locations[i % len(locations)],
            company_name="BlitzenX",
            company_type="Technology",
            job_status=statuses[i % len(statuses)],
            no_of_positions=1 + (i % 3),
            salary_range=f"${80000 + (i * 10000)}-${120000 + (i * 10000)}",
            business_unit=1,
            tenant_id=1,
            created_at=datetime.utcnow() - timedelta(days=20-i),
            hiring_manager_id="superuser-uuid",
        )
        jobs.append(job)
        db.add(job)

    db.commit()
    print(f"✅ Created {count} jobs")
    return jobs

def create_test_interviews(db, candidates, jobs):
    """Create test interviews for Interviews page."""
    print("Creating test interviews...")

    if not candidates or not jobs:
        print("⚠️  No candidates or jobs - skipping interviews")
        return []

    interviews = []
    rounds = ["HR", "Technical", "Manager"]

    for i in range(min(5, len(candidates))):
        for round_idx, round_name in enumerate(rounds):
            interview = Interviews(
                interview_id=str(uuid.uuid4()),
                candidate_id=candidates[i].candidate_id,
                job_id=jobs[i % len(jobs)].job_id,
                round_name=round_name,
                start_time=datetime.utcnow() + timedelta(days=7+round_idx),
                end_time=datetime.utcnow() + timedelta(days=7+round_idx, hours=1),
                status="Scheduled",
                interviewer_id="superuser-uuid",
                tenant_id=1,
                created_at=datetime.utcnow()
            )
            interviews.append(interview)
            db.add(interview)

    db.commit()
    print(f"✅ Created {len(interviews)} interviews")
    return interviews

def create_test_offers(db, candidates):
    """Create test offers for Offer Letters page."""
    print("Creating test offers...")

    if not candidates:
        print("⚠️  No candidates - skipping offers")
        return []

    offers = []
    for i in range(min(3, len(candidates))):
        offer = Offers(
            offer_id=str(uuid.uuid4()),
            candidate_id=candidates[i].candidate_id,
            position=f"Senior Position {i+1}",
            salary=100000 + (i * 10000),
            offer_status="Approved",
            tenant_id=1,
            created_at=datetime.utcnow() - timedelta(days=5-i)
        )
        offers.append(offer)
        db.add(offer)

    db.commit()
    print(f"✅ Created {len(offers)} offers")
    return offers

def main():
    """Populate all test data."""
    print("\n" + "="*60)
    print("POPULATING TEST DATABASE")
    print("="*60 + "\n")

    db = get_db_session()

    try:
        # Create test data in order
        candidates = create_test_candidates(db, count=20)
        jobs = create_test_jobs(db, count=10)
        interviews = create_test_interviews(db, candidates, jobs)
        offers = create_test_offers(db, candidates)

        print("\n" + "="*60)
        print("✅ TEST DATA CREATED SUCCESSFULLY")
        print("="*60)
        print(f"\nCreated:")
        print(f"  - {len(candidates)} candidates")
        print(f"  - {len(jobs)} jobs")
        print(f"  - {len(interviews)} interviews")
        print(f"  - {len(offers)} offers")
        print("\nNow test these pages:")
        print("  ✓ /candidates - Should show 20 candidates")
        print("  ✓ /jobs - Should show 10 jobs")
        print("  ✓ /interviews - Should show 15 interviews")
        print("  ✓ /offer-letters - Should show 3 offers")
        print("\n")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
