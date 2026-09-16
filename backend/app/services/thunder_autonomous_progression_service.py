"""
Thunder Autonomous Progression Service - Phase 3B
Manages autonomous candidate progression through hiring stages.
Implements Spartan Phalanx health monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_job_score import CandidateJobScore
from app.models.interview_pipeline import SubmissionInterview
from app.models.offer import OfferLetter
from app.models.employee import Employee
from app.models.candidate_conversation import CandidateConversation
from app.models.conversation_event import ConversationEvent
from app.models.jobs import Jobs
from app.services.skill_matching_service import SkillMatchingService

logger = logging.getLogger(__name__)


class ThunderAutonomousProgression:
    """Autonomous candidate progression through hiring stages (Phase 3B)"""

    PROFILE_COMPLETENESS_THRESHOLD = 0.75  # 75% complete to qualify
    JOB_MATCH_SCORE_THRESHOLD = 60  # 60% match to screen
    INTERVIEW_FEEDBACK_THRESHOLD = 70  # 70% positive to generate offer
    QUALIFICATION_TIMEOUT_HOURS = 24  # Must qualify within 24h of engagement

    @staticmethod
    def attempt_qualify_candidate(db: Session, candidate_id: str) -> Dict:
        """
        Stage 1: ENGAGED → QUALIFYING
        Check if candidate ready to progress from outreach to qualifying.

        Criteria:
        - Conversation exists with ≥2 exchanges
        - Last exchange within 24 hours
        - Profile completeness ≥75%
        """
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                return {"status": "blocked", "reason": "candidate_not_found"}

            # Check conversation history
            conversation = db.query(CandidateConversation).filter(
                CandidateConversation.candidate_id == candidate_id
            ).order_by(CandidateConversation.created_at.desc()).first()

            if not conversation:
                return {"status": "blocked", "reason": "no_conversation_started"}

            # Count exchanges
            exchange_count = db.query(ConversationEvent).filter(
                ConversationEvent.conversation_id == conversation.id
            ).count()

            if exchange_count < 2:
                return {"status": "blocked", "reason": f"only_{exchange_count}_exchanges"}

            # Check recency (last exchange within 24h)
            last_event = db.query(ConversationEvent).filter(
                ConversationEvent.conversation_id == conversation.id
            ).order_by(ConversationEvent.created_at.desc()).first()

            if last_event:
                hours_ago = (datetime.utcnow() - last_event.created_at).total_seconds() / 3600
                if hours_ago > 24:
                    return {"status": "blocked", "reason": "conversation_stale"}

            # Check profile completeness
            completeness = _calculate_profile_completeness(candidate)
            if completeness < ThunderAutonomousProgression.PROFILE_COMPLETENESS_THRESHOLD:
                return {
                    "status": "blocked",
                    "reason": f"profile_incomplete_{int(completeness*100)}%"
                }

            # Update status to QUALIFYING
            candidate.candidate_status = "QUALIFYING"
            db.commit()

            logger.info(f"[Thunder-P3B] Qualified candidate {candidate_id} (completeness={int(completeness*100)}%)")
            return {
                "status": "progressed",
                "profile_completeness": int(completeness * 100)
            }

        except Exception as e:
            logger.error(f"[Thunder-P3B] Qualification failed for {candidate_id}: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def attempt_screen_candidate(db: Session, candidate_id: str) -> Dict:
        """
        Stage 2: QUALIFYING → SCREENED
        Score candidate against open jobs.
        Progress to SCREENED if match ≥60%.
        """
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate or candidate.candidate_status != "QUALIFYING":
                return {"status": "blocked", "reason": "not_qualifying"}

            # Check if already screened
            existing_score = db.query(CandidateJobScore).filter(
                CandidateJobScore.candidate_id == candidate_id
            ).first()

            if existing_score:
                return {"status": "already_screened", "job_id": existing_score.job_id}

            # Get open jobs
            open_jobs = db.query(Jobs).filter(
                Jobs.status == "Open"
            ).all()

            if not open_jobs:
                return {"status": "blocked", "reason": "no_open_jobs"}

            # Score against each job
            top_matches = []
            for job in open_jobs:
                score = SkillMatchingService.score_candidate_for_job(
                    db, candidate_id, job.jobID
                )
                if score >= ThunderAutonomousProgression.JOB_MATCH_SCORE_THRESHOLD:
                    top_matches.append({"job_id": job.jobID, "job_title": job.jobTitle, "score": score})

            if not top_matches:
                return {"status": "no_match", "reason": "no_jobs_above_threshold"}

            # Sort by score and pick best match
            top_matches.sort(key=lambda x: x["score"], reverse=True)
            best_match = top_matches[0]

            # Create job score record
            job_score = CandidateJobScore(
                candidate_id=candidate_id,
                job_id=best_match["job_id"],
                score=best_match["score"],
                scored_at=datetime.utcnow()
            )
            db.add(job_score)

            # Update candidate status
            candidate.candidate_status = "SCREENED"
            db.commit()

            logger.info(f"[Thunder-P3B] Screened {candidate_id} for {best_match['job_title']} (score={best_match['score']}%)")
            return {
                "status": "screened",
                "job_id": best_match["job_id"],
                "job_title": best_match["job_title"],
                "score": best_match["score"],
                "top_3_matches": top_matches[:3]
            }

        except Exception as e:
            logger.error(f"[Thunder-P3B] Screening failed for {candidate_id}: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def attempt_schedule_interview(db: Session, candidate_id: str, job_id: str) -> Dict:
        """
        Stage 3: SCREENED → INTERVIEW
        Find available interviewer and schedule interview.
        """
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate or candidate.candidate_status != "SCREENED":
                return {"status": "blocked", "reason": "not_screened"}

            # Check if interview already scheduled
            existing_interview = db.query(SubmissionInterview).filter(
                SubmissionInterview.candidate_id == candidate_id,
                SubmissionInterview.job_id == job_id
            ).first()

            if existing_interview:
                return {"status": "already_scheduled", "interview_id": existing_interview.id}

            # Find available slot (simplified - next available weekday)
            interview_slot = _find_available_interview_slot(db, job_id)
            if not interview_slot:
                return {"status": "escalated", "reason": "no_interviewer_available"}

            # Create interview record
            interview = SubmissionInterview(
                candidate_id=candidate_id,
                job_id=job_id,
                start_time=interview_slot["start_time"],
                end_time=interview_slot["end_time"],
                panel_id=interview_slot["panel_id"],
                status="Scheduled"
            )
            db.add(interview)

            # Update candidate status
            candidate.candidate_status = "INTERVIEW"
            db.commit()

            logger.info(f"[Thunder-P3B] Scheduled interview for {candidate_id} on {interview_slot['start_time']}")
            return {
                "status": "scheduled",
                "interview_id": interview.id,
                "scheduled_time": interview_slot["start_time"].isoformat()
            }

        except Exception as e:
            logger.error(f"[Thunder-P3B] Interview scheduling failed for {candidate_id}: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def attempt_generate_offer(db: Session, candidate_id: str, job_id: str) -> Dict:
        """
        Stage 4: INTERVIEW → OFFER
        Create offer letter if interview feedback ≥70% positive.
        """
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                return {"status": "blocked", "reason": "candidate_not_found"}

            # Check if offer already generated
            existing_offer = db.query(OfferLetter).filter(
                OfferLetter.candidate_id == candidate_id,
                OfferLetter.job_id == job_id
            ).first()

            if existing_offer:
                return {"status": "already_generated", "offer_id": existing_offer.id}

            # Get interview feedback
            interview = db.query(SubmissionInterview).filter(
                SubmissionInterview.candidate_id == candidate_id,
                SubmissionInterview.job_id == job_id
            ).first()

            if not interview:
                return {"status": "pending_feedback", "reason": "no_interview_found"}

            # Check feedback score
            feedback_score = _calculate_interview_feedback_score(db, interview.id)
            if feedback_score < ThunderAutonomousProgression.INTERVIEW_FEEDBACK_THRESHOLD:
                return {
                    "status": "pending_feedback",
                    "feedback_score": int(feedback_score)
                }

            # Generate offer
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            offer = OfferLetter(
                candidate_id=candidate_id,
                job_id=job_id,
                job_title=job.jobTitle if job else "Unknown",
                salary=job.salary if job else 0,
                offer_status="Pending",
                created_by="Thunder-Autonomous",
                created_at=datetime.utcnow()
            )
            db.add(offer)

            # Update candidate status
            candidate.candidate_status = "OFFER"
            db.commit()

            logger.info(f"[Thunder-P3B] Generated offer for {candidate_id} (feedback={int(feedback_score)}%)")
            return {
                "status": "generated",
                "offer_id": offer.id,
                "feedback_score": int(feedback_score)
            }

        except Exception as e:
            logger.error(f"[Thunder-P3B] Offer generation failed for {candidate_id}: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def attempt_onboard_candidate(db: Session, candidate_id: str) -> Dict:
        """
        Stage 5: OFFER → JOINED
        Convert candidate to Employee and start onboarding.
        """
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                return {"status": "blocked", "reason": "candidate_not_found"}

            # Check if offer accepted
            offer = db.query(OfferLetter).filter(
                OfferLetter.candidate_id == candidate_id,
                OfferLetter.offer_status == "Accepted"
            ).first()

            if not offer:
                return {"status": "pending_acceptance", "reason": "no_accepted_offer"}

            # Check if already employee
            existing_employee = db.query(Employee).filter(
                Employee.candidate_id == candidate_id
            ).first()

            if existing_employee:
                return {"status": "already_onboarded", "employee_id": existing_employee.id}

            # Create employee record
            employee = Employee(
                candidate_id=candidate_id,
                email=candidate.candidateEmail,
                first_name=candidate.candidateFirstName,
                last_name=candidate.candidateLastName,
                start_date=datetime.utcnow().date(),
                status="Active"
            )
            db.add(employee)

            # Update candidate status
            candidate.candidate_status = "JOINED"
            db.commit()

            logger.info(f"[Thunder-P3B] Onboarded {candidate_id} as employee")
            return {
                "status": "onboarded",
                "employee_id": employee.id
            }

        except Exception as e:
            logger.error(f"[Thunder-P3B] Onboarding failed for {candidate_id}: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    @staticmethod
    def calculate_thunder_health(db: Session) -> Dict:
        """
        Calculate Thunder's shield strength and formation integrity.

        Returns: {shield_strength: 0-100, success_rate, latency_ms, quality_score, confidence}
        """
        try:
            # Get progression events from last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_events = db.query(ConversationEvent).filter(
                ConversationEvent.created_at >= one_hour_ago
            ).all()

            if not recent_events:
                return {
                    "shield_strength": 85,  # Default healthy
                    "success_rate": 85,
                    "latency_ms": 3600000,
                    "quality_score": 85,
                    "confidence": 85,
                    "cascade_forecast": {
                        "will_screener_have_candidates": True,
                        "will_interviewer_be_available": True,
                        "will_offer_generation_complete": True,
                        "estimated_throughput_15min": 3
                    }
                }

            # Calculate metrics
            total_events = len(recent_events)
            successful_progressions = len([e for e in recent_events if e.event_type == "PROGRESSED"])
            success_rate = (successful_progressions / total_events * 100) if total_events > 0 else 85

            # Quality score (profile completeness)
            qualified_candidates = db.query(Candidate).filter(
                Candidate.candidate_status.in_(["QUALIFYING", "SCREENED", "INTERVIEW", "OFFER", "JOINED"])
            ).all()

            if qualified_candidates:
                quality_scores = [_calculate_profile_completeness(c) for c in qualified_candidates]
                quality_score = sum(quality_scores) / len(quality_scores) * 100
            else:
                quality_score = 85

            # Calculate shield strength (weighted average)
            shield_strength = (
                (success_rate * 0.40) +
                (quality_score * 0.30) +
                (85 * 0.20) +  # latency compliance (simplified)
                (85 * 0.10)    # confidence
            )

            return {
                "shield_strength": int(shield_strength),
                "success_rate": int(success_rate),
                "latency_ms": 3600000,
                "quality_score": int(quality_score),
                "confidence": 85,
                "cascade_forecast": {
                    "will_screener_have_candidates": True,
                    "will_interviewer_be_available": True,
                    "will_offer_generation_complete": success_rate > 70,
                    "estimated_throughput_15min": int(successful_progressions / 12)  # Per 5-min cycle
                }
            }

        except Exception as e:
            logger.error(f"[Thunder-P3B] Health calculation failed: {e}", exc_info=True)
            return {"shield_strength": 50, "error": str(e)}


# --- Helper Functions ---

def _calculate_profile_completeness(candidate: Candidate) -> float:
    """
    Calculate profile completeness as % of required fields filled.
    Required fields: firstName, lastName, email, phone, location
    """
    required_fields = [
        candidate.candidateFirstName,
        candidate.candidateLastName,
        candidate.candidateEmail,
        candidate.phone,
        candidate.candidateCurrentLocation
    ]
    filled = sum(1 for field in required_fields if field)
    return filled / len(required_fields)


def _find_available_interview_slot(db: Session, job_id: str) -> Optional[Dict]:
    """
    Find next available interview slot for a job.
    Returns: {start_time, end_time, panel_id}
    """
    # Simplified: assume next weekday, 10 AM, 1-hour duration
    today = datetime.utcnow()
    next_slot = today.replace(hour=10, minute=0, second=0, microsecond=0)

    # Skip to next weekday if today is weekend
    while next_slot.weekday() > 4:
        next_slot += timedelta(days=1)

    # If past 10 AM today, move to tomorrow
    if next_slot < datetime.utcnow():
        next_slot = next_slot.replace(day=next_slot.day + 1)

    return {
        "start_time": next_slot,
        "end_time": next_slot + timedelta(hours=1),
        "panel_id": 1  # Simplified: use default panel
    }


def _calculate_interview_feedback_score(db: Session, interview_id: int) -> float:
    """
    Calculate interview feedback score (0-100).
    Simplified: average of feedback recommendations.
    """
    from app.models.interview import InterviewFeedback

    feedbacks = db.query(InterviewFeedback).filter(
        InterviewFeedback.interview_id == interview_id
    ).all()

    if not feedbacks:
        return 0

    # Score: "Hire" = 100, "Must Hire" = 100, "Average" = 70, "Not sure" = 50, "No Hire" = 0
    score_map = {
        "Hire": 85,
        "Must Hire": 100,
        "Average": 70,
        "Not sure": 50,
        "No Hire": 0
    }

    scores = [score_map.get(f.recommendation, 50) for f in feedbacks]
    return sum(scores) / len(scores) if scores else 0
