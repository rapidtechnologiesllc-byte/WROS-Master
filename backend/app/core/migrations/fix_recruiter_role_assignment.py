"""
Migration: Fix HR Manager Recruiter Assignments

This migration identifies any candidates currently assigned to HR Managers
(instead of Recruiters) and reassigns them to actual Recruiters using round-robin.

CRITICAL FIX: HR Managers were mistakenly included in the recruiter_assignment_service
pool. This migration corrects any assignments that resulted from that bug.

Idempotent: Safe to run multiple times.
Reversible: Can be rolled back by noting which candidates were reassigned.
"""

import logging
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core import roles
from app.models.candidate import Candidate
from app.models.user import Users

logger = logging.getLogger(__name__)


def fix_hr_manager_recruiter_assignments(db: Session, tenant_id: int = 1) -> dict:
    """
    Fix any candidates assigned to HR Managers by reassigning them to Recruiters.

    Returns:
        {
            'hr_managers_found': count,
            'candidates_reassigned': count,
            'reassignments': [
                {'candidate_id': str, 'old_recruiter_id': str, 'new_recruiter_id': str},
                ...
            ]
        }
    """

    # Step 1: Find all HR Managers
    hr_managers = db.query(Users).filter(
        Users.UserRole == roles.HR_MANAGER,
        Users.tenant_id == tenant_id
    ).all()

    logger.info(f"[Migration] Found {len(hr_managers)} HR Managers in tenant {tenant_id}")

    if not hr_managers:
        return {
            'hr_managers_found': 0,
            'candidates_reassigned': 0,
            'reassignments': []
        }

    hr_manager_ids = [hm.UserID for hm in hr_managers]

    # Step 2: Find all candidates assigned to HR Managers
    candidates_with_hr_recruiters = db.query(Candidate).filter(
        and_(
            Candidate.tenant_id == tenant_id,
            Candidate.assigned_recruiter_id.in_(hr_manager_ids)
        )
    ).all()

    logger.info(f"[Migration] Found {len(candidates_with_hr_recruiters)} candidates assigned to HR Managers")

    reassignments = []

    # Step 3: Get all actual Recruiters
    recruiters = db.query(Users).filter(
        and_(
            Users.UserRole == roles.RECRUITER,
            Users.tenant_id == tenant_id,
            Users.terminated_at.is_(None)
        )
    ).all()

    if not recruiters:
        logger.error(f"[Migration] No Recruiters found in tenant {tenant_id} - cannot reassign candidates")
        return {
            'hr_managers_found': len(hr_managers),
            'candidates_reassigned': 0,
            'reassignments': []
        }

    logger.info(f"[Migration] Found {len(recruiters)} Recruiters available for reassignment")

    # Step 4: Reassign candidates to Recruiters using round-robin
    for idx, candidate in enumerate(candidates_with_hr_recruiters):
        old_recruiter_id = candidate.assigned_recruiter_id

        # Simple round-robin: use modulo to distribute evenly
        new_recruiter = recruiters[idx % len(recruiters)]
        candidate.assigned_recruiter_id = new_recruiter.UserID
        candidate.assigned_recruiter_changed_at = datetime.utcnow()
        candidate.assigned_recruiter_changed_by = "MIGRATION_FIX_HR_MANAGER"

        reassignments.append({
            'candidate_id': candidate.candidateID,
            'old_recruiter_id': old_recruiter_id,
            'new_recruiter_id': new_recruiter.UserID
        })

        logger.info(
            f"[Migration] Reassigned {candidate.candidateID}: "
            f"{old_recruiter_id} (HR Manager) → {new_recruiter.UserID} (Recruiter)"
        )

    # Step 5: Commit all changes
    db.commit()

    logger.info(
        f"[Migration] COMPLETE: Reassigned {len(candidates_with_hr_recruiters)} "
        f"candidates from HR Managers to Recruiters"
    )

    return {
        'hr_managers_found': len(hr_managers),
        'candidates_reassigned': len(candidates_with_hr_recruiters),
        'reassignments': reassignments
    }


if __name__ == "__main__":
    # For manual testing
    from app.core.database import SessionLocal

    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        result = fix_hr_manager_recruiter_assignments(db)
        print(f"\nMigration Result:")
        print(f"  HR Managers found: {result['hr_managers_found']}")
        print(f"  Candidates reassigned: {result['candidates_reassigned']}")
        print(f"  Reassignments: {len(result['reassignments'])}")
        for r in result['reassignments']:
            print(f"    - {r['candidate_id']}: {r['old_recruiter_id']} → {r['new_recruiter_id']}")
    finally:
        db.close()
