"""Sentry Integration - Error tracking and monitoring for production

Phase 4: Monitoring & Alerting
Captures all errors, tracks error rates, monitors system health.
"""
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    logger.warning("[Sentry] sentry-sdk not installed. Install with: pip install sentry-sdk")
    SENTRY_AVAILABLE = False


class SentryIntegration:
    """Sentry error tracking and monitoring."""

    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    @staticmethod
    def initialize() -> bool:
        """Initialize Sentry SDK if configured."""
        if not SentryIntegration.SENTRY_DSN:
            logger.warning("[Sentry] SENTRY_DSN not configured, error tracking disabled")
            return False

        if not SENTRY_AVAILABLE:
            logger.error("[Sentry] sentry-sdk not installed, cannot initialize")
            return False

        try:
            sentry_sdk.init(
                dsn=SentryIntegration.SENTRY_DSN,
                environment=SentryIntegration.ENVIRONMENT,
                traces_sample_rate=0.1,  # 10% of transactions
                debug=SentryIntegration.ENVIRONMENT == "development",
                integrations=[
                    FlaskIntegration(),
                    SqlalchemyIntegration(),
                ]
            )
            logger.info(f"[Sentry] ✅ Initialized in {SentryIntegration.ENVIRONMENT} environment")
            return True
        except Exception as e:
            logger.error(f"[Sentry] Failed to initialize: {e}", exc_info=True)
            return False

    @staticmethod
    def capture_exception(exception: Exception, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Capture exception and send to Sentry.

        Args:
            exception: Exception to capture
            context: Additional context data

        Returns:
            event_id (string) if sent, empty string if not configured
        """
        if not SENTRY_AVAILABLE or not SentryIntegration.SENTRY_DSN:
            logger.error(f"[Sentry] Exception not captured (not configured): {type(exception).__name__}")
            return ""

        try:
            if context:
                sentry_sdk.set_context("error_context", context)

            event_id = sentry_sdk.capture_exception(exception)
            logger.info(f"[Sentry] ✅ Exception captured: {event_id}")
            return str(event_id) if event_id else ""
        except Exception as e:
            logger.error(f"[Sentry] Failed to capture exception: {e}")
            return ""

    @staticmethod
    def capture_message(message: str, level: str = "info", context: Optional[Dict[str, Any]] = None) -> str:
        """
        Capture message and send to Sentry.

        Args:
            message: Message to capture
            level: Severity level (debug, info, warning, error, critical)
            context: Additional context data

        Returns:
            event_id (string) if sent, empty string if not configured
        """
        if not SENTRY_AVAILABLE or not SentryIntegration.SENTRY_DSN:
            logger.debug(f"[Sentry] Message not captured (not configured): {message}")
            return ""

        try:
            if context:
                sentry_sdk.set_context("message_context", context)

            event_id = sentry_sdk.capture_message(message, level=level)
            logger.info(f"[Sentry] ✅ Message captured: {event_id} (level={level})")
            return str(event_id) if event_id else ""
        except Exception as e:
            logger.error(f"[Sentry] Failed to capture message: {e}")
            return ""

    @staticmethod
    def set_user(user_id: str, email: str = "", username: str = "") -> None:
        """Set current user context for Sentry."""
        if not SENTRY_AVAILABLE:
            return

        try:
            sentry_sdk.set_user({
                "id": user_id,
                "email": email,
                "username": username
            })
        except Exception as e:
            logger.warning(f"[Sentry] Failed to set user context: {e}")

    @staticmethod
    def set_tag(key: str, value: str) -> None:
        """Set a tag for error grouping."""
        if not SENTRY_AVAILABLE:
            return

        try:
            sentry_sdk.set_tag(key, value)
        except Exception as e:
            logger.warning(f"[Sentry] Failed to set tag: {e}")

    @staticmethod
    def track_queue_error(queue_name: str, handler_name: str, error: str, job_id: str = "") -> None:
        """Track queue handler errors with context."""
        SentryIntegration.capture_exception(
            Exception(f"Queue handler error: {error}"),
            context={
                "queue": queue_name,
                "handler": handler_name,
                "job_id": job_id,
                "error_message": error,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @staticmethod
    def track_api_error(endpoint: str, method: str, status_code: int, error: str) -> None:
        """Track API endpoint errors with context."""
        SentryIntegration.capture_exception(
            Exception(f"API error: {error}"),
            context={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "error_message": error,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @staticmethod
    def track_database_error(operation: str, error: str, table: str = "") -> None:
        """Track database errors with context."""
        SentryIntegration.capture_exception(
            Exception(f"Database error: {error}"),
            context={
                "operation": operation,
                "table": table,
                "error_message": error,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
