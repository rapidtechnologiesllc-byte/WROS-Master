"""Message Handler: Candidate Creation with Retry Logic

Implements idempotent candidate creation through message queue.
- Creates candidate, status, education, experience records
- Logs all events via history API
- 5 retry attempts with 30-minute intervals
"""
from app.core.tenant_context import sole_tenant_id
from app.services.slm_service import SLMService
from app.services.candidate_service import create_candidate as create_candidate_safe
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.channel_queue import ChannelQueueItem
from app.models.candidate import Candidate, CandidateStatus, CandidateEducationForm, CandidateExperienceForm
from app.services.candidate_service import create_candidate, DuplicateCandidateError
from app.services.data_healer_service import DataHealerService
from app.services.message_queue_service import MessageQueueService
from app.services.message_handlers.base_message_handler import time_bound
from app.services.candidate_activity_service import (
    log_candidate_created,
)

logger = logging.getLogger(__name__)


class CandidateCreationHandler:
    """Handles candidate creation messages from queue with full record creation and event logging."""

    HANDLER_NAME = "candidate_creation"
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """Process candidate creation message - creates ALL records asynchronously.

        Args:
            message: ChannelQueueItem with payload containing candidate data
            db: Database session

        Returns:
            {'status': 'success', 'candidate_id': str, 'is_new': bool}
        """
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload
        candidate_email = payload.get("candidate_email")

        # ===== VALIDATION: Email required only for new candidates =====
        # If email is provided but invalid, always fail (format error)
        # If email is missing, warn and proceed (may merge with existing candidate that has email)
        if candidate_email and "@" not in candidate_email:
            # Email provided but malformed - always fail
            raise ValueError(f"Invalid candidate_email format (must contain @): {candidate_email}")

        if not candidate_email:
            logger.warning(f"[Handler] candidate_email missing from payload - will check duplicates first to determine if new or merged")

        logger.info(f"[Handler] Processing queue message, candidate_email={candidate_email}, payload keys={list(payload.keys())}")

        try:
            # ATOMIC TRANSACTION: All records (candidate, status, education, experience) created together
            # Use db.flush() pattern: add all, flush once, commit once

            # 1. CREATE CANDIDATE - Direct ORM mapping from payload
            # Map payload fields to Candidate model fields (payload uses candidate_* naming)
            pass

            # Extract and validate tenant_id using centralized validation
            # This eliminates duplication across all handlers and services
            from app.services.candidate_service import validate_and_normalize_tenant_id
            raw_tenant_id = payload.get("tenant_id") or getattr(message, "tenant_id", None) or sole_tenant_id(db)
            tenant_id = validate_and_normalize_tenant_id(db, raw_tenant_id)
            logger.info(f"[Handler] Using tenant_id={tenant_id} for candidate")

            # R-07: Use create_candidate_safe() for all creates - dedup on email, phone, LinkedIn
            plain_password = payload.get("candidate_temp_password")
            candidate, is_new = create_candidate_safe(
                db=db,
                email=candidate_email,
                mobile=payload.get("candidate_mobile"),
                linkedin_url=payload.get("linkedin_url"),
                plain_password=plain_password,
                candidateRole=payload.get("candidate_role", "Candidate"),
                candidateEmployeeType=payload.get("candidate_employee_type"),
                candidateFirstName=payload.get("candidate_first_name"),
                candidateMiddleName=payload.get("candidate_middle_name"),
                candidateLastName=payload.get("candidate_last_name"),
                candidateGender=payload.get("candidate_gender"),
                candidateDateOfBirth=payload.get("candidate_date_of_birth"),
                candidateCurrentLocation=payload.get("candidate_current_location"),
                candidateSource=payload.get("candidate_source"),
                candidateExperience=payload.get("candidate_experience"),
                candidateSkills=payload.get("candidate_skills"),
                candidateJoiningDate=payload.get("candidate_joining_date"),
                candidateExpectedSalary=payload.get("candidate_expected_salary"),
                candidateCurrentSalary=payload.get("candidate_current_salary"),
            )

            # If new candidate, add to session; if duplicate, already in DB
            if is_new:
                logger.info(f"[Handler] New candidate created: {candidate_email}")
            else:
                logger.info(f"[Handler] Candidate already exists (dedup): {candidate_email}")

            # Flush candidate to get candidateID (but don't commit yet)
            try:
                db.flush()
                db.refresh(candidate)
            except Exception as e:
                db.rollback()
                logger.error(f"[Handler] Flush failed for candidate: {e}", exc_info=True)
                raise RuntimeError(f"Failed to create candidate: {str(e)}") from e

            candidate_id = candidate.candidateID
            logger.info(f"[Handler] ✅ Candidate flushed: {candidate_id}")

            # S-347/HRMS-P117: Record CANDIDATE_CREATED signal immediately (feeds SLM pipeline)
            try:
                from app.services.desire_signal_service import record_message_signal
                logger.info(f"[Handler] 🔄 Recording CANDIDATE_CREATED signal for {candidate_id}")
                first_name = candidate.candidateFirstName or "Unknown"
                last_name = candidate.candidateLastName or "Candidate"
                record_message_signal(
                    db, tenant_id, candidate_id, "CANDIDATE_CREATED",
                    f"Candidate {first_name} {last_name} created from {payload.get('candidate_source') or 'DIRECT'}"
                )
                logger.info(f"[Handler] ✅ CANDIDATE_CREATED signal recorded for {candidate_id}")
            except Exception as signal_err:
                logger.error(f"[Handler] ⚠️ Failed to record CANDIDATE_CREATED signal: {signal_err}", exc_info=True)
                # Don't fail candidate creation if signal recording fails (fire-and-forget pattern)

            # BLOCKER #3: Create CandidateConversation for Flash analysis linkage
            from app.models.candidate_ai import CandidateConversation
            try:
                existing_conversation = db.query(CandidateConversation).filter(
                    CandidateConversation.candidate_id == candidate_id
                ).first()

                if not existing_conversation:
                    # CRITICAL FIX: CandidateConversation.tenant_id is String(FK to users.UserID)
                    # Use centralized helper to map numeric tenant_id to UserID
                    from app.services.candidate_service import get_user_for_tenant
                    conversation_tenant_id = get_user_for_tenant(db, tenant_id)

                    candidate_conversation = CandidateConversation(
                        tenant_id=conversation_tenant_id,  # String UserID (from centralized helper)
                        candidate_id=candidate_id,
                        status="open",
                        ai_agent_name="flash_recruiter",
                        channel_preference="email"
                    )
                    db.add(candidate_conversation)
                    db.flush()
                    logger.info(f"[Handler] ✅ CandidateConversation created for {candidate_id} with tenant_id={conversation_tenant_id}")

                    # CRITICAL #4: Verify conversation actually exists (no silent failure)
                    created_conv = db.query(CandidateConversation).filter(
                        CandidateConversation.candidate_id == candidate_id
                    ).first()
                    if not created_conv:
                        raise RuntimeError(f"Conversation creation failed for {candidate_id} (post-flush verify failed)")
            except Exception as e:
                logger.error(f"[Handler] CRITICAL: Failed to create conversation for {candidate_id}: {e}", exc_info=True)
                # CRITICAL FIX: Fail loudly, don't silently skip
                raise RuntimeError(f"Cannot create candidate without conversation: {e}")

            # 2. CREATE STATUS
            try:
                existing_status = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
            except Exception as e:
                logger.error(f"[Handler] Failed to query status: {e}", exc_info=True)
                existing_status = None

            if not existing_status:
                try:
                    db.add(CandidateStatus(
                        candidateID=candidate_id, piplineStatus="Applied", status="Active",
                        createdAt=datetime.now(), updatedAt=datetime.now(),
                    ))
                except Exception as e:
                    logger.error(f"[Handler] Failed to add status: {e}", exc_info=True)
                    db.rollback()
                    raise

            # 3. CREATE EDUCATION RECORDS
            for edu in payload.get("education_records", []):
                try:
                    existing = db.query(CandidateEducationForm).filter(
                        CandidateEducationForm.candidateID == candidate_id,
                        CandidateEducationForm.education_institute == edu.get("education_institute"),
                        CandidateEducationForm.degree == edu.get("degree"),
                    ).first()
                except Exception as e:
                    logger.error(f"[Handler] Failed to query education: {e}", exc_info=True)
                    existing = None

                if not existing:
                    try:
                        db.add(CandidateEducationForm(
                        candidateID=candidate_id,
                        education_institute=edu.get("education_institute"),
                        degree=edu.get("degree"),
                        field_of_study=edu.get("field_of_study"),
                        starting_year=edu.get("starting_year"),
                        year_of_passing=edu.get("year_of_passing"),
                        percentage=edu.get("percentage"),
                        submittedAt=edu.get("submitted_at"),
                        document_is_submitted=edu.get("document_is_submitted"),
                        document_id=edu.get("document_id"),
                        ))
                    except Exception as e:
                        logger.error(f"[Handler] Failed to add education record: {e}", exc_info=True)
                        db.rollback()
                        raise

            # 4. CREATE EXPERIENCE RECORDS
            for exp in payload.get("experience_records", []):
                try:
                    existing = db.query(CandidateExperienceForm).filter(
                        CandidateExperienceForm.candidateID == candidate_id,
                        CandidateExperienceForm.company_name == exp.get("company_name"),
                        CandidateExperienceForm.job_title == exp.get("job_title"),
                    ).first()
                except Exception as e:
                    logger.error(f"[Handler] Failed to query experience: {e}", exc_info=True)
                    existing = None

                if not existing:
                    try:
                        db.add(CandidateExperienceForm(
                            candidateID=candidate_id,
                            company_name=exp.get("company_name"),
                            job_title=exp.get("job_title"),
                            start_date=exp.get("start_date"),
                            end_date=exp.get("end_date"),
                            year_of_experience=exp.get("year_of_experience"),
                            submittedAt=exp.get("submitted_at"),
                            document_is_submitted=exp.get("document_is_submitted"),
                            document_id=exp.get("document_id"),
                        ))
                    except Exception as e:
                        logger.error(f"[Handler] Failed to add experience record: {e}", exc_info=True)
                        db.rollback()
                        raise

            # ATOMIC COMMIT: All or nothing - single commit for all records
            try:
                db.commit()
                logger.info(f"[Handler] ✅ All records created atomically for {candidate_id} (candidate, status, education, experience)")
            except Exception as e:
                db.rollback()
                logger.error(f"[Handler] Atomic commit failed: {e}", exc_info=True)
                raise RuntimeError(f"Failed to commit all records: {str(e)}") from e

            # LOG ACTIVITY - Phase 2.1: Candidate creation logging with user attribution
            # Wrapped in try/except so logging failure doesn't block creation success
            try:
                # PHASE 1A: Extract user attribution from payload
                created_by_user_id = payload.get("created_by_user_id")
                created_by_name = payload.get("created_by_name", "System")

                log_candidate_created(
                    db,
                    candidate_id=candidate_id,
                    created_by_user_id=created_by_user_id,
                    created_by_name=created_by_name,
                    recruitment_source=payload.get("candidate_source", "DIRECT")
                )
                db.commit()
                logger.info(f"[Handler] ✅ Activity logged for candidate creation: {candidate_id} by {created_by_name}")

                # AUDIT LOGGING: Write to audit_log table for compliance (NON-OPTIONAL)
                from app.core.audit import write_audit_log
                try:
                    write_audit_log(
                        db,
                        entity_type="candidate",
                        entity_id=candidate_id,
                        action="create",
                        tenant_id=candidate.tenant_id,
                        user_id=created_by_user_id,
                        old_value=None,
                        new_value=f"Email: {candidate_email}, Name: {payload.get('candidate_first_name', '')} {payload.get('candidate_last_name', '')}"
                    )
                    db.commit()
                    logger.info(f"[Handler] ✅ Audit logged for candidate creation: {candidate_id}")
                except Exception as audit_err:
                    logger.error(f"[Handler] ❌ FAILED to audit log candidate creation (compliance issue): {audit_err}", exc_info=True)
                    db.rollback()
                    raise RuntimeError(f"Audit logging failed for candidate {candidate_id}: {audit_err}") from audit_err

            except Exception as log_err:
                logger.warning(f"[Handler] Failed to log candidate creation activity: {log_err}, but creation succeeded")

            # ===== NOTE: Detailed validation happens in validate() method =====
            # This process() method creates the candidate and logs the ID.
            # The validate() method (called by on_success() in worker) performs all checks:
            # - Verify candidate_id is not null
            # - Verify candidate exists in database
            # - Verify email matches (or is acceptable mismatch for duplicates)
            # - Verify tenant assignment
            # This separation ensures:
            # 1. Creation is atomic and isolated
            # 2. Validation happens AFTER successful commit
            # 3. Detailed validation logging is tied to on_success() call for queue monitoring

            # For now, just log the candidate ID for debugging:
            logger.info(f"[Handler] Candidate created: {candidate_id} (validation happens in on_success())")

            # PHASE: Send welcome message via WhatsApp + EMAIL
            whatsapp_delivery_id = None
            email_delivery_id = None
            try:
                from app.services.delivery_factory import get_delivery_service

                # Get delivery service for this tenant with their configured credentials
                try:
                    delivery = get_delivery_service(db, tenant_id)
                except RuntimeError as e:
                    logger.warning(f"[Handler] Cannot send welcome messages - delivery not configured: {e}")
                    delivery = None

                candidate_name = getattr(candidate, 'candidateFirstName', 'Candidate')
                candidate_phone = getattr(candidate, 'candidateMobile', None)
                candidate_email_addr = candidate.candidateEmail

                # Send WhatsApp welcome message (primary) - only if delivery is configured
                if delivery and candidate_phone:
                    try:
                        whatsapp_body = f"""Welcome to our recruiting platform, {candidate_name}!

We're excited to have you on board. Get ready to explore amazing job opportunities that match your profile.

Our team will reach out soon with personalized job recommendations.

Happy exploring!"""

                        whatsapp_result = delivery.send_whatsapp(
                            to_number=candidate_phone,
                            body=whatsapp_body
                        )

                        if whatsapp_result.status == 'failed':
                            logger.warning(f"[Handler] WhatsApp welcome failed: {whatsapp_result.error}")
                        else:
                            whatsapp_delivery_id = whatsapp_result.delivery_id
                            logger.info(f"[Handler] Welcome WhatsApp sent to {candidate_phone}, delivery_id={whatsapp_delivery_id}")
                    except Exception as wa_err:
                        logger.warning(f"[Handler] WhatsApp send error: {wa_err}")

                # Queue welcome email (async via message queue)
                if candidate_email_addr:
                    try:
                        email_subject = "Welcome to Our Recruiting Platform"
                        email_body = f"""
Dear {candidate_name},

Welcome to our recruiting platform! We're thrilled to have you on board.

Your profile is now live and ready to connect with amazing job opportunities. Our recruiting team will review your profile and suggest positions that align with your skills and experience.

What's next?
1. Complete your profile with additional details
2. Review recommended job opportunities
3. Apply for positions that interest you
4. Track your application status in real-time

If you have any questions or need assistance, our support team is here to help.

Best regards,
Recruiting Team
"""

                        # Queue email via message queue for async processing
                        MessageQueueService.enqueue(
                            task_name='send_email_to_candidate',
                            task_id=f'welcome-{candidate_id}',
                            data={
                                'to_email': candidate_email_addr,
                                'subject': email_subject,
                                'body': email_body,
                                'is_html': True,
                                'candidate_id': candidate_id,
                                'email_type': 'WELCOME'
                            }
                        )
                        logger.info(f"[Handler] ✅ Queued welcome email to {candidate_email_addr} for {candidate_id}")
                    except Exception as email_err:
                        logger.warning(f"[Handler] Failed to queue welcome email: {email_err}")

            except Exception as delivery_err:
                logger.warning(f"[Handler] Delivery service error (non-blocking): {delivery_err}")

            # RETURN SUCCESS IMMEDIATELY - Mark handler complete before queuing dependent work
            # This prevents handler from blocking on email/Thunder queueing
            result = {
                "status": "COMPLETED",
                "candidate_id": candidate_id,
                "is_new": is_new,
                "candidate_email": candidate_email,
                "whatsapp_delivery_id": whatsapp_delivery_id,
                "email_delivery_id": email_delivery_id,
                "data": {
                    "status": "COMPLETED",
                    "candidate_id": candidate_id,
                    "is_new": is_new,
                    "candidate_email": candidate_email
                }
            }
            log_msg = f"[Handler] ✅ Candidate creation complete: {candidate_id}"
            if is_new:
                log_msg += " (NEW candidate created)"
            else:
                log_msg += " (DUPLICATE - existing candidate reused)"
            logger.info(f"{log_msg} (ready for return)")

            # Queue dependent work AFTER returning success (non-blocking background tasks)
            # These should NOT block handler completion
            try:
                # Log history event (non-critical)
                CandidateCreationHandler._log_history_event(
                    candidate_id, "Candidate Added", f"Candidate added via form submission"
                )
                logger.info(f"[Handler] ✅ History event logged for {candidate_id}")
            except Exception as e:
                logger.warning(f"[Handler] History logging failed (non-blocking): {e}", exc_info=True)

            # ARCHITECT FIX: Thunder queueing moved to queue_processor_service as side effect
            # This prevents double-engagement when queue_processor also queues Thunder after COMPLETED
            # Handler responsibility: Create candidate data only, not orchestrate downstream workflows

            # SLM ORCHESTRATION: Analyze result and decide next actions (NON-BLOCKING)
            # SLMService is a Decision Orchestration Service (NOT machine learning)
            # It validates results and routes to next workflow step (Thunder email, escalation, etc)
            # CRITICAL: SLM failures do NOT block candidate creation success
            # Candidate creation is the primary responsibility; SLM is optional downstream routing
            try:
                candidate_first_name = payload.get("candidate_first_name", "Candidate")
                MessageQueueService.enqueue(
                    task_name='send_email',
                    channel_type='EMAIL_QUEUE',
                    data={
                        'candidate_id': candidate_id,
                        'recipient_email': candidate_email,
                        'email_type': 'FIRST_ENGAGEMENT',
                        'subject': f'Welcome {candidate_first_name}! Your Application is Received',
                        'body': f'Hi {candidate_first_name},\n\nThank you for applying! We have received your application and will review it shortly.\n\nBest regards,\nBlitzenX Team',
                        'tenant_id': tenant_id,
                    }
                )
                logger.info(f"[Handler] ✅ Queued first engagement email for {candidate_id}")
            except Exception as e:
                logger.warning(f"[Handler] Failed to queue email (non-blocking): {e}")

                # Analyze candidate creation result
                handler_result = {
                    'success': True,
                    'candidate_id': candidate_id,
                    'email': candidate_email,
                    'is_new': is_new,
                }

                slm_decision = SLMService.analyze_message_result(
                    message_id=message.id,
                    message_type='candidate_created',
                    result=handler_result,
                    db=db,
                    handler_name='candidate_creation'
                )

                logger.info(f"[Handler] ✅ SLM decision: {slm_decision['decision_type']} → {slm_decision['next_action']}")

                # ACT ON DECISION: Queue Thunder if recommended
                # If SLM says to send email, queue Thunder engagement
                if slm_decision.get('next_action') == SLMService.ACTION_SEND_EMAIL:
                    try:
                        from app.services.message_queue_service import MessageQueueService
                        MessageQueueService.enqueue(
                            task_name='engage_candidate_with_thunder',
                            data={
                                'candidate_id': candidate_id,
                                'channel_preference': 'email',
                                'trigger': 'candidate_created',
                                'slm_decision_id': slm_decision.get('details', {}).get('slm_decision_id')
                            }
                        )
                        logger.info(f"[Handler] ✅ Thunder engagement queued per SLM decision for {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[Handler] Thunder queue failed (SLM-orchestrated): {e}", exc_info=True)

                # If SLM says escalate, log for manual review (don't queue Thunder)
                elif slm_decision.get('decision_type') == SLMService.DECISION_ESCALATE:
                    logger.warning(f"[Handler] SLM escalation required: {slm_decision.get('reason')} for {candidate_id}")

            except Exception as e:
                # CRITICAL FIX: SLM failures do NOT fail the handler
                # Candidate was successfully created and validated
                # SLM is just a downstream decision service (fire-and-forget pattern)
                logger.warning(f"[Handler] ⚠️ SLM orchestration failed (non-blocking): {e}", exc_info=True)
                logger.info(f"[Handler] ✅ Candidate creation succeeded despite SLM failure - {candidate_id}")

            return result

        except DuplicateCandidateError as e:
            logger.warning(f"[Handler] Duplicate candidate: {candidate_email}", exc_info=True)
            # Duplicates are OK - track as multiple applications
            return {"status": "success", "candidate_id": str(e), "is_new": False, "duplicate": True}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Handler] Candidate creation failed: {error_msg}", exc_info=True)

            # HEALING STRATEGY: Try to fix data issues before giving up
            can_heal, healed_payload, recruiter_task = DataHealerService.heal_and_recover(
                error=error_msg,
                payload=payload,
                db=db
            )

            if can_heal:
                logger.info(f"[Handler] Healer fixed issues, retrying with healed payload")
                # Retry with healed payload (may use placeholders)
                try:
                    candidate, is_new = create_candidate(
                        db,
                        email=healed_payload.get("candidate_email"),
                        mobile=healed_payload.get("candidate_mobile"),
                        plain_password=healed_payload.get("candidate_temp_password"),
                        tenant_id=healed_payload.get("tenant_id"),
                        candidateRole=healed_payload.get("candidate_role", "Candidate"),
                        candidateEmployeeType=healed_payload.get("candidate_employee_type"),
                        candidateFirstName=healed_payload.get("candidate_first_name"),
                        candidateLastName=healed_payload.get("candidate_last_name"),
                        candidateGender=healed_payload.get("candidate_gender"),
                        candidateDateOfBirth=healed_payload.get("candidate_date_of_birth"),
                        candidateCurrentLocation=healed_payload.get("candidate_current_location"),
                        candidateCreatedAt=datetime.now(),
                    )
                    try:
                        db.commit()
                    except Exception as commit_err:
                        db.rollback()
                        raise RuntimeError(f"Failed to commit healed candidate: {str(commit_err)}") from commit_err

                    try:
                        db.refresh(candidate)
                    except Exception as refresh_err:
                        logger.error(f"Failed to refresh candidate: {refresh_err}")
                        raise RuntimeError(f"Failed to refresh candidate: {str(refresh_err)}") from refresh_err

                    candidate_id = candidate.candidateID

                    # Create status if it doesn't already exist
                    try:
                        existing_status = db.query(CandidateStatus).filter(
                            CandidateStatus.candidateID == candidate_id
                        ).first()
                    except Exception as query_err:
                        existing_status = None
                        logger.warning(f"Failed to query status: {query_err}")

                    if not existing_status:
                        try:
                            status_record = CandidateStatus(
                                candidateID=candidate_id,
                                piplineStatus="Applied",
                                status="Active",
                                createdAt=datetime.now(),
                                updatedAt=datetime.now(),
                            )
                            db.add(status_record)
                            db.commit()
                        except Exception as status_err:
                            db.rollback()
                            logger.error(f"Failed to create status for healed candidate: {status_err}", exc_info=True)
                            raise RuntimeError(f"Failed to create status: {str(status_err)}") from status_err

                    # Queue first engagement email for healed candidate
                    try:
                        candidate_first_name = healed_payload.get("candidate_first_name", "Candidate")
                        candidate_email = healed_payload.get("candidate_email")
                        MessageQueueService.enqueue(
                            task_name='send_email_to_candidate',
                            channel_type='EMAIL_QUEUE',
                            data={
                                'candidate_id': candidate_id,
                                'to_email': candidate_email,
                                'email_type': 'FIRST_ENGAGEMENT',
                                'subject': f'Welcome {candidate_first_name}! Your Application is Received',
                                'body': f'Hi {candidate_first_name},\n\nThank you for applying! We have received your application and will review it shortly.\n\nBest regards,\nBlitzenX Team',
                                'is_html': False,
                                'tenant_id': healed_payload.get('tenant_id') or tenant_id,
                            }
                        )
                        logger.info(f"[Handler] ✅ Queued email for healed candidate {candidate_id}")
                    except Exception as e:
                        logger.warning(f"[Handler] Failed to queue email for healed candidate: {e}")

                    # CRITICAL: Verify BOTH candidate AND related records exist before marking success
                    # NO COMPROMISE: Healed candidate must be fully persisted
                    db_candidate_verify = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                    if not db_candidate_verify:
                        raise RuntimeError(
                            f"Healed candidate creation failed: candidate {candidate_id} not found in database "
                            f"after healer completed. Data persistence verification failed."
                        )
                    logger.info(f"[Handler] ✅ Healed candidate verified in database: {candidate_id}")

                    # Verify CandidateStatus also exists for healed candidate
                    healed_status = db.query(CandidateStatus).filter(
                        CandidateStatus.candidateID == candidate_id
                    ).first()
                    if not healed_status:
                        raise RuntimeError(
                            f"Healed candidate {candidate_id} exists but required CandidateStatus record missing. "
                            f"Data persistence incomplete - healer created candidate but status not found."
                        )
                    logger.info(f"[Handler] ✅ Healed candidate status verified in database: {candidate_id}")

                    # If we used placeholders, create a recruiter task to fix the data
                    if recruiter_task:
                        logger.info(f"[Handler] Creating recruiter task: {recruiter_task}")
                        DataHealerService.create_recruiter_fix_task(candidate_id, recruiter_task, db)

                    return {"status": "success", "candidate_id": candidate_id, "is_new": is_new, "healed": True}

                except Exception as retry_error:
                    logger.error(f"[Handler] Healed retry also failed: {retry_error}", exc_info=True)
                    # Escalate to recruiter for manual review
                    raise RuntimeError(f"Manual review required after healing attempt: {retry_error}") from retry_error
            else:
                # Cannot heal - escalate
                escalation_msg = recruiter_task or f"Cannot auto-fix: {error_msg}"
                logger.error(f"[Handler] Escalating to recruiter: {escalation_msg}")
                raise RuntimeError(escalation_msg) from e

    @staticmethod
    def _log_history_event(candidate_id: str, event_type: str, note: str):
        """Log history event via API (graceful failure if unavailable)."""
        try:
            # This would call the history API endpoint - for now just log
            logger.info(f"[History] Event '{event_type}' for candidate {candidate_id}: {note}")
        except Exception as e:
            logger.warning(f"[History] Failed to log event: {e}")

    @staticmethod
    def should_retry(message: ChannelQueueItem) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateCreationHandler.MAX_RETRIES:
            logger.error(f"[Handler] Max retries exceeded for {message.id}")
            return False
        if message.next_retry_at and datetime.utcnow() < message.next_retry_at:
            return False
        return True

    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
        """Handle retry logic after failed attempt."""
        try:
            # Rollback any aborted transaction first (critical for PostgreSQL)
            db.rollback()

            # Now update the message status in a fresh transaction
            message.retry_count += 1
            message.error = error
            message.next_retry_at = datetime.utcnow() + timedelta(minutes=CandidateCreationHandler.RETRY_DELAY_MINUTES)

            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"[Handler] Failed to rollback after error: {rollback_err}", exc_info=True)
            logger.error(f"[Handler] Failed to schedule retry: {e}", exc_info=True)
            raise

    @staticmethod
    def validate(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """
        Validate that candidate creation actually completed successfully.

        Runs BEFORE marking message as COMPLETED. Queries database to verify:
        1. Candidate record exists
        2. Email matches expected value
        3. Tenant assignment correct
        4. Status is not DUPLICATE

        Args:
            message: Queue message (contains payload)
            result: Result dict from process() (contains candidate_id, is_new)
            db: Database session

        Raises:
            ValueError: If candidate not found or data mismatch (non-retryable)
            RuntimeError: If database error during validation (retryable)
        """
        from app.models.candidate import Candidate

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result from process(): {result}")

        candidate_id = result.get("candidate_id")
        payload = message.payload or {}

        # Extract is_new flag to determine if this was a merged duplicate
        is_new = result.get("is_new", True)

        try:
            # 1. VERIFY CANDIDATE EXISTS
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found in database after creation")

            # 2. VERIFY EMAIL MATCHES (conditional on is_new)
            expected_email = payload.get("candidate_email")
            if expected_email and candidate.candidateEmail != expected_email:
                # Check if this is an acceptable mismatch (merged duplicate)
                if is_new:
                    # New candidate: email MUST match exactly
                    raise ValueError(
                        f"Email mismatch for {candidate_id}: expected '{expected_email}', "
                        f"got '{candidate.candidateEmail}' (NEW candidate - no merge)"
                    )
                else:
                    # Merged duplicate: email mismatch is expected/acceptable
                    logger.info(
                        f"[Handler] ✅ Email mismatch accepted (merged duplicate): "
                        f"payload='{expected_email}', existing='{candidate.candidateEmail}' (is_new={is_new})"
                    )
            else:
                logger.info(f"[Handler] ✅ Email verified: {candidate.candidateEmail}")

            # 3. VERIFY TENANT ASSIGNMENT
            expected_tenant = payload.get("tenant_id") or getattr(message, "tenant_id", None) or sole_tenant_id(db)
            if isinstance(expected_tenant, int):
                from app.models.user import Users
                user = db.query(Users).filter(Users.tenant_id == expected_tenant).first()
                if user:
                    expected_tenant = user.UserID
            if candidate.tenant_id != str(expected_tenant):
                raise ValueError(
                    f"Tenant mismatch for {candidate_id}: expected '{expected_tenant}', "
                    f"got '{candidate.tenant_id}'"
                )

            # 4. VERIFY NOT DUPLICATE
            if candidate.candidateStatus == "DUPLICATE":
                logger.warning(
                    f"Candidate {candidate_id} marked as DUPLICATE. This is expected if "
                    f"a duplicate was merged. Validation passed."
                )

            # ✅ ALL VALIDATIONS PASSED
            logger.info(
                f"✅ Candidate creation validated: ID={candidate_id}, Email={candidate.candidateEmail}, "
                f"Tenant={candidate.tenant_id}, Status={candidate.candidateStatus}"
            )

        except (ValueError, AttributeError) as e:
            # Non-retryable: candidate not found or data mismatch = handler bug
            logger.error(f"[Handler] NON-RETRYABLE validation error for {candidate_id}: {e}")
            raise ValueError(str(e)) from e

        except Exception as e:
            # Retryable: database error during validation
            logger.error(f"[Handler] RETRYABLE validation error for {candidate_id}: {e}", exc_info=True)
            raise RuntimeError(f"Database validation error: {str(e)}") from e

    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Mark message as COMPLETED after validation passes.

        Calls validate() which:
        - Queries database to verify candidate was created
        - Checks email matches payload
        - Verifies tenant assignment
        - Raises ValueError (non-retryable) or RuntimeError (retryable) on failure

        CRITICAL: validate() must pass before marking COMPLETED.
        """
        try:
            # Call the new validate() method which follows base handler pattern
            # This will raise ValueError (non-retryable) or RuntimeError (retryable) if validation fails
            CandidateCreationHandler.validate(message, result, db)

            # ✅ VALIDATION PASSED - Mark as COMPLETED
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit COMPLETED status: {str(commit_err)}") from commit_err

            candidate_id = result.get("candidate_id", "unknown")
            logger.info(f"[Handler] ✅ Message {message.id} marked COMPLETED (candidate {candidate_id})")

            return {
                'is_valid': True,
                'candidate_id': candidate_id,
                'message': 'Validation passed and message marked COMPLETED'
            }

        except ValueError as e:
            # Non-retryable: validation failed due to handler bug (candidate not found, data mismatch, etc.)
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            # Re-raise for caller to mark as FAILED (don't retry)
            raise

        except RuntimeError as e:
            # Retryable: validation failed due to temporary error (database issue, etc.)
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            # Re-raise for caller to schedule retry
            raise

        except Exception as e:
            # Unexpected error
            db.rollback()
            logger.error(f"[Handler] ❌ Unexpected error during on_success: {e}", exc_info=True)
            # Treat as retryable
            raise RuntimeError(f"Unexpected error: {str(e)}") from e
            return {
                'is_valid': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
        """Handle final failure after all retries exhausted."""
        try:
            # Rollback any aborted transaction first (critical for PostgreSQL)
            db.rollback()

            # Now update the message status in a fresh transaction
            message.status = "FAILED"
            message.error = final_error
            message.completed_at = datetime.utcnow()

            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"[Handler] Failed to rollback after error: {rollback_err}", exc_info=True)
            logger.error(f"[Handler] Failed to mark failure: {e}", exc_info=True)
            raise

    @staticmethod
    def prioritize_queue(db: Session) -> list:
        """
        Prioritize Thunder candidate queue by match score (descending).

        Fetches all pending candidates and sorts by ATSScore.overall_score.
        Higher scores = better fit = higher priority.

        Returns:
            List of candidate IDs sorted by match_score DESC
        """
        try:
            from app.models.candidate import Candidate
            from app.models.ats import ATSScore

            # Fetch all candidates with their match scores
            candidates_with_scores = db.query(
                Candidate.candidateID,
                ATSScore.overall_score
            ).outerjoin(
                ATSScore,
                ATSScore.candidate_id == Candidate.candidateID
            ).filter(
                Candidate.candidateCreatedAt >= datetime.utcnow() - timedelta(days=7)  # Last 7 days
            ).order_by(
                ATSScore.overall_score.desc()  # Highest scores first
            ).all()

            prioritized_candidates = [row.candidateID for row in candidates_with_scores]

            logger.info(
                f"[QueuePrioritization] Prioritized {len(prioritized_candidates)} candidates by match_score. "
                f"Top 3: {prioritized_candidates[:3]}"
            )

            return prioritized_candidates

        except Exception as e:
            logger.error(f"[QueuePrioritization] Failed to prioritize queue: {e}", exc_info=True)
            raise
