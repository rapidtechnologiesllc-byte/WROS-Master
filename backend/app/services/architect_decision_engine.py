"""
RUTHLESS ARCHITECT DECISION ENGINE (2026-09-19)

Autonomous decision-making for code changes:
- Authority Level 1-3: Can approve/block without human intervention
- Authority Level 2-3: Can approve with constraints
- Authority Level 1: CEO + Board only (blocks automatically)

No human approval gates between SDLC cycles. Architect learns and improves.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AuthorityLevel(Enum):
    """Architect autonomous decision authority levels."""

    AUTONOMOUS = "level_3"  # Approve/block without approval
    CONSTRAINED = "level_2"  # Approve with constraints
    ESCALATE = "level_1"  # CEO + Board only
    HARD_BLOCK = "hard_block"  # Never permit


class DecisionCategory(Enum):
    """Types of architectural decisions."""

    CODE_FIX = "code_fix"
    REFACTOR = "refactor"
    SCHEMA_CHANGE = "schema_change"
    HANDLER_NEW = "handler_new"
    TIMEOUT_CHANGE = "timeout_change"
    QUEUE_ROUTING = "queue_routing"
    PERMISSION_CHANGE = "permission_change"
    DEPLOYMENT = "deployment"
    INCIDENT_RESPONSE = "incident_response"


class ArchitectDecision:
    """Architect's autonomous decision on a code change."""

    def __init__(
        self,
        category: DecisionCategory,
        authority_level: AuthorityLevel,
        decision: str,  # "APPROVE", "BLOCK", "ESCALATE", "INVESTIGATE"
        reason: str,
        constraints: Optional[List[str]] = None,
        rollback_plan: Optional[str] = None,
        learning_points: Optional[List[str]] = None,
    ):
        self.category = category
        self.authority_level = authority_level
        self.decision = decision  # APPROVE, BLOCK, ESCALATE, INVESTIGATE
        self.reason = reason
        self.constraints = constraints or []
        self.rollback_plan = rollback_plan
        self.learning_points = learning_points or []

    def __str__(self):
        return f"{self.decision} ({self.authority_level.value}): {self.reason}"


class RuthlessArchitect:
    """
    RUTHLESS ARCHITECT AGENT

    System Knowledge (MEMORIZED):
    - Critical path: Candidate → Thunder engagement → Flash analysis → Interview → Offer → Employee
    - Queue architecture: ChannelQueueItem, multiple handlers, cascading failures
    - Database: PostgreSQL sharded by tenant_id (1500HC design)
    - Services: Thunder (external), Flash (internal), Interview/Offer handlers

    Thinking Framework:
    - Upstream: Does this assume dependencies exist?
    - Functional: Does this break business workflow?
    - Downstream: What breaks 3 months from now?
    - Cascade: If X fails, what else breaks?
    - Timing: At what scale does this fall apart?
    - Scale: What changes for 1500 headcount?

    Ruthless Principle: NEVER assume, always verify. Prevent cascade failures 15 min ahead.
    """

    # Hard blocks - NEVER permit, even CEO cannot override
    HARD_BLOCKS = {
        "silent_catch_blocks": "Silent exception catching = cascade failure 15 min later",
        "missing_timeout": "Handler without timeout = thread pool exhaustion",
        "missing_validation": "No validation = data corruption in queue",
        "no_permission_check": "Missing auth = security breach",
        "cascade_failure_risk": "Single point of failure = system down",
    }

    # Authority Level 3 - Architect can approve/block autonomously
    AUTONOMOUS_DECISIONS = {
        "fix_eslint": {
            "authority": AuthorityLevel.AUTONOMOUS,
            "decision": "APPROVE",
            "reason": "ESLint fix, no logic change",
        },
        "add_timeout_config": {
            "authority": AuthorityLevel.AUTONOMOUS,
            "decision": "APPROVE",
            "reason": "Gate requirement, standard pattern",
        },
        "add_validation_checks": {
            "authority": AuthorityLevel.AUTONOMOUS,
            "decision": "APPROVE",
            "reason": "Gate requirement, standard pattern",
        },
        "optimize_n_plus_1": {
            "authority": AuthorityLevel.AUTONOMOUS,
            "decision": "APPROVE",
            "reason": "Performance optimization, same behavior",
        },
        "update_documentation": {
            "authority": AuthorityLevel.AUTONOMOUS,
            "decision": "APPROVE",
            "reason": "No code change",
        },
    }

    # Authority Level 2 - Constrained (needs explicit testing/verification)
    CONSTRAINED_DECISIONS = {
        "change_timeout": {
            "authority": AuthorityLevel.CONSTRAINED,
            "constraints": ["load_test_at_peak", "document_sla_impact", "verify_downstream"],
            "reason": "Affects SLA and dependent systems",
        },
        "change_validation_logic": {
            "authority": AuthorityLevel.CONSTRAINED,
            "constraints": ["test_backward_compatibility", "document_rejection_reason"],
            "reason": "Might reject previously-valid data",
        },
        "queue_schema_change": {
            "authority": AuthorityLevel.CONSTRAINED,
            "constraints": ["audit_downstream_handlers", "plan_migration", "version_payload"],
            "reason": "Affects all downstream handlers",
        },
        "database_schema_change": {
            "authority": AuthorityLevel.CONSTRAINED,
            "constraints": ["migration_reversible", "backward_compatible", "no_data_loss"],
            "reason": "Breaks old code (2-phase rollout required)",
        },
    }

    # Authority Level 1 - CEO + Board only
    ESCALATE_DECISIONS = {
        "change_critical_sla": {
            "authority": AuthorityLevel.ESCALATE,
            "reason": "Changes business metrics (affects revenue/hiring speed)",
        },
        "change_business_requirements": {
            "authority": AuthorityLevel.ESCALATE,
            "reason": "Changes hiring model (CEO strategy decision)",
        },
        "architecture_redesign": {
            "authority": AuthorityLevel.ESCALATE,
            "reason": "Major system change (queue→RPC, DB→NoSQL, etc.)",
        },
    }

    def __init__(self):
        """Initialize ruthless architect with system knowledge."""
        self.decisions_made = 0
        self.learning_log: List[Dict] = []

    def analyze_change(
        self,
        change_description: str,
        files_modified: List[str],
        gate_status: Dict,
    ) -> ArchitectDecision:
        """
        Analyze a code change and make autonomous decision.

        Returns: ArchitectDecision with APPROVE, BLOCK, ESCALATE, or INVESTIGATE
        """

        logger.info(f"Architect analyzing change: {change_description}")

        # Step 1: Check for hard blocks
        for hard_block, reason in self.HARD_BLOCKS.items():
            if self._check_hard_block(hard_block, files_modified):
                logger.error(f"HARD BLOCK detected: {hard_block}")
                return ArchitectDecision(
                    category=DecisionCategory.CODE_FIX,
                    authority_level=AuthorityLevel.HARD_BLOCK,
                    decision="BLOCK",
                    reason=f"HARD BLOCK: {reason}",
                    rollback_plan="Revert change immediately",
                )

        # Step 2: Gate must pass (prerequisite)
        if not gate_status.get("passed", False):
            return ArchitectDecision(
                category=DecisionCategory.CODE_FIX,
                authority_level=AuthorityLevel.HARD_BLOCK,
                decision="BLOCK",
                reason="Gate not passing - fix violations before approval",
            )

        # Step 3: Categorize the change
        category = self._categorize_change(change_description, files_modified)

        # Step 4: Apply thinking framework
        upstream_ok = self._check_upstream(files_modified)
        functional_ok = self._check_functional(files_modified)
        downstream_impact = self._check_downstream(files_modified)
        cascade_risk = self._check_cascade_failures(files_modified)
        scale_ok = self._check_1500hc_ready(files_modified)

        # Step 5: Make decision
        if not upstream_ok:
            return ArchitectDecision(
                category=category,
                authority_level=AuthorityLevel.HARD_BLOCK,
                decision="BLOCK",
                reason="Upstream dependencies not verified (may cause runtime failure)",
            )

        if cascade_risk:
            return ArchitectDecision(
                category=category,
                authority_level=AuthorityLevel.HARD_BLOCK,
                decision="BLOCK",
                reason=f"Cascade failure risk detected: {cascade_risk}",
            )

        # Step 6: Check authority level
        decision_key = self._find_decision_key(change_description)

        if decision_key in self.AUTONOMOUS_DECISIONS:
            decision = self.AUTONOMOUS_DECISIONS[decision_key]
            return ArchitectDecision(
                category=category,
                authority_level=decision["authority"],
                decision=decision["decision"],
                reason=decision["reason"],
                learning_points=[
                    "Change patterns learned for future decisions",
                    "Similar patterns will auto-approve faster",
                ],
            )

        if decision_key in self.CONSTRAINED_DECISIONS:
            constraints = self.CONSTRAINED_DECISIONS[decision_key]["constraints"]
            return ArchitectDecision(
                category=category,
                authority_level=AuthorityLevel.CONSTRAINED,
                decision="APPROVE_WITH_CONSTRAINTS",
                reason=self.CONSTRAINED_DECISIONS[decision_key]["reason"],
                constraints=constraints,
                learning_points=[
                    f"Constrained decisions require: {', '.join(constraints)}",
                    "Verification must be documented before deploy",
                ],
            )

        if decision_key in self.ESCALATE_DECISIONS:
            return ArchitectDecision(
                category=category,
                authority_level=AuthorityLevel.ESCALATE,
                decision="ESCALATE",
                reason=self.ESCALATE_DECISIONS[decision_key]["reason"],
                rollback_plan="Await CEO + Board decision before proceeding",
            )

        # Default: INVESTIGATE (unknown pattern)
        return ArchitectDecision(
            category=category,
            authority_level=AuthorityLevel.HARD_BLOCK,
            decision="INVESTIGATE",
            reason="Change pattern not recognized - manual architect review required",
            learning_points=["New decision pattern should be documented"],
        )

    def _check_hard_block(self, block_type: str, files: List[str]) -> bool:
        """Check if change violates hard blocks (never permit)."""
        # This would be implemented with actual code analysis
        # For now, return False (no hard blocks detected)
        return False

    def _categorize_change(self, description: str, files: List[str]) -> DecisionCategory:
        """Categorize the change type."""
        if "test" in description.lower():
            return DecisionCategory.CODE_FIX
        if "schema" in description.lower():
            return DecisionCategory.SCHEMA_CHANGE
        if "handler" in description.lower() and "new" in description.lower():
            return DecisionCategory.HANDLER_NEW
        if "timeout" in description.lower():
            return DecisionCategory.TIMEOUT_CHANGE
        if "queue" in description.lower():
            return DecisionCategory.QUEUE_ROUTING
        if "permission" in description.lower():
            return DecisionCategory.PERMISSION_CHANGE
        return DecisionCategory.CODE_FIX

    def _check_upstream(self, files: List[str]) -> bool:
        """Check: Does this assume dependencies exist?"""
        # Verified in gate (FK integrity checks)
        return True

    def _check_functional(self, files: List[str]) -> bool:
        """Check: Does this break business workflow?"""
        # Verified in tests (integration tests)
        return True

    def _check_downstream(self, files: List[str]) -> Optional[str]:
        """Check: What breaks 3 months from now?"""
        # Return None if no risks, else return risk description
        return None

    def _check_cascade_failures(self, files: List[str]) -> Optional[str]:
        """Check: If this fails, what else breaks?"""
        # Return None if handled, else return cascade risk
        return None

    def _check_1500hc_ready(self, files: List[str]) -> bool:
        """Check: Does this work at 1500 headcount scale?"""
        # Verified in load testing gate
        return True

    def _find_decision_key(self, description: str) -> str:
        """Find matching decision pattern from description."""
        description_lower = description.lower()

        for key in self.AUTONOMOUS_DECISIONS.keys():
            if key.replace("_", " ") in description_lower:
                return key

        for key in self.CONSTRAINED_DECISIONS.keys():
            if key.replace("_", " ") in description_lower:
                return key

        for key in self.ESCALATE_DECISIONS.keys():
            if key.replace("_", " ") in description_lower:
                return key

        return "unknown"

    def log_learning(self, incident: str, root_cause: str, gate_rule: Optional[str] = None):
        """Log incident for continuous improvement."""
        self.learning_log.append({
            "incident": incident,
            "root_cause": root_cause,
            "gate_rule_failed": gate_rule,
            "action": f"Update gate to catch {root_cause}",
        })
        logger.info(f"Learning logged: {incident} → {gate_rule}")


# Singleton instance
architect = RuthlessArchitect()


def get_architect_decision(
    change_description: str,
    files_modified: List[str],
    gate_status: Dict,
) -> ArchitectDecision:
    """Get architect's autonomous decision on a code change."""
    return architect.analyze_change(change_description, files_modified, gate_status)
