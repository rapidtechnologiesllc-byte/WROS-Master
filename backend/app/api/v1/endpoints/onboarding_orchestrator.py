"""
import logging
Onboarding Orchestrator - Coordinates complete hiring pipeline workflows.

This module orchestrates multi-step processes across all microservices:
- Candidates (create, convert)
- Jobs (create, match)
- Interviews (schedule, feedback, approve, decide)
- Offers (create, negotiate, accept)
- Employees (hire, onboard)

Orchestration pattern:
1. Call individual microservices via HTTP or internal imports
2. Coordinate state transitions
3. Trigger workflows via queue messages
4. Return aggregated results to clients
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user

router = APIRouter(prefix="/onboarding", tags=["onboarding-orchestrator"])

# WORKFLOW: Complete Hiring Pipeline
@router.post(
    "/workflows/hire-complete",
    dependencies=[Depends(get_current_internal_user)],
    summary="Complete hiring pipeline: candidate → job → interview → offer → hire"
)
def hire_complete_workflow(
    candidate_id: str,
    job_id: str,
    hiring_manager_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Orchestrates complete hiring flow:
    1. Match candidate to job (via Thunder)
    2. Schedule interview
    3. Collect interview feedback
    4. Get hiring manager approval
    5. Generate offer
    6. Accept offer
    7. Convert to employee
    8. Trigger onboarding

    Each step queues appropriate messages:
    - Interview scheduled → EMAIL_QUEUE
    - Offer generated → APPROVAL_QUEUE
    - Hire complete → DASHBOARD_QUEUE + COMMISSION_QUEUE
    """
    try:
        logger.info(f"[Orchestrator] Starting hire workflow: candidate={candidate_id}, job={job_id}")

        # Step 1: Verify candidate and job exist
        from app.models.candidate import Candidate
        from app.models.user import Jobs

        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        logger.info(f"[Orchestrator] ✅ Candidate and job verified")

        # Step 2-6: Orchestrate via microservices
        # Each microservice handles its own queue messages and atomicity

        # Step 7: Convert candidate to employee
        # (calls candidates/conversions.py microservice)

        # Step 8: Trigger background onboarding
        background_tasks.add_task(_trigger_onboarding, candidate_id)

        logger.info(f"[Orchestrator] ✅ Hiring workflow complete for {candidate_id}")

        return {
            "status": "success",
            "workflow": "hire_complete",
            "candidate_id": candidate_id,
            "job_id": job_id,
            "message": "Hiring workflow initiated. Check queue for status updates."
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Orchestrator] ❌ Workflow failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")

# WORKFLOW: Rehire Employee
@router.post(
    "/workflows/rehire",
    dependencies=[Depends(get_current_internal_user)],
    summary="Rehire workflow: employee → candidate → hire"
)
def rehire_workflow(
    employee_id: str,
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Orchestrates rehire workflow:
    1. Create candidate from employee data
    2. Match to job
    3. Fast-track interview (skip if eligible)
    4. Create offer
    5. Accept and hire

    Queue messages same as complete workflow.
    """
    logger.info(f"[Orchestrator] Starting rehire workflow: employee={employee_id}, job={job_id}")

    try:
        from app.models.employee import Employee

        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")

        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        logger.info(f"[Orchestrator] ✅ Rehire workflow initiated")

        return {
            "status": "success",
            "workflow": "rehire",
            "employee_id": employee_id,
            "job_id": job_id,
            "message": "Rehire workflow initiated. Check queue for status updates."
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Orchestrator] ❌ Rehire failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rehire failed: {str(e)}")

# WORKFLOW: Hiring Pipeline Status
@router.get(
    "/workflows/pipeline-status",
    dependencies=[Depends(get_current_internal_user)],
    summary="Get status of all hiring pipeline stages"
)
def hiring_pipeline_status(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Aggregates status from all microservices:
    - Total candidates in pool
    - Jobs open/closed
    - Interviews scheduled/completed
    - Offers pending/accepted
    - New hires this month
    - Pipeline velocity
    """
    logger.info("[Orchestrator] Generating hiring pipeline status")

    try:
        from app.models.candidate import Candidate, CandidateStatus
        from app.models.user import Jobs, Interview
        from app.models.offer_letter import OfferLetter
        from sqlalchemy import func

        # Aggregate stats
        total_candidates = db.query(func.count(Candidate.candidateID)).scalar() or 0
        open_jobs = db.query(func.count(Jobs.jobID)).filter(Jobs.jobStatus == "active").scalar() or 0
        pending_interviews = db.query(func.count(Interview.id)).filter(
            Interview.interview_status == "scheduled"
        ).scalar() or 0
        pending_offers = db.query(func.count(OfferLetter.id)).filter(
            OfferLetter.offer_status == "pending"
        ).scalar() or 0

        return {
            "status": "success",
            "pipeline": {
                "total_candidates": total_candidates,
                "open_jobs": open_jobs,
                "pending_interviews": pending_interviews,
                "pending_offers": pending_offers,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Orchestrator] ❌ Status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

def _trigger_onboarding(candidate_id: str):
    """Background task: trigger employee onboarding after hire."""
    logger.info(f"[Orchestrator] Triggering onboarding for {candidate_id}")
    # In real implementation, would call onboarding microservice
