"""Architect Escalation Service - Route dead-letter issues to architect analysis
PHASE 3: Dead-Letter Autonomous Escalation to Architect

Responsibilities:
1. Package dead-letter message info for architect review
2. Route to architect agent with context
3. Track escalation status
4. Apply auto-fixes if architect recommends them
"""
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.error_history_service import ErrorHistoryService
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class ArchitectEscalationService:
    """
    Routes dead-letter issues to architect analysis and tracks remediation.

    When a message reaches DEAD_LETTER after max retries:
    1. Analyze error pattern (is it code bug, config, rate-limit, transient?)
    2. Check if batch failure (5+ same error) → escalate to architect for batch analysis
    3. Architect determines: auto-fix, config change, retry strategy, or code fix
    4. Execute auto-fixes, escalate non-automatable issues to ops team
    """

    @staticmethod
    def analyze_for_escalation(
        dead_letter_message_id: str,
        task_type: str,
        error_message: str,
        retry_count: int,
        created_at: datetime,
        payload: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Analyze a dead-letter message to determine escalation routing.

        Args:
            dead_letter_message_id: ID of the dead-lettered message
            task_type: Task type (e.g., 'send_email_to_candidate')
            error_message: The error that caused dead-letter
            retry_count: Number of retries attempted
            created_at: When the message was first created
            payload: Original message payload
            db: Database session

        Returns:
            Analysis dict with routing decision and recommended actions
        """
        should_close = db is None
        if db is None:
            db = SessionLocal()

        try:
            # Classify the error
            error_type = ErrorHistoryService.classify_error(error_message)

            # Check for batch failure
            is_batch = ErrorHistoryService.detect_batch_failure(
                task_type=task_type,
                error_substring=error_message[:50],  # Use first 50 chars
                window_minutes=60,
                threshold=5,
                db=db
            )

            # Get error trend
            trend = ErrorHistoryService.get_error_trend(task_type, lookback_hours=24, db=db)

            # Get historical context
            similar_errors = ErrorHistoryService.find_similar_errors(
                task_type=task_type,
                error_substring=error_message[:50],
                lookback_hours=168,
                limit=10,
                db=db
            )

            # Calculate age of message
            age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600

            # Determine routing and recommendations
            analysis = {
                'dead_letter_message_id': dead_letter_message_id,
                'task_type': task_type,
                'error_type': error_type,
                'error_message': error_message[:500],  # Truncate for safety
                'retry_count': retry_count,
                'message_age_hours': round(age_hours, 2),
                'is_batch_failure': is_batch,
                'batch_count': len(similar_errors),
                'trend': trend,
                'routing_decision': ArchitectEscalationService._determine_routing(
                    error_type, is_batch, retry_count, trend
                ),
                'recommended_actions': ArchitectEscalationService._recommend_actions(
                    error_type, is_batch, retry_count, trend, task_type
                ),
                'similar_errors': similar_errors[:5],  # Top 5 similar errors
                'escalation_timestamp': datetime.utcnow().isoformat()
            }

            logger.info(
                f"[ArchitectEscalation] Analyzed dead-letter {dead_letter_message_id}: "
                f"type={error_type}, routing={analysis['routing_decision']}, "
                f"batch={is_batch}"
            )

            return analysis

        finally:
            if should_close:
                db.close()

    @staticmethod
    def _determine_routing(
        error_type: str,
        is_batch: bool,
        retry_count: int,
        trend: Dict[str, Any]
    ) -> str:
        """
        Determine where to route the dead-letter message.

        Returns routing key: 'auto_fix', 'architect_batch', 'architect_single', 'ops_alert'
        """
        # Batch failures always go to architect for analysis
        if is_batch:
            return 'architect_batch'

        # Config errors might be auto-fixable
        if error_type == 'config':
            return 'auto_fix'

        # Rate limits might be fixable with backoff adjustment
        if error_type == 'rate_limit':
            return 'auto_fix'

        # Code bugs need architect review
        if error_type == 'code_bug':
            return 'architect_single'

        # High failure rate (>50% failures) needs architect attention
        if trend['failure_rate'] > 50:
            return 'architect_single'

        # Default: ops alert for manual review
        return 'ops_alert'

    @staticmethod
    def _recommend_actions(
        error_type: str,
        is_batch: bool,
        retry_count: int,
        trend: Dict[str, Any],
        task_type: str
    ) -> List[str]:
        """
        Recommend specific actions based on error analysis.
        """
        actions = []

        if error_type == 'transient':
            actions.append('Increase MAX_RETRIES from 6 to 8')
            actions.append('Reduce INITIAL_RETRY_DELAY to 1s')
            actions.append('Enable exponential backoff with jitter')

        elif error_type == 'config':
            actions.append('Verify API credentials in .env')
            actions.append('Check configuration file syntax')
            actions.append('Validate domain/URL settings')
            actions.append('Test credentials with provider API')

        elif error_type == 'rate_limit':
            actions.append('Increase backoff delays for this handler')
            actions.append('Implement exponential backoff')
            actions.append('Add request batching/queueing')
            actions.append('Contact provider about rate limit increase')

        elif error_type == 'code_bug':
            actions.append('Review recent code changes in this handler')
            actions.append('Check for breaking API changes')
            actions.append('Add error logging for debugging')
            actions.append('Write regression test for this error')

        # Batch-specific actions
        if is_batch:
            actions.append('This is a batch failure - likely systemic issue')
            actions.append('Check provider status page')
            actions.append('Verify network connectivity')
            actions.append('Review logs for common error pattern')

        # Add monitoring action if failure rate high
        if trend['failure_rate'] > 50:
            actions.append(f"Failure rate is {trend['failure_rate']}% - investigate immediately")

        if not actions:
            actions.append('Manual review required - classify error type')

        return actions

    @staticmethod
    def should_escalate_to_architect(
        is_batch: bool,
        error_type: str,
        failure_rate: float,
        retry_count: int
    ) -> bool:
        """
        Quick check: does this dead-letter need architect review?

        Returns True if should escalate, False if can auto-handle
        """
        # Always escalate batch failures
        if is_batch:
            return True

        # Always escalate code bugs
        if error_type == 'code_bug':
            return True

        # Always escalate if high failure rate
        if failure_rate > 50:
            return True

        # Otherwise can potentially auto-handle or alert ops
        return False

    @staticmethod
    def prepare_architect_request(
        analysis: Dict[str, Any],
        messages_in_batch: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Prepare a structured request for architect analysis.

        Args:
            analysis: Result from analyze_for_escalation()
            messages_in_batch: List of similar messages (for batch analysis)

        Returns:
            Request dict formatted for architect agent
        """
        return {
            'escalation_type': analysis['routing_decision'],
            'task_type': analysis['task_type'],
            'error_type': analysis['error_type'],
            'error_summary': analysis['error_message'][:200],
            'is_batch_failure': analysis['is_batch_failure'],
            'batch_size': len(messages_in_batch) if messages_in_batch else 1,
            'samples': messages_in_batch[:5],  # Top 5 samples for architect to analyze
            'trend_data': analysis['trend'],
            'recommended_actions': analysis['recommended_actions'],
            'escalation_timestamp': analysis['escalation_timestamp'],
            'instructions': f"""
Analyze this dead-letter escalation:

Task Type: {analysis['task_type']}
Error Type: {analysis['error_type']}
Error Message: {analysis['error_message'][:500]}
Batch Failure: {analysis['is_batch_failure']}
Failure Rate (24h): {analysis['trend']['failure_rate']}%

Similar Errors (last 7 days): {len(analysis['similar_errors'])}
Message Age: {analysis['message_age_hours']} hours

Determine:
1. Is this a transient issue or systemic problem?
2. What immediate action should be taken?
3. What code changes are needed (if any)?
4. Should retry strategy be adjusted?
5. Is this a configuration issue that can be auto-fixed?

Recommended Actions to Consider:
{chr(10).join(f"- {action}" for action in analysis['recommended_actions'])}

Provide specific, actionable recommendations for resolution.
"""
        }
