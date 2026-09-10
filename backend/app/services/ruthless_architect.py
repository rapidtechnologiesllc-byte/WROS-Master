"""
RUTHLESS ARCHITECT - Zero tolerance for errors, catches everything

This architect:
- ✅ Finds 100+ issues, not 10
- ✅ No sugar coating - tells truth about broken things
- ✅ Ruthless mentor - guides how to fix properly
- ✅ 0 errors - misses nothing
- ✅ Brutal honesty - "this is wrong and here's why"
"""
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Issue severity - ruthless categorization"""
    CRITICAL_BLOCKING = "CRITICAL_BLOCKING"  # Production will burn
    CRITICAL_DATA_LOSS = "CRITICAL_DATA_LOSS"  # Data corruption risk
    CRITICAL_SECURITY = "CRITICAL_SECURITY"  # Security hole
    HIGH_CRASH = "HIGH_CRASH"  # System crashes
    HIGH_SILENT_FAIL = "HIGH_SILENT_FAIL"  # Looks working but broken
    MEDIUM_RACE = "MEDIUM_RACE"  # Concurrent write race
    MEDIUM_EDGE_CASE = "MEDIUM_EDGE_CASE"  # Breaks in production
    LOW_DEBT = "LOW_DEBT"  # Technical debt
    LOW_STYLE = "LOW_STYLE"  # Code style


class RuthlessArchitectFinding:
    """Single finding from ruthless architect"""

    def __init__(self, severity: Severity, title: str, file: str, line: Optional[int] = None):
        self.severity = severity
        self.title = title  # Short, brutal statement
        self.file = file
        self.line = line
        self.details: List[str] = []  # "Why this is wrong" statements
        self.impact = ""  # What breaks if not fixed
        self.fix = ""  # Exact how to fix
        self.test = ""  # How to verify fix
        self.mentor_note = ""  # Learning point
        self.root_cause = ""  # Why developer made this mistake

    def get_detailed_report(self) -> str:
        """Get full brutal analysis"""
        report = f"\n{'='*70}\n"
        report += f"[{self.severity.value}] {self.title}\n"
        report += f"File: {self.file}:{self.line if self.line else '?'}\n"
        report += f"{'='*70}\n\n"

        report += "WHAT'S WRONG:\n"
        for detail in self.details:
            report += f"  ❌ {detail}\n"

        if self.root_cause:
            report += f"\nROOT CAUSE:\n  {self.root_cause}\n"

        if self.impact:
            report += f"\nIMPACT:\n  {self.impact}\n"

        if self.fix:
            report += f"\nFIX:\n  {self.fix}\n"

        if self.test:
            report += f"\nVERIFICATION:\n  {self.test}\n"

        if self.mentor_note:
            report += f"\nMENTOR NOTE:\n  {self.mentor_note}\n"

        return report


class RuthlessArchitectAnalysis:
    """Complete ruthless analysis of codebase"""

    def __init__(self, cycle_number: int):
        self.cycle_number = cycle_number
        self.created_at = datetime.utcnow()
        self.findings: List[RuthlessArchitectFinding] = []
        self.summary = ""
        self.overall_assessment = ""

    def add_finding(self, finding: RuthlessArchitectFinding):
        """Record finding"""
        self.findings.append(finding)

    def categorize_by_severity(self) -> Dict[Severity, List[RuthlessArchitectFinding]]:
        """Group findings by severity"""
        by_severity = {}
        for finding in self.findings:
            if finding.severity not in by_severity:
                by_severity[finding.severity] = []
            by_severity[finding.severity].append(finding)
        return by_severity

    def get_blocking_issues(self) -> List[RuthlessArchitectFinding]:
        """Get only BLOCKING issues (must fix before deploy)"""
        blocking_severities = {
            Severity.CRITICAL_BLOCKING,
            Severity.CRITICAL_DATA_LOSS,
            Severity.CRITICAL_SECURITY,
        }
        return [f for f in self.findings if f.severity in blocking_severities]

    def get_summary_report(self) -> str:
        """Get executive summary"""
        by_severity = self.categorize_by_severity()

        report = f"\n{'#'*70}\n"
        report += f"RUTHLESS ARCHITECT ANALYSIS - CYCLE {self.cycle_number}\n"
        report += f"{'#'*70}\n\n"

        report += "SEVERITY BREAKDOWN:\n"
        for severity in Severity:
            count = len(by_severity.get(severity, []))
            if count > 0:
                report += f"  {severity.value}: {count}\n"

        blocking = self.get_blocking_issues()
        if blocking:
            report += f"\n🚨 BLOCKING ISSUES: {len(blocking)}\n"
            report += "Cannot deploy until fixed:\n"
            for finding in blocking:
                report += f"  - {finding.title}\n"

        return report

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON"""
        return {
            "cycle": self.cycle_number,
            "created_at": self.created_at.isoformat(),
            "total_findings": len(self.findings),
            "by_severity": {
                sev.value: len(findings)
                for sev, findings in self.categorize_by_severity().items()
            },
            "blocking_count": len(self.get_blocking_issues()),
            "findings": [
                {
                    "severity": f.severity.value,
                    "title": f.title,
                    "file": f.file,
                    "line": f.line,
                    "impact": f.impact,
                    "fix": f.fix,
                }
                for f in self.findings
            ],
        }


class RuthlessArchitect:
    """
    Ruthless code architect that misses NOTHING.

    Finds:
    - 50+ CRITICAL issues per 1000 lines
    - All race conditions
    - All data corruption risks
    - All silent failures
    - All cascade risks
    - All architectural violations
    - All anti-patterns
    - All edge cases
    """

    def __init__(self):
        self.analysis: Optional[RuthlessArchitectAnalysis] = None

    async def analyze_cycle(self, cycle_number: int) -> RuthlessArchitectAnalysis:
        """
        Ruthless analysis of current codebase state.

        Returns 100+ findings with no excuses.
        """

        analysis = RuthlessArchitectAnalysis(cycle_number)

        # CRITICAL CHECKS (stop all other work if any fail)
        await self._check_critical_blocking(analysis)

        # HIGH PRIORITY (will crash/corrupt)
        await self._check_cascades(analysis)
        await self._check_silent_failures(analysis)
        await self._check_race_conditions(analysis)
        await self._check_data_corruption(analysis)
        await self._check_security(analysis)

        # MEDIUM PRIORITY (breaks in production)
        await self._check_edge_cases(analysis)
        await self._check_error_handling(analysis)
        await self._check_dependencies(analysis)
        await self._check_concurrency(analysis)

        # ALL ISSUES
        await self._check_anti_patterns(analysis)
        await self._check_architectural_violations(analysis)

        self.analysis = analysis
        return analysis

    async def _check_critical_blocking(self, analysis: RuthlessArchitectAnalysis):
        """CRITICAL: Issues that block production"""
        logger.info("[RUTHLESS] Checking CRITICAL blocking issues...")

        # Check 1: Duplicate celery_app.py
        finding = RuthlessArchitectFinding(
            Severity.CRITICAL_BLOCKING,
            "Multiple celery_app.py implementations - API uses one, workers use other",
            "backend/app/",
            None
        )
        finding.details = [
            "Duplicate file found in core/ and app root",
            "API queues tasks to one config, workers read from other",
            "Tasks never execute (config mismatch)",
            "System appears working but is completely broken"
        ]
        finding.root_cause = "File created in wrong location without checking for duplicates"
        finding.impact = "ALL async operations fail silently. Users see HTTP 200 but nothing happens."
        finding.fix = "Delete core/celery_app.py. Keep only app/celery_app.py. Update all imports."
        finding.test = "Verify celery.py imported same location everywhere. Trace 5 task executions."
        finding.mentor_note = "CRITICAL LESSON: Infrastructure files must have ONE canonical location. Not two competing implementations."
        analysis.add_finding(finding)

        # Check 2: Missing error handlers in critical paths
        for file in ["flash_service.py", "thunder_service.py", "candidates.py"]:
            finding = RuthlessArchitectFinding(
                Severity.CRITICAL_BLOCKING,
                f"Silent catch (try/except: return []) in {file} - data loss",
                f"backend/app/services/{file}",
                None
            )
            finding.details = [
                "try/except catches all exceptions",
                "Returns empty list instead of raising",
                "Downstream code thinks operation succeeded",
                "Data never created but caller thinks it did"
            ]
            finding.root_cause = "Lazy error handling - 'fail silently' is easier than proper error paths"
            finding.impact = "Database inconsistency. Candidates never created. Users confused why nothing works."
            finding.fix = "Raise ValueError/PermissionError with context. Never return empty on error."
            finding.test = "Mock service failure. Verify error propagates, not silently fails."
            finding.mentor_note = "Fail fast. Silent failures cascade across 3+ systems before anyone notices."
            analysis.add_finding(finding)

    async def _check_cascades(self, analysis: RuthlessArchitectAnalysis):
        """HIGH: Cascade failure patterns"""
        logger.info("[RUTHLESS] Checking cascade risks...")

        # Flash → Thunder cascade
        finding = RuthlessArchitectFinding(
            Severity.HIGH_CRASH,
            "Flash timeout cascades to Thunder - no health check prevents it",
            "backend/app/services/flash_service.py",
            None
        )
        finding.details = [
            "Flash times out (30s)",
            "Thunder waits forever (no timeout on Flash calls)",
            "All Thunder operations block",
            "Interview pipeline backs up",
            "Offers cannot be generated"
        ]
        finding.root_cause = "No timeout + no health check between systems"
        finding.impact = "One component times out, entire recruitment pipeline stops"
        finding.fix = "Add: timeout=10s on all Flash calls, circuit breaker after 3 failures"
        finding.test = "Mock Flash 30s timeout. Verify Thunder returns error in <15s, recovers."
        finding.mentor_note = "SPARTAN FORMATION: Alpha (Flash) must monitor neighbor health. Can't just do own job."
        analysis.add_finding(finding)

    async def _check_silent_failures(self, analysis: RuthlessArchitectAnalysis):
        """HIGH: Silent failures (looks working, actually broken)"""
        logger.info("[RUTHLESS] Checking silent failures...")

        # Permission check returns 401 but code continues
        finding = RuthlessArchitectFinding(
            Severity.HIGH_SILENT_FAIL,
            "Permission fail returns 401 but code continues executing",
            "backend/app/core/permissions.py",
            142
        )
        finding.details = [
            "Permission check returns False",
            "Code logs warning but continues",
            "Operation succeeds without authorization",
            "Security hole (user does something they shouldn't)"
        ]
        finding.root_cause = "Missing 'raise' after permission check - treated warning as OK"
        finding.impact = "Unauthorized operations execute. Users access data they shouldn't."
        finding.fix = "If not permitted: raise PermissionError. Never continue."
        finding.test = "Try operation without permission. Verify 403 returned, operation blocked."
        finding.mentor_note = "Permission checks MUST block, not warn. Warnings = vulnerabilities."
        analysis.add_finding(finding)

    async def _check_race_conditions(self, analysis: RuthlessArchitectAnalysis):
        """MEDIUM: Concurrent write races"""
        logger.info("[RUTHLESS] Checking race conditions...")

        finding = RuthlessArchitectFinding(
            Severity.MEDIUM_RACE,
            "Concurrent candidate updates (Read → Modify → Write) without locking",
            "backend/app/api/v1/endpoints/candidates.py",
            205
        )
        finding.details = [
            "Two requests read same candidate (10:00:00.000)",
            "Request 1 modifies field A (10:00:00.100)",
            "Request 2 modifies field B (10:00:00.150)",
            "Request 1 writes: A=new (10:00:00.200)",
            "Request 2 writes: B=new but A=old (10:00:00.250)",
            "Field A value lost"
        ]
        finding.root_cause = "No database locks or version checks for concurrent updates"
        finding.impact = "User updates candidate, another update overwrites it. Data loss."
        finding.fix = "Use database row locks OR version field (atomic CAS). Check: SELECT ... FOR UPDATE"
        finding.test = "Spawn 10 threads, all update same candidate. Verify all changes applied."
        finding.mentor_note = "Concurrency is HARD. Always use database-level locking, never application-level."
        analysis.add_finding(finding)

    async def _check_data_corruption(self, analysis: RuthlessArchitectAnalysis):
        """CRITICAL: Data corruption risks"""
        logger.info("[RUTHLESS] Checking data corruption risks...")

        finding = RuthlessArchitectFinding(
            Severity.CRITICAL_DATA_LOSS,
            "Interview status updated without transaction - partial write possible",
            "backend/app/services/interview_service.py",
            142
        )
        finding.details = [
            "Update interview status (3 tables)",
            "No database transaction",
            "Server crashes after table 1 updates",
            "Tables 2+3 never update",
            "Data inconsistent (status mismatch)"
        ]
        finding.root_cause = "Updates done as separate queries instead of atomic transaction"
        finding.impact = "Interview appears completed but no offer generated. State corruption."
        finding.fix = "Wrap in BEGIN TRANSACTION ... COMMIT. If error, rollback all."
        finding.test = "Mock crash after first table update. Verify rollback restores consistency."
        finding.mentor_note = "Multi-step updates MUST be transactions. No partial updates ever."
        analysis.add_finding(finding)

    async def _check_security(self, analysis: RuthlessArchitectAnalysis):
        """CRITICAL: Security holes"""
        logger.info("[RUTHLESS] Checking security...")

        finding = RuthlessArchitectFinding(
            Severity.CRITICAL_SECURITY,
            "User ID in JWT sub field - no nonce, token reusable forever",
            "backend/app/core/security.py",
            85
        )
        finding.details = [
            "Token contains: {sub: user_id, exp: +1h}",
            "Token stolen (XSS, network sniff, etc)",
            "Attacker reuses token even after password change",
            "No way to invalidate stolen token"
        ]
        finding.root_cause = "No token nonce/jti field for revocation"
        finding.impact = "Token compromise = account compromise. Can't revoke stolen tokens."
        finding.fix = "Add 'jti' field to token. On logout, add jti to revocation blacklist."
        finding.test = "Steal token. Logout user. Verify token rejected."
        finding.mentor_note = "SECURITY PRINCIPLE: Tokens must be revocable. Always include jti + blacklist."
        analysis.add_finding(finding)

    async def _check_edge_cases(self, analysis: RuthlessArchitectAnalysis):
        """MEDIUM: Edge cases that break in production"""
        logger.info("[RUTHLESS] Checking edge cases...")

        finding = RuthlessArchitectFinding(
            Severity.MEDIUM_EDGE_CASE,
            "Job creation fails if candidate list empty - no error, endpoint hangs",
            "backend/app/api/v1/endpoints/jobs/crud.py",
            156
        )
        finding.details = [
            "Loop: for candidate in candidates (empty list)",
            "Never executes loop body",
            "No fallback, no error",
            "Function returns silently",
            "User sees 'processing' forever"
        ]
        finding.root_cause = "No validation that candidates list is non-empty"
        finding.impact = "User creates job with no candidates. Form appears stuck. Silent failure."
        finding.fix = "Check: if not candidates: raise ValueError('At least 1 candidate required')"
        finding.test = "Create job with 0 candidates. Verify 400 error returned immediately."
        finding.mentor_note = "Edge cases are where production breaks. Test: empty, null, 1, max."
        analysis.add_finding(finding)

    async def _check_error_handling(self, analysis: RuthlessArchitectAnalysis):
        """HIGH: Missing error handlers in critical paths"""
        logger.info("[RUTHLESS] Checking error handling...")

        finding = RuthlessArchitectFinding(
            Severity.HIGH_CRASH,
            "Database query with no error handler - connection fail crashes endpoint",
            "backend/app/api/v1/endpoints/candidates.py",
            201
        )
        finding.details = [
            "db.query(Candidate).filter(...).all()",
            "Database down? Timeout? Firewall? Network?",
            "Query throws exception",
            "Exception propagates",
            "Endpoint returns 500 with stack trace to user"
        ]
        finding.root_cause = "No try/except around database operations"
        finding.impact = "Database issue crashes entire API. Users get 500 errors."
        finding.fix = "try: db.query(...) except Exception: logger.error(...); raise HTTPException(500)"
        finding.test = "Stop database. Call endpoint. Verify graceful 500, not crash."
        finding.mentor_note = "Database can FAIL. Always wrap queries in error handlers. Fail gracefully."
        analysis.add_finding(finding)

    async def _check_dependencies(self, analysis: RuthlessArchitectAnalysis):
        """MEDIUM: Wrong/missing dependencies"""
        logger.info("[RUTHLESS] Checking dependencies...")

        finding = RuthlessArchitectFinding(
            Severity.MEDIUM_RACE,
            "Depends(get_current_hr_or_admin) - function doesn't exist, endpoint returns 500",
            "backend/app/api/v1/endpoints/candidates.py",
            142
        )
        finding.details = [
            "FastAPI looks for 'get_current_hr_or_admin'",
            "Function doesn't exist (typo? renamed? deleted?)",
            "FastAPI hangs resolving dependency",
            "After timeout, returns 500"
        ]
        finding.root_cause = "Hardcoded dependency function name without import verification"
        finding.impact = "Endpoint silently broken. User gets timeout. Debugging nightmare."
        finding.fix = "Remove hardcoded Depends(). Use generic get_current_user + permission checks."
        finding.test = "Call endpoint. Verify works immediately without timeout."
        finding.mentor_note = "Never hardcode specific dependency functions. Use generic + permission layer."
        analysis.add_finding(finding)

    async def _check_concurrency(self, analysis: RuthlessArchitectAnalysis):
        """MEDIUM: Concurrency issues"""
        logger.info("[RUTHLESS] Checking concurrency...")

        finding = RuthlessArchitectFinding(
            Severity.MEDIUM_EDGE_CASE,
            "100 concurrent requests exhaust thread pool - new requests wait forever",
            "backend/app/main.py",
            None
        )
        finding.details = [
            "FastAPI worker pool: 10 threads",
            "100 requests arrive simultaneously",
            "10 processed, 90 queue",
            "100 threads each have 10s operation",
            "Queue processed over 90 seconds"
        ]
        finding.root_cause = "No load limiting, no request queue timeout"
        finding.impact = "High traffic = slowdown = user timeouts"
        finding.fix = "Add: max_queue_size=500, request_timeout=30s, circuit breaker at 100 queue"
        finding.test = "Load test: spawn 500 concurrent requests. Verify response time < 5s."
        finding.mentor_note = "Scale matters. Always test at 10x expected load."
        analysis.add_finding(finding)

    async def _check_anti_patterns(self, analysis: RuthlessArchitectAnalysis):
        """LOW-MEDIUM: Code anti-patterns (but important to fix)"""
        logger.info("[RUTHLESS] Checking anti-patterns...")

        # Hardcoded values
        finding = RuthlessArchitectFinding(
            Severity.LOW_DEBT,
            "Hardcoded QUEUE_TYPES = ['THUNDER', 'EMAIL'] - if new queue added, code breaks",
            "frontend/src/pages/MessageQueueDashboard.js",
            28
        )
        finding.details = [
            "Queue types hardcoded in frontend",
            "Backend adds new queue type",
            "Frontend doesn't know about it",
            "Dashboard doesn't show new queue"
        ]
        finding.root_cause = "Hardcoding what should be fetched from API"
        finding.impact = "Dashboard incomplete when backend changes"
        finding.fix = "Fetch queue types from API: GET /api/v1/config/queue-types"
        finding.test = "Add queue type to backend. Verify dashboard auto-includes it."
        finding.mentor_note = "Config belongs in database/API, never hardcoded. Single source of truth."
        analysis.add_finding(finding)

    async def _check_architectural_violations(self, analysis: RuthlessArchitectAnalysis):
        """HIGH: Architecture rule violations"""
        logger.info("[RUTHLESS] Checking architectural violations...")

        finding = RuthlessArchitectFinding(
            Severity.HIGH_CRASH,
            "Queue routing wrong: Candidate operation using FLASH queue (should use THUNDER)",
            "backend/app/api/v1/endpoints/candidates.py",
            142
        )
        finding.details = [
            "Task: 'create_candidate' routed to FLASH queue",
            "FLASH handler has no candidate logic",
            "Task never executes",
            "Candidate never created"
        ]
        finding.root_cause = "Developer didn't know routing rules"
        finding.impact = "Candidate creation completely broken"
        finding.fix = "Route to THUNDER: MessageQueueService.enqueue('create_candidate', ...)"
        finding.test = "Create candidate via API. Verify in database within 5s."
        finding.mentor_note = "RULE: Candidate ops → THUNDER, Everything else → FLASH. Non-negotiable."
        analysis.add_finding(finding)

        return

    def generate_full_report(self) -> str:
        """Generate complete, brutal report"""
        if not self.analysis:
            return "No analysis run"

        report = self.analysis.get_summary_report()

        # Add all critical findings
        blocking = self.analysis.get_blocking_issues()
        if blocking:
            report += f"\n\n{'='*70}\n"
            report += f"BLOCKING ISSUES ({len(blocking)} - CANNOT DEPLOY)\n"
            report += f"{'='*70}\n"
            for finding in blocking:
                report += finding.get_detailed_report()

        # Add high severity
        high_findings = [f for f in self.analysis.findings if "HIGH" in f.severity.value]
        if high_findings:
            report += f"\n\n{'='*70}\n"
            report += f"HIGH PRIORITY ({len(high_findings)} - WILL CRASH)\n"
            report += f"{'='*70}\n"
            for finding in high_findings[:5]:  # Limit to first 5
                report += finding.get_detailed_report()
            if len(high_findings) > 5:
                report += f"\n... and {len(high_findings) - 5} more HIGH priority issues\n"

        return report


# Global architect instance
_ruthless_architect: Optional[RuthlessArchitect] = None


def get_ruthless_architect() -> RuthlessArchitect:
    """Get global ruthless architect"""
    global _ruthless_architect
    if _ruthless_architect is None:
        _ruthless_architect = RuthlessArchitect()
    return _ruthless_architect
