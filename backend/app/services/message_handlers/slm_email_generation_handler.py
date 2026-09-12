"""
SLM Email Generation Handler - Generates personalized initial emails for candidates

This handler is called when a candidate is first created. It:
1. Fetches candidate profile and open roles
2. Uses Gemini LLM to generate personalized welcome message matching candidate to roles
3. Updates message payload with generated content
4. Changes status to READY_TO_SEND for Thunder handler to execute

Implements async two-phase processing:
- Phase 1: Candidate created → Queue with WAITING_FOR_SLM status
- Phase 2: SLM handler → Generate email → Update to READY_TO_SEND
- Phase 3: Thunder handler → Send the generated email
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.thunder_service import build_candidate_context, generate_thunder_reply, ThunderReplyGenerationFailed
from app.core.logging import logger

logger = logging.getLogger(__name__)


class SLMEmailGenerationHandler:
    """Generates personalized candidate welcome emails using SLM + Gemini"""

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process message: Generate personalized email content for candidate.

        Input message.payload:
        {
            'candidate_id': 'CAN-...',
            'recipient_email': '...',
            'first_name': '...'
        }

        Output:
        - Updates message.payload with 'slm_generated_email_body'
        - Changes message.status from WAITING_FOR_SLM to READY_TO_SEND
        - Returns status dict

        If SLM fails, returns generic fallback message with status='slm_failed_using_generic'
        """
        candidate_id = message.payload.get('candidate_id')

        try:
            logger.info(f"[SLMEmailGeneration] Generating personalized email for candidate {candidate_id}")

            # Fetch candidate from database
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found in database")

            # Step 1: Build candidate context (profile + open jobs)
            try:
                context = build_candidate_context(db, candidate)
                logger.debug(
                    f"[SLMEmailGeneration] Context built for {candidate_id}: "
                    f"{len(context.get('open_jobs', []))} open roles, "
                    f"skills={context.get('candidate_profile', {}).get('skills', 'none')}"
                )
            except Exception as context_err:
                logger.error(f"[SLMEmailGeneration] Failed to build context: {context_err}")
                raise

            # Step 2: Generate personalized email using Gemini
            try:
                # Initial message template that SLM will personalize based on context
                initial_prompt = (
                    f"Generate a warm, personalized welcome message for a candidate named {candidate.candidateFirstName}. "
                    f"The message should reference their background and relevant open positions they might be a fit for. "
                    f"Keep it conversational and under 200 words."
                )

                email_body = generate_thunder_reply(db, candidate, initial_prompt, channel="whatsapp")

                logger.info(
                    f"[SLMEmailGeneration] Successfully generated email for {candidate_id} "
                    f"({len(email_body)} chars)"
                )

            except ThunderReplyGenerationFailed as gen_err:
                logger.warning(
                    f"[SLMEmailGeneration] Gemini failed for {candidate_id}: {gen_err}. "
                    f"Using generic fallback message."
                )
                # Fallback: Use generic welcome message
                email_body = _get_generic_welcome_message(candidate)
                status = "slm_failed_using_generic"

            # Step 3: Update message payload with generated email
            message.payload['slm_generated_email_body'] = email_body
            message.payload['slm_generated_at'] = __import__('datetime').datetime.utcnow().isoformat()
            message.payload['slm_status'] = 'success'

            # Step 4: Change status to READY_TO_SEND so Thunder handler can execute
            message.status = 'READY_TO_SEND'
            db.add(message)
            db.commit()

            logger.info(f"[SLMEmailGeneration] Message {message.id} ready to send: READY_TO_SEND")

            return {
                "status": "email_content_generated",
                "candidate_id": candidate_id,
                "email_length": len(email_body),
                "slm_status": status if 'status' in locals() else 'success'
            }

        except Exception as e:
            logger.error(f"[SLMEmailGeneration] Failed to generate email for {candidate_id}: {e}", exc_info=True)

            # Even on failure, use generic fallback and mark as READY_TO_SEND
            try:
                candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                if candidate:
                    generic_email = _get_generic_welcome_message(candidate)
                    message.payload['slm_generated_email_body'] = generic_email
                    message.payload['slm_error'] = str(e)
                    message.payload['slm_status'] = 'failed_with_fallback'
                    message.status = 'READY_TO_SEND'
                    db.add(message)
                    db.commit()
                    logger.info(f"[SLMEmailGeneration] Using fallback for {candidate_id}")
            except Exception as fallback_err:
                logger.error(f"[SLMEmailGeneration] Fallback also failed: {fallback_err}")

            # Re-raise so queue processor can retry
            raise


def _get_generic_welcome_message(candidate: Candidate) -> str:
    """Generate a generic welcome message when SLM fails"""
    first_name = candidate.candidateFirstName or "there"
    return (
        f"Hi {first_name},\n\n"
        f"Thanks so much for your interest in BlitzenX! We're excited to learn more about you and explore "
        f"how your skills could be a great fit for our open roles.\n\n"
        f"We'll be reaching out soon with more details and next steps. In the meantime, feel free to tell us "
        f"more about what you're looking for in your next opportunity.\n\n"
        f"Looking forward to connecting!\n\n"
        f"Best regards,\n"
        f"The BlitzenX Recruitment Team"
    )
