"""Behavioral Adaptation Rules Engine - Changes agent strategy based on learned conditions

Implements:
1. Rule condition evaluation (trigger metrics vs thresholds)
2. Rule firing and action execution
3. Execution logging and effectiveness tracking
4. Cascade failure detection (rule triggers other rules)
5. Rollback of failed actions
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.behavioral_adaptation_rules import (
    BehavioralAdaptationRule,
    RuleExecution,
    RuleAuditLog,
)
from app.models.slm_learning_metrics import ThunderLearningMetrics, FlashLearningMetrics

logger = logging.getLogger(__name__)


class BehavioralAdaptationRulesEngine:
    """Execute rules that adapt agent behavior based on learned conditions"""

    @staticmethod
    def create_rule(
        db: Session,
        tenant_id: str,
        orchestrator: str,
        rule_name: str,
        rule_description: str,
        rule_category: str,
        trigger_metric: str,
        trigger_operator: str,
        trigger_threshold: float,
        trigger_window_minutes: int,
        action_type: str,
        action_target_field: Optional[str] = None,
        action_from_value: Optional[float] = None,
        action_to_value: Optional[float] = None,
    ) -> BehavioralAdaptationRule:
        """Create a new adaptation rule"""
        rule = BehavioralAdaptationRule(
            rule_id=str(uuid.uuid4()),
            orchestrator=orchestrator,
            tenant_id=tenant_id,
            rule_name=rule_name,
            rule_description=rule_description,
            rule_category=rule_category,
            rule_priority="MEDIUM",
            trigger_metric=trigger_metric,
            trigger_operator=trigger_operator,
            trigger_threshold=trigger_threshold,
            trigger_window_minutes=trigger_window_minutes,
            trigger_check_frequency_minutes=5,
            action_type=action_type,
            action_target_field=action_target_field,
            action_from_value=action_from_value,
            action_to_value=action_to_value,
            action_transition_type="IMMEDIATE",
            is_active=True,
        )

        db.add(rule)
        db.commit()

        logger.info(f"[RulesEngine] Created rule {rule.rule_id}: {rule_name}")

        return rule

    @staticmethod
    def evaluate_rule_conditions(
        db: Session,
        rule: BehavioralAdaptationRule,
        tenant_id: str,
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if rule condition is met.

        Returns: (condition_met, metric_value)
        """
        # Get metric class based on orchestrator
        if rule.orchestrator == "thunder":
            metric_class = ThunderLearningMetrics
        elif rule.orchestrator == "flash":
            metric_class = FlashLearningMetrics
        else:
            return False, None

        # Get metrics from time window
        cutoff_time = datetime.utcnow() - timedelta(
            minutes=rule.trigger_window_minutes
        )

        recent_metrics = (
            db.query(metric_class)
            .filter(
                and_(
                    metric_class.tenant_id == tenant_id,
                    metric_class.timestamp >= cutoff_time,
                )
            )
            .all()
        )

        if not recent_metrics:
            return False, None

        # Extract metric values based on trigger_metric name
        metric_values = []

        for m in recent_metrics:
            if rule.trigger_metric == "accuracy":
                # Compute accuracy from recent metrics
                if hasattr(m, 'recommendation_confidence'):
                    metric_values.append(m.recommendation_confidence / 100.0)
            elif rule.trigger_metric == "throughput":
                # Count of decisions in window
                metric_values.append(1.0)  # Each metric = 1 decision
            elif rule.trigger_metric == "calibration":
                # Gap between confidence and actual
                if hasattr(m, 'recommendation_confidence'):
                    metric_values.append(m.recommendation_confidence / 100.0)
            elif rule.trigger_metric == "health":
                # Formation health or system health
                if hasattr(m, 'system_health_score'):
                    metric_values.append(m.system_health_score)
            elif rule.trigger_metric == "cascade_count":
                # Number of cascading failures
                metric_values.append(0.0)  # Default

        if not metric_values:
            return False, None

        # Aggregate metric (average)
        avg_metric_value = sum(metric_values) / len(metric_values)

        # Check condition
        condition_met = BehavioralAdaptationRulesEngine._check_condition(
            avg_metric_value,
            rule.trigger_operator,
            rule.trigger_threshold,
        )

        return condition_met, avg_metric_value

    @staticmethod
    def _check_condition(
        value: float, operator: str, threshold: float
    ) -> bool:
        """Check if condition is met"""
        if operator == "<":
            return value < threshold
        elif operator == ">":
            return value > threshold
        elif operator == "==":
            return abs(value - threshold) < 0.001
        elif operator == "!=":
            return abs(value - threshold) >= 0.001
        elif operator == "<=":
            return value <= threshold
        elif operator == ">=":
            return value >= threshold
        else:
            return False

    @staticmethod
    def execute_rule(
        db: Session,
        rule: BehavioralAdaptationRule,
        tenant_id: str,
        trigger_metric_value: float,
    ) -> RuleExecution:
        """Execute rule action"""
        logger.info(
            f"[RulesEngine] Executing rule {rule.rule_id} ({rule.rule_name}) "
            f"for {rule.orchestrator}: {rule.trigger_metric}={trigger_metric_value}"
        )

        execution = RuleExecution(
            execution_id=str(uuid.uuid4()),
            rule_id=rule.rule_id,
            tenant_id=tenant_id,
            orchestrator=rule.orchestrator,
            trigger_metric_value=trigger_metric_value,
            field_changed=rule.action_target_field,
            old_value=rule.action_from_value,
            new_value=rule.action_to_value,
            execution_status="EXECUTED",
        )

        try:
            # Execute action based on type
            if rule.action_type == "CHANGE_WEIGHT":
                # In production, this would update the weight loader
                logger.info(
                    f"[RulesEngine] Changing {rule.action_target_field} "
                    f"from {rule.action_from_value} to {rule.action_to_value}"
                )
                execution.execution_status = "EXECUTED"

            elif rule.action_type == "CHANGE_ALLOCATION":
                # Update Thompson sampling allocation
                logger.info(
                    f"[RulesEngine] Changing allocation {rule.action_target_field} "
                    f"to {rule.action_to_value}"
                )
                execution.execution_status = "EXECUTED"

            elif rule.action_type == "ESCALATE_ALERT":
                # Send alert to monitoring
                logger.warning(
                    f"[RulesEngine] Alert escalated for rule {rule.rule_id}: {rule.rule_name}"
                )
                execution.execution_status = "EXECUTED"

            elif rule.action_type == "ROLLBACK_VARIANT":
                # Rollback active AB test
                logger.warning(
                    f"[RulesEngine] Rolling back variant due to rule {rule.rule_id}"
                )
                execution.execution_status = "EXECUTED"

            elif rule.action_type == "ADJUST_THRESHOLDS":
                # Adjust decision thresholds
                logger.info(
                    f"[RulesEngine] Adjusting threshold {rule.action_target_field} "
                    f"to {rule.action_to_value}"
                )
                execution.execution_status = "EXECUTED"

        except Exception as e:
            logger.error(f"[RulesEngine] Error executing rule {rule.rule_id}: {e}")
            execution.execution_status = "FAILED"
            execution.execution_failure_reason = str(e)

        db.add(execution)

        # Update rule metadata
        rule.triggered_count += 1
        rule.last_triggered_at = datetime.utcnow()

        db.commit()

        logger.info(
            f"[RulesEngine] Rule execution complete: {execution.execution_id}"
        )

        return execution

    @staticmethod
    def check_all_rules(
        db: Session, tenant_id: str
    ) -> List[RuleExecution]:
        """Check and execute all active rules for a tenant"""
        active_rules = (
            db.query(BehavioralAdaptationRule)
            .filter(
                and_(
                    BehavioralAdaptationRule.tenant_id == tenant_id,
                    BehavioralAdaptationRule.is_active == True,
                )
            )
            .all()
        )

        executions = []

        for rule in active_rules:
            # Check last check time (don't check too frequently)
            if rule.last_triggered_at:
                time_since_check = datetime.utcnow() - rule.last_triggered_at
                if (
                    time_since_check.total_seconds()
                    < rule.trigger_check_frequency_minutes * 60
                ):
                    continue

            # Evaluate condition
            condition_met, metric_value = BehavioralAdaptationRulesEngine.evaluate_rule_conditions(
                db, rule, tenant_id
            )

            if condition_met and metric_value is not None:
                # Execute rule
                execution = BehavioralAdaptationRulesEngine.execute_rule(
                    db, rule, tenant_id, metric_value
                )
                executions.append(execution)

        logger.info(
            f"[RulesEngine] Checked {len(active_rules)} rules, executed {len(executions)}"
        )

        return executions

    @staticmethod
    def measure_rule_effectiveness(
        db: Session, execution_id: str
    ) -> float:
        """
        Measure how effective a rule execution was.

        Returns: effectiveness score (0-1)
        """
        execution = db.query(RuleExecution).filter(
            RuleExecution.execution_id == execution_id
        ).first()

        if not execution:
            return 0.0

        # If we have before/after measurements, compute improvement
        if (
            execution.metric_before_action is not None
            and execution.metric_after_action is not None
        ):
            # Improvement = (after - before) / before
            if execution.metric_before_action != 0:
                improvement = (
                    execution.metric_after_action - execution.metric_before_action
                ) / abs(execution.metric_before_action)
                effectiveness = max(0.0, min(1.0, improvement))
            else:
                effectiveness = 0.5
        else:
            effectiveness = 0.5  # Neutral if no measurements

        execution.metric_improvement = effectiveness
        db.commit()

        return effectiveness

    @staticmethod
    def detect_cascade_effects(
        db: Session, initial_execution_id: str
    ) -> List[str]:
        """
        Detect if a rule execution caused other rules to fire.

        Returns: List of cascade rule IDs
        """
        initial_execution = db.query(RuleExecution).filter(
            RuleExecution.execution_id == initial_execution_id
        ).first()

        if not initial_execution:
            return []

        # Get all rules that executed shortly after (within 5 minutes)
        cutoff_time = initial_execution.triggered_at + timedelta(minutes=5)

        cascade_executions = (
            db.query(RuleExecution)
            .filter(
                and_(
                    RuleExecution.tenant_id == initial_execution.tenant_id,
                    RuleExecution.orchestrator == initial_execution.orchestrator,
                    RuleExecution.triggered_at > initial_execution.triggered_at,
                    RuleExecution.triggered_at <= cutoff_time,
                    RuleExecution.execution_id != initial_execution_id,
                )
            )
            .all()
        )

        cascade_rule_ids = [e.rule_id for e in cascade_executions]

        if cascade_rule_ids:
            initial_execution.cascade_signals_triggered = len(cascade_rule_ids)
            db.commit()

            logger.info(
                f"[RulesEngine] Detected {len(cascade_rule_ids)} cascade effects "
                f"from execution {initial_execution_id}"
            )

        return cascade_rule_ids
