"""
Thunder Pre-Screening Service
Manages candidate intake sessions, form persistence, resume parsing, and AI Recruiter handoff
"""

import logging
from datetime import datetime
from uuid import uuid4
from typing import Optional, Dict, List, Any
import json

from app.models import (
    ThunderSession,
    ThunderSessionStatus,
    Candidate,
    Jobs,
)
from app.core.storage import upload_to_s3
from app.services.resume_parser_agent import ResumeParsedAgent

logger = logging.getLogger(__name__)

THUNDER_QUESTIONS = {
    "Q1": {
        "text": "What is your email address?",
        "type": "text",
        "required": True,
        "conditional": False,
    },
    "Q2": {
        "text": "What is your current job title?",
        "type": "text",
        "required": True,
        "conditional": False,
    },
    "Q3": {
        "text": "How many years of experience do you have?",
        "type": "number",
        "required": True,
        "conditional": False,
    },
    "Q4": {
        "text": "What is your current company?",
        "type": "text",
        "required": False,
        "conditional": False,
    },
    "Q5": {
        "text": "Do you have a resume on file? (We have {resume_date})",
        "type": "yes_no",
        "required": True,
        "conditional": False,
    },
    "Q6": {
        "text": "Your current location is listed as {location}. Is this still accurate?",
        "type": "yes_no",
        "required": True,
        "conditional": False,
    },
    "Q7": {
        "text": "If location changed, please select your current location:",
        "type": "dropdown",
        "required": False,
        "conditional": True,
        "condition": "Q6 == 'no'",
        "options": "LOCATION_DROPDOWN",  # Reuse existing location dropdown
    },
    "Q8": {
        "text": "Are you authorized to work in {country}?",
        "type": "yes_no",
        "required": True,
        "conditional": True,
        "condition": "job_location == 'US' or job_location == 'US_REMOTE'",
    },
    "Q9": {
        "text": "Do you require visa sponsorship?",
        "type": "yes_no",
        "required": True,
        "conditional": True,
        "condition": "Q8 == 'no'",
    },
    "Q10": {
        "text": "Please upload your updated resume:",
        "type": "file_upload",
        "required": True,
        "conditional": True,
        "condition": "Q5 == 'no'",
    },
    "Q11": {
        "text": "I agree to be contacted about opportunities:",
        "type": "yes_no",
        "required": True,
        "conditional": False,
    },
    "Q12": {
        "text": "I agree to the terms and conditions:",
        "type": "yes_no",
        "required": True,
        "conditional": False,
    },
}


class ThunderService:
    """Service for managing Thunder pre-screening flow"""

    async def create_session(
        self,
        candidate_email: str,
        device_type: str,
        utm_source: str,
        db,
    ) -> ThunderSession:
        """Create new Thunder session or fetch existing candidate data"""
        try:
            # Check if candidate exists with resume on file
            candidate = None
            resume_on_file = False
            candidate_data = {}

            # Find candidate by email (external candidates table might exist)
            session = ThunderSession(
                id=str(uuid4()),
                candidate_email=candidate_email,
                status=ThunderSessionStatus.STARTED,
                created_at=datetime.utcnow(),
                started_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
                last_question_reached="Q1",
                questions_answered=0,
                completion_percentage=0,
                form_state={},
                form_responses={},
                resume_parsed=resume_on_file,
                screening_responses={
                    "work_auth": None,
                    "agreements": {"terms": False, "contact": False},
                },
            )

            db.add(session)
            db.commit()

            return session

        except Exception as e:
            logger.error(f"Error creating Thunder session: {str(e)}")
            raise

    async def get_session(self, session_id: str, db) -> Optional[ThunderSession]:
        """Fetch session by ID"""
        return db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

    async def save_response(
        self,
        session: ThunderSession,
        question: str,
        response: Any,
        time_taken_seconds: Optional[int],
        db,
    ) -> Dict:
        """Save question response and update session state"""
        try:
            # Store response
            if not session.form_responses:
                session.form_responses = {}

            session.form_responses[question] = {
                "response": response,
                "time_taken_seconds": time_taken_seconds,
                "answered_at": datetime.utcnow().isoformat(),
            }

            # Update progress
            session.questions_answered = len(session.form_responses)
            session.last_question_reached = question
            session.completion_percentage = int((session.questions_answered / 12) * 100)
            session.last_activity_at = datetime.utcnow()
            session.status = ThunderSessionStatus.IN_PROGRESS

            db.commit()

            return {"status": "ok", "question": question}

        except Exception as e:
            logger.error(f"Error saving response: {str(e)}")
            raise

    async def get_next_question(
        self,
        session: ThunderSession,
        current_question: str,
        db,
    ) -> Optional[str]:
        """
        Determine next question based on conditional logic.
        Examples:
        - Q7 only if Q6 answer is "no"
        - Q8 (work auth) only if job location is US
        """
        try:
            q_map = {
                "Q1": "Q2",
                "Q2": "Q3",
                "Q3": "Q4",
                "Q4": "Q5",
                "Q5": "Q6",
                "Q6": self._evaluate_conditional("Q7", session),
                "Q7": self._evaluate_conditional("Q8", session),
                "Q8": self._evaluate_conditional("Q9", session),
                "Q9": self._evaluate_conditional("Q10", session),
                "Q10": "Q11",
                "Q11": "Q12",
                "Q12": None,  # End of flow
            }

            return q_map.get(current_question)

        except Exception as e:
            logger.error(f"Error determining next question: {str(e)}")
            return None

    def _evaluate_conditional(self, question: str, session: ThunderSession) -> Optional[str]:
        """Evaluate conditional logic for question visibility"""
        q_def = THUNDER_QUESTIONS.get(question)

        if not q_def or not q_def.get("conditional"):
            return question

        condition = q_def.get("condition", "")

        # Parse condition (simple version)
        if "Q6 == 'no'" in condition:
            if session.form_responses.get("Q6", {}).get("response") == "no":
                return question
            else:
                # Skip Q7 and try next
                return self._evaluate_conditional("Q8", session)

        if "Q8 == 'no'" in condition:
            if session.form_responses.get("Q8", {}).get("response") == "no":
                return question
            else:
                return self._evaluate_conditional("Q10", session)

        if "Q5 == 'no'" in condition:
            if session.form_responses.get("Q5", {}).get("response") == "no":
                return question
            else:
                # Resume already on file, skip upload
                return self._evaluate_conditional("Q11", session)

        return question

    async def upload_and_parse_resume(
        self,
        session: ThunderSession,
        file,
        db,
    ) -> tuple[str, Dict]:
        """Upload resume to S3 and trigger parsing"""
        try:
            # Upload to S3
            resume_url = await upload_to_s3(file, f"resumes/{session.candidate_email}/")

            # Trigger resume parser agent (async, stores in batch retry if fails)
            parser = ResumeParsedAgent()
            parsed_data = await parser.parse_resume(resume_url)

            return resume_url, parsed_data

        except Exception as e:
            logger.error(f"Error uploading/parsing resume: {str(e)}")
            raise

    async def finalize_candidate(
        self,
        session: ThunderSession,
        db,
    ) -> Candidate:
        """Create or update candidate record from Thunder session"""
        try:
            # Check if candidate already exists
            candidate = db.query(Candidate).filter(
                Candidate.candidateEmail == session.candidate_email
            ).first()

            if not candidate:
                # Create new candidate
                candidate = Candidate(
                    candidateID=f"cand_{uuid4().hex[:8]}",
                    candidateName=session.candidate_data.get("name", ""),
                    candidateEmail=session.candidate_email,
                    candidatePhone=session.candidate_data.get("phone", ""),
                    currentLocation=session.candidate_data.get("location", ""),
                    currentCompany=session.candidate_data.get("company", ""),
                    currentJobTitle=session.candidate_data.get("title", ""),
                    candidateStatus="Applied",
                    resumeURL=session.resume_url,
                    createdAt=datetime.utcnow(),
                )
                db.add(candidate)
            else:
                # Update existing candidate
                candidate.resumeURL = session.resume_url or candidate.resumeURL
                candidate.currentLocation = session.candidate_data.get("location") or candidate.currentLocation

            db.commit()

            return candidate

        except Exception as e:
            logger.error(f"Error finalizing candidate: {str(e)}")
            raise

    def get_session_progress(self, session: ThunderSession) -> Dict:
        """Get detailed session progress for UI"""
        return {
            "session_id": session.id,
            "status": session.status.value,
            "completion_percentage": session.completion_percentage,
            "last_question_reached": session.last_question_reached,
            "questions_answered": session.questions_answered,
            "time_elapsed_minutes": (
                (datetime.utcnow() - session.created_at).total_seconds() / 60
                if session.created_at
                else 0
            ),
            "resume_uploaded": session.resume_url is not None,
            "can_resume": session.status in [
                ThunderSessionStatus.PAUSED,
                ThunderSessionStatus.IN_PROGRESS,
            ],
        }
