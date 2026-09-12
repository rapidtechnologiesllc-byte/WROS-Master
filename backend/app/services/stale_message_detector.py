"""Stale Message Detector - Error classification and diagnostics for stuck messages

Analyzes errors, timeouts, and performance issues to classify why a message is stuck
and calculate a safety_score for automatic recovery.
"""
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ErrorClassification(str, Enum):
    """Error types that cause message stalls"""
    TIMEOUT_LOOP = "TIMEOUT_LOOP"  # Handler keeps timing out
    LARGE_PAYLOAD = "LARGE_PAYLOAD"  # Message too large to process atomically
    DB_POOL = "DB_POOL"  # Database connection pool exhausted
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"  # Required service/handler not available
    TRANSACTION_DEADLOCK = "TRANSACTION_DEADLOCK"  # Database transaction deadlock
    STATE_CORRUPTION = "STATE_CORRUPTION"  # Data inconsistency or corruption
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"  # Memory, CPU, or other resource limits
    UNKNOWN = "UNKNOWN"  # Unable to classify


class StaleMessageDetector:
    """Classifies stuck messages and calculates recovery safety scores"""

    @staticmethod
    def classify_error(error_message: str, handler_duration_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Classify an error message to determine root cause.

        Args:
            error_message: Error string from handler
            handler_duration_ms: How long handler ran before failing

        Returns:
            {
                'classification': ErrorClassification,
                'confidence': 0-100 (how confident are we about this classification?),
                'indicators': [list of patterns found],
                'root_cause': 'Human-readable root cause description'
            }
        """
        if not error_message:
            return {
                'classification': ErrorClassification.UNKNOWN,
                'confidence': 0,
                'indicators': [],
                'root_cause': 'No error message available'
            }

        error_lower = error_message.lower()

        # Pattern: Timeout errors (repeated)
        if StaleMessageDetector._match_timeout_pattern(error_lower):
            timeout_count = error_lower.count('timeout') + error_lower.count('timed out')
            return {
                'classification': ErrorClassification.TIMEOUT_LOOP,
                'confidence': 95,
                'indicators': ['timeout', 'timed out', 'deadline exceeded'],
                'root_cause': f'Handler timeout (detected {timeout_count} timeout mentions). Handler may be stuck in infinite loop or blocked on I/O.'
            }

        # Pattern: Large payload / message size errors
        if StaleMessageDetector._match_payload_pattern(error_lower):
            return {
                'classification': ErrorClassification.LARGE_PAYLOAD,
                'confidence': 85,
                'indicators': ['payload', 'size', 'too large', 'memory', 'truncated'],
                'root_cause': 'Message payload too large or complex to process. May exceed handler memory limits.'
            }

        # Pattern: Database pool exhaustion
        if StaleMessageDetector._match_db_pool_pattern(error_lower):
            return {
                'classification': ErrorClassification.DB_POOL,
                'confidence': 90,
                'indicators': ['connection pool', 'no more connections', 'connection timeout', 'db pool'],
                'root_cause': 'Database connection pool exhausted. Other messages are holding connections too long.'
            }

        # Pattern: Missing dependency / handler not found
        if StaleMessageDetector._match_missing_dependency_pattern(error_lower):
            return {
                'classification': ErrorClassification.MISSING_DEPENDENCY,
                'confidence': 88,
                'indicators': ['not found', 'not registered', 'missing', 'no handler', 'undefined'],
                'root_cause': 'Required handler, service, or dependency is not available.'
            }

        # Pattern: Database deadlock
        if StaleMessageDetector._match_deadlock_pattern(error_lower):
            return {
                'classification': ErrorClassification.TRANSACTION_DEADLOCK,
                'confidence': 92,
                'indicators': ['deadlock', 'locked', 'transaction conflict'],
                'root_cause': 'Database transaction deadlock. Multiple messages competing for same rows.'
            }

        # Pattern: Data corruption / state issues
        if StaleMessageDetector._match_state_corruption_pattern(error_lower):
            return {
                'classification': ErrorClassification.STATE_CORRUPTION,
                'confidence': 80,
                'indicators': ['constraint violation', 'foreign key', 'integrity error', 'invalid state'],
                'root_cause': 'Data corruption or invalid state. Message references missing or inconsistent data.'
            }

        # Pattern: Resource exhaustion
        if StaleMessageDetector._match_resource_exhaustion_pattern(error_lower):
            return {
                'classification': ErrorClassification.RESOURCE_EXHAUSTION,
                'confidence': 85,
                'indicators': ['out of memory', 'cpu', 'disk full', 'too many open files'],
                'root_cause': 'System resource limits exceeded. Memory, CPU, or file descriptors exhausted.'
            }

        # Default: Unknown
        return {
            'classification': ErrorClassification.UNKNOWN,
            'confidence': 30,
            'indicators': [],
            'root_cause': f'Unable to classify error: {error_message[:100]}'
        }

    @staticmethod
    def _match_timeout_pattern(error_lower: str) -> bool:
        """Check for timeout patterns"""
        timeout_patterns = [
            r'timeout',
            r'timed out',
            r'deadline exceeded',
            r'handler.*exceeded.*seconds',
            r'connection.*timeout',
        ]
        return any(re.search(pattern, error_lower) for pattern in timeout_patterns)

    @staticmethod
    def _match_payload_pattern(error_lower: str) -> bool:
        """Check for payload/size patterns"""
        payload_patterns = [
            r'payload.*too.*large',
            r'message.*too.*large',
            r'size.*exceed',
            r'memory.*exceed',
            r'truncated.*payload',
            r'out of memory',
        ]
        return any(re.search(pattern, error_lower) for pattern in payload_patterns)

    @staticmethod
    def _match_db_pool_pattern(error_lower: str) -> bool:
        """Check for database pool exhaustion patterns"""
        pool_patterns = [
            r'connection pool.*exhaust',
            r'no more connection',
            r'pool.*overflow',
            r'connection.*limit',
            r'queue.*full',
        ]
        return any(re.search(pattern, error_lower) for pattern in pool_patterns)

    @staticmethod
    def _match_missing_dependency_pattern(error_lower: str) -> bool:
        """Check for missing handler/service patterns"""
        dependency_patterns = [
            r'not.*found',
            r'not.*registered',
            r'no.*handler',
            r'undefined',
            r'no such.*',
            r'missing.*handler',
        ]
        return any(re.search(pattern, error_lower) for pattern in dependency_patterns)

    @staticmethod
    def _match_deadlock_pattern(error_lower: str) -> bool:
        """Check for database deadlock patterns"""
        deadlock_patterns = [
            r'deadlock',
            r'transaction.*conflict',
            r'wait for',
            r'lock.*timeout',
        ]
        return any(re.search(pattern, error_lower) for pattern in deadlock_patterns)

    @staticmethod
    def _match_state_corruption_pattern(error_lower: str) -> bool:
        """Check for data corruption patterns"""
        corruption_patterns = [
            r'constraint.*violation',
            r'foreign key.*fail',
            r'integrity.*error',
            r'invalid.*state',
            r'not.*null',
        ]
        return any(re.search(pattern, error_lower) for pattern in corruption_patterns)

    @staticmethod
    def _match_resource_exhaustion_pattern(error_lower: str) -> bool:
        """Check for resource exhaustion patterns"""
        resource_patterns = [
            r'out of memory',
            r'memory.*error',
            r'cpu.*limit',
            r'disk.*full',
            r'too many open files',
        ]
        return any(re.search(pattern, error_lower) for pattern in resource_patterns)

    @staticmethod
    def calculate_safety_score(
        error_classification: str,
        handler_duration_ms: int,
        retry_count: int,
        message_age_seconds: int,
        error_message: str = "",
    ) -> int:
        """
        Calculate safety_score (0-100) for auto-recovery.

        Higher score = safer to auto-recover
        Lower score = more risky, should escalate to ops

        Args:
            error_classification: Classification from classify_error()
            handler_duration_ms: How long handler ran
            retry_count: How many times has this been retried?
            message_age_seconds: How long has this been stuck?
            error_message: The error message

        Returns:
            0-100 safety score
        """
        score = 50  # Base score

        # Factor 1: Error type safety
        classification_safety = {
            ErrorClassification.TIMEOUT_LOOP: 75,  # Safe to retry with extended timeout
            ErrorClassification.LARGE_PAYLOAD: 70,  # Safe to split and retry
            ErrorClassification.DB_POOL: 85,  # Safe to delay and retry
            ErrorClassification.MISSING_DEPENDENCY: 40,  # Risky - needs investigation
            ErrorClassification.TRANSACTION_DEADLOCK: 65,  # Moderately safe to rollback and retry
            ErrorClassification.STATE_CORRUPTION: 20,  # Very risky - data may be corrupted
            ErrorClassification.RESOURCE_EXHAUSTION: 60,  # Moderately safe to retry after delay
            ErrorClassification.UNKNOWN: 30,  # Risky - don't know what's wrong
        }

        score = classification_safety.get(error_classification, 30)

        # Factor 2: Retry history (more retries = less safe to auto-recover)
        if retry_count >= 5:
            score -= 25  # Already retried many times
        elif retry_count >= 3:
            score -= 15  # Retried a few times

        # Factor 3: Message age (very old messages are riskier)
        if message_age_seconds > 3600:  # > 1 hour
            score -= 20
        elif message_age_seconds > 600:  # > 10 minutes
            score -= 10

        # Factor 4: Handler duration (very long handlers risky)
        if handler_duration_ms > 30000:  # > 30 seconds
            score -= 15

        # Factor 5: Error severity keywords
        severe_keywords = ['corruption', 'deadlock', 'constraint', 'foreign key']
        if any(kw in error_message.lower() for kw in severe_keywords):
            score -= 20

        # Clamp to 0-100
        return max(0, min(100, score))

    @staticmethod
    def diagnose_message(
        message_id: str,
        error_message: str,
        handler_duration_ms: int,
        retry_count: int,
        message_age_seconds: int,
    ) -> Dict[str, Any]:
        """
        Complete diagnosis for a stuck message.

        Returns comprehensive diagnostic data suitable for ops escalation.
        """
        # Classify the error
        classification_result = StaleMessageDetector.classify_error(error_message, handler_duration_ms)
        classification = classification_result['classification']

        # Calculate safety score
        safety_score = StaleMessageDetector.calculate_safety_score(
            error_classification=classification,
            handler_duration_ms=handler_duration_ms,
            retry_count=retry_count,
            message_age_seconds=message_age_seconds,
            error_message=error_message,
        )

        # Determine recommended action
        recommended_action = StaleMessageDetector._recommend_action(
            classification=classification,
            safety_score=safety_score,
            handler_duration_ms=handler_duration_ms,
        )

        return {
            'error_classification': classification,
            'classification_confidence': classification_result.get('confidence', 0),
            'safety_score': safety_score,
            'root_cause': classification_result.get('root_cause', ''),
            'indicators': classification_result.get('indicators', []),
            'recommended_action': recommended_action,
            'diagnostic_summary': f"Message {message_id} stuck for {message_age_seconds}s. "
                                 f"Classification: {classification.value}. "
                                 f"Safety Score: {safety_score}/100. "
                                 f"Recommendation: {recommended_action}"
        }

    @staticmethod
    def _recommend_action(
        classification: str,
        safety_score: int,
        handler_duration_ms: int,
    ) -> str:
        """Recommend action based on classification and safety score"""

        # If safety score is high enough, recommend specific recovery
        if safety_score >= 80:
            if classification == ErrorClassification.TIMEOUT_LOOP:
                return "Retry with extended timeout (60s)"
            elif classification == ErrorClassification.LARGE_PAYLOAD:
                return "Split payload into smaller messages and retry each"
            elif classification == ErrorClassification.DB_POOL:
                return "Delay 30 seconds to allow connections to free up, then retry"
            elif classification == ErrorClassification.TRANSACTION_DEADLOCK:
                return "Rollback transaction state and retry from beginning"

        # If safety score is moderate, escalate with recommendation
        if safety_score >= 60:
            return "Escalate to ops for manual review before recovery"

        # If safety score is low, definitely escalate
        return "Escalate to ops - do not auto-recover without review"
