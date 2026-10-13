"""Learning Outcome Tracker - Measures actual results vs predicted outcomes

Every decision made by Thunder/Flash/Interview/Offer has:
1. PREDICTED outcome (when decision made): "This candidate 70% likely to engage"
2. ACTUAL outcome (later): "Candidate opened email 2 hours later" → SUCCESS
3. LEARNING: Confidence gap = actual vs predicted → update weights

This enables:
- Decision quality measurement (was the prediction correct?)
- Confidence calibration (are we too confident or under-confident?)
- Continuous improvement (adjust decision weights based on accuracy)
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.slm_learning_metrics import (
    ThunderLearningMetrics,
    FlashLearningMetrics,
    LearningWeightUpdate,
)

logger = logging.getLogger(__name__)


class DecisionOutcome:
    """Track a single predicted → actual outcome pair"""

    def __init__(
        self,
        decision_id: str,
        decision_type: str,  # "thunder_outreach", "flash_job_match", "interview_prediction", "offer_acceptance"
        orchestrator: str,  # "thunder", "flash", "interview", "offer", "finance"
        entity_id: str,  # candidate_id, job_id, interview_id, offer_id
        predicted_outcome: str,  # "engagement", "interview_scheduled", "offer_accepted", "profit_positive"
        predicted_probability: float,  # 0.0-1.0
        predicted_at: datetime,
        decision_metadata: Dict[str, Any],  # What factors drove decision?
    ):
        self.decision_id = decision_id
        self.decision_type = decision_type
        self.orchestrator = orchestrator
        self.entity_id = entity_id
        self.predicted_outcome = predicted_outcome
        self.predicted_probability = predicted_probability
        self.predicted_at = predicted_at
        self.decision_metadata = decision_metadata

        # Outcome fields (filled later)
        self.actual_outcome: Optional[str] = None
        self.actual_result: Optional[bool] = None  # True if prediction was correct
        self.outcome_recorded_at: Optional[datetime] = None
        self.outcome_metadata: Dict[str, Any] = {}

    def record_outcome(
        self,
        actual_outcome: str,
        actual_result: bool,
        outcome_metadata: Dict[str, Any],
    ):
        """Record actual outcome when it becomes available"""
        self.actual_outcome = actual_outcome
        self.actual_result = actual_result
        self.outcome_recorded_at = datetime.utcnow()
        self.outcome_metadata = outcome_metadata

        # Calculate confidence gap
        confidence_gap = self._calculate_confidence_gap()
        logger.info(
            f"[OutcomeTracker] {self.orchestrator}:{self.decision_type} "
            f"decision_id={self.decision_id} "
            f"predicted={self.predicted_outcome}({self.predicted_probability:.2f}) "
            f"actual={self.actual_outcome}({actual_result}) "
            f"gap={confidence_gap:.2f}"
        )

        return {
            "decision_id": self.decision_id,
            "predicted": self.predicted_outcome,
            "predicted_probability": self.predicted_probability,
            "actual": self.actual_outcome,
            "actual_result": actual_result,
            "confidence_gap": confidence_gap,
        }

    def _calculate_confidence_gap(self) -> float:
        """
        Gap between predicted probability and actual outcome.
        0.0 = perfect prediction
        1.0 = completely wrong prediction
        """
        if self.actual_result is None:
            return 0.0

        # If predicted 70% and it happened (True), gap = |0.7 - 1.0| = 0.3
        # If predicted 70% and it didn't happen (False), gap = |0.7 - 0.0| = 0.7
        predicted_for_actual = 1.0 if self.actual_result else 0.0
        gap = abs(self.predicted_probability - predicted_for_actual)
        return gap


class LearningOutcomeTracker:
    """Service for tracking and recording decision outcomes"""

    # Map decision types to outcome timeframes
    OUTCOME_TIMEFRAMES = {
        "thunder_email_sent": timedelta(hours=24),  # Did they open within 24h?
        "thunder_sms_sent": timedelta(hours=2),  # Response expected within 2h
        "thunder_whatsapp_sent": timedelta(hours=4),  # Within 4h
        "interview_scheduled": timedelta(days=1),  # Did they show up?
        "offer_generated": timedelta(days=5),  # Decision within 5 days
        "candidate_created": timedelta(days=7),  # Reached interview within week
        "job_posted": timedelta(days=30),  # Hire made within 30 days
    }

    @staticmethod
    def create_decision(
        db: Session,
        orchestrator: str,
        decision_type: str,
        entity_id: str,
        predicted_outcome: str,
        predicted_probability: float,
        decision_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a decision record with predicted outcome.

        Called when Thunder/Flash/Interview makes a decision.

        Args:
            orchestrator: "thunder", "flash", "interview", "offer", "finance"
            decision_type: "email_sent", "job_match", "interview_pass_prediction", "offer_salary"
            entity_id: candidate_id, job_id, interview_id, offer_id
            predicted_outcome: string description of expected outcome
            predicted_probability: 0.0-1.0 confidence
            decision_metadata: dict of factors that drove decision

        Returns:
            Decision record for later outcome recording
        """
        decision_id = str(uuid.uuid4())

        try:
            decision = DecisionOutcome(
                decision_id=decision_id,
                decision_type=decision_type,
                orchestrator=orchestrator,
                entity_id=entity_id,
                predicted_outcome=predicted_outcome,
                predicted_probability=predicted_probability,
                predicted_at=datetime.utcnow(),
                decision_metadata=decision_metadata,
            )

            logger.info(
                f"[OutcomeTracker] Decision created: "
                f"id={decision_id} "
                f"type={decision_type} "
                f"entity={entity_id} "
                f"predicted={predicted_outcome} "
                f"confidence={predicted_probability:.2f}"
            )

            return {
                "decision_id": decision_id,
                "decision": decision,
                "outcome_timeframe": LearningOutcomeTracker.OUTCOME_TIMEFRAMES.get(
                    decision_type, timedelta(days=7)
                ),
                "expected_outcome_by": datetime.utcnow()
                + LearningOutcomeTracker.OUTCOME_TIMEFRAMES.get(
                    decision_type, timedelta(days=7)
                ),
            }

        except Exception as e:
            logger.error(f"[OutcomeTracker] Failed to create decision: {e}")
            raise

    @staticmethod
    def record_outcome(
        decision: DecisionOutcome,
        actual_outcome: str,
        actual_result: bool,
        outcome_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Record actual outcome when it becomes available.

        Called when we learn the real result:
        - Thunder: Email opened → record engagement outcome
        - Interview: Interviewer feedback received → record pass/fail
        - Offer: Candidate response received → record acceptance/rejection

        Args:
            decision: DecisionOutcome object from create_decision
            actual_outcome: what actually happened
            actual_result: True if prediction was correct, False if wrong
            outcome_metadata: details about what happened

        Returns:
            Outcome record with confidence gap measurement
        """
        if decision is None:
            logger.error("[OutcomeTracker] Cannot record outcome for None decision")
            raise ValueError("Decision object required")

        return decision.record_outcome(actual_outcome, actual_result, outcome_metadata)

    @staticmethod
    def get_pending_outcomes(
        db: Session,
        cutoff_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all decisions that are overdue for outcome recording.

        Args:
            cutoff_date: datetime after which to consider outcome "late"
                        If None, uses now - 1 hour (some decisions take time to complete)

        Returns:
            List of pending decision records
        """
        if cutoff_date is None:
            cutoff_date = datetime.utcnow() - timedelta(hours=1)

        # Query Thunder metrics for pending outcomes
        pending_thunder = (
            db.query(ThunderLearningMetrics)
            .filter(
                and_(
                    ThunderLearningMetrics.timestamp < cutoff_date,
                )
            )
            .all()
        )

        # Query Flash metrics for pending outcomes
        pending_flash = (
            db.query(FlashLearningMetrics)
            .filter(
                and_(
                    FlashLearningMetrics.timestamp < cutoff_date,
                )
            )
            .all()
        )

        logger.info(
            f"[OutcomeTracker] Found {len(pending_thunder)} Thunder, "
            f"{len(pending_flash)} Flash pending outcomes"
        )

        return {
            "thunder_pending": pending_thunder,
            "flash_pending": pending_flash,
            "total_pending": len(pending_thunder) + len(pending_flash),
        }

    @staticmethod
    def calculate_decision_quality(
        db: Session,
        orchestrator: str,
        decision_type: str,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Calculate quality of recent decisions: how often was prediction correct?

        Args:
            orchestrator: "thunder", "flash", "interview", "offer"
            decision_type: "email_sent", "interview_pass", "offer_accepted"
            lookback_days: analyze last N days of decisions

        Returns:
            Quality metrics: accuracy, precision, recall, confidence calibration
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        # This would query the outcome table once we integrate it
        # For now, placeholder structure
        return {
            "orchestrator": orchestrator,
            "decision_type": decision_type,
            "lookback_days": lookback_days,
            "total_decisions": 0,
            "correct_predictions": 0,
            "accuracy": 0.0,
            "average_confidence": 0.0,
            "confidence_gap": 0.0,  # Should be close to 0.0 for good calibration
            "recommendation": "Increase data collection before analyzing",
        }
