"""
PHASE 3: GATE AUDIT DASHBOARD (2026-09-19)

Monitor code review gate effectiveness:
- Violation patterns (what does gate catch most?)
- Developer statistics (who has most violations?)
- False positive/negative rates (does gate miss real issues?)
- Prevention effectiveness (how many issues caught before production?)
- Violation trends over time
- Gate tuning metrics (should we raise/lower thresholds?)

This dashboard helps optimize gate criteria and identify patterns
in code quality across developers.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ViolationSeverity(Enum):
    """Severity levels for gate violations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WARNING = "warning"


class ViolationCategory(Enum):
    """Categories of violations the gate detects."""
    LINTING = "linting"
    TYPE_SAFETY = "type_safety"
    ERROR_PROPAGATION = "error_propagation"
    PERMISSION_MISSING = "permission_missing"
    HARDCODED_VALUE = "hardcoded_value"
    MISSING_VALIDATION = "missing_validation"
    NULL_CHECK = "null_check"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    OTHER = "other"


@dataclass
class GateViolation:
    """Record of a single gate violation."""
    timestamp: datetime
    violation_id: str
    developer: str
    file_path: str
    line_number: int
    category: ViolationCategory
    severity: ViolationSeverity
    message: str
    was_fixed: bool = False
    fixed_timestamp: Optional[datetime] = None
    production_impact: Optional[str] = None  # none, bug, security, data_loss, performance
    was_false_positive: bool = False


@dataclass
class CommitAttempt:
    """Record of developer attempting to commit."""
    timestamp: datetime
    commit_id: str
    developer: str
    message: str
    files_changed: int
    violations_found: int
    violations_by_severity: Dict[ViolationSeverity, int]
    commit_blocked: bool
    bypass_attempted: bool = False  # Did developer try --no-verify?


class Phase3GateAuditDashboard:
    """
    Monitor code review gate violations and prevention effectiveness.

    Endpoints:
    - GET /monitoring/gate/violations
    - GET /monitoring/gate/patterns
    - GET /monitoring/gate/developer-stats
    - GET /monitoring/gate/false-positives
    - GET /monitoring/gate/prevention-rate
    - GET /monitoring/gate/trends
    - GET /monitoring/gate/health
    """

    def __init__(self):
        """Initialize gate audit dashboard."""
        self.violations: List[GateViolation] = []
        self.commit_attempts: List[CommitAttempt] = []
        self.dashboard_started = datetime.now()

    def record_violation(
        self,
        violation_id: str,
        developer: str,
        file_path: str,
        line_number: int,
        category: ViolationCategory,
        severity: ViolationSeverity,
        message: str,
    ) -> None:
        """Record gate violation."""
        violation = GateViolation(
            timestamp=datetime.now(),
            violation_id=violation_id,
            developer=developer,
            file_path=file_path,
            line_number=line_number,
            category=category,
            severity=severity,
            message=message,
        )
        self.violations.append(violation)
        logger.info(
            f"[GATE] Violation {violation_id}: {category.value} "
            f"({severity.value}) in {file_path}:{line_number} by {developer}"
        )

    def record_commit_attempt(
        self,
        commit_id: str,
        developer: str,
        message: str,
        files_changed: int,
        violations_found: int,
        violations_by_severity: Dict[ViolationSeverity, int],
        commit_blocked: bool,
        bypass_attempted: bool = False,
    ) -> None:
        """Record developer commit attempt and gate result."""
        attempt = CommitAttempt(
            timestamp=datetime.now(),
            commit_id=commit_id,
            developer=developer,
            message=message,
            files_changed=files_changed,
            violations_found=violations_found,
            violations_by_severity=violations_by_severity,
            commit_blocked=commit_blocked,
            bypass_attempted=bypass_attempted,
        )
        self.commit_attempts.append(attempt)

        if bypass_attempted:
            logger.warning(
                f"[GATE] BYPASS ATTEMPT {commit_id} by {developer} "
                f"(--no-verify or force push)"
            )
        elif commit_blocked:
            logger.info(
                f"[GATE] Commit {commit_id} BLOCKED by {developer} "
                f"({violations_found} violations)"
            )
        else:
            logger.info(
                f"[GATE] Commit {commit_id} APPROVED by {developer}"
            )

    def mark_violation_fixed(self, violation_id: str) -> None:
        """Mark violation as fixed in subsequent commit."""
        for violation in self.violations:
            if violation.violation_id == violation_id:
                violation.was_fixed = True
                violation.fixed_timestamp = datetime.now()
                logger.info(f"[GATE] Violation {violation_id} FIXED")
                break

    def mark_false_positive(
        self,
        violation_id: str,
        production_impact: str = "none",
    ) -> None:
        """Mark violation as false positive (gate was wrong)."""
        for violation in self.violations:
            if violation.violation_id == violation_id:
                violation.was_false_positive = True
                violation.production_impact = production_impact
                logger.warning(
                    f"[GATE] Violation {violation_id} FALSE POSITIVE "
                    f"(impact: {production_impact})"
                )
                break

    def record_production_impact(
        self,
        violation_id: str,
        production_impact: str,  # bug, security, data_loss, performance
    ) -> None:
        """Record that a violation (or false positive) had production impact."""
        for violation in self.violations:
            if violation.violation_id == violation_id:
                violation.production_impact = production_impact
                if not violation.was_false_positive:
                    logger.info(
                        f"[GATE] Violation {violation_id} detected real issue "
                        f"(impact: {production_impact})"
                    )
                break

    # ======== DASHBOARD ENDPOINTS ========

    def get_violation_metrics(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/gate/violations

        Current violations by category and severity.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [v for v in self.violations if v.timestamp >= cutoff]

        if not recent:
            return {
                "total_violations": 0,
                "by_category": {},
                "by_severity": {},
                "unfixed": 0,
            }

        # By category
        by_category = {}
        for violation in recent:
            cat = violation.category.value
            if cat not in by_category:
                by_category[cat] = {"total": 0, "fixed": 0, "false_positives": 0}
            by_category[cat]["total"] += 1
            if violation.was_fixed:
                by_category[cat]["fixed"] += 1
            if violation.was_false_positive:
                by_category[cat]["false_positives"] += 1

        # By severity
        by_severity = {}
        for violation in recent:
            sev = violation.severity.value
            if sev not in by_severity:
                by_severity[sev] = {"total": 0, "fixed": 0}
            by_severity[sev]["total"] += 1
            if violation.was_fixed:
                by_severity[sev]["fixed"] += 1

        unfixed = sum(1 for v in recent if not v.was_fixed)

        return {
            "total_violations": len(recent),
            "by_category": by_category,
            "by_severity": by_severity,
            "unfixed_count": unfixed,
            "fix_rate": (
                sum(1 for v in recent if v.was_fixed) / len(recent)
                if recent
                else 0.0
            ),
            "false_positive_rate": (
                sum(1 for v in recent if v.was_false_positive) / len(recent)
                if recent
                else 0.0
            ),
        }

    def get_violation_patterns(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/gate/patterns

        Most common violation patterns (what does gate catch most?).
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [v for v in self.violations if v.timestamp >= cutoff]

        if not recent:
            return {"patterns": {}}

        # Most common files
        file_violations = {}
        for violation in recent:
            file = violation.file_path
            if file not in file_violations:
                file_violations[file] = 0
            file_violations[file] += 1

        # Top 10 files with most violations
        top_files = sorted(
            file_violations.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Most common messages
        message_counts = {}
        for violation in recent:
            msg = violation.message
            if msg not in message_counts:
                message_counts[msg] = 0
            message_counts[msg] += 1

        top_messages = sorted(
            message_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "total_violations": len(recent),
            "top_problem_files": [
                {"file": f, "violations": c} for f, c in top_files
            ],
            "top_violation_patterns": [
                {"message": m, "count": c} for m, c in top_messages
            ],
        }

    def get_developer_stats(self, hours: int = 24) -> Dict:
        """
        GET /monitoring/gate/developer-stats

        Per-developer violation statistics.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [v for v in self.violations if v.timestamp >= cutoff]

        if not recent:
            return {"developers": {}}

        # Per developer
        dev_stats = {}
        for violation in recent:
            dev = violation.developer
            if dev not in dev_stats:
                dev_stats[dev] = {
                    "violations": 0,
                    "by_severity": {},
                    "false_positives": 0,
                }
            dev_stats[dev]["violations"] += 1
            sev = violation.severity.value
            dev_stats[dev]["by_severity"][sev] = (
                dev_stats[dev]["by_severity"].get(sev, 0) + 1
            )
            if violation.was_false_positive:
                dev_stats[dev]["false_positives"] += 1

        # Add commit attempt data
        attempts = [a for a in self.commit_attempts if a.timestamp >= cutoff]
        commits_by_dev = {}
        for attempt in attempts:
            dev = attempt.developer
            if dev not in commits_by_dev:
                commits_by_dev[dev] = {"total": 0, "blocked": 0, "bypassed": 0}
            commits_by_dev[dev]["total"] += 1
            if attempt.commit_blocked:
                commits_by_dev[dev]["blocked"] += 1
            if attempt.bypass_attempted:
                commits_by_dev[dev]["bypassed"] += 1

        # Merge stats
        for dev in dev_stats:
            dev_stats[dev]["commit_attempts"] = commits_by_dev.get(dev, {})

        return {
            "developers": dev_stats,
            "worst_offenders": sorted(
                dev_stats.items(),
                key=lambda x: x[1]["violations"],
                reverse=True,
            )[:5],
        }

    def get_false_positive_rate(self) -> Dict:
        """
        GET /monitoring/gate/false-positives

        False positive analysis (gate was wrong).
        """
        false_positives = [v for v in self.violations if v.was_false_positive]

        if not self.violations:
            return {"false_positive_rate": 0.0, "false_positives": []}

        fpr = len(false_positives) / len(self.violations)

        # By category
        by_category = {}
        for fp in false_positives:
            cat = fp.category.value
            if cat not in by_category:
                by_category[cat] = 0
            by_category[cat] += 1

        return {
            "false_positive_rate": fpr,
            "false_positive_count": len(false_positives),
            "by_category": by_category,
            "recent_false_positives": [
                {
                    "violation_id": fp.violation_id,
                    "category": fp.category.value,
                    "message": fp.message,
                    "file": fp.file_path,
                    "timestamp": fp.timestamp.isoformat(),
                }
                for fp in false_positives[-10:]  # Last 10
            ],
        }

    def get_prevention_rate(self) -> Dict:
        """
        GET /monitoring/gate/prevention-rate

        How many issues does gate catch BEFORE production?
        """
        # Issues found by gate
        gate_violations = len(self.violations)

        # Issues that made it to production despite gate
        production_impacts = [
            v for v in self.violations
            if v.production_impact in ["bug", "security", "data_loss", "performance"]
        ]

        # Prevention rate = issues caught / (issues caught + issues escaped)
        issues_escaped = len(production_impacts)

        if gate_violations + issues_escaped == 0:
            prevention_rate = 1.0
        else:
            prevention_rate = gate_violations / (gate_violations + issues_escaped)

        # By severity (how many CRITICAL issues escaped?)
        critical_escapes = [
            v for v in production_impacts
            if v.severity == ViolationSeverity.CRITICAL
        ]

        return {
            "prevention_rate": prevention_rate,
            "issues_caught": gate_violations,
            "issues_escaped": issues_escaped,
            "critical_issues_escaped": len(critical_escapes),
            "escape_impacts": [
                {"impact": v.production_impact, "file": v.file_path, "category": v.category.value}
                for v in critical_escapes[:5]
            ],
        }

    def get_trends(self, days: int = 7) -> Dict:
        """
        GET /monitoring/gate/trends

        Violation trends over time.
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent = [v for v in self.violations if v.timestamp >= cutoff]

        if not recent:
            return {"violations_by_day": {}}

        # Group by day
        by_day = {}
        for violation in recent:
            day = violation.timestamp.date().isoformat()
            if day not in by_day:
                by_day[day] = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
            by_day[day]["total"] += 1
            sev = violation.severity.value
            if sev in by_day[day]:
                by_day[day][sev] += 1

        return {
            "violations_by_day": by_day,
            "trend": (
                "improving" if len(by_day) > 1
                and by_day[max(by_day.keys())]["total"] < by_day[min(by_day.keys())]["total"]
                else "stable" if len(by_day) > 1
                else "unknown"
            ),
        }

    def get_health_summary(self) -> Dict:
        """
        GET /monitoring/gate/health

        Overall gate health and effectiveness.
        """
        return {
            "uptime": (datetime.now() - self.dashboard_started).total_seconds(),
            "total_violations_detected": len(self.violations),
            "total_commit_attempts": len(self.commit_attempts),
            "commits_blocked": sum(1 for a in self.commit_attempts if a.commit_blocked),
            "bypass_attempts": sum(1 for a in self.commit_attempts if a.bypass_attempted),
            "false_positive_rate": self.get_false_positive_rate()["false_positive_rate"],
            "prevention_rate": self.get_prevention_rate()["prevention_rate"],
            "violations_1h": self.get_violation_metrics(hours=1)["total_violations"],
            "violations_24h": self.get_violation_metrics(hours=24)["total_violations"],
        }


# Global instance
_gate_audit_instance: Optional[Phase3GateAuditDashboard] = None


def get_gate_audit_dashboard() -> Phase3GateAuditDashboard:
    """Get or create global gate audit dashboard instance."""
    global _gate_audit_instance
    if _gate_audit_instance is None:
        _gate_audit_instance = Phase3GateAuditDashboard()
    return _gate_audit_instance
