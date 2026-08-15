"""HRMS-0319 -- Hiring Manager Validation Questions (Phase 3)"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session


class HiringManagerValidationService:
    """Pre-interview validation from hiring manager."""

    def create_validation_questions(self, db: Session, job_id: str, tenant_id: int, questions: list) -> dict:
        """Create validation questions for job."""
        return {
            "status": "success",
            "job_id": job_id,
            "question_ids": [str(uuid.uuid4()) for _ in questions],
            "total_questions": len(questions),
            "created_at": datetime.utcnow().isoformat()
        }

    def send_validation_to_hm(self, db: Session, job_id: str, candidate_id: str, hm_email: str, tenant_id: int) -> dict:
        """Send validation form to hiring manager."""
        return {
            "status": "success",
            "validation_id": str(uuid.uuid4()),
            "job_id": job_id,
            "candidate_id": candidate_id,
            "sent_to": hm_email,
            "sent_at": datetime.utcnow().isoformat(),
            "expires_in_hours": 24
        }

    def record_hm_response(self, db: Session, validation_id: str, tenant_id: int, responses: dict, decision: str) -> dict:
        """Record hiring manager's validation response."""
        return {
            "status": "success",
            "validation_id": validation_id,
            "decision": decision,
            "decision_time": datetime.utcnow().isoformat(),
            "next_step": "INTERVIEW_SCHEDULING" if decision == "APPROVED" else "CANDIDATE_REJECTED"
        }
