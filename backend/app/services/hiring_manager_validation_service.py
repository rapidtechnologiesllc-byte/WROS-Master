"""HRMS-1104 -- Hiring Manager Validation Questions (Phase 3, S-319)"""
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional, Dict, Any, List

from app.models import (
    HiringManagerValidation,
    HMValidationResponse,
    HMValidationStatus,
    Jobs,
    Candidate,
    Users,
    Demand,
)

logger = logging.getLogger(__name__)


class HiringManagerValidationService:
    """Pre-interview validation from hiring manager (HRMS-1104).

    Workflow:
    1. After candidate matches to job (Thunder → AI Recruiter)
    2. Check if job requires HM validation
    3. Create validation request and send to HM
    4. HM answers questions via email or dashboard
    5. HM decision (APPROVED → schedule interview, REJECTED → try next candidate, MAYBE → escalate)
    """

    def create_validation_questions(
        self,
        db: Session,
        job_id: str,
        tenant_id: int,
        questions: List[Dict[str, Any]],
        timeout_hours: int = 24,
        auto_schedule: bool = True
    ) -> Dict[str, Any]:
        """
        Create/update validation questions for a job.

        Args:
            db: Database session
            job_id: Job ID (Demand.id)
            tenant_id: Tenant ID
            questions: List of question dicts with question_id, question_text, question_type, etc.
            timeout_hours: How long before validation expires
            auto_schedule: Auto-schedule interview if HM approves

        Returns:
            Dict with status, job_id, question_count, created_at

        Raises:
            ValueError if job not found or questions invalid
        """
        try:
            # Fetch job (demand)
            job = db.query(Demand).filter(
                and_(Demand.id == job_id, Demand.tenant_id == tenant_id)
            ).first()

            if not job:
                raise ValueError(f"Job {job_id} not found for tenant {tenant_id}")

            if not questions or len(questions) == 0:
                raise ValueError("At least one question is required")

            if len(questions) > 10:
                raise ValueError("Maximum 10 questions allowed")

            # Validate each question has required fields
            for q in questions:
                if 'question_id' not in q or 'question_text' not in q:
                    raise ValueError("Each question must have question_id and question_text")

            # Store questions as JSON in job record
            job.hm_validation_questions = questions
            job.hm_validation_required = True
            job.hm_validation_timeout_hours = timeout_hours
            job.auto_schedule_after_approval = auto_schedule

            db.commit()

            logger.info(
                f"Created {len(questions)} validation questions for job {job_id}",
                extra={"tenant_id": tenant_id}
            )

            return {
                "status": "success",
                "job_id": job_id,
                "question_count": len(questions),
                "question_ids": [q.get("question_id") for q in questions],
                "template_version": "1.0",
                "timeout_hours": timeout_hours,
                "auto_schedule_after_approval": auto_schedule,
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to create validation questions: {str(e)}")
            raise

    def send_to_hm(
        self,
        db: Session,
        job_id: str,
        candidate_id: str,
        hiring_manager_id: str,
        tenant_id: int
    ) -> Dict[str, Any]:
        """
        Create validation request and send to hiring manager.

        Args:
            db: Database session
            job_id: Job ID (Demand.id)
            candidate_id: Candidate ID
            hiring_manager_id: User ID of hiring manager
            tenant_id: Tenant ID

        Returns:
            Dict with validation_id, status, sent_at, expires_in_hours

        Raises:
            ValueError if job, candidate, or HM not found
        """
        try:
            # Validate job exists and has validation questions
            job = db.query(Demand).filter(
                and_(Demand.id == job_id, Demand.tenant_id == tenant_id)
            ).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            if not job.hm_validation_required or not job.hm_validation_questions:
                raise ValueError(f"Job {job_id} does not have validation questions configured")

            # Validate candidate exists
            candidate = db.query(Candidate).filter(
                and_(Candidate.candidateID == candidate_id, Candidate.tenant_id == tenant_id)
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # Validate hiring manager exists
            hm = db.query(Users).filter(Users.UserID == hiring_manager_id).first()

            if not hm:
                raise ValueError(f"Hiring manager {hiring_manager_id} not found")

            # Check if validation already exists for this candidate/job combo
            existing = db.query(HiringManagerValidation).filter(
                and_(
                    HiringManagerValidation.candidate_id == candidate_id,
                    HiringManagerValidation.job_id == job_id,
                    HiringManagerValidation.status == HMValidationStatus.PENDING
                )
            ).first()

            if existing:
                # Return existing validation instead of creating duplicate
                logger.info(
                    f"Validation already exists for candidate {candidate_id} job {job_id}",
                    extra={"validation_id": existing.id}
                )
                return {
                    "status": "already_exists",
                    "validation_id": existing.id,
                    "job_id": job_id,
                    "candidate_id": candidate_id,
                    "sent_to": hm.user_email,
                    "sent_at": existing.email_sent_at.isoformat() if existing.email_sent_at else None,
                    "expires_in_hours": job.hm_validation_timeout_hours or 24,
                    "dashboard_link": f"/validations/{existing.id}"
                }

            # Create validation record
            validation_id = str(uuid.uuid4())
            now = datetime.utcnow()
            due_at = now + timedelta(hours=job.hm_validation_timeout_hours or 24)

            validation = HiringManagerValidation(
                id=validation_id,
                candidate_id=candidate_id,
                job_id=job_id,
                hiring_manager_id=hiring_manager_id,
                status=HMValidationStatus.PENDING,
                created_at=now,
                due_at=due_at,
                email_sent_at=now,
                created_by="ai_recruiter_system"
            )

            db.add(validation)
            db.commit()

            logger.info(
                f"Created validation {validation_id} for candidate {candidate_id}, job {job_id}, HM {hiring_manager_id}",
                extra={"tenant_id": tenant_id}
            )

            # TODO: Send email notification to HM (integrate with email service)
            # email_service.send_hm_validation_email(
            #     to=hm.user_email,
            #     validation=validation,
            #     candidate=candidate,
            #     job=job,
            #     questions=job.hm_validation_questions
            # )

            return {
                "status": "success",
                "validation_id": validation_id,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "sent_to": hm.user_email,
                "sent_at": now.isoformat(),
                "expires_in_hours": job.hm_validation_timeout_hours or 24,
                "dashboard_link": f"/validations/{validation_id}"
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to send validation to HM: {str(e)}")
            raise

    def record_hm_response(
        self,
        db: Session,
        validation_id: str,
        tenant_id: int,
        responses: Dict[str, Any],
        decision_comment: Optional[str] = None,
        decision_score: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Record hiring manager's validation response.

        Args:
            db: Database session
            validation_id: Validation ID
            tenant_id: Tenant ID
            responses: Map of question_id -> response value
            decision_comment: HM's comment/reasoning
            decision_score: HM's recommendation score (1-10)

        Returns:
            Dict with validation_id, decision status, next_step

        Raises:
            ValueError if validation not found or already responded
        """
        try:
            # Fetch validation
            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"Validation {validation_id} not found")

            if validation.status != HMValidationStatus.PENDING:
                raise ValueError(f"Validation already responded to with status {validation.status}")

            if not responses or len(responses) == 0:
                raise ValueError("At least one response is required")

            # Record response details
            validation.responses = responses
            validation.decision_comment = decision_comment
            validation.decision_score = decision_score
            validation.responded_at = datetime.utcnow()
            validation.response_time_hours = int(
                (validation.responded_at - validation.created_at).total_seconds() / 3600
            )

            # Store individual Q&A records for audit trail
            for question_id, response_value in responses.items():
                response_record = HMValidationResponse(
                    id=str(uuid.uuid4()),
                    validation_id=validation.id,
                    question_id=question_id,
                    question_text=f"Question {question_id}",  # Could fetch from job template
                    question_type="yes_no",  # Could vary by question
                    response_value=str(response_value),
                    response_at=datetime.utcnow()
                )
                db.add(response_record)

            # Determine decision based on HM responses
            decision = self._determine_decision(
                responses=responses,
                decision_score=decision_score,
                validation=validation,
                db=db
            )

            validation.status = decision["status"]
            next_step = decision["next_step"]

            db.commit()

            logger.info(
                f"Recorded HM response for validation {validation_id}: decision={validation.status}, next_step={next_step}",
                extra={"tenant_id": tenant_id}
            )

            return {
                "status": "success",
                "validation_id": validation_id,
                "decision": validation.status.value,
                "decision_comment": decision_comment,
                "decision_score": decision_score,
                "response_time_hours": validation.response_time_hours,
                "decision_time": validation.responded_at.isoformat(),
                "next_step": next_step
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to record HM response: {str(e)}")
            raise

    def determine_decision(
        self,
        responses: Dict[str, Any],
        decision_score: Optional[int],
        job_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Determine HM decision based on responses (used by endpoint).

        Args:
            responses: Map of question_id -> response value
            decision_score: HM's recommendation score (1-10)
            job_id: Job ID for context
            db: Database session

        Returns:
            Dict with status and next_step
        """
        # Look for decision question (typically final yes/no/maybe question)
        final_decision = responses.get("q_004") or responses.get("final_decision")

        if final_decision and str(final_decision).lower() in ["yes", "approved", "true", "1"]:
            return {
                "status": HMValidationStatus.APPROVED,
                "next_step": "schedule_interview"
            }
        elif final_decision and str(final_decision).lower() in ["no", "rejected", "false", "0"]:
            return {
                "status": HMValidationStatus.REJECTED,
                "next_step": "return_to_pool"
            }
        elif final_decision and str(final_decision).lower() in ["maybe", "uncertain", "escalate"]:
            return {
                "status": HMValidationStatus.MAYBE,
                "next_step": "escalate_for_review"
            }
        elif decision_score and decision_score <= 4:
            # Low score = rejection
            return {
                "status": HMValidationStatus.REJECTED,
                "next_step": "return_to_pool"
            }
        elif decision_score and decision_score >= 8:
            # High score = approval
            return {
                "status": HMValidationStatus.APPROVED,
                "next_step": "schedule_interview"
            }
        else:
            # Ambiguous = escalate for review
            return {
                "status": HMValidationStatus.MAYBE,
                "next_step": "escalate_for_review"
            }

    def _determine_decision(
        self,
        responses: Dict[str, Any],
        decision_score: Optional[int],
        validation: HiringManagerValidation,
        db: Session
    ) -> Dict[str, Any]:
        """
        Internal method to determine decision based on responses.

        Business logic:
        - Look for q_004 (primary decision question)
        - If yes/approved → APPROVED
        - If no/rejected → REJECTED
        - If maybe/uncertain → MAYBE (escalate)
        - If score ≤4 → REJECTED
        - If score ≥8 → APPROVED
        - Otherwise → MAYBE
        """
        # Check for decision question
        final_decision = responses.get("q_004") or responses.get("final_decision")

        if final_decision:
            final_str = str(final_decision).lower().strip()
            if final_str in ["yes", "approved", "true", "1", "approve"]:
                return {
                    "status": HMValidationStatus.APPROVED,
                    "next_step": "schedule_interview"
                }
            elif final_str in ["no", "rejected", "false", "0", "reject"]:
                return {
                    "status": HMValidationStatus.REJECTED,
                    "next_step": "return_to_pool"
                }
            elif final_str in ["maybe", "uncertain", "escalate", "2", "maybe"]:
                return {
                    "status": HMValidationStatus.MAYBE,
                    "next_step": "escalate_for_review"
                }

        # Fall back to score if present
        if decision_score:
            if decision_score <= 4:
                return {
                    "status": HMValidationStatus.REJECTED,
                    "next_step": "return_to_pool"
                }
            elif decision_score >= 8:
                return {
                    "status": HMValidationStatus.APPROVED,
                    "next_step": "schedule_interview"
                }
            else:  # 5-7
                return {
                    "status": HMValidationStatus.MAYBE,
                    "next_step": "escalate_for_review"
                }

        # Default to escalation if unclear
        return {
            "status": HMValidationStatus.MAYBE,
            "next_step": "escalate_for_review"
        }

    async def schedule_interview_after_approval(
        self,
        validation: HiringManagerValidation,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Schedule interview after HM approves candidate.

        Args:
            validation: Approved validation record
            db: Database session

        Returns:
            Interview details or None if not auto-scheduled

        Note: This is a placeholder for actual interview scheduling logic.
        The actual implementation would call the interview service.
        """
        try:
            # TODO: Implement interview scheduling
            # This would call interview_service.create_interview() with:
            # - job_id = validation.job_id
            # - candidate_id = validation.candidate_id
            # - hiring_manager_id = validation.hiring_manager_id
            # - hm_answers = validation.responses (pass to interview panel for context)

            logger.info(
                f"Interview scheduling triggered for validation {validation.id}",
                extra={"candidate_id": validation.candidate_id, "job_id": validation.job_id}
            )

            return None

        except Exception as e:            logger.error(f"Failed to schedule interview: {str(e)}")
            return None

    async def return_candidate_to_pool(
        self,
        validation: HiringManagerValidation,
        db: Session
    ) -> None:
        """
        Return candidate to pool when HM rejects.

        Args:
            validation: Rejected validation record
            db: Database session

        Note: This would trigger Thunder to try the next best candidate for the job.
        """
        try:
            logger.info(
                f"Returning candidate {validation.candidate_id} to pool (validation {validation.id} rejected)",
                extra={"job_id": validation.job_id}
            )

            # TODO: Trigger "try next candidate" in Thunder
            # This would call thunder_service.try_next_candidate(job_id=validation.job_id)

        except Exception as e:            logger.error(f"Failed to return candidate to pool: {str(e)}")

    async def escalate_validation(
        self,
        validation: HiringManagerValidation,
        reason: str,
        db: Session,
        escalate_to_user_id: Optional[str] = None
    ) -> None:
        """
        Escalate validation for manual review (when HM is uncertain).

        Args:
            validation: MAYBE status validation record
            reason: Reason for escalation
            db: Database session
            escalate_to_user_id: Optional user to escalate to (HM's manager)
        """
        try:
            validation.status = HMValidationStatus.ESCALATED
            validation.escalation_reason = reason
            validation.escalated_at = datetime.utcnow()

            if escalate_to_user_id:
                validation.escalated_to_user_id = escalate_to_user_id

            db.commit()

            logger.info(
                f"Escalated validation {validation.id} for manual review: {reason}",
                extra={"candidate_id": validation.candidate_id, "job_id": validation.job_id}
            )

            # TODO: Send escalation notification
            # notification_service.send_escalation_alert(
            #     user_id=escalate_to_user_id or validation.hiring_manager_id,
            #     validation=validation,
            #     reason=reason
            # )

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to escalate validation: {str(e)}")

    async def send_validation_email(
        self,
        validation: HiringManagerValidation,
        is_reminder: bool = False,
        db: Session = None
    ) -> None:
        """
        Send validation form email to hiring manager.

        Args:
            validation: Validation record
            is_reminder: Whether this is a reminder email
            db: Database session

        Note: This is a placeholder for actual email sending.
        The actual implementation would use an email service.
        """
        try:
            if is_reminder:
                validation.email_reminder_sent_at = datetime.utcnow()
                if db:
                    db.commit()
                logger.info(
                    f"Sent reminder email for validation {validation.id}",
                    extra={"hiring_manager_id": validation.hiring_manager_id}
                )
            else:
                logger.info(
                    f"Sent validation email for validation {validation.id}",
                    extra={"hiring_manager_id": validation.hiring_manager_id}
                )

            # TODO: Send actual email
            # email_service.send_hm_validation_email(
            #     to=hm.user_email,
            #     validation=validation,
            #     is_reminder=is_reminder
            # )

        except Exception as e:            logger.error(f"Failed to send email: {str(e)}")

    def get_validation_stats(self, db: Session, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get validation statistics for dashboard.

        Args:
            db: Database session
            job_id: Optional filter by job

        Returns:
            Dict with validation counts and rates
        """
        try:
            query = db.query(HiringManagerValidation)

            if job_id:
                query = query.filter(HiringManagerValidation.job_id == job_id)

            total = query.count()
            pending = query.filter(HiringManagerValidation.status == HMValidationStatus.PENDING).count()
            approved = query.filter(HiringManagerValidation.status == HMValidationStatus.APPROVED).count()
            rejected = query.filter(HiringManagerValidation.status == HMValidationStatus.REJECTED).count()
            maybe = query.filter(HiringManagerValidation.status == HMValidationStatus.MAYBE).count()
            expired = query.filter(HiringManagerValidation.status == HMValidationStatus.EXPIRED).count()

            # Average response time for completed validations
            completed = query.filter(HiringManagerValidation.response_time_hours.isnot(None))
            avg_response_time = db.query(func.avg(HiringManagerValidation.response_time_hours)).filter(
                HiringManagerValidation.response_time_hours.isnot(None)
            ).scalar() or 0

            approval_rate = (approved / total * 100) if total > 0 else 0
            rejection_rate = (rejected / total * 100) if total > 0 else 0

            return {
                "total_validations": total,
                "pending_count": pending,
                "approved_count": approved,
                "rejected_count": rejected,
                "maybe_count": maybe,
                "expired_count": expired,
                "average_response_time_hours": round(float(avg_response_time), 2),
                "approval_rate": round(approval_rate, 2),
                "rejection_rate": round(rejection_rate, 2)
            }

        except Exception as e:            logger.error(f"Failed to get validation stats: {str(e)}")
            return {}
