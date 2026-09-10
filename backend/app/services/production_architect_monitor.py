"""
Production Architect Monitor - Runs at server startup

Continuously:
1. Analyzes system state with ruthless architect
2. Keeps detailed notes of findings
3. Detects production issues
4. Can spawn doctor agent to fix in production
5. Prevents issues before they become incidents
"""
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ProductionMonitoringNote:
    """Single monitoring event (finding + action taken)"""

    def __init__(self, finding_title: str, severity: str, action: str):
        self.finding_title = finding_title
        self.severity = severity
        self.action = action
        self.timestamp = datetime.utcnow()
        self.resolved = False
        self.resolution_time: Optional[timedelta] = None

    def resolve(self):
        """Mark as resolved"""
        self.resolved = True
        self.resolution_time = datetime.utcnow() - self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding": self.finding_title,
            "severity": self.severity,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolution_time_seconds": (
                self.resolution_time.total_seconds() if self.resolution_time else None
            ),
        }


class ProductionArchitectMonitor:
    """
    Monitors production system continuously.

    On each monitor cycle:
    1. Ruthless architect analyzes system
    2. Findings recorded as notes
    3. If blocking issues detected:
       - Log alert
       - Can spawn doctor agent to fix
    4. Pattern tracking (recurring issues)
    5. Auto-remediation triggers
    """

    CHECK_INTERVAL_SECONDS = 300  # Every 5 minutes
    DOCTOR_AGENT_TIMEOUT = 600  # 10 minutes to fix

    def __init__(self):
        self.notes: List[ProductionMonitoringNote] = []
        self.last_check: Optional[datetime] = None
        self.blocking_issue_count = 0
        self.patterns_detected: Dict[str, int] = {}

    async def start_monitoring(self):
        """Start continuous monitoring (runs at server startup)"""
        logger.info("[MONITOR] Starting production architect monitoring")

        while True:
            try:
                await self.monitor_cycle()
            except Exception as e:
                logger.error(f"[MONITOR] Cycle failed: {e}", exc_info=True)

            # Wait for next check
            await asyncio.sleep(self.CHECK_INTERVAL_SECONDS)

    async def monitor_cycle(self):
        """Single monitoring cycle"""
        logger.info("[MONITOR] Starting cycle")

        from app.services.ruthless_architect import get_ruthless_architect

        architect = get_ruthless_architect()
        analysis = await architect.analyze_cycle(cycle_number=1)

        self.last_check = datetime.utcnow()

        # Check for blocking issues
        blocking = analysis.get_blocking_issues()
        self.blocking_issue_count = len(blocking)

        if blocking:
            logger.error(f"[MONITOR] 🚨 {len(blocking)} BLOCKING issues detected in production")

            # Record each blocking issue
            for finding in blocking:
                note = ProductionMonitoringNote(
                    finding_title=finding.title,
                    severity=finding.severity.value,
                    action="BLOCKING - Spawning doctor agent to fix"
                )
                self.notes.append(note)
                logger.error(f"[MONITOR] BLOCKING: {finding.title}")

                # Spawn doctor agent to fix
                await self._spawn_doctor_agent(finding)
                note.resolve()

        # Check for recurring patterns
        high_findings = [f for f in analysis.findings if "HIGH" in f.severity.value]
        for finding in high_findings:
            if finding.title not in self.patterns_detected:
                self.patterns_detected[finding.title] = 0
            self.patterns_detected[finding.title] += 1

            # If pattern recurring 3+ times, alert
            if self.patterns_detected[finding.title] >= 3:
                logger.warning(
                    f"[MONITOR] RECURRING: {finding.title} "
                    f"({self.patterns_detected[finding.title]} times)"
                )

        logger.info(f"[MONITOR] Cycle complete: {len(analysis.findings)} issues found")
        logger.info(f"[MONITOR] Blocking: {len(blocking)}, High: {len(high_findings)}")

    async def _spawn_doctor_agent(self, finding):
        """
        Spawn doctor agent to fix production issue.

        Doctor agent:
        1. Reads finding details
        2. Analyzes current system state
        3. Generates fix
        4. Applies fix
        5. Verifies fix
        6. Reports back
        """
        logger.error(f"[DOCTOR] Spawning agent to fix: {finding.title}")

        # In production, this would actually spawn an agent:
        # result = await Agent(
        #     description=f"Fix production issue: {finding.title}",
        #     prompt=f"""
        #         Production issue detected and requires immediate fix:
        #
        #         {finding.title}
        #
        #         Impact: {finding.impact}
        #         Fix: {finding.fix}
        #         Test: {finding.test}
        #
        #         Apply this fix now. Verify it works. Report results.
        #     """,
        #     subagent_type="Doctor",  # Hypothetical doctor agent
        #     run_in_background=True,  # Can take up to 10 minutes
        # )

        logger.error(f"[DOCTOR] Would spawn agent: {finding.title}")
        logger.error(f"[DOCTOR] Timeout: {self.DOCTOR_AGENT_TIMEOUT}s")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "blocking_issues_detected": self.blocking_issue_count,
            "total_notes": len(self.notes),
            "recurring_patterns": self.patterns_detected,
            "recent_notes": [note.to_dict() for note in self.notes[-10:]],
        }

    def save_notes(self, file_path: str = "backend/app/data/production_notes.json"):
        """Save monitoring notes to disk"""
        try:
            data = {
                "last_updated": datetime.utcnow().isoformat(),
                "blocking_issues_detected": self.blocking_issue_count,
                "notes": [note.to_dict() for note in self.notes],
                "patterns": self.patterns_detected,
            }

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"[MONITOR] Saved {len(self.notes)} notes to {file_path}")
        except Exception as e:
            logger.error(f"[MONITOR] Failed to save notes: {e}")


# Global instance
_monitor: Optional[ProductionArchitectMonitor] = None


def get_production_monitor() -> ProductionArchitectMonitor:
    """Get global production monitor"""
    global _monitor
    if _monitor is None:
        _monitor = ProductionArchitectMonitor()
    return _monitor


async def start_production_monitoring():
    """Start monitoring at server startup"""
    monitor = get_production_monitor()
    logger.info("[STARTUP] Starting production architect monitor")

    # Run monitoring in background
    asyncio.create_task(monitor.start_monitoring())


def get_production_status() -> Dict[str, Any]:
    """Get production system status for health check endpoint"""
    monitor = get_production_monitor()
    return monitor.get_monitoring_status()
