"""Cascading Signal Broker - Routes learning signals between orchestrators

Implements:
1. Signal routing (Thunder → Flash → Interview → Offer → Finance)
2. Cascade failure detection (15-minute forward prediction)
3. Signal effectiveness tracking
4. Missed signal detection and escalation
5. Bidirectional formation health monitoring
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.cascading_signal_log import (
    CascadingSignalLog,
    CascadingSignalMetrics,
)
from app.models.agent_phalanx import AgentPhalanx

logger = logging.getLogger(__name__)


class CascadingSignalBroker:
    """Broker signals between orchestrators for cascading learning"""

    # Signal routing map
    SIGNAL_ROUTES = {
        "thunder": ["flash", "interview"],
        "flash": ["interview", "offer"],
        "interview": ["offer", "finance"],
        "offer": ["finance", "thunder"],
        "finance": ["thunder"],
    }

    @staticmethod
    def send_signal(
        db: Session,
        source_orchestrator: str,
        target_orchestrator: str,
        tenant_id: str,
        signal_type: str,
        metric_name: str,
        metric_previous_value: float,
        metric_current_value: float,
        metric_threshold: float,
        predicted_cascade_impact: str,
        cascade_impact_severity: str,
        cascade_impact_timeline_minutes: int,
        recommended_action: str,
    ) -> CascadingSignalLog:
        """Send signal from source to target orchestrator"""
        signal = CascadingSignalLog(
            signal_id=str(uuid.uuid4()),
            orchestrator=source_orchestrator,
            source_orchestrator=source_orchestrator,
            target_orchestrator=target_orchestrator,
            tenant_id=tenant_id,
            signal_type=signal_type,
            priority="HIGH" if cascade_impact_severity == "CRITICAL" else "MEDIUM",
            metric_name=metric_name,
            metric_previous_value=metric_previous_value,
            metric_current_value=metric_current_value,
            metric_threshold=metric_threshold,
            variance_percent=(
                (metric_current_value - metric_previous_value) / metric_previous_value * 100
                if metric_previous_value != 0
                else 0.0
            ),
            predicted_cascade_impact=predicted_cascade_impact,
            cascade_impact_severity=cascade_impact_severity,
            cascade_impact_timeline_minutes=cascade_impact_timeline_minutes,
            recommended_action=recommended_action,
            recommended_action_priority="IMMEDIATE"
            if cascade_impact_severity == "CRITICAL"
            else "URGENT",
            sent_at=datetime.utcnow(),
        )

        db.add(signal)
        db.commit()

        logger.info(
            f"[SignalBroker] Signal sent {source_orchestrator}→{target_orchestrator}: "
            f"{metric_name}={metric_current_value:.3f} ({signal.variance_percent:+.1f}%)"
        )

        return signal

    @staticmethod
    def acknowledge_signal(
        db: Session, signal_id: str, action_taken: str
    ) -> CascadingSignalLog:
        """Target acknowledges signal receipt"""
        signal = db.query(CascadingSignalLog).filter(
            CascadingSignalLog.signal_id == signal_id
        ).first()

        if not signal:
            logger.warning(f"[SignalBroker] Signal {signal_id} not found for acknowledgment")
            return None

        signal.received_at = datetime.utcnow()
        signal.acknowledged_at = datetime.utcnow()
        signal.action_taken = action_taken

        db.commit()

        logger.info(
            f"[SignalBroker] Signal {signal_id} acknowledged by {signal.target_orchestrator}"
        )

        return signal

    @staticmethod
    def record_action_effectiveness(
        db: Session,
        signal_id: str,
        effectiveness_score: float,
    ) -> CascadingSignalLog:
        """Record how effective the action was"""
        signal = db.query(CascadingSignalLog).filter(
            CascadingSignalLog.signal_id == signal_id
        ).first()

        if not signal:
            return None

        signal.action_effectiveness = effectiveness_score
        signal.resolved_at = datetime.utcnow()

        db.commit()

        return signal

    @staticmethod
    def detect_cascade_failure(
        db: Session,
        source_orchestrator: str,
        metric_name: str,
        metric_current_value: float,
        metric_threshold: float,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Predict cascade failure 15 minutes ahead.

        Analyze: If source metric degrades, what else breaks downstream?
        """
        if metric_current_value < metric_threshold:
            # Metric is in danger zone
            # Simulate 15-minute forward prediction
            worst_case_metric = metric_current_value * 0.8  # Assume 20% degradation

            cascade_prediction = {
                "source_orchestrator": source_orchestrator,
                "current_metric": metric_name,
                "current_value": metric_current_value,
                "predicted_worst_case_15min": worst_case_metric,
                "risk_level": "CRITICAL" if worst_case_metric < metric_threshold * 0.9 else "HIGH",
                "affected_downstream": CascadingSignalBroker.SIGNAL_ROUTES.get(
                    source_orchestrator, []
                ),
            }

            logger.warning(
                f"[SignalBroker] Cascade failure predicted for {source_orchestrator}: "
                f"{metric_name} may degrade from {metric_current_value:.3f} to "
                f"{worst_case_metric:.3f} in 15 minutes"
            )

            return cascade_prediction

        return None

    @staticmethod
    def check_missed_signals(
        db: Session, tenant_id: str
    ) -> List[CascadingSignalLog]:
        """Identify signals that were not acknowledged or acted upon"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)

        missed_signals = (
            db.query(CascadingSignalLog)
            .filter(
                and_(
                    CascadingSignalLog.tenant_id == tenant_id,
                    CascadingSignalLog.sent_at < cutoff_time,
                    CascadingSignalLog.acknowledged_at == None,
                )
            )
            .all()
        )

        for signal in missed_signals:
            signal.missed_response = True
            signal.missed_response_consequence = (
                f"Signal not acknowledged within {cutoff_time} window. "
                f"Cascade may have occurred."
            )

        if missed_signals:
            db.commit()
            logger.critical(
                f"[SignalBroker] {len(missed_signals)} signals missed - escalating"
            )

        return missed_signals

    @staticmethod
    def compute_signal_metrics(
        db: Session,
        source_orchestrator: str,
        target_orchestrator: str,
        tenant_id: str,
    ) -> CascadingSignalMetrics:
        """Compute signal health between two orchestrators"""
        signals = (
            db.query(CascadingSignalLog)
            .filter(
                and_(
                    CascadingSignalLog.source_orchestrator == source_orchestrator,
                    CascadingSignalLog.target_orchestrator == target_orchestrator,
                    CascadingSignalLog.tenant_id == tenant_id,
                )
            )
            .all()
        )

        if not signals:
            return None

        total_sent = len(signals)
        acknowledged_count = sum(1 for s in signals if s.acknowledged_at)
        action_taken_count = sum(1 for s in signals if s.action_taken)
        ignored_count = sum(1 for s in signals if s.missed_response)

        acknowledgment_rate = acknowledged_count / total_sent if total_sent > 0 else 0.0
        action_taken_rate = action_taken_count / total_sent if total_sent > 0 else 0.0
        ignore_rate = ignored_count / total_sent if total_sent > 0 else 0.0

        # Response times
        response_times = [
            (s.acknowledged_at - s.sent_at).total_seconds()
            for s in signals
            if s.acknowledged_at
        ]
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        median_response = (
            sorted(response_times)[len(response_times) // 2]
            if response_times
            else 0
        )
        p99_response = (
            sorted(response_times)[int(len(response_times) * 0.99)]
            if response_times
            else 0
        )

        # Compute signal quality score
        # High quality: fast response, high acknowledgment, high action rate
        signal_quality = (
            acknowledgment_rate * 0.4 +
            action_taken_rate * 0.4 +
            max(0, 1 - (avg_response / 60)) * 0.2  # 60s target
        )

        metrics = CascadingSignalMetrics(
            metrics_id=str(uuid.uuid4()),
            source_orchestrator=source_orchestrator,
            target_orchestrator=target_orchestrator,
            tenant_id=tenant_id,
            total_signals_sent=total_sent,
            signals_acknowledged_count=acknowledged_count,
            acknowledgment_rate=acknowledgment_rate,
            signals_action_taken_count=action_taken_count,
            action_taken_rate=action_taken_rate,
            signals_ignored_count=ignored_count,
            ignore_rate=ignore_rate,
            avg_signal_to_action_seconds=int(avg_response),
            median_signal_to_action_seconds=int(median_response),
            p99_signal_to_action_seconds=int(p99_response),
            signal_quality_score=signal_quality,
        )

        db.add(metrics)
        db.commit()

        logger.info(
            f"[SignalBroker] Signal metrics {source_orchestrator}→{target_orchestrator}: "
            f"ack_rate={acknowledgment_rate:.1%}, action_rate={action_taken_rate:.1%}, "
            f"quality={signal_quality:.2f}"
        )

        return metrics
