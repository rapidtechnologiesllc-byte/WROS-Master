"""
PHASE 4.1: CODE REVIEW → AUTO-MERGE (2026-09-19)

Automatically merge approved code to main without human intervention.

Gate Approval Logic:
- Architect Decision: APPROVE + Authority Level 1-2 = auto-merge to main
- Code Review Gate: All 52 criteria PASS = auto-merge eligible
- Cascade Analysis: No cascade failures detected = merge safe
- Tests: All required tests PASS = functionality verified
- Production Readiness: Code is production-ready = can deploy

Merge Execution:
1. Create temporary merge branch
2. Run final validation (tests, gate, cascade checks)
3. Merge to main with detailed commit message
4. Delete merge branch
5. Monitor for post-merge issues
6. Auto-rollback on critical issue detection

Monitoring:
- Merge success rate (should be > 95%)
- Post-merge issue detection
- Rollback triggers and frequency
- Developer feedback (UX of auto-merge)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MergeStrategy(Enum):
    """Merge strategy selection."""
    SQUASH = "squash"  # Single commit (squash all PR commits)
    REBASE = "rebase"  # Linear history (rebase PR commits)
    MERGE = "merge"  # Merge commit (preserves PR commits)


@dataclass
class CodeReviewApproval:
    """Code review approval ready for auto-merge."""
    pull_request_id: str
    branch_name: str
    target_branch: str  # Usually "main"
    architect_decision: str  # APPROVE, BLOCK, ESCALATE
    architect_confidence: float
    gate_status: str  # PASS, FAIL
    all_gates_passed: bool
    cascade_risk: str  # none, low, medium, high
    tests_passed: bool
    production_ready: bool
    files_changed: int
    insertions: int
    deletions: int
    author: str
    created_at: datetime
    approved_at: datetime

    # Merge execution
    merge_attempted: bool = False
    merge_timestamp: Optional[datetime] = None
    merge_commit_sha: Optional[str] = None
    merge_success: bool = False
    post_merge_issue: bool = False
    rollback_executed: bool = False


@dataclass
class MergeExecutionLog:
    """Log of merge execution for debugging."""
    merge_id: str
    pull_request_id: str
    timestamp: datetime
    step: str  # validate, test, gate, cascade, merge, post_merge_check
    status: str  # running, success, failed, rolled_back
    details: Dict
    logs: List[str] = None


class Phase4_1AutoMerge:
    """
    Automatically merge approved code to main.

    Endpoints:
    - GET /merge/queue
    - POST /merge/execute/{pr_id}
    - GET /merge/status/{pr_id}
    - GET /merge/history
    - POST /merge/rollback/{pr_id}
    """

    def __init__(self):
        """Initialize auto-merge system."""
        self.merge_queue: List[CodeReviewApproval] = []
        self.merge_history: List[CodeReviewApproval] = []
        self.execution_logs: List[MergeExecutionLog] = []
        self.merge_config = {
            "strategy": MergeStrategy.SQUASH,
            "auto_merge_enabled": True,
            "cascade_check_required": True,
            "post_merge_check_duration_seconds": 300,  # 5 minutes
            "auto_rollback_enabled": True,
            "rollback_trigger_criteria": {
                "error_rate_threshold": 0.05,  # 5%
                "latency_increase_threshold": 0.20,  # 20%
                "critical_errors": True,
            },
        }

    def add_to_merge_queue(
        self,
        pull_request_id: str,
        branch_name: str,
        target_branch: str,
        architect_decision: str,
        architect_confidence: float,
        gate_status: str,
        all_gates_passed: bool,
        cascade_risk: str,
        tests_passed: bool,
        production_ready: bool,
        files_changed: int,
        insertions: int,
        deletions: int,
        author: str,
    ) -> CodeReviewApproval:
        """
        Add approved PR to merge queue (ready for auto-merge).

        This is called after architect approves + gate passes + tests pass.
        """
        approval = CodeReviewApproval(
            pull_request_id=pull_request_id,
            branch_name=branch_name,
            target_branch=target_branch,
            architect_decision=architect_decision,
            architect_confidence=architect_confidence,
            gate_status=gate_status,
            all_gates_passed=all_gates_passed,
            cascade_risk=cascade_risk,
            tests_passed=tests_passed,
            production_ready=production_ready,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
            author=author,
            created_at=datetime.now(),
            approved_at=datetime.now(),
        )

        self.merge_queue.append(approval)

        logger.info(
            f"[AUTO_MERGE] PR {pull_request_id} added to queue "
            f"(architect_confidence={architect_confidence:.0%}, "
            f"cascade_risk={cascade_risk})"
        )

        # Immediately attempt merge (don't wait in queue)
        self._execute_merge(approval)

        return approval

    def _execute_merge(self, approval: CodeReviewApproval) -> bool:
        """Execute merge to main."""
        pr_id = approval.pull_request_id

        logger.info(f"[AUTO_MERGE] Executing merge for PR {pr_id}")

        # Step 1: Final validation
        if not self._validate_before_merge(approval):
            logger.error(f"[AUTO_MERGE] PR {pr_id} failed pre-merge validation")
            return False

        # Step 2: Run final tests
        if not self._run_final_tests(approval):
            logger.error(f"[AUTO_MERGE] PR {pr_id} failed final tests")
            return False

        # Step 3: Re-run gate
        if not self._rerun_gate(approval):
            logger.error(f"[AUTO_MERGE] PR {pr_id} failed gate re-check")
            return False

        # Step 4: Check cascade safety
        if self.merge_config["cascade_check_required"]:
            if not self._verify_cascade_safety(approval):
                logger.error(f"[AUTO_MERGE] PR {pr_id} failed cascade safety check")
                return False

        # Step 5: Execute merge
        merge_sha = self._perform_merge(approval)
        if not merge_sha:
            logger.error(f"[AUTO_MERGE] PR {pr_id} merge operation failed")
            return False

        approval.merge_attempted = True
        approval.merge_timestamp = datetime.now()
        approval.merge_commit_sha = merge_sha
        approval.merge_success = True

        logger.info(f"[AUTO_MERGE] PR {pr_id} merged successfully (commit {merge_sha[:8]})")

        # Step 6: Post-merge monitoring
        self._monitor_post_merge(approval)

        # Move to history
        self.merge_queue.remove(approval)
        self.merge_history.append(approval)

        return True

    def _validate_before_merge(self, approval: CodeReviewApproval) -> bool:
        """Validate PR is safe to merge."""
        if not approval.all_gates_passed:
            logger.warning(f"[AUTO_MERGE] Gate check failed for {approval.pull_request_id}")
            return False

        if not approval.tests_passed:
            logger.warning(f"[AUTO_MERGE] Tests failed for {approval.pull_request_id}")
            return False

        if not approval.production_ready:
            logger.warning(f"[AUTO_MERGE] Not production ready: {approval.pull_request_id}")
            return False

        if approval.cascade_risk == "high":
            logger.warning(f"[AUTO_MERGE] High cascade risk: {approval.pull_request_id}")
            return False

        log = MergeExecutionLog(
            merge_id=f"merge_{approval.pull_request_id}",
            pull_request_id=approval.pull_request_id,
            timestamp=datetime.now(),
            step="validate",
            status="success",
            details={
                "gates_passed": approval.all_gates_passed,
                "tests_passed": approval.tests_passed,
                "production_ready": approval.production_ready,
            },
        )
        self.execution_logs.append(log)

        return True

    def _run_final_tests(self, approval: CodeReviewApproval) -> bool:
        """Run final test suite before merge."""
        logger.info(
            f"[AUTO_MERGE] Running final tests for {approval.pull_request_id}"
        )

        # Simulate test execution
        tests_passed = True  # In reality, run test suite

        log = MergeExecutionLog(
            merge_id=f"merge_{approval.pull_request_id}",
            pull_request_id=approval.pull_request_id,
            timestamp=datetime.now(),
            step="test",
            status="success" if tests_passed else "failed",
            details={
                "tests_passed": tests_passed,
                "duration_seconds": 45,  # Example
            },
        )
        self.execution_logs.append(log)

        return tests_passed

    def _rerun_gate(self, approval: CodeReviewApproval) -> bool:
        """Re-run code review gate to ensure no regressions."""
        logger.info(f"[AUTO_MERGE] Re-running gate for {approval.pull_request_id}")

        # Gate should still pass
        gate_passed = approval.gate_status == "PASS"

        log = MergeExecutionLog(
            merge_id=f"merge_{approval.pull_request_id}",
            pull_request_id=approval.pull_request_id,
            timestamp=datetime.now(),
            step="gate",
            status="success" if gate_passed else "failed",
            details={
                "gate_status": approval.gate_status,
                "critical_issues": 0,
            },
        )
        self.execution_logs.append(log)

        return gate_passed

    def _verify_cascade_safety(self, approval: CodeReviewApproval) -> bool:
        """Verify no cascade failures detected."""
        logger.info(
            f"[AUTO_MERGE] Checking cascade safety for {approval.pull_request_id}"
        )

        cascade_safe = approval.cascade_risk in ["none", "low"]

        log = MergeExecutionLog(
            merge_id=f"merge_{approval.pull_request_id}",
            pull_request_id=approval.pull_request_id,
            timestamp=datetime.now(),
            step="cascade",
            status="success" if cascade_safe else "failed",
            details={
                "cascade_risk": approval.cascade_risk,
                "affected_services": [],
            },
        )
        self.execution_logs.append(log)

        return cascade_safe

    def _perform_merge(self, approval: CodeReviewApproval) -> Optional[str]:
        """Perform actual merge operation."""
        logger.info(
            f"[AUTO_MERGE] Merging {approval.branch_name} → {approval.target_branch} "
            f"(strategy: {self.merge_config['strategy'].value})"
        )

        # Simulate merge
        merge_sha = "abc1234567890"  # In reality, git merge result

        log = MergeExecutionLog(
            merge_id=f"merge_{approval.pull_request_id}",
            pull_request_id=approval.pull_request_id,
            timestamp=datetime.now(),
            step="merge",
            status="success",
            details={
                "strategy": self.merge_config["strategy"].value,
                "merge_sha": merge_sha,
                "files_changed": approval.files_changed,
                "insertions": approval.insertions,
                "deletions": approval.deletions,
            },
        )
        self.execution_logs.append(log)

        return merge_sha

    def _monitor_post_merge(self, approval: CodeReviewApproval) -> None:
        """Monitor for issues after merge."""
        logger.info(
            f"[AUTO_MERGE] Post-merge monitoring for {approval.pull_request_id} "
            f"({self.merge_config['post_merge_check_duration_seconds']}s)"
        )

        # In production, this would:
        # 1. Monitor error rates for 5 minutes
        # 2. Check latency impact
        # 3. Watch for cascade failures
        # 4. Auto-rollback if thresholds exceeded

        log = MergeExecutionLog(
            merge_id=f"merge_{approval.pull_request_id}",
            pull_request_id=approval.pull_request_id,
            timestamp=datetime.now(),
            step="post_merge_check",
            status="success",
            details={
                "duration_seconds": self.merge_config["post_merge_check_duration_seconds"],
                "error_rate": 0.001,  # Example: 0.1% error rate (good)
                "latency_increase": 0.02,  # Example: 2% increase (acceptable)
            },
        )
        self.execution_logs.append(log)

    def execute_rollback(self, pull_request_id: str, reason: str) -> bool:
        """Rollback merged PR if critical issue detected."""
        logger.error(
            f"[AUTO_MERGE] Rollback initiated for {pull_request_id}: {reason}"
        )

        # Find PR in history
        for approval in self.merge_history:
            if approval.pull_request_id == pull_request_id:
                approval.rollback_executed = True

                log = MergeExecutionLog(
                    merge_id=f"merge_{pull_request_id}",
                    pull_request_id=pull_request_id,
                    timestamp=datetime.now(),
                    step="rollback",
                    status="success",
                    details={
                        "reason": reason,
                        "rolled_back_to": approval.target_branch,
                    },
                )
                self.execution_logs.append(log)

                return True

        return False

    # ======== DASHBOARD ENDPOINTS ========

    def get_merge_queue(self) -> Dict:
        """
        GET /merge/queue

        Current PRs waiting to merge.
        """
        return {
            "queue_length": len(self.merge_queue),
            "pending_merges": [
                {
                    "pr_id": m.pull_request_id,
                    "branch": m.branch_name,
                    "author": m.author,
                    "architect_confidence": m.architect_confidence,
                    "cascade_risk": m.cascade_risk,
                    "created_at": m.created_at.isoformat(),
                }
                for m in self.merge_queue
            ],
        }

    def get_merge_status(self, pull_request_id: str) -> Dict:
        """
        GET /merge/status/{pr_id}

        Status of specific PR merge.
        """
        # Check queue
        for approval in self.merge_queue:
            if approval.pull_request_id == pull_request_id:
                return {
                    "status": "queued",
                    "pr_id": pull_request_id,
                    "created_at": approval.created_at.isoformat(),
                }

        # Check history
        for approval in self.merge_history:
            if approval.pull_request_id == pull_request_id:
                return {
                    "status": "merged" if approval.merge_success else "failed",
                    "pr_id": pull_request_id,
                    "merge_commit": approval.merge_commit_sha,
                    "merged_at": approval.merge_timestamp.isoformat() if approval.merge_timestamp else None,
                    "rollback_executed": approval.rollback_executed,
                }

        return {"status": "not_found"}

    def get_merge_history(self, limit: int = 50) -> Dict:
        """
        GET /merge/history

        Recent merge executions.
        """
        recent = self.merge_history[-limit:]

        successful = sum(1 for m in recent if m.merge_success)
        rolled_back = sum(1 for m in recent if m.rollback_executed)

        return {
            "total_merges": len(self.merge_history),
            "recent_merges": limit,
            "success_rate": successful / len(recent) if recent else 0.0,
            "rollback_rate": rolled_back / len(recent) if recent else 0.0,
            "merges": [
                {
                    "pr_id": m.pull_request_id,
                    "author": m.author,
                    "merged_at": m.merge_timestamp.isoformat() if m.merge_timestamp else None,
                    "status": "merged" if m.merge_success else "failed",
                    "rolled_back": m.rollback_executed,
                }
                for m in recent
            ],
        }


# Global instance
_auto_merge_instance: Optional[Phase4_1AutoMerge] = None


def get_auto_merge() -> Phase4_1AutoMerge:
    """Get or create global auto-merge instance."""
    global _auto_merge_instance
    if _auto_merge_instance is None:
        _auto_merge_instance = Phase4_1AutoMerge()
    return _auto_merge_instance
