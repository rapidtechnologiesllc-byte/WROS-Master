"""
Hiring Manager Validation API Endpoints
HM approval checkpoint before interview scheduling
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from uuid import uuid4
import logging
from typing import Optional, List

from app.models import HiringManagerValidation, HMValidationStatus, HMValidationResponse, Candidate, Demand
from app.services.hiring_manager_validation_service import HiringManagerValidationService
from app.core.database import get_db
from app.schemas.hm_validation_schemas import (
    HMValidationListResponse,
    HMValidationDetailResponse,
    HMValidationResponseSubmit,
    HMValidationDecisionResponse,
    CreateValidationQuestionsRequest,
    SendValidationToHMRequest,
    SendValidationToHMResponse,
)

router = APIRouter(prefix="/hiring-manager-validations", tags=["HM Validation"])
logger = logging.getLogger(__name__)

hm_service = HiringManagerValidationService()


@router.post("/jobs/{job_id}/create-questions", response_model=dict)
async def create_validation_questions_endpoint(
    job_id: str,
    req: CreateValidationQuestionsRequest,
    db=None
):
    """
    Create validation questions for a job.
    Called during job setup by recruiter/admin.

    Args:
        job_id: Job/Demand ID
        req: Question template request with questions list

    Returns:
        Dict with status, job_id, question_count, created_at
    """
    try:
        db = db or next(get_db())

        result = hm_service.create_validation_questions(
            db=db,
            job_id=job_id,
            tenant_id=1,  # TODO: Get from current user context
            questions=[q.dict() for q in req.questions],
            timeout_hours=req.timeout_hours,
            auto_schedule=req.auto_schedule_after_approval
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating validation questions for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create validation questions")


@router.post("/send-to-hiring-manager", response_model=SendValidationToHMResponse)
async def send_to_hiring_manager(
    req: SendValidationToHMRequest,
    db=None
):
    """
    Send validation form to hiring manager.
    Called after candidate matches to job (Thunder -> AI Recruiter flow).

    Args:
        req: Request with job_id, candidate_id, hiring_manager_id

    Returns:
        SendValidationToHMResponse with validation_id, sent_to, expires_in_hours
    """
    try:
        db = db or next(get_db())

        result = hm_service.send_to_hm(
            db=db,
            job_id=req.job_id,
            candidate_id=req.candidate_id,
            hiring_manager_id=req.hiring_manager_id,
            tenant_id=1  # TODO: Get from current user context
        )

        return SendValidationToHMResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending validation to HM: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send validation")


@router.post("/record-response", response_model=dict)
async def record_hm_response_endpoint(
    validation_id: str,
    req: HMValidationResponseSubmit,
    db=None
):
    """
    Record hiring manager's validation response.
    Called when HM submits validation form via dashboard or email.

    Args:
        validation_id: Validation record ID
        req: Response submission with responses dict, decision_comment, decision_score

    Returns:
        Dict with validation_id, decision status, next_step
    """
    try:
        db = db or next(get_db())

        result = hm_service.record_hm_response(
            db=db,
            validation_id=validation_id,
            tenant_id=1,  # TODO: Get from current user context
            responses=req.responses,
            decision_comment=req.decision_comment,
            decision_score=req.decision_score
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error recording HM response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record response")


@router.get("", response_model=List[HMValidationListResponse])
async def list_validations(
    status: Optional[str] = Query(None),
    hiring_manager_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db=None
):
    """
    List pending HM validations for dashboard.
    Filters by status (PENDING, APPROVED, REJECTED, MAYBE, EXPIRED, ESCALATED)
    and hiring manager ID.
    """
    try:
        db = db or next(get_db())
        query = db.query(HiringManagerValidation)

        # Status filter
        if status:
            try:
                status_enum = HMValidationStatus[status.upper()]
                query = query.filter(HiringManagerValidation.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        # Hiring manager filter
        if hiring_manager_id:
            query = query.filter(HiringManagerValidation.hiring_manager_id == hiring_manager_id)

        # Default to PENDING if no status specified
        if not status:
            query = query.filter(HiringManagerValidation.status == HMValidationStatus.PENDING)

        total = query.count()
        validations = query.order_by(HiringManagerValidation.created_at.desc()).offset(offset).limit(limit).all()

        return [HMValidationListResponse.from_orm(v) for v in validations]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing validations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch validations")


@router.get("/{validation_id}", response_model=HMValidationDetailResponse)
async def get_validation(validation_id: str, db=None):
    """
    Get HM validation with questions and candidate details.
    Used by HM to make decision.
    """
    try:
        db = db or next(get_db())
        validation = db.query(HiringManagerValidation).filter(
            HiringManagerValidation.id == validation_id
        ).first()

        if not validation:
            raise HTTPException(status_code=404, detail="Validation not found")

        # Track dashboard view
        if not validation.notification_viewed_at:
            validation.notification_viewed_at = datetime.utcnow()
            db.commit()

        # Build response with questions from job template
        job = db.query(Jobs).filter(Jobs.jobID == validation.job_id).first()
        candidate = db.query(Candidate).filter(Candidate.candidateID == validation.candidate_id).first()

        return HMValidationDetailResponse(
            id=validation.id,
            candidate_id=validation.candidate_id,
            job_id=validation.job_id,
            status=validation.status.value,
            due_at=validation.due_at,
            questions=job.hm_validation_questions or [],
            candidate_data={
                "name": candidate.candidateName if candidate else "Unknown",
                "email": validation.candidate_id,
                "skills": candidate.skills if candidate else [],
                "experience_years": 0,  # Could be parsed from resume
            },
            resume_url=validation.candidate_resume_url if hasattr(validation, 'candidate_resume_url') else None,
            match_score=validation.match_score if hasattr(validation, 'match_score') else 0.0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching validation {validation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch validation")


@router.post("/{validation_id}/respond", response_model=HMValidationDecisionResponse)
async def submit_validation_response(
    validation_id: str,
    req: HMValidationResponseSubmit,
    db=None
):
    """
    Submit HM validation responses.
    Determines decision (APPROVED/REJECTED/MAYBE) and triggers downstream actions.
    """
    try:
        db = db or next(get_db())
        validation = db.query(HiringManagerValidation).filter(
            HiringManagerValidation.id == validation_id
        ).first()

        if not validation:
            raise HTTPException(status_code=404, detail="Validation not found")

        if validation.status != HMValidationStatus.PENDING:
            raise HTTPException(status_code=400, detail="Validation already responded to")

        # Store responses
        validation.responses = req.responses
        validation.decision_comment = req.decision_comment
        validation.decision_score = req.decision_score
        validation.responded_at = datetime.utcnow()
        validation.response_time_hours = (
            (validation.responded_at - validation.created_at).total_seconds() / 3600
        )

        # Determine decision based on responses
        decision = await hm_service.determine_decision(
            responses=req.responses,
            decision_score=req.decision_score,
            job_id=validation.job_id,
            db=db
        )

        # Store individual Q&A records for audit trail
        for q_id, response_value in req.responses.items():
            response_record = HMValidationResponse(
                id=str(uuid4()),
                validation_id=validation.id,
                question_id=q_id,
                question_text=f"Question {q_id}",  # Could fetch from job template
                question_type="yes_no",  # Could vary
                response_value=str(response_value),
                response_at=datetime.utcnow()
            )
            db.add(response_record)

        validation.status = decision["status"]

        # Handle decision outcome
        if decision["status"] == HMValidationStatus.APPROVED:
            # Schedule interview (if auto-schedule enabled)
            interview = await hm_service.schedule_interview_after_approval(
                validation=validation,
                db=db
            )
            next_action = "schedule_interview"

        elif decision["status"] == HMValidationStatus.REJECTED:
            # Mark to try next candidate
            validation.next_candidate_tried = False
            await hm_service.return_candidate_to_pool(
                validation=validation,
                db=db
            )
            next_action = "return_to_pool"

        else:  # MAYBE / UNCERTAIN
            # Escalate to HM's manager
            await hm_service.escalate_validation(
                validation=validation,
                reason="HM uncertain about candidate fit",
                db=db
            )
            next_action = "escalate_for_review"

        db.commit()

        return HMValidationDecisionResponse(
            status=validation.status.value,
            next_action=next_action,
            interview_scheduled=None,  # Could populate if auto-scheduled
            candidate_notification="Email sent"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting validation response {validation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit response")


@router.put("/{validation_id}/remind")
async def send_reminder(validation_id: str, db=None):
    """
    Send reminder email to HM for pending validations.
    Extends due date by 24 hours.
    """
    try:
        db = db or next(get_db())
        validation = db.query(HiringManagerValidation).filter(
            HiringManagerValidation.id == validation_id
        ).first()

        if not validation:
            raise HTTPException(status_code=404, detail="Validation not found")

        if validation.status != HMValidationStatus.PENDING:
            raise HTTPException(status_code=400, detail="Can only remind on pending validations")

        # Send reminder email
        await hm_service.send_validation_email(
            validation=validation,
            is_reminder=True,
            db=db
        )

        # Extend due date by 24 hours
        new_due_at = validation.due_at + timedelta(hours=24)
        validation.email_reminder_sent_at = datetime.utcnow()
        validation.due_at = new_due_at
        db.commit()

        return {
            "status": "reminder_sent",
            "reminder_sent_at": validation.email_reminder_sent_at.isoformat(),
            "new_due_at": new_due_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending reminder for validation {validation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send reminder")


@router.get("/{validation_id}/audit-trail")
async def get_audit_trail(validation_id: str, db=None):
    """
    Get full audit trail of HM validation (all Q&A responses with timestamps).
    """
    try:
        db = db or next(get_db())
        responses = db.query(HMValidationResponse).filter(
            HMValidationResponse.validation_id == validation_id
        ).order_by(HMValidationResponse.response_at).all()

        return {
            "validation_id": validation_id,
            "responses": [r.to_dict() for r in responses]
        }

    except Exception as e:
        logger.error(f"Error fetching audit trail for validation {validation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch audit trail")


@router.post("/jobs/{job_id}/validation-template", response_model=dict)
async def create_validation_template(
    job_id: str,
    template_req: "CreateValidationQuestionsRequest",
    db=None
):
    """
    Create HM validation question template for a job.
    """
    try:
        db = db or next(get_db())

        # Convert request to dict for service
        result = hm_service.create_validation_questions(
            db=db,
            job_id=job_id,
            tenant_id=1,  # TODO: Get from current user context
            questions=[q.dict() for q in template_req.questions],
            timeout_hours=template_req.timeout_hours,
            auto_schedule=template_req.auto_schedule_after_approval
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating validation template for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get("/jobs/{job_id}/validation-template", response_model=dict)
async def get_validation_template(job_id: str, db=None):
    """
    Get HM validation question template for a job.
    """
    try:
        db = db or next(get_db())
        from app.models import Demand

        job = db.query(Demand).filter(Demand.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return {
            "job_id": job_id,
            "hm_validation_required": job.hm_validation_required if hasattr(job, 'hm_validation_required') else False,
            "timeout_hours": job.hm_validation_timeout_hours if hasattr(job, 'hm_validation_timeout_hours') else 24,
            "auto_schedule_after_approval": job.auto_schedule_after_approval if hasattr(job, 'auto_schedule_after_approval') else True,
            "questions": job.hm_validation_questions or []
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching validation template for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch template")
