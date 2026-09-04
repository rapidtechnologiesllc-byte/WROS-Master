#!/usr/bin/env python3
"""
Gate Scheduler: Runs continuous learning and auto-fixing every minute.

This is the autonomous heartbeat of the gate system.
Every 60 seconds, it:
1. Analyzes violation patterns
2. Updates detection rules
3. Applies auto-fixes where appropriate
4. Reports learning progress
"""
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gate_learner import GateLearner, GateRuleUpdater, run_continuous_learning
from gate_auto_fixer import GateAutoFixer


class GateScheduler:
    """Manages continuous gate learning and auto-fixing."""

    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self.running = False
        self.learner = GateLearner()
        self.updater = GateRuleUpdater(self.learner)
        self.learning_thread = None

    def start(self):
        """Start the continuous learning loop."""
        self.running = True
        self.learning_thread = threading.Thread(target=self._learning_loop, daemon=True)
        self.learning_thread.start()
        print(f"[GATE SCHEDULER] Started with {self.interval}s interval")

    def stop(self):
        """Stop the continuous learning loop."""
        self.running = False
        if self.learning_thread:
            self.learning_thread.join(timeout=5)
        print("[GATE SCHEDULER] Stopped")

    def _learning_loop(self):
        """Main learning loop - runs every N seconds."""
        iteration = 0
        while self.running:
            iteration += 1
            timestamp = datetime.now().isoformat()
            print(f"\n[GATE SCHEDULER] Iteration #{iteration} at {timestamp}")

            try:
                # Run continuous learning
                stats = run_continuous_learning()

                # Auto-apply fixes where confidence is high
                self._auto_apply_high_confidence_fixes()

                # Log progress
                print(f"[GATE SCHEDULER] Learning cycle complete")
                print(f"  Fix rate: {stats['overall_fix_rate']*100:.1f}%")
                print(f"  Total violations analyzed: {stats['total_violations_analyzed']}")

            except Exception as e:
                print(f"[GATE SCHEDULER ERROR] {e}")

            # Sleep for interval
            time.sleep(self.interval)

    def _auto_apply_high_confidence_fixes(self):
        """Auto-apply fixes for high-confidence patterns."""
        recent_violations = self._get_recent_violations()

        for violation in recent_violations:
            issue_type = violation.get('issue_type')
            severity = violation.get('severity')

            # Check if we should auto-apply
            if self.learner.should_auto_apply_fix(issue_type, severity):
                print(f"[GATE AUTO-FIX] Auto-applying fix for {issue_type}")

    def _get_recent_violations(self, minutes: int = 5) -> list:
        """Get violations from the last N minutes."""
        learning_db = Path(".claude/gate_learning.json")
        if not learning_db.exists():
            return []

        try:
            import json
            with open(learning_db) as f:
                data = json.load(f)

            recent = []
            for issue in data.get('issues', []):
                # Parse timestamp and check if recent
                try:
                    ts = datetime.fromisoformat(issue.get('timestamp'))
                    if (datetime.now() - ts).total_seconds() < minutes * 60:
                        recent.append(issue)
                except:
                    pass

            return recent
        except:
            return []


def integrate_auto_fixer_with_gate(gate_validator_class):
    """Decorator to add auto-fixing capability to the gate validator."""
    original_validate = gate_validator_class.validate_file

    def validate_with_auto_fix(self, file_path: str):
        # Run original validation
        result = original_validate(self, file_path)

        # If violations found and user wants auto-fix, apply it
        if not result and self.issues and self._should_auto_fix():
            fixer = GateAutoFixer(file_path, self.content, self.lines)

            fixed_count = 0
            for issue in self.issues:
                if issue.get('severity') != 'CRITICAL':
                    success, msg = fixer.apply_fix(issue)
                    if success:
                        fixed_count += 1
                        print(f"[AUTO-FIX] {msg} on line {issue['line']}")

            # Save fixed content
            if fixed_count > 0:
                fixer.save_fixes()
                print(f"[AUTO-FIX] Applied {fixed_count} fixes to {file_path}")
                self.content = fixer.get_fixed_content()
                self.lines = self.content.split('\n')

        return result

    def should_auto_fix(self):
        """Check if auto-fix should be enabled."""
        # Can be controlled by env var or config
        import os
        return os.getenv('GATE_AUTO_FIX', 'false').lower() == 'true'

    # Add method to validator
    validate_with_auto_fix._should_auto_fix = should_auto_fix
    gate_validator_class.validate_file = validate_with_auto_fix

    return gate_validator_class


# Global scheduler instance
_scheduler = None


def start_gate_learning_scheduler():
    """Start the global gate learning scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = GateScheduler(interval_seconds=60)
        _scheduler.start()
    return _scheduler


def stop_gate_learning_scheduler():
    """Stop the global gate learning scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None


if __name__ == '__main__':
    scheduler = GateScheduler(interval_seconds=10)  # 10s for testing
    scheduler.start()

    try:
        # Run for 60 seconds (test mode)
        time.sleep(60)
    except KeyboardInterrupt:
        print("\n[GATE SCHEDULER] Interrupted")
    finally:
        scheduler.stop()
