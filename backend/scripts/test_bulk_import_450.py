"""
Message Queue Test: Bulk Import 450 Candidates
================================================

This script generates 450 unique test candidates and queues them as async Celery tasks.
Used to test message queue system with realistic load.

Execution:
    python scripts/test_bulk_import_450.py

Expected output:
    - 450 candidates created in database
    - 450 async tasks queued in Celery/Redis
    - Real-time progress updates
    - Task ID list for monitoring
    - Dashboard URL for live viewing
"""

import sys
import os
import time
import uuid
from datetime import datetime, timedelta
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.candidate import Candidate
from app.tasks.bulk_import import import_candidates_task
from app.api.v1.endpoints.admin_queue import TaskStatus, log_task_message

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test data generation
JOBS = [
    "Senior Software Engineer",
    "Full Stack Developer",
    "Data Engineer",
    "Product Manager",
    "UX Designer",
    "DevOps Engineer",
    "Machine Learning Engineer",
    "Solutions Architect",
    "Business Analyst",
    "Quality Assurance Engineer"
]

LOCATIONS = [
    "San Francisco, CA",
    "New York, NY",
    "Austin, TX",
    "Seattle, WA",
    "Boston, MA",
    "Denver, CO",
    "Chicago, IL",
    "Los Angeles, CA",
    "Portland, OR",
    "Miami, FL"
]

EXPERIENCE_LEVELS = ["Entry", "Mid", "Senior", "Lead", "Principal"]


def generate_test_candidate(index: int) -> dict:
    """Generate a single test candidate with realistic data."""

    job_idx = index % len(JOBS)
    location_idx = index % len(LOCATIONS)
    exp_idx = (index // 10) % len(EXPERIENCE_LEVELS)

    candidate_id = str(uuid.uuid4())

    candidate = {
        "candidate_id": candidate_id,
        "name": f"Test Candidate {index+1:04d}",
        "email": f"candidate{index+1:04d}@test.example.com",
        "phone": f"+1-555-{1000 + (index % 9000):04d}",
        "location": LOCATIONS[location_idx],
        "job_title": JOBS[job_idx],
        "experience_years": 1 + (index % 20),
        "experience_level": EXPERIENCE_LEVELS[exp_idx],
        "resume_text": f"Experience as {JOBS[job_idx]} for {1 + (index % 20)} years",
        "status": "INTAKE",
        "source": "BULK_IMPORT_TEST",
        "created_at": datetime.utcnow().isoformat(),
    }

    return candidate


def create_candidates_in_batch(candidates: list, batch_size: int = 50) -> list:
    """Create candidates in database with batch processing."""

    db = SessionLocal()
    created_ids = []

    try:
        for i, candidate_data in enumerate(candidates):
            try:
                # Create candidate model
                candidate = Candidate(
                    CandidateID=candidate_data['candidate_id'],
                    CandidateName=candidate_data['name'],
                    CandidateEmail=candidate_data['email'],
                    CandidatePhone=candidate_data['phone'],
                    CandidateLocation=candidate_data['location'],
                    CandidateJobTitle=candidate_data['job_title'],
                    CandidateExperienceYears=candidate_data['experience_years'],
                    CandidateExperienceLevel=candidate_data['experience_level'],
                    ResumeText=candidate_data['resume_text'],
                    CandidateStatus=candidate_data['status'],
                    SourceOfCandidate=candidate_data['source'],
                    TenantID="default",
                )

                db.add(candidate)
                created_ids.append(candidate_data['candidate_id'])

                # Batch commit every N records
                if (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(f"Committed batch at record {i+1}/{len(candidates)}")

            except Exception as e:
               logger.error(f"Error: {str(e)}", exc_info=True)
                logger.error(f"Error creating candidate {i+1}: {str(e)}")
                db.rollback()
                db.add(candidate)

        # Final commit
        db.commit()
        logger.info(f"Final commit: {len(created_ids)} total candidates created")

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Database error: {str(e)}")
        db.rollback()
    finally:
        db.close()

    return created_ids


def queue_tasks(candidate_ids: list) -> list:
    """Queue async tasks for each candidate."""

    task_ids = []

    for i, candidate_id in enumerate(candidate_ids):
        try:
            # Queue async task
            task = import_candidates_task.delay(
                file_path=f"candidate_{candidate_id}",
                tenant_id="default"
            )

            task_ids.append(task.id)

            if (i + 1) % 50 == 0:
                logger.info(f"Queued {i+1}/{len(candidate_ids)} tasks")

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error queuing task for candidate {i+1}: {str(e)}")

    return task_ids


def print_summary(total: int, created: int, queued: int, start_time: datetime):
    """Print summary statistics."""

    elapsed = (datetime.utcnow() - start_time).total_seconds()

    print("\n" + "="*70)
    print(" MESSAGE QUEUE TEST: 450-CANDIDATE IMPORT")
    print("="*70)
    print(f"\nTest Execution Summary:")
    print(f"  Start Time:          {start_time.strftime('%H:%M:%S')}")
    print(f"  End Time:            {datetime.utcnow().strftime('%H:%M:%S')}")
    print(f"  Duration:            {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"\nCandidate Statistics:")
    print(f"  Total Generated:     {total}")
    print(f"  Successfully Created: {created}")
    print(f"  Creation Rate:       {created/elapsed:.1f} candidates/second")
    print(f"\nTask Queueing:")
    print(f"  Tasks Queued:        {queued}")
    print(f"  Queueing Rate:       {queued/elapsed:.1f} tasks/second")
    print(f"\nMonitoring:")
    print(f"  Dashboard URL:       http://localhost:8000/admin/queue/tasks")
    print(f"  Expected Completion: ~{created/3:.0f} seconds (at 3 tasks/sec)")
    print(f"\nNext Steps:")
    print(f"  1. Open http://localhost:8000/admin/queue/tasks in browser")
    print(f"  2. Monitor task status and progress")
    print(f"  3. Execute failure scenarios per test plan")
    print(f"  4. Document results in test_results/ directory")
    print("="*70 + "\n")


def main():
    """Main test execution."""

    start_time = datetime.utcnow()

    logger.info("="*70)
    logger.info("MESSAGE QUEUE TEST: 450-CANDIDATE BULK IMPORT")
    logger.info("="*70)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Phase 1: Generate candidates
    logger.info("\n[PHASE 1] Generating 450 test candidates...")
    candidates = [generate_test_candidate(i) for i in range(450)]
    logger.info(f"✓ Generated {len(candidates)} candidates")

    # Phase 2: Create in database
    logger.info("\n[PHASE 2] Creating candidates in database...")
    created_ids = create_candidates_in_batch(candidates)
    logger.info(f"✓ Created {len(created_ids)} candidates in database")

    # Phase 3: Queue tasks
    logger.info("\n[PHASE 3] Queuing async Celery tasks...")
    task_ids = queue_tasks(created_ids)
    logger.info(f"✓ Queued {len(task_ids)} async tasks")

    # Phase 4: Summary
    end_time = datetime.utcnow()
    print_summary(
        total=len(candidates),
        created=len(created_ids),
        queued=len(task_ids),
        start_time=start_time
    )

    # Phase 5: Initial queue status
    logger.info("\n[PHASE 5] Checking initial queue status...")
    time.sleep(2)  # Give Celery time to process initial tasks

    all_tasks = TaskStatus.get_all_tasks()
    stats = {
        "total": len(all_tasks),
        "queued": len([t for t in all_tasks if t["status"] == "queued"]),
        "active": len([t for t in all_tasks if t["status"] == "active"]),
        "completed": len([t for t in all_tasks if t["status"] == "completed"]),
        "failed": len([t for t in all_tasks if t["status"] == "failed"]),
    }

    logger.info("\nInitial Queue Status:")
    logger.info(f"  Total:     {stats['total']}")
    logger.info(f"  Queued:    {stats['queued']}")
    logger.info(f"  Active:    {stats['active']}")
    logger.info(f"  Completed: {stats['completed']}")
    logger.info(f"  Failed:    {stats['failed']}")

    logger.info("\n✅ Test setup complete!")
    logger.info(f"Monitor at: http://localhost:8000/admin/queue/tasks")
    logger.info(f"Task IDs (first 10): {task_ids[:10]}")

    return {
        "total_candidates": len(candidates),
        "created_candidates": len(created_ids),
        "queued_tasks": len(task_ids),
        "task_ids": task_ids,
        "initial_stats": stats,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


if __name__ == "__main__":
    try:
        result = main()
        print("\n✅ SUCCESS: Bulk import test initialized")
        print(f"   Created: {result['created_candidates']} candidates")
        print(f"   Queued:  {result['queued_tasks']} tasks")
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"❌ FAILED: {str(e)}", exc_info=True)
        sys.exit(1)
