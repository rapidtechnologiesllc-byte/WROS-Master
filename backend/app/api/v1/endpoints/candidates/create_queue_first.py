"""
Create Candidate Endpoint - Queue-Driven (Async via Thunder)
=============================================================
This endpoint is registered FIRST in routes.py so the POST /create route 
matches before the general candidates/{id} route.

Workflow:
1. Validate candidate data
2. Queue async task to Thunder
3. Return message_id for polling task status
4. Thunder handler processes: SLM analysis → email delivery
"""

import logging
from datetime import date
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant_context import tenant_id_of
from app.core.dependencies import get_current_user, require_resource_permission
from app.schemas.candidate import EducationRecord, ExperienceRecord, HrCertificationItem, HrSkillItem
from app.services.message_queue_service import MessageQueueService

# CandidateEducationForm.percentage is String(10); an over-length value would
# fail the queued commit and retry until the message is FAILED.
MAX_PERCENTAGE_LENGTH = 10

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])


class CreateCandidateRequest(BaseModel):
    """Request to create a new candidate (queued for async processing)"""
    email: Optional[str] = None
    candidate_email: Optional[str] = None
    first_name: Optional[str] = None
    candidate_first_name: Optional[str] = None
    last_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    mobile: Optional[str] = None
    candidate_mobile: Optional[str] = None
    gender: Optional[str] = None
    candidate_gender: Optional[str] = None
    current_location: Optional[str] = None
    candidate_current_location: Optional[str] = None
    source: Optional[str] = "form_submission"
    candidate_source: Optional[str] = None
    resume_data: Optional[dict] = None
    education: Optional[list] = None
    experience: Optional[list] = None
    certifications: Optional[list] = None
    # Fields sent by the Add Candidate form (CandidateCreate.js). Previously
    # undeclared, so Pydantic silently discarded them.
    candidate_role: Optional[str] = None  # accepted but ignored - the role is always "Candidate"
    candidate_middle_name: Optional[str] = None
    # Add Candidate form's Thunder toggle (None = default: enabled)
    thunder_enabled: Optional[bool] = None
    candidate_job_title: Optional[str] = None
    candidate_experience: Optional[str] = None
    candidate_skills: Optional[Union[str, List[str]]] = None
    candidate_date_of_birth: Optional[date] = None
    candidate_joining_date: Optional[date] = None
    candidate_expected_salary: Optional[str] = None
    candidate_expected_salary_type: Optional[str] = None
    candidate_current_salary: Optional[str] = None
    candidate_current_salary_type: Optional[str] = None
    assigned_recruiter_id: Optional[str] = None  # Recruiter assigned to this candidate (not HR Manager - different role)
    assigned_report_manager_id: Optional[str] = None
    candidate_notice_period: Optional[int] = None
    education_records: Optional[List[EducationRecord]] = None
    experience_records: Optional[List[ExperienceRecord]] = None
    skill_records: Optional[List[HrSkillItem]] = None
    certification_records: Optional[List[HrCertificationItem]] = None
    # Employee referral: who referred the candidate (Employee.id, required when the source is
    # an employee referral) and the job they were referred for, if one was picked
    referring_employee_id: Optional[str] = None
    job_id: Optional[str] = None

    class Config:
        populate_by_name = True

    def get_email(self):
        return self.email or self.candidate_email

    def get_first_name(self):
        return self.first_name or self.candidate_first_name

    def get_last_name(self):
        return self.last_name or self.candidate_last_name

    def get_mobile(self):
        return self.mobile or self.candidate_mobile

    def get_gender(self):
        return self.gender or self.candidate_gender

    def get_current_location(self):
        return self.current_location or self.candidate_current_location

    def get_source(self):
        return self.candidate_source or self.source or "form_submission"


EMPLOYEE_REFERRAL_SOURCE = "Employee Referral"


def _validate_referral(db: Session, request: "CreateCandidateRequest", source: str, tenant_id: int) -> None:
    """Fail fast (400) before queueing: an employee-referral candidate must name a current
    employee of this tenant, and a named job must exist in the tenant."""
    if source == EMPLOYEE_REFERRAL_SOURCE and not request.referring_employee_id:
        raise HTTPException(status_code=400, detail="Select the employee who referred this candidate")
    if not request.referring_employee_id:
        return
    from app.models.employee import Employee
    from app.services.employee_referral_service import NOT_REFERABLE_STATUSES
    employee = db.query(Employee).filter(Employee.id == request.referring_employee_id,
                                         Employee.tenant_id == tenant_id).first()
    if employee is None or employee.status in NOT_REFERABLE_STATUSES:
        raise HTTPException(status_code=400, detail="The referring employee is not a current employee")
    if request.job_id:
        from app.models.user import Jobs
        if db.query(Jobs.jobID).filter(Jobs.jobID == request.job_id, Jobs.tenant_id == tenant_id).first() is None:
            raise HTTPException(status_code=400, detail="The selected job does not exist")
    # Already in the system (same email/phone match creation uses): only a dormant candidate
    # can be referred; otherwise warn now, before anything is queued
    from app.services.candidate_service import find_duplicate_candidate
    from app.services.employee_referral_service import EmployeeReferralService
    existing, _ = find_duplicate_candidate(db, email=request.get_email(), mobile=request.get_mobile())
    if existing is not None:
        block = EmployeeReferralService.existing_candidate_referral_block(db, existing)
        if block:
            raise HTTPException(status_code=409, detail=block)


class CreateCandidateResponse(BaseModel):
    """Response for candidate creation request"""
    status: str
    message_id: str
    polling_endpoint: str
    polling_interval_seconds: int


@router.post(
    "/create",
    response_model=CreateCandidateResponse,
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
)
async def create_candidate(
    request: CreateCandidateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Queue candidate creation for async processing via Thunder.

    This endpoint does NOT create the candidate synchronously.
    It queues the request and returns a polling endpoint to check status.

    Workflow:
    1. Validate required fields (email, first_name, last_name)
    2. Generate candidate ID
    3. Queue 'create_candidate' task to Thunder
    4. Return message_id for polling

    Thunder async task will:
    1. Create Candidate record in database
    2. Trigger SLM for candidate analysis
    3. SLM instructs Thunder on email delivery
    4. Thunder sends welcome email

    Args:
        request: CreateCandidateRequest with candidate data
        db: Database session
        current_user: Authenticated user making the request

    Returns:
        CreateCandidateResponse with:
        - status: 'queued'
        - message_id: UUID for polling
        - polling_endpoint: URL to check status
        - polling_interval_seconds: Recommended interval

    Raises:
        HTTPException 400: Missing required fields (email, first_name, last_name)
        HTTPException 500: Failed to queue task
    """
    try:
        email = request.get_email()
        first_name = request.get_first_name()
        last_name = request.get_last_name()
        mobile = request.get_mobile()
        gender = request.get_gender()
        current_location = request.get_current_location()
        source = request.get_source()

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        if not first_name:
            raise HTTPException(status_code=400, detail="First name is required")
        if not last_name:
            raise HTTPException(status_code=400, detail="Last name is required")
        for i, record in enumerate(request.education_records or []):
            if len(record.percentage or "") > MAX_PERCENTAGE_LENGTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"Education row {i + 1}: percentage must be at most {MAX_PERCENTAGE_LENGTH} characters",
                )
        tenant_id = tenant_id_of(current_user)
        _validate_referral(db, request, source, tenant_id)

        logger.info(f"[CANDIDATE_CREATE] Queueing candidate: {email} ({first_name} {last_name})")

        # Generate task_id BEFORE enqueue to ensure returned ID matches queued message
        from uuid import uuid4
        task_id = str(uuid4())

        payload = {
            "candidate_email": email,
            "candidate_first_name": first_name,
            "candidate_last_name": last_name,
            "candidate_mobile": mobile,
            "candidate_gender": gender,
            "candidate_current_location": current_location,
            "candidate_source": source,
            "resume_data": request.resume_data,
            "education": request.education,
            "experience": request.experience,
            "certifications": request.certifications,
            "candidate_middle_name": request.candidate_middle_name,
            "thunder_enabled": request.thunder_enabled,
            "candidate_job_title": request.candidate_job_title,
            "candidate_experience": request.candidate_experience,
            "candidate_skills": request.candidate_skills,
            # enqueue() json.dumps the payload, so dates travel as ISO strings
            "candidate_date_of_birth": request.candidate_date_of_birth.isoformat() if request.candidate_date_of_birth else None,
            "candidate_joining_date": request.candidate_joining_date.isoformat() if request.candidate_joining_date else None,
            "candidate_expected_salary": request.candidate_expected_salary,
            "candidate_expected_salary_type": request.candidate_expected_salary_type,
            "candidate_current_salary": request.candidate_current_salary,
            "candidate_current_salary_type": request.candidate_current_salary_type,
            "assigned_recruiter_id": request.assigned_recruiter_id,
            "assigned_report_manager_id": request.assigned_report_manager_id,
            "candidate_notice_period": request.candidate_notice_period,
            "education_records": [r.model_dump(mode="json") for r in request.education_records or []],
            "experience_records": [r.model_dump(mode="json") for r in request.experience_records or []],
            "skill_records": [r.model_dump(mode="json") for r in request.skill_records or []],
            "certification_records": [r.model_dump(mode="json") for r in request.certification_records or []],
            "created_by_user_id": getattr(current_user, 'UserID', None),
            "tenant_id": tenant_id,
            "referring_employee_id": request.referring_employee_id,
            "referral_job_id": request.job_id if request.referring_employee_id else None,
        }

        enqueue_result = MessageQueueService.enqueue(
            task_name='create_candidate',
            task_id=task_id,
            data=payload,
        )

        # CRITICAL: Verify the enqueue result contains message_id/task_id
        if not enqueue_result:
            raise RuntimeError("Enqueue returned empty result - message not queued")

        returned_task_id = enqueue_result.get('task_id')
        returned_message_id = enqueue_result.get('message_id')

        if not returned_task_id:
            raise RuntimeError(f"CRITICAL: Enqueue failed to return task_id. Result: {enqueue_result}")

        if not returned_message_id:
            raise RuntimeError(f"CRITICAL: Enqueue failed to return message_id. Result: {enqueue_result}")

        # Verify the task_id in response matches what we sent
        if returned_task_id != task_id:
            logger.error(f"[CANDIDATE_CREATE] WARNING: task_id mismatch! Sent: {task_id}, Got: {returned_task_id}")
            # Use the returned task_id as it's the one in the queue
            task_id = returned_task_id

        # CRITICAL: Verify queue item actually exists in database
        try:
            from app.models.channel_queue import ChannelQueueItem
            from app.core.database import SessionLocal
            verify_db = SessionLocal()
            queue_item = verify_db.query(ChannelQueueItem).filter(
                ChannelQueueItem.message_id == returned_task_id
            ).first()
            verify_db.close()

            if not queue_item:
                raise RuntimeError(f"CRITICAL: Queue message {returned_task_id} not found in database after enqueue")

            logger.info(f"[CANDIDATE_CREATE] ✅ Queue item verified in DB: {returned_task_id}")
        except Exception as verify_err:
            logger.error(f"[CANDIDATE_CREATE] Failed to verify queue item: {verify_err}", exc_info=True)
            raise RuntimeError(f"Failed to verify queue creation: {str(verify_err)}")

        logger.info(f"[CANDIDATE_CREATE] ✅ Queued: task_id={task_id}, message_id={returned_message_id}")

        return CreateCandidateResponse(
            status="queued",
            message_id=returned_message_id,
            polling_endpoint=f"/api/v1/message-queue/tasks/{returned_message_id}/status",
            polling_interval_seconds=2,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CANDIDATE_CREATE] Error queuing candidate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue candidate creation: {str(e)}")
