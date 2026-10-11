"""Unified Learning Weight Service - Single source for weight optimization

Consolidates functionality from:
- learning_weight_optimizer.py (batch analysis and weight computation)
- slm_learning_framework.py (weight update methods)

Provides:
- Decision batch analysis
- Weight computation from accuracy metrics
- Weight application with exponential smoothing
- Confidence calibration monitoring
- Weight history tracking
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.learning_weights import LearningWeightUpdate, LearningWeightHistory

logger = logging.getLogger(__name__)


class UnifiedLearningWeightService:
    """Unified service for learning weight optimization"""

    # Configuration
    OPERATIONS_PER_BATCH = 50  # Update weights after 50 operations
    MIN_DECISIONS_FOR_UPDATE = 5  # Need at least 5 decisions to update
    CONFIDENCE_OVERCONFIDENCE_THRESHOLD = 0.15  # 15% gap = overconfident
    CONFIDENCE_UNDERCONFIDENCE_THRESHOLD = 0.05  # 5% gap = target
    WEIGHT_DECAY = 0.9  # Exponential smoothing: 90% old, 10% new

    @staticmethod
    def analyze_decision_batch(
        db: Session,
        tenant_id: str,
        decision_batch: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze a batch of completed decisions.

        Called by learning orchestrator after collecting decision outcomes.

        Args:
            db: Database session
            tenant_id: Tenant ID
            decision_batch: List of decision records with predicted and actual outcomes

        Returns:
            Analysis results with accuracy, calibration, patterns
        """
        try:
            if not decision_batch or len(decision_batch) < UnifiedLearningWeightService.MIN_DECISIONS_FOR_UPDATE:
                return {
                    "batch_size": len(decision_batch),
                    "min_required": UnifiedLearningWeightService.MIN_DECISIONS_FOR_UPDATE,
                    "analyzable": False,
                    "reason": "Batch too small",
                }

            # Separate by module for individual analysis
            by_module = {}
            for decision in decision_batch:
                module = decision.get("orchestrator", "unknown")
                if module not in by_module:
                    by_module[module] = []
                by_module[module].append(decision)

            # Analyze each module
            module_analyses = {}
            for module, decisions in by_module.items():
                module_analyses[module] = (
                    UnifiedLearningWeightService._analyze_module_decisions(decisions)
                )

            # Aggregate analysis
            total_decisions = len(decision_batch)
            completed = sum(1 for d in decision_batch if d.get("status") == "completed")

            correct_predictions = sum(
                1
                for d in decision_batch
                if d.get("status") == "completed"
                and (
                    (d.get("actual_success") and d.get("predicted_probability", 0) >= 0.5)
                    or (not d.get("actual_success") and d.get("predicted_probability", 0) < 0.5)
                )
            )

            overall_accuracy = (
                correct_predictions / completed if completed > 0 else 0.0
            )

            # Confidence gap analysis
            gaps = [
                abs(d.get("predicted_probability", 0.5) - (1.0 if d.get("actual_success") else 0.0))
                for d in decision_batch
                if d.get("status") == "completed"
            ]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0.0

            is_overconfident = avg_gap > UnifiedLearningWeightService.CONFIDENCE_OVERCONFIDENCE_THRESHOLD
            is_underconfident = avg_gap < UnifiedLearningWeightService.CONFIDENCE_UNDERCONFIDENCE_THRESHOLD

            return {
                "batch_size": total_decisions,
                "completed": completed,
                "analyzable": True,
                "overall_accuracy": overall_accuracy,
                "average_confidence_gap": avg_gap,
                "is_overconfident": is_overconfident,
                "is_underconfident": is_underconfident,
                "calibration_status": (
                    "overconfident" if is_overconfident
                    else "underconfident" if is_underconfident
                    else "well_calibrated"
                ),
                "module_analyses": module_analyses,
            }

        except Exception as e:
            logger.error(f"Failed to analyze decision batch: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def compute_weight_updates(
        db: Session,
        tenant_id: str,
        batch_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute new weights based on batch analysis.

        Weight adjustment strategy:
        - If overconfident: reduce weights by 10%
        - If underconfident: increase weights by 5%
        - If well-calibrated: keep weights stable

        Args:
            db: Database session
            tenant_id: Tenant ID
            batch_analysis: Results from analyze_decision_batch

        Returns:
            New weight updates for all modules
        """
        try:
            if not batch_analysis.get("analyzable"):
                return {
                    "computed": False,
                    "reason": batch_analysis.get("reason", "Not analyzable"),
                }

            calibration_status = batch_analysis.get("calibration_status", "well_calibrated")

            # Determine adjustment factor based on calibration
            if calibration_status == "overconfident":
                adjustment_factor = 0.9  # Reduce weights
            elif calibration_status == "underconfident":
                adjustment_factor = 1.05  # Increase weights
            else:
                adjustment_factor = 1.0  # Keep stable

            # Compute module-specific weights
            new_weights = {}
            for module, analysis in batch_analysis.get("module_analyses", {}).items():
                accuracy = analysis.get("accuracy", 0.5)

                # Weight = accuracy * adjustment_factor
                new_weight = accuracy * adjustment_factor

                # Clamp to 0-1
                new_weight = max(0.0, min(1.0, new_weight))

                new_weights[module] = {
                    "module": module,
                    "accuracy": accuracy,
                    "adjustment_factor": adjustment_factor,
                    "new_weight": new_weight,
                }

            return {
                "computed": True,
                "calibration_status": calibration_status,
                "adjustment_factor": adjustment_factor,
                "new_weights": new_weights,
            }

        except Exception as e:
            logger.error(f"Failed to compute weight updates: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def apply_weight_updates(
        db: Session,
        tenant_id: str,
        module: str,
        new_weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Apply new weights to a module.

        Uses exponential smoothing: new_value = 90% old + 10% new

        Args:
            db: Database session
            tenant_id: Tenant ID
            module: Module name (thunder, flash, interview, offer, finance, employee)
            new_weights: New weight values

        Returns:
            Update record with old and new values
        """
        try:
            # Get current weights
            current = db.query(LearningWeightUpdate).filter(
                and_(
                    LearningWeightUpdate.tenant_id == tenant_id,
                    LearningWeightUpdate.module == module,
                )
            ).order_by(LearningWeightUpdate.updated_at.desc()).first()

            old_weights = {}
            if current:
                old_weights = json.loads(current.weights) if current.weights else {}

            # Apply exponential smoothing
            smoothed_weights = {}
            for key, new_value in new_weights.items():
                old_value = old_weights.get(key, 0.5)
                smoothed = (
                    old_value * UnifiedLearningWeightService.WEIGHT_DECAY
                    + new_value * (1 - UnifiedLearningWeightService.WEIGHT_DECAY)
                )
                smoothed_weights[key] = smoothed

            # Create update record
            weight_update = LearningWeightUpdate(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                module=module,
                weights=json.dumps(smoothed_weights),
                old_weights=json.dumps(old_weights),
                reason="Batch accuracy analysis",
                updated_at=datetime.utcnow(),
            )
            db.add(weight_update)

            # Keep history
            weight_history = LearningWeightHistory(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                module=module,
                weights=json.dumps(smoothed_weights),
                timestamp=datetime.utcnow(),
            )
            db.add(weight_history)

            db.commit()

            return {
                "module": module,
                "update_id": weight_update.id,
                "old_weights": old_weights,
                "new_weights": smoothed_weights,
                "applied_at": weight_update.updated_at,
            }

        except Exception as e:
            logger.error(f"Failed to apply weight updates: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def get_weight_history(
        db: Session,
        tenant_id: str,
        module: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Get historical weight progression for a module.

        Args:
            db: Database session
            tenant_id: Tenant ID
            module: Module name
            days: How many days of history to return

        Returns:
            List of weight changes over time
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)

            history = db.query(LearningWeightHistory).filter(
                and_(
                    LearningWeightHistory.tenant_id == tenant_id,
                    LearningWeightHistory.module == module,
                    LearningWeightHistory.timestamp >= cutoff_time,
                )
            ).order_by(LearningWeightHistory.timestamp).all()

            return [
                {
                    "timestamp": h.timestamp,
                    "module": h.module,
                    "weights": json.loads(h.weights) if h.weights else {},
                }
                for h in history
            ]

        except Exception as e:
            logger.error(f"Failed to get weight history: {e}", exc_info=True)
            return []

    @staticmethod
    def calibrate_confidence(
        db: Session,
        tenant_id: str,
        batch_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check confidence calibration and flag issues.

        Confidence should equal actual success rate:
        - If we say 70% confidence, 70% should succeed
        - Gap should be minimal (target <5%)

        Args:
            db: Database session
            tenant_id: Tenant ID
            batch_analysis: Batch analysis results

        Returns:
            Calibration report with recommendations
        """
        try:
            avg_gap = batch_analysis.get("average_confidence_gap", 0.0)
            calibration = batch_analysis.get("calibration_status", "unknown")

            recommendations = []

            if calibration == "overconfident":
                recommendations.append(
                    "Reduce confidence thresholds by 10-15% to match actual success rate"
                )
                recommendations.append(
                    f"Current gap: {avg_gap:.2%}, target: <5%"
                )

            elif calibration == "underconfident":
                recommendations.append(
                    "Increase confidence thresholds to better utilize past data"
                )
                recommendations.append(
                    f"Current gap: {avg_gap:.2%}, opportunity: +{(0.05 - avg_gap):.2%}"
                )

            else:
                recommendations.append(
                    "Confidence calibration is good, maintain current approach"
                )

            return {
                "calibration_status": calibration,
                "average_gap": avg_gap,
                "target_gap": 0.05,
                "gap_vs_target": avg_gap - 0.05,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Failed to calibrate confidence: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def _analyze_module_decisions(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Internal: Analyze decisions for a single module."""
        completed = [d for d in decisions if d.get("status") == "completed"]

        if not completed:
            return {
                "total": len(decisions),
                "completed": 0,
                "accuracy": 0.0,
            }

        correct = sum(
            1
            for d in completed
            if (d.get("actual_success") and d.get("predicted_probability", 0) >= 0.5)
            or (not d.get("actual_success") and d.get("predicted_probability", 0) < 0.5)
        )

        accuracy = correct / len(completed) if completed else 0.0

        gaps = [
            abs(d.get("predicted_probability", 0.5) - (1.0 if d.get("actual_success") else 0.0))
            for d in completed
        ]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0.0

        return {
            "total": len(decisions),
            "completed": len(completed),
            "accuracy": accuracy,
            "average_gap": avg_gap,
        }
