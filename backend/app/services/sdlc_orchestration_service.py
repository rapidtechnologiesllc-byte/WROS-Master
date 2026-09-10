"""
SDLC Orchestration Service - Autonomous 90-second cycle automation

Manages the Spartan SDLC cycle without blocking on architect responses.
Implements fallback spec generation when architect agent times out.

Flow:
1. Request architect spec for CYCLE N
2. Wait up to 120 seconds for response
3. If timeout → activate fallback spec, continue
4. Execute CYCLE N (development → test → commit)
5. Schedule CYCLE N+1 after 90-second pause
6. Repeat
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class CycleStatus(Enum):
    """SDLC cycle execution status."""
    PENDING = "pending"
    ARCHITECT_SPEC_REQUESTED = "architect_spec_requested"
    ARCHITECT_SPEC_RECEIVED = "architect_spec_received"
    ARCHITECT_SPEC_TIMEOUT = "architect_spec_timeout"
    FALLBACK_SPEC_GENERATED = "fallback_spec_generated"
    DEVELOPMENT_IN_PROGRESS = "development_in_progress"
    GATE_REVIEW = "gate_review"
    GATE_PASSED = "gate_passed"
    GATE_FAILED = "gate_failed"
    COMMITTED = "committed"
    TESTING = "testing"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class FallbackSpecCategory(Enum):
    """Safe fallback change categories (no architect needed)."""
    DOCUMENTATION = "documentation"
    CODE_STYLE = "code_style"
    SIMPLE_REFACTOR = "simple_refactor"
    TEST_ADDITIONS = "test_additions"
    GATE_CLEARANCE = "gate_clearance"  # Fix known violations


class SDLCCycleState:
    """Tracks state of current SDLC cycle."""

    def __init__(self, cycle_number: int):
        self.cycle_number = cycle_number
        self.status = CycleStatus.PENDING
        self.architect_spec_requested_at: Optional[datetime] = None
        self.architect_spec_received_at: Optional[datetime] = None
        self.architect_spec: Optional[Dict[str, Any]] = None
        self.fallback_spec: Optional[Dict[str, Any]] = None
        self.using_fallback = False
        self.development_completed_at: Optional[datetime] = None
        self.gate_status: Optional[str] = None
        self.commits: List[str] = []
        self.test_results: Optional[Dict[str, Any]] = None
        self.rolled_back = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize cycle state to dict."""
        return {
            "cycle_number": self.cycle_number,
            "status": self.status.value,
            "architect_spec_requested_at": self.architect_spec_requested_at.isoformat() if self.architect_spec_requested_at else None,
            "architect_spec_received_at": self.architect_spec_received_at.isoformat() if self.architect_spec_received_at else None,
            "using_fallback": self.using_fallback,
            "commits": self.commits,
            "gate_status": self.gate_status,
        }


class SDLCOrchestrationService:
    """
    Orchestrates autonomous SDLC cycles with architect timeout fallback.

    Key behaviors:
    - Never blocks development on architect response > 120 seconds
    - Generates fallback spec when architect times out
    - Continues 90-second cycle even if architect delayed
    - Tracks all cycle state for audit trail
    """

    ARCHITECT_RESPONSE_TIMEOUT_SECONDS = 120
    CYCLE_PAUSE_SECONDS = 90

    FALLBACK_SPECS = {
        FallbackSpecCategory.DOCUMENTATION: {
            "description": "Update documentation, comments, docstrings",
            "safe": True,
            "examples": [
                "Update CLAUDE.md with cycle results",
                "Add inline code comments",
                "Update module docstrings",
            ]
        },
        FallbackSpecCategory.CODE_STYLE: {
            "description": "Code formatting, naming, style improvements",
            "safe": True,
            "examples": [
                "Fix PEP8 violations",
                "Rename variables for clarity",
                "Remove unused imports",
            ]
        },
        FallbackSpecCategory.SIMPLE_REFACTOR: {
            "description": "Simple refactoring with no logic changes",
            "safe": True,
            "examples": [
                "Extract method (no logic change)",
                "Combine similar functions",
                "Simplify nested conditions",
            ]
        },
        FallbackSpecCategory.TEST_ADDITIONS: {
            "description": "Add tests for existing code paths",
            "safe": True,
            "examples": [
                "Add unit tests for existing functions",
                "Add integration tests",
                "Improve test coverage",
            ]
        },
        FallbackSpecCategory.GATE_CLEARANCE: {
            "description": "Fix known gate violations",
            "safe": True,
            "examples": [
                "Fix missing error handlers",
                "Add missing permissions checks",
                "Remove silent failures",
            ]
        },
    }

    def __init__(self):
        self.current_cycle: Optional[SDLCCycleState] = None
        self.cycle_history: List[SDLCCycleState] = []

    def start_cycle(self, cycle_number: int) -> SDLCCycleState:
        """Initialize new SDLC cycle."""
        cycle = SDLCCycleState(cycle_number)
        self.current_cycle = cycle
        logger.info(f"[SDLC] Starting CYCLE {cycle_number}")
        return cycle

    def request_architect_spec(self, cycle: SDLCCycleState, requirement: str) -> None:
        """
        Request architect specification for cycle.

        Sets 120-second timeout - if spec not received by then, activate fallback.
        """
        cycle.architect_spec_requested_at = datetime.utcnow()
        cycle.status = CycleStatus.ARCHITECT_SPEC_REQUESTED
        logger.info(f"[SDLC] CYCLE {cycle.cycle_number}: Requesting architect spec")
        logger.info(f"[SDLC] Timeout: {self.ARCHITECT_RESPONSE_TIMEOUT_SECONDS}s")
        logger.info(f"[SDLC] Requirement: {requirement}")

    def receive_architect_spec(self, cycle: SDLCCycleState, spec: Dict[str, Any]) -> None:
        """Record architect specification received."""
        cycle.architect_spec_received_at = datetime.utcnow()
        cycle.architect_spec = spec
        cycle.status = CycleStatus.ARCHITECT_SPEC_RECEIVED
        delay = (cycle.architect_spec_received_at - cycle.architect_spec_requested_at).total_seconds()
        logger.info(f"[SDLC] CYCLE {cycle.cycle_number}: Architect spec received in {delay:.1f}s")

    def check_architect_timeout(self, cycle: SDLCCycleState) -> bool:
        """Check if architect response timeout exceeded."""
        if not cycle.architect_spec_requested_at:
            return False
        elapsed = (datetime.utcnow() - cycle.architect_spec_requested_at).total_seconds()
        return elapsed > self.ARCHITECT_RESPONSE_TIMEOUT_SECONDS

    def generate_fallback_spec(self, cycle: SDLCCycleState, category: FallbackSpecCategory) -> Dict[str, Any]:
        """
        Generate fallback spec when architect times out.

        Fallback specs are safe, low-risk changes that don't require architecture input.
        """
        # Calculate timeout_at if architect was requested, otherwise use now
        if cycle.architect_spec_requested_at:
            timeout_at = (cycle.architect_spec_requested_at + timedelta(seconds=self.ARCHITECT_RESPONSE_TIMEOUT_SECONDS)).isoformat()
        else:
            timeout_at = datetime.utcnow().isoformat()

        spec = {
            "cycle": cycle.cycle_number,
            "status": "FALLBACK",
            "generated_at": datetime.utcnow().isoformat(),
            "timeout_at": timeout_at,
            "category": category.value,
            "details": self.FALLBACK_SPECS[category],
            "note": "Architect spec pending - executing under fallback protocol"
        }
        cycle.fallback_spec = spec
        cycle.using_fallback = True
        cycle.status = CycleStatus.FALLBACK_SPEC_GENERATED
        logger.warning(f"[SDLC] CYCLE {cycle.cycle_number}: Architect timeout - activated {category.value} fallback")
        return spec

    def record_development_complete(self, cycle: SDLCCycleState) -> None:
        """Record when development phase completes."""
        cycle.development_completed_at = datetime.utcnow()
        cycle.status = CycleStatus.DEVELOPMENT_IN_PROGRESS

    def record_gate_result(self, cycle: SDLCCycleState, passed: bool, details: str = "") -> None:
        """Record code review gate result."""
        cycle.gate_status = "PASSED" if passed else "FAILED"
        cycle.status = CycleStatus.GATE_PASSED if passed else CycleStatus.GATE_FAILED
        logger.info(f"[SDLC] CYCLE {cycle.cycle_number}: Gate {cycle.gate_status}")
        if details:
            logger.info(f"[SDLC] Gate details: {details}")

    def record_commit(self, cycle: SDLCCycleState, commit_hash: str, message: str) -> None:
        """Record successful commit."""
        cycle.commits.append(commit_hash)
        logger.info(f"[SDLC] CYCLE {cycle.cycle_number}: Committed {commit_hash}")
        logger.info(f"[SDLC] Message: {message}")

    def record_test_results(self, cycle: SDLCCycleState, results: Dict[str, Any]) -> None:
        """Record end-to-end test results."""
        cycle.test_results = results
        cycle.status = CycleStatus.COMPLETED
        logger.info(f"[SDLC] CYCLE {cycle.cycle_number}: Tests completed")
        logger.info(f"[SDLC] Results: {json.dumps(results, indent=2)}")

    def complete_cycle(self, cycle: SDLCCycleState) -> None:
        """Mark cycle as complete and add to history."""
        self.cycle_history.append(cycle)
        logger.info(f"[SDLC] CYCLE {cycle.cycle_number}: COMPLETE")
        logger.info(f"[SDLC] Status: {cycle.to_dict()}")

    def get_next_cycle_number(self) -> int:
        """Get next cycle number."""
        return (self.current_cycle.cycle_number + 1) if self.current_cycle else 1

    def get_cycle_summary(self) -> Dict[str, Any]:
        """Get summary of all completed cycles."""
        return {
            "total_cycles": len(self.cycle_history),
            "cycles": [c.to_dict() for c in self.cycle_history],
            "current_cycle": self.current_cycle.cycle_number if self.current_cycle else None,
        }


# Global singleton instance
_orchestration = SDLCOrchestrationService()


def get_orchestration_service() -> SDLCOrchestrationService:
    """Get global SDLC orchestration service."""
    return _orchestration
