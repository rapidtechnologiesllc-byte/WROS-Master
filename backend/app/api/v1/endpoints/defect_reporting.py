"""Reported issues (CEO 2026-11-27): a report from the app (Ask Flash -> Report an Issue) is stored and tracked until it
is fixed, under Admin -> System -> Reported issues (app.services.reported_issue_service). Anyone signed in (my-tasks
view) may report; the "error-logs" permission gates the log: view to see and comment, edit to assign and change status."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.reported_issue import ReportedIssue
from app.models.user import Users
from app.schemas.defect import DefectReportRequest, DefectReportResponse
from app.services import reported_issue_service as issues

router = APIRouter(tags=["Defect Reporting"])


class ReportedIssueItem(BaseModel):
    id: int
    reference: str
    screen: str
    summary: str
    issue_type: str
    description: str
    severity: str
    blocking: bool
    status: str
    reporter_name: Optional[str] = None
    assignee_user_id: Optional[str] = None
    assignee_name: Optional[str] = None
    resolution: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None


class IssueComment(BaseModel):
    id: int
    author_name: Optional[str] = None
    body: str
    kind: str
    created_at: Optional[str] = None


class ReportedIssueDetail(ReportedIssueItem):
    comments: List[IssueComment] = []


class CommentRequest(BaseModel):
    body: str


class ReportedIssueList(BaseModel):
    issues: List[ReportedIssueItem]
    open_count: int


class IssueUpdateRequest(BaseModel):
    status: Optional[str] = None
    resolution: Optional[str] = None
    # "" unassigns; leave out to keep the assignee
    assignee_user_id: Optional[str] = None


def _iso(value) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


def _item(db: Session, issue: ReportedIssue, cls=ReportedIssueItem, **extra):
    assignee = db.get(Users, issue.assignee_user_id) if issue.assignee_user_id else None
    return cls(
        id=issue.id, reference=issue.reference, screen=issue.screen, summary=issue.summary,
        issue_type=issue.issue_type, description=issue.description, severity=issue.severity,
        blocking=issue.blocking, status=issue.status, reporter_name=issue.reporter_name,
        assignee_user_id=issue.assignee_user_id,
        assignee_name=(assignee.UserName or assignee.UserEmail) if assignee else None,
        resolution=issue.resolution, created_at=_iso(issue.created_at), updated_at=_iso(issue.updated_at),
        resolved_at=_iso(issue.resolved_at), **extra)


def _visible_issue(db: Session, issue_id: int, user: Users) -> ReportedIssue:
    issue = db.get(ReportedIssue, issue_id)
    if issue is None or issue.tenant_id not in (None, user.tenant_id):
        raise HTTPException(status_code=404, detail="Reported issue not found")
    return issue


@router.post(
    "/defects/report",
    response_model=DefectReportResponse,
    # anyone signed in may report (the button is on every screen); seeing and working the log stays with error-logs.
    # Until 2026-11-27 this needed error-logs create, which only administrators hold: staff reports were refused.
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
)
def report_defect(report: DefectReportRequest, db: Session = Depends(get_db),
                  current_user: Users = Depends(get_current_internal_user)):
    """Report an issue: stored and tracked until it is fixed."""
    try:
        issue = issues.report(db, current_user, screen=report.affected_screen, description=report.description,
                              severity=report.severity, blocking=report.blocking_production,
                              summary=report.summary, issue_type=report.issue_type)
    except issues.IssueRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return DefectReportResponse(defect_id=issue.reference, timestamp=issue.created_at.isoformat() + "Z",
                                message="Thanks: your report is logged and will be tracked until it is fixed.")


@router.get(
    "/defects",
    response_model=ReportedIssueList,
    dependencies=[Depends(require_resource_permission("error-logs", "view"))],
)
def list_reported_issues(status: Optional[str] = None, db: Session = Depends(get_db),
                         current_user: Users = Depends(get_current_internal_user)):
    """Every reported issue of the caller's tenant: open ones first (blocking, most severe, oldest)."""
    rows = issues.list_issues(db, current_user.tenant_id, status=status)
    return ReportedIssueList(issues=[_item(db, i) for i in rows],
                             open_count=sum(1 for i in rows if i.status not in ("FIXED", "WONT_FIX", "DUPLICATE")))


@router.put(
    "/defects/{issue_id}",
    response_model=ReportedIssueItem,
    dependencies=[Depends(require_resource_permission("error-logs", "edit"))],
)
def update_reported_issue(issue_id: int, body: IssueUpdateRequest, db: Session = Depends(get_db),
                          current_user: Users = Depends(get_current_internal_user)):
    issue = _visible_issue(db, issue_id, current_user)
    try:
        if body.assignee_user_id is not None:
            issues.assign(db, issue, current_user, body.assignee_user_id)
        if body.status is not None:
            issues.update(db, issue, current_user, status=body.status, resolution=body.resolution)
        elif body.resolution is not None:
            issue.resolution = body.resolution.strip() or None
    except issues.IssueRefused as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return _item(db, issue)


def _detail(db: Session, issue: ReportedIssue) -> ReportedIssueDetail:
    thread = [IssueComment(id=c.id, author_name=c.author_name, body=c.body, kind=c.kind, created_at=_iso(c.created_at))
              for c in issues.comments(db, issue.id)]
    return _item(db, issue, ReportedIssueDetail, comments=thread)


@router.get(
    "/defects/{issue_id}",
    response_model=ReportedIssueDetail,
    dependencies=[Depends(require_resource_permission("error-logs", "view"))],
)
def get_reported_issue(issue_id: int, db: Session = Depends(get_db),
                       current_user: Users = Depends(get_current_internal_user)):
    return _detail(db, _visible_issue(db, issue_id, current_user))


@router.post(
    "/defects/{issue_id}/comments",
    response_model=ReportedIssueDetail,
    dependencies=[Depends(require_resource_permission("error-logs", "view"))],
)
def comment_on_reported_issue(issue_id: int, body: CommentRequest, db: Session = Depends(get_db),
                              current_user: Users = Depends(get_current_internal_user)):
    issue = _visible_issue(db, issue_id, current_user)
    try:
        issues.comment(db, issue, current_user, body.body)
    except issues.IssueRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return _detail(db, issue)
