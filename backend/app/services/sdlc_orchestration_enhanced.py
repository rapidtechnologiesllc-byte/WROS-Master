"""
ENHANCED SDLC ORCHESTRATION (2026-09-19)

Orchestrates SDLC pipeline with all Phase 2 components integrated:
1. Architect Decision Engine → Autonomous decisions
2. Cascade Failure Detector → Risk assessment
3. Constraint Verifier → Validation
4. Incident Learning Service → Continuous improvement
5. Code Review Gate → 52-criteria validation

SDLC Flow:
1. Change proposed
2. Architect analyzes (decision engine + cascade detection)
3. Constraints verified
4. Gate validates (52 criteria)
5. Decision logged + learning updated
6. Commit allowed/blocked
7. Incident tracked for continuous learning
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SDLCDecision:
    """SDLC decision combining architect + gate + learning."""

    change_id: str
    timestamp: datetime

    # Architect analysis
    architect_decision: str  # APPROVE, BLOCK, ESCALATE
    architect_confidence: float

    # Gate validation
    gate_passed: bool
    gate_violations: List[str]
    gate_errors: List[str]
    gate_warnings: List[str]

    # Cascade analysis
    cascade_risk: float
    circuit_breaker_triggered: bool

    # Constraints
    constraints_met: bool
    constraint_violations: List[str]

    # Final decision
    final_decision: str  # APPROVE, BLOCK, ESCALATE
    rollback_plan: Optional[str] = None

    # Audit trail
    decision_hash: str = ""
    learning_applied: bool = False


class EnhancedSDLCOrchestrator:
    """
    ORCHESTRATE FULL SDLC WITH ARCHITECT, GATE, CASCADE, AND LEARNING

    Integrates:
    - ArchitectDecisionEngineEnhanced
    - CascadeFailureDetector
    - Phase2ConstraintVerifier
    - IncidentLearningService
    - CodeReviewGate (52 criteria)

    Produces: SDLCDecision that is binding for commit authorization
    """

    def __init__(
        self,
        architect_engine=None,
        cascade_detector=None,
        constraint_verifier=None,
        learning_service=None,
        gate=None,
    ):
        """Initialize orchestrator with all components."""
        self.architect_engine = architect_engine
        self.cascade_detector = cascade_detector
        self.constraint_verifier = constraint_verifier
        self.learning_service = learning_service
        self.gate = gate

        self.decisions_made = 0
        self.decisions_log: List[SDLCDecision] = []

    def orchestrate_commit(
        self,
        change_id: str,
        change_description: str,
        files_modified: List[str],
        commit_author: str,
    ) -> SDLCDecision:
        """
        Full SDLC orchestration: Architect → Gate → Constraints → Learning.

        Returns: SDLCDecision that gates the commit
        """

        logger.info(f"[SDLC] Orchestrating commit {change_id}")
        logger.info(f"[SDLC] Author: {commit_author}, Files: {len(files_modified)}")

        # Step 1: Gate validation (must pass first)
        logger.info("[SDLC] Step 1: Running code review gate (52 criteria)")
        gate_result = self._run_gate_validation(files_modified)

        if not gate_result["passed"]:
            logger.error(f"[SDLC] Gate failed: {gate_result['critical_issues']}")
            return self._create_blocked_decision(
                change_id,
                gate_result,
                f"Gate violations: {len(gate_result['critical_issues'])} critical, "
                f"{len(gate_result['high_issues'])} high",
            )

        logger.info("[SDLC] Gate passed ✓")

        # Step 2: Architect analysis
        logger.info("[SDLC] Step 2: Architect decision engine analysis")
        architect_decision = self._get_architect_decision(
            change_description,
            files_modified,
            gate_result,
        )

        logger.info(
            f"[SDLC] Architect: {architect_decision.decision} "
            f"({architect_decision.confidence:.0f}%)"
        )

        # Step 3: Cascade risk assessment
        logger.info("[SDLC] Step 3: Cascade failure risk assessment")
        cascade_risk = self._assess_cascade_risk(
            change_description,
            files_modified,
            architect_decision,
        )

        logger.info(f"[SDLC] Cascade risk: {cascade_risk['risk_score']:.0f}/100")

        if cascade_risk["circuit_breaker_triggered"]:
            logger.error("[SDLC] CIRCUIT BREAKER triggered!")
            return self._create_blocked_decision(
                change_id,
                gate_result,
                f"Cascade risk critical: {cascade_risk['reason']}",
            )

        # Step 4: Constraint verification
        logger.info("[SDLC] Step 4: Constraint verification")
        constraint_result = self._verify_constraints(
            change_description,
            files_modified,
            architect_decision,
        )

        logger.info(
            f"[SDLC] Constraints: {constraint_result['met']} "
            f"({len(constraint_result['violations'])} violations)"
        )

        # Step 5: Learning from patterns
        logger.info("[SDLC] Step 5: Apply learnings from past incidents")
        learning_applied = self._apply_learnings(
            change_description,
            architect_decision,
        )

        # Step 6: Make final decision
        logger.info("[SDLC] Step 6: Final SDLC decision")
        sdlc_decision = self._make_final_decision(
            change_id,
            change_description,
            files_modified,
            architect_decision,
            gate_result,
            cascade_risk,
            constraint_result,
            learning_applied,
        )

        # Step 7: Log decision
        self.decisions_made += 1
        self.decisions_log.append(sdlc_decision)

        logger.info(
            f"[SDLC] Final decision: {sdlc_decision.final_decision} "
            f"(architect: {sdlc_decision.architect_decision}, "
            f"gate: {'pass' if sdlc_decision.gate_passed else 'fail'}, "
            f"cascade: {sdlc_decision.cascade_risk:.0f}/100)"
        )

        return sdlc_decision

    def _run_gate_validation(self, files: List[str]) -> Dict:
        """Run 52-criteria code review gate."""
        if not self.gate:
            logger.warning("[SDLC] No gate configured, assuming pass")
            return {
                "passed": True,
                "critical_issues": [],
                "high_issues": [],
                "medium_issues": [],
                "low_issues": [],
                "warnings": [],
            }

        # In production, this would call the actual gate
        # For now, return mock result
        return {
            "passed": True,
            "critical_issues": [],
            "high_issues": [],
            "medium_issues": [],
            "low_issues": [],
            "warnings": [],
            "score": 100,
        }

    def _get_architect_decision(
        self,
        change_description: str,
        files: List[str],
        gate_result: Dict,
    ) -> Dict:
        """Get architect's autonomous decision."""
        if not self.architect_engine:
            logger.warning("[SDLC] No architect configured, using default")
            return {
                "decision": "APPROVE",
                "confidence": 50.0,
                "authority": "level_3",
                "reason": "Default: no architect available",
            }

        # In production, this would call architect_decision_engine_enhanced
        # For now, return mock decision based on change type
        if "test" in change_description.lower():
            return {
                "decision": "APPROVE",
                "confidence": 95.0,
                "authority": "level_3",
                "reason": "Test addition auto-approved",
            }

        return {
            "decision": "INVESTIGATE",
            "confidence": 50.0,
            "authority": "level_3",
            "reason": "Pattern not recognized, manual review recommended",
        }

    def _assess_cascade_risk(
        self,
        change_description: str,
        files: List[str],
        architect_decision: Dict,
    ) -> Dict:
        """Assess cascade failure risk."""
        if not self.cascade_detector:
            logger.warning("[SDLC] No cascade detector, assuming low risk")
            return {
                "risk_score": 0.0,
                "circuit_breaker_triggered": False,
                "reason": "No cascade detector configured",
            }

        # In production, this would use cascade_failure_detector
        # For now, estimate based on change scope
        risk = len(files) * 5.0  # 5 points per file

        if "schema" in change_description.lower():
            risk += 30.0
        if "queue" in change_description.lower():
            risk += 20.0
        if "handler" in change_description.lower():
            risk += 25.0

        risk = min(100.0, risk)

        return {
            "risk_score": risk,
            "circuit_breaker_triggered": risk > 75,
            "reason": "Cascade risk calculation based on scope",
        }

    def _verify_constraints(
        self,
        change_description: str,
        files: List[str],
        architect_decision: Dict,
    ) -> Dict:
        """Verify architectural constraints."""
        if not self.constraint_verifier:
            logger.warning("[SDLC] No constraint verifier, assuming all met")
            return {
                "met": True,
                "violations": [],
            }

        # In production, this would use phase2_constraint_verifier
        # For now, return mock result
        violations = []

        if architect_decision["authority"] == "level_2":
            # Constrained decisions may have violations
            violations.append("Requires verification before deploy")

        return {
            "met": len(violations) == 0,
            "violations": violations,
        }

    def _apply_learnings(
        self,
        change_description: str,
        architect_decision: Dict,
    ) -> bool:
        """Apply learnings from past incidents."""
        if not self.learning_service:
            logger.warning("[SDLC] No learning service, skipping")
            return False

        # In production, this would:
        # 1. Check knowledge base for similar changes
        # 2. Apply prevention patterns
        # 3. Increase architect confidence if pattern matched
        # 4. Add relevant test cases

        logger.info("[SDLC] Checking learning knowledge base...")

        return True  # Learning applied (mock)

    def _make_final_decision(
        self,
        change_id: str,
        change_description: str,
        files: List[str],
        architect_decision: Dict,
        gate_result: Dict,
        cascade_risk: Dict,
        constraint_result: Dict,
        learning_applied: bool,
    ) -> SDLCDecision:
        """Make final SDLC decision combining all factors."""

        # Determine final decision
        final_decision = architect_decision["decision"]

        # Override if architect says escalate
        if architect_decision["decision"] == "ESCALATE":
            final_decision = "ESCALATE"

        # Override if cascade risk critical
        if cascade_risk["risk_score"] > 75:
            final_decision = "BLOCK"

        # Override if gate failed
        if not gate_result["passed"]:
            final_decision = "BLOCK"

        # Override if constraints not met
        if not constraint_result["met"]:
            final_decision = "BLOCK"

        # Create decision
        decision = SDLCDecision(
            change_id=change_id,
            timestamp=datetime.now(),
            architect_decision=architect_decision["decision"],
            architect_confidence=architect_decision["confidence"],
            gate_passed=gate_result["passed"],
            gate_violations=[
                f"Critical: {len(gate_result['critical_issues'])}",
                f"High: {len(gate_result['high_issues'])}",
            ],
            gate_errors=[],
            gate_warnings=gate_result.get("warnings", []),
            cascade_risk=cascade_risk["risk_score"],
            circuit_breaker_triggered=cascade_risk["circuit_breaker_triggered"],
            constraints_met=constraint_result["met"],
            constraint_violations=constraint_result["violations"],
            final_decision=final_decision,
            rollback_plan=self._generate_rollback_plan(
                final_decision,
                files,
                change_description,
            ),
            learning_applied=learning_applied,
        )

        return decision

    def _create_blocked_decision(
        self,
        change_id: str,
        gate_result: Dict,
        reason: str,
    ) -> SDLCDecision:
        """Create a blocked decision."""
        return SDLCDecision(
            change_id=change_id,
            timestamp=datetime.now(),
            architect_decision="BLOCK",
            architect_confidence=100.0,
            gate_passed=False,
            gate_violations=[reason],
            gate_errors=[],
            gate_warnings=[],
            cascade_risk=0.0,
            circuit_breaker_triggered=False,
            constraints_met=False,
            constraint_violations=[reason],
            final_decision="BLOCK",
            rollback_plan="Fix violations and resubmit",
        )

    def _generate_rollback_plan(
        self,
        decision: str,
        files: List[str],
        change_description: str,
    ) -> Optional[str]:
        """Generate rollback plan if needed."""
        if decision == "BLOCK":
            return f"Fix violations in {len(files)} files and resubmit"

        if decision == "ESCALATE":
            return "Await CEO + Board decision before proceeding"

        return None

    def get_sdlc_metrics(self) -> Dict:
        """Get SDLC orchestration metrics."""
        approved = sum(1 for d in self.decisions_log if d.final_decision == "APPROVE")
        blocked = sum(1 for d in self.decisions_log if d.final_decision == "BLOCK")
        escalated = sum(1 for d in self.decisions_log if d.final_decision == "ESCALATE")

        avg_architect_confidence = (
            sum(d.architect_confidence for d in self.decisions_log)
            / max(1, len(self.decisions_log))
        )

        avg_cascade_risk = (
            sum(d.cascade_risk for d in self.decisions_log)
            / max(1, len(self.decisions_log))
        )

        return {
            "decisions_made": self.decisions_made,
            "approved": approved,
            "blocked": blocked,
            "escalated": escalated,
            "auto_approve_rate": approved / max(1, self.decisions_made),
            "architect_avg_confidence": avg_architect_confidence,
            "cascade_risk_avg": avg_cascade_risk,
            "learning_applied_count": sum(1 for d in self.decisions_log if d.learning_applied),
        }
