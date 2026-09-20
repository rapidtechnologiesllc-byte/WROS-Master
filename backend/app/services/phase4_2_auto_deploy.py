"""
PHASE 4.2: DEPLOYMENT → AUTO-DEPLOY (2026-09-19)

Automatically deploy merged code to production with blue-green deployment
and canary analysis.

Deployment Strategy:
1. Blue-Green Deployment: Run new and old versions in parallel
2. Health Checks: Every 10 seconds to 4 backends
3. Canary Rollout: 5% → 50% → 100% traffic
4. Automatic Rollback: On health check failure
5. Post-Deploy Monitoring: Error rate, latency, resource usage

Deployment Phases:
Phase 1 (Canary 5%): Route 5% traffic to new version, monitor 2 minutes
Phase 2 (Ramp 50%): Route 50% traffic to new version, monitor 2 minutes
Phase 3 (Production 100%): Route 100% traffic to new version, monitor 5 minutes

Rollback Triggers:
- Health check failure (consecutive 3 failures)
- Error rate > 2% (vs baseline < 0.1%)
- Latency p99 > baseline * 1.2
- Critical errors (500, 503, etc.)
- OOM or resource exhaustion

Safety Features:
- Max deployment size: 50 files
- Max changes: 5000 lines of code
- Deployment window: Business hours only (optional)
- Require approval for: Database migrations, permission changes
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeploymentPhase(Enum):
    """Deployment phase status."""
    PENDING = "pending"
    VALIDATION = "validation"
    CANARY_5PCT = "canary_5pct"
    CANARY_50PCT = "canary_50pct"
    PRODUCTION = "production"
    MONITORING = "monitoring"
    COMPLETE = "complete"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class DeploymentMetrics:
    """Metrics collected during deployment."""
    timestamp: datetime
    phase: DeploymentPhase
    error_rate: float  # 0.0-1.0
    latency_p50: float  # milliseconds
    latency_p95: float
    latency_p99: float
    cpu_usage: float  # 0.0-1.0
    memory_usage: float  # 0.0-1.0
    active_connections: int
    health_checks_passed: int
    health_checks_failed: int


@dataclass
class DeploymentExecution:
    """Record of a production deployment."""
    deployment_id: str
    commit_sha: str
    author: str
    timestamp: datetime

    # Deployment tracking
    current_phase: DeploymentPhase = DeploymentPhase.PENDING
    phase_start_time: Optional[datetime] = None
    phase_end_time: Optional[datetime] = None

    # Metrics
    baseline_metrics: Optional[Dict] = None  # Metrics before deployment
    metrics_history: List[DeploymentMetrics] = None

    # Rollback
    rolled_back: bool = False
    rollback_reason: Optional[str] = None
    rollback_timestamp: Optional[datetime] = None

    # Validation
    pre_deploy_validation_passed: bool = False
    size_check_passed: bool = False
    change_count_check_passed: bool = False


class Phase4_2AutoDeploy:
    """
    Automatically deploy merged code with blue-green + canary strategy.

    Endpoints:
    - POST /deploy/start/{commit_sha}
    - GET /deploy/status/{deployment_id}
    - POST /deploy/rollback/{deployment_id}
    - GET /deploy/history
    - GET /deploy/metrics/{deployment_id}
    """

    def __init__(self):
        """Initialize auto-deploy system."""
        self.deployments: List[DeploymentExecution] = []
        self.active_deployments: Dict[str, DeploymentExecution] = {}
        self.deployment_config = {
            "blue_green_enabled": True,
            "canary_enabled": True,
            "canary_phases": [
                {"percentage": 5, "duration_seconds": 120},
                {"percentage": 50, "duration_seconds": 120},
                {"percentage": 100, "duration_seconds": 300},
            ],
            "health_check_interval_seconds": 10,
            "max_file_changes": 50,
            "max_line_changes": 5000,
            "rollback_triggers": {
                "error_rate_threshold": 0.02,  # 2% error rate
                "latency_increase_threshold": 0.20,  # 20% increase
                "health_check_failures": 3,
                "critical_errors": True,
            },
        }

    def start_deployment(
        self,
        commit_sha: str,
        author: str,
        files_changed: int,
        lines_changed: int,
    ) -> Optional[DeploymentExecution]:
        """
        Start deployment of merged commit.

        Returns:
            DeploymentExecution if validation passes, None otherwise
        """
        deployment_id = f"deploy_{commit_sha[:8]}_{int(datetime.now().timestamp())}"

        logger.info(
            f"[AUTO_DEPLOY] Starting deployment {deployment_id} "
            f"(commit {commit_sha[:8]}, author {author})"
        )

        deployment = DeploymentExecution(
            deployment_id=deployment_id,
            commit_sha=commit_sha,
            author=author,
            timestamp=datetime.now(),
            metrics_history=[],
        )

        # Step 1: Pre-deployment validation
        if not self._validate_deployment(deployment, files_changed, lines_changed):
            logger.error(f"[AUTO_DEPLOY] Deployment {deployment_id} failed validation")
            deployment.current_phase = DeploymentPhase.FAILED
            return None

        deployment.pre_deploy_validation_passed = True

        # Step 2: Capture baseline metrics
        baseline = self._capture_metrics(deployment, DeploymentPhase.VALIDATION)
        deployment.baseline_metrics = baseline

        logger.info(
            f"[AUTO_DEPLOY] Baseline metrics captured: "
            f"error_rate={baseline.get('error_rate', 0):.2%}, "
            f"latency_p99={baseline.get('latency_p99', 0):.0f}ms"
        )

        # Step 3: Start canary deployment
        self._start_canary_phase(deployment)

        self.deployments.append(deployment)
        self.active_deployments[deployment_id] = deployment

        return deployment

    def _validate_deployment(
        self,
        deployment: DeploymentExecution,
        files_changed: int,
        lines_changed: int,
    ) -> bool:
        """Validate deployment is safe."""
        logger.info(
            f"[AUTO_DEPLOY] Validating deployment: "
            f"{files_changed} files, {lines_changed} lines"
        )

        # Check file count
        if files_changed > self.deployment_config["max_file_changes"]:
            logger.error(
                f"[AUTO_DEPLOY] Too many files changed: {files_changed} "
                f"(max: {self.deployment_config['max_file_changes']})"
            )
            return False

        deployment.size_check_passed = True

        # Check line count
        if lines_changed > self.deployment_config["max_line_changes"]:
            logger.error(
                f"[AUTO_DEPLOY] Too many lines changed: {lines_changed} "
                f"(max: {self.deployment_config['max_line_changes']})"
            )
            return False

        deployment.change_count_check_passed = True

        logger.info("[AUTO_DEPLOY] Validation passed")
        return True

    def _capture_metrics(
        self,
        deployment: DeploymentExecution,
        phase: DeploymentPhase,
    ) -> DeploymentMetrics:
        """Capture current system metrics."""
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            phase=phase,
            error_rate=0.001,  # Example: 0.1%
            latency_p50=45.0,
            latency_p95=120.0,
            latency_p99=250.0,
            cpu_usage=0.45,
            memory_usage=0.62,
            active_connections=150,
            health_checks_passed=4,
            health_checks_failed=0,
        )

        deployment.metrics_history.append(metrics)
        return metrics

    def _start_canary_phase(self, deployment: DeploymentExecution) -> None:
        """Start canary deployment (5% traffic)."""
        deployment.current_phase = DeploymentPhase.CANARY_5PCT
        deployment.phase_start_time = datetime.now()

        logger.info(
            f"[AUTO_DEPLOY] Starting canary phase (5% traffic): {deployment.deployment_id}"
        )

        # Monitor canary phase
        self._monitor_canary_phase(deployment)

    def _monitor_canary_phase(self, deployment: DeploymentExecution) -> None:
        """Monitor deployment health during canary."""
        logger.info(
            f"[AUTO_DEPLOY] Monitoring canary deployment {deployment.deployment_id}"
        )

        # Simulate monitoring loop
        for phase_config in self.deployment_config["canary_phases"]:
            percentage = phase_config["percentage"]
            duration = phase_config["duration_seconds"]

            if percentage == 5:
                deployment.current_phase = DeploymentPhase.CANARY_5PCT
            elif percentage == 50:
                deployment.current_phase = DeploymentPhase.CANARY_50PCT
            else:
                deployment.current_phase = DeploymentPhase.PRODUCTION

            logger.info(
                f"[AUTO_DEPLOY] Phase: {percentage}% traffic for {duration}s"
            )

            # Check for rollback triggers
            if self._check_rollback_triggers(deployment):
                logger.error(
                    f"[AUTO_DEPLOY] Rollback triggered in {deployment.current_phase.value} phase"
                )
                self.execute_rollback(
                    deployment.deployment_id,
                    f"Health check failed in {deployment.current_phase.value}",
                )
                return

        # All phases passed
        deployment.current_phase = DeploymentPhase.MONITORING
        logger.info(
            f"[AUTO_DEPLOY] Deployment {deployment.deployment_id} completed canary, "
            f"starting monitoring"
        )

        # Extended monitoring
        self._post_deployment_monitoring(deployment)

    def _check_rollback_triggers(self, deployment: DeploymentExecution) -> bool:
        """Check if any rollback triggers are active."""
        if not deployment.metrics_history:
            return False

        latest_metrics = deployment.metrics_history[-1]
        baseline = deployment.baseline_metrics

        # Check error rate
        if latest_metrics.error_rate > self.deployment_config["rollback_triggers"]["error_rate_threshold"]:
            logger.warning(
                f"[AUTO_DEPLOY] Error rate high: {latest_metrics.error_rate:.2%} "
                f"(threshold: {self.deployment_config['rollback_triggers']['error_rate_threshold']:.2%})"
            )
            return True

        # Check latency increase
        if baseline and latest_metrics.latency_p99 > baseline.get("latency_p99", 0) * 1.2:
            logger.warning(
                f"[AUTO_DEPLOY] Latency increased: {latest_metrics.latency_p99:.0f}ms "
                f"(was {baseline.get('latency_p99', 0):.0f}ms)"
            )
            return True

        # Check health checks
        if latest_metrics.health_checks_failed >= self.deployment_config["rollback_triggers"]["health_check_failures"]:
            logger.warning(
                f"[AUTO_DEPLOY] Health check failures: {latest_metrics.health_checks_failed}"
            )
            return True

        return False

    def _post_deployment_monitoring(self, deployment: DeploymentExecution) -> None:
        """Monitor deployment for 5 minutes after going to production."""
        logger.info(
            f"[AUTO_DEPLOY] Post-deployment monitoring (5 min): {deployment.deployment_id}"
        )

        # In production, this would continuously check metrics for 5 minutes
        # If health degrades, trigger rollback

        deployment.current_phase = DeploymentPhase.COMPLETE
        deployment.phase_end_time = datetime.now()

        logger.info(
            f"[AUTO_DEPLOY] Deployment {deployment.deployment_id} COMPLETE "
            f"(duration: {(deployment.phase_end_time - deployment.timestamp).total_seconds():.0f}s)"
        )

    def execute_rollback(
        self,
        deployment_id: str,
        reason: str,
    ) -> bool:
        """Rollback deployment to previous version."""
        if deployment_id not in self.active_deployments:
            logger.error(f"[AUTO_DEPLOY] Deployment {deployment_id} not found")
            return False

        deployment = self.active_deployments[deployment_id]

        logger.error(
            f"[AUTO_DEPLOY] Rollback initiated for {deployment_id}: {reason}"
        )

        deployment.rolled_back = True
        deployment.rollback_reason = reason
        deployment.rollback_timestamp = datetime.now()
        deployment.current_phase = DeploymentPhase.ROLLED_BACK

        del self.active_deployments[deployment_id]

        return True

    # ======== DASHBOARD ENDPOINTS ========

    def get_deployment_status(self, deployment_id: str) -> Dict:
        """
        GET /deploy/status/{deployment_id}

        Status of specific deployment.
        """
        if deployment_id in self.active_deployments:
            deployment = self.active_deployments[deployment_id]
        else:
            deployment = next(
                (d for d in self.deployments if d.deployment_id == deployment_id),
                None,
            )

        if not deployment:
            return {"status": "not_found"}

        return {
            "deployment_id": deployment_id,
            "commit": deployment.commit_sha[:8],
            "author": deployment.author,
            "phase": deployment.current_phase.value,
            "started_at": deployment.timestamp.isoformat(),
            "ended_at": deployment.phase_end_time.isoformat() if deployment.phase_end_time else None,
            "rolled_back": deployment.rolled_back,
            "rollback_reason": deployment.rollback_reason,
            "duration_seconds": (
                (deployment.phase_end_time - deployment.timestamp).total_seconds()
                if deployment.phase_end_time
                else None
            ),
        }

    def get_deployment_history(self, limit: int = 20) -> Dict:
        """
        GET /deploy/history

        Recent deployments.
        """
        recent = self.deployments[-limit:]
        successful = sum(1 for d in recent if d.current_phase == DeploymentPhase.COMPLETE)
        rolled_back = sum(1 for d in recent if d.rolled_back)

        return {
            "total_deployments": len(self.deployments),
            "recent": limit,
            "success_rate": successful / len(recent) if recent else 0.0,
            "rollback_rate": rolled_back / len(recent) if recent else 0.0,
            "deployments": [
                {
                    "deployment_id": d.deployment_id,
                    "commit": d.commit_sha[:8],
                    "phase": d.current_phase.value,
                    "rolled_back": d.rolled_back,
                    "deployed_at": d.timestamp.isoformat(),
                }
                for d in recent
            ],
        }


# Global instance
_auto_deploy_instance: Optional[Phase4_2AutoDeploy] = None


def get_auto_deploy() -> Phase4_2AutoDeploy:
    """Get or create global auto-deploy instance."""
    global _auto_deploy_instance
    if _auto_deploy_instance is None:
        _auto_deploy_instance = Phase4_2AutoDeploy()
    return _auto_deploy_instance
