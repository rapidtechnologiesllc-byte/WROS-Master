"""Error History Service - Track and analyze historical errors for dead-letter escalation
PHASE 3: Dead-Letter Error Pattern Analysis

Responsibilities:
1. Query similar errors in past 7 days
2. Identify error patterns and trends
3. Detect batch failures (5+ same error in 1 hour)
4. Support error classification (transient, config, code bug, rate-limit)
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from app.models.channel_queue import ChannelQueueItem
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class ErrorHistoryService:
    """
    Analyzes historical errors to detect patterns and trends.

    Used by dead-letter escalation to determine:
    - If this is a known/recurring error
    - If it's part of a batch failure (5+ same error)
    - What was tried before
    """

    @staticmethod
    def find_similar_errors(
        task_name: str,
        error_substring: str,
        lookback_hours: int = 168,  # 7 days
        limit: int = 100,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar errors in history.

        Args:
            task_name: Task type to search (e.g., 'send_email_to_candidate')
            error_substring: Search for errors containing this substring
            lookback_hours: How far back to search (default 7 days)
            limit: Maximum results to return
            db: Database session (creates new one if not provided)

        Returns:
            List of similar error records
        """
        should_close = db is None
        if db is None:
            db = SessionLocal()

        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)

            # Query messages with same task type and similar errors
            similar_errors = db.query(
                ChannelQueueItem.id,
                ChannelQueueItem.type,
                ChannelQueueItem.status,
                ChannelQueueItem.result,
                ChannelQueueItem.created_at,
                ChannelQueueItem.last_attempted_at,
                ChannelQueueItem.retry_count
            ).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status.in_(['FAILED', 'DEAD_LETTER', 'RETRY']),
                    ChannelQueueItem.created_at >= cutoff_time,
                    # Note: This is a LIKE query on JSON field, may be slow on large datasets
                    # Consider adding error_summary column if this becomes a bottleneck
                )
            ).order_by(
                ChannelQueueItem.created_at.desc()
            ).limit(limit).all()

            # Filter results to only those with matching error substring
            results = []
            for item in similar_errors:
                try:
                    import json
                    result_data = json.loads(item.result) if item.result else {}
                    error_msg = result_data.get('error', '') or ''

                    if error_substring.lower() in error_msg.lower():
                        results.append({
                            'message_id': str(item.id),
                            'task_type': item.type,
                            'status': item.status,
                            'error': error_msg[:200],  # Truncate for display
                            'created_at': item.created_at.isoformat(),
                            'last_attempted_at': item.last_attempted_at.isoformat() if item.last_attempted_at else None,
                            'retry_count': item.retry_count
                        })
                except Exception as e:
                    logger.warning(f"[ErrorHistoryService] Failed to parse result for {item.id}: {e}")

            logger.info(
                f"[ErrorHistoryService] Found {len(results)} similar errors for {task_name} "
                f"(searched last {lookback_hours}h, {limit} messages scanned)"
            )
            return results

        finally:
            if should_close:
                db.close()

    @staticmethod
    def get_error_trend(
        task_name: str,
        lookback_hours: int = 24,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Get error trend statistics for a task type.

        Args:
            task_name: Task type (e.g., 'send_email_to_candidate')
            lookback_hours: Time period to analyze
            db: Database session

        Returns:
            Trend data including total failures, completion rate, avg retries
        """
        should_close = db is None
        if db is None:
            db = SessionLocal()

        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)

            # Count total messages
            total_messages = db.query(func.count(ChannelQueueItem.id)).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.created_at >= cutoff_time
                )
            ).scalar() or 0

            # Count completed messages
            completed_messages = db.query(func.count(ChannelQueueItem.id)).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status == 'COMPLETED',
                    ChannelQueueItem.created_at >= cutoff_time
                )
            ).scalar() or 0

            # Count dead-lettered messages
            dead_letter_messages = db.query(func.count(ChannelQueueItem.id)).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status == 'DEAD_LETTER',
                    ChannelQueueItem.created_at >= cutoff_time
                )
            ).scalar() or 0

            # Count failed messages
            failed_messages = db.query(func.count(ChannelQueueItem.id)).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status == 'FAILED',
                    ChannelQueueItem.created_at >= cutoff_time
                )
            ).scalar() or 0

            # Calculate average retry count for completed messages
            avg_retries_completed = db.query(func.avg(ChannelQueueItem.retry_count)).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status == 'COMPLETED',
                    ChannelQueueItem.created_at >= cutoff_time
                )
            ).scalar() or 0

            # Calculate average retry count for dead-lettered messages
            avg_retries_dead = db.query(func.avg(ChannelQueueItem.retry_count)).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status == 'DEAD_LETTER',
                    ChannelQueueItem.created_at >= cutoff_time
                )
            ).scalar() or 0

            success_rate = (completed_messages / total_messages * 100) if total_messages > 0 else 0
            failure_rate = ((failed_messages + dead_letter_messages) / total_messages * 100) if total_messages > 0 else 0

            return {
                'task_name': task_name,
                'lookback_hours': lookback_hours,
                'total_messages': total_messages,
                'completed': completed_messages,
                'dead_letter': dead_letter_messages,
                'failed': failed_messages,
                'pending_retry': total_messages - completed_messages - dead_letter_messages - failed_messages,
                'success_rate': round(success_rate, 2),
                'failure_rate': round(failure_rate, 2),
                'avg_retries_successful': round(float(avg_retries_completed), 2),
                'avg_retries_dead_letter': round(float(avg_retries_dead), 2),
                'analyzed_at': datetime.utcnow().isoformat()
            }

        finally:
            if should_close:
                db.close()

    @staticmethod
    def detect_batch_failure(
        task_name: str,
        error_substring: str,
        window_minutes: int = 60,
        threshold: int = 5,
        db: Optional[Session] = None
    ) -> bool:
        """
        Detect if 5+ messages failed with same error in recent time window.

        This indicates a systemic issue (configuration, dependency down, etc.)
        rather than a transient failure.

        Args:
            task_name: Task type
            error_substring: Error pattern to search for
            window_minutes: Time window to check
            threshold: Number of failures to trigger batch detection
            db: Database session

        Returns:
            True if batch failure detected (5+ failures), False otherwise
        """
        should_close = db is None
        if db is None:
            db = SessionLocal()

        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)

            # Count messages with same error in recent window
            # Search in both RETRY and DEAD_LETTER states
            similar_error_count = 0
            messages = db.query(
                ChannelQueueItem.result
            ).filter(
                and_(
                    ChannelQueueItem.type == task_name,
                    ChannelQueueItem.status.in_(['RETRY', 'DEAD_LETTER', 'FAILED']),
                    ChannelQueueItem.last_attempted_at >= cutoff_time
                )
            ).limit(threshold + 10).all()  # Get a few extra to check

            for message in messages:
                try:
                    import json
                    result_data = json.loads(message.result) if message.result else {}
                    error_msg = result_data.get('error', '') or ''

                    if error_substring.lower() in error_msg.lower():
                        similar_error_count += 1
                except Exception:
                    pass

            is_batch = similar_error_count >= threshold

            logger.info(
                f"[ErrorHistoryService] Batch failure check for {task_name}: "
                f"{similar_error_count} messages in {window_minutes}min window "
                f"(threshold={threshold}, batch_detected={is_batch})"
            )

            return is_batch

        finally:
            if should_close:
                db.close()

    @staticmethod
    def classify_error(error_message: str) -> str:
        """
        Classify error type for escalation routing.

        Returns: 'transient', 'config', 'code_bug', 'rate_limit', 'unknown'
        """
        error_lower = error_message.lower()

        # Transient errors (retry might help)
        transient_keywords = ['timeout', 'connection', 'temporarily', 'busy', 'throttle', 'try again', 'temporary']
        if any(keyword in error_lower for keyword in transient_keywords):
            return 'transient'

        # Config/setup errors
        config_keywords = ['api_key', 'auth', 'token', 'credential', 'not found', 'invalid host', 'dns', 'invalid', 'secret']
        if any(keyword in error_lower for keyword in config_keywords):
            return 'config'

        # Code bugs
        bug_keywords = ['traceback', 'exception', 'type error', 'attribute error', 'keyerror', 'typeerror', 'nonetype', 'nameerror']
        if any(keyword in error_lower for keyword in bug_keywords):
            return 'code_bug'

        # Rate limits
        rate_keywords = ['rate limit', 'too many requests', '429', 'quota', 'exceeded', 'throttled']
        if any(keyword in error_lower for keyword in rate_keywords):
            return 'rate_limit'

        return 'unknown'
