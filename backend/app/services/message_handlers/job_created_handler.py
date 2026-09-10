"""Job Created Message Handler - Process job_created queue messages."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.user import Jobs

logger = logging.getLogger(__name__)


def handle_job_created(message: Any, db: Session) -> Dict[str, Any]:
    """Handle job_created message - CREATE job from queue data and assign AI recruiter.

    Queue-driven flow:
    1. Create job record in database from payload
    2. Assign AI recruiter agent to job
    3. Initiate candidate matching & sourcing autonomously

    Args:
        message: ChannelQueueItem with type='job_created' or 'job_created_flash'
        db: SQLAlchemy session

    Returns:
        {status, job_id, recruiter_assigned, sourcing_initiated}
    """
    try:
        from uuid import uuid4
        from datetime import datetime

        payload = message.payload or {}

        # Extract job data from payload
        job_data = {
            'job_id': payload.get('job_id') or str(uuid4()),
            'job_title': payload.get('job_title'),
            'job_description': payload.get('job_description'),
            'job_location': payload.get('job_location'),
            'job_skills': payload.get('job_skills', ''),
            'no_of_positions': payload.get('no_of_positions', 1),
            'hiring_manager_id': payload.get('hiring_manager_id'),
            'business_unit_id': payload.get('business_unit_id'),
            'job_status': 'Open',
            'jobCreatedAt': datetime.utcnow()
        }

        # 1. CREATE job in database (queue-driven)
        job = Jobs(
            jobID=job_data['job_id'],
            jobTitle=job_data['job_title'],
            jobDescription=job_data['job_description'],
            jobLocation=job_data['job_location'],
            jobSkills=job_data['job_skills'],
            noOfPositions=job_data['no_of_positions'],
            hiringManagerID=job_data['hiring_manager_id'],
            business_unit_id=job_data['business_unit_id'],
            jobStatus=job_data['job_status'],
            jobCreatedAt=job_data['jobCreatedAt']
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"[JobCreatedFlash] ✅ Created job {job_data['job_id']} ({job_data['job_title']}) via queue")

        # 2. Assign AI recruiter agent to job
        recruiter_assigned = False
        try:
            from app.services.spartan_orchestration_service import SpartanOrchestrationService

            recruiter_result = SpartanOrchestrationService.assign_recruiter_to_job(
                job_id=job_data['job_id'],
                job_title=job_data['job_title'],
                db=db
            )
            recruiter_assigned = recruiter_result.get('assigned', False)

            logger.info(f"[JobCreatedFlash] Recruiter assigned: {recruiter_assigned}")
        except Exception as recruiter_err:
            logger.warning(f"[JobCreatedFlash] Could not assign recruiter to {job_data['job_id']}: {recruiter_err}")

        # 3. Initiate autonomous candidate sourcing
        sourcing_initiated = False
        try:
            # Queue candidate sourcing task
            from app.services.message_queue_service import MessageQueueService

            # Spartan Pattern: Pass structured skills through queue so recruiter agents can leverage recency scoring
            sourcing_data = {
                "job_id": job_data['job_id'],
                "job_title": job_data['job_title'],
                "job_skills": job_data['job_skills']
            }

            # Include structured skills if available (Skill Matching Service will use these)
            if 'structured_skills' in payload and payload['structured_skills']:
                sourcing_data['structured_skills'] = payload['structured_skills']

            sourcing_msg = MessageQueueService.enqueue(
                task_name="source_candidates_for_job",
                data=sourcing_data
            )
            sourcing_initiated = sourcing_msg.get('status') == 'queued'

            logger.info(f"[JobCreatedFlash] Candidate sourcing initiated: {sourcing_initiated}")
        except Exception as source_err:
            logger.warning(f"[JobCreatedFlash] Could not initiate sourcing for {job_data['job_id']}: {source_err}")

        result = {
            "status": "job_created",
            "job_id": job_data['job_id'],
            "job_title": job_data['job_title'],
            "recruiter_assigned": recruiter_assigned,
            "sourcing_initiated": sourcing_initiated,
            "message": f"Job created and AI recruiter assigned for autonomous candidate sourcing"
        }

        logger.info(f"[JobCreatedFlash] ✅ Completed: {job_data['job_id']}")
        return result

    except ValueError as ve:
        logger.error(f"[JobCreatedFlash] Validation error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[JobCreatedFlash] Failed to process job creation from queue: {e}", exc_info=True)
        raise
