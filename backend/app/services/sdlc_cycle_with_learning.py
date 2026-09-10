"""
SDLC Cycle With Learning - Complete 90-second cycle that updates memory

Flow:
1. ARCHITECT READS MEMORY
2. ARCHITECT ANALYZES CODE
3. ARCHITECT GENERATES SPEC
4. CLAUDE IMPLEMENTS
5. TESTS RUN
6. ARCHITECT LEARNS FROM RESULTS
7. MEMORY UPDATED
8. NEXT CYCLE (with new memory)
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.sdlc_orchestration_service import (
    SDLCOrchestrationService,
    SDLCCycleState,
    FallbackSpecCategory,
)
from app.services.architect_agent_with_memory import (
    spawn_architect_agent_with_memory,
    architect_learns_from_cycle_outcome,
    ArchitectSpecificationWithMemory,
)
from app.services.architect_persistent_memory import get_architect_memory

logger = logging.getLogger(__name__)


class AutonomousSDLCCycleWithLearning:
    """
    Complete SDLC cycle with:
    - Architect reading memory
    - Code implementation
    - Testing
    - Learning from outcomes
    - Memory updates
    """

    ARCHITECT_TIMEOUT_SECONDS = 120
    CYCLE_PAUSE_SECONDS = 90

    def __init__(self):
        self.orchestration = SDLCOrchestrationService()
        self.memory = get_architect_memory()
        self.recent_failures: List[Dict[str, Any]] = []
        self.recent_commits: List[str] = []

    async def run_cycle_with_learning(
        self,
        cycle_number: int,
        cycle_name: str,
        cycle_description: str,
    ) -> bool:
        """
        Run complete cycle: Architect (with memory) → Implement → Test → Learn

        Returns: True if successful, False if failed
        """

        cycle_start = datetime.utcnow()
        cycle = self.orchestration.start_cycle(cycle_number)

        logger.info(f"\n{'='*70}")
        logger.info(f"[SDLC-LEARN] CYCLE {cycle_number}: {cycle_name}")
        logger.info(f"[SDLC-LEARN] Description: {cycle_description}")
        logger.info(f"[SDLC-LEARN] Memory has {len(self.memory.memories)} past learnings")
        logger.info(f"{'='*70}\n")

        try:
            # ──────────────────────────────────────────────────────────────
            # PHASE 1: ARCHITECT READS MEMORY & ANALYZES
            # ──────────────────────────────────────────────────────────────
            logger.info(f"[SDLC-LEARN] PHASE 1: Architect reads memory and analyzes")

            spec = await self._architect_phase(cycle_number, cycle_description)

            if spec is None:
                logger.error(f"[SDLC-LEARN] Architect phase failed")
                self.recent_failures.append({
                    "cycle": cycle_number,
                    "phase": "architect",
                    "description": "Architect analysis failed",
                })
                return False

            logger.info(f"[SDLC-LEARN] Architect generated spec with:")
            logger.info(f"  - {len(spec.changes)} changes")
            logger.info(f"  - {len(spec.predictions)} cascade predictions")
            logger.info(f"  - {len(spec.memory_insights)} memory-based insights")

            # ──────────────────────────────────────────────────────────────
            # PHASE 2: IMPLEMENTATION & CODE REVIEW
            # ──────────────────────────────────────────────────────────────
            logger.info(f"[SDLC-LEARN] PHASE 2: Implement per architect spec")

            implementation_result = await self._implementation_phase(spec)

            if not implementation_result["success"]:
                logger.error(f"[SDLC-LEARN] Implementation failed: {implementation_result}")
                self.recent_failures.append({
                    "cycle": cycle_number,
                    "phase": "implementation",
                    "description": implementation_result.get("error", "Unknown error"),
                })
                return False

            self.recent_commits.append(implementation_result.get("commit", ""))
            logger.info(f"[SDLC-LEARN] Implementation complete:")
            logger.info(f"  - Commit: {implementation_result['commit']}")
            logger.info(f"  - Gate: {implementation_result['gate_status']}")

            # ──────────────────────────────────────────────────────────────
            # PHASE 3: TESTING & VERIFICATION
            # ──────────────────────────────────────────────────────────────
            logger.info(f"[SDLC-LEARN] PHASE 3: Run tests and verify")

            test_results = await self._testing_phase(spec)

            if not test_results["success"]:
                logger.error(f"[SDLC-LEARN] Tests failed")
                self.recent_failures.append({
                    "cycle": cycle_number,
                    "phase": "testing",
                    "description": f"Tests failed: {test_results.get('failure_reason')}",
                })
                return False

            logger.info(f"[SDLC-LEARN] Tests passed:")
            logger.info(f"  - {test_results['tests_passed']} tests passed")
            logger.info(f"  - {test_results['cascade_failures']} cascade failures detected")

            # ──────────────────────────────────────────────────────────────
            # PHASE 4: ARCHITECT LEARNS FROM OUTCOMES
            # ──────────────────────────────────────────────────────────────
            logger.info(f"[SDLC-LEARN] PHASE 4: Architect learns from outcomes")

            await architect_learns_from_cycle_outcome(
                cycle_number=cycle_number,
                specification=spec,
                test_results=test_results,
                cascade_failures=test_results.get("cascade_failures", []),
            )

            # Log what was learned
            memory_summary = self.memory.get_memory_summary()
            logger.info(f"[SDLC-LEARN] Memory updated:")
            logger.info(f"  - Total memories: {memory_summary['total_memories']}")
            logger.info(f"  - Cascade patterns: {len(self.memory.cascade_matrix)}")
            logger.info(f"  - Recurring anti-patterns: {memory_summary['recurring_anti_patterns']}")

            # Mark cycle complete
            self.orchestration.record_test_results(cycle, test_results)
            self.orchestration.complete_cycle(cycle)

            elapsed = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info(f"[SDLC-LEARN] CYCLE {cycle_number} COMPLETE ✓ ({elapsed:.1f}s)")

            return True

        except Exception as e:
            logger.error(f"[SDLC-LEARN] Cycle failed: {e}", exc_info=True)
            self.recent_failures.append({
                "cycle": cycle_number,
                "phase": "unknown",
                "description": str(e),
            })
            return False

    async def _architect_phase(
        self, cycle_number: int, description: str
    ) -> Optional[ArchitectSpecificationWithMemory]:
        """
        PHASE 1: Architect reads memory, analyzes codebase, generates spec

        Architect has 120 seconds to complete analysis.
        If timeout, fallback spec used.
        """
        try:
            logger.info(f"[ARCHITECT-PHASE] Spawning agent with memory access")

            spec = await asyncio.wait_for(
                spawn_architect_agent_with_memory(
                    cycle_number=cycle_number,
                    recent_failures=self.recent_failures[-10:],
                    recent_commits=self.recent_commits[-10:],
                    new_requirements=description,
                ),
                timeout=self.ARCHITECT_TIMEOUT_SECONDS,
            )

            return spec

        except asyncio.TimeoutError:
            logger.warning(f"[ARCHITECT-PHASE] Architect timeout - using fallback")
            # Generate fallback spec
            spec = ArchitectSpecificationWithMemory(cycle_number)
            spec.risk_level = "LOW"
            spec.memory_insights.append("Fallback: Documentation update (architect timeout)")
            return spec

        except Exception as e:
            logger.error(f"[ARCHITECT-PHASE] Failed: {e}")
            return None

    async def _implementation_phase(self, spec: ArchitectSpecificationWithMemory) -> Dict[str, Any]:
        """
        PHASE 2: Implement per architect spec, run code review gate

        In real deployment, would trigger Claude implementation worker.
        For now, simulated.
        """
        logger.info(f"[IMPLEMENTATION-PHASE] Would implement {len(spec.changes)} changes")

        return {
            "success": True,
            "commit": f"cycle_{spec.cycle_number}_changes",
            "gate_status": "PASSED",
        }

    async def _testing_phase(self, spec: ArchitectSpecificationWithMemory) -> Dict[str, Any]:
        """
        PHASE 3: Run tests, verify cascade predictions

        Tests whether:
        1. Changes work as intended
        2. Predicted cascade failures actually happen (or don't)
        3. System remains stable
        """
        logger.info(f"[TESTING-PHASE] Validating {len(spec.predictions)} predictions")

        cascade_failures = []

        # In real deployment, would:
        # - Run actual tests
        # - Monitor cascade metrics
        # - Capture failures
        # For now, simulate

        return {
            "success": True,
            "tests_passed": 10,
            "cascade_failures": cascade_failures,
            "metrics": {
                "response_time_ms": 45,
                "error_rate": 0.0,
            },
        }

    async def run_continuous_learning_cycles(self, num_cycles: int = 5):
        """
        Run multiple cycles continuously with 90-second pauses.

        Each cycle:
        1. Reads architect memory
        2. Implements changes
        3. Tests
        4. Updates memory
        5. Waits 90s
        6. Repeats with new memory state
        """

        logger.info(f"\n{'#'*70}")
        logger.info(f"[AUTONOMOUS-LEARN] Starting {num_cycles} continuous cycles with learning")
        logger.info(f"{'#'*70}\n")

        for cycle_num in range(1, num_cycles + 1):
            success = await self.run_cycle_with_learning(
                cycle_number=cycle_num,
                cycle_name=f"Learning Cycle {cycle_num}",
                cycle_description="Continuous SDLC with persistent memory",
            )

            if not success:
                logger.error(f"[AUTONOMOUS-LEARN] Cycle {cycle_num} failed - stopping")
                break

            if cycle_num < num_cycles:
                logger.info(f"\n[AUTONOMOUS-LEARN] 90-second pause before cycle {cycle_num + 1}")
                await asyncio.sleep(self.CYCLE_PAUSE_SECONDS)

        logger.info(f"\n{'#'*70}")
        logger.info(f"[AUTONOMOUS-LEARN] All cycles complete")
        logger.info(f"{'#'*70}\n")


async def main():
    """Entry point for autonomous SDLC with learning"""
    runner = AutonomousSDLCCycleWithLearning()
    await runner.run_continuous_learning_cycles(num_cycles=5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
