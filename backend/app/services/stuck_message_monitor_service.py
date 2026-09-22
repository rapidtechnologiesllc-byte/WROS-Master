"""
STUCK MESSAGE MONITORING SERVICE

Monitors queue for messages stuck in PROCESSING state (> 5 minutes).
Runs continuously in background, detects and recovers autonomously.

10-second cycle:
1. Detect: Query for messages in PROCESSING > 5 minutes
2. Heal: Apply escalating recovery strategies
3. Analyze: Identify root causes for prevention
4. Cache: Store status for API queries

No human intervention needed - fully automatic.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from threading import Lock

from app.core.database import SessionLocal
from app.services.stuck_message_detector import (
    StuckMessageDetector,
    StuckMessageHealer,
    StuckMessageArchitect,
    DeadLetterDetector,
    DeadLetterArchitect
)
from app.services.recovery_engine import DeadLetterRecoveryEngine

logger = logging.getLogger(__name__)


class StuckMessageMonitorService:
    """Runs 10-second monitoring cycle for stuck messages"""

    # Monitoring cycle interval
    CHECK_INTERVAL = 10  # seconds

    def __init__(self):
        self.running = False
        self.detector = StuckMessageDetector()
        self.dead_letter_detector = DeadLetterDetector()
        self.status_cache: Dict[str, Any] = {
            "running": False,
            "last_check": None,
            "stuck_detected": 0,
            "dead_letter_patterns": 0,
            "healed": [],
            "failed": [],
            "dead_letters_recovered": [],
            "root_causes": [],
            "dead_letter_fixes": [],
            "cycles_completed": 0
        }
        self.status_lock = Lock()
        self.healer: Optional[StuckMessageHealer] = None
        self.architect: Optional[StuckMessageArchitect] = None
        self.dead_letter_architect: Optional[DeadLetterArchitect] = None
        self.recovery_engine: Optional[DeadLetterRecoveryEngine] = None

    def start_monitoring(self):
        """
        Start monitoring loop (runs in background thread)

        This is a blocking call - runs forever until stop() called
        """
        logger.info("[StuckMessageMonitor] Starting 10-second monitoring cycle...")
        self.running = True

        try:
            while self.running:
                try:
                    self._run_cycle()
                    time.sleep(self.CHECK_INTERVAL)
                except Exception as e:
                    logger.error(f"[StuckMessageMonitor] Cycle failed: {e}", exc_info=True)
                    # Don't crash - continue monitoring
                    time.sleep(self.CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("[StuckMessageMonitor] Monitoring stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"[StuckMessageMonitor] Monitoring crashed: {e}", exc_info=True)
            self.running = False

        logger.info("[StuckMessageMonitor] Monitoring stopped")

    def _run_cycle(self):
        """Run one complete monitoring cycle"""
        # CRITICAL FIX (2026-09-21): Release DB connection between sub-operations
        # Original code held ONE connection for entire cycle (detect + heal + analyze + dead letter detection)
        # If these operations take 5+ seconds and monitor runs every 10s, connection pool gets exhausted
        # New: Create fresh connection for each operation, close immediately after
        try:
            self.status_lock.acquire()
            self.status_cache["cycles_completed"] = self.status_cache.get("cycles_completed", 0) + 1
            self.status_cache["last_check"] = datetime.utcnow().isoformat()
            self.status_lock.release()

            # STEP 1: Detect stuck messages (fresh connection, close immediately after)
            db = SessionLocal()
            try:
                stuck_messages = self.detector.get_all_stuck_messages(db)
                if stuck_messages:
                    logger.warning(StuckMessageDetector.format_stuck_message_report(stuck_messages))
            finally:
                db.close()

            # Update cache with detection results
            with self.status_lock:
                self.status_cache["stuck_detected"] = len(stuck_messages)

            if not stuck_messages:
                # No stuck messages - cycle complete
                return

            # STEP 2: Heal stuck messages (fresh connection, close immediately after)
            db = SessionLocal()  # Fresh connection for healing step
            try:
                if not self.healer:
                    self.healer = StuckMessageHealer(db)
                else:
                    self.healer.db = db

                # Run async heal function
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    healing_results = loop.run_until_complete(self.healer.heal_stuck_messages(stuck_messages))
                finally:
                    loop.close()

                with self.status_lock:
                    self.status_cache["healed"] = healing_results.get("retried", [])
                    self.status_cache["failed"] = healing_results.get("moved_to_dlq", [])

                logger.info(
                    f"[StuckMessageMonitor] Healed: {len(healing_results.get('retried', []))} "
                    f"| DLQ: {len(healing_results.get('moved_to_dlq', []))}"
                )
            finally:
                db.close()

            # STEP 3: Architect analyzes (fresh connection, close immediately after)
            db = SessionLocal()  # Fresh connection for analysis step
            try:
                if not self.architect:
                    self.architect = StuckMessageArchitect(self.detector, self.healer)
                else:
                    self.architect.detector = self.detector
                    self.architect.healer = self.healer

                # Run async analysis function
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    root_causes = loop.run_until_complete(self.architect.analyze_stuck_messages(stuck_messages))
                finally:
                    loop.close()

                with self.status_lock:
                    self.status_cache["root_causes"] = [
                        {
                            "task_name": cause.get("task_name"),
                            "root_cause": cause.get("root_cause"),
                            "severity": cause.get("severity")
                        }
                        for cause in root_causes
                    ]

                if root_causes:
                    logger.warning(f"[StuckMessageMonitor] Found {len(root_causes)} root causes")
                    for cause in root_causes[:3]:
                        logger.warning(f"  • {cause['task_name']}: {cause['root_cause']}")
            finally:
                db.close()

            # STEP 4: Monitor dead-letter patterns (fresh connection, close immediately after)
            db = SessionLocal()
            try:
                self._monitor_dead_letters(db)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"[StuckMessageMonitor] Cycle error: {e}", exc_info=True)

    def _monitor_dead_letters(self, db: Session):
        """
        Monitor dead-letter messages for autonomous healing

        90-second cycle:
        1. DOCTOR: Detect patterns (5+ messages with same error)
        2. ARCHITECT: Analyze and generate fix specs
        3. HEALER: Apply fixes and re-queue messages
        4. DOCTOR: Monitor recovery success
        """

        try:
            # DOCTOR: Detect dead-letter patterns
            patterns = self.dead_letter_detector.get_dead_letter_patterns(db)

            if patterns:
                logger.warning(DeadLetterDetector.format_dead_letter_report(patterns))

                with self.status_lock:
                    self.status_cache["dead_letter_patterns"] = len(patterns)

            if not patterns:
                return  # No patterns to heal

            # ARCHITECT: Analyze first (highest priority) pattern
            pattern = patterns[0]
            logger.info(f"[DeadLetterMonitor] Analyzing pattern: {pattern.error_type} ({pattern.count} messages)")

            if not self.dead_letter_architect:
                self.dead_letter_architect = DeadLetterArchitect()

            # Run async analysis
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                fix_spec = loop.run_until_complete(
                    self.dead_letter_architect.analyze_dead_letter_pattern(pattern)
                )
            finally:
                loop.close()

            logger.info(f"[DeadLetterMonitor] Fix spec generated: {fix_spec.get('fix_type')} (confidence: {fix_spec.get('confidence'):.0%})")

            with self.status_lock:
                self.status_cache["dead_letter_fixes"].append({
                    "error_type": pattern.error_type,
                    "message_count": pattern.count,
                    "fix_type": fix_spec.get("fix_type"),
                    "confidence": fix_spec.get("confidence"),
                    "timestamp": datetime.utcnow().isoformat()
                })

            # HEALER: Execute recovery (re-queue messages)
            if not self.recovery_engine:
                self.recovery_engine = DeadLetterRecoveryEngine()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                recovery_result = loop.run_until_complete(
                    self.recovery_engine.recover_dead_letters(
                        fix_spec,
                        pattern.message_ids,
                        db
                    )
                )
            finally:
                loop.close()

            logger.info(f"[DeadLetterMonitor] Recovery: {recovery_result.get('messages_recovered')}/{pattern.count} messages re-queued")

            with self.status_lock:
                self.status_cache["dead_letters_recovered"].append({
                    "pattern": pattern.error_type,
                    "recovered": recovery_result.get("messages_recovered", 0),
                    "timestamp": datetime.utcnow().isoformat()
                })

        except Exception as e:
            logger.error(f"[DeadLetterMonitor] Dead-letter monitoring failed: {e}", exc_info=True)

    def get_current_status(self) -> Dict[str, Any]:
        """Return current monitoring status for API queries"""
        with self.status_lock:
            return {
                "running": self.running,
                "last_check": self.status_cache.get("last_check"),
                "stuck_detected": self.status_cache.get("stuck_detected", 0),
                "healed_count": len(self.status_cache.get("healed", [])),
                "failed_count": len(self.status_cache.get("failed", [])),
                "root_causes_found": len(self.status_cache.get("root_causes", [])),
                "dead_letter_patterns_detected": self.status_cache.get("dead_letter_patterns", 0),
                "dead_letters_recovered": len(self.status_cache.get("dead_letters_recovered", [])),
                "cycles_completed": self.status_cache.get("cycles_completed", 0),
                "root_causes": self.status_cache.get("root_causes", [])[:5],  # Last 5
                "dead_letter_fixes": self.status_cache.get("dead_letter_fixes", [])[:5]  # Last 5
            }

    def get_history(self) -> Dict[str, Any]:
        """Return monitoring history"""
        with self.status_lock:
            return {
                "last_check": self.status_cache.get("last_check"),
                "cycles_completed": self.status_cache.get("cycles_completed", 0),
                "recent_healed": self.status_cache.get("healed", [])[-10:],  # Last 10
                "recent_failed": self.status_cache.get("failed", [])[-10:],
                "recent_root_causes": self.status_cache.get("root_causes", [])[-10:]
            }

    def stop(self):
        """Stop monitoring"""
        logger.info("[StuckMessageMonitor] Stopping monitoring...")
        self.running = False


# Global instance
_monitor_service: Optional[StuckMessageMonitorService] = None


def get_monitor_service() -> StuckMessageMonitorService:
    """Get or create global monitor service"""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = StuckMessageMonitorService()
    return _monitor_service


def start_stuck_message_monitoring():
    """Start the monitoring service (call from main.py startup)"""
    service = get_monitor_service()
    service.start_monitoring()
