"""
INCIDENT LEARNING SERVICE (2026-09-19)

Continuous learning from production incidents:
1. Parse incident logs
2. Extract root cause
3. Identify prevention pattern
4. Update architect knowledge
5. Improve gate criteria
6. Generate test cases

Learning Categories (8 patterns):
1. Silent failures → Add error propagation gate
2. Cascade failures → Add cascade detection gate
3. Timeout issues → Add timeout validation gate
4. Race conditions → Add atomic operation check
5. Data consistency → Add validation layer
6. Missing logging → Add logging requirements
7. Dependency failures → Add upstream verification
8. Permission issues → Add permission validation

Architect uses these learnings to auto-approve similar changes faster.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class LearningCategory(Enum):
    """Categories of learnings from incidents."""

    SILENT_FAILURE = "silent_failure"
    CASCADE_FAILURE = "cascade_failure"
    TIMEOUT_ISSUE = "timeout_issue"
    RACE_CONDITION = "race_condition"
    DATA_CONSISTENCY = "data_consistency"
    MISSING_LOGGING = "missing_logging"
    DEPENDENCY_FAILURE = "dependency_failure"
    PERMISSION_ISSUE = "permission_issue"


@dataclass
class IncidentAnalysis:
    """Analysis of a production incident."""

    incident_id: str
    incident_time: datetime
    duration_seconds: int  # How long before fixed

    learning_category: LearningCategory
    root_cause: str
    symptoms: List[str] = field(default_factory=list)
    affected_systems: List[str] = field(default_factory=list)
    customer_impact: str = ""  # Business impact

    prevention_rule: Optional[str] = None
    gate_improvement: Optional[str] = None
    test_case_generated: Optional[str] = None

    confidence: float = 0.0  # How confident in root cause


class IncidentLearningService:
    """
    CONTINUOUS LEARNING FROM INCIDENTS

    Parses production incidents and extracts learnings to improve:
    1. Gate validation (52 criteria)
    2. Architect decision patterns
    3. Test coverage (chaos engineering)
    4. Documentation and runbooks
    """

    # Root cause patterns → learning category
    ROOT_CAUSE_PATTERNS = {
        # Silent failures
        "silent_catch": {
            "category": LearningCategory.SILENT_FAILURE,
            "rule": "All catch blocks must re-raise or log + propagate",
            "gate_improvement": "Flag catch blocks with return [] or return None",
            "test_case": "Test that exception propagates, not swallowed",
        },
        "swallowed_exception": {
            "category": LearningCategory.SILENT_FAILURE,
            "rule": "Exception must propagate up the call stack",
            "gate_improvement": "Detect exception types caught but not re-raised",
            "test_case": "Call endpoint, verify error response, not silent success",
        },

        # Cascade failures
        "missing_circuit_breaker": {
            "category": LearningCategory.CASCADE_FAILURE,
            "rule": "Handler must have circuit breaker for dependent systems",
            "gate_improvement": "Require CircuitBreakerPattern for API-dependent handlers",
            "test_case": "Inject dependency failure, verify circuit breaker halts",
        },
        "unhandled_cascade": {
            "category": LearningCategory.CASCADE_FAILURE,
            "rule": "Handler must detect and handle cascade failures",
            "gate_improvement": "Check handler tests include cascade scenarios",
            "test_case": "Test downstream failure scenarios for each handler",
        },

        # Timeout issues
        "missing_timeout": {
            "category": LearningCategory.TIMEOUT_ISSUE,
            "rule": "Every external call must have timeout",
            "gate_improvement": "Require TIMEOUT_SECONDS for API/DB calls",
            "test_case": "Inject timeout, verify handler recovers",
        },
        "timeout_cascade": {
            "category": LearningCategory.TIMEOUT_ISSUE,
            "rule": "Sum of timeouts in cascade must be less than SLA",
            "gate_improvement": "Calculate total SLA for full workflow",
            "test_case": "Verify p99 latency < SLA for cascade",
        },

        # Race conditions
        "concurrent_write": {
            "category": LearningCategory.RACE_CONDITION,
            "rule": "Concurrent writes to same record require locking",
            "gate_improvement": "Flag database writes without WHERE + locking",
            "test_case": "Run 100 concurrent writes, verify no corruption",
        },
        "race_condition_order": {
            "category": LearningCategory.RACE_CONDITION,
            "rule": "Message processing order must be guaranteed",
            "gate_improvement": "Require idempotency_key validation",
            "test_case": "Process same message twice, verify idempotent",
        },

        # Data consistency
        "partial_update": {
            "category": LearningCategory.DATA_CONSISTENCY,
            "rule": "All related fields must update atomically",
            "gate_improvement": "Require transaction boundaries for multi-field updates",
            "test_case": "Force rollback mid-transaction, verify consistency",
        },
        "stale_cache": {
            "category": LearningCategory.DATA_CONSISTENCY,
            "rule": "Cache must invalidate on update",
            "gate_improvement": "Require cache.invalidate() calls on writes",
            "test_case": "Update DB, verify cache refreshed",
        },

        # Missing logging
        "no_error_context": {
            "category": LearningCategory.MISSING_LOGGING,
            "rule": "All errors must log with context (user_id, tenant_id, etc.)",
            "gate_improvement": "Require logger.error() with exc_info=True",
            "test_case": "Trigger error, verify logs contain full context",
        },
        "insufficient_tracing": {
            "category": LearningCategory.MISSING_LOGGING,
            "rule": "All state transitions must be logged",
            "gate_improvement": "Require logs at handler start/validation/completion",
            "test_case": "Trace message through system, verify logs complete",
        },

        # Dependency failures
        "undefined_dependency": {
            "category": LearningCategory.DEPENDENCY_FAILURE,
            "rule": "All Depends() functions must exist and be testable",
            "gate_improvement": "Verify Depends() functions exist at commit time",
            "test_case": "Test endpoint with missing dependency, verify error",
        },
        "missing_upstream": {
            "category": LearningCategory.DEPENDENCY_FAILURE,
            "rule": "Verify upstream data exists before processing",
            "gate_improvement": "Require FK checks before handler processing",
            "test_case": "Process message with missing parent, verify rejection",
        },

        # Permission issues
        "hardcoded_role": {
            "category": LearningCategory.PERMISSION_ISSUE,
            "rule": "Never hardcode role checks, use role_template permissions",
            "gate_improvement": "Flag Depends(get_current_hr_or_admin) pattern",
            "test_case": "Test endpoint with different roles, verify permission check",
        },
        "missing_permission_check": {
            "category": LearningCategory.PERMISSION_ISSUE,
            "rule": "All write operations require permission check",
            "gate_improvement": "Require @dependencies=[Depends(require_permission)] on POST/PUT",
            "test_case": "Test endpoint without auth, verify 401/403",
        },
    }

    def __init__(self):
        """Initialize learning service."""
        self.incidents_analyzed = 0
        self.learnings_log: List[IncidentAnalysis] = []
        self.knowledge_base: Dict[str, List[str]] = {}  # Category → learnings

    def analyze_incident(
        self,
        incident_id: str,
        incident_time: datetime,
        duration_seconds: int,
        error_logs: List[str],
        affected_systems: List[str],
    ) -> IncidentAnalysis:
        """
        Analyze production incident and extract learnings.

        Args:
            incident_id: Unique incident identifier
            incident_time: When incident started
            duration_seconds: How long to fix
            error_logs: Raw error messages
            affected_systems: Which systems failed

        Returns:
            IncidentAnalysis with root cause and learnings
        """

        logger.info(f"[Learning] Analyzing incident {incident_id} ({duration_seconds}s)")

        # Step 1: Extract root cause from logs
        root_cause = self._extract_root_cause(error_logs)
        logger.info(f"[Learning] Root cause: {root_cause}")

        # Step 2: Identify learning category
        pattern = self.ROOT_CAUSE_PATTERNS.get(root_cause, {})
        learning_category = pattern.get("category", LearningCategory.SILENT_FAILURE)

        # Step 3: Extract symptoms
        symptoms = self._extract_symptoms(error_logs)

        # Step 4: Create analysis
        analysis = IncidentAnalysis(
            incident_id=incident_id,
            incident_time=incident_time,
            duration_seconds=duration_seconds,
            learning_category=learning_category,
            root_cause=root_cause,
            symptoms=symptoms,
            affected_systems=affected_systems,
            confidence=self._calculate_root_cause_confidence(error_logs, root_cause),
        )

        # Step 5: Generate prevention rule
        if "rule" in pattern:
            analysis.prevention_rule = pattern["rule"]

        # Step 6: Recommend gate improvement
        if "gate_improvement" in pattern:
            analysis.gate_improvement = pattern["gate_improvement"]

        # Step 7: Generate test case
        if "test_case" in pattern:
            analysis.test_case_generated = pattern["test_case"]

        # Step 8: Assess customer impact
        analysis.customer_impact = self._assess_impact(
            duration_seconds,
            affected_systems,
        )

        # Store learning
        self.learnings_log.append(analysis)
        self.incidents_analyzed += 1
        self._update_knowledge_base(learning_category, analysis)

        logger.info(f"[Learning] Category: {learning_category.value}")
        logger.info(f"[Learning] Prevention: {analysis.prevention_rule}")
        logger.warning(f"[Learning] Impact: {analysis.customer_impact}")

        return analysis

    def _extract_root_cause(self, error_logs: List[str]) -> str:
        """Extract root cause from error logs."""
        log_text = " ".join(error_logs).lower()

        # Check for pattern matches
        for pattern in self.ROOT_CAUSE_PATTERNS.keys():
            pattern_variants = [
                pattern,
                pattern.replace("_", " "),
                pattern.replace("_", "-"),
            ]
            for variant in pattern_variants:
                if variant in log_text:
                    return pattern

        # Fallback: detect by error keywords
        if "exception" in log_text and "caught" in log_text:
            return "silent_catch"
        if "timeout" in log_text:
            return "missing_timeout"
        if "cascade" in log_text:
            return "unhandled_cascade"
        if "race" in log_text or "concurrent" in log_text:
            return "concurrent_write"
        if "permission" in log_text or "denied" in log_text:
            return "hardcoded_role"

        return "unknown"

    def _extract_symptoms(self, error_logs: List[str]) -> List[str]:
        """Extract observable symptoms from logs."""
        symptoms = []
        log_text = " ".join(error_logs).lower()

        if "timeout" in log_text:
            symptoms.append("Request timeout")
        if "503" in log_text or "service unavailable" in log_text:
            symptoms.append("Service unavailable (503)")
        if "500" in log_text or "internal error" in log_text:
            symptoms.append("Internal error (500)")
        if "queue" in log_text:
            symptoms.append("Queue processing delay")
        if "database" in log_text or "db" in log_text:
            symptoms.append("Database operation failed")
        if "memory" in log_text:
            symptoms.append("Memory pressure detected")
        if "connection" in log_text:
            symptoms.append("Connection pool exhausted")

        return symptoms or ["Unknown symptom"]

    def _calculate_root_cause_confidence(
        self,
        error_logs: List[str],
        root_cause: str,
    ) -> float:
        """Calculate confidence in root cause identification."""
        log_text = " ".join(error_logs).lower()
        confidence = 0.5  # Baseline

        # Increase confidence if root cause term appears in logs
        if root_cause.lower() in log_text:
            confidence = 0.9

        # Decrease confidence if error logs are vague
        if "unknown" in log_text or "error" in log_text:
            confidence = max(0.3, confidence - 0.2)

        # Increase confidence if multiple consistent symptoms
        symptom_count = sum(
            1 for _ in [
                "timeout" in log_text,
                "cascade" in log_text,
                "failed" in log_text,
            ]
            if _
        )
        confidence = min(0.99, confidence + (0.1 * symptom_count))

        return confidence

    def _assess_impact(self, duration_seconds: int, affected_systems: List[str]) -> str:
        """Assess customer/business impact of incident."""
        impact_score = duration_seconds / 60 * len(affected_systems)

        if impact_score > 100:
            return f"CRITICAL: {duration_seconds}s outage affecting {len(affected_systems)} systems"
        elif impact_score > 30:
            return f"HIGH: {duration_seconds}s downtime, {len(affected_systems)} systems affected"
        elif impact_score > 10:
            return f"MEDIUM: {duration_seconds}s degradation, {len(affected_systems)} services"
        else:
            return f"LOW: {duration_seconds}s issue in {', '.join(affected_systems)}"

    def _update_knowledge_base(
        self,
        category: LearningCategory,
        analysis: IncidentAnalysis,
    ) -> None:
        """Update knowledge base with this learning."""
        key = category.value

        if key not in self.knowledge_base:
            self.knowledge_base[key] = []

        # Store both root cause and prevention rule
        learning = f"{analysis.root_cause} → {analysis.prevention_rule}"
        if learning not in self.knowledge_base[key]:
            self.knowledge_base[key].append(learning)

    def get_architect_improvements(self) -> Dict[str, List[str]]:
        """Get improvements to architect decision patterns."""
        improvements = {}

        for category, learnings in self.knowledge_base.items():
            if learnings:
                improvements[category] = learnings

        return improvements

    def get_gate_improvements(self) -> Dict[str, str]:
        """Get improvements for gate validation criteria."""
        improvements = {}

        for analysis in self.learnings_log:
            if analysis.gate_improvement:
                key = f"{analysis.learning_category.value}_{analysis.root_cause}"
                improvements[key] = analysis.gate_improvement

        return improvements

    def get_test_cases(self) -> List[str]:
        """Get auto-generated test cases from incidents."""
        test_cases = []

        for analysis in self.learnings_log:
            if analysis.test_case_generated:
                test_cases.append(
                    f"[{analysis.incident_id}] {analysis.test_case_generated}"
                )

        return test_cases

    def get_learning_status(self) -> Dict:
        """Get current learning status."""
        return {
            "incidents_analyzed": self.incidents_analyzed,
            "categories": {
                category.value: len(learnings)
                for category, learnings in self.knowledge_base.items()
                if learnings
            },
            "recent_learnings": [
                {
                    "incident": analysis.incident_id,
                    "root_cause": analysis.root_cause,
                    "category": analysis.learning_category.value,
                    "prevention": analysis.prevention_rule,
                    "confidence": f"{analysis.confidence:.0%}",
                    "impact": analysis.customer_impact,
                }
                for analysis in self.learnings_log[-10:]
            ],
            "architect_improvements": self.get_architect_improvements(),
            "gate_improvements": self.get_gate_improvements(),
            "test_cases_generated": len(self.get_test_cases()),
        }
