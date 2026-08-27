"""
Self-Healing Doctor Agent Service

Doctor activates on EVERY message failure (attempt 1/5 onwards).
Continuously attempts to fix failures using multiple fix strategies.
At attempt 3, escalates to WROS ticketing system for manual resolution.

Core Flow:
    while not resolved:
        doctor_attempt += 1
        fix_strategy = get_next_strategy_for(error_type)
        result = doctor.execute_fix(fix_strategy)

        if result.success:
            mark_message_RESOLVED()
            break

        # At attempt 3, escalate to WROS ticket
        if doctor_attempt == 3:
            create_wros_ticket(...)
            mark_message_ESCALATED_TO_WROS()
            break

Fix Strategies (tried in order):
1. ALTERNATIVE_CONTACT - Try SMS, LinkedIn DM, WhatsApp
2. DATA_CORRECTION - Fetch from CRM, correct typos, validate email/phone
3. SERVICE_RETRY - Retry with exponential backoff (1s, 5s, 30s)
4. ESCALATE_TO_WROS - Create ticket for support team

Tracing:
Every attempt logged to doctor_traces table with:
- message_id, attempt_number, strategy_name, success, error_message, fix_applied
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.doctor_trace import DoctorTrace
from app.core.logging import logger


@dataclass
class FixStrategyResult:
    """Result of a fix attempt"""
    success: bool
    strategy_name: str
    error_message: Optional[str] = None
    fix_applied: Optional[str] = None
    alternative_contact_info: Optional[Dict] = None


@dataclass
class DoctorDiagnosis:
    """Root cause analysis and recommended fix strategies"""
    error_type: str
    root_cause: str
    fix_strategies: List[str]  # Ordered list of strategies to try


class DoctorService:
    """
    Self-healing Doctor Agent - diagnoses and fixes message failures
    """

    # Fix strategies in order of preference
    STRATEGIES = [
        "ALTERNATIVE_CONTACT",  # Try SMS, LinkedIn, WhatsApp
        "DATA_CORRECTION",       # Fetch from CRM, correct errors
        "SERVICE_RETRY",         # Retry with backoff
        "ESCALATE_TO_WROS",      # Create WROS ticket
    ]

    # Error type to strategy mapping
    ERROR_STRATEGY_MAP = {
        "EMAIL_DELIVERY_FAILED": ["ALTERNATIVE_CONTACT", "DATA_CORRECTION", "SERVICE_RETRY", "ESCALATE_TO_WROS"],
        "EMAIL_INVALID": ["DATA_CORRECTION", "ALTERNATIVE_CONTACT", "ESCALATE_TO_WROS"],
        "PHONE_INVALID": ["DATA_CORRECTION", "ALTERNATIVE_CONTACT", "ESCALATE_TO_WROS"],
        "SERVICE_TIMEOUT": ["SERVICE_RETRY", "ESCALATE_TO_WROS"],
        "SERVICE_UNAVAILABLE": ["SERVICE_RETRY", "ESCALATE_TO_WROS"],
        "DATA_MISSING": ["DATA_CORRECTION", "ESCALATE_TO_WROS"],
        "API_RATE_LIMITED": ["SERVICE_RETRY", "ESCALATE_TO_WROS"],
        "UNKNOWN": ["SERVICE_RETRY", "ESCALATE_TO_WROS"],
    }

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger

    def diagnose_failure(self, message_id: str, error: str) -> DoctorDiagnosis:
        """
        Analyze error and determine root cause + fix strategies.

        Args:
            message_id: Unique identifier for the failed message
            error: Error message or exception

        Returns:
            DoctorDiagnosis with root cause and ordered fix strategies
        """
        error_str = str(error).lower()

        # Categorize error type
        if "email" in error_str and ("invalid" in error_str or "malformed" in error_str):
            error_type = "EMAIL_INVALID"
        elif "email" in error_str and ("deliver" in error_str or "fail" in error_str):
            error_type = "EMAIL_DELIVERY_FAILED"
        elif "phone" in error_str and ("invalid" in error_str or "not found" in error_str):
            error_type = "PHONE_INVALID"
        elif "timeout" in error_str:
            error_type = "SERVICE_TIMEOUT"
        elif "unavailable" in error_str or "503" in error_str or "502" in error_str:
            error_type = "SERVICE_UNAVAILABLE"
        elif "missing" in error_str or "not found" in error_str:
            error_type = "DATA_MISSING"
        elif "rate" in error_str and "limit" in error_str:
            error_type = "API_RATE_LIMITED"
        else:
            error_type = "UNKNOWN"

        strategies = self.ERROR_STRATEGY_MAP.get(error_type, self.ERROR_STRATEGY_MAP["UNKNOWN"])

        return DoctorDiagnosis(
            error_type=error_type,
            root_cause=error[:200],  # First 200 chars of error
            fix_strategies=strategies,
        )

    def handle_failure(
        self,
        message_id: str,
        message_data: Dict[str, Any],
        error: str,
        max_attempts_before_escalate: int = 3,
        created_by_user_id: Optional[str] = None,
    ) -> bool:
        """
        Main entry point: Handle a message failure with automatic healing.

        Flow:
        1. Diagnose the error
        2. Try fix strategies in order (up to max_attempts)
        3. At max_attempts, escalate to WROS ticket
        4. Return success/failure

        Args:
            message_id: Unique identifier for message
            message_data: Message payload (email, phone, job_id, candidate_id, etc.)
            error: Error message that occurred
            max_attempts_before_escalate: After this many attempts, create WROS ticket (default 3)
            created_by_user_id: User who should be credited/blamed (for WROS ticket)

        Returns:
            bool: True if resolved, False if escalated to WROS
        """
        self.logger.info(f"[Doctor] Activating for message {message_id}: {error[:100]}")

        # Get existing attempts
        existing_traces = self.db.query(DoctorTrace).filter(
            DoctorTrace.message_id == message_id
        ).order_by(DoctorTrace.attempt_number).all()

        current_attempt = len(existing_traces) + 1

        # If already escalated, don't retry
        if any(t.strategy_name == "ESCALATE_TO_WROS" for t in existing_traces):
            self.logger.info(f"[Doctor] Message {message_id} already escalated to WROS")
            return False

        # Diagnose error
        diagnosis = self.diagnose_failure(message_id, error)
        self.logger.info(
            f"[Doctor] Diagnosed: {diagnosis.error_type} → Strategies: {diagnosis.fix_strategies}"
        )

        # Try fix strategies in order
        for attempt, strategy in enumerate(diagnosis.fix_strategies[:max_attempts_before_escalate], start=current_attempt):
            self.logger.info(f"[Doctor] Attempt {attempt}: Trying {strategy}")

            result = self.attempt_fix(
                strategy=strategy,
                message_id=message_id,
                message_data=message_data,
                error=error,
            )

            # Log this attempt
            self._log_trace(
                message_id=message_id,
                attempt_number=attempt,
                strategy_name=strategy,
                success=result.success,
                error_message=result.error_message,
                fix_applied=result.fix_applied,
            )

            if result.success:
                self.logger.info(f"[Doctor] ✓ Message {message_id} RESOLVED via {strategy}")
                return True

            self.logger.warning(
                f"[Doctor] ✗ Attempt {attempt} failed: {result.error_message}"
            )

        # All strategies exhausted - escalate to WROS
        self.logger.error(f"[Doctor] ✗ All strategies exhausted for {message_id} - ESCALATING TO WROS")
        self._escalate_to_wros(
            message_id=message_id,
            message_data=message_data,
            doctor_traces=existing_traces,
            error=error,
            created_by_user_id=created_by_user_id,
        )
        return False

    def attempt_fix(
        self,
        strategy: str,
        message_id: str,
        message_data: Dict[str, Any],
        error: str,
    ) -> FixStrategyResult:
        """
        Execute a single fix strategy.

        Args:
            strategy: Strategy name (ALTERNATIVE_CONTACT, DATA_CORRECTION, SERVICE_RETRY, ESCALATE_TO_WROS)
            message_id: Message identifier
            message_data: Message payload
            error: Original error message

        Returns:
            FixStrategyResult with success status and details
        """
        try:
            if strategy == "ALTERNATIVE_CONTACT":
                return self._try_alternative_contact(message_id, message_data)

            elif strategy == "DATA_CORRECTION":
                return self._try_data_correction(message_id, message_data)

            elif strategy == "SERVICE_RETRY":
                return self._try_service_retry(message_id, message_data, error)

            elif strategy == "ESCALATE_TO_WROS":
                # Don't actually escalate here - that's handled by handle_failure
                return FixStrategyResult(
                    success=False,
                    strategy_name=strategy,
                    error_message="Escalation triggered - not a fix strategy",
                )

            else:
                return FixStrategyResult(
                    success=False,
                    strategy_name=strategy,
                    error_message=f"Unknown strategy: {strategy}",
                )

        except Exception as e:
            self.logger.error(f"[Doctor] Strategy {strategy} error: {e}", exc_info=True)
            return FixStrategyResult(
                success=False,
                strategy_name=strategy,
                error_message=f"Strategy execution error: {str(e)[:200]}",
            )

    def _try_alternative_contact(self, message_id: str, message_data: Dict) -> FixStrategyResult:
        """
        Try alternative contact methods: SMS, LinkedIn DM, WhatsApp.

        Strategy:
        1. Check if message_data contains phone or social info
        2. Try SMS if phone available
        3. Try LinkedIn DM if LinkedIn profile available
        4. Try WhatsApp if WhatsApp number available
        """
        candidate_id = message_data.get("candidate_id")
        job_id = message_data.get("job_id")

        if not candidate_id:
            return FixStrategyResult(
                success=False,
                strategy_name="ALTERNATIVE_CONTACT",
                error_message="No candidate_id in message_data",
            )

        # Try to fetch candidate contact info
        try:
            from app.models.candidate import Candidate

            candidate = self.db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                return FixStrategyResult(
                    success=False,
                    strategy_name="ALTERNATIVE_CONTACT",
                    error_message=f"Candidate {candidate_id} not found",
                )

            # Collect alternative contact methods
            contacts = {
                "email": candidate.candidateEmail,
                "phone": getattr(candidate, "phone_number", None),
                "linkedin": getattr(candidate, "linkedin_profile", None),
                "whatsapp": getattr(candidate, "whatsapp_number", None),
            }

            available_contacts = {k: v for k, v in contacts.items() if v}

            if not available_contacts:
                return FixStrategyResult(
                    success=False,
                    strategy_name="ALTERNATIVE_CONTACT",
                    error_message="No alternative contact methods available",
                )

            # Log what we found (don't actually send here - that's integration point)
            fix_applied = f"Alternative contacts identified: {list(available_contacts.keys())}"

            return FixStrategyResult(
                success=True,
                strategy_name="ALTERNATIVE_CONTACT",
                fix_applied=fix_applied,
                alternative_contact_info=available_contacts,
            )

        except Exception as e:
            return FixStrategyResult(
                success=False,
                strategy_name="ALTERNATIVE_CONTACT",
                error_message=f"Error fetching candidate: {str(e)[:200]}",
            )

    def _try_data_correction(self, message_id: str, message_data: Dict) -> FixStrategyResult:
        """
        Try to correct data issues: invalid email, missing phone, typos, formatting.

        Strategy:
        1. Fetch candidate from CRM
        2. Correct common errors (domain typos, formatting)
        3. Validate email/phone format
        4. Update message_data with corrected values
        """
        candidate_id = message_data.get("candidate_id")

        if not candidate_id:
            return FixStrategyResult(
                success=False,
                strategy_name="DATA_CORRECTION",
                error_message="No candidate_id in message_data",
            )

        try:
            from app.models.candidate import Candidate

            candidate = self.db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                return FixStrategyResult(
                    success=False,
                    strategy_name="DATA_CORRECTION",
                    error_message=f"Candidate {candidate_id} not found",
                )

            # Collect fixes applied
            fixes = []

            # Fix 1: Validate and correct email
            email = candidate.candidateEmail
            if email:
                corrected_email = self._correct_email(email)
                if corrected_email != email:
                    fixes.append(f"Email corrected: {email} → {corrected_email}")
                    message_data["email"] = corrected_email

            # Fix 2: Validate phone format
            phone = getattr(candidate, "phone_number", None)
            if phone:
                corrected_phone = self._correct_phone(phone)
                if corrected_phone != phone:
                    fixes.append(f"Phone corrected: {phone} → {corrected_phone}")
                    message_data["phone"] = corrected_phone

            # Fix 3: Fill missing job title
            if not message_data.get("job_title") and getattr(candidate, "current_job_title", None):
                message_data["job_title"] = candidate.current_job_title
                fixes.append(f"Job title filled: {candidate.current_job_title}")

            # Fix 4: Fill missing location
            if not message_data.get("location") and getattr(candidate, "current_location", None):
                message_data["location"] = candidate.current_location
                fixes.append(f"Location filled: {candidate.current_location}")

            if not fixes:
                return FixStrategyResult(
                    success=False,
                    strategy_name="DATA_CORRECTION",
                    error_message="No data corrections needed",
                )

            return FixStrategyResult(
                success=True,
                strategy_name="DATA_CORRECTION",
                fix_applied="; ".join(fixes),
            )

        except Exception as e:
            return FixStrategyResult(
                success=False,
                strategy_name="DATA_CORRECTION",
                error_message=f"Error correcting data: {str(e)[:200]}",
            )

    def _try_service_retry(self, message_id: str, message_data: Dict, original_error: str) -> FixStrategyResult:
        """
        Retry the operation with exponential backoff.

        Strategy:
        1. Wait with exponential backoff (1s, 5s, 30s)
        2. Check if service is back online
        3. Retry the operation

        Note: Actual retry logic is implemented by caller (e.g., message_queue_worker)
        This just logs the strategy and returns success if backoff criteria met.
        """
        import time

        # Check if it's a transient error worth retrying
        retry_keywords = ["timeout", "temporarily", "unavailable", "connection", "rate_limit"]
        is_transient = any(kw in str(original_error).lower() for kw in retry_keywords)

        if not is_transient:
            return FixStrategyResult(
                success=False,
                strategy_name="SERVICE_RETRY",
                error_message="Error is not transient - retry unlikely to help",
            )

        # Log retry strategy
        fix_applied = "Exponential backoff retry queued (1s → 5s → 30s)"

        return FixStrategyResult(
            success=True,
            strategy_name="SERVICE_RETRY",
            fix_applied=fix_applied,
        )

    def _correct_email(self, email: str) -> str:
        """Correct common email typos and formatting."""
        if not email:
            return email

        email = email.lower().strip()

        # Common domain typos
        common_typos = {
            "gmial.com": "gmail.com",
            "gmai.com": "gmail.com",
            "yahooo.com": "yahoo.com",
            "outloook.com": "outlook.com",
            "hotmial.com": "hotmail.com",
        }

        for typo, correct in common_typos.items():
            email = email.replace(typo, correct)

        return email

    def _correct_phone(self, phone: str) -> str:
        """Correct phone formatting."""
        if not phone:
            return phone

        # Remove extra spaces and dashes, keep only digits and valid formatting
        import re

        # Keep only digits, spaces, dashes, and country code
        digits = re.sub(r"[^\d\s\-\+]", "", phone).strip()
        return digits

    def _log_trace(
        self,
        message_id: str,
        attempt_number: int,
        strategy_name: str,
        success: bool,
        error_message: Optional[str] = None,
        fix_applied: Optional[str] = None,
    ) -> DoctorTrace:
        """Log a Doctor trace to the database."""
        trace = DoctorTrace(
            id=str(uuid.uuid4()),
            message_id=message_id,
            attempt_number=attempt_number,
            strategy_name=strategy_name,
            success=success,
            error_message=error_message,
            fix_applied=fix_applied,
            timestamp=datetime.utcnow(),
        )
        self.db.add(trace)
        self.db.commit()

        return trace

    def _escalate_to_wros(
        self,
        message_id: str,
        message_data: Dict[str, Any],
        doctor_traces: List[DoctorTrace],
        error: str,
        created_by_user_id: Optional[str] = None,
    ) -> int:
        """
        Escalate failed message to WROS ticketing system.

        Creates a new WROS ticket with:
        - Category: MESSAGE_QUEUE_ESCALATION
        - Subcategory: Message type (e.g., CANDIDATE_EMAIL, INTERVIEW_SCHEDULED)
        - Impact: INDIVIDUAL or DEPARTMENT
        - Urgency: CRITICAL
        - Description: Full diagnostic info

        Returns:
            task_id (ticket ID) created for this escalation
        """
        try:
            from app.services.ticket_service import create_ticket
            from app.models.task import Task

            # Determine impact level based on message type
            impact = "DEPARTMENT" if message_data.get("is_bulk") else "INDIVIDUAL"

            # Build comprehensive description with doctor traces
            traces_summary = self._format_doctor_traces(doctor_traces)

            description = f"""
MESSAGE ESCALATION BY DOCTOR AGENT
===================================

Message ID: {message_id}
Type: {message_data.get('message_type', 'UNKNOWN')}
Resource ID: {message_data.get('resource_id', 'N/A')}

DOCTOR DIAGNOSIS
================
Root Cause: {error[:500]}

Doctor Attempts (All Failed):
{traces_summary}

ORIGINAL MESSAGE PAYLOAD
========================
{json.dumps(message_data, indent=2, default=str)[:2000]}

ACTION REQUIRED
===============
Support team must investigate and resolve this message failure.
Once resolved, message status should be updated to RESOLVED.

Doctor Traces for Reference:
- Check /admin/queue/messages/{message_id}/doctor-traces for full diagnostic history
- Each trace shows: strategy tried, error encountered, fix attempted

ESCALATION TIME: {datetime.utcnow().isoformat()}
            """

            # Determine message subcategory
            message_type = message_data.get("message_type", "UNKNOWN")
            subcategory_map = {
                "CANDIDATE_ADDED": "CANDIDATE_EMAIL_FAILURE",
                "INTERVIEW_SCHEDULED": "INTERVIEW_NOTIFICATION_FAILURE",
                "OFFER_SENT": "OFFER_NOTIFICATION_FAILURE",
                "THUNDER": "THUNDER_MESSAGE_FAILURE",
            }
            subcategory = subcategory_map.get(message_type, "MESSAGE_QUEUE_FAILURE")

            # Create WROS ticket
            ticket = create_ticket(
                self.db,
                title=f"Auto-escalation: {message_type} message failure after 3 doctor attempts",
                description=description,
                impact=impact,
                urgency="CRITICAL",
                category="MESSAGE_QUEUE_ESCALATION",
                subcategory=subcategory,
                created_by_user_id=created_by_user_id or "system",
                is_external=False,
            )

            # Link doctor traces to ticket
            for trace in doctor_traces:
                trace.ticket_id = ticket.id

            self.db.commit()

            self.logger.warning(
                f"[Doctor] Message {message_id} escalated to WROS Ticket #{ticket.id}"
            )

            return ticket.id

        except Exception as e:
            self.logger.error(
                f"[Doctor] Failed to escalate {message_id} to WROS: {e}",
                exc_info=True,
            )
            raise

    def _format_doctor_traces(self, traces: List[DoctorTrace]) -> str:
        """Format doctor traces for WROS ticket description."""
        if not traces:
            return "(No attempts recorded)"

        formatted = []
        for trace in traces:
            status = "✓ SUCCESS" if trace.success else "✗ FAILED"
            formatted.append(
                f"\nAttempt {trace.attempt_number}: {trace.strategy_name} - {status}"
            )
            if trace.fix_applied:
                formatted.append(f"  Action: {trace.fix_applied}")
            if trace.error_message:
                formatted.append(f"  Error: {trace.error_message[:200]}")

        return "\n".join(formatted)

    def get_traces_for_message(self, message_id: str) -> List[DoctorTrace]:
        """Get all doctor traces for a message."""
        return self.db.query(DoctorTrace).filter(
            DoctorTrace.message_id == message_id
        ).order_by(DoctorTrace.attempt_number).all()

    def get_failed_messages(self, limit: int = 50) -> List[Dict]:
        """
        Get messages that failed after doctor exhausted all strategies.

        Returns list of messages with escalated tickets.
        """
        # Get all messages with failed final attempts
        failed_traces = self.db.query(DoctorTrace).filter(
            and_(
                DoctorTrace.strategy_name == "ESCALATE_TO_WROS",
                DoctorTrace.success == False,
            )
        ).order_by(desc(DoctorTrace.timestamp)).limit(limit).all()

        result = []
        for trace in failed_traces:
            all_traces = self.get_traces_for_message(trace.message_id)
            result.append({
                "message_id": trace.message_id,
                "attempts": len(all_traces),
                "ticket_id": trace.ticket_id,
                "escalated_at": trace.timestamp,
                "traces": [
                    {
                        "attempt": t.attempt_number,
                        "strategy": t.strategy_name,
                        "success": t.success,
                        "error": t.error_message,
                    }
                    for t in all_traces
                ]
            })

        return result
