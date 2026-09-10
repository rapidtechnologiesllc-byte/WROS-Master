"""CYCLE 15: Career Portal Service - Career site backend implementation"""
from typing import Dict, List, Optional
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.candidate import Candidate
from app.models.demand import Demand
from app.models.submission import Submission
from app.models.candidate_job_score import CandidateJobScore

logger = logging.getLogger(__name__)


class CareerPortalService:
    """Career site backend for candidate-facing job browsing and applications"""

    @staticmethod
    def get_open_jobs(
        db: Session,
        location: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict]:
        """Get all open jobs for career site (public browsing)"""
        try:
            query = db.query(Demand).filter(
                Demand.status == "OPEN"
            )

            if location:
                query = query.filter(Demand.job_location.ilike(f"%{location}%"))

            jobs = query.offset(skip).limit(limit).all()

            return [
                {
                    "id": job.id,
                    "title": job.job_title,
                    "description": job.job_description,
                    "location": job.job_location,
                    "experience_required": float(job.min_experience_years),
                    "skills_required": json.loads(job.required_skills) if job.required_skills else [],
                    "employment_type": job.employment_type,
                    "urgency": job.urgency,
                    "status": job.status,
                }
                for job in jobs
            ]
        except Exception as e:
            logger.error(f"Failed to get open jobs: {e}", exc_info=True)
            raise

    @staticmethod
    def get_job_detail(db: Session, job_id: str) -> Optional[Dict]:
        """Get detailed view of a specific job"""
        try:
            job = db.query(Demand).filter(
                and_(Demand.id == job_id, Demand.status == "OPEN")
            ).first()

            if not job:
                return None

            return {
                "id": job.id,
                "title": job.job_title,
                "description": job.job_description,
                "location": job.job_location,
                "experience_required": float(job.min_experience_years),
                "skills_required": json.loads(job.required_skills) if job.required_skills else [],
                "employment_type": job.employment_type,
                "urgency": job.urgency,
                "status": job.status,
                "client_name": job.client_id,  # Should lookup from clients table if needed
                "domain": job.domain,
                "interview_type": job.interview_type_required,
                "headcount": job.headcount,
                "positions_filled": job.positions_filled,
                "required_start_date": job.required_start_date.isoformat() if job.required_start_date else None,
            }
        except Exception as e:
            logger.error(f"Failed to get job detail {job_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def get_existing_application(
        db: Session,
        candidate_id: str,
        job_id: str
    ) -> Optional[Submission]:
        """Check if candidate already applied to this job"""
        try:
            # Get demand to find all submissions for that job
            demand = db.query(Demand).filter(Demand.id == job_id).first()
            if not demand:
                return None

            application = db.query(Submission).filter(
                and_(
                    Submission.candidate_id == candidate_id,
                    Submission.demand_id == job_id
                )
            ).first()

            return application
        except Exception as e:
            logger.error(f"Failed to check existing application: {e}", exc_info=True)
            raise

    @staticmethod
    def create_application(
        db: Session,
        candidate_id: str,
        job_id: str,
        resume_text: Optional[str] = None,
        cover_letter: Optional[str] = None,
        custom_answers: Optional[dict] = None
    ) -> Optional[Dict]:
        """Create new application submission"""
        try:
            # Get demand/job
            demand = db.query(Demand).filter(Demand.id == job_id).first()
            if not demand:
                return None

            # Create submission
            submission = Submission(
                demand_id=job_id,
                client_id=demand.client_id,
                candidate_id=candidate_id,
                status="SUBMITTED",
                submitted_by_user_id=None  # Career site submission, no user context
            )

            db.add(submission)
            db.commit()
            db.refresh(submission)

            return {
                "id": submission.id,
                "job_id": demand.id,
                "job_title": demand.job_title,
                "status": submission.status,
                "applied_date": submission.submitted_at.isoformat() if submission.submitted_at else None,
                "fit_score": None,  # Will be calculated by Thunder
                "last_update": submission.submitted_at.isoformat() if submission.submitted_at else None,
                "next_step": "Awaiting recruiter review",
            }
        except Exception as e:
            logger.error(f"Failed to create application: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def get_candidate_applications(
        db: Session,
        candidate_id: str
    ) -> List[Dict]:
        """Get all applications submitted by candidate"""
        try:
            submissions = db.query(Submission).filter(
                Submission.candidate_id == candidate_id
            ).order_by(Submission.submitted_at.desc()).all()

            result = []
            for sub in submissions:
                # Get demand details
                demand = db.query(Demand).filter(Demand.id == sub.demand_id).first()
                if demand:
                    result.append({
                        "id": sub.id,
                        "job_id": demand.id,
                        "job_title": demand.job_title,
                        "status": sub.status,
                        "applied_date": sub.submitted_at.isoformat() if sub.submitted_at else None,
                        "fit_score": None,  # Would come from candidate_job_scores
                        "last_update": sub.client_response_at.isoformat() if sub.client_response_at else None,
                        "next_step": CareerPortalService._get_next_step(sub.status),
                    })

            return result
        except Exception as e:
            logger.error(f"Failed to get candidate applications: {e}", exc_info=True)
            raise

    @staticmethod
    def get_application_status(
        db: Session,
        application_id: str,
        candidate_id: str
    ) -> Optional[Dict]:
        """Get status of specific application"""
        try:
            submission = db.query(Submission).filter(
                and_(
                    Submission.id == application_id,
                    Submission.candidate_id == candidate_id
                )
            ).first()

            if not submission:
                return None

            # Get demand details
            demand = db.query(Demand).filter(Demand.id == submission.demand_id).first()
            if not demand:
                return None

            return {
                "id": submission.id,
                "job_id": demand.id,
                "job_title": demand.job_title,
                "status": submission.status,
                "applied_date": submission.submitted_at.isoformat() if submission.submitted_at else None,
                "fit_score": None,
                "last_update": submission.client_response_at.isoformat() if submission.client_response_at else None,
                "next_step": CareerPortalService._get_next_step(submission.status),
            }
        except Exception as e:
            logger.error(f"Failed to get application status: {e}", exc_info=True)
            raise

    @staticmethod
    def get_candidate_profile(
        db: Session,
        candidate_id: str
    ) -> Optional[Dict]:
        """Get candidate's public profile"""
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                return None

            # Parse skills if stored as JSON
            skills = []
            if candidate.candidateSkills:
                try:
                    skills = json.loads(candidate.candidateSkills)
                except:
                    skills = candidate.candidateSkills.split(",") if candidate.candidateSkills else []

            return {
                "id": candidate.candidateID,
                "name": f"{candidate.candidateFirstName} {candidate.candidateLastName}".strip(),
                "email": candidate.candidateEmail,
                "phone": candidate.candidateMobile,
                "current_location": candidate.candidateCurrentLocation,
                "current_role": candidate.candidateJobTitle,
                "experience_years": candidate.total_experience_months // 12 if candidate.total_experience_months else None,
                "skills": skills,
            }
        except Exception as e:
            logger.error(f"Failed to get candidate profile: {e}", exc_info=True)
            raise

    @staticmethod
    def analyze_resume_fit(
        db: Session,
        candidate_id: str,
        job_id: str,
        resume_text: str
    ) -> Optional[Dict]:
        """Analyze resume fit against job requirements"""
        try:
            # Get job requirements
            demand = db.query(Demand).filter(Demand.id == job_id).first()
            if not demand:
                return None

            # Get candidate
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()
            if not candidate:
                return None

            # Parse required skills
            required_skills = []
            if demand.required_skills:
                required_skills = json.loads(demand.required_skills)

            # Analyze resume (simplified scoring)
            technical_match = CareerPortalService._score_technical_match(
                resume_text,
                required_skills
            )
            experience_match = CareerPortalService._score_experience_match(
                candidate,
                demand
            )
            skills_match = CareerPortalService._score_skills_match(
                resume_text,
                required_skills
            )

            overall_fit_score = int((technical_match + experience_match + skills_match) / 3)

            gaps = CareerPortalService._identify_gaps(
                candidate,
                demand,
                resume_text
            )

            has_critical_gaps = len([g for g in gaps if "critical" in g.lower()]) > 0

            return {
                "overall_fit_score": overall_fit_score,
                "technical_match": technical_match,
                "experience_match": experience_match,
                "skills_match": skills_match,
                "gaps_identified": gaps,
                "strengths": CareerPortalService._identify_strengths(resume_text, required_skills),
                "has_critical_gaps": has_critical_gaps,
            }
        except Exception as e:
            logger.error(f"Failed to analyze resume: {e}", exc_info=True)
            raise

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @staticmethod
    def _get_next_step(status: str) -> str:
        """Get next step text based on application status"""
        steps = {
            "SUBMITTED": "Awaiting recruiter review",
            "SHORTLISTED": "Your application has been shortlisted",
            "CLIENT_INTERVIEW_REQUESTED": "Interview scheduled - check your email",
            "OFFER_EXTENDED": "Offer received - awaiting your response",
            "PLACED": "Congratulations! You have been placed",
            "REJECTED_BY_CLIENT": "Application not selected",
            "WITHDRAWN": "Application withdrawn",
        }
        return steps.get(status, "In progress")

    @staticmethod
    def _score_technical_match(resume_text: str, required_skills: List[str]) -> int:
        """Score technical skills match (0-100)"""
        if not required_skills:
            return 75  # Default if no specific skills required

        resume_lower = resume_text.lower()
        matches = sum(1 for skill in required_skills if skill.lower() in resume_lower)
        return int((matches / len(required_skills)) * 100) if required_skills else 75

    @staticmethod
    def _score_experience_match(candidate: Candidate, demand: Demand) -> int:
        """Score experience level match (0-100)"""
        if not candidate.total_experience_months:
            return 50  # Unknown experience

        candidate_years = candidate.total_experience_months / 12
        required_years = float(demand.min_experience_years)

        if candidate_years >= required_years:
            return 100
        elif candidate_years >= (required_years * 0.75):
            return 80
        elif candidate_years >= (required_years * 0.5):
            return 60
        else:
            return 40

    @staticmethod
    def _score_skills_match(resume_text: str, required_skills: List[str]) -> int:
        """Score skills match from resume (0-100)"""
        return CareerPortalService._score_technical_match(resume_text, required_skills)

    @staticmethod
    def _identify_gaps(
        candidate: Candidate,
        demand: Demand,
        resume_text: str
    ) -> List[str]:
        """Identify gaps between candidate and job requirements"""
        gaps = []

        # Experience gap
        if candidate.total_experience_months:
            candidate_years = candidate.total_experience_months / 12
            required_years = float(demand.min_experience_years)
            if candidate_years < required_years:
                gap_years = required_years - candidate_years
                gaps.append(f"Missing {gap_years:.1f} years of experience")

        # Skills gaps
        required_skills = json.loads(demand.required_skills) if demand.required_skills else []
        resume_lower = resume_text.lower()
        missing_skills = [s for s in required_skills if s.lower() not in resume_lower]
        if missing_skills:
            gaps.append(f"Missing skills: {', '.join(missing_skills[:3])}")

        return gaps

    @staticmethod
    def _identify_strengths(resume_text: str, required_skills: List[str]) -> List[str]:
        """Identify candidate strengths matching job"""
        strengths = []
        resume_lower = resume_text.lower()

        matching_skills = [s for s in required_skills if s.lower() in resume_lower]
        if matching_skills:
            strengths.append(f"Strong in: {', '.join(matching_skills[:3])}")

        if "leadership" in resume_lower or "led" in resume_lower:
            strengths.append("Leadership experience")

        if "team" in resume_lower:
            strengths.append("Team collaboration")

        return strengths[:3]  # Top 3 strengths
