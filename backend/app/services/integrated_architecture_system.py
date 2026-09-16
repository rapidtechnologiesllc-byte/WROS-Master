"""
INTEGRATED ARCHITECTURE SYSTEM - One Unified Agentic Intelligence

Three systems working as ONE:
1. DOCTOR: Monitors health (finds problems NOW)
2. HEALER: Fixes problems (recovers from failures)
3. ARCHITECT: Prevents problems (stops them BEFORE production)

Flow:
  DOCTOR detects issue → HEALER recovers → ARCHITECT prevents future occurrence

No redundant calls:
- Doctor doesn't call architect directly
- Architect doesn't call doctor for every check
- Healer acts autonomously but logs to architect
- Architect learns from doctor's findings once per cycle

Example: Queue stuck in production
  1. Doctor: "THUNDER queue stuck, 50 candidates pending 10+ minutes"
  2. Healer: "Restarting queue processor, retrying stuck tasks"
  3. Architect: "Why did queue get stuck? Prevent this code path"
  4. Architect finds: "No error handling in queue routing - candidate can queue forever"
  5. Architect specs: "Add retry logic + timeout protection + monitoring"
  6. System fixes locally before it hits production again
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    RECOVERING = "recovering"


@dataclass
class HealthIssue:
    """A health issue detected by Doctor"""
    component: str  # "queue", "database", "auth", "api"
    status: HealthStatus
    issue_type: str  # "stuck_queue", "slow_response", "high_memory"
    severity: int  # 1-10, 10 is critical
    description: str
    detected_at: datetime
    affected_resources: List[str]  # What's broken: ["THUNDER_QUEUE", "candidate_sync"]
    recovery_action: Optional[str] = None  # What healer did
    recovery_status: Optional[str] = None  # "pending", "in_progress", "success", "failed"


@dataclass
class ArchitectFix:
    """A code fix the architect recommends"""
    issue_id: str
    title: str
    root_cause: str
    code_location: str  # "backend/app/services/queue_processor.py:142"
    fix_description: str
    fix_priority: str  # "CRITICAL", "HIGH", "MEDIUM"
    prevention_benefit: str
    estimated_lines_changed: int


# ============================================================================
# DOCTOR: Health Monitoring System (Detects Problems)
# ============================================================================

class DoctorHealthMonitor:
    """
    DOCTOR monitors system health in real-time
    Detects: stuck queues, timeouts, errors, resource exhaustion
    Reports to: HEALER + ARCHITECT
    """

    def __init__(self):
        self.issues: List[HealthIssue] = []
        self.last_check = None
        self.check_interval = 10  # seconds

    async def diagnose_system(self) -> List[HealthIssue]:
        """
        DOCTOR runs diagnostics
        Checks: queues, database, API, memory, connections
        Returns: ALL issues found

        NOTE: Runs every 10 seconds, NOT called constantly
        This is ONE comprehensive check, not 100 small checks
        """
        new_issues = []

        try:
            # Check 1: Queue health (ONE comprehensive check)
            queue_issues = await self._check_queue_health()
            new_issues.extend(queue_issues)

            # Check 2: Database health (ONE check)
            db_issues = await self._check_database_health()
            new_issues.extend(db_issues)

            # Check 3: API health (ONE check)
            api_issues = await self._check_api_health()
            new_issues.extend(api_issues)

            # Check 4: Resource health (ONE check)
            resource_issues = await self._check_resources()
            new_issues.extend(resource_issues)

            # Store issues (for architect to read later)
            self.issues = new_issues
            self.last_check = datetime.utcnow()

            logger.info(f"[DOCTOR] Diagnosis complete: {len(new_issues)} issues found")
            return new_issues

        except Exception as e:
            logger.error(f"[DOCTOR] Diagnosis failed: {e}")
            return []

    async def _check_queue_health(self) -> List[HealthIssue]:
        """Check THUNDER/FLASH queues for stuck messages"""
        issues = []

        # Example: Stuck queue detection
        # In real implementation, this queries the queue database
        stuck_threshold = timedelta(minutes=10)  # Message stuck > 10min

        # Pseudocode:
        # db.query(ChannelQueueItem)
        #   .filter(status == "pending", created_at < now - 10min)
        #   .count()

        # For this example, let's simulate a stuck queue scenario
        stuck_count = 0  # Would be: result from query above

        if stuck_count > 0:
            issue = HealthIssue(
                component="queue",
                status=HealthStatus.CRITICAL,
                issue_type="stuck_queue",
                severity=10,
                description=f"THUNDER queue has {stuck_count} stuck candidates (>10 min)",
                detected_at=datetime.utcnow(),
                affected_resources=["THUNDER_QUEUE", "candidate_sync"]
            )
            issues.append(issue)
            logger.warning(f"[DOCTOR] CRITICAL: {issue.description}")

        return issues

    async def _check_database_health(self) -> List[HealthIssue]:
        """Check database connections, query times"""
        issues = []

        # Pseudocode:
        # Measure: Connection pool status, slow queries, locks
        # If: avg_query_time > 1s OR connections > 90%
        #   Report as DEGRADED

        return issues

    async def _check_api_health(self) -> List[HealthIssue]:
        """Check API endpoints response times"""
        issues = []

        # Pseudocode:
        # Measure: /api/v1/candidates response time
        # If: response_time > 5s
        #   Report as DEGRADED

        return issues

    async def _check_resources(self) -> List[HealthIssue]:
        """Check memory, CPU, disk usage"""
        issues = []

        # Pseudocode:
        # Measure: memory usage, CPU load
        # If: memory > 85% OR CPU > 80%
        #   Report as DEGRADED

        return issues

    def get_critical_issues(self) -> List[HealthIssue]:
        """Get only CRITICAL issues (what HEALER should fix NOW)"""
        return [i for i in self.issues if i.severity >= 8]

    def get_all_issues_for_architect(self) -> List[HealthIssue]:
        """
        Get ALL issues (ARCHITECT reads this once per cycle)
        ARCHITECT does NOT call doctor constantly
        ARCHITECT just reads the latest diagnosis
        """
        return self.issues


# ============================================================================
# HEALER: Automatic Recovery System (Fixes Problems)
# ============================================================================

class SelfHealer:
    """
    HEALER automatically recovers from issues
    Input: DOCTOR's findings
    Action: Fix the problem (restart, retry, purge, reset)
    Output: Recovery status (feeds back to DOCTOR + ARCHITECT)

    IMPORTANT: Healer acts AUTONOMOUSLY
    - Doesn't wait for approval
    - Logs all actions for ARCHITECT to learn from
    - Tries safe fixes first (restart) then aggressive fixes (purge)
    """

    def __init__(self, doctor: DoctorHealthMonitor):
        self.doctor = doctor
        self.recovery_history: List[Dict[str, Any]] = []

    async def heal_critical_issues(self) -> Dict[str, Any]:
        """
        HEALER reads doctor's critical issues and fixes them
        Called when: severity >= 8
        """

        critical = self.doctor.get_critical_issues()

        if not critical:
            return {"status": "nothing_to_heal"}

        recovery_results = {
            "total_issues": len(critical),
            "fixed": [],
            "failed": []
        }

        for issue in critical:
            try:
                if issue.issue_type == "stuck_queue":
                    result = await self._heal_stuck_queue(issue)

                elif issue.issue_type == "slow_database":
                    result = await self._heal_slow_database(issue)

                elif issue.issue_type == "memory_exhausted":
                    result = await self._heal_memory_pressure(issue)

                else:
                    result = {"status": "unknown_issue_type"}

                # Log the recovery
                issue.recovery_action = result.get("action")
                issue.recovery_status = result.get("status")

                recovery_results["fixed"].append({
                    "issue": issue.issue_type,
                    "action": result.get("action"),
                    "status": result.get("status")
                })

                logger.info(f"[HEALER] Recovered from {issue.issue_type}: {result.get('action')}")

            except Exception as e:
                logger.error(f"[HEALER] Failed to heal {issue.issue_type}: {e}")
                recovery_results["failed"].append({
                    "issue": issue.issue_type,
                    "error": str(e)
                })

        # STORE recovery actions for ARCHITECT to learn from
        self.recovery_history.append({
            "timestamp": datetime.utcnow(),
            "results": recovery_results
        })

        return recovery_results

    async def _heal_stuck_queue(self, issue: HealthIssue) -> Dict[str, Any]:
        """
        Heal stuck queue by restarting processor and retrying tasks

        Strategy:
        1. SAFE: Restart queue processor (restart the worker)
        2. MEDIUM: Retry stuck tasks (re-enqueue them)
        3. AGGRESSIVE: Purge and reset (only if others fail)
        """

        try:
            # Step 1: Restart queue processor (safest option)
            logger.info("[HEALER] Step 1: Restarting queue processor...")
            # Pseudocode:
            # from app.services.queue_processor import QueueProcessorService
            # await QueueProcessorService.restart()

            # Step 2: Retry stuck tasks
            logger.info("[HEALER] Step 2: Retrying stuck tasks...")
            # Pseudocode:
            # db.query(ChannelQueueItem)
            #   .filter(status == "pending", created_at < now - 10min)
            #   .update({status: "retrying"})

            # Step 3: Monitor recovery
            await asyncio.sleep(5)  # Wait for processor to catch up

            # Check if stuck queue is recovered
            # stuck_remaining = check_queue_health()

            return {
                "status": "success",
                "action": "restarted_processor_and_retried_tasks",
                "timestamp": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"[HEALER] Queue healing failed: {e}")
            return {
                "status": "failed",
                "action": "queue_restart_failed",
                "error": str(e)
            }

    async def _heal_slow_database(self, issue: HealthIssue) -> Dict[str, Any]:
        """Heal slow database by killing long-running queries"""
        try:
            logger.info("[HEALER] Cancelling long-running database queries...")
            # Pseudocode:
            # db.query(slow_queries)
            #   .where(duration > 30s)
            #   .kill()

            return {
                "status": "success",
                "action": "killed_slow_queries"
            }
        except Exception as e:
            return {
                "status": "failed",
                "action": "query_kill_failed",
                "error": str(e)
            }

    async def _heal_memory_pressure(self, issue: HealthIssue) -> Dict[str, Any]:
        """Heal memory exhaustion by clearing caches and restarting"""
        try:
            logger.info("[HEALER] Clearing caches and restarting service...")
            # Pseudocode:
            # redis.flushdb()
            # restart_service()

            return {
                "status": "success",
                "action": "cleared_cache_and_restarted"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    def get_recovery_history(self) -> List[Dict[str, Any]]:
        """Return healing history (for ARCHITECT to learn from)"""
        return self.recovery_history


# ============================================================================
# ARCHITECT: Prevention System (Stops Problems BEFORE Production)
# ============================================================================

class IntegratedArchitect:
    """
    ARCHITECT learns from DOCTOR and HEALER
    Input: DOCTOR's findings + HEALER's recovery history
    Analysis: "Why did this happen? How do we prevent it?"
    Output: Code fixes to prevent future occurrences

    KEY POINT: Architect does NOT run constantly
    - Reads DOCTOR's diagnosis once per SDLC cycle
    - Reads HEALER's recovery history once per cycle
    - Analyzes code to find root causes
    - Recommends fixes to prevent repetition
    """

    def __init__(self, doctor: DoctorHealthMonitor, healer: SelfHealer):
        self.doctor = doctor
        self.healer = healer
        self.cycle_number = 0

    async def analyze_issues_and_recommend_fixes(self) -> List[ArchitectFix]:
        """
        ARCHITECT analyzes ONE TIME per SDLC cycle
        Reads: All doctor findings + healer recovery history
        Asks: "Why did each issue happen?"
        Recommends: Code fixes to prevent repetition
        """

        self.cycle_number += 1
        logger.info(f"\n[ARCHITECT] CYCLE {self.cycle_number} - Analyzing issues...")

        fixes = []

        # Get doctor's findings (just read, don't call constantly)
        doctor_findings = self.doctor.get_all_issues_for_architect()

        # Get healer's recovery history
        healer_history = self.healer.get_recovery_history()

        logger.info(f"[ARCHITECT] Reading {len(doctor_findings)} issues + {len(healer_history)} recovery actions")

        # Analyze each issue
        for issue in doctor_findings:
            if issue.issue_type == "stuck_queue":
                fix = await self._analyze_stuck_queue_issue(issue)
                if fix:
                    fixes.append(fix)

            elif issue.issue_type == "slow_database":
                fix = await self._analyze_slow_database_issue(issue)
                if fix:
                    fixes.append(fix)

            elif issue.issue_type == "memory_exhausted":
                fix = await self._analyze_memory_issue(issue)
                if fix:
                    fixes.append(fix)

        logger.info(f"[ARCHITECT] Recommending {len(fixes)} code fixes")
        return fixes

    async def _analyze_stuck_queue_issue(self, issue: HealthIssue) -> Optional[ArchitectFix]:
        """
        ANALYZE: Stuck queue in production

        EXAMPLE SCENARIO:
        Doctor says: "THUNDER queue stuck with 50 candidates pending"
        Healer did: "Restarted processor and retried tasks"
        Architect asks: "WHY did the queue get stuck?"

        Common causes:
        1. Queue processor crashed (no error handler)
        2. Task processing times out (no timeout protection)
        3. Database transaction deadlock (no retry logic)
        4. Celery worker died (no monitoring)
        5. Memory leak in task (no memory limits)
        """

        logger.info("[ARCHITECT] Analyzing stuck queue root cause...")

        # ROOT CAUSE ANALYSIS (pseudocode)
        # 1. Check queue processor code for error handlers
        # 2. Check task processing for timeouts
        # 3. Check database for transaction locks
        # 4. Check worker process for crashes
        # 5. Check logs for error patterns

        # EXAMPLE: Found missing error handler in queue routing
        fix = ArchitectFix(
            issue_id=f"stuck_queue_{issue.detected_at.timestamp()}",
            title="Add error handling and retry logic to queue processor",
            root_cause="Queue processor crashes silently on exceptions, leaving messages stuck",
            code_location="backend/app/services/queue_processor.py:142-167",
            fix_description="""
            Add try/except with proper error handling:
            1. Catch exceptions during task processing
            2. Log error with context (task ID, candidate ID, error)
            3. Retry with exponential backoff (3 attempts)
            4. Move to dead-letter queue if all retries fail
            5. Alert architect system on repeated failures

            Before:
                for task in pending_tasks:
                    process_task(task)  # Crashes silently

            After:
                for task in pending_tasks:
                    try:
                        process_task(task, timeout=30s)
                    except TaskTimeoutError as e:
                        retry_task(task, attempt=1)
                    except Exception as e:
                        if retry_count < 3:
                            retry_task(task, attempt=retry_count+1)
                        else:
                            move_to_deadletter(task)
                            alert_architect(task, error=e)
            """,
            fix_priority="CRITICAL",
            prevention_benefit="Prevents queue from ever getting stuck; recovers automatically from transient failures",
            estimated_lines_changed=25
        )

        return fix

    async def _analyze_slow_database_issue(self, issue: HealthIssue) -> Optional[ArchitectFix]:
        """Analyze slow database queries"""

        fix = ArchitectFix(
            issue_id=f"slow_db_{issue.detected_at.timestamp()}",
            title="Add database query optimization and connection pooling",
            root_cause="Missing indexes on frequently queried columns; connection pool exhausted",
            code_location="backend/app/core/database.py:50-100",
            fix_description="Add indexes, optimize queries, increase connection pool",
            fix_priority="HIGH",
            prevention_benefit="Prevents database from becoming bottleneck",
            estimated_lines_changed=15
        )

        return fix

    async def _analyze_memory_issue(self, issue: HealthIssue) -> Optional[ArchitectFix]:
        """Analyze memory exhaustion"""

        fix = ArchitectFix(
            issue_id=f"memory_{issue.detected_at.timestamp()}",
            title="Add memory limits and garbage collection",
            root_cause="Unbounded list/cache growth; circular references preventing GC",
            code_location="backend/app/services/cache.py:80-120",
            fix_description="Add LRU cache limits, enable periodic garbage collection",
            fix_priority="HIGH",
            prevention_benefit="Prevents memory exhaustion and service crashes",
            estimated_lines_changed=20
        )

        return fix

    def generate_sdlc_spec(self, fixes: List[ArchitectFix]) -> Dict[str, Any]:
        """
        ARCHITECT generates spec for next dev cycle
        This is what developers implement
        """

        critical_fixes = [f for f in fixes if f.fix_priority == "CRITICAL"]
        high_fixes = [f for f in fixes if f.fix_priority == "HIGH"]

        return {
            "cycle": self.cycle_number,
            "blocking_fixes": [
                {
                    "title": f.title,
                    "location": f.code_location,
                    "priority": f.fix_priority,
                    "lines_to_change": f.estimated_lines_changed
                }
                for f in critical_fixes
            ],
            "recommended_fixes": [
                {
                    "title": f.title,
                    "priority": f.fix_priority
                }
                for f in high_fixes
            ],
            "total_recommendations": len(fixes),
            "total_critical": len(critical_fixes),
            "total_high": len(high_fixes)
        }


# ============================================================================
# ORCHESTRATOR: Connects All Three Systems (90-Second Cycle)
# ============================================================================

class IntegratedSystemOrchestrator:
    """
    Orchestrates DOCTOR → HEALER → ARCHITECT
    Runs on 90-second SDLC cycle

    CYCLE FLOW:
    T+0s:   DOCTOR runs diagnosis (finds all problems)
    T+5s:   HEALER reads critical issues, fixes them
    T+30s:  ARCHITECT reads doctor findings + healer history
    T+60s:  ARCHITECT generates specs for next development cycle
    T+90s:  Wait for developers to implement fixes
    T+180s: Next cycle begins

    KEY: Each system runs ONCE per cycle
    - No redundant calls
    - Clean data flow
    - Minimal overhead
    """

    def __init__(self):
        self.doctor = DoctorHealthMonitor()
        self.healer = SelfHealer(self.doctor)
        self.architect = IntegratedArchitect(self.doctor, self.healer)
        self.running = False
        self.cycle = 0

    async def start(self):
        """Start the integrated system"""
        logger.info("[ORCHESTRATOR] Starting Integrated Architecture System...")
        self.running = True
        asyncio.create_task(self._run_cycle_loop())

    async def _run_cycle_loop(self):
        """
        Main 90-second SDLC cycle
        """
        while self.running:
            try:
                self.cycle += 1
                logger.info(f"\n{'='*80}")
                logger.info(f"[ORCHESTRATOR] CYCLE {self.cycle} - Integrated Health & Prevention")
                logger.info(f"{'='*80}\n")

                # T+0s: DOCTOR diagnoses
                logger.info("[ORCHESTRATOR] T+0s: DOCTOR running diagnosis...")
                doctor_findings = await self.doctor.diagnose_system()
                logger.info(f"[ORCHESTRATOR] Doctor found {len(doctor_findings)} issues")

                # T+5s: HEALER recovers (only from critical issues)
                logger.info("[ORCHESTRATOR] T+5s: HEALER fixing critical issues...")
                await asyncio.sleep(5)
                healing_results = await self.healer.heal_critical_issues()
                logger.info(f"[ORCHESTRATOR] Healer recovered from {len(healing_results.get('fixed', []))} issues")

                # T+30s: ARCHITECT analyzes
                logger.info("[ORCHESTRATOR] T+30s: ARCHITECT analyzing root causes...")
                await asyncio.sleep(25)  # Wait 30s total from start
                architect_fixes = await self.architect.analyze_issues_and_recommend_fixes()

                # T+60s: ARCHITECT generates spec
                await asyncio.sleep(30)
                spec = self.architect.generate_sdlc_spec(architect_fixes)
                logger.info(f"[ORCHESTRATOR] Architect recommends {spec['total_recommendations']} fixes")
                if spec['total_critical'] > 0:
                    logger.warning(f"  🚨 {spec['total_critical']} CRITICAL fixes needed")

                # T+90s: Wait for next cycle
                logger.info("[ORCHESTRATOR] T+90s: Cycle complete, waiting for next cycle...")
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Cycle failed: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def stop(self):
        """Stop the integrated system"""
        logger.info("[ORCHESTRATOR] Stopping Integrated Architecture System...")
        self.running = False

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "running": self.running,
            "cycle": self.cycle,
            "doctor_issues": len(self.doctor.issues),
            "critical_issues": len(self.doctor.get_critical_issues()),
            "recent_recoveries": len(self.healer.recovery_history),
            "last_diagnosis": self.doctor.last_check
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_orchestrator: Optional[IntegratedSystemOrchestrator] = None


def get_integrated_system() -> IntegratedSystemOrchestrator:
    """Get or create the integrated system"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntegratedSystemOrchestrator()
    return _orchestrator


async def init_integrated_system():
    """Initialize and start the system"""
    orchestrator = get_integrated_system()
    await orchestrator.start()
    logger.info("[SYSTEM] Integrated Architecture System initialized and running")
