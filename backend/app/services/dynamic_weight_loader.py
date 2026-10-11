"""Dynamic Weight Loader - Load evolved weights at runtime from genetic populations

Implements:
1. Load best-performing weights from genetic population
2. AB test variant selection (Thompson sampling)
3. Weight version management
4. Thread-safe weight caching
5. Fallback to baseline if variant unavailable
"""

import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.genetic_weight_population import (
    GeneticWeightPopulation,
    GeneticWeightChromosome,
)
from app.models.ab_test_deployment import ABTestDeployment
from app.services.adaptive_weight_ab_tester import AdaptiveWeightABTester

logger = logging.getLogger(__name__)


class DynamicWeightLoader:
    """Load and manage evolved weights at runtime"""

    # Thread-safe weight cache
    _weight_cache = {}
    _cache_lock = threading.RLock()

    @staticmethod
    def get_current_weights(
        db: Session,
        tenant_id: str,
        orchestrator: str,
    ) -> Dict[str, Any]:
        """
        Get current weights for orchestrator.

        Priority:
        1. If active AB test with variant in EXPAND/FULL_ROLLOUT: use variant
        2. If active AB test with variant in EXPERIMENT: 5% variant, 95% baseline (Thompson)
        3. If best-performer available: use latest generation best
        4. Fallback: use default weights
        """
        cache_key = f"{tenant_id}:{orchestrator}"

        # Check cache first
        with DynamicWeightLoader._cache_lock:
            if cache_key in DynamicWeightLoader._weight_cache:
                cached = DynamicWeightLoader._weight_cache[cache_key]
                # Refresh cache every 5 minutes
                if (
                    datetime.utcnow() - cached["timestamp"]
                ).seconds < 300:
                    return cached["weights"]

        # Get latest population
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
            logger.warning(
                f"[WeightLoader] No population found for {orchestrator}, using defaults"
            )
            return DynamicWeightLoader._get_default_weights(orchestrator)

        weights = None

        # Check if population is in active AB test
        if population.ab_test_id:
            ab_test = db.query(ABTestDeployment).filter(
                ABTestDeployment.test_id == population.ab_test_id
            ).first()

            if ab_test and ab_test.current_stage != "ROLLED_BACK":
                if ab_test.current_stage == "EXPERIMENT":
                    # Thompson sampling allocation
                    allocation = AdaptiveWeightABTester.compute_thompson_allocation(
                        db, ab_test.test_id
                    )
                    variant_allocation = allocation["variant_allocation"]

                    if variant_allocation > 0.5:
                        # Use variant
                        variant_chromosome = db.query(GeneticWeightChromosome).filter(
                            GeneticWeightChromosome.chromosome_id
                            == ab_test.variant_chromosome_id
                        ).first()

                        if variant_chromosome:
                            weights = variant_chromosome.weight_schema
                            logger.info(
                                f"[WeightLoader] Using variant weights (Thompson: {variant_allocation:.1%})"
                            )
                    else:
                        # Use baseline
                        baseline_chromosome = db.query(GeneticWeightChromosome).filter(
                            GeneticWeightChromosome.chromosome_id
                            == ab_test.baseline_chromosome_id
                        ).first()

                        if baseline_chromosome:
                            weights = baseline_chromosome.weight_schema
                            logger.info(
                                f"[WeightLoader] Using baseline weights (Thompson: {1-variant_allocation:.1%})"
                            )

                elif ab_test.current_stage in ["EXPAND", "FULL_ROLLOUT"]:
                    # Use variant (winning)
                    variant_chromosome = db.query(GeneticWeightChromosome).filter(
                        GeneticWeightChromosome.chromosome_id
                        == ab_test.variant_chromosome_id
                    ).first()

                    if variant_chromosome:
                        weights = variant_chromosome.weight_schema
                        logger.info(
                            f"[WeightLoader] Using winning variant weights (stage={ab_test.current_stage})"
                        )

        # If not from AB test, use best-performer from current generation
        if not weights and population.best_performer_id:
            best_chromosome = db.query(GeneticWeightChromosome).filter(
                and_(
                    GeneticWeightChromosome.chromosome_id == population.best_performer_id,
                    GeneticWeightChromosome.population_id == population.population_id,
                )
            ).first()

            if best_chromosome:
                weights = best_chromosome.weight_schema
                logger.info(
                    f"[WeightLoader] Using best-performer weights "
                    f"(G{population.generation_number}, fitness={best_chromosome.fitness_score:.4f})"
                )

        # Fallback to defaults
        if not weights:
            logger.warning(f"[WeightLoader] Fallback to default weights for {orchestrator}")
            weights = DynamicWeightLoader._get_default_weights(orchestrator)

        # Update cache
        with DynamicWeightLoader._cache_lock:
            DynamicWeightLoader._weight_cache[cache_key] = {
                "weights": weights,
                "timestamp": datetime.utcnow(),
                "source": "dynamic",
            }

        return weights

    @staticmethod
    def _get_default_weights(orchestrator: str) -> Dict[str, Any]:
        """Get default weights (baseline)"""
        if orchestrator == "thunder":
            return {
                "channel_weights": {
                    "email": 0.4,
                    "sms": 0.3,
                    "whatsapp": 0.3,
                },
                "timing_weights": {
                    "morning": 0.3,
                    "afternoon": 0.4,
                    "evening": 0.3,
                },
                "confidence_thresholds": {
                    "high_confidence": 0.8,
                    "medium_confidence": 0.6,
                    "low_confidence": 0.4,
                },
                "bias_corrections": {
                    "recency_bias": 0.1,
                    "urgency_bias": 0.15,
                },
            }
        else:  # flash, interview, offer, finance
            return {
                "match_quality_weights": {
                    "skill_match": 0.4,
                    "experience_match": 0.3,
                    "cultural_fit": 0.3,
                },
                "conversion_weights": {
                    "interview_probability": 0.5,
                    "offer_probability": 0.5,
                },
                "diversity_bonus": 0.0,
            }

    @staticmethod
    def clear_weight_cache(tenant_id: Optional[str] = None):
        """Clear weight cache (useful after AB test completion)"""
        with DynamicWeightLoader._cache_lock:
            if tenant_id:
                keys_to_remove = [
                    k for k in DynamicWeightLoader._weight_cache.keys()
                    if k.startswith(tenant_id)
                ]
                for key in keys_to_remove:
                    del DynamicWeightLoader._weight_cache[key]
                logger.info(
                    f"[WeightLoader] Cleared {len(keys_to_remove)} cache entries"
                )
            else:
                DynamicWeightLoader._weight_cache.clear()
                logger.info("[WeightLoader] Cleared entire weight cache")

    @staticmethod
    def get_weight_version_info(
        db: Session, tenant_id: str, orchestrator: str
    ) -> Dict[str, Any]:
        """Get metadata about current weights"""
        population = (
            db.query(GeneticWeightPopulation)
            .filter(
                and_(
                    GeneticWeightPopulation.orchestrator == orchestrator,
                    GeneticWeightPopulation.tenant_id == tenant_id,
                )
            )
            .order_by(desc(GeneticWeightPopulation.generation_number))
            .first()
        )

        if not population:
            return {
                "status": "NO_POPULATION",
                "weights_source": "default",
                "generation": 0,
                "best_performer": None,
            }

        info = {
            "status": population.status,
            "generation": population.generation_number,
            "best_performer_id": population.best_performer_id,
            "average_fitness": population.average_fitness,
            "has_converged": population.has_converged,
            "weights_source": "genetic_algorithm",
        }

        if population.ab_test_id:
            ab_test = db.query(ABTestDeployment).filter(
                ABTestDeployment.test_id == population.ab_test_id
            ).first()

            if ab_test:
                info["ab_test"] = {
                    "test_id": ab_test.test_id,
                    "current_stage": ab_test.current_stage,
                    "baseline_accuracy": ab_test.baseline_accuracy,
                    "variant_accuracy": ab_test.variant_accuracy,
                    "rolled_back": ab_test.rolled_back,
                }

        return info
