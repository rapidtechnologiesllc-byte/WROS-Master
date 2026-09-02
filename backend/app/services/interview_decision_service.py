"""
S-311 — HRMS-0311: Interview Decision Engine (Phase 3)
Coordinates hiring manager feedback → panel decision → offer generation pathway.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)
from app.models.user import Interview, Jobs, Users
from app.models.interview import InterviewFeedback, InterviewDecisionLog, InterviewPanelDecision
from app.models.offer import Offer, OfferStatus
from app.models.candidate import Candidate


class InterviewDecisionService:
    """Manages the workflow from interview completion to offer decision."""

    def get_interview_status(self, db: Session, interview_id: int, tenant_id: int) -> Dict[str, Any]:
        """Get full interview status with all feedback collected."""
        try:
            if not interview_id:
                raise ValueError("interview_id is required")

            # Query interview
            interview = db.query(Interview).filter(
                Interview.id == interview_id
            ).first()

            if not interview:
                raise ValueError(f"Interview {interview_id} not found")

            # Get all feedback from panel
            feedbacks = db.query(InterviewFeedback).filter(
                InterviewFeedback.interview_id == interview_id
            ).all()

            if not feedbacks:
                feedbacks = []

            feedback_submitted = len(feedbacks)
            all_feedback_details = []

            for feedback in feedbacks:
                all_feedback_details.append({
                    "feedback_id": feedback.id,
                    "interviewer_id": feedback.interviewer_id,
                    "technical_score": feedback.technical_score,
                    "communication_score": feedback.communication_score,
                    "problem_solving_score": feedback.problem_solving_score,
                    "culture_fit_score": feedback.culture_fit_score,
                    "submitted_at": feedback.submitted_at.isoformat() if feedback.submitted_at else None
                })

            return {
                "interview_id": interview_id,
                "candidate_id": interview.candidate_id,
                "status": interview.status,
                "start_time": interview.start_time.isoformat() if interview.start_time else None,
                "end_time": interview.end_time.isoformat() if interview.end_time else None,
                "feedback_received": feedback_submitted,
                "feedbacks": all_feedback_details
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to get interview status: {str(e)}")

    def calculate_panel_decision(self, db: Session, interview_id: int, tenant_id: int) -> Dict[str, Any]:
        """Aggregate panel feedback into hiring decision."""
        try:
            feedbacks = db.query(InterviewFeedback).filter(
                InterviewFeedback.interview_id == interview_id
            ).all()

            if not feedbacks:
                return {
                    "decision": "PENDING",
                    "reason": "No feedback submitted",
                    "voting": {
                        "strong_yes": 0,
                        "yes": 0,
                        "no": 0,
                        "strong_no": 0,
                        "abstain": 0,
                        "total_panelists": 0
                    }
                }

            # Count recommendations
            recommendations = {
                "STRONG_YES": 0,
                "YES": 0,
                "NO": 0,
                "STRONG_NO": 0,
                "ABSTAIN": 0
            }

            for feedback in feedbacks:
                rec = getattr(feedback, 'recommendation', 'ABSTAIN')
                if rec in recommendations:
                    recommendations[rec] += 1

            strong_yes = recommendations.get("STRONG_YES", 0)
            yes = recommendations.get("YES", 0)
            no = recommendations.get("NO", 0)
            strong_no = recommendations.get("STRONG_NO", 0)
            abstain = recommendations.get("ABSTAIN", 0)
            total = len(feedbacks)

            # Decision logic
            if strong_no > 0 or (no + strong_no) > total / 2:
                decision = "REJECTED"
                reason = "Panel consensus: candidate not suitable"
            elif strong_yes + yes == total:
                decision = "APPROVED"
                reason = "Panel consensus: strong candidate"
            elif (strong_yes + yes) > total / 2:
                decision = "APPROVED"
                reason = "Panel majority: move to offer"
            elif (strong_yes + yes) == (no + strong_no):
                decision = "PENDING_REVIEW"
                reason = "Tied vote - requires hiring manager review"
            else:
                decision = "PENDING_REVIEW"
                reason = "Mixed feedback - requires hiring manager review"

            # Calculate average scores
            avg_technical = None
            avg_communication = None
            avg_problem_solving = None
            avg_culture_fit = None

            technical_scores = [f.technical_score for f in feedbacks if f.technical_score]
            if technical_scores:
                avg_technical = sum(technical_scores) / len(technical_scores)

            communication_scores = [f.communication_score for f in feedbacks if f.communication_score]
            if communication_scores:
                avg_communication = sum(communication_scores) / len(communication_scores)

            problem_solving_scores = [f.problem_solving_score for f in feedbacks if f.problem_solving_score]
            if problem_solving_scores:
                avg_problem_solving = sum(problem_solving_scores) / len(problem_solving_scores)

            culture_fit_scores = [f.culture_fit_score for f in feedbacks if f.culture_fit_score]
            if culture_fit_scores:
                avg_culture_fit = sum(culture_fit_scores) / len(culture_fit_scores)

            return {
                "decision": decision,
                "reason": reason,
                "voting": {
                    "strong_yes": strong_yes,
                    "yes": yes,
                    "no": no,
                    "strong_no": strong_no,
                    "abstain": abstain,
                    "total_panelists": total
                },
                "average_scores": {
                    "technical": round(avg_technical, 2) if avg_technical else None,
                    "communication": round(avg_communication, 2) if avg_communication else None,
                    "problem_solving": round(avg_problem_solving, 2) if avg_problem_solving else None,
                    "culture_fit": round(avg_culture_fit, 2) if avg_culture_fit else None
                }
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to calculate panel decision: {str(e)}")

    def move_to_offer(
        self,
        db: Session,
        interview_id: int,
        candidate_id: str,
        job_id: str,
        tenant_id: int,
        approved_salary_usd_cents: int,
        position_title: str,
        start_date: datetime,
        created_by_user_id: str
    ) -> Dict[str, Any]:
        """Create offer after interview approval."""
        try:
            # Verify interview exists
            interview = db.query(Interview).filter(
                Interview.id == interview_id
            ).first()

            if not interview:
                return {
                    "status": "error",
                    "message": "Interview not found",
                    "offer_id": None
                }

            # Check decision
            decision = self.calculate_panel_decision(db, interview_id, tenant_id)
            if decision["decision"] not in ["APPROVED"]:
                return {
                    "status": "error",
                    "message": f"Interview decision is {decision['decision']}, not approved for offer",
                    "offer_id": None
                }

            # Create offer
            offer_id = str(uuid.uuid4())
            offer = Offer(
                id=offer_id,
                candidate_id=candidate_id,
                job_id=job_id,
                tenant_id=tenant_id,
                status=OfferStatus.DRAFT,
                base_salary_usd_cents=approved_salary_usd_cents,
                position_title=position_title,
                expected_start_date=start_date.date() if isinstance(start_date, datetime) else start_date,
                created_by_user_id=created_by_user_id
            )

            db.add(offer)

            # Create decision log
            decision_log_id = str(uuid.uuid4())
            decision_log = InterviewDecisionLog(
                id=decision_log_id,
                interview_id=interview_id,
                candidate_id=candidate_id,
                tenant_id=tenant_id,
                outcome="APPROVED",
                strong_yes_count=decision["voting"].get("strong_yes", 0),
                yes_count=decision["voting"].get("yes", 0),
                no_count=decision["voting"].get("no", 0),
                strong_no_count=decision["voting"].get("strong_no", 0),
                abstain_count=decision["voting"].get("abstain", 0),
                total_panelists=decision["voting"].get("total_panelists", 0),
                decided_by_user_id=created_by_user_id,
                decided_at=datetime.utcnow()
            )
            db.add(decision_log)

            db.commit()

            return {
                "status": "success",
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "position_title": position_title,
                "salary_usd_cents": approved_salary_usd_cents,
                "start_date": start_date.isoformat() if isinstance(start_date, datetime) else start_date.isoformat()
            }
        except Exception as e:            logger.error(f"Failed to create offer: {str(e)}", exc_info=True)
            db.rollback()
            raise ValueError(f"Failed to create offer: {str(e)}")

    def reject_candidate(
        self,
        db: Session,
        interview_id: int,
        tenant_id: int,
        rejection_reason: str,
        rejected_by_user_id: str
    ) -> Dict[str, Any]:
        """Mark candidate as rejected after interview."""
        try:
            interview = db.query(Interview).filter(
                Interview.id == interview_id
            ).first()

            if not interview:
                return {
                    "status": "error",
                    "message": "Interview not found"
                }

            interview.status = "REJECTED"
            db.add(interview)

            # Create decision log
            decision_log_id = str(uuid.uuid4())
            decision_log = InterviewDecisionLog(
                id=decision_log_id,
                interview_id=interview_id,
                candidate_id=interview.candidate_id,
                tenant_id=tenant_id,
                outcome="REJECTED",
                decision_summary=rejection_reason,
                decided_by_user_id=rejected_by_user_id,
                decided_at=datetime.utcnow()
            )
            db.add(decision_log)

            db.commit()

            return {
                "status": "success",
                "interview_id": interview_id,
                "candidate_id": interview.candidate_id,
                "rejection_reason": rejection_reason,
                "rejected_at": datetime.utcnow().isoformat()
            }
        except Exception as e:            logger.error(f"Failed to reject candidate: {str(e)}", exc_info=True)
            db.rollback()
            raise ValueError(f"Failed to reject candidate: {str(e)}")
