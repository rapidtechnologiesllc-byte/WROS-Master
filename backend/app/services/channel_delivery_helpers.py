"""Channel Delivery Helpers - Error classification and retry logic

Determines if errors are transient (retry) or permanent (fail),
handles template rendering, and manages delivery status.
"""
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorClassifier:
    """Classify errors as transient (retry) or permanent (fail)"""

    # HTTP status codes that indicate transient errors (should retry)
    TRANSIENT_HTTP_CODES = {
        408,  # Request Timeout
        429,  # Too Many Requests (rate limit)
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }

    # HTTP status codes that indicate permanent errors (should not retry)
    PERMANENT_HTTP_CODES = {
        400,  # Bad Request
        401,  # Unauthorized
        403,  # Forbidden
        404,  # Not Found
        405,  # Method Not Allowed
        406,  # Not Acceptable
        409,  # Conflict
        410,  # Gone
        422,  # Unprocessable Entity (validation error)
    }

    # Keywords in error messages that indicate transient errors
    TRANSIENT_KEYWORDS = {
        "timeout",
        "connection",
        "temporary",
        "unavailable",
        "try again",
        "retry",
        "throttle",
        "rate limit",
        "backoff",
        "temporarily",
        "overloaded",
        "busy",
    }

    # Keywords in error messages that indicate permanent errors
    PERMANENT_KEYWORDS = {
        "invalid",
        "not found",
        "unauthorized",
        "forbidden",
        "forbidden",
        "wrong",
        "malformed",
        "bad request",
        "unrecognized",
        "unprocessable",
        "validation error",
        "syntax error",
    }

    @staticmethod
    def is_transient(error_code: Optional[int], error_message: str) -> bool:
        """
        Determine if an error is transient (should retry) or permanent (should not).

        Args:
            error_code: HTTP status code or similar numeric code
            error_message: Error message string

        Returns:
            True if transient (should retry), False if permanent (should not)
        """
        error_lower = error_message.lower()

        # Check HTTP status code first (highest priority)
        if error_code is not None:
            if error_code in ErrorClassifier.TRANSIENT_HTTP_CODES:
                logger.debug(
                    f"Classified as TRANSIENT (HTTP {error_code}): {error_message[:100]}"
                )
                return True

            if error_code in ErrorClassifier.PERMANENT_HTTP_CODES:
                logger.debug(
                    f"Classified as PERMANENT (HTTP {error_code}): {error_message[:100]}"
                )
                return False

        # Check keyword matches
        for keyword in ErrorClassifier.PERMANENT_KEYWORDS:
            if keyword in error_lower:
                logger.debug(
                    f"Classified as PERMANENT (matched '{keyword}'): {error_message[:100]}"
                )
                return False

        for keyword in ErrorClassifier.TRANSIENT_KEYWORDS:
            if keyword in error_lower:
                logger.debug(
                    f"Classified as TRANSIENT (matched '{keyword}'): {error_message[:100]}"
                )
                return True

        # Default: Assume transient (safer to retry than to silently fail)
        logger.debug(
            f"Classified as TRANSIENT (default): {error_message[:100]}"
        )
        return True

    @staticmethod
    def get_retry_delay(retry_count: int) -> int:
        """
        Calculate exponential backoff delay for retries.

        Args:
            retry_count: Number of retries already attempted

        Returns:
            Delay in seconds for next retry
        """
        # Exponential backoff: 5m, 10m, 20m, 40m, 80m (capped at 2 hours)
        base_delay = 300  # 5 minutes
        delay = base_delay * (2 ** retry_count)
        max_delay = 7200  # 2 hours
        return min(delay, max_delay)


class TemplateRenderer:
    """Render email templates with variable substitution"""

    @staticmethod
    def render(template_text: str, variables: dict) -> str:
        """
        Render a template by substituting variables.

        Supports {{variable}} syntax.

        Args:
            template_text: Template string with {{variable}} placeholders
            variables: Dictionary of variable values

        Returns:
            Rendered template with variables substituted
        """
        try:
            rendered = template_text
            for key, value in variables.items():
                placeholder = "{{" + key + "}}"
                rendered = rendered.replace(placeholder, str(value))
            return rendered
        except Exception as e:
            logger.error(f"Failed to render template: {e}", exc_info=True)
            raise ValueError(f"Template rendering failed: {e}")

    @staticmethod
    def render_from_database(
        template_text: str,
        subject_text: str,
        variables: dict,
    ) -> Tuple[str, str]:
        """
        Render both subject and body templates.

        Args:
            template_text: Body template with placeholders
            subject_text: Subject template with placeholders
            variables: Dictionary of variable values

        Returns:
            Tuple of (rendered_subject, rendered_body)
        """
        try:
            subject = TemplateRenderer.render(subject_text, variables)
            body = TemplateRenderer.render(template_text, variables)
            return subject, body
        except Exception as e:
            logger.error(f"Failed to render templates: {e}", exc_info=True)
            raise


class DeliveryStatus:
    """Helper for tracking delivery status"""

    @staticmethod
    def success(delivery_id: str, provider: str) -> dict:
        """
        Create a success status response.

        Args:
            delivery_id: ID from the delivery provider
            provider: Provider name (e.g., 'microsoft_graph', 'twilio', etc.)

        Returns:
            Status dict
        """
        return {
            "status": "success",
            "delivery_id": delivery_id,
            "provider": provider,
        }

    @staticmethod
    def failure(error_message: str, error_code: Optional[int] = None) -> dict:
        """
        Create a failure status response.

        Args:
            error_message: Human-readable error message
            error_code: Numeric error code if applicable

        Returns:
            Status dict
        """
        return {
            "status": "failure",
            "error": error_message,
            "error_code": error_code,
        }
