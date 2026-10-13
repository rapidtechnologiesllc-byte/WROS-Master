"""Queue Processor Learning Integration - Phase 4
Triggers autonomous learning cycle after message processing

Integrates queue processor with genetic algorithm evolution system:
1. After message COMPLETED, track decision outcome
2. When decision count reaches WEIGHT_UPDATE_FREQUENCY (50), trigger genetic evolution
3. Genetic evolution triggers A/B test if fitness improves > 5%
4. A/B test triggers behavioral rules and cascading signals
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.unified_learning_orchestrator import UnifiedLearningOrchestrator
from app.services.genetic_weight_evolver import GeneticWeightEvolver
from app.services.dynamic_weight_loader import DynamicWeightLoader
from app.models.genetic_weight_population import GeneticWeightPopulation
from sqlalchemy import and_, desc

logger = logging.getLogger(__name__)


class QueueProcessorLearningIntegration:
    """Orchestrate learning cycle after message processing"""

    # Decision count threshold before triggering weight update
    DECISIONS_PER_WEIGHT_UPDATE = 50

    @staticmethod
    def trigger_learning_cycle_if_needed(
        db: Session,
        tenant_id: str,
        orchestrator: str,
        handler_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if learning cycle should run after message completion.

        Runs when:
        1. Message processed successfully
        2. Decision count for orchestrator >= DECISIONS_PER_WEIGHT_UPDATE

        Returns learning cycle report or None if cycle not triggered.
        """
        try:
            # Get current population for orchestrator
            population = (
                db.query(GeneticWeightPopulation)
                .filter(
                    and_(
                        GeneticWeightPopulation.orchestrator == orchestrator,
                        GeneticWeightPopulation.tenant_id == tenant_id,
                        GeneticWeightPopulation.status != "ROLLED_BACK",
                    )
                )
                .order_by(desc(GeneticWeightPopulation.generation_number))
                .first()
            )

            if not population:
                # Initialize population if missing
                logger.info(
                    f"[LearningIntegration] No population for {orchestrator}, initializing..."
                )
                population = GeneticWeightEvolver.initialize_population(
                    db, tenant_id, orchestrator, generation_number=1
                )

            # Check if we've processed enough decisions to trigger weight update
            decision_count = QueueProcessorLearningIntegration._get_recent_decision_count(
                db, tenant_id, orchestrator
            )

            if decision_count < QueueProcessorLearningIntegration.DECISIONS_PER_WEIGHT_UPDATE:
                # Not enough decisions yet, don't trigger learning
                return None

            logger.info(
                f"[LearningIntegration] {decision_count} decisions processed for {orchestrator}, "
                f"triggering learning cycle"
            )

            # Trigger learning cycle
            cycle_result = QueueProcessorLearningIntegration._run_autonomous_learning_cycle(
                db, tenant_id, orchestrator, population
            )

            return cycle_result

        except Exception as e:
            logger.error(
                f"[LearningIntegration] Error triggering learning cycle: {e}",
                exc_info=True
            )
            # Don't fail message processing if learning fails
            return None

    @staticmethod
    def _get_recent_decision_count(
        db: Session,
        tenant_id: str,
        orchestrator: str,
    ) -> int:
        """Count decisions processed in recent batch"""
        # This would query the SLM learning metrics or decision log
        # For now, return a placeholder - in production this would query actual decision count
        from app.models.slm_learning_metrics import ThunderLearningMetrics, FlashLearningMetrics

        if orchestrator == "thunder":
            metric_class = ThunderLearningMetrics
        elif orchestrator == "flash":
            metric_class = FlashLearningMetrics
        else:
            return 0

        count = (
            db.query(metric_class)
            .filter(metric_class.tenant_id == tenant_id)
            .count()
        )

        return count

    @staticmethod
    def _run_autonomous_learning_cycle(
        db: Session,
        tenant_id: str,
        orchestrator: str,
        current_population: GeneticWeightPopulation,
    ) -> Dict[str, Any]:
        """
        Execute full autonomous learning cycle:
        1. Evaluate current generation fitness
        2. Detect convergence
        3. Create next generation
        4. Trigger A/B test if fitness improves
        5. Check behavioral rules
        6. Detect cascade failures
        """
        cycle_start = {
            "orchestrator": orchestrator,
            "generation": current_population.generation_number,
        }

        try:
            # Step 1: Evaluate generation fitness
            logger.info(
                f"[LearningIntegration] Evaluating generation G{current_population.generation_number} "
                f"for {orchestrator}"
            )
            evaluation = GeneticWeightEvolver.evaluate_generation(
                db, tenant_id, current_population.population_id
            )

            cycle_start["evaluation"] = evaluation
            logger.info(
                f"[LearningIntegration] Evaluation complete: avg_fitness={evaluation['average_fitness']:.4f}, "
                f"improvement={evaluation['fitness_improvement']:.4f}"
            )

            # Step 2: Check convergence
            converged, convergence_reason = GeneticWeightEvolver.detect_convergence(
                db, current_population.population_id
            )
            cycle_start["converged"] = converged
            if converged:
                logger.info(
                    f"[LearningIntegration] Population converged: {convergence_reason}"
                )

            # Step 3: Create next generation
            logger.info(
                f"[LearningIntegration] Creating next generation from G{current_population.generation_number}"
            )
            next_population = GeneticWeightEvolver.create_next_generation(
                db, tenant_id, current_population.population_id
            )
            cycle_start["next_generation"] = next_population.generation_number

            # Step 4: Check if AB test should be triggered
            ab_test = GeneticWeightEvolver.trigger_ab_test_if_needed(
                db, tenant_id, next_population.population_id
            )
            if ab_test:
                cycle_start["ab_test_triggered"] = ab_test.test_id
                logger.info(
                    f"[LearningIntegration] A/B test triggered: {ab_test.test_id}"
                )

            # Step 5: Clear weight cache so next decisions use new weights
            DynamicWeightLoader.clear_weight_cache(tenant_id)
            logger.info(
                f"[LearningIntegration] Weight cache cleared for tenant {tenant_id}"
            )

            # Step 6: Run unified learning orchestrator
            logger.info(
                f"[LearningIntegration] Running unified learning orchestrator for {orchestrator}"
            )
            orchestrator_report = UnifiedLearningOrchestrator.run_learning_cycle(
                db, tenant_id
            )
            cycle_start["orchestrator_report"] = orchestrator_report

            logger.info(
                f"[LearningIntegration] Learning cycle complete for {orchestrator}"
            )
            return cycle_start

        except Exception as e:
            logger.error(
                f"[LearningIntegration] Error in learning cycle: {e}",
                exc_info=True
            )
            cycle_start["error"] = str(e)
            return cycle_start
