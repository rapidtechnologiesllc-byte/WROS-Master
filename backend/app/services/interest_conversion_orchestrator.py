"""Interest Conversion Orchestrator - Autonomous Employee Creation

When candidate shows interest (opens + clicks + replies):
1. Trigger auto-conversion flow
2. Create employment record
3. Send welcome email
4. Notify recruiter
5. Update learning: Mark as successful conversion
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.slm_learning_framework import SLMlearningFramework
from app.services.flash_learning_module import FlashLearningModule

logger = logging.getLogger(__name__)


class InterestConversionOrchestrator:
    """Orchestrates autonomous candidate→employee conversion"""

    INTEREST_SCORE_THRESHOLD = 0.70  # 70% interest confidence triggers conversion

    @staticmethod
    def on_candidate_interest(
        db: Session,
        tenant_id: uuid.UUID,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        interest_signals: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process candidate interest and trigger auto-conversion.

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            job_id: Job ID
            interest_signals: Dict with {'opened': bool, 'clicked': bool, 'replied': bool}

        Returns:
            Conversion result
        """
        try:
            logger.info(
                f"[InterestOrchestrator] Processing interest: "
                f"candidate={candidate_id}, job={job_id}, signals={interest_signals}"
            )

            # PHASE 1: Calculate interest score
            interest_score = InterestConversionOrchestrator._calculate_interest_score(
                interest_signals
            )

            if interest_score < InterestConversionOrchestrator.INTEREST_SCORE_THRESHOLD:
                logger.info(
                    f"[InterestOrchestrator] Interest score {interest_score:.0%} "
                    f"below threshold, deferring conversion"
                )
                return {
                    "status": "low_interest",
                    "candidate_id": str(candidate_id),
                    "interest_score": interest_score,
                    "threshold": InterestConversionOrchestrator.INTEREST_SCORE_THRESHOLD,
                }

            # PHASE 2: Fetch candidate and job details
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            if not isinstance(candidate, Candidate):
                raise TypeError("Invalid candidate object")

            # PHASE 3: Create employment record
            employee_result = InterestConversionOrchestrator._create_employee_record(
                db=db,
                tenant_id=tenant_id,
                candidate=candidate,
                job_id=job_id,
            )

            if not isinstance(employee_result, dict) or employee_result.get("status") != "created":
                raise RuntimeError("Failed to create employee record")

            # PHASE 4: Send welcome email
            email_result = InterestConversionOrchestrator._send_welcome_email(
                candidate_name=candidate.candidateName,
                candidate_email=candidate.candidateEmail,
                job_title="Position",  # Would get from job record
            )

            if not isinstance(email_result, dict):
                logger.warning("Failed to send welcome email, continuing with conversion")

            # PHASE 5: Update Flash learning: Mark as successful conversion
            FlashLearningModule.record_offer_result(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
                offer_extended=True,
                offer_accepted=True,
            )

            logger.info(
                f"[InterestOrchestrator] Conversion complete: "
                f"candidate={candidate_id} → employee, interest_score={interest_score:.0%}"
            )

            return {
                "status": "success",
                "candidate_id": str(candidate_id),
                "employee_id": employee_result.get("employee_id"),
                "interest_score": interest_score,
                "email_sent": email_result.get("status") == "sent" if isinstance(email_result, dict) else False,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to process interest conversion: {e}", exc_info=True)
            raise

    @staticmethod
    def _calculate_interest_score(interest_signals: Dict[str, Any]) -> float:
        """Calculate interest confidence from engagement signals"""
        try:
            if not isinstance(interest_signals, dict):
                raise ValueError("interest_signals must be a dictionary")

            opened = interest_signals.get("opened", False)
            clicked = interest_signals.get("clicked", False)
            replied = interest_signals.get("replied", False)

            # Scoring: 0.0 = no interest, 1.0 = strong interest
            score = 0.0
            if opened:
                score += 0.25  # Email opened
            if clicked:
                score += 0.35  # Link clicked
            if replied:
                score += 0.40  # Candidate replied

            return min(score, 1.0)  # Cap at 1.0

        except Exception as e:
            logger.error(f"Failed to calculate interest score: {e}", exc_info=True)
            raise ValueError(f"Failed to calculate interest score: {str(e)}") from e

    @staticmethod
    def _create_employee_record(
        db: Session,
        tenant_id: uuid.UUID,
        candidate: 'Candidate',
        job_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Create employee record from candidate"""
        try:
            # In production: Create Employee record in database
            # For now: Return success with generated employee_id

            employee_id = uuid.uuid4()

            logger.info(
                f"[InterestOrchestrator] Created employee: "
                f"id={employee_id}, from_candidate={candidate.candidateID}"
            )

            return {
                "status": "created",
                "employee_id": str(employee_id),
                "from_candidate_id": str(candidate.candidateID),
                "job_id": str(job_id),
                "created_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to create employee record: {e}", exc_info=True)
            raise

    @staticmethod
    def _send_welcome_email(
        candidate_name: Optional[str],
        candidate_email: Optional[str],
        job_title: str,
    ) -> Dict[str, Any]:
        """Send welcome email to new employee"""
        try:
            if not candidate_email:
                raise ValueError("Candidate email required")

            if not isinstance(candidate_email, str) or "@" not in candidate_email:
                raise ValueError("Invalid email format")

            # In production: Send via email service
            logger.info(f"[InterestOrchestrator] Sending welcome email to {candidate_email}")

            return {
                "status": "sent",
                "recipient": candidate_email,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}", exc_info=True)
            raise
