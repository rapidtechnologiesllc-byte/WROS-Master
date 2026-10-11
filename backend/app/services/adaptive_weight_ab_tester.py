"""Adaptive Weight A/B Tester - Thompson sampling allocation + stage transitions

Implements:
1. Thompson sampling for adaptive traffic allocation
2. Stage progression (EXPERIMENT → EXPAND → FULL_ROLLOUT)
3. Rollback triggers (formation health < 70%, accuracy regression)
4. Statistical significance testing (p-value, CI)
5. Automatic variant deployment when variant wins
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.ab_test_deployment import (
    ABTestDeployment,
    ABTestDecision,
    ABTestStageMetrics,
)
from app.models.genetic_weight_population import GeneticWeightChromosome
from scipy import stats

logger = logging.getLogger(__name__)


class AdaptiveWeightABTester:
    """A/B test weight variants using Thompson sampling"""

    # Stage parameters
    EXPERIMENT_DECISIONS = 100  # 5% traffic stage
    EXPAND_DECISIONS = 400  # 25% traffic stage
    FULL_ROLLOUT_DECISIONS = 1000  # 100% traffic stage

    # Formation health threshold for rollback
    FORMATION_HEALTH_ROLLBACK_THRESHOLD = 0.70

    @staticmethod
    def log_decision(
        db: Session,
        test_id: str,
        variant: str,  # "baseline" or "variant"
        predicted_confidence: float,
        actual_success: bool,
        execution_time_ms: int = 0,
    ) -> ABTestDecision:
        """Log a single decision in A/B test"""
        decision = ABTestDecision(
            decision_id=str(uuid.uuid4()),
            test_id=test_id,
            variant=variant,
            predicted_confidence=predicted_confidence,
            actual_success=actual_success,
            execution_time_ms=execution_time_ms,
            confidence_gap=abs(predicted_confidence - (1.0 if actual_success else 0.0)),
        )

        db.add(decision)
        db.commit()

        return decision

    @staticmethod
    def compute_thompson_allocation(
        db: Session, test_id: str
    ) -> Dict[str, float]:
        """
        Compute Thompson sampling allocation for next traffic split.

        Thompson sampling: For each variant, sample from posterior distribution
        of success rate, allocate traffic proportional to sampled success rate.
        """
        test = db.query(ABTestDeployment).filter(
            ABTestDeployment.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        # Get decisions for baseline and variant
        baseline_decisions = db.query(ABTestDecision).filter(
            and_(ABTestDecision.test_id == test_id, ABTestDecision.variant == "baseline")
        ).all()

        variant_decisions = db.query(ABTestDecision).filter(
            and_(ABTestDecision.test_id == test_id, ABTestDecision.variant == "variant")
        ).all()

        # Compute success counts
        baseline_successes = sum(
            1 for d in baseline_decisions if d.actual_success
        )
        baseline_failures = len(baseline_decisions) - baseline_successes

        variant_successes = sum(
            1 for d in variant_decisions if d.actual_success
        )
        variant_failures = len(variant_decisions) - variant_successes

        # Thompson sampling: Beta(successes + 1, failures + 1)
        # Sample from posterior distribution
        baseline_sample = (
            1.0
            if len(baseline_decisions) == 0
            else max(0.0, min(1.0,
                stats.beta.rvs(
                    baseline_successes + 1, baseline_failures + 1
                )
            ))
        )
        variant_sample = (
            1.0
            if len(variant_decisions) == 0
            else max(0.0, min(1.0,
                stats.beta.rvs(
                    variant_successes + 1, variant_failures + 1
                )
            ))
        )

        # Allocation proportional to samples
        total = baseline_sample + variant_sample
        baseline_allocation = (
            baseline_sample / total if total > 0 else 0.5
        )
        variant_allocation = 1.0 - baseline_allocation

        return {
            "baseline_allocation": baseline_allocation,
            "variant_allocation": variant_allocation,
            "baseline_successes": baseline_successes,
            "baseline_total": len(baseline_decisions),
            "variant_successes": variant_successes,
            "variant_total": len(variant_decisions),
        }

    @staticmethod
    def evaluate_stage_metrics(
        db: Session, test_id: str, stage: str
    ) -> ABTestStageMetrics:
        """Compute stage-level metrics with statistical significance"""
        test = db.query(ABTestDeployment).filter(
            ABTestDeployment.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        # Get decisions for this stage
        baseline_decisions = db.query(ABTestDecision).filter(
            and_(
                ABTestDecision.test_id == test_id,
                ABTestDecision.variant == "baseline",
                ABTestDecision.stage == stage,
            )
        ).all()

        variant_decisions = db.query(ABTestDecision).filter(
            and_(
                ABTestDecision.test_id == test_id,
                ABTestDecision.variant == "variant",
                ABTestDecision.stage == stage,
            )
        ).all()

        # Compute accuracy
        baseline_accuracy = (
            sum(1 for d in baseline_decisions if d.actual_success)
            / len(baseline_decisions)
            if baseline_decisions
            else 0.0
        )
        variant_accuracy = (
            sum(1 for d in variant_decisions if d.actual_success)
            / len(variant_decisions)
            if variant_decisions
            else 0.0
        )

        accuracy_improvement = variant_accuracy - baseline_accuracy

        # Chi-square test for significance
        contingency_table = [
            [
                sum(1 for d in baseline_decisions if d.actual_success),
                sum(1 for d in baseline_decisions if not d.actual_success),
            ],
            [
                sum(1 for d in variant_decisions if d.actual_success),
                sum(1 for d in variant_decisions if not d.actual_success),
            ],
        ]

        try:
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        except:
            p_value = 1.0

        # Compute 95% confidence interval using proportions
        variant_ci_lower = (
            max(0, variant_accuracy - 1.96 * (variant_accuracy * (1 - variant_accuracy) / max(1, len(variant_decisions))) ** 0.5)
            if variant_decisions
            else 0.0
        )
        variant_ci_upper = (
            min(1, variant_accuracy + 1.96 * (variant_accuracy * (1 - variant_accuracy) / max(1, len(variant_decisions))) ** 0.5)
            if variant_decisions
            else 1.0
        )

        stage_metrics = ABTestStageMetrics(
            stage_metric_id=str(uuid.uuid4()),
            test_id=test_id,
            stage=stage,
            baseline_count=len(baseline_decisions),
            variant_count=len(variant_decisions),
            baseline_accuracy=baseline_accuracy,
            variant_accuracy=variant_accuracy,
            accuracy_improvement=accuracy_improvement,
            p_value=p_value,
            confidence_interval_lower=variant_ci_lower,
            confidence_interval_upper=variant_ci_upper,
        )

        db.add(stage_metrics)
        db.commit()

        return stage_metrics

    @staticmethod
    def should_advance_stage(
        db: Session, test_id: str
    ) -> tuple[bool, str]:
        """Decide whether to advance to next stage"""
        test = db.query(ABTestDeployment).filter(
            ABTestDeployment.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        current_stage = test.current_stage
        target_decisions = test.stage_target_decisions or 100
        required_improvement = test.stage_required_improvement or 0.02

        # Count decisions in current stage
        decisions = db.query(ABTestDecision).filter(
            and_(
                ABTestDecision.test_id == test_id,
                ABTestDecision.stage == current_stage,
            )
        ).count()

        if decisions < target_decisions:
            return False, f"Need {target_decisions - decisions} more decisions"

        # Evaluate metrics
        stage_metrics = AdaptiveWeightABTester.evaluate_stage_metrics(
            db, test_id, current_stage
        )

        # Advance if:
        # 1. Variant accuracy improved > required_improvement
        # 2. Improvement is statistically significant (p < 0.05)
        if (
            stage_metrics.accuracy_improvement > required_improvement
            and stage_metrics.p_value < 0.05
        ):
            return True, (
                f"Variant improved by {stage_metrics.accuracy_improvement:.2%} "
                f"(p={stage_metrics.p_value:.4f})"
            )

        return False, (
            f"Improvement {stage_metrics.accuracy_improvement:.2%} "
            f"below required {required_improvement:.2%}"
        )

    @staticmethod
    def advance_stage(db: Session, test_id: str) -> ABTestDeployment:
        """Advance to next stage"""
        test = db.query(ABTestDeployment).filter(
            ABTestDeployment.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        stage_transitions = {
            "EXPERIMENT": "EXPAND",
            "EXPAND": "FULL_ROLLOUT",
            "FULL_ROLLOUT": "COMPLETED",
        }

        next_stage = stage_transitions.get(test.current_stage)

        if not next_stage:
            raise ValueError(f"Cannot advance from stage {test.current_stage}")

        test.current_stage = next_stage
        test.stage_start_time = datetime.utcnow()
        test.stage_duration_seconds = 0

        # Update allocation based on stage
        if next_stage == "EXPAND":
            test.experiment_allocation = 0.25  # Increase to 25%
        elif next_stage == "FULL_ROLLOUT":
            test.experiment_allocation = 1.0  # 100% traffic

        db.commit()

        logger.info(
            f"[ABTester] Advanced test {test_id} from {test.current_stage} to {next_stage}"
        )

        return test

    @staticmethod
    def check_rollback_triggers(
        db: Session, test_id: str
    ) -> tuple[bool, Optional[str]]:
        """Check if test should be rolled back"""
        test = db.query(ABTestDeployment).filter(
            ABTestDeployment.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        # Check 1: Formation health below threshold
        if test.variant_formation_health and test.variant_formation_health < AdaptiveWeightABTester.FORMATION_HEALTH_ROLLBACK_THRESHOLD:
            return True, (
                f"Variant formation health {test.variant_formation_health:.2%} "
                f"below {AdaptiveWeightABTester.FORMATION_HEALTH_ROLLBACK_THRESHOLD:.2%}"
            )

        # Check 2: Variant accuracy regression
        if (
            test.baseline_accuracy
            and test.variant_accuracy
            and test.variant_accuracy < test.baseline_accuracy * 0.95
        ):
            return (
                True,
                f"Variant accuracy regressed to {test.variant_accuracy:.2%} "
                f"({test.baseline_accuracy:.2%} baseline)",
            )

        # Check 3: High error rate in variant
        variant_decisions = db.query(ABTestDecision).filter(
            and_(
                ABTestDecision.test_id == test_id,
                ABTestDecision.variant == "variant",
            )
        ).all()

        error_rate = (
            sum(1 for d in variant_decisions if d.error_count > 0)
            / len(variant_decisions)
            if variant_decisions
            else 0.0
        )

        if error_rate > 0.10:  # > 10% error rate
            return True, f"Variant error rate {error_rate:.2%} exceeds 10% threshold"

        return False, None

    @staticmethod
    def rollback_test(db: Session, test_id: str, reason: str) -> ABTestDeployment:
        """Rollback test, revert to baseline"""
        test = db.query(ABTestDeployment).filter(
            ABTestDeployment.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"Test {test_id} not found")

        test.current_stage = "ROLLED_BACK"
        test.rolled_back = True
        test.rollback_reason = reason
        test.rollback_at = datetime.utcnow()

        db.commit()

        logger.warning(f"[ABTester] Rolled back test {test_id}: {reason}")

        return test
