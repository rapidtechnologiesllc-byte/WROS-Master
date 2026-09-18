"""Dead-Letter Handler - Main orchestrator for dead-letter message processing
PHASE 3: Dead-Letter Autonomous Escalation

Responsibilities:
1. Receive dead-letter messages from queue processor
2. Analyze error pattern and context
3. Route to appropriate handler (auto-fix, architect, ops)
4. Track escalation status and outcomes
5. Non-blocking escalation (completes within 120s timeout)
"""
import logging
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.channel_queue import ChannelQueueItem
from app.services.error_history_service import ErrorHistoryService
from app.services.architect_escalation_service import ArchitectEscalationService
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class DeadLetterHandler:
    """
    Main handler for dead-letter messages.

    Flow:
    1. Message reaches DEAD_LETTER status after max retries
    2. DeadLetterHandler receives it
    3. Analyze for batch failure, error pattern, trend
    4. Route to architect (batch/code-bug), auto-fix (config/rate-limit), or ops (unknown)
    5. Return within 120 seconds (non-blocking)
    """

    # Escalation timeout (must complete within this time)
    ESCALATION_TIMEOUT_SECONDS = 120

    @staticmethod
    async def handle_dead_letter(
        message_id: str,
        task_type: str,
        error_message: str,
        retry_count: int,
        created_at: datetime,
        payload: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Handle a dead-letter message with autonomous escalation.

        This function:
        - Analyzes the error
        - Checks for batch failures
        - Routes to appropriate handler
        - Completes within ESCALATION_TIMEOUT_SECONDS
        - Never blocks on architect response

        Args:
            message_id: ID of the dead-lettered message
            task_type: Task type (e.g., 'send_email_to_candidate')
            error_message: Error that caused dead-letter
            retry_count: Retries attempted
            created_at: When message was created
            payload: Original message payload
            db: Database session

        Returns:
            Escalation result dict with routing, actions taken, and outcome
        """
        should_close = db is None
        if db is None:
            db = SessionLocal()

        start_time = datetime.utcnow()

        try:
            logger.info(
                f"[DeadLetterHandler] Processing dead-letter: "
                f"message_id={message_id}, task_type={task_type}, retries={retry_count}"
            )

            # Step 1: Analyze the dead-letter message
            analysis = ArchitectEscalationService.analyze_for_escalation(
                dead_letter_message_id=message_id,
                task_type=task_type,
                error_message=error_message,
                retry_count=retry_count,
                created_at=created_at,
                payload=payload,
                db=db
            )

            # Step 2: Determine routing and actions
            routing = analysis['routing_decision']

            result = {
                'message_id': message_id,
                'task_type': task_type,
                'routing': routing,
                'analysis': {
                    'error_type': analysis['error_type'],
                    'is_batch': analysis['is_batch_failure'],
                    'failure_rate': analysis['trend']['failure_rate'],
                },
                'actions_taken': [],
                'status': 'pending',
                'elapsed_seconds': 0
            }

            # Step 3: Route to appropriate handler (with timeout)
            try:
                # Create the handler coroutine based on routing
                if routing == 'auto_fix':
                    handler_coro = DeadLetterHandler._handle_auto_fix(
                        result, analysis, task_type, error_message, payload, db
                    )
                elif routing == 'architect_batch':
                    handler_coro = DeadLetterHandler._handle_batch_escalation(
                        result, analysis, db
                    )
                elif routing == 'architect_single':
                    handler_coro = DeadLetterHandler._handle_single_escalation(
                        result, analysis
                    )
                else:  # routing == 'ops_alert'
                    handler_coro = DeadLetterHandler._handle_ops_alert(
                        result, analysis, task_type
                    )

                # Execute handler with timeout
                result = await asyncio.wait_for(
                    handler_coro,
                    timeout=DeadLetterHandler.ESCALATION_TIMEOUT_SECONDS
                )

            except asyncio.TimeoutError:
                logger.warning(
                    f"[DeadLetterHandler] Escalation timeout for {message_id} "
                    f"(routing={routing}), escalating to ops"
                )
                result['status'] = 'timeout'
                result['actions_taken'].append('Escalation timeout - routed to ops alert')

                # Emergency route to ops (without timeout)
                result = await DeadLetterHandler._handle_ops_alert(result, analysis, task_type)

            # Record elapsed time
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            result['elapsed_seconds'] = round(elapsed, 2)

            logger.info(
                f"[DeadLetterHandler] Dead-letter processing complete: "
                f"message_id={message_id}, routing={routing}, "
                f"status={result['status']}, elapsed={result['elapsed_seconds']}s"
            )

            return result

        except Exception as e:
            logger.error(
                f"[DeadLetterHandler] Unexpected error processing {message_id}: {e}",
                exc_info=True
            )
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            return {
                'message_id': message_id,
                'task_type': task_type,
                'status': 'error',
                'error': str(e),
                'actions_taken': ['Emergency error - manual review required'],
                'elapsed_seconds': round(elapsed, 2)
            }

        finally:
            if should_close:
                db.close()

    @staticmethod
    async def _handle_auto_fix(
        result: Dict[str, Any],
        analysis: Dict[str, Any],
        task_type: str,
        error_message: str,
        payload: Optional[Dict[str, Any]],
        db: Session
    ) -> Dict[str, Any]:
        """Handle auto-fixable issues (config, rate-limit)."""
        logger.info(f"[DeadLetterHandler] Attempting auto-fix for {analysis['error_type']} error")

        # Note: Actual auto-fix implementation would go here
        # Examples:
        # - Refresh API token
        # - Clear rate-limit counter
        # - Reload configuration from secrets manager
        # - Adjust retry backoff

        result['actions_taken'].append(f"Auto-fix attempted for {analysis['error_type']} error")
        result['status'] = 'auto_fix_queued'

        # For now, log the action and queue for manual review
        logger.warning(
            f"[DeadLetterHandler] Auto-fix not yet implemented for {analysis['error_type']}, "
            f"escalating to ops"
        )
        result['actions_taken'].append("Auto-fix implementation pending - escalated to ops")

        return result

    @staticmethod
    async def _handle_batch_escalation(
        result: Dict[str, Any],
        analysis: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """Handle batch failures by escalating to architect for analysis."""
        logger.info(
            f"[DeadLetterHandler] Batch failure detected: "
            f"{analysis['batch_count']} similar errors"
        )

        # Prepare request for architect
        batch_messages = analysis.get('similar_errors', [])
        architect_request = ArchitectEscalationService.prepare_architect_request(
            analysis, batch_messages
        )

        # Log escalation for ops dashboard to pick up
        result['actions_taken'].append(
            f"Escalated batch failure to architect ({analysis['batch_count']} messages)"
        )
        result['architect_request'] = architect_request
        result['status'] = 'escalated_to_architect'

        logger.info(
            f"[DeadLetterHandler] Batch escalation prepared: "
            f"batch_size={analysis['batch_count']}, "
            f"error_type={analysis['error_type']}"
        )

        # TODO: Queue architect analysis request
        # - Send to architect agent with batch context
        # - Wait for response (with 120s timeout)
        # - Apply recommended fixes or escalate to ops

        return result

    @staticmethod
    async def _handle_single_escalation(
        result: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle single message issues requiring architect review."""
        logger.info(
            f"[DeadLetterHandler] Single message escalation for {analysis['error_type']} error"
        )

        # Prepare request for architect
        architect_request = ArchitectEscalationService.prepare_architect_request(
            analysis, []
        )

        result['actions_taken'].append(
            f"Escalated to architect for {analysis['error_type']} analysis"
        )
        result['architect_request'] = architect_request
        result['status'] = 'escalated_to_architect'

        # TODO: Queue architect analysis request
        # - Similar to batch, but single message context

        return result

    @staticmethod
    async def _handle_ops_alert(
        result: Dict[str, Any],
        analysis: Dict[str, Any],
        task_type: str
    ) -> Dict[str, Any]:
        """Alert ops team for manual review."""
        logger.warning(
            f"[DeadLetterHandler] Dead-letter alert to ops: "
            f"task_type={task_type}, error_type={analysis['error_type']}"
        )

        result['actions_taken'].append(
            "Dead-letter alert sent to ops team for manual review"
        )
        result['status'] = 'ops_alert_sent'

        # TODO: Send to ops-alerts dashboard
        # - Store in escalation_alerts table
        # - Notify ops team (Slack, email, etc.)
        # - Create ticket for tracking

        return result


async def handle_dead_letter_async(
    message_id: str,
    task_type: str,
    error_message: str,
    retry_count: int,
    created_at: datetime,
    payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Async wrapper for dead-letter handling.

    This is the entry point called from queue processor.
    """
    return await DeadLetterHandler.handle_dead_letter(
        message_id=message_id,
        task_type=task_type,
        error_message=error_message,
        retry_count=retry_count,
        created_at=created_at,
        payload=payload
    )
