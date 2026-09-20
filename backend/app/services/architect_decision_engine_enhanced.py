"""
ENHANCED ARCHITECT DECISION ENGINE (2026-09-19)

Autonomous decision-making with:
- Pattern matching for 20+ decision categories
- Constraint verification from phase2_constraint_verifier
- Confidence scoring (0-100%)
- Cascade risk integration from phase2_sdlc_cascade_simulator
- Rollback planning with alternatives

Authority Levels:
- Level 3 (AUTONOMOUS): Approve/block without approval (Authority Level 3)
- Level 2 (CONSTRAINED): Approve with constraints/verification (Authority Level 2)
- Level 1 (ESCALATE): CEO + Board only (Authority Level 1)
- HARD_BLOCK: Never permit, technical impossibility
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class DecisionCategory(Enum):
    """20+ decision categories with authority level."""

    # Authority Level 3 (AUTONOMOUS)
    CODE_FIX = "code_fix"  # ESLint, syntax, formatting
    DOCUMENTATION = "documentation"  # README, docstrings, comments
    SIMPLE_REFACTOR = "simple_refactor"  # Extract method, rename variable (no logic)
    TEST_ADDITION = "test_addition"  # Add tests for existing code
    GATE_CLEARANCE = "gate_clearance"  # Fix gate violations

    # Authority Level 2 (CONSTRAINED)
    TIMEOUT_CHANGE = "timeout_change"  # Change handler timeout
    VALIDATION_LOGIC = "validation_logic"  # Change what's valid/invalid
    QUEUE_SCHEMA = "queue_schema"  # Message payload schema change
    DATABASE_SCHEMA = "database_schema"  # Table/column changes
    NEW_HANDLER = "new_handler"  # New message handler
    QUEUE_ROUTING = "queue_routing"  # Change Thunder/Flash boundaries
    PERMISSION_SYSTEM = "permission_system"  # RBAC changes
    INFRASTRUCTURE = "infrastructure"  # Database, cache, queue config
    ERROR_HANDLING = "error_handling"  # Silent catch → exception
    DEPENDENCY_UPGRADE = "dependency_upgrade"  # Library version change

    # Authority Level 1 (ESCALATE)
    SLA_CHANGE = "sla_change"  # Critical path timing
    BUSINESS_REQUIREMENTS = "business_requirements"  # Hiring model
    ARCHITECTURE_REDESIGN = "architecture_redesign"  # Queue→RPC, DB→NoSQL
    SECURITY_POLICY = "security_policy"  # Auth strategy


@dataclass
class ArchitectDecision:
    """Enhanced decision with confidence, alternatives, and rollback."""

    category: DecisionCategory
    authority_level: str  # "level_3", "level_2", "level_1", "hard_block"
    decision: str  # "APPROVE", "BLOCK", "ESCALATE", "INVESTIGATE"
    confidence: float  # 0-100 (50+ = confident)
    reason: str

    constraints: List[str] = field(default_factory=list)
    rollback_plan: Optional[str] = None
    alternative_approaches: List[str] = field(default_factory=list)
    learning_points: List[str] = field(default_factory=list)
    cascade_risk_score: float = 0.0  # 0-100 (higher = riskier)
    sla_impact: Optional[str] = None  # e.g. "p99 latency +50ms"

    timestamp: datetime = field(default_factory=datetime.now)
    decision_hash: str = ""  # For audit trail

    def __str__(self) -> str:
        """Human-readable decision summary."""
        return (
            f"{self.decision} ({self.authority_level}) [{self.confidence:.0f}%]\n"
            f"Category: {self.category.value}\n"
            f"Reason: {self.reason}\n"
            f"Cascade Risk: {self.cascade_risk_score:.0f}/100"
        )


class EnhancedArchitectDecisionEngine:
    """
    ENHANCED ARCHITECT with:
    - 20+ decision patterns
    - Confidence scoring
    - Cascade risk calculation
    - Alternative approaches
    - Learning integration
    """

    # Hard blocks (never permit, even CEO)
    HARD_BLOCKS = {
        "silent_catch": "Silent exception catch = cascade 15 min later",
        "missing_timeout": "Handler without timeout = thread exhaustion",
        "missing_validation": "No validation = data corruption",
        "no_permission_check": "Missing auth = security breach",
        "cascade_unhandled": "Unhandled cascade failure = system down",
        "undefined_dependency": "Non-existent Depends() = endpoint hang",
    }

    # Decision patterns with confidence baseline (before adjustments)
    DECISION_PATTERNS = {
        # Authority Level 3 (AUTONOMOUS - 90%+ confidence)
        "code_fix": {
            "authority": "level_3",
            "base_confidence": 95,
            "decision": "APPROVE",
            "reason": "Code fix or syntax correction",
            "constraints": [],
        },
        "documentation": {
            "authority": "level_3",
            "base_confidence": 98,
            "decision": "APPROVE",
            "reason": "Documentation update, no code change",
            "constraints": [],
        },
        "simple_refactor": {
            "authority": "level_3",
            "base_confidence": 92,
            "decision": "APPROVE",
            "reason": "Refactoring with same behavior",
            "constraints": ["verify_tests_pass"],
        },
        "test_addition": {
            "authority": "level_3",
            "base_confidence": 95,
            "decision": "APPROVE",
            "reason": "New tests for existing code",
            "constraints": ["verify_test_passes"],
        },
        "gate_clearance": {
            "authority": "level_3",
            "base_confidence": 90,
            "decision": "APPROVE",
            "reason": "Fix gate violations",
            "constraints": ["gate_must_pass", "no_new_violations"],
        },

        # Authority Level 2 (CONSTRAINED - requires verification)
        "timeout_change": {
            "authority": "level_2",
            "base_confidence": 70,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Timeout affects SLA and downstream",
            "constraints": [
                "load_test_at_peak",
                "document_sla_impact",
                "verify_downstream_handles",
            ],
        },
        "validation_logic": {
            "authority": "level_2",
            "base_confidence": 65,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Validation change might reject valid data",
            "constraints": [
                "test_backward_compatibility",
                "document_rejection_reason",
                "verify_no_cascade",
            ],
        },
        "queue_schema": {
            "authority": "level_2",
            "base_confidence": 60,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Queue schema affects all downstream handlers",
            "constraints": [
                "audit_downstream_handlers",
                "plan_migration_strategy",
                "version_payload_schema",
                "test_handler_compatibility",
            ],
        },
        "database_schema": {
            "authority": "level_2",
            "base_confidence": 55,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Schema changes require 2-phase rollout",
            "constraints": [
                "migration_must_be_reversible",
                "backward_compatible_for_2_cycles",
                "no_data_loss_possible",
                "index_strategy_documented",
            ],
        },
        "new_handler": {
            "authority": "level_2",
            "base_confidence": 70,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "New handler increases system complexity",
            "constraints": [
                "timeout_configured",
                "validation_4_steps_complete",
                "exception_categorization_correct",
                "logging_all_transitions",
                "transaction_safety_verified",
                "idempotency_key_implemented",
                "circuit_breaker_pattern",
                "cascade_failure_detection",
                "result_serializable",
                "compensation_pattern_documented",
                "monitoring_hooks_emit",
                "schema_version_gating",
            ],
        },
        "queue_routing": {
            "authority": "level_2",
            "base_confidence": 65,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Queue routing affects handler assignment",
            "constraints": [
                "thunder_vs_flash_boundary_clear",
                "handler_exists_for_queue_type",
                "no_orphaned_queues",
                "test_message_routing",
            ],
        },
        "permission_system": {
            "authority": "level_2",
            "base_confidence": 60,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "RBAC changes affect security",
            "constraints": [
                "no_hardcoded_user_functions",
                "dynamic_role_checks_only",
                "test_all_role_combinations",
                "audit_permission_changes",
            ],
        },
        "infrastructure": {
            "authority": "level_2",
            "base_confidence": 65,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Infrastructure changes affect availability",
            "constraints": [
                "capacity_planning_documented",
                "monitoring_wired_before_deploy",
                "graceful_degradation_tested",
                "runbook_complete",
            ],
        },
        "error_handling": {
            "authority": "level_2",
            "base_confidence": 75,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Error handling fixes cascade failures",
            "constraints": [
                "no_silent_catches",
                "exception_logged_with_context",
                "downstream_notified",
            ],
        },
        "dependency_upgrade": {
            "authority": "level_2",
            "base_confidence": 70,
            "decision": "APPROVE_WITH_CONSTRAINTS",
            "reason": "Library upgrades may have breaking changes",
            "constraints": [
                "major_version_breaking_changes_reviewed",
                "all_tests_pass",
                "no_new_vulnerabilities",
            ],
        },

        # Authority Level 1 (ESCALATE - CEO + Board)
        "sla_change": {
            "authority": "level_1",
            "base_confidence": 0,
            "decision": "ESCALATE",
            "reason": "Changes business SLA (impacts revenue/hiring speed)",
            "constraints": ["ceo_board_approval_required"],
        },
        "business_requirements": {
            "authority": "level_1",
            "base_confidence": 0,
            "decision": "ESCALATE",
            "reason": "Changes hiring model (CEO strategy decision)",
            "constraints": ["ceo_board_approval_required"],
        },
        "architecture_redesign": {
            "authority": "level_1",
            "base_confidence": 0,
            "decision": "ESCALATE",
            "reason": "Major system redesign (queue→RPC, DB→NoSQL)",
            "constraints": ["ceo_board_approval_required"],
        },
        "security_policy": {
            "authority": "level_1",
            "base_confidence": 0,
            "decision": "ESCALATE",
            "reason": "Security policy changes require board approval",
            "constraints": ["security_review_required", "ceo_board_approval_required"],
        },
    }

    def __init__(self):
        """Initialize enhanced decision engine."""
        self.decisions_made = 0
        self.decisions_log: List[ArchitectDecision] = []
        self.learning_patterns: Dict[str, int] = {}  # Pattern → count

    def analyze_change(
        self,
        change_description: str,
        files_modified: List[str],
        gate_status: Dict,
        constraint_verifier=None,
        cascade_simulator=None,
    ) -> ArchitectDecision:
        """
        Analyze code change with pattern matching, constraints, cascade risk.

        Args:
            change_description: What changed and why
            files_modified: List of file paths
            gate_status: Gate validation results
            constraint_verifier: Phase2ConstraintVerifier instance
            cascade_simulator: Phase2SDLCCascadeSimulator instance

        Returns:
            ArchitectDecision with confidence, alternatives, rollback
        """

        logger.info(f"[Architect] Analyzing: {change_description}")
        logger.info(f"[Architect] Files modified: {files_modified}")

        # Step 1: Check hard blocks (automatic rejection)
        hard_block_result = self._check_hard_blocks(files_modified)
        if hard_block_result:
            logger.error(f"[Architect] HARD BLOCK: {hard_block_result}")
            return ArchitectDecision(
                category=DecisionCategory.CODE_FIX,
                authority_level="hard_block",
                decision="BLOCK",
                confidence=100,
                reason=f"HARD BLOCK: {hard_block_result}",
                rollback_plan="Revert change immediately, fix root cause",
            )

        # Step 2: Gate must pass
        if not gate_status.get("passed", False):
            logger.warning("[Architect] Gate not passing")
            return ArchitectDecision(
                category=DecisionCategory.GATE_CLEARANCE,
                authority_level="hard_block",
                decision="BLOCK",
                confidence=100,
                reason=f"Gate violations: {gate_status.get('violations', [])}",
                rollback_plan="Fix gate violations before resubmit",
            )

        # Step 3: Categorize the change
        category = self._categorize_change(change_description, files_modified)
        logger.info(f"[Architect] Category: {category.value}")

        # Step 4: Get base pattern
        pattern = self.DECISION_PATTERNS.get(
            category.value,
            {
                "authority": "level_3",
                "base_confidence": 50,
                "decision": "INVESTIGATE",
                "reason": "Unknown decision pattern",
                "constraints": [],
            }
        )

        # Step 5: Calculate confidence adjustments
        confidence = pattern["base_confidence"]
        confidence = self._adjust_confidence_for_scale(confidence, files_modified)
        confidence = self._adjust_confidence_for_risk(confidence, cascade_simulator, files_modified)

        # Step 6: Calculate cascade risk
        cascade_risk = 0.0
        if cascade_simulator:
            cascade_risk = cascade_simulator.calculate_cascade_risk(
                category=category.value,
                files_modified=files_modified,
                change_description=change_description,
            )
            logger.info(f"[Architect] Cascade risk: {cascade_risk:.0f}/100")

        # Step 7: Verify constraints
        constraint_violations = []
        if constraint_verifier:
            constraint_violations = constraint_verifier.verify_constraints(
                change_description=change_description,
                files_modified=files_modified,
                expected_constraints=pattern.get("constraints", []),
            )
            logger.info(f"[Architect] Constraints: {len(constraint_violations)} violations")

        # Step 8: Generate alternatives if needed
        alternatives = []
        if category in [
            DecisionCategory.TIMEOUT_CHANGE,
            DecisionCategory.DATABASE_SCHEMA,
            DecisionCategory.QUEUE_SCHEMA,
        ]:
            alternatives = self._generate_alternative_approaches(category)

        # Step 9: Generate rollback plan
        rollback_plan = self._generate_rollback_plan(category, files_modified)

        # Step 10: Make final decision
        decision_str = pattern["decision"]

        # Adjust decision based on constraints
        if pattern["authority"] == "level_2" and constraint_violations:
            logger.warning(f"[Architect] Constraints not fully met: {constraint_violations}")
            decision_str = "APPROVE_WITH_CONSTRAINTS"
            confidence = max(0, confidence - 15)  # Reduce confidence

        # Log decision
        decision = ArchitectDecision(
            category=category,
            authority_level=pattern["authority"],
            decision=decision_str,
            confidence=confidence,
            reason=pattern["reason"],
            constraints=pattern.get("constraints", []),
            rollback_plan=rollback_plan,
            alternative_approaches=alternatives,
            cascade_risk_score=cascade_risk,
            learning_points=[
                f"Pattern: {category.value} (base confidence {pattern['base_confidence']}%)",
                f"Adjusted confidence: {confidence:.0f}%",
                f"Cascade risk: {cascade_risk:.0f}/100",
                f"Authority level: {pattern['authority']}",
            ],
        )

        self.decisions_made += 1
        self.decisions_log.append(decision)
        self._update_learning_patterns(category.value)

        logger.info(f"[Architect] Decision: {decision_str} ({confidence:.0f}%)")

        return decision

    def _check_hard_blocks(self, files_modified: List[str]) -> Optional[str]:
        """Check for hard blocks (automatic rejection)."""
        # In production, this would scan files for violations
        # For now, return None (no hard blocks)
        return None

    def _categorize_change(
        self,
        description: str,
        files: List[str],
    ) -> DecisionCategory:
        """Categorize change into one of 20+ categories."""
        desc_lower = description.lower()

        # Check for autonomous patterns first
        if any(word in desc_lower for word in ["eslint", "formatting", "syntax"]):
            return DecisionCategory.CODE_FIX
        if any(word in desc_lower for word in ["readme", "docstring", "comment", "docs"]):
            return DecisionCategory.DOCUMENTATION
        if any(word in desc_lower for word in ["extract", "rename", "refactor"]):
            return DecisionCategory.SIMPLE_REFACTOR
        if "test" in desc_lower and any(f.endswith("_test.py") for f in files):
            return DecisionCategory.TEST_ADDITION
        if "gate" in desc_lower and any(word in desc_lower for word in ["violation", "fix"]):
            return DecisionCategory.GATE_CLEARANCE

        # Check for constrained patterns
        if "timeout" in desc_lower:
            return DecisionCategory.TIMEOUT_CHANGE
        if "validation" in desc_lower and "logic" in desc_lower:
            return DecisionCategory.VALIDATION_LOGIC
        if "queue" in desc_lower and "schema" in desc_lower:
            return DecisionCategory.QUEUE_SCHEMA
        if "database" in desc_lower or "schema" in desc_lower or "migration" in desc_lower:
            return DecisionCategory.DATABASE_SCHEMA
        if "handler" in desc_lower and "new" in desc_lower:
            return DecisionCategory.NEW_HANDLER
        if "queue" in desc_lower and "routing" in desc_lower:
            return DecisionCategory.QUEUE_ROUTING
        if "permission" in desc_lower or "rbac" in desc_lower:
            return DecisionCategory.PERMISSION_SYSTEM
        if any(word in desc_lower for word in ["infrastructure", "deployment", "config"]):
            return DecisionCategory.INFRASTRUCTURE
        if "error" in desc_lower or "exception" in desc_lower or "catch" in desc_lower:
            return DecisionCategory.ERROR_HANDLING
        if "upgrade" in desc_lower or "dependency" in desc_lower:
            return DecisionCategory.DEPENDENCY_UPGRADE

        # Check for escalate patterns
        if "sla" in desc_lower or "latency" in desc_lower:
            return DecisionCategory.SLA_CHANGE
        if "business" in desc_lower or "requirement" in desc_lower:
            return DecisionCategory.BUSINESS_REQUIREMENTS
        if "architecture" in desc_lower or "redesign" in desc_lower:
            return DecisionCategory.ARCHITECTURE_REDESIGN
        if "security" in desc_lower and "policy" in desc_lower:
            return DecisionCategory.SECURITY_POLICY

        # Default to code fix
        return DecisionCategory.CODE_FIX

    def _adjust_confidence_for_scale(self, base_confidence: float, files: List[str]) -> float:
        """Adjust confidence based on number of files and scope."""
        file_count = len(files)

        if file_count > 5:
            return max(0, base_confidence - 10)  # Multi-file change, riskier
        if file_count > 10:
            return max(0, base_confidence - 20)  # Large change
        if file_count > 20:
            return max(0, base_confidence - 30)  # Very large change

        return base_confidence

    def _adjust_confidence_for_risk(
        self,
        base_confidence: float,
        cascade_simulator,
        files: List[str],
    ) -> float:
        """Adjust confidence based on cascade risk."""
        if not cascade_simulator:
            return base_confidence

        risk = cascade_simulator.calculate_cascade_risk(
            category="unknown",
            files_modified=files,
            change_description="",
        )

        # High risk = lower confidence
        if risk > 75:
            return max(0, base_confidence - 30)
        if risk > 50:
            return max(0, base_confidence - 15)

        return base_confidence

    def _generate_alternative_approaches(self, category: DecisionCategory) -> List[str]:
        """Generate alternative approaches for high-risk changes."""
        alternatives = {
            DecisionCategory.TIMEOUT_CHANGE: [
                "Use circuit breaker instead of timeout change",
                "Gradual timeout increase (10% per cycle)",
                "Separate fast/slow paths with different timeouts",
            ],
            DecisionCategory.DATABASE_SCHEMA: [
                "Add column as nullable, migrate data in background",
                "Use shadow table pattern (new schema, migrate gradually)",
                "Temporal versioning (old schema available for 2 cycles)",
            ],
            DecisionCategory.QUEUE_SCHEMA: [
                "Version the message payload (v1, v2 support parallel)",
                "Add new field as optional, make required in v2",
                "Use adapter pattern (translate between schema versions)",
            ],
        }

        return alternatives.get(category, [])

    def _generate_rollback_plan(self, category: DecisionCategory, files: List[str]) -> str:
        """Generate rollback plan for the change."""
        if category in [
            DecisionCategory.DATABASE_SCHEMA,
            DecisionCategory.QUEUE_SCHEMA,
        ]:
            return (
                f"Rollback: Revert {len(files)} migrations, "
                f"restore database from pre-change snapshot, "
                f"verify handlers process old schema. "
                f"Time: ~30 minutes, zero data loss if reverted within 1 hour."
            )

        if category == DecisionCategory.NEW_HANDLER:
            return (
                "Rollback: Remove handler registration, "
                "drain queue (process remaining messages), "
                "revert code changes. "
                "Time: ~10 minutes, no data loss."
            )

        return (
            f"Rollback: git revert {len(files)} files, "
            f"verify tests pass, "
            f"redeploy. Time: <5 minutes, zero impact."
        )

    def _update_learning_patterns(self, category: str) -> None:
        """Update learning patterns for future decisions."""
        if category not in self.learning_patterns:
            self.learning_patterns[category] = 0
        self.learning_patterns[category] += 1


# Singleton instance
_enhanced_engine = None


def get_enhanced_decision_engine() -> EnhancedArchitectDecisionEngine:
    """Get singleton instance of enhanced decision engine."""
    global _enhanced_engine
    if _enhanced_engine is None:
        _enhanced_engine = EnhancedArchitectDecisionEngine()
    return _enhanced_engine


def get_architect_enhanced_decision(
    change_description: str,
    files_modified: List[str],
    gate_status: Dict,
    constraint_verifier=None,
    cascade_simulator=None,
) -> ArchitectDecision:
    """Get architect's autonomous decision on a code change (enhanced version)."""
    engine = get_enhanced_decision_engine()
    return engine.analyze_change(
        change_description=change_description,
        files_modified=files_modified,
        gate_status=gate_status,
        constraint_verifier=constraint_verifier,
        cascade_simulator=cascade_simulator,
    )
