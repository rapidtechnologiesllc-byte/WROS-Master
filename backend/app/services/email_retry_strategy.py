"""Email Retry Strategy - Smart exponential backoff with per-handler configs
PHASE 2: Email Retry Backoff + Jitter + Retry-After Honor

Responsibilities:
1. Calculate retry delays with exponential backoff
2. Add jitter to prevent thundering herd
3. Honor Retry-After header from email providers (Microsoft, Gmail)
4. Support per-handler retry configurations
5. Track retry history for dead-letter escalation
"""
import logging
import random
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EmailRetryStrategy:
    """
    Smart retry strategy for email and other queue handlers.

    Features:
    - Per-handler retry configurations (different backoff for email vs API calls)
    - Exponential backoff with jitter (prevent synchronized retries)
    - Honor Retry-After headers from providers
    - Track retry history for analysis
    """

    # Default retry configuration (fallback for handlers without specific config)
    DEFAULT_RETRY_CONFIG = {
        'delays': [1, 2, 4, 8, 16, 32],  # Delays in seconds (6 total attempts)
        'max_attempts': 6,
        'honor_retry_after': True,
        'jitter': 0.10  # ±10% randomization
    }

    # Per-handler retry configurations
    # Email handlers need longer backoff (email providers have rate limits)
    # API handlers can retry faster
    HANDLER_RETRY_CONFIG = {
        'send_email_to_candidate': {
            'delays': [2, 4, 8, 16, 32, 64],  # 2s → 4s → 8s → 16s → 32s → 64s
            'max_attempts': 6,
            'honor_retry_after': True,  # Honor Microsoft's Retry-After header
            'jitter': 0.15  # ±15% randomization
        },
        'send_email_message': {
            'delays': [2, 4, 8, 16, 32, 64],  # Same as send_email_to_candidate
            'max_attempts': 6,
            'honor_retry_after': True,
            'jitter': 0.15
        },
        'engage_candidate_with_thunder': {
            'delays': [5, 10, 20, 40, 80],  # Thunder (external API): longer initial delay
            'max_attempts': 5,
            'honor_retry_after': False,
            'jitter': 0.15
        },
        'send_whatsapp_message': {
            'delays': [3, 6, 12, 24, 48],  # WhatsApp rate limits
            'max_attempts': 5,
            'honor_retry_after': True,
            'jitter': 0.15
        },
        'send_sms_message': {
            'delays': [3, 6, 12, 24, 48],  # SMS rate limits
            'max_attempts': 5,
            'honor_retry_after': True,
            'jitter': 0.15
        },
        # Forwarded-email intake: Graph / LLM / SharePoint outages last minutes, not seconds
        'thunder_process_forwarded_email': {
            'delays': [60, 300, 900, 1800, 3600],
            'max_attempts': 5,
            'honor_retry_after': True,
            'jitter': 0.15
        },
        # Database operations can retry quickly
        'create_candidate': {
            'delays': [1, 2, 4, 8, 16],
            'max_attempts': 5,
            'honor_retry_after': False,
            'jitter': 0.10
        },
        'update_candidate': {
            'delays': [1, 2, 4, 8, 16],
            'max_attempts': 5,
            'honor_retry_after': False,
            'jitter': 0.10
        },
    }

    @staticmethod
    def get_handler_config(handler_name: str) -> Dict[str, Any]:
        """Get retry configuration for a handler.

        Args:
            handler_name: Name of the handler (e.g., 'send_email_message')

        Returns:
            Retry configuration dict with delays, max_attempts, honor_retry_after, jitter
        """
        if handler_name in EmailRetryStrategy.HANDLER_RETRY_CONFIG:
            return EmailRetryStrategy.HANDLER_RETRY_CONFIG[handler_name]
        return EmailRetryStrategy.DEFAULT_RETRY_CONFIG

    @staticmethod
    def calculate_next_retry_delay(
        handler_name: str,
        retry_count: int,
        retry_after_header: Optional[str] = None,
        retry_after_seconds: Optional[int] = None
    ) -> Optional[int]:
        """
        Calculate the delay before next retry.

        Args:
            handler_name: Name of the handler
            retry_count: Current retry count (0-based, will increment before delay)
            retry_after_header: Optional Retry-After header value (HTTP date or seconds)
            retry_after_seconds: Optional Retry-After value already parsed as seconds

        Returns:
            Delay in seconds, or None if max retries exceeded
        """
        config = EmailRetryStrategy.get_handler_config(handler_name)

        # Check if we've exceeded max attempts
        if retry_count >= config['max_attempts']:
            logger.warning(
                f"[EmailRetryStrategy] Max retries ({config['max_attempts']}) "
                f"exceeded for {handler_name} (retry_count={retry_count})"
            )
            return None  # No more retries

        # Honor Retry-After header if configured and provided
        if config['honor_retry_after']:
            parsed_seconds = EmailRetryStrategy._parse_retry_after(retry_after_header)
            if parsed_seconds is not None:
                jitter = EmailRetryStrategy._calculate_jitter(parsed_seconds, config['jitter'])
                final_delay = parsed_seconds + jitter
                logger.info(
                    f"[EmailRetryStrategy] Using Retry-After header: "
                    f"{parsed_seconds}s (+ {jitter:.2f}s jitter) for {handler_name}"
                )
                return int(final_delay)

            # If retry_after_seconds provided, use it directly
            if retry_after_seconds is not None:
                jitter = EmailRetryStrategy._calculate_jitter(retry_after_seconds, config['jitter'])
                final_delay = retry_after_seconds + jitter
                logger.info(
                    f"[EmailRetryStrategy] Using provided retry_after_seconds: "
                    f"{retry_after_seconds}s (+ {jitter:.2f}s jitter) for {handler_name}"
                )
                return int(final_delay)

        # Use exponential backoff from config
        base_delay = config['delays'][retry_count]
        jitter = EmailRetryStrategy._calculate_jitter(base_delay, config['jitter'])
        final_delay = base_delay + jitter

        logger.debug(
            f"[EmailRetryStrategy] Calculated delay for {handler_name}: "
            f"retry_count={retry_count}, base={base_delay}s, "
            f"jitter={jitter:.2f}s, final={final_delay:.2f}s"
        )

        return int(final_delay)

    @staticmethod
    def _calculate_jitter(base_seconds: float, jitter_percentage: float) -> float:
        """
        Calculate jitter value (random ±X% of base value).

        Args:
            base_seconds: Base delay in seconds
            jitter_percentage: Jitter as percentage (0.10 = 10%)

        Returns:
            Random jitter value between -jitter_percentage and +jitter_percentage
        """
        jitter_range = base_seconds * jitter_percentage
        return random.uniform(-jitter_range, jitter_range)

    @staticmethod
    def _parse_retry_after(retry_after_header: Optional[str]) -> Optional[int]:
        """
        Parse Retry-After header.

        Supports two formats:
        1. Delay in seconds: "120"
        2. HTTP date: "Fri, 31 Dec 1999 23:59:59 GMT"

        Args:
            retry_after_header: The value of Retry-After header

        Returns:
            Seconds to wait, or None if header not valid
        """
        if not retry_after_header:
            return None

        try:
            # Try parsing as integer (seconds)
            return int(retry_after_header)
        except ValueError:
            pass

        try:
            # Try parsing as HTTP date
            # Expected format: "Fri, 31 Dec 1999 23:59:59 GMT"
            retry_after_date = datetime.strptime(
                retry_after_header,
                "%a, %d %b %Y %H:%M:%S %Z"
            )
            seconds_until = int((retry_after_date - datetime.utcnow()).total_seconds())
            if seconds_until > 0:
                return seconds_until
        except (ValueError, AttributeError):
            pass

        logger.warning(f"[EmailRetryStrategy] Could not parse Retry-After header: {retry_after_header}")
        return None

    @staticmethod
    def should_retry(
        handler_name: str,
        retry_count: int,
        error_type: Optional[str] = None
    ) -> bool:
        """
        Check if a handler should retry based on error type and retry count.

        Some errors are non-retryable (permanent failures):
        - Invalid email format
        - Authentication failures
        - User not found

        Args:
            handler_name: Name of the handler
            retry_count: Current retry count
            error_type: Optional error type/classification

        Returns:
            True if should retry, False if should give up
        """
        # Check if already at max retries
        config = EmailRetryStrategy.get_handler_config(handler_name)
        if retry_count >= config['max_attempts']:
            return False

        # Check for non-retryable errors
        non_retryable_errors = [
            'INVALID_EMAIL',
            'INVALID_PHONE',
            'USER_NOT_FOUND',
            'AUTHENTICATION_FAILED',
            'PERMISSION_DENIED',
            'RATE_LIMIT_EXCEEDED_ACCOUNT',  # Account-level rate limits (permanent this request)
        ]

        if error_type and error_type in non_retryable_errors:
            logger.info(
                f"[EmailRetryStrategy] Non-retryable error {error_type} for {handler_name}"
            )
            return False

        return True

    @staticmethod
    def get_max_retry_attempts(handler_name: str) -> int:
        """Get maximum retry attempts for a handler."""
        config = EmailRetryStrategy.get_handler_config(handler_name)
        return config['max_attempts']

    @staticmethod
    def get_retry_history_summary(retry_count: int, handler_name: str) -> Dict[str, Any]:
        """
        Get a summary of retry history for logging/escalation.

        Args:
            retry_count: Current retry count
            handler_name: Name of the handler

        Returns:
            Summary dict with attempt number, delays used so far, etc.
        """
        config = EmailRetryStrategy.get_handler_config(handler_name)
        delays_used = config['delays'][:retry_count] if retry_count > 0 else []
        total_wait_time = sum(delays_used)

        return {
            'attempt_number': retry_count + 1,
            'max_attempts': config['max_attempts'],
            'delays_used': delays_used,
            'total_wait_time_seconds': total_wait_time,
            'next_delay_seconds': (
                config['delays'][retry_count]
                if retry_count < len(config['delays'])
                else None
            ),
            'is_final_attempt': (retry_count + 1) >= config['max_attempts']
        }
