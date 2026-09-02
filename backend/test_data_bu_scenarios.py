#!/usr/bin/env python3
"""
import logging
PHASE 3: Test Data Population with BU Scoping Scenarios

This script creates test data that enables NEGATIVE TEST CASES for BU scoping:
- Scenario A: Candidate NOT assigned to any job (NULL BU_ID - org-wide)
- Scenario B: Candidate assigned to Job in BU 1
- Scenario C: Candidate assigned to Job in BU 1, then rejected (BU_ID reverts to NULL)
- Scenario D: Candidate reassigned to different BU after rejection

Test Data Created:
- BU 1: "North America"
- BU 2: "Europe"
- BU 3: "Asia Pacific"
- Candidates: Alice (NULL), Bob (NULL), Charlie (NULL), Diana (NULL)
- Jobs: Job X (BU 1), Job Y (BU 2), Job Z (BU 3)
"""

import os
import sys
import uuid
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal, engine
from app.models.candidate import Candidate, CandidateStatus
from app.models.user import Jobs
from app.models.business_unit import BusinessUnit
from app.core.security import get_password_hash
from app.utils.uniq_id_generator import generate_password

def create_test_data():
    """Create test data with BU scoping scenarios."""
    db = SessionLocal()

    try:
        print("\n" + "="*60)
        print("PHASE 3: Test Data Population with BU Scoping Scenarios")
        print("="*60)

        # Step 1: Create Business Units
        print("\n[STEP 1] Creating Business Units...")

        bu_na = BusinessUnit(
            id=1,
            name="North America",
            display_name="North America",
            bu_code="NA",
            manager_id=None,
            tenant_id=1,
            active=True,
            created_at=datetime.utcnow()
        )
        bu_eu = BusinessUnit(
            id=2,
            name="Europe",
            display_name="Europe",
            bu_code="EU",
            manager_id=None,
            tenant_id=1,
            active=True,
            created_at=datetime.utcnow()
        )
        bu_ap = BusinessUnit(
            id=3,
            name="Asia Pacific",
            display_name="Asia Pacific",
            bu_code="APAC",
            manager_id=None,
            tenant_id=1,
            active=True,
            created_at=datetime.utcnow()
        )

        # Check if BUs already exist
        existing_bus = db.query(BusinessUnit).filter(BusinessUnit.id.in_([1, 2, 3])).count()
        if existing_bus == 0:
            db.add(bu_na)
            db.add(bu_eu)
            db.add(bu_ap)
            db.commit()
            print(f"✓ Created 3 BUs: NA, EU, APAC")
        else:
            print(f"✓ BUs already exist (count: {existing_bus}/3)")

        # Step 2: Create Jobs for each BU
        print("\n[STEP 2] Creating Jobs by BU...")

        jobs_data = [
            {
                "jobID": "job-x-" + str(uuid.uuid4())[:8],
                "jobTitle": "Senior Engineer - NA",
                "businessUnit": "NA",
                "business_unit_id": 1,
                "company_name": "BlitzenX",
                "department": "Engineering",
            },
            {
                "jobID": "job-y-" + str(uuid.uuid4())[:8],
                "jobTitle": "Product Manager - EU",
                "businessUnit": "EU",
                "business_unit_id": 2,
                "company_name": "BlitzenX",
                "department": "Product",
            },
            {
                "jobID": "job-z-" + str(uuid.uuid4())[:8],
                "jobTitle": "Data Scientist - APAC",
                "businessUnit": "APAC",
                "business_unit_id": 3,
                "company_name": "BlitzenX",
                "department": "Data",
            },
        ]

        job_objects = {}
        for job_data in jobs_data:
            existing_job = db.query(Jobs).filter(
                Jobs.jobTitle == job_data["jobTitle"]
            ).first()

            if not existing_job:
                job = Jobs(
                    jobID=job_data["jobID"],
                    jobTitle=job_data["jobTitle"],
                    business_unit_id=job_data["business_unit_id"],
                    company_name=job_data["company_name"],
                    department=job_data["department"],
                    noOfPosition=1,
                    minExperience=3,
                    maxExperience=10,
                    minSalary=100000,
                    maxSalary=150000,
                    createdAt=datetime.utcnow(),
                )
                db.add(job)
                db.flush()
                job_objects[job_data["businessUnit"]] = job
                print(f"✓ Created Job: {job_data['jobTitle']} (BU: {job_data['businessUnit']})")
            else:
                job_objects[existing_job.business_unit_id] = existing_job
                print(f"✓ Job exists: {existing_job.jobTitle}")

        db.commit()

        # Step 3: Create Test Candidates (Scenario A - all start with NULL BU_ID)
        print("\n[STEP 3] Creating Test Candidates (all starting with NULL BU_ID)...")

        candidates_data = [
            {
                "name": "Alice",
                "email": "alice.test@example.com",
                "scenario": "A - Org-wide (not assigned to any job)"
            },
            {
                "name": "Bob",
                "email": "bob.test@example.com",
                "scenario": "B - Will be assigned to Job in BU 1"
            },
            {
                "name": "Charlie",
                "email": "charlie.test@example.com",
                "scenario": "C - Will be assigned then rejected (reverts to NULL)"
            },
            {
                "name": "Diana",
                "email": "diana.test@example.com",
                "scenario": "D - Will be reassigned across BUs"
            },
        ]

        candidate_objects = {}
        for cand_data in candidates_data:
            existing_candidate = db.query(Candidate).filter(
                Candidate.candidateEmail == cand_data["email"]
            ).first()

            if not existing_candidate:
                password = generate_password()
                candidate = Candidate(
                    candidateID="cand-" + str(uuid.uuid4())[:12],
                    candidateFirstName=cand_data["name"],
                    candidateEmail=cand_data["email"],
                    candidateMobile="555-0000",
                    candidatePassword=get_password_hash(password),
                    candidateTempPassword=password,
                    candidateRole="Candidate",
                    candidateCurrentLocation="San Francisco, CA, USA",
                    candidateCreatedAt=datetime.utcnow(),
                    # BU Scoping: Start with NULL (org-wide)
                    submission_bu_id=None,
                    associated_bu_id=None,
                    submission_timestamp=None,
                )
                db.add(candidate)
                db.flush()

                # Create candidate status
                status = CandidateStatus(
                    candidateID=candidate.candidateID,
                    piplineStatus="Applied",
                    status="Active",
                    createdAt=datetime.utcnow(),
                    updatedAt=datetime.utcnow(),
                )
                db.add(status)

                candidate_objects[cand_data["name"]] = candidate
                print(f"✓ Created Candidate: {cand_data['name']}")
                print(f"  - Email: {cand_data['email']}")
                print(f"  - BU: NULL (org-wide)")
                print(f"  - Scenario: {cand_data['scenario']}")
            else:
                candidate_objects[cand_data["name"]] = existing_candidate
                print(f"✓ Candidate exists: {cand_data['name']}")

        db.commit()

        # Step 4: Test Scenario B - Assign Bob to Job X in BU 1
        print("\n[STEP 4] Testing Scenario B: Assign Bob to Job in BU 1...")

        bob = candidate_objects.get("Bob")
        if bob and bob.associated_bu_id is None:
            bob.submission_bu_id = 1
            bob.associated_bu_id = 1
            bob.submission_timestamp = datetime.utcnow()
            db.commit()
            print(f"✓ Bob assigned to BU 1 (North America)")
            print(f"  - submission_bu_id: {bob.submission_bu_id}")
            print(f"  - associated_bu_id: {bob.associated_bu_id}")
            print(f"  - Now visible to: BU 1 users only")
            print(f"  - Not visible to: BU 2, BU 3 users")

        # Step 5: Test Scenario C - Assign Charlie to Job in BU 1, then reject
        print("\n[STEP 5] Testing Scenario C: Assign Charlie to BU 1, then reject...")

        charlie = candidate_objects.get("Charlie")
        if charlie and charlie.associated_bu_id is None:
            # Initial assignment
            charlie.submission_bu_id = 1
            charlie.associated_bu_id = 1
            charlie.submission_timestamp = datetime.utcnow()
            db.commit()
            print(f"✓ Charlie assigned to BU 1")
            print(f"  - submission_bu_id: {charlie.submission_bu_id}")
            print(f"  - associated_bu_id: {charlie.associated_bu_id}")

            # Simulate rejection (revert to NULL)
            charlie.associated_bu_id = None
            charlie.submission_bu_id = None
            db.commit()
            print(f"✓ Charlie rejected - reverted to org-wide")
            print(f"  - submission_bu_id: {charlie.submission_bu_id}")
            print(f"  - associated_bu_id: {charlie.associated_bu_id}")
            print(f"  - Now visible to: ALL HR users")

        # Step 6: Print Summary
        print("\n" + "="*60)
        print("TEST DATA SUMMARY")
        print("="*60)

        print("\nBusiness Units Created:")
        for bu in db.query(BusinessUnit).filter(BusinessUnit.id.in_([1, 2, 3])).all():
            print(f"  - BU {bu.id}: {bu.name} ({bu.bu_code})")

        print("\nJobs Created:")
        for job in db.query(Jobs).order_by(Jobs.business_unit_id).all():
            print(f"  - Job: {job.jobTitle}")
            print(f"    - BU ID: {job.business_unit_id}")

        print("\nCandidates Created:")
        for cand in db.query(Candidate).order_by(Candidate.candidateFirstName).all():
            bu_info = f"BU {cand.associated_bu_id}" if cand.associated_bu_id else "NULL (org-wide)"
            print(f"  - Candidate: {cand.candidateFirstName}")
            print(f"    - Email: {cand.candidateEmail}")
            print(f"    - Associated BU: {bu_info}")
            print(f"    - Submission BU: {cand.submission_bu_id}")

        print("\n" + "="*60)
        print("SCENARIOS READY FOR TESTING")
        print("="*60)

        print("""
Scenario A: Alice (NULL BU_ID - org-wide)
  - ✓ Created
  - Test: Can be seen by ALL HR users (not filtered by BU)
  - Test: Can be submitted to any job regardless of BU

Scenario B: Bob (assigned to BU 1)
  - ✓ Created and assigned to BU 1
  - Test: Only HR users in BU 1 can see Bob
  - Test: Users in BU 2 CANNOT see Bob

Scenario C: Charlie (assigned to BU 1, then rejected, reverts to NULL)
  - ✓ Created, assigned to BU 1, then rejected
  - Now BU_ID is NULL again
  - Test: NOW visible to ALL HR users again

Scenario D: Diana (will be reassigned across BUs)
  - ✓ Created with NULL BU_ID
  - Next: Submit Diana to Job Y (BU 2)
  - Then: Verify Diana's BU_ID becomes 2
  - Then: Switch to BU 1 user and verify Diana NO LONGER visible
        """)

        print("\n✓ Phase 3 Complete: Test Data Populated")
        return True

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"✗ Error during test data creation: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = create_test_data()
    sys.exit(0 if success else 1)
