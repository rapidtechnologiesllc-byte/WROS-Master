"""Reported issues (CEO 2026-11-27): record every report, list them, move them through their status, and bring in the
reports written to the old DEFECTS_LOG.md file before this existed."""
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.reported_issue import (CLOSED_STATUSES, ISSUE_SEVERITIES, ISSUE_STATUSES, ISSUE_TYPES, ReportedIssue,
                                       ReportedIssueComment)
from app.models.user import Users

logger = logging.getLogger(__name__)

# where the old endpoint appended reports (backend/DEFECTS_LOG.md)
LEGACY_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "DEFECTS_LOG.md")


class IssueRefused(ValueError):
    """The change is not allowed; the message says why."""


def summary_of(description: str) -> str:
    first = (description or "").strip().splitlines()[0] if (description or "").strip() else "(no description)"
    return first[:252] + "..." if len(first) > 255 else first


def _reference(now: datetime) -> str:
    """Unique even for two reports in the same clock tick (Windows ticks are coarse)."""
    import secrets

    return f"DEFECT-{now.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3).upper()}"


def report(db: Session, user: Users, *, screen: str, description: str, severity: str, blocking: bool,
           summary: Optional[str] = None, issue_type: str = "BUG") -> ReportedIssue:
    if not (description or "").strip():
        raise IssueRefused("Say what went wrong")
    if not (screen or "").strip():
        raise IssueRefused("Pick the screen with the issue")
    severity = "CRITICAL" if blocking else (severity or "MEDIUM").upper()
    if severity not in ISSUE_SEVERITIES:
        raise IssueRefused(f"Severity must be one of {', '.join(ISSUE_SEVERITIES)}")
    issue_type = (issue_type or "BUG").upper()
    if issue_type not in ISSUE_TYPES:
        raise IssueRefused(f"Type must be one of {', '.join(ISSUE_TYPES)}")
    issue = ReportedIssue(reference=_reference(datetime.utcnow()), tenant_id=user.tenant_id,
                          summary=(summary or "").strip()[:255] or summary_of(description), issue_type=issue_type,
                          reported_by_user_id=user.UserID, reporter_name=user.UserName or user.UserEmail,
                          screen=screen.strip()[:255], description=description.strip(), severity=severity,
                          blocking=bool(blocking), status="OPEN")
    db.add(issue)
    db.flush()
    logger.warning(f"[ReportedIssue] {issue.reference} {severity} on {issue.screen} by {user.UserID}"
                   + (" (BLOCKING production)" if blocking else ""))
    return issue


def list_issues(db: Session, tenant_id: Optional[int], *, status: Optional[str] = None,
                open_only: bool = False) -> List[ReportedIssue]:
    query = db.query(ReportedIssue)
    if tenant_id is not None:
        query = query.filter((ReportedIssue.tenant_id == tenant_id) | ReportedIssue.tenant_id.is_(None))
    if status:
        query = query.filter(ReportedIssue.status == status)
    elif open_only:
        query = query.filter(ReportedIssue.status.notin_(CLOSED_STATUSES))
    # blocking and most severe first, then oldest first: the order they are tackled in
    severity_rank = {s: i for i, s in enumerate(reversed(ISSUE_SEVERITIES))}
    issues = query.all()
    return sorted(issues, key=lambda i: (i.status in CLOSED_STATUSES, not i.blocking,
                                         severity_rank.get(i.severity, 9), i.created_at or datetime.min))


def comment(db: Session, issue: ReportedIssue, user: Optional[Users], body: str, kind: str = "COMMENT"):
    if not (body or "").strip():
        raise IssueRefused("Write the comment")
    row = ReportedIssueComment(issue_id=issue.id, author_user_id=user.UserID if user else None,
                               author_name=(user.UserName or user.UserEmail) if user else "System", body=body.strip(),
                               kind=kind)
    db.add(row)
    issue.updated_at = datetime.utcnow()
    db.flush()
    return row


def comments(db: Session, issue_id: int) -> list:
    return db.query(ReportedIssueComment).filter(ReportedIssueComment.issue_id == issue_id)         .order_by(ReportedIssueComment.created_at, ReportedIssueComment.id).all()


def assign(db: Session, issue: ReportedIssue, user: Users, assignee_user_id: Optional[str]) -> ReportedIssue:
    assignee = None
    if assignee_user_id:
        assignee = db.query(Users).filter(Users.UserID == assignee_user_id, Users.terminated_at.is_(None),
                                          Users.tenant_id == user.tenant_id).first()
        if assignee is None:
            raise IssueRefused("Pick an active person of your organisation")
    if (issue.assignee_user_id or None) != (assignee_user_id or None):
        issue.assignee_user_id = assignee_user_id or None
        comment(db, issue, user, f"Assigned to {assignee.UserName or assignee.UserEmail}" if assignee else "Unassigned",
                kind="CHANGE")
    return issue


def update(db: Session, issue: ReportedIssue, user: Users, *, status: str, resolution: Optional[str]) -> ReportedIssue:
    if status not in ISSUE_STATUSES:
        raise IssueRefused(f"Status must be one of {', '.join(ISSUE_STATUSES)}")
    if status in CLOSED_STATUSES and not (resolution or issue.resolution or "").strip():
        raise IssueRefused("Say what was done (or why not), and where: the PR or commit")
    previous = issue.status
    issue.status = status
    if previous != status:
        comment(db, issue, user, f"Status {previous} -> {status}" + (f": {resolution.strip()}" if resolution else ""),
                kind="CHANGE")
    if resolution is not None:
        issue.resolution = resolution.strip() or None
    if status in CLOSED_STATUSES:
        issue.resolved_by_user_id, issue.resolved_at = user.UserID, datetime.utcnow()
    else:
        issue.resolved_by_user_id = issue.resolved_at = None
    db.flush()
    return issue


_ENTRY = re.compile(r"^## \[(?P<ref>DEFECT-[^\]]+)\] (?P<severity>\w+) - (?P<screen>.*)$", re.MULTILINE)


def import_legacy_log(db: Session, path: str = LEGACY_LOG_FILE) -> int:
    """The reports the old endpoint appended to DEFECTS_LOG.md, once each (by reference). Reporter emails in the
    file are not copied; the reporter is matched to their login by that email when it exists."""
    if not os.path.exists(path):
        return 0
    text = open(path, encoding="utf-8", errors="replace").read()
    have = {row[0] for row in db.query(ReportedIssue.reference)}
    matches = list(_ENTRY.finditer(text))
    added = 0
    for index, match in enumerate(matches):
        ref = match.group("ref")
        if ref in have:
            continue
        body = text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]

        def field(name):
            found = re.search(rf"\*\*{name}:\*\*\s*(.*)", body)
            return found.group(1).strip() if found else ""

        description = body.split("**Description:**", 1)[-1].split("**Status:**", 1)[0].strip()
        email = re.search(r"\(([^()\s]+@[^()\s]+)\)", field("Reporter"))
        user = db.query(Users).filter(Users.UserEmail == email.group(1)).first() if email else None
        try:
            created = datetime.fromisoformat(field("Timestamp"))
        except ValueError:
            created = None
        severity = match.group("severity").upper()
        extra = {"created_at": created} if created else {}
        db.add(ReportedIssue(
            **extra, reference=ref, tenant_id=user.tenant_id if user else None,
            reported_by_user_id=user.UserID if user else None,
            reporter_name=(user.UserName if user else field("Reporter").split("(")[0].strip()) or None,
            screen=match.group("screen").strip()[:255] or "Other", description=description or "(no description)",
            summary=summary_of(description), issue_type="BUG",
            severity=severity if severity in ISSUE_SEVERITIES else "MEDIUM",
            blocking=field("Blocking Production Function").lower().startswith("yes"),
            status="OPEN"))
        added += 1
    if added:
        db.flush()
    return added
