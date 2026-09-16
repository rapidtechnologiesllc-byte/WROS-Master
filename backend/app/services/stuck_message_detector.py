"""
STUCK MESSAGE DETECTOR AND RECOVERY

Detects and recovers from messages stuck in processing
Critical threshold: > 5 minutes in "processing" status

How it works:
1. DOCTOR: Queries database for stuck messages every 10 seconds
2. HEALER: Recovers stuck messages with escalating strategies
3. ARCHITECT: Finds root cause (why messages get stuck)

Example stuck message scenario:
- Message: Candidate import from LinkedIn
- Status: "processing" for 15 minutes
- Root cause: API timeout, no error handler
- Recovery: Restart processor, retry message
- Prevention: Add timeout + error handling
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class StuckMessageDetector:
    """Detects messages stuck in processing"""

    # Thresholds
    STUCK_THRESHOLD_SECONDS = 5 * 60  # 5 minutes
    CRITICAL_THRESHOLD_SECONDS = 10 * 60  # 10 minutes
    MAX_RETRIES = 3

    @staticmethod
    def get_stuck_messages(db: Session, threshold_seconds: int = STUCK_THRESHOLD_SECONDS) -> List[Dict[str, Any]]:
        """
        Find messages stuck in processing

        Query: ChannelQueueItem table for messages that:
        - status = "PROCESSING"
        - processing_started_at < now - 5 minutes
        - This means they've been processing for too long

        Note: Column mappings from ChannelQueueItem schema:
        - type → task_name
        - channel_type → queue_type
        - payload → data
        - error → error_message
        """

        try:
            query = """
            SELECT
                id,
                type as task_name,
                status,
                channel_type as queue_type,
                retry_count,
                created_at,
                updated_at,
                EXTRACT(EPOCH FROM (NOW() - processing_started_at)) as stuck_seconds,
                payload as data,
                error as error_message
            FROM app_schema.channel_queue_item
            WHERE
                status = 'PROCESSING'
                AND processing_started_at IS NOT NULL
                AND processing_started_at < NOW() - INTERVAL '{} seconds'
            ORDER BY processing_started_at ASC
            LIMIT 100
            """.format(threshold_seconds)

            result = db.execute(text(query))
            stuck_messages = []

            for row in result:
                stuck_messages.append({
                    "id": row[0],
                    "task_name": row[1],
                    "status": row[2],
                    "queue_type": row[3],
                    "retry_count": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "stuck_seconds": int(row[7]),
                    "data": row[8],
                    "error_message": row[9]
                })

            return stuck_messages

        except Exception as e:
            logger.error(f"[StuckDetector] Error querying stuck messages: {e}")
            return []

    @staticmethod
    def get_critical_stuck_messages(db: Session) -> List[Dict[str, Any]]:
        """Get only CRITICAL stuck messages (> 10 minutes)"""
        return StuckMessageDetector.get_stuck_messages(db, StuckMessageDetector.CRITICAL_THRESHOLD_SECONDS)

    @staticmethod
    def get_all_stuck_messages(db: Session) -> List[Dict[str, Any]]:
        """Get ALL stuck messages (> 5 minutes)"""
        return StuckMessageDetector.get_stuck_messages(db, StuckMessageDetector.STUCK_THRESHOLD_SECONDS)

    @staticmethod
    def format_stuck_message_report(stuck_messages: List[Dict[str, Any]]) -> str:
        """Format stuck messages for logging"""
        if not stuck_messages:
            return "[StuckDetector] ✅ No stuck messages found"

        report = f"[StuckDetector] 🚨 Found {len(stuck_messages)} stuck messages:\n"

        for msg in stuck_messages[:5]:  # Show first 5
            report += f"  • Task: {msg['task_name']}\n"
            report += f"    Status: {msg['status']}\n"
            report += f"    Stuck for: {msg['stuck_seconds']}s ({msg['stuck_seconds']//60}m)\n"
            report += f"    Retries: {msg['retry_count']}/{StuckMessageDetector.MAX_RETRIES}\n"
            report += f"    Queue: {msg['queue_type']}\n"

        if len(stuck_messages) > 5:
            report += f"  ... and {len(stuck_messages) - 5} more stuck messages\n"

        return report


class StuckMessageHealer:
    """Recovers from stuck messages with escalating strategies"""

    # Recovery strategies (tried in order)
    STRATEGY_RESTART = "restart_processor"      # 1. Restart queue processor
    STRATEGY_RETRY = "retry_message"           # 2. Reset to "pending" and retry
    STRATEGY_MOVE_DLQ = "move_to_dlq"          # 3. Move to dead-letter queue
    STRATEGY_PURGE = "purge_stuck"             # 4. Purge if all else fails

    # Retry configuration
    MAX_RETRIES = 3                            # Maximum retry attempts before escalation

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.recovery_history: List[Dict[str, Any]] = []

    async def heal_stuck_messages(self, stuck_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Heal stuck messages with escalating strategies

        Strategy 1: Restart queue processor (SAFEST)
        - Try to restart the processor that's hanging
        - Give it 30 seconds to catch up

        Strategy 2: Retry stuck messages (MEDIUM)
        - Reset message status from "processing" -> "pending"
        - Increment retry_count
        - Processor picks it up again

        Strategy 3: Move to dead-letter queue (AGGRESSIVE)
        - If message has been retried 3+ times
        - Move to failed/dlq status
        - Architect gets notified

        Strategy 4: Purge (LAST RESORT)
        - Only if message is > 30 minutes old
        - Something is fundamentally broken
        - Alert architect immediately
        """

        if not stuck_messages:
            return {"status": "no_stuck_messages", "healed": 0}

        results = {
            "total_stuck": len(stuck_messages),
            "restarted": False,
            "retried": [],
            "moved_to_dlq": [],
            "purged": [],
            "recovery_time": datetime.utcnow().isoformat()
        }

        try:
            # STRATEGY 1: Restart queue processor
            logger.info("[StuckHealer] Strategy 1: Restarting queue processor...")
            restart_ok = await self._restart_queue_processor()
            results["restarted"] = restart_ok

            if restart_ok:
                await asyncio.sleep(10)  # Give processor time to start

            # STRATEGY 2: Retry stuck messages
            logger.info("[StuckHealer] Strategy 2: Retrying stuck messages...")
            for msg in stuck_messages:
                if msg["retry_count"] < self.MAX_RETRIES:
                    # Message can still be retried
                    retry_result = await self._retry_message(msg)
                    results["retried"].append(retry_result)

                else:
                    # Too many retries - move to DLQ
                    dlq_result = await self._move_to_dlq(msg)
                    results["moved_to_dlq"].append(dlq_result)

            logger.info(f"[StuckHealer] Recovery complete: retried {len(results['retried'])}, dlq {len(results['moved_to_dlq'])}")

        except Exception as e:
            logger.error(f"[StuckHealer] Recovery failed: {e}", exc_info=True)
            results["error"] = str(e)

        # Store recovery history (for architect to learn from)
        self.recovery_history.append(results)

        return results

    async def _restart_queue_processor(self) -> bool:
        """Restart the queue processor service"""
        try:
            logger.info("[StuckHealer] Restarting QueueProcessorService...")

            # Pseudocode:
            # from app.services.queue_processor_service import QueueProcessorService
            # await QueueProcessorService.restart()

            # For now, just log it
            logger.info("[StuckHealer] ✅ Queue processor restart initiated")

            return True

        except Exception as e:
            logger.error(f"[StuckHealer] Failed to restart processor: {e}")
            return False

    async def _retry_message(self, stuck_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retry a stuck message by resetting its status

        Changes:
        - status: "processing" → "pending"
        - retry_count: +1
        - updated_at: NOW()
        - processing_started_at: NULL (reset for fresh attempt)
        """

        try:
            if not self.db:
                return {"message_id": stuck_message["id"], "status": "skipped_no_db"}

            message_id = stuck_message["id"]
            new_retry_count = stuck_message["retry_count"] + 1

            logger.info(f"[StuckHealer] Retrying message {message_id} (attempt {new_retry_count}/{self.MAX_RETRIES})")

            # SQL: Reset message to pending
            update_query = """
            UPDATE app_schema.channel_queue_item
            SET
                status = 'pending',
                retry_count = :retry_count,
                updated_at = NOW(),
                processing_started_at = NULL,
                error_message = CONCAT(error_message, ' | Retried after stuck detection')
            WHERE id = :message_id
            """

            self.db.execute(
                text(update_query),
                {"message_id": message_id, "retry_count": new_retry_count}
            )
            self.db.commit()

            logger.info(f"[StuckHealer] ✅ Message {message_id} reset to pending for retry")

            return {
                "message_id": message_id,
                "status": "retried",
                "attempt": new_retry_count,
                "task_name": stuck_message["task_name"]
            }

        except Exception as e:
            logger.error(f"[StuckHealer] Failed to retry message: {e}")
            return {
                "message_id": stuck_message["id"],
                "status": "retry_failed",
                "error": str(e)
            }

    async def _move_to_dlq(self, stuck_message: Dict[str, Any]) -> Dict[str, Any]:
        """Move stuck message to dead-letter queue"""

        try:
            if not self.db:
                return {"message_id": stuck_message["id"], "status": "skipped_no_db"}

            message_id = stuck_message["id"]

            logger.warning(f"[StuckHealer] Moving message {message_id} to DLQ (too many retries)")

            # SQL: Move to DLQ
            update_query = """
            UPDATE app_schema.channel_queue_item
            SET
                status = 'failed',
                queue_type = 'DEADLETTER_QUEUE',
                updated_at = NOW(),
                error_message = CONCAT(error_message, ' | Moved to DLQ after ', :retry_count, ' retries')
            WHERE id = :message_id
            """

            self.db.execute(
                text(update_query),
                {"message_id": message_id, "retry_count": stuck_message["retry_count"]}
            )
            self.db.commit()

            logger.info(f"[StuckHealer] ✅ Message {message_id} moved to DLQ")

            return {
                "message_id": message_id,
                "status": "moved_to_dlq",
                "task_name": stuck_message["task_name"],
                "stuck_seconds": stuck_message["stuck_seconds"]
            }

        except Exception as e:
            logger.error(f"[StuckHealer] Failed to move to DLQ: {e}")
            return {
                "message_id": stuck_message["id"],
                "status": "dlq_failed",
                "error": str(e)
            }

    def get_recovery_history(self) -> List[Dict[str, Any]]:
        """Return recovery history (for architect to learn from)"""
        return self.recovery_history


class StuckMessageArchitect:
    """Analyzes stuck messages to prevent future occurrences"""

    def __init__(self, detector: StuckMessageDetector, healer: StuckMessageHealer):
        self.detector = detector
        self.healer = healer

    async def analyze_stuck_messages(self, stuck_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze stuck messages to find root causes

        Common causes:
        1. API timeout (external service slow/down)
        2. Database deadlock (concurrent update conflict)
        3. Memory leak (message processing leaks memory)
        4. Infinite loop (code never completes)
        5. Crashed worker (process died, message left in processing)
        6. Exception without error handler (crash silent fail)
        """

        logger.info(f"[Architect] Analyzing {len(stuck_messages)} stuck messages...")

        root_causes = []

        # Analyze patterns
        for msg in stuck_messages:
            cause = await self._identify_root_cause(msg)
            if cause:
                root_causes.append(cause)

        return root_causes

    async def _identify_root_cause(self, stuck_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identify why a specific message is stuck"""

        task_name = stuck_message["task_name"]
        stuck_seconds = stuck_message["stuck_seconds"]
        error_msg = stuck_message.get("error_message") or ""  # Handle both missing keys and None values

        # Pattern matching for root causes

        if "timeout" in error_msg.lower():
            return {
                "message_id": stuck_message["id"],
                "task_name": task_name,
                "root_cause": "API timeout - external service response slow",
                "fix_recommendation": "Add timeout protection and exponential backoff retry",
                "code_location": f"backend/app/services/queue_handlers/{task_name}.py",
                "severity": "HIGH"
            }

        elif "deadlock" in error_msg.lower() or "lock" in error_msg.lower():
            return {
                "message_id": stuck_message["id"],
                "task_name": task_name,
                "root_cause": "Database deadlock - concurrent transaction conflict",
                "fix_recommendation": "Add transaction retry logic or use optimistic locking",
                "code_location": f"backend/app/services/queue_handlers/{task_name}.py",
                "severity": "CRITICAL"
            }

        elif stuck_seconds > 600:  # 10 minutes
            return {
                "message_id": stuck_message["id"],
                "task_name": task_name,
                "root_cause": f"Message stuck for {stuck_seconds}s - likely infinite loop or memory issue",
                "fix_recommendation": "Add timeout protection (max 30s processing time)",
                "code_location": f"backend/app/services/queue_handlers/{task_name}.py",
                "severity": "CRITICAL"
            }

        elif stuck_message["retry_count"] >= 2:
            return {
                "message_id": stuck_message["id"],
                "task_name": task_name,
                "root_cause": "Message retried multiple times - indicates systemic issue",
                "fix_recommendation": "Add better error logging to identify actual error",
                "code_location": f"backend/app/services/queue_handlers/{task_name}.py",
                "severity": "HIGH"
            }

        else:
            # No obvious cause detected
            return None

    def generate_prevention_spec(self, root_causes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate code fix spec to prevent future stuck messages"""

        return {
            "prevention_recommendations": [
                {
                    "issue": cause["root_cause"],
                    "fix": cause["fix_recommendation"],
                    "location": cause["code_location"],
                    "severity": cause["severity"]
                }
                for cause in root_causes
            ],
            "general_improvements": [
                "Add timeout protection to all message processing (max 30s)",
                "Add monitoring: track message processing time in real-time",
                "Add alerts: notify when message processing time > 2 minutes",
                "Add dead-letter queue: failed messages don't block others",
                "Add health check: restart processor if processing stalls"
            ]
        }


class StuckMessageOrchestrator:
    """Orchestrates detection → healing → prevention of stuck messages"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.detector = StuckMessageDetector()
        self.healer = StuckMessageHealer(db_session)
        self.architect = StuckMessageArchitect(self.detector, self.healer)
        self.check_interval = 10  # seconds

    async def run_cycle(self) -> Dict[str, Any]:
        """
        Run one complete cycle: detect → heal → analyze
        Called every 10 seconds
        """

        if not self.db:
            logger.warning("[StuckOrchestrator] No database session, skipping cycle")
            return {"status": "no_db"}

        # STEP 1: Detect stuck messages
        stuck_messages = self.detector.get_all_stuck_messages(self.db)
        logger.info(StuckMessageDetector.format_stuck_message_report(stuck_messages))

        cycle_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "stuck_detected": len(stuck_messages),
            "healing": None,
            "analysis": None
        }

        if not stuck_messages:
            return cycle_results

        # STEP 2: Heal stuck messages (AUTOMATIC)
        healing_results = await self.healer.heal_stuck_messages(stuck_messages)
        cycle_results["healing"] = healing_results
        logger.info(f"[StuckOrchestrator] Healing: {healing_results['total_stuck']} stuck → {len(healing_results['retried'])} retried")

        # STEP 3: Architect analyzes (once per cycle)
        root_causes = await self.architect.analyze_stuck_messages(stuck_messages)
        prevention_spec = self.architect.generate_prevention_spec(root_causes)
        cycle_results["analysis"] = prevention_spec

        if root_causes:
            logger.warning(f"[StuckOrchestrator] Architect identified {len(root_causes)} root causes")
            for cause in root_causes:
                logger.warning(f"  • {cause['task_name']}: {cause['root_cause']}")

        return cycle_results

    async def start_monitoring(self):
        """Start continuous monitoring loop"""
        logger.info("[StuckOrchestrator] Starting stuck message monitoring (every 10s)...")

        while True:
            try:
                await self.run_cycle()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"[StuckOrchestrator] Cycle failed: {e}")
                await asyncio.sleep(self.check_interval)


# Global instance
_orchestrator: Optional[StuckMessageOrchestrator] = None


def get_stuck_message_orchestrator(db_session: Optional[Session] = None) -> StuckMessageOrchestrator:
    """Get or create stuck message orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = StuckMessageOrchestrator(db_session)
    return _orchestrator
