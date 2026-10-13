"""Learning Analytics Endpoints - Phase 4 Dashboard Data API

Provides data visualization for autonomous learning system:
1. Genetic populations (generation history, fitness distribution, elite chromosomes)
2. A/B tests (stage progression, Thompson allocation, formation health, accuracy comparison)
3. Behavioral rules (execution history, cascade effects)
4. Cascading signals (orchestrator pair metrics, signal activity, cascade failures)
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.models.user import Users
# from app.models.genetic_weight_population import GeneticWeightPopulation
# from app.models.ab_test_deployment import ABTestDeployment, ABTestDecision, ABTestStageMetrics
# from app.models.behavioral_adaptation_rules import BehavioralAdaptationRule, RuleExecution
# from app.models.cascading_signal_log import CascadingSignalLog, CascadingSignalMetrics

logger = logging.getLogger(__name__)

# Learning-system data is SLM administration: every route needs slm-dashboard view,
# and anything that starts a learning cycle needs slm-dashboard edit (route-level below).
router = APIRouter(prefix="/learning", tags=["learning_analytics"],
                   dependencies=[Depends(require_resource_permission("slm-dashboard", "view"))])


# ============================================================================
# GENETIC POPULATIONS ENDPOINTS
# ============================================================================

@router.get("/genetic-populations/{orchestrator}")
def get_genetic_populations(
    orchestrator: str,
    tenant_id: str = Query(..., description="Tenant ID"),
    limit: int = Query(10, description="Number of generations to return"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get genetic population history for orchestrator"""
    try:
        populations = (
            db.query(GeneticWeightPopulation)
            .filter(
                and_(
                    GeneticWeightPopulation.orchestrator == orchestrator,
                    GeneticWeightPopulation.tenant_id == tenant_id,
                )
            )
            .order_by(desc(GeneticWeightPopulation.generation_number))
            .limit(limit)
            .all()
        )

        if not populations:
            return {
                "orchestrator": orchestrator,
                "generations": [],
                "total_generations": 0,
                "latest_generation": None,
            }

        latest = populations[0]
        generations_data = []

        for pop in reversed(populations):
            # Get elite chromosomes for this generation
            elite = [c for c in pop.chromosomes if c.is_elite] if pop.chromosomes else []

            generations_data.append({
                "generation_number": pop.generation_number,
                "population_size": pop.population_size,
                "average_fitness": pop.average_fitness or 0.0,
                "fitness_improvement": pop.fitness_improvement or 0.0,
                "best_performer_id": pop.best_performer_id,
                "best_performer_fitness": None,
                "has_converged": pop.has_converged,
                "status": pop.status,
                "elite_count": len(elite),
                "created_at": pop.created_at.isoformat() if pop.created_at else None,
            })

            # Add best performer fitness if available
            if pop.best_performer_id:
                best = next(
                    (c for c in pop.chromosomes if c.chromosome_id == pop.best_performer_id),
                    None
                )
                if best:
                    generations_data[-1]["best_performer_fitness"] = best.fitness_score

        return {
            "orchestrator": orchestrator,
            "generations": generations_data,
            "total_generations": len(populations),
            "latest_generation": {
                "generation_number": latest.generation_number,
                "average_fitness": latest.average_fitness or 0.0,
                "status": latest.status,
                "has_converged": latest.has_converged,
            }
        }
    except Exception as e:
        logger.error(f"Error fetching genetic populations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/genetic-populations/{orchestrator}/latest")
def get_latest_population(
    orchestrator: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get latest genetic population with all chromosomes"""
    try:
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
            raise HTTPException(status_code=404, detail="No population found")

        chromosomes_data = []
        if population.chromosomes:
            for c in population.chromosomes:
                chromosomes_data.append({
                    "chromosome_id": c.chromosome_id,
                    "fitness_score": c.fitness_score,
                    "accuracy": c.accuracy,
                    "calibration": c.calibration,
                    "throughput": c.throughput,
                    "diversity_bonus": c.diversity_bonus,
                    "is_elite": c.is_elite,
                    "is_best_performer": c.is_best_performer,
                })

        return {
            "generation_number": population.generation_number,
            "orchestrator": orchestrator,
            "population_size": population.population_size,
            "average_fitness": population.average_fitness or 0.0,
            "fitness_improvement": population.fitness_improvement or 0.0,
            "has_converged": population.has_converged,
            "status": population.status,
            "chromosomes": sorted(chromosomes_data, key=lambda x: x["fitness_score"], reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest population: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# A/B TEST ENDPOINTS
# ============================================================================

@router.get("/ab-tests/{orchestrator}")
def get_ab_tests(
    orchestrator: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get A/B tests for orchestrator"""
    try:
        tests = (
            db.query(ABTestDeployment)
            .filter(
                and_(
                    ABTestDeployment.orchestrator == orchestrator,
                    ABTestDeployment.tenant_id == tenant_id,
                )
            )
            .order_by(desc(ABTestDeployment.created_at))
            .all()
        )

        tests_data = []
        for test in tests:
            # Get stage metrics
            stage_metrics = (
                db.query(ABTestStageMetrics)
                .filter(ABTestStageMetrics.test_id == test.test_id)
                .order_by(ABTestStageMetrics.stage)
                .all()
            )

            metrics_by_stage = {}
            for metric in stage_metrics:
                metrics_by_stage[metric.stage] = {
                    "baseline_accuracy": metric.baseline_accuracy,
                    "variant_accuracy": metric.variant_accuracy,
                    "accuracy_improvement": metric.accuracy_improvement,
                    "p_value": metric.p_value,
                    "confidence_interval": [metric.confidence_interval_lower, metric.confidence_interval_upper],
                    "baseline_count": metric.baseline_count,
                    "variant_count": metric.variant_count,
                }

            tests_data.append({
                "test_id": test.test_id,
                "current_stage": test.current_stage,
                "baseline_accuracy": test.baseline_accuracy,
                "variant_accuracy": test.variant_accuracy,
                "variant_formation_health": test.variant_formation_health or 0.0,
                "rolled_back": test.rolled_back,
                "rollback_reason": test.rollback_reason,
                "experiment_allocation": test.experiment_allocation,
                "expand_allocation": test.expand_allocation,
                "stage_metrics": metrics_by_stage,
                "created_at": test.created_at.isoformat() if test.created_at else None,
            })

        return {
            "orchestrator": orchestrator,
            "tests": tests_data,
            "total_tests": len(tests),
        }
    except Exception as e:
        logger.error(f"Error fetching A/B tests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ab-tests/{orchestrator}/active")
def get_active_ab_test(
    orchestrator: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get currently active A/B test"""
    try:
        test = (
            db.query(ABTestDeployment)
            .filter(
                and_(
                    ABTestDeployment.orchestrator == orchestrator,
                    ABTestDeployment.tenant_id == tenant_id,
                    ABTestDeployment.current_stage != "ROLLED_BACK",
                    ABTestDeployment.current_stage != "COMPLETED",
                )
            )
            .order_by(desc(ABTestDeployment.created_at))
            .first()
        )

        if not test:
            return {"orchestrator": orchestrator, "active_test": None}

        # Get Thompson allocation
        allocation = {
            "baseline_allocation": 0.5,
            "variant_allocation": 0.5,
        }

        # Count decisions by variant
        baseline_decisions = db.query(ABTestDecision).filter(
            and_(
                ABTestDecision.test_id == test.test_id,
                ABTestDecision.variant == "baseline",
            )
        ).count()

        variant_decisions = db.query(ABTestDecision).filter(
            and_(
                ABTestDecision.test_id == test.test_id,
                ABTestDecision.variant == "variant",
            )
        ).count()

        total = baseline_decisions + variant_decisions

        return {
            "orchestrator": orchestrator,
            "active_test": {
                "test_id": test.test_id,
                "current_stage": test.current_stage,
                "baseline_accuracy": test.baseline_accuracy,
                "variant_accuracy": test.variant_accuracy,
                "variant_formation_health": test.variant_formation_health or 0.0,
                "allocation": allocation,
                "decisions": {
                    "baseline": baseline_decisions,
                    "variant": variant_decisions,
                    "total": total,
                },
                "created_at": test.created_at.isoformat() if test.created_at else None,
            }
        }
    except Exception as e:
        logger.error(f"Error fetching active A/B test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BEHAVIORAL RULES ENDPOINTS
# ============================================================================

@router.get("/behavioral-rules/{orchestrator}")
def get_behavioral_rules(
    orchestrator: str,
    tenant_id: str = Query(...),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get behavioral adaptation rules for orchestrator"""
    try:
        query = db.query(BehavioralAdaptationRule).filter(
            and_(
                BehavioralAdaptationRule.orchestrator == orchestrator,
                BehavioralAdaptationRule.tenant_id == tenant_id,
            )
        )

        if is_active is not None:
            query = query.filter(BehavioralAdaptationRule.is_active == is_active)

        rules = query.order_by(desc(BehavioralAdaptationRule.created_at)).all()

        rules_data = []
        for rule in rules:
            # Get recent executions
            executions = (
                db.query(RuleExecution)
                .filter(RuleExecution.rule_id == rule.rule_id)
                .order_by(desc(RuleExecution.triggered_at))
                .limit(5)
                .all()
            )

            rules_data.append({
                "rule_id": rule.rule_id,
                "rule_name": rule.rule_name,
                "rule_description": rule.rule_description,
                "rule_category": rule.rule_category,
                "trigger_metric": rule.trigger_metric,
                "trigger_operator": rule.trigger_operator,
                "trigger_threshold": rule.trigger_threshold,
                "action_type": rule.action_type,
                "is_active": rule.is_active,
                "triggered_count": rule.triggered_count or 0,
                "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
                "recent_executions": [
                    {
                        "execution_id": e.execution_id,
                        "status": e.execution_status,
                        "triggered_at": e.triggered_at.isoformat() if e.triggered_at else None,
                    }
                    for e in executions
                ],
            })

        return {
            "orchestrator": orchestrator,
            "rules": rules_data,
            "total_rules": len(rules),
        }
    except Exception as e:
        logger.error(f"Error fetching behavioral rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CASCADING SIGNALS ENDPOINTS
# ============================================================================

@router.get("/cascading-signals/metrics")
def get_cascading_signal_metrics(
    source_orchestrator: str = Query(...),
    target_orchestrator: str = Query(...),
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get signal quality metrics between two orchestrators"""
    try:
        metrics = (
            db.query(CascadingSignalMetrics)
            .filter(
                and_(
                    CascadingSignalMetrics.source_orchestrator == source_orchestrator,
                    CascadingSignalMetrics.target_orchestrator == target_orchestrator,
                    CascadingSignalMetrics.tenant_id == tenant_id,
                )
            )
            .order_by(desc(CascadingSignalMetrics.created_at))
            .first()
        )

        if not metrics:
            return {
                "source_orchestrator": source_orchestrator,
                "target_orchestrator": target_orchestrator,
                "metrics": None,
            }

        return {
            "source_orchestrator": source_orchestrator,
            "target_orchestrator": target_orchestrator,
            "metrics": {
                "total_signals_sent": metrics.total_signals_sent,
                "signals_acknowledged_count": metrics.signals_acknowledged_count,
                "acknowledgment_rate": metrics.acknowledgment_rate,
                "signals_action_taken_count": metrics.signals_action_taken_count,
                "action_taken_rate": metrics.action_taken_rate,
                "signals_ignored_count": metrics.signals_ignored_count,
                "ignore_rate": metrics.ignore_rate,
                "avg_signal_to_action_seconds": metrics.avg_signal_to_action_seconds,
                "median_signal_to_action_seconds": metrics.median_signal_to_action_seconds,
                "p99_signal_to_action_seconds": metrics.p99_signal_to_action_seconds,
                "signal_quality_score": metrics.signal_quality_score,
            }
        }
    except Exception as e:
        logger.error(f"Error fetching cascading signal metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascading-signals/recent")
def get_recent_signals(
    tenant_id: str = Query(...),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get recent cascading signals"""
    try:
        signals = (
            db.query(CascadingSignalLog)
            .filter(CascadingSignalLog.tenant_id == tenant_id)
            .order_by(desc(CascadingSignalLog.sent_at))
            .limit(limit)
            .all()
        )

        signals_data = []
        for signal in signals:
            signals_data.append({
                "signal_id": signal.signal_id,
                "source_orchestrator": signal.source_orchestrator,
                "target_orchestrator": signal.target_orchestrator,
                "signal_type": signal.signal_type,
                "metric_name": signal.metric_name,
                "metric_current_value": signal.metric_current_value,
                "cascade_impact_severity": signal.cascade_impact_severity,
                "cascade_impact_timeline_minutes": signal.cascade_impact_timeline_minutes,
                "acknowledged_at": signal.acknowledged_at.isoformat() if signal.acknowledged_at else None,
                "sent_at": signal.sent_at.isoformat() if signal.sent_at else None,
            })

        return {
            "signals": signals_data,
            "total_signals": len(signals),
        }
    except Exception as e:
        logger.error(f"Error fetching recent signals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
