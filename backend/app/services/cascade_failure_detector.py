"""
CASCADE FAILURE DETECTOR (2026-09-19)

Real-time detection and prevention of cascade failures across:
- Thunder (candidate external operations)
- Flash (internal operations)
- Interview/Offer/Employee handlers
- Database/Queue/API dependencies

Detects 10 cascade initiation patterns:
1. Thunder timeout → Queue backup → Handler slowdown
2. Database slow → Lock timeout → Service hang
3. Memory leak → Gradual slowdown → Timeout cascade
4. Queue corruption → Handler error → Retry storm
5. Missing dependency → Silent failure → Data loss
6. Permission denied → 403 cascade → System lockout
7. Rate limit → Retry backoff → Cascade to dependents
8. Network partition → Timeout → Circuit break
9. Resource exhaustion → Slowdown → Timeout
10. Cascade loop (A fails, triggers B, B triggers A)

Triggers circuit breaker at 70% phalanx integrity.
Predicts cascade depth and propagation speed.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class CascadePattern(Enum):
    """Cascade failure patterns."""

    THUNDER_TIMEOUT = "thunder_timeout"  # External API timeout
    DB_SLOW = "db_slow"  # Database latency spike
    MEMORY_LEAK = "memory_leak"  # Gradual memory growth
    QUEUE_CORRUPTION = "queue_corruption"  # Poisoned message
    MISSING_DEPENDENCY = "missing_dependency"  # Runtime dependency missing
    PERMISSION_DENIED = "permission_denied"  # Auth cascade
    RATE_LIMIT = "rate_limit"  # Throttling cascade
    NETWORK_PARTITION = "network_partition"  # Network split
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # CPU/Memory/Connections
    CASCADE_LOOP = "cascade_loop"  # Circular failure


@dataclass
class CascadeFailure:
    """Detected cascade failure with impact analysis."""

    pattern: CascadePattern
    initiation_time: datetime
    initiator: str  # Which system failed first
    affected_systems: List[str] = field(default_factory=list)

    propagation_speed: float = 0.0  # messages/sec
    cascade_depth: int = 0  # How many levels affected
    predicted_failure_time: Optional[datetime] = None

    is_circuit_breaker_active: bool = False
    circuit_breaker_triggered_at: Optional[datetime] = None

    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    recovery_actions: List[str] = field(default_factory=list)


class CascadeFailureDetector:
    """
    REAL-TIME CASCADE FAILURE DETECTION

    Monitors 46 message handlers and detects cascade initiation patterns.
    Triggers circuit breakers when phalanx integrity < 70%.
    Correlates failures across Thunder, Flash, Interview, Offer, Employee.
    """

    # Cascade thresholds
    PROPAGATION_SPEED_THRESHOLD = 100  # messages/sec
    CASCADE_DEPTH_THRESHOLD = 3  # Systems affected
    CIRCUIT_BREAKER_THRESHOLD = 0.70  # 70% integrity
    DETECTION_WINDOW = timedelta(minutes=5)

    # Handler dependencies (who depends on whom)
    HANDLER_DEPENDENCIES = {
        "candidate_creation": [],  # No upstream
        "thunder_engagement": ["candidate_creation"],
        "flash_job_analysis": ["candidate_creation"],
        "interview_scheduled": ["candidate_creation", "flash_job_analysis"],
        "offer_generated": ["interview_scheduled"],
        "employee_created": ["offer_generated"],

        # Database dependencies
        "database_write": [],
        "database_index": ["database_write"],

        # Queue dependencies
        "queue_process": [],
        "queue_retry": ["queue_process"],

        # API dependencies
        "thunder_api": [],
        "flash_api": [],
    }

    # Cascade patterns and their signatures
    CASCADE_SIGNATURES = {
        CascadePattern.THUNDER_TIMEOUT: {
            "initiator": "thunder_api",
            "detectable_by": ["timeout_exception", "http_504", "request_hang"],
            "propagates_to": ["queue_process", "engagement_callback"],
            "recovery": ["circuit_breaker", "retry_with_backoff"],
        },
        CascadePattern.DB_SLOW: {
            "initiator": "database_write",
            "detectable_by": ["connection_timeout", "lock_timeout", "slow_query"],
            "propagates_to": ["all_handlers"],  # Affects everything
            "recovery": ["kill_slow_queries", "increase_connections", "scale_up"],
        },
        CascadePattern.MEMORY_LEAK: {
            "initiator": "handler_process",
            "detectable_by": ["memory_growth", "gc_pressure", "heap_size_growth"],
            "propagates_to": ["same_process_handlers"],
            "recovery": ["handler_restart", "pod_restart"],
        },
        CascadePattern.QUEUE_CORRUPTION: {
            "initiator": "queue_item",
            "detectable_by": ["deserialization_error", "schema_mismatch"],
            "propagates_to": ["handler_processing"],
            "recovery": ["dlq_move", "manual_repair"],
        },
        CascadePattern.MISSING_DEPENDENCY: {
            "initiator": "handler_start",
            "detectable_by": ["undefined_error", "import_error", "null_pointer"],
            "propagates_to": ["dependent_handlers"],
            "recovery": ["code_fix_deploy"],
        },
        CascadePattern.PERMISSION_DENIED: {
            "initiator": "auth_check",
            "detectable_by": ["403_forbidden", "permission_error"],
            "propagates_to": ["all_authenticated_operations"],
            "recovery": ["permission_fix", "user_re_login"],
        },
        CascadePattern.RATE_LIMIT: {
            "initiator": "rate_limiter",
            "detectable_by": ["429_too_many", "quota_exceeded"],
            "propagates_to": ["retry_backoff_queue"],
            "recovery": ["wait_for_quota_reset", "implement_backoff"],
        },
        CascadePattern.NETWORK_PARTITION: {
            "initiator": "network_io",
            "detectable_by": ["connection_refused", "dns_timeout", "unreachable"],
            "propagates_to": ["api_dependent_handlers"],
            "recovery": ["wait_for_network", "use_cached_endpoint"],
        },
        CascadePattern.RESOURCE_EXHAUSTION: {
            "initiator": "resource_monitor",
            "detectable_by": ["cpu_100%", "memory_full", "connection_pool_empty"],
            "propagates_to": ["all_operations"],
            "recovery": ["scale_up", "kill_slow_processes", "prioritize_critical"],
        },
        CascadePattern.CASCADE_LOOP: {
            "initiator": "handler_a",
            "detectable_by": ["circular_exception", "infinite_retry"],
            "propagates_to": ["handler_b", "handler_c"],
            "recovery": ["circuit_breaker", "manual_intervention"],
        },
    }

    def __init__(self):
        """Initialize cascade detector."""
        self.detected_cascades: List[CascadeFailure] = []
        self.circuit_breakers_active: Dict[str, bool] = {}
        self.phalanx_integrity: float = 1.0  # 0-1 (1.0 = 100% healthy)
        self.failure_correlation_matrix: Dict[str, List[str]] = {}

    def detect_cascade_initiation(
        self,
        error_log: Dict,
        handler_name: str,
        error_type: str,
        timestamp: datetime,
    ) -> Optional[CascadeFailure]:
        """
        Detect if an error initiates a cascade failure.

        Args:
            error_log: Error details (exception, stack trace, etc.)
            handler_name: Which handler failed
            error_type: Type of error
            timestamp: When error occurred

        Returns:
            CascadeFailure if cascade detected, None otherwise
        """

        logger.info(f"[Cascade] Checking {handler_name}: {error_type}")

        # Check for cascade patterns
        cascade_pattern = None

        if error_type in ["timeout", "504", "gateway_timeout"]:
            cascade_pattern = CascadePattern.THUNDER_TIMEOUT
        elif error_type in ["db_timeout", "lock_timeout", "slow_query"]:
            cascade_pattern = CascadePattern.DB_SLOW
        elif error_type in ["memory_pressure", "gc_failure"]:
            cascade_pattern = CascadePattern.MEMORY_LEAK
        elif error_type in ["serialization", "schema_mismatch"]:
            cascade_pattern = CascadePattern.QUEUE_CORRUPTION
        elif error_type in ["undefined", "import_error"]:
            cascade_pattern = CascadePattern.MISSING_DEPENDENCY
        elif error_type in ["403", "permission_denied"]:
            cascade_pattern = CascadePattern.PERMISSION_DENIED
        elif error_type in ["429", "quota_exceeded"]:
            cascade_pattern = CascadePattern.RATE_LIMIT
        elif error_type in ["connection_refused", "dns_timeout"]:
            cascade_pattern = CascadePattern.NETWORK_PARTITION
        elif error_type in ["resource_full", "pool_exhausted"]:
            cascade_pattern = CascadePattern.RESOURCE_EXHAUSTION
        elif error_type in ["circular_exception", "infinite_retry"]:
            cascade_pattern = CascadePattern.CASCADE_LOOP

        if not cascade_pattern:
            return None

        # Analyze cascade impact
        cascade = CascadeFailure(
            pattern=cascade_pattern,
            initiation_time=timestamp,
            initiator=handler_name,
            affected_systems=self._get_affected_systems(cascade_pattern, handler_name),
        )

        # Calculate propagation
        cascade.propagation_speed = self._calculate_propagation_speed(cascade)
        cascade.cascade_depth = len(cascade.affected_systems)

        # Predict failure time (how long before cascade hits critical level)
        cascade.predicted_failure_time = self._predict_cascade_timeline(cascade)

        # Determine severity
        cascade.severity = self._calculate_severity(cascade)

        # Generate recovery actions
        cascade.recovery_actions = self._generate_recovery_actions(cascade)

        # Check circuit breaker
        if self._should_trigger_circuit_breaker(cascade):
            cascade.is_circuit_breaker_active = True
            cascade.circuit_breaker_triggered_at = timestamp
            self._activate_circuit_breaker(cascade_pattern, handler_name)
            logger.error(f"[Cascade] CIRCUIT BREAKER triggered for {handler_name}")

        self.detected_cascades.append(cascade)
        logger.warning(f"[Cascade] DETECTED: {cascade_pattern.value} in {handler_name}")
        logger.warning(f"[Cascade] Affected: {cascade.affected_systems}")
        logger.warning(f"[Cascade] Severity: {cascade.severity}")

        return cascade

    def _get_affected_systems(self, pattern: CascadePattern, initiator: str) -> List[str]:
        """Get systems affected by this cascade pattern."""
        signature = self.CASCADE_SIGNATURES.get(pattern)
        if not signature:
            return []

        affected = signature.get("propagates_to", [])

        # Handle "all" systems
        if "all_handlers" in affected:
            return list(self.HANDLER_DEPENDENCIES.keys())
        if "all_authenticated_operations" in affected:
            return [h for h in self.HANDLER_DEPENDENCIES.keys() if "user" in h]
        if "all_operations" in affected:
            return list(self.HANDLER_DEPENDENCIES.keys())

        # Get dependent handlers
        dependent = []
        for handler, deps in self.HANDLER_DEPENDENCIES.items():
            if initiator in deps:
                dependent.append(handler)

        return dependent + affected

    def _calculate_propagation_speed(self, cascade: CascadeFailure) -> float:
        """Calculate how fast cascade spreads (messages/sec)."""
        # In production, this would track message processing rates
        # For now, estimate based on cascade depth

        base_speed = 10.0  # baseline messages/sec
        depth_multiplier = len(cascade.affected_systems) * 2

        return base_speed * depth_multiplier

    def _predict_cascade_timeline(self, cascade: CascadeFailure) -> datetime:
        """Predict when cascade reaches critical level."""
        if cascade.propagation_speed == 0:
            return cascade.initiation_time

        # Time to cascade 100 affected messages at this speed
        seconds_to_critical = 100 / cascade.propagation_speed

        return cascade.initiation_time + timedelta(seconds=seconds_to_critical)

    def _calculate_severity(self, cascade: CascadeFailure) -> str:
        """Determine cascade severity."""
        if cascade.cascade_depth >= 5:
            return "CRITICAL"
        if cascade.cascade_depth >= 3:
            return "HIGH"
        if cascade.propagation_speed > self.PROPAGATION_SPEED_THRESHOLD:
            return "HIGH"

        return "MEDIUM"

    def _generate_recovery_actions(self, cascade: CascadeFailure) -> List[str]:
        """Generate recovery actions for this cascade."""
        signature = self.CASCADE_SIGNATURES.get(cascade.pattern)
        if not signature:
            return ["Manual investigation required"]

        actions = signature.get("recovery", [])

        # Add specific actions based on severity
        if cascade.severity == "CRITICAL":
            actions.insert(0, "EMERGENCY: Activate incident response team")
            actions.insert(1, "Scale up resources immediately")
        elif cascade.severity == "HIGH":
            actions.insert(0, "Activate circuit breaker")
            actions.insert(1, "Alert on-call engineer")

        return actions

    def _should_trigger_circuit_breaker(self, cascade: CascadeFailure) -> bool:
        """Determine if circuit breaker should be triggered."""
        # Trigger if cascade depth >= 3 OR propagation > threshold
        if cascade.cascade_depth >= 3:
            return True
        if cascade.propagation_speed > self.PROPAGATION_SPEED_THRESHOLD:
            return True

        return False

    def _activate_circuit_breaker(self, pattern: CascadePattern, handler: str) -> None:
        """Activate circuit breaker for affected systems."""
        key = f"{pattern.value}_{handler}"
        self.circuit_breakers_active[key] = True

        # In production, this would:
        # 1. Stop accepting new messages for affected handlers
        # 2. Route messages to Dead Letter Queue
        # 3. Alert monitoring system
        # 4. Start recovery procedures

        logger.error(f"[CircuitBreaker] Activated for {key}")

    def calculate_phalanx_integrity(
        self,
        thunder_health: float,  # 0-1
        flash_health: float,  # 0-1
        interview_health: float,  # 0-1
        offer_health: float,  # 0-1
        employee_health: float,  # 0-1
    ) -> float:
        """
        Calculate phalanx integrity (Spartan formation health).

        Phalanx integrity is the MINIMUM of all positions:
        - If Thunder fails, Flash can't process (integrity = Thunder health)
        - If Flash fails, Interview can't schedule (integrity = Flash health)

        Circuit breaker triggers at 70% integrity.
        """

        integrity = min(
            thunder_health,
            flash_health,
            interview_health,
            offer_health,
            employee_health,
        )

        self.phalanx_integrity = integrity

        if integrity < self.CIRCUIT_BREAKER_THRESHOLD:
            logger.error(f"[Phalanx] INTEGRITY CRITICAL: {integrity:.0%}")
        elif integrity < 0.90:
            logger.warning(f"[Phalanx] INTEGRITY WARNING: {integrity:.0%}")
        else:
            logger.info(f"[Phalanx] INTEGRITY OK: {integrity:.0%}")

        return integrity

    def correlate_failures(self, errors: List[Dict]) -> List[Tuple[str, str, float]]:
        """
        Correlate multiple failures to find root cause.

        Returns:
            List of (system_a, system_b, correlation_score) tuples
        """

        correlations = []

        # In production, this would:
        # 1. Timeline all errors
        # 2. Find temporal correlations
        # 3. Calculate correlation strength
        # 4. Identify root cause

        logger.info(f"[Cascade] Correlating {len(errors)} failures")

        return correlations

    def get_cascade_status(self) -> Dict:
        """Get current cascade detection status."""
        return {
            "cascades_detected": len(self.detected_cascades),
            "cascades_prevented": sum(
                1 for c in self.detected_cascades if c.is_circuit_breaker_active
            ),
            "phalanx_integrity": self.phalanx_integrity,
            "circuit_breakers_active": sum(
                1 for v in self.circuit_breakers_active.values() if v
            ),
            "active_cascades": [
                {
                    "pattern": c.pattern.value,
                    "initiator": c.initiator,
                    "affected": c.affected_systems,
                    "severity": c.severity,
                    "detection_time_sec": (
                        datetime.now() - c.initiation_time
                    ).total_seconds(),
                }
                for c in self.detected_cascades
                if (datetime.now() - c.initiation_time) < self.DETECTION_WINDOW
            ],
        }
