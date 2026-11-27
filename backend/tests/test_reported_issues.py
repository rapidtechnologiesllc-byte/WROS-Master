"""Reported issues (CEO 2026-11-27): every report from the app is tracked in HRMS until it is fixed, laid out like an
issue log with comments; the reports written to the old DEFECTS_LOG.md file are brought in once."""
import pytest

from app.models.reported_issue import ReportedIssue
from app.services import reported_issue_service as issues
from tests import factories as f


def test_a_report_is_tracked_with_summary_and_blocking_means_critical(db):
    reporter = f.user(db, UserName="Asha Rao")
    issue = issues.report(db, reporter, screen="Candidates", description="Schedule button does nothing\nsteps...",
                          severity="LOW", blocking=True)
    assert issue.status == "OPEN" and issue.severity == "CRITICAL" and issue.blocking
    assert issue.summary == "Schedule button does nothing" and issue.reporter_name == "Asha Rao"
    assert issue.reference.startswith("DEFECT-")
    with pytest.raises(issues.IssueRefused):
        issues.report(db, reporter, screen="Candidates", description="  ", severity="LOW", blocking=False)


def test_open_blocking_issues_come_first(db):
    user = f.user(db)
    low = issues.report(db, user, screen="Jobs", description="typo", severity="LOW", blocking=False)
    blocking = issues.report(db, user, screen="Jobs", description="cannot save", severity="MEDIUM", blocking=True)
    fixed = issues.report(db, user, screen="Jobs", description="old", severity="CRITICAL", blocking=False)
    issues.update(db, fixed, user, status="FIXED", resolution="PR #1")
    order = [i.id for i in issues.list_issues(db, user.tenant_id) if i.id in (low.id, blocking.id, fixed.id)]
    assert order == [blocking.id, low.id, fixed.id]


def test_status_changes_need_a_resolution_to_close_and_are_written_to_the_thread(db):
    user = f.user(db, UserName="Fixer")
    assignee = f.user(db, UserName="Dev One")
    issue = issues.report(db, user, screen="P&L", description="totals wrong", severity="HIGH", blocking=False)
    with pytest.raises(issues.IssueRefused):
        issues.update(db, issue, user, status="FIXED", resolution=None)
    issues.assign(db, issue, user, assignee.UserID)
    issues.comment(db, issue, user, "Reproduced on the CEO dashboard")
    issues.update(db, issue, user, status="FIXED", resolution="Fixed in PR #584")
    thread = issues.comments(db, issue.id)
    assert [c.kind for c in thread] == ["CHANGE", "COMMENT", "CHANGE"]
    assert "Dev One" in thread[0].body and "OPEN -> FIXED" in thread[2].body
    assert issue.resolved_by_user_id == user.UserID and issue.resolved_at is not None
    issues.update(db, issue, user, status="OPEN", resolution=None)  # reopened
    assert issue.resolved_at is None


def test_the_old_log_file_is_imported_once(db, tmp_path):
    log = tmp_path / "DEFECTS_LOG.md"
    log.write_text("""# Defect Reports - Production

## [DEFECT-2026-11-20T101500] CRITICAL - Candidates

**Reporter:** Nobody (nobody@nowhere.test)
**Timestamp:** 2026-11-20T10:15:00.123456
**Severity:** CRITICAL
**Blocking Production Function:** Yes
**Screen:** Candidates

**Description:**
Cannot schedule interviews at all

**Status:** OPEN
**Resolution:** Pending review

---
""", encoding="utf-8")
    assert issues.import_legacy_log(db, str(log)) == 1
    assert issues.import_legacy_log(db, str(log)) == 0
    row = db.query(ReportedIssue).filter(ReportedIssue.reference == "DEFECT-2026-11-20T101500").one()
    assert row.blocking and row.severity == "CRITICAL" and row.summary == "Cannot schedule interviews at all"
    assert row.screen == "Candidates" and row.reporter_name == "Nobody"
