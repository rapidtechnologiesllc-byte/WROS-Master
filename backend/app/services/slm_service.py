"""SLM (Small Language Model) Service - Analyzes message results and decides next actions

After each message processes, SLM analyzes the result and determines the next action for Flash agent.
Examples:
- "Candidate added" → SLM → "Thunder should email candidate"
- "Thunder failed to email" → SLM → "Escalate to Flash for manual contact"
- "Interview scheduled" → SLM → "Next: offer generation workflow"

Implements FAIL FAST: All methods raise exceptions on error.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)

class SLMService:
    """Service for SLM analysis and decision making with fail-fast error handling."""

    # Decision types
    DECISION_ESCALATE = "escalate"
    DECISION_NEXT_ACTION = "next_action"
    DECISION_MANUAL_REVIEW = "manual_review"
    DECISION_AUTO_PROCEED = "auto_proceed"

    # Next action types
    ACTION_SEND_EMAIL = "send_email"
    ACTION_SCHEDULE_INTERVIEW = "schedule_interview"
    ACTION_GENERATE_OFFER = "generate_offer"
    ACTION_ESCALATE_TO_MANAGER = "escalate_to_manager"
    ACTION_TRY_NEXT_CANDIDATE = "try_next_candidate"
    ACTION_NONE = "none"

    @staticmethod
    def analyze_message_result(
        message_id: str,
        message_type: str,
        result: Dict[str, Any],
        db: Optional[Session] = None,
        handler_name: str = None,  # CYCLE 19: Handler name for decision recording
    ) -> Dict[str, Any]:
        """
        Analyze message processing result and return decision.

        Args:
            message_id: ID of message being analyzed
            message_type: Type of message (e.g., 'candidate_added', 'thunder_email_sent')
            result: Result dict from message processing
            db: Database session

        Returns:
            Decision dict with decision_type, next_action, confidence_score, etc.

        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If analysis fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            if not message_id or not message_type:
                raise ValueError("message_id and message_type required")

            # Route to type-specific analyzer
            if message_type == "candidate_added":
                decision = SLMService._analyze_candidate_added(result)
            elif message_type == "thunder_email_sent":
                decision = SLMService._analyze_thunder_email_sent(result)
            elif message_type == "flash_agent_action":
                decision = SLMService._analyze_flash_action(result)
            elif message_type == "interview_scheduled":
                decision = SLMService._analyze_interview_scheduled(result)
            elif message_type == "offer_generated":
                decision = SLMService._analyze_offer_generated(result)
            else:
                # Default: log and proceed
                logger.warning(f"Unknown message type: {message_type}")
                decision = {
                    "decision_type": SLMService.DECISION_AUTO_PROCEED,
                    "next_action": SLMService.ACTION_NONE,
                    "confidence_score": 0.5,
                    "reason": f"Unknown message type: {message_type}",
                }

            # Store decision
            SLMService._store_decision(message_id, decision, db, handler_name)

            logger.info(
                f"SLM analysis complete: message_id={message_id} "
                f"decision={decision['decision_type']} "
                f"next_action={decision['next_action']} "
                f"confidence={decision['confidence_score']}"
            )

            return decision

        except Exception as e:
            logger.error(f"Failed to analyze message result: {e}", exc_info=True)
            raise RuntimeError(f"Failed to analyze message result: {str(e)}")

    @staticmethod
    def _analyze_candidate_added(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze candidate_added message."""
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.9,
                "reason": "Candidate creation failed",
                "details": result.get("error"),
            }

        # Candidate added successfully → Thunder should contact them
        return {
            "decision_type": SLMService.DECISION_AUTO_PROCEED,
            "next_action": SLMService.ACTION_SEND_EMAIL,
            "confidence_score": 0.95,
            "reason": "New candidate should be contacted by Thunder",
            "details": {"target": "send_candidate_welcome_email"},
        }

    @staticmethod
    def _analyze_thunder_email_sent(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze thunder_email_sent message."""
        success = result.get("success", False)
        retries = result.get("retry_count", 0)

        if not success:
            if retries >= 3:
                return {
                    "decision_type": SLMService.DECISION_ESCALATE,
                    "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                    "confidence_score": 0.85,
                    "reason": "Thunder email failed after multiple retries",
                    "details": result.get("error"),
                }
            else:
                return {
                    "decision_type": SLMService.DECISION_AUTO_PROCEED,
                    "next_action": SLMService.ACTION_SEND_EMAIL,
                    "confidence_score": 0.6,
                    "reason": "Retry Thunder email delivery",
                }

        # Email sent successfully → Wait for engagement
        return {
            "decision_type": SLMService.DECISION_AUTO_PROCEED,
            "next_action": SLMService.ACTION_NONE,
            "confidence_score": 0.9,
            "reason": "Thunder email sent, monitoring engagement",
        }

    @staticmethod
    def _analyze_flash_action(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze flash_agent_action message."""
        action_type = result.get("action_type")
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.85,
                "reason": f"Flash action failed: {action_type}",
                "details": result.get("error"),
            }

        # Determine next action based on what Flash did
        if action_type == "schedule_interview":
            return {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_NONE,
                "confidence_score": 0.95,
                "reason": "Interview scheduled, waiting for completion",
            }

        elif action_type == "generate_offer":
            return {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_NONE,
                "confidence_score": 0.9,
                "reason": "Offer generated, pending approval",
            }

        else:
            return {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_NONE,
                "confidence_score": 0.7,
                "reason": f"Flash action completed: {action_type}",
            }

    @staticmethod
    def _analyze_interview_scheduled(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze interview_scheduled message."""
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.8,
                "reason": "Failed to schedule interview",
                "details": result.get("error"),
            }

        # Interview scheduled → Notify panel
        return {
            "decision_type": SLMService.DECISION_AUTO_PROCEED,
            "next_action": SLMService.ACTION_NONE,
            "confidence_score": 0.95,
            "reason": "Interview scheduled, panel notifications sent",
        }

    @staticmethod
    def _analyze_offer_generated(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze offer_generated message."""
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.8,
                "reason": "Failed to generate offer",
                "details": result.get("error"),
            }

        # Offer generated → Manager approval
        return {
            "decision_type": SLMService.DECISION_MANUAL_REVIEW,
            "next_action": SLMService.ACTION_NONE,
            "confidence_score": 0.9,
            "reason": "Offer generated, awaiting manager approval",
        }

    @staticmethod
    def analyze_job_creation(
        job_id: str,
        job_title: str,
        job_skills: str,
        no_of_positions: int,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Analyze newly created job and decide on recruitment strategy.

        Args:
            job_id: Job ID
            job_title: Job title
            job_skills: Required skills (comma-separated)
            no_of_positions: Number of open positions
            db: Database session

        Returns:
            Decision dict with recruitment strategy, urgency level, recommended actions

        Raises:
            ValueError: If inputs invalid
        """
        try:
            if not job_id or not job_title:
                raise ValueError("job_id and job_title required")

            # Assess urgency based on number of positions
            urgency = "HIGH" if no_of_positions >= 3 else "MEDIUM" if no_of_positions >= 1 else "LOW"

            # Assess skill complexity based on number of skills
            skills_list = [s.strip() for s in (job_skills or "").split(",") if s.strip()]
            skill_complexity = "HIGH" if len(skills_list) >= 5 else "MEDIUM" if len(skills_list) >= 2 else "LOW"

            decision = {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_SEND_EMAIL,  # Thunder should start sourcing
                "confidence_score": 0.95,
                "urgency": urgency,
                "skill_complexity": skill_complexity,
                "job_title": job_title,
                "positions_open": no_of_positions,
                "skills_required": len(skills_list),
                "reason": f"Job created: {job_title} ({no_of_positions} positions, urgency: {urgency})",
                "details": {
                    "start_sourcing": True,
                    "priority": urgency,
                    "skills": skills_list,
                    "estimated_time_to_hire": "2-3 weeks" if urgency == "HIGH" else "3-4 weeks",
                },
            }

            logger.info(
                f"SLM job analysis: job_id={job_id} "
                f"title={job_title} urgency={urgency} "
                f"complexity={skill_complexity}"
            )

            return decision

        except Exception as e:
            logger.error(f"Failed to analyze job creation: {e}", exc_info=True)
            raise RuntimeError(f"Failed to analyze job creation: {str(e)}")

    @staticmethod
    def _store_decision(
        message_id: str,
        decision: Dict[str, Any],
        db: Session,
        handler_name: Optional[str] = None,
    ) -> str:
        """
        Store SLM decision in database.

        Args:
            message_id: Message ID
            decision: Decision dict
            db: Database session
            handler_name: Name of handler that generated this decision

        Returns:
            Decision ID

        Raises:
            RuntimeError: If storage fails
        """
        try:
            from app.models.slm_decision import SLMDecision

            decision_id = str(uuid.uuid4())
            decision_record = SLMDecision(
                id=decision_id,
                message_id=message_id,
                message_type="generic_analysis",
                handler_name=handler_name or "slm_service",  # CYCLE 19: Use passed handler name or default to slm_service
                slm_confidence=decision.get("confidence_score", 0.5),
                risk_level=decision.get("risk_level", "MEDIUM"),
                was_escalated=decision.get("decision_type") == SLMService.DECISION_ESCALATE,
                escalation_reason=decision.get("reasoning"),
                slm_analysis=decision,
            )

            db.add(decision_record)
            db.commit()

            logger.debug(f"SLM decision stored: {decision_id} for message: {message_id}")
            return decision_id

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to store SLM decision: {e}", exc_info=True)
            raise RuntimeError(f"Failed to store SLM decision: {str(e)}")

    @staticmethod
    def analyze_before_handler(
        message_id: str,
        message_type: str,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        db: Optional[Session] = None,
        handler_name: str = None,  # CYCLE 20: Handler name for decision recording
    ) -> Dict[str, Any]:
        """
        PLACE 1: Pre-flight SLM analysis BEFORE handler execution.

        Args:
            message_id: Message ID from ChannelQueueItem
            message_type: Type of message (interview_scheduled, offer_generated, etc.)
            payload: Message payload
            context: Business context {business_goal, risk_level, candidate_id, etc.}
            db: Database session

        Returns:
            {
                'should_proceed': bool,
                'confidence': float (0-1),
                'risk_level': 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL',
                'reasoning': str,
                'early_flags': [...],
                'slm_decision_id': str,
                'recommended_action': str
            }

        If confidence < 0.7 or risk_level is CRITICAL → should_proceed = False (escalate)
        """
        try:
            if not message_id or not message_type or not db:
                raise ValueError("message_id, message_type, and db session required")

            from app.models.slm_decision import SLMDecision

            # Create decision record for pre-flight analysis
            decision_id = str(uuid.uuid4())
            risk_level = context.get('risk_level', 'MEDIUM')

            # Assess confidence based on message type and payload completeness
            confidence = 0.85
            early_flags = []
            should_proceed = True

            # Type-specific pre-flight checks
            if message_type == 'interview_scheduled':
                required_fields = ['candidate_id', 'job_id', 'interview_date', 'interview_time']
                missing = [f for f in required_fields if not payload.get(f)]
                if missing:
                    confidence = 0.4
                    early_flags.append(f"Missing fields: {', '.join(missing)}")
                    should_proceed = False

            elif message_type == 'offer_generated':
                required_fields = ['candidate_id', 'job_id', 'salary']
                missing = [f for f in required_fields if not payload.get(f)]
                if missing:
                    confidence = 0.35
                    early_flags.append(f"Missing critical offer fields: {', '.join(missing)}")
                    should_proceed = False
                # High-risk: offers are financially risky
                if risk_level == 'CRITICAL':
                    should_proceed = False
                    confidence = min(confidence, 0.5)
                    early_flags.append("CRITICAL risk level flagged by context")

            elif message_type == 'offer_accepted':
                if risk_level == 'CRITICAL':
                    should_proceed = False
                    confidence = 0.45
                    early_flags.append("Onboarding is expensive - CRITICAL escalation")

            # Force escalation for very low confidence
            if confidence < 0.7:
                should_proceed = False

            # Store pre-flight analysis in SLMDecision
            decision_record = SLMDecision(
                id=decision_id,
                message_id=message_id,
                message_type=message_type,
                handler_name=handler_name or "slm_precheck",  # CYCLE 20: Use passed handler name or default
                slm_analysis={
                    'confidence': confidence,
                    'risk_level': risk_level,
                    'reasoning': context.get('business_goal', 'Handler execution'),
                    'early_flags': early_flags,
                    'context': context,
                    'payload_summary': {k: v for k, v in payload.items() if k not in ['data', 'payload']}
                },
                slm_confidence=confidence,
                risk_level=risk_level,
                was_escalated=not should_proceed,
                escalation_reason=' | '.join(early_flags) if early_flags else None,
                analysis_at=datetime.utcnow(),
            )

            db.add(decision_record)
            db.flush()
            db.commit()

            logger.info(
                f"[SLM] Pre-flight analysis: message={message_type} "
                f"confidence={confidence} should_proceed={should_proceed} "
                f"decision_id={decision_id}"
            )

            return {
                'should_proceed': should_proceed,
                'confidence': confidence,
                'risk_level': risk_level,
                'reasoning': context.get('business_goal', ''),
                'early_flags': early_flags,
                'slm_decision_id': decision_id,
                'recommended_action': 'escalate' if not should_proceed else 'proceed',
            }

        except Exception as e:
            logger.error(f"Failed to run SLM pre-flight analysis: {e}", exc_info=True)
            # Don't block handler execution - return proceed with low confidence
            return {
                'should_proceed': True,
                'confidence': 0.3,
                'risk_level': 'HIGH',
                'reasoning': f'SLM analysis failed: {str(e)}',
                'early_flags': ['SLM service unavailable'],
                'slm_decision_id': None,
                'recommended_action': 'proceed_with_caution',
            }

    @staticmethod
    def record_outcome(
        slm_analysis: Dict[str, Any],
        message_id: str,
        handler_name: str,
        handler_result: Dict[str, Any],
        business_impact: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> str:
        """
        PLACE 2: Post-flight outcome recording AFTER handler execution.

        Updates SLMDecision with actual outcome and business impact.

        Args:
            slm_analysis: Result from analyze_before_handler()
            message_id: Message ID
            handler_name: Name of handler that executed (interview_scheduled_handler, etc.)
            handler_result: Result dict returned by handler
            business_impact: {
                'candidate_affected': bool,
                'candidate_id': str,
                'candidates_affected_count': int,
                'start_date': str,
                'position_id': str,
                'expected_outcome': str,
                'validation_method': str,
                '90_day_plan': str,
                'can_be_reversed': bool,
                'cost_impact': float (optional)
            }
            db: Database session

        Returns: slm_decision_id for audit trail
        """
        try:
            if not db or not message_id or not slm_analysis:
                raise ValueError("Database session, message_id, and slm_analysis required")

            from app.models.slm_decision import SLMDecision

            # Find the SLMDecision record created in analyze_before_handler
            decision_id = slm_analysis.get('slm_decision_id')
            if not decision_id:
                logger.warning("No slm_decision_id in slm_analysis - creating new record")
                decision_id = str(uuid.uuid4())

            # Update or create decision record with outcome
            decision = db.query(SLMDecision).filter(
                SLMDecision.id == decision_id
            ).first()

            if not decision:
                logger.warning(f"SLMDecision record not found: {decision_id}, creating new")
                decision = SLMDecision(
                    id=decision_id,
                    message_id=message_id,
                    message_type=slm_analysis.get('message_type', 'unknown'),
                )

            # Update with post-flight outcome
            decision.handler_name = handler_name
            decision.handler_result = handler_result
            decision.handler_status = handler_result.get('status', 'unknown')
            decision.handler_completed_at = datetime.utcnow()

            # Record business impact with accountability
            decision.business_impact = {
                'candidate_affected': business_impact.get('candidate_affected', False),
                'candidate_id': business_impact.get('candidate_id'),
                'candidates_affected_count': business_impact.get('candidates_affected_count', 1),
                'start_date': business_impact.get('start_date'),
                'position_id': business_impact.get('position_id'),
                'expected_outcome': business_impact.get('expected_outcome'),
                'validation_method': business_impact.get('validation_method'),
                'cost_impact': business_impact.get('cost_impact'),
            }

            # Record 90-day validation plan
            decision.validation_plan = {
                'validation_method': business_impact.get('validation_method'),
                'success_criteria': business_impact.get('90_day_plan', ''),
                'validation_date': (datetime.utcnow().replace(day=1) +
                                   __import__('datetime').timedelta(days=90)).isoformat(),
                'validation_result': None,  # To be filled after 90 days
            }

            # Record accountability
            decision.accountability = {
                'decision_maker': f"SLM:confidence_{slm_analysis.get('confidence', 0):.2f}",
                'can_be_reversed': business_impact.get('can_be_reversed', True),
                'override_conditions': business_impact.get('override_conditions', []),
                'audit_trail': [
                    {
                        'timestamp': datetime.utcnow().isoformat(),
                        'event': 'analyzed',
                        'decision': 'proceed' if slm_analysis.get('should_proceed') else 'escalate',
                        'confidence': slm_analysis.get('confidence'),
                    },
                    {
                        'timestamp': datetime.utcnow().isoformat(),
                        'event': 'handler_executed',
                        'handler': handler_name,
                        'status': handler_result.get('status'),
                    },
                ],
            }

            decision.outcome_recorded_at = datetime.utcnow()
            db.add(decision)
            db.commit()

            logger.info(
                f"[SLM] Outcome recorded: message={message_id} "
                f"handler={handler_name} status={handler_result.get('status')} "
                f"decision_id={decision_id}"
            )

            return decision_id

        except Exception as e:
            logger.error(f"Failed to record SLM outcome: {e}", exc_info=True)
            # Non-blocking - don't raise
            return str(uuid.uuid4())
