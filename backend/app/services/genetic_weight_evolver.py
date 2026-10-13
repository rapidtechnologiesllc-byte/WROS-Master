"""Genetic Weight Evolver - Evolves decision weights through genetic algorithm

Implements:
1. Fitness evaluation (accuracy, calibration, throughput)
2. Elite selection (keep top 20%)
3. Mutation (15% rate) + crossover
4. Convergence detection
5. AB test triggering when fitness improves > 5%

Integrates with LearningWeightOptimizer to use measured outcomes.
Works with queue processor to trigger evolution after every 50 decisions.
"""

import json
import logging
import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.models.genetic_weight_population import (
    GeneticWeightPopulation,
    GeneticWeightChromosome,
    WeightDeploymentHistory,
)
from app.models.ab_test_deployment import ABTestDeployment
from app.services.learning_weight_optimizer import LearningWeightOptimizer

logger = logging.getLogger(__name__)


class GeneticWeightEvolver:
    """Evolve decision weights using genetic algorithm"""

    # Genetic algorithm parameters
    POPULATION_SIZE = 30
    ELITE_RATE = 0.20  # Top 20% (6 chromosomes)
    MUTATION_RATE = 0.15  # 15% of genes mutate
    GENERATIONS_WITHOUT_IMPROVEMENT_THRESHOLD = 5
    FITNESS_IMPROVEMENT_THRESHOLD_FOR_AB_TEST = 0.05  # 5% improvement triggers AB test

    @staticmethod
    def initialize_population(
        db: Session,
        tenant_id: str,
        orchestrator: str,
        generation_number: int = 1,
    ) -> GeneticWeightPopulation:
        """Create initial population with default weights"""
        logger.info(
            f"[GeneticEvolver] Initializing population G{generation_number} for {orchestrator}"
        )

        population = GeneticWeightPopulation(
            population_id=str(uuid.uuid4()),
            generation_number=generation_number,
            orchestrator=orchestrator,
            tenant_id=tenant_id,
            population_size=GeneticWeightEvolver.POPULATION_SIZE,
            mutation_rate=GeneticWeightEvolver.MUTATION_RATE,
            elite_rate=GeneticWeightEvolver.ELITE_RATE,
            status="GENERATED",
        )

        # Create initial chromosomes with default weights
        for i in range(GeneticWeightEvolver.POPULATION_SIZE):
            chromosome = GeneticWeightEvolver._create_default_chromosome(
                population.population_id, orchestrator
            )
            population.chromosomes.append(chromosome)

        db.add(population)
        db.commit()

        logger.info(f"[GeneticEvolver] Created population {population.population_id} with {GeneticWeightEvolver.POPULATION_SIZE} chromosomes")
        return population

    @staticmethod
    def _create_default_chromosome(
        population_id: str, orchestrator: str
    ) -> GeneticWeightChromosome:
        """Create chromosome with default (baseline) weights"""
        if orchestrator == "thunder":
            weight_schema = {
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
            weight_schema = {
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

        return GeneticWeightChromosome(
            chromosome_id=str(uuid.uuid4()),
            population_id=population_id,
            weight_schema=weight_schema,
            fitness_score=0.0,
            accuracy=0.5,
            calibration=0.5,
            throughput=0.0,
            diversity_bonus=0.0,
            is_elite=False,
            selected_for_crossover=False,
            is_best_performer=False,
        )

    @staticmethod
    def evaluate_generation(
        db: Session,
        tenant_id: str,
        population_id: str,
    ) -> Dict[str, Any]:
        """Evaluate fitness of all chromosomes in population using measured outcomes"""
        logger.info(f"[GeneticEvolver] Evaluating generation {population_id}")

        population = db.query(GeneticWeightPopulation).filter(
            GeneticWeightPopulation.population_id == population_id
        ).first()

        if not population:
            raise ValueError(f"Population {population_id} not found")

        fitness_scores = {}
        total_fitness = 0.0

        # Get outcomes from LearningWeightOptimizer (represents measured decision quality)
        analysis = LearningWeightOptimizer.analyze_decision_batch(
            db, tenant_id, population.orchestrator
        )

        accuracy = analysis.get("accuracy", 0.5)
        gap = analysis.get("confidence_gap", 0.0)
        decisions_analyzed = analysis.get("decisions_analyzed", 0)

        # Evaluate each chromosome's fitness
        for chromosome in population.chromosomes:
            # Fitness = (accuracy * 0.5) + (1 - gap * 0.3) + (diversity_bonus * 0.2)
            # Higher accuracy = higher fitness
            # Lower gap (better calibration) = higher fitness
            # Diversity bonus encourages population variation
            fitness = (
                accuracy * 0.5 +
                max(0, 1 - gap * 3) * 0.3 +
                chromosome.diversity_bonus * 0.2
            )

            chromosome.fitness_score = fitness
            chromosome.accuracy = accuracy
            chromosome.calibration = 1 - gap
            fitness_scores[chromosome.chromosome_id] = fitness
            total_fitness += fitness

        # Calculate average fitness
        avg_fitness = total_fitness / len(population.chromosomes) if population.chromosomes else 0.0

        # Find best performer
        best_chromosome_id = max(
            fitness_scores, key=fitness_scores.get
        ) if fitness_scores else None
        best_chromosome = next(
            (c for c in population.chromosomes if c.chromosome_id == best_chromosome_id),
            None,
        )

        if best_chromosome:
            best_chromosome.is_best_performer = True

        # Update population metrics
        previous_avg_fitness = population.average_fitness or 0.0
        fitness_improvement = avg_fitness - previous_avg_fitness

        population.generation_fitness_scores = json.dumps(fitness_scores)
        population.average_fitness = avg_fitness
        population.fitness_improvement = fitness_improvement
        population.best_performer_id = best_chromosome_id

        db.commit()

        logger.info(
            f"[GeneticEvolver] Generation fitness: avg={avg_fitness:.4f}, "
            f"improvement={fitness_improvement:.4f}, best={best_chromosome_id[:8]}..."
        )

        return {
            "population_id": population_id,
            "fitness_scores": fitness_scores,
            "average_fitness": avg_fitness,
            "fitness_improvement": fitness_improvement,
            "best_performer_id": best_chromosome_id,
            "decisions_analyzed": decisions_analyzed,
        }

    @staticmethod
    def select_elite(
        db: Session, population_id: str
    ) -> List[GeneticWeightChromosome]:
        """Select top (elite_rate)% chromosomes for breeding"""
        population = db.query(GeneticWeightPopulation).filter(
            GeneticWeightPopulation.population_id == population_id
        ).first()

        if not population:
            raise ValueError(f"Population {population_id} not found")

        elite_count = max(1, int(GeneticWeightEvolver.ELITE_RATE * len(population.chromosomes)))

        # Sort by fitness and select top
        elite = sorted(population.chromosomes, key=lambda c: c.fitness_score, reverse=True)[
            :elite_count
        ]

        for chromosome in elite:
            chromosome.is_elite = True

        db.commit()

        logger.info(f"[GeneticEvolver] Selected {len(elite)} elite chromosomes")
        return elite

    @staticmethod
    def create_next_generation(
        db: Session,
        tenant_id: str,
        current_population_id: str,
    ) -> GeneticWeightPopulation:
        """Create next generation through crossover and mutation"""
        logger.info(f"[GeneticEvolver] Creating next generation from {current_population_id}")

        current_population = db.query(GeneticWeightPopulation).filter(
            GeneticWeightPopulation.population_id == current_population_id
        ).first()

        if not current_population:
            raise ValueError(f"Population {current_population_id} not found")

        # Select elite
        elite = GeneticWeightEvolver.select_elite(db, current_population_id)

        # Create new population
        new_generation = current_population.generation_number + 1
        new_population = GeneticWeightPopulation(
            population_id=str(uuid.uuid4()),
            generation_number=new_generation,
            orchestrator=current_population.orchestrator,
            tenant_id=tenant_id,
            population_size=GeneticWeightEvolver.POPULATION_SIZE,
            mutation_rate=GeneticWeightEvolver.MUTATION_RATE,
            elite_rate=GeneticWeightEvolver.ELITE_RATE,
            status="GENERATED",
        )

        # Keep elite (elitism)
        for elite_chromosome in elite:
            new_chromosome = GeneticWeightEvolver._clone_chromosome(
                elite_chromosome, new_population.population_id
            )
            new_chromosome.parent_1_id = elite_chromosome.chromosome_id
            new_population.chromosomes.append(new_chromosome)

        # Fill rest with crossover + mutation
        while len(new_population.chromosomes) < GeneticWeightEvolver.POPULATION_SIZE:
            # Select two random parents from elite
            parent1 = random.choice(elite)
            parent2 = random.choice(elite)

            # Crossover
            child_weights = GeneticWeightEvolver._crossover(
                parent1.weight_schema, parent2.weight_schema
            )

            # Mutation
            if random.random() < GeneticWeightEvolver.MUTATION_RATE:
                child_weights = GeneticWeightEvolver._mutate(child_weights)

            # Create new chromosome
            child_chromosome = GeneticWeightChromosome(
                chromosome_id=str(uuid.uuid4()),
                population_id=new_population.population_id,
                weight_schema=child_weights,
                fitness_score=0.0,
                parent_1_id=parent1.chromosome_id,
                parent_2_id=parent2.chromosome_id,
                mutation_applied=random.random() < GeneticWeightEvolver.MUTATION_RATE,
            )

            new_population.chromosomes.append(child_chromosome)

        db.add(new_population)
        db.commit()

        logger.info(
            f"[GeneticEvolver] Created generation G{new_generation} with "
            f"{len(elite)} elite + {len(new_population.chromosomes) - len(elite)} offspring"
        )

        return new_population

    @staticmethod
    def _clone_chromosome(
        source: GeneticWeightChromosome, new_population_id: str
    ) -> GeneticWeightChromosome:
        """Create a copy of chromosome for next generation"""
        return GeneticWeightChromosome(
            chromosome_id=str(uuid.uuid4()),
            population_id=new_population_id,
            weight_schema=json.loads(json.dumps(source.weight_schema)),
            fitness_score=0.0,
            accuracy=source.accuracy,
            calibration=source.calibration,
            diversity_bonus=source.diversity_bonus,
        )

    @staticmethod
    def _crossover(weights1: Dict, weights2: Dict) -> Dict:
        """Uniform crossover - randomly mix parent weights"""
        child_weights = {}

        # For each key in weights, randomly pick from parent1 or parent2
        all_keys = set(weights1.keys()) | set(weights2.keys())

        for key in all_keys:
            if key in weights1 and key in weights2:
                if random.random() < 0.5:
                    child_weights[key] = json.loads(json.dumps(weights1[key]))
                else:
                    child_weights[key] = json.loads(json.dumps(weights2[key]))
            elif key in weights1:
                child_weights[key] = json.loads(json.dumps(weights1[key]))
            else:
                child_weights[key] = json.loads(json.dumps(weights2[key]))

        return child_weights

    @staticmethod
    def _mutate(weights: Dict) -> Dict:
        """Mutation - randomly adjust weight values by ±10%"""
        mutated = json.loads(json.dumps(weights))

        def mutate_value(val):
            if isinstance(val, (int, float)):
                # Adjust by ±10%
                adjustment = random.uniform(-0.1, 0.1)
                new_val = val * (1 + adjustment)
                # Clamp to [0, 1]
                return max(0.0, min(1.0, new_val))
            return val

        def mutate_dict(d):
            for key, val in d.items():
                if isinstance(val, dict):
                    mutate_dict(val)
                else:
                    d[key] = mutate_value(val)

        mutate_dict(mutated)
        return mutated

    @staticmethod
    def detect_convergence(
        db: Session, population_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if population has converged (no improvement for N generations)"""
        population = db.query(GeneticWeightPopulation).filter(
            GeneticWeightPopulation.population_id == population_id
        ).first()

        if not population:
            return False, None

        # Get last N generations for this orchestrator
        recent_generations = (
            db.query(GeneticWeightPopulation)
            .filter(
                and_(
                    GeneticWeightPopulation.orchestrator == population.orchestrator,
                    GeneticWeightPopulation.tenant_id == population.tenant_id,
                )
            )
            .order_by(desc(GeneticWeightPopulation.generation_number))
            .limit(GeneticWeightEvolver.GENERATIONS_WITHOUT_IMPROVEMENT_THRESHOLD + 1)
            .all()
        )

        # Check if fitness improvement is minimal across last N generations
        if len(recent_generations) >= GeneticWeightEvolver.GENERATIONS_WITHOUT_IMPROVEMENT_THRESHOLD:
            improvements = [
                g.fitness_improvement or 0.0 for g in recent_generations
            ]
            avg_improvement = sum(improvements) / len(improvements)

            if avg_improvement < 0.001:  # Less than 0.1% improvement
                logger.info(
                    f"[GeneticEvolver] Population {population_id} has converged "
                    f"(avg improvement: {avg_improvement:.6f})"
                )
                population.has_converged = True
                db.commit()
                return True, f"Average improvement {avg_improvement:.6f} below threshold"

        return False, None

    @staticmethod
    def trigger_ab_test_if_needed(
        db: Session,
        tenant_id: str,
        current_population_id: str,
    ) -> Optional[ABTestDeployment]:
        """Create AB test if fitness improvement > threshold"""
        current_population = db.query(GeneticWeightPopulation).filter(
            GeneticWeightPopulation.population_id == current_population_id
        ).first()

        if not current_population:
            return None

        fitness_improvement = current_population.fitness_improvement or 0.0

        if (
            fitness_improvement > GeneticWeightEvolver.FITNESS_IMPROVEMENT_THRESHOLD_FOR_AB_TEST
            and not current_population.ab_test_id
        ):
            logger.info(
                f"[GeneticEvolver] Fitness improvement {fitness_improvement:.2%} "
                f"exceeds {GeneticWeightEvolver.FITNESS_IMPROVEMENT_THRESHOLD_FOR_AB_TEST:.2%} "
                f"→ Triggering AB test"
            )

            # Get previous generation as baseline
            previous_population = (
                db.query(GeneticWeightPopulation)
                .filter(
                    and_(
                        GeneticWeightPopulation.orchestrator == current_population.orchestrator,
                        GeneticWeightPopulation.tenant_id == tenant_id,
                        GeneticWeightPopulation.generation_number
                        == current_population.generation_number - 1,
                    )
                )
                .first()
            )

            baseline_chromosome_id = (
                previous_population.best_performer_id if previous_population else None
            )
            variant_chromosome_id = current_population.best_performer_id

            if baseline_chromosome_id and variant_chromosome_id:
                ab_test = ABTestDeployment(
                    test_id=str(uuid.uuid4()),
                    population_id=current_population.population_id,
                    orchestrator=current_population.orchestrator,
                    tenant_id=tenant_id,
                    baseline_chromosome_id=baseline_chromosome_id,
                    variant_chromosome_id=variant_chromosome_id,
                    current_stage="EXPERIMENT",
                    stage_target_decisions=100,
                    stage_required_improvement=0.02,
                    experiment_allocation=0.05,
                    expand_allocation=0.25,
                )

                db.add(ab_test)
                current_population.ab_test_id = ab_test.test_id
                current_population.status = "STAGED_FOR_AB_TEST"
                db.commit()

                logger.info(f"[GeneticEvolver] Created AB test {ab_test.test_id}")
                return ab_test

        return None
