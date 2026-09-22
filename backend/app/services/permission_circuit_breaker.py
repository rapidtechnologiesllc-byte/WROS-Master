"""
Permission Service Circuit Breaker - Prevents cascading failures.

Pattern: Tracks consecutive permission service failures. After 3 consecutive
failures, switches to OPEN state and returns fallback immediately without
calling the underlying service. Auto-resets after 60 seconds of stable operation.

Prevents resource exhaustion when permission service is overwhelmed.
"""

import time
import logging
from enum import Enum
from threading import Lock
from datetime import datetime

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"          # Normal operation
    OPEN = "OPEN"              # Failing - return fallback immediately
    HALF_OPEN = "HALF_OPEN"    # Testing if service recovered


class PermissionCircuitBreaker:
    """
    Circuit breaker for permission service.

    Prevents cascading failures by short-circuiting calls to failing permission service.
    """

    FAILURE_THRESHOLD = 3           # Failures before opening circuit
    SUCCESS_THRESHOLD = 1           # Successes to close circuit from half-open
    TIMEOUT_SECONDS = 60            # Time in OPEN state before trying again

    def __init__(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()
        self.lock = Lock()

    def call(self, func, *args, fallback_value=None, **kwargs):
        """
        Execute function through circuit breaker.

        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to function
            fallback_value: Value to return if circuit is OPEN

        Returns:
            Function result or fallback_value if circuit OPEN
        """
        with self.lock:
            # Check if circuit should transition from OPEN → HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info("[CircuitBreaker] Transitioning to HALF_OPEN - attempting reset")
                else:
                    # Still in timeout - return fallback
                    logger.debug("[CircuitBreaker] Circuit OPEN (within timeout) - returning fallback")
                    return fallback_value

        # Try to execute function
        try:
            result = func(*args, **kwargs)

            with self.lock:
                # Success - record it
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.SUCCESS_THRESHOLD:
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                        self.last_state_change = datetime.utcnow()
                        logger.info("[CircuitBreaker] Circuit CLOSED - service recovered")
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = 0

            return result

        except Exception as e:
            with self.lock:
                self.failure_count += 1
                self.last_failure_time = datetime.utcnow()

                logger.error(f"[CircuitBreaker] Call failed (count={self.failure_count}): {e}")

                # Check if we should open circuit
                if self.failure_count >= self.FAILURE_THRESHOLD:
                    if self.state != CircuitState.OPEN:
                        self.state = CircuitState.OPEN
                        self.last_state_change = datetime.utcnow()
                        logger.warning(f"[CircuitBreaker] Circuit OPEN - {self.failure_count} consecutive failures")

                    return fallback_value
                else:
                    # Still have retries before opening
                    raise

    def _should_attempt_reset(self) -> bool:
        """Check if timeout has elapsed to attempt reset"""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.TIMEOUT_SECONDS

    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring"""
        with self.lock:
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
                "last_state_change": self.last_state_change.isoformat(),
                "uptime_seconds": (datetime.utcnow() - self.last_state_change).total_seconds()
            }


# Global instance - singleton
_permission_breaker = None

def get_permission_breaker() -> PermissionCircuitBreaker:
    """Get or create global permission circuit breaker"""
    global _permission_breaker
    if _permission_breaker is None:
        _permission_breaker = PermissionCircuitBreaker()
    return _permission_breaker
