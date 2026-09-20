"""
PHASE 2 MONITORING DASHBOARD (2026-09-19)

Real-time visibility into Phase 2 systems:
- Architect decision engine (confidence, auto-approve rate)
- Cascade detector (cascades detected/prevented)
- Incident learning (learnings applied, gate improvements)
- SDLC orchestration (decision metrics)
- Chaos tests (failure scenario results)

Metrics exposed as REST endpoints for real-time monitoring.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Phase2MonitoringDashboard:
    """
    Real-time metrics for Phase 2 (Architect, Cascade, Learning, SDLC)

    Endpoints:
    - GET /monitoring/architect-decisions
    - GET /monitoring/cascade-detection
    - GET /monitoring/incidents
    - GET /monitoring/sdlc-status
    - GET /monitoring/chaos-tests
    - GET /monitoring/phase2-health
    """

    def __init__(
        self,
        architect_engine=None,
        cascade_detector=None,
        learning_service=None,
        sdlc_orchestrator=None,
        chaos_suite=None,
    ):
        """Initialize monitoring dashboard with all Phase 2 components."""
        self.architect = architect_engine
        self.cascade = cascade_detector
        self.learning = learning_service
        self.sdlc = sdlc_orchestrator
        self.chaos = chaos_suite

        self.dashboard_started = datetime.now()

    def get_architect_decisions_metrics(self) -> Dict:
        """
        GET /monitoring/architect-decisions

        Returns: Architect decision metrics and confidence scores
        """
        if not self.architect:
            return {
                "error": "Architect engine not configured",
                "decisions_made": 0,
            }

        decisions = self.architect.decisions_log

        if not decisions:
            return {
                "decisions_made": 0,
                "auto_approve_rate": 0.0,
                "decision_accuracy": 0.0,
                "average_confidence": 0.0,
                "decisions_by_authority_level": {},
            }

        # Count by decision type
        approved = sum(1 for d in decisions if d.decision == "APPROVE")
        blocked = sum(1 for d in decisions if d.decision == "BLOCK")
        escalated = sum(1 for d in decisions if d.decision == "ESCALATE")
        investigate = sum(1 for d in decisions if d.decision == "INVESTIGATE")

        # Count by authority level
        by_authority = {}
        for d in decisions:
            level = d.authority_level
            by_authority[level] = by_authority.get(level, 0) + 1

        # Calculate metrics
        avg_confidence = sum(d.confidence for d in decisions) / len(decisions)

        return {
            "decisions_made": len(decisions),
            "approved": approved,
            "blocked": blocked,
            "escalated": escalated,
            "investigate": investigate,
            "auto_approve_rate": approved / len(decisions),
            "average_confidence": avg_confidence,
            "decisions_by_authority_level": by_authority,
            "recent_decisions": [
                {
                    "category": d.category.value,
                    "decision": d.decision,
                    "confidence": f"{d.confidence:.0f}%",
                    "timestamp": d.timestamp.isoformat(),
                }
                for d in decisions[-5:]
            ],
        }

    def get_cascade_detection_metrics(self) -> Dict:
        """
        GET /monitoring/cascade-detection

        Returns: Cascade failure detection and prevention metrics
        """
        if not self.cascade:
            return {
                "error": "Cascade detector not configured",
                "cascades_detected": 0,
            }

        status = self.cascade.get_cascade_status()

        return {
            "cascades_detected": status.get("cascades_detected", 0),
            "cascades_prevented": status.get("cascades_prevented", 0),
            "phalanx_integrity": f"{status.get('phalanx_integrity', 1.0):.0%}",
            "circuit_breakers_active": status.get("circuit_breakers_active", 0),
            "average_detection_time_ms": 0,  # Would be calculated from real data
            "active_cascades": status.get("active_cascades", []),
            "cascade_patterns": [
                {
                    "pattern": c["pattern"],
                    "initiator": c["initiator"],
                    "affected_systems": len(c["affected"]),
                    "severity": c["severity"],
                }
                for c in status.get("active_cascades", [])
            ],
        }

    def get_incident_learning_metrics(self) -> Dict:
        """
        GET /monitoring/incidents

        Returns: Incident learning and gate improvement metrics
        """
        if not self.learning:
            return {
                "error": "Learning service not configured",
                "incidents_analyzed": 0,
            }

        status = self.learning.get_learning_status()

        return {
            "incidents_analyzed": status.get("incidents_analyzed", 0),
            "root_causes_identified": sum(
                len(v) for v in status.get("categories", {}).values()
            ),
            "gate_rules_improved": len(status.get("gate_improvements", {})),
            "test_cases_generated": status.get("test_cases_generated", 0),
            "learning_categories": status.get("categories", {}),
            "recent_learnings": status.get("recent_learnings", [])[:5],
            "architect_improvements": [
                f"{k}: {len(v)} learnings"
                for k, v in status.get("architect_improvements", {}).items()
            ][:5],
        }

    def get_sdlc_status_metrics(self) -> Dict:
        """
        GET /monitoring/sdlc-status

        Returns: SDLC orchestration metrics
        """
        if not self.sdlc:
            return {
                "error": "SDLC orchestrator not configured",
                "decisions_made": 0,
            }

        metrics = self.sdlc.get_sdlc_metrics()

        return {
            "decisions_made": metrics.get("decisions_made", 0),
            "approved": metrics.get("approved", 0),
            "blocked": metrics.get("blocked", 0),
            "escalated": metrics.get("escalated", 0),
            "auto_approve_rate": f"{metrics.get('auto_approve_rate', 0):.0%}",
            "architect_average_confidence": f"{metrics.get('architect_avg_confidence', 0):.0f}%",
            "cascade_risk_average": f"{metrics.get('cascade_risk_avg', 0):.0f}/100",
            "learning_applied_count": metrics.get("learning_applied_count", 0),
        }

    def get_chaos_test_metrics(self) -> Dict:
        """
        GET /monitoring/chaos-tests

        Returns: Chaos engineering test results
        """
        if not self.chaos:
            return {
                "error": "Chaos test suite not configured",
                "tests_run": 0,
            }

        summary = self.chaos.get_results_summary()

        return {
            "tests_run": summary.get("tests_run", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "pass_rate": f"{summary.get('pass_rate', 0):.0%}",
            "average_recovery_time_sec": f"{summary.get('avg_recovery_time_sec', 0):.1f}s",
            "zero_data_loss_count": summary.get("zero_data_loss_count", 0),
            "logs_complete_count": summary.get("logs_complete_count", 0),
            "results": summary.get("results", [])[:10],
        }

    def get_phase2_health(self) -> Dict:
        """
        GET /monitoring/phase2-health

        Returns: Overall Phase 2 system health
        """

        # Aggregate all metrics
        architect_metrics = self.get_architect_decisions_metrics()
        cascade_metrics = self.get_cascade_detection_metrics()
        learning_metrics = self.get_incident_learning_metrics()
        sdlc_metrics = self.get_sdlc_status_metrics()
        chaos_metrics = self.get_chaos_test_metrics()

        # Calculate health score (0-100)
        health_score = 100

        # Reduce for architect issues
        if architect_metrics.get("auto_approve_rate", 0) < 0.70:
            health_score -= 10

        # Reduce for cascade risk
        cascade_integrity = self._parse_percentage(cascade_metrics.get("phalanx_integrity", "100%"))
        if cascade_integrity < 0.90:
            health_score -= 15

        # Reduce if incidents not being learned
        if learning_metrics.get("incidents_analyzed", 0) == 0:
            health_score -= 5

        # Reduce for chaos test failures
        if chaos_metrics.get("tests_run", 0) > 0:
            chaos_pass_rate = self._parse_percentage(chaos_metrics.get("pass_rate", "100%"))
            if chaos_pass_rate < 1.0:
                health_score -= (1.0 - chaos_pass_rate) * 20

        return {
            "overall_health_score": health_score,
            "health_status": "HEALTHY" if health_score >= 85 else (
                "DEGRADED" if health_score >= 70 else "CRITICAL"
            ),
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": (
                (datetime.now() - self.dashboard_started).total_seconds() / 3600
            ),
            "architect_decisions": architect_metrics,
            "cascade_detection": cascade_metrics,
            "incident_learning": learning_metrics,
            "sdlc_orchestration": sdlc_metrics,
            "chaos_engineering": chaos_metrics,
            "alerts": self._generate_alerts(
                architect_metrics,
                cascade_metrics,
                learning_metrics,
                chaos_metrics,
            ),
        }

    def _parse_percentage(self, value: str) -> float:
        """Parse percentage string to float."""
        try:
            return float(value.rstrip("%")) / 100.0
        except (ValueError, AttributeError):
            return 1.0

    def _generate_alerts(self, *metrics_dicts) -> list:
        """Generate alerts based on metrics."""
        alerts = []

        for metrics in metrics_dicts:
            if metrics.get("error"):
                alerts.append(f"ERROR: {metrics['error']}")

        return alerts


# Dashboard REST endpoints (for FastAPI integration)
async def get_architect_decisions(dashboard: Phase2MonitoringDashboard):
    """GET /monitoring/architect-decisions"""
    return dashboard.get_architect_decisions_metrics()


async def get_cascade_detection(dashboard: Phase2MonitoringDashboard):
    """GET /monitoring/cascade-detection"""
    return dashboard.get_cascade_detection_metrics()


async def get_incident_learning(dashboard: Phase2MonitoringDashboard):
    """GET /monitoring/incidents"""
    return dashboard.get_incident_learning_metrics()


async def get_sdlc_status(dashboard: Phase2MonitoringDashboard):
    """GET /monitoring/sdlc-status"""
    return dashboard.get_sdlc_status_metrics()


async def get_chaos_tests(dashboard: Phase2MonitoringDashboard):
    """GET /monitoring/chaos-tests"""
    return dashboard.get_chaos_test_metrics()


async def get_phase2_health(dashboard: Phase2MonitoringDashboard):
    """GET /monitoring/phase2-health - Overall Phase 2 system health"""
    return dashboard.get_phase2_health()
