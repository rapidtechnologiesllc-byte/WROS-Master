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
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class SLMEmailGenerationHandler:
    """Generates personalized candidate welcome emails using SLM + Gemini"""

    @staticmethod
    @time_bound(timeout_seconds=15)
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

            # Spawn SLM agent to learn candidate facts (background, non-blocking)
            try:
                agent_result = SLMEmailGenerationHandler._spawn_slm_agent_for_candidate(candidate, db)
                logger.info(f"[SLMEmailGeneration] SLM agent spawned: {agent_result}")
            except Exception as agent_err:
                logger.warning(f"[SLMEmailGeneration] Failed to spawn SLM agent (non-blocking): {agent_err}")

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


    @staticmethod
    def _spawn_slm_agent_for_candidate(candidate: Candidate, db: Session) -> Dict[str, Any]:
        """Spawn SLM agent to learn and extract candidate facts (background thread, non-blocking)"""
        from app.services.candidate_memory_service import upsert_fact
        import threading

        candidate_id = candidate.candidateID

        def extract_facts():
            """Background task to extract and store facts"""
            try:
                logger.info(f"[SLMAgent] Spawning fact extraction for {candidate_id}")

                # FACT 1: Expected salary
                if candidate.candidateExpectedSalary:
                    try:
                        expected_salary = str(candidate.candidateExpectedSalary).strip()
                        if expected_salary and expected_salary != 'None':
                            upsert_fact(
                                db=db,
                                candidate_id=candidate_id,
                                tenant_id=candidate.tenant_id or 1,
                                fact_category='SALARY',
                                fact_key='expected_salary',
                                fact_value=expected_salary,
                                confidence=0.85
                            )
                            logger.info(f"[SLMAgent] Stored salary fact for {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[SLMAgent] Failed to store salary: {e}")

                # FACT 2: Current location
                if candidate.candidateCurrentLocation:
                    try:
                        location = candidate.candidateCurrentLocation.strip()
                        if location:
                            upsert_fact(
                                db=db,
                                candidate_id=candidate_id,
                                tenant_id=candidate.tenant_id or 1,
                                fact_category='PREFERENCE',
                                fact_key='location_preference',
                                fact_value=location,
                                confidence=0.90
                            )
                            logger.info(f"[SLMAgent] Stored location fact for {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[SLMAgent] Failed to store location: {e}")

                # FACT 3: Skills
                if candidate.candidateSkills:
                    try:
                        skills = candidate.candidateSkills
                        if isinstance(skills, list):
                            skills_str = ', '.join(str(s) for s in skills)
                        else:
                            skills_str = str(skills)

                        if skills_str.strip():
                            upsert_fact(
                                db=db,
                                candidate_id=candidate_id,
                                tenant_id=candidate.tenant_id or 1,
                                fact_category='SKILL',
                                fact_key='primary_skills',
                                fact_value=skills_str,
                                confidence=0.88
                            )
                            logger.info(f"[SLMAgent] Stored skills fact for {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[SLMAgent] Failed to store skills: {e}")

                # FACT 4: Experience level
                if candidate.candidateExperience or getattr(candidate, 'total_experience_months', None):
                    try:
                        experience_text = candidate.candidateExperience or f"{getattr(candidate, 'total_experience_months', 0) or 0} months"
                        if experience_text.strip():
                            upsert_fact(
                                db=db,
                                candidate_id=candidate_id,
                                tenant_id=candidate.tenant_id or 1,
                                fact_category='MOTIVATOR',
                                fact_key='experience_level',
                                fact_value=str(experience_text),
                                confidence=0.80
                            )
                            logger.info(f"[SLMAgent] Stored experience fact for {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[SLMAgent] Failed to store experience: {e}")

                # FACT 5: Recruitment source
                if candidate.candidateSource:
                    try:
                        source = candidate.candidateSource.strip()
                        if source:
                            upsert_fact(
                                db=db,
                                candidate_id=candidate_id,
                                tenant_id=candidate.tenant_id or 1,
                                fact_category='EMPLOYER',
                                fact_key='recruitment_source',
                                fact_value=source,
                                confidence=0.95
                            )
                            logger.info(f"[SLMAgent] Stored source fact for {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[SLMAgent] Failed to store source: {e}")

                logger.info(f"[SLMAgent] Fact extraction complete for {candidate_id}")
                db.commit()

            except Exception as e:
                logger.error(f"[SLMAgent] Fact extraction failed: {e}", exc_info=True)
                try:
                    db.rollback()
                except:
                    pass

        # Spawn background thread (non-blocking)
        agent_thread = threading.Thread(
            target=extract_facts,
            daemon=True,
            name=f"SLMAgent-{candidate_id}"
        )
        agent_thread.start()

        return {"spawn_id": f"slm-agent-{candidate_id}", "status": "spawned", "background": True}

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate email was generated and staged."""
        if not result or result.get('status') != 'email_content_generated':
            raise ValueError(f"Invalid SLM email result: {result}")

        if result.get('email_length', 0) <= 0:
            raise ValueError(f"Email content empty or invalid length: {result.get('email_length')}")

        candidate_id = result.get('candidate_id')
        if not candidate_id:
            raise ValueError("Missing candidate_id in result")

        logger.info(f"[SLMEmailGeneration] ✅ Validated: candidate={candidate_id}, email_length={result.get('email_length')}")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        from datetime import datetime, timedelta
        MAX_RETRIES = 3

        if message.retry_count >= MAX_RETRIES:
            return False

        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False

        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        from datetime import datetime, timedelta
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
            logger.info(f"[SLMEmailGeneration] Scheduled retry: retry_count={message.retry_count}")
        except Exception as e:
            db.rollback()
            logger.error(f"[SLMEmailGeneration] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        from datetime import datetime
        try:
            SLMEmailGenerationHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            db.commit()
            logger.info(f"[SLMEmailGeneration] ✅ Message marked COMPLETED: candidate={result.get('candidate_id')}")
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[SLMEmailGeneration] Failed to mark success: {e}", exc_info=True)
            raise RuntimeError(f"Failed to mark success: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        from datetime import datetime
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()
            db.commit()
            logger.error(f"[SLMEmailGeneration] Message FAILED: {final_error}")
        except Exception as e:
            db.rollback()
            logger.error(f"[SLMEmailGeneration] Failed to mark as FAILED: {e}", exc_info=True)
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
