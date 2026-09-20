"""
PHASE 3: ARCHITECT APPROVAL DASHBOARD (2026-09-19)

Real-time decision metrics for architect approval engine:
- Decision accuracy (% of decisions that were correct in retrospect)
- Confidence scores (trust in each decision)
- Decision speed (time to decision)
- Authority Level distribution (level 1-3 decisions)
- Escalation tracking (what gets escalated, why)
- Learning improvement curves (accuracy improving over time)
- Cascade detection accuracy (false positives/negatives)

This dashboard enables monitoring of architect quality and identifies areas
where architect decision patterns can improve.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ArchitectDecisionRecord:
    """Record of a single architect decision for analysis."""
    timestamp: datetime
    decision_id: str
    category: str  # code_quality, security, architecture, performance, data_integrity
    decision: str  # APPROVE, BLOCK, ESCALATE, INVESTIGATE
    authority_level: int  # 1=autonomous, 2=needs_approval, 3=ceo_only
    confidence: float  # 0.0-1.0
    reasoning: str
    affected_files: List[str]
    time_to_decision_seconds: float

    # Retroactive accuracy assessment (assigned later)
    was_correct: Optional[bool] = None
    production_impact: Optional[str] = None  # none, minor, major, critical
    learning_applied: Optional[str] = None  # What was learned


@dataclass
class EscalationEvent:
    """Record of escalation to higher authority."""
    timestamp: datetime
    decision_id: str
    from_level: int
    to_level: int
    reason: str
    human_approval_time_seconds: Optional[float] = None
    final_decision: Optional[str] = None
    was_architect_correct: Optional[bool] = None


class Phase3ArchitectApprovalDashboard:
    """
    Monitor architect approval engine quality and learning loop.

    Endpoints:
    - GET /monitoring/architect/accuracy
    - GET /monitoring/architect/confidence
    - GET /monitoring/architect/decision-speed
    - GET /monitoring/architect/escalations
    - GET /monitoring/architect/learning-curves
    - GET /monitoring/architect/health
    """

    def __init__(self):
        """Initialize approval dashboard."""
        self.decisions: List[ArchitectDecisionRecord] = []
        self.escalations: List[EscalationEvent] = []
        self.dashboard_started = datetime.now()
        self.learning_history: List[Dict] = []

    def record_decision(
        self,
        decision_id: str,
        category: str,
        decision: str,
        authority_level: int,
        confidence: float,
        reasoning: str,
        affected_files: List[str],
        time_to_decision_seconds: float,
    ) -> None:
        """Record architect decision for metrics tracking."""
        record = ArchitectDecisionRecord(
            timestamp=datetime.now(),
            decision_id=decision_id,
            category=category,
            decision=decision,
            authority_level=authority_level,
            confidence=confidence,
            reasoning=reasoning,
            affected_files=affected_files,
            time_to_decision_seconds=time_to_decision_seconds,
        )
        self.decisions.append(record)
        logger.info(
            f"[ARCHITECT] Decision {decision_id}: {decision} "
            f"(confidence: {confidence:.2%}, time: {time_to_decision_seconds:.1f}s)"
        )

    def record_escalation(
        self,
        decision_id: str,
        from_level: int,
        to_level: int,
        reason: str,
    ) -> None:
        """Record decision escalation."""
        escalation = EscalationEvent(
            timestamp=datetime.now(),
            decision_id=decision_id,
            from_level=from_level,
            to_level=to_level,
            reason=reason,
        )
        self.escalations.append(escalation)
        logger.info(
            f"[ARCHITECT] Escalation {decision_id}: Level {from_level} → {to_level} "
            f"({reason})"
        )

    def complete_escalation(
        self,
        decision_id: str,
        approval_time_seconds: float,
        final_decision: str,
        was_architect_correct: bool,
    ) -> None:
        """Mark escalation as complete with human approval outcome."""
        for escalation in self.escalations:
            if escalation.decision_id == decision_id:
                escalation.human_approval_time_seconds = approval_time_seconds
                escalation.final_decision = final_decision
                escalation.was_architect_correct = was_architect_correct

                if was_architect_correct:
                    logger.info(
                        f"[ARCHITECT] Escalation {decision_id} VALIDATED "
                        f"(approval time: {approval_time_seconds:.0f}s)"
                    )
                else:
                    logger.warning(
                        f"[ARCHITECT] Escalation {decision_id} OVERRIDDEN "
                        f"by human approval"
                    )
                break

    def assess_decision_accuracy(
        self,
        decision_id: str,
        was_correct: bool,
        production_impact: str,
        learning: Optional[str] = None,
    ) -> None:
        """
        Assess decision accuracy in retrospect (after commit shipped).

        Args:
            decision_id: Decision to assess
            was_correct: Was architect right?
            production_impact: none | minor | major | critical
            learning: What to learn (None if correct)
        """
        for decision in self.decisions:
            if decision.decision_id == decision_id:
                decision.was_correct = was_correct
                decision.production_impact = production_impact
                decision.learning_applied = learning

                if was_correct:
                    logger.info(
                        f"[ARCHITECT] Decision {decision_id} VALIDATED "
                        f"(impact: {production_impact})"
                    )
                else:
                    logger.warning(
                        f"[ARCHITECT] Decision {decision_id} INCORRECT "
                        f"(impact: {production_impact}, learning: {learning})"
                    )

                if learning:
                    self.learning_history.append({
                        "timestamp": datetime.now(),
                        "decision_id": decision_id,
                        "learning": learning,
                        "category": decision.category,
                    })
                break

    # ======== DASHBOARD ENDPOINTS ========

    def get_accuracy_metrics(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/architect/accuracy

        Decision accuracy over recent period.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [d for d in self.decisions if d.timestamp >= cutoff and d.was_correct is not None]

        if not recent:
            return {
                "decisions_assessed": 0,
                "accuracy": None,
                "by_category": {},
                "by_authority_level": {},
            }

        correct = sum(1 for d in recent if d.was_correct)
        accuracy = correct / len(recent)

        # By category
        by_category = {}
        for decision in recent:
            cat = decision.category
            if cat not in by_category:
                by_category[cat] = {"total": 0, "correct": 0}
            by_category[cat]["total"] += 1
            if decision.was_correct:
                by_category[cat]["correct"] += 1

        for cat in by_category:
            by_category[cat]["accuracy"] = (
                by_category[cat]["correct"] / by_category[cat]["total"]
            )

        # By authority level
        by_level = {}
        for decision in recent:
            level = f"level_{decision.authority_level}"
            if level not in by_level:
                by_level[level] = {"total": 0, "correct": 0}
            by_level[level]["total"] += 1
            if decision.was_correct:
                by_level[level]["correct"] += 1

        for level in by_level:
            by_level[level]["accuracy"] = (
                by_level[level]["correct"] / by_level[level]["total"]
            )

        # Impact analysis
        critical_mistakes = [
            d for d in recent
            if not d.was_correct and d.production_impact == "critical"
        ]

        return {
            "decisions_assessed": len(recent),
            "accuracy": accuracy,
            "by_category": by_category,
            "by_authority_level": by_level,
            "critical_mistakes_count": len(critical_mistakes),
            "critical_mistakes": [
                {
                    "decision_id": d.decision_id,
                    "category": d.category,
                    "timestamp": d.timestamp.isoformat(),
                    "learning": d.learning_applied,
                }
                for d in critical_mistakes[:5]  # Top 5
            ],
        }

    def get_confidence_metrics(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/architect/confidence

        Confidence scores vs actual accuracy.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [d for d in self.decisions if d.timestamp >= cutoff and d.was_correct is not None]

        if not recent:
            return {
                "decisions": 0,
                "average_confidence": None,
                "confidence_calibration": None,
            }

        # Group by confidence buckets
        buckets = {
            "0-50%": [],
            "50-70%": [],
            "70-85%": [],
            "85-95%": [],
            "95-100%": [],
        }

        for decision in recent:
            conf = decision.confidence
            if conf < 0.5:
                buckets["0-50%"].append(decision)
            elif conf < 0.7:
                buckets["50-70%"].append(decision)
            elif conf < 0.85:
                buckets["70-85%"].append(decision)
            elif conf < 0.95:
                buckets["85-95%"].append(decision)
            else:
                buckets["95-100%"].append(decision)

        # Calculate accuracy per bucket
        calibration = {}
        for bucket_name, decisions_in_bucket in buckets.items():
            if decisions_in_bucket:
                accuracy = sum(1 for d in decisions_in_bucket if d.was_correct) / len(
                    decisions_in_bucket
                )
                calibration[bucket_name] = {
                    "count": len(decisions_in_bucket),
                    "accuracy": accuracy,
                    "expected_accuracy": float(bucket_name.split("-")[0].rstrip("%")) / 100,
                }

        avg_confidence = sum(d.confidence for d in recent) / len(recent)

        return {
            "decisions": len(recent),
            "average_confidence": avg_confidence,
            "confidence_calibration": calibration,
            "confidence_over_time": [
                {
                    "timestamp": d.timestamp.isoformat(),
                    "confidence": d.confidence,
                    "was_correct": d.was_correct,
                }
                for d in recent[-20:]  # Last 20
            ],
        }

    def get_decision_speed_metrics(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/architect/decision-speed

        How fast architect makes decisions (and does speed correlate with accuracy?).
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [d for d in self.decisions if d.timestamp >= cutoff]

        if not recent:
            return {"decisions": 0, "average_speed": None}

        times = [d.time_to_decision_seconds for d in recent]
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)

        # By category
        by_category = {}
        for decision in recent:
            cat = decision.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(decision.time_to_decision_seconds)

        for cat in by_category:
            times_cat = by_category[cat]
            by_category[cat] = {
                "count": len(times_cat),
                "average": sum(times_cat) / len(times_cat),
                "min": min(times_cat),
                "max": max(times_cat),
            }

        # Speed vs accuracy (does fast = wrong?)
        with_accuracy = [d for d in recent if d.was_correct is not None]
        if with_accuracy:
            fast = [d for d in with_accuracy if d.time_to_decision_seconds < avg_time]
            slow = [d for d in with_accuracy if d.time_to_decision_seconds >= avg_time]

            fast_accuracy = (
                sum(1 for d in fast if d.was_correct) / len(fast) if fast else None
            )
            slow_accuracy = (
                sum(1 for d in slow if d.was_correct) / len(slow) if slow else None
            )
        else:
            fast_accuracy = None
            slow_accuracy = None

        return {
            "decisions": len(recent),
            "average_decision_time_seconds": avg_time,
            "min_time_seconds": min_time,
            "max_time_seconds": max_time,
            "by_category": by_category,
            "fast_decisions_accuracy": fast_accuracy,
            "slow_decisions_accuracy": slow_accuracy,
        }

    def get_escalation_metrics(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/architect/escalations

        Escalation patterns and human approval outcomes.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [e for e in self.escalations if e.timestamp >= cutoff]

        if not recent:
            return {
                "escalations": 0,
                "escalation_rate": 0.0,
            }

        # Escalation paths
        paths = {}
        for escalation in recent:
            path = f"level_{escalation.from_level}_to_{escalation.to_level}"
            if path not in paths:
                paths[path] = {"count": 0, "approved_architect": 0, "overridden": 0}
            paths[path]["count"] += 1
            if escalation.was_architect_correct is not None:
                if escalation.was_architect_correct:
                    paths[path]["approved_architect"] += 1
                else:
                    paths[path]["overridden"] += 1

        # Approval time
        approved_escalations = [
            e for e in recent
            if e.human_approval_time_seconds is not None
        ]
        avg_approval_time = (
            sum(e.human_approval_time_seconds for e in approved_escalations)
            / len(approved_escalations)
            if approved_escalations
            else None
        )

        total_decisions = len(
            [d for d in self.decisions if d.timestamp >= cutoff]
        )
        escalation_rate = len(recent) / total_decisions if total_decisions else 0

        return {
            "escalations": len(recent),
            "escalation_rate": escalation_rate,
            "paths": paths,
            "average_approval_time_seconds": avg_approval_time,
            "architect_validation_rate": (
                sum(1 for e in approved_escalations if e.was_architect_correct)
                / len(approved_escalations)
                if approved_escalations
                else None
            ),
        }

    def get_learning_curves(self) -> Dict:
        """
        GET /monitoring/architect/learning-curves

        Architect quality improving over time (learning from mistakes).
        """
        if not self.decisions or not self.learning_history:
            return {
                "learnings_applied": 0,
                "accuracy_trend": None,
            }

        # Accuracy over time (last week)
        week_ago = datetime.now() - timedelta(days=7)
        week_decisions = [
            d for d in self.decisions
            if d.timestamp >= week_ago and d.was_correct is not None
        ]

        if not week_decisions:
            return {
                "learnings_applied": len(self.learning_history),
                "accuracy_trend": None,
            }

        # Split into quarters
        days = 7
        quarter_size = len(week_decisions) // 4 if len(week_decisions) >= 4 else 1

        quarters = []
        for i in range(4):
            start_idx = i * quarter_size
            end_idx = (i + 1) * quarter_size if i < 3 else len(week_decisions)
            if start_idx < len(week_decisions):
                quarter_decisions = week_decisions[start_idx:end_idx]
                accuracy = (
                    sum(1 for d in quarter_decisions if d.was_correct)
                    / len(quarter_decisions)
                    if quarter_decisions
                    else None
                )
                quarters.append({
                    "quarter": i + 1,
                    "accuracy": accuracy,
                    "decisions": len(quarter_decisions),
                })

        # Group learnings by category
        learnings_by_category = {}
        for learning_record in self.learning_history:
            cat = learning_record["category"]
            if cat not in learnings_by_category:
                learnings_by_category[cat] = []
            learnings_by_category[cat].append(learning_record["learning"])

        return {
            "learnings_applied": len(self.learning_history),
            "accuracy_trend": quarters,
            "learnings_by_category": learnings_by_category,
            "recent_learnings": [
                {
                    "timestamp": l["timestamp"].isoformat(),
                    "category": l["category"],
                    "learning": l["learning"],
                }
                for l in self.learning_history[-10:]  # Last 10
            ],
        }

    def get_health_summary(self) -> Dict:
        """
        GET /monitoring/architect/health

        Overall architect approval system health.
        """
        return {
            "dashboard_uptime": (
                (datetime.now() - self.dashboard_started).total_seconds()
            ),
            "decisions_made": len(self.decisions),
            "escalations": len(self.escalations),
            "learnings_applied": len(self.learning_history),
            "recent_accuracy": self.get_accuracy_metrics(hours=1).get("accuracy"),
            "average_confidence": self.get_confidence_metrics(hours=1).get(
                "average_confidence"
            ),
            "escalation_rate": self.get_escalation_metrics(hours=1).get(
                "escalation_rate"
            ),
            "average_decision_speed": self.get_decision_speed_metrics(hours=1).get(
                "average_decision_time_seconds"
            ),
        }


# Global instance for monitoring
_dashboard_instance: Optional[Phase3ArchitectApprovalDashboard] = None


def get_architect_approval_dashboard() -> Phase3ArchitectApprovalDashboard:
    """Get or create global dashboard instance."""
    global _dashboard_instance
    if _dashboard_instance is None:
        _dashboard_instance = Phase3ArchitectApprovalDashboard()
    return _dashboard_instance
