"""Employee performance (CEO 2026-10-24; models in app.models.performance).

Reviews
- Who is reviewed: everyone employed or on leave (bench and HTD included); not before joining, not
  while serving notice, not after exit.
- Cadence: the reporting manager every PERF_REVIEW_MANAGER_DAYS (periods counted from the joining
  date), the BU head every calendar month, the partner every calendar quarter. The reviewer is read
  at the time: manager from the org chart, BU head of the employee's BU and company, the BU's partner.
- The daily job (run_performance_reviews) opens the current period's review with a task for the
  reviewer (due at the period end), books the Teams meeting in the period's last working days
  (PERF_REVIEW_TEAMS_ENABLED; recorded automatically), pulls the recording from Teams after the
  meeting (PERF_REVIEW_FETCH_RECORDINGS) and marks reviews not written up by their due date MISSED.

Who sees what (authority from the org chart and the role template's function only)
- the reporting chain: every manager above the employee in the org chart, their BU head and partner
- HR: anyone in the HR function
- a review: its chain and HR; the employee only once it is completed and shared with them
  (visibility EMPLOYEE_AND_CHAIN). Peers never see reviews.
- peer feedback: praise -- everyone; feedback -- the employee, the chain and HR. An anonymous
  author is shown to HR only (and to the author).
- internal notes: the chain and HR only.
"""
import logging
import os
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core import authority
from app.core.config import settings
from app.models.employee import Employee
from app.models.performance import PeerFeedback, PerformanceNote, PerformanceReview
from app.models.user import Users

logger = logging.getLogger(__name__)

REVIEWED_STATUSES = ("ACTIVE", "BENCH", "ALLOCATED", "ON_LEAVE", "SPECIALITY_READY", "PERFORMANCE_MANAGED")
LEVEL_LABEL = {"MANAGER": "Reporting manager", "BU_HEAD": "BU head", "PARTNER": "Partner"}
MAX_CHAIN_DEPTH = 20


class PerformanceRefused(ValueError):
    pass


# --- periods and reviewers ---------------------------------------------------------------------

def period(level: str, employee: Employee, today: date) -> Tuple[date, date]:
    """The review period containing today for this level."""
    if level == "MANAGER":
        length = settings.PERF_REVIEW_MANAGER_DAYS
        anchor = employee.joining_date
        start = anchor + timedelta(days=((today - anchor).days // length) * length)
        return start, start + timedelta(days=length - 1)
    if level == "BU_HEAD":
        return today.replace(day=1), today.replace(day=monthrange(today.year, today.month)[1])
    quarter_first_month = 3 * ((today.month - 1) // 3) + 1
    start = date(today.year, quarter_first_month, 1)
    last_month = quarter_first_month + 2
    return start, date(today.year, last_month, monthrange(today.year, last_month)[1])


def reviewer_for(db: Session, level: str, employee: Employee) -> Optional[Users]:
    from app.models.business_unit import BusinessUnit
    from app.services.bu_leadership import head_user_id
    from app.services.org_structure_service import manager_user_for

    if level == "MANAGER":
        return manager_user_for(db, employee)
    if not employee.bu_id:
        return None
    if level == "BU_HEAD":
        user_id = head_user_id(db, employee.bu_id, employee.company_id)
    else:
        unit = db.query(BusinessUnit).filter(BusinessUnit.id == employee.bu_id).first()
        user_id = unit.partner_user_id if unit else None
    if not user_id or user_id == employee.wros_user_id:
        return None
    return db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()


def chain_user_ids(db: Session, employee: Employee) -> Set[str]:
    """Everyone above the employee: managers up the org chart, the BU head and the partner."""
    from app.services.org_structure_service import manager_user_for

    chain: Set[str] = set()
    current = employee
    for _ in range(MAX_CHAIN_DEPTH):
        boss = manager_user_for(db, current)
        if boss is None or boss.UserID in chain:
            break
        chain.add(boss.UserID)
        current = db.query(Employee).filter(Employee.wros_user_id == boss.UserID).first()
        if current is None:
            break
    for level in ("BU_HEAD", "PARTNER"):
        person = reviewer_for(db, level, employee)
        if person is not None:
            chain.add(person.UserID)
    chain.discard(employee.wros_user_id)
    return chain


def is_hr(db: Session, viewer: Users) -> bool:
    return authority.in_function(db, viewer, "HR")


class Access:
    """What one viewer may see and do about one employee's performance."""

    def __init__(self, db: Session, viewer: Users, employee: Employee):
        self.viewer = viewer
        self.employee = employee
        self.is_self = bool(employee.wros_user_id) and employee.wros_user_id == viewer.UserID
        self.in_chain = viewer.UserID in chain_user_ids(db, employee)
        self.is_hr = is_hr(db, viewer)
        self.oversees = self.in_chain or self.is_hr

    def can_see_review(self, review: PerformanceReview) -> bool:
        if self.oversees or review.reviewer_user_id == self.viewer.UserID:
            return True
        return self.is_self and review.status == "COMPLETED" and review.visibility == "EMPLOYEE_AND_CHAIN"

    def can_see_feedback(self, item: PeerFeedback) -> bool:
        return item.kind == "PRAISE" or self.oversees or self.is_self or item.author_user_id == self.viewer.UserID

    def sees_author(self, item: PeerFeedback) -> bool:
        return not item.anonymous or self.is_hr or item.author_user_id == self.viewer.UserID


# --- reading -----------------------------------------------------------------------------------

def _names(db: Session, ids: Iterable[str]) -> Dict[str, str]:
    ids = {i for i in ids if i}
    return {u.UserID: u.UserName or u.UserEmail for u in db.query(Users).filter(Users.UserID.in_(ids))} if ids else {}


def review_item(review: PerformanceReview, names: Dict[str, str], access: Access) -> dict:
    is_reviewer = review.reviewer_user_id == access.viewer.UserID
    has_recording = bool(review.recording_path or review.recording_url)
    return {
        "id": review.id, "level": review.level, "level_label": LEVEL_LABEL[review.level],
        "reviewer_user_id": review.reviewer_user_id, "reviewer_name": names.get(review.reviewer_user_id),
        "period_start": review.period_start.isoformat(), "period_end": review.period_end.isoformat(),
        "due_date": review.due_date.isoformat(), "status": review.status,
        "meeting_start": review.meeting_start.isoformat() if review.meeting_start else None,
        "meeting_join_url": review.meeting_join_url, "meeting_note": review.meeting_note,
        "recording_source": review.recording_source, "has_recording": has_recording,
        "recording_url": review.recording_url,
        "recording_fetch_error": review.recording_fetch_error if (is_reviewer or access.oversees) else None,
        "rating": review.rating, "summary": review.summary, "strengths": review.strengths,
        "improvements": review.improvements, "goals": review.goals, "visibility": review.visibility,
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "can_write": is_reviewer and review.status in ("PENDING", "SCHEDULED", "MISSED"),
    }


def performance_for(db: Session, viewer: Users, employee: Employee) -> dict:
    access = Access(db, viewer, employee)
    reviews = [r for r in db.query(PerformanceReview).filter(PerformanceReview.employee_id == employee.id)
               .order_by(PerformanceReview.period_end.desc()).all() if access.can_see_review(r)]
    feedback = [f for f in db.query(PeerFeedback).filter(PeerFeedback.employee_id == employee.id)
                .order_by(PeerFeedback.created_at.desc()).all() if access.can_see_feedback(f)]
    notes = db.query(PerformanceNote).filter(PerformanceNote.employee_id == employee.id) \
        .order_by(PerformanceNote.created_at.desc()).all() if access.oversees else []
    names = _names(db, [r.reviewer_user_id for r in reviews] + [f.author_user_id for f in feedback]
                   + [n.author_user_id for n in notes])
    return {
        "reviews": [review_item(r, names, access) for r in reviews],
        "feedback": [{
            "id": f.id, "kind": f.kind, "body": f.body, "anonymous": f.anonymous,
            "author_name": names.get(f.author_user_id) if access.sees_author(f) else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        } for f in feedback],
        "notes": [{"id": n.id, "body": n.body, "author_name": names.get(n.author_user_id),
                   "created_at": n.created_at.isoformat() if n.created_at else None} for n in notes],
        "can_add_note": access.oversees,
        "can_give_feedback": not access.is_self,
        "rating_max": settings.PERF_REVIEW_RATING_MAX,
        "visibilities": ["EMPLOYEE_AND_CHAIN", "CHAIN_ONLY"],
    }


# --- writing -----------------------------------------------------------------------------------

def write_review(db: Session, review: PerformanceReview, viewer: Users, data: dict, *, complete: bool) -> None:
    from app.models.performance import REVIEW_VISIBILITIES

    if review.reviewer_user_id != viewer.UserID:
        raise PermissionError("Only the reviewer writes this review")
    if review.status in ("COMPLETED", "CANCELLED"):
        raise PerformanceRefused(f"This review is {review.status.lower()}")
    if "rating" in data and data["rating"] is not None and not 1 <= data["rating"] <= settings.PERF_REVIEW_RATING_MAX:
        raise PerformanceRefused(f"Rating is 1 to {settings.PERF_REVIEW_RATING_MAX}")
    if "visibility" in data and data["visibility"] not in REVIEW_VISIBILITIES:
        raise PerformanceRefused(f"Visibility is one of {list(REVIEW_VISIBILITIES)}")
    for field in ("rating", "summary", "strengths", "improvements", "goals", "visibility"):
        if field in data:
            value = data[field]
            setattr(review, field, value.strip() or None if isinstance(value, str) else value)
    if complete:
        if not review.summary or review.rating is None:
            raise PerformanceRefused("A completed review needs a rating and a summary")
        review.status = "COMPLETED"
        review.completed_at = datetime.utcnow()
        _close_task(db, review)


def _close_task(db: Session, review: PerformanceReview) -> None:
    from app.models.task import Task

    if review.task_id:
        db.query(Task).filter(Task.id == review.task_id, Task.status.notin_(("COMPLETED", "CANCELLED"))) \
            .update({Task.status: "COMPLETED"}, synchronize_session=False)


RECORDING_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov", "audio/mpeg": ".mp3",
                   "audio/mp4": ".m4a", "audio/x-m4a": ".m4a"}


def recording_dir(tenant_id) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "performance-recordings", str(tenant_id))
    os.makedirs(path, exist_ok=True)
    return path


def store_recording(review: PerformanceReview, data: bytes, extension: str, source: str) -> None:
    if not data:
        raise PerformanceRefused("The recording file is empty")
    if len(data) > settings.PERF_REVIEW_RECORDING_MAX_BYTES:
        raise PerformanceRefused(f"The recording is larger than {settings.PERF_REVIEW_RECORDING_MAX_BYTES // (1024 * 1024)} MB")
    path = os.path.join(recording_dir(review.tenant_id), f"{review.id}{extension}")
    with open(path, "wb") as handle:
        handle.write(data)
    review.recording_path, review.recording_url, review.recording_source = path, None, source
    review.recording_fetch_error = None


def add_feedback(db: Session, viewer: Users, employee: Employee, kind: str, body: str, anonymous: bool) -> PeerFeedback:
    from app.models.performance import FEEDBACK_KINDS

    if kind not in FEEDBACK_KINDS:
        raise PerformanceRefused(f"Kind is one of {list(FEEDBACK_KINDS)}")
    if employee.wros_user_id == viewer.UserID:
        raise PerformanceRefused("You cannot give yourself praise or feedback")
    if len((body or "").strip()) < 3:
        raise PerformanceRefused("Write a few words")
    item = PeerFeedback(tenant_id=employee.tenant_id, employee_id=employee.id, author_user_id=viewer.UserID,
                        kind=kind, body=body.strip(), anonymous=bool(anonymous))
    db.add(item)
    return item


def add_note(db: Session, viewer: Users, employee: Employee, body: str) -> PerformanceNote:
    if not Access(db, viewer, employee).oversees:
        raise PermissionError("Only the reporting chain and HR keep notes on an employee")
    if len((body or "").strip()) < 3:
        raise PerformanceRefused("Write a few words")
    note = PerformanceNote(tenant_id=employee.tenant_id, employee_id=employee.id, author_user_id=viewer.UserID,
                           body=body.strip())
    db.add(note)
    return note


# --- the daily job -----------------------------------------------------------------------------

def _working_days_before(due: date, count: int) -> List[date]:
    days, day = [], due
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return sorted(days)


def _open_review(db: Session, employee: Employee, level: str, reviewer: Users, today: date) -> PerformanceReview:
    from app.services.task_service import create_task

    start, end = period(level, employee, today)
    review = PerformanceReview(tenant_id=employee.tenant_id, employee_id=employee.id, level=level,
                               reviewer_user_id=reviewer.UserID, period_start=start, period_end=end, due_date=end)
    db.add(review)
    db.flush()
    name = f"{employee.first_name} {employee.last_name}".strip()
    task = create_task(
        db, title=f"{LEVEL_LABEL[level]} review: {name} ({start:%d %b} - {end:%d %b})",
        description=(f"Meet {name}, then write up the review (rating, summary, strengths, improvements, goals) "
                     f"by {end:%d %b %Y} and choose who sees it: {employee.first_name} and the reporting chain, "
                     "or the reporting chain only."
                     + ("" if settings.PERF_REVIEW_TEAMS_ENABLED else
                        " Set up the Teams meeting with them and record it.")),
        priority="MEDIUM", tenant_id=employee.tenant_id, assigned_to_user_id=reviewer.UserID,
        category="PERFORMANCE", due_date=datetime.combine(end, datetime.min.time()),
        link=f"/employees/{employee.id}?tab=performance&review={review.id}",
    )
    review.task_id = task.id
    return review


def _book(db: Session, review: PerformanceReview, employee: Employee, today: date) -> None:
    from app.services import performance_teams

    reviewer = db.query(Users).filter(Users.UserID == review.reviewer_user_id).first()
    window = [d for d in _working_days_before(review.due_date, settings.PERF_REVIEW_BOOK_WITHIN_DAYS) if d >= today]
    if not window:
        return
    taken = {r.meeting_start.date() for r in db.query(PerformanceReview.meeting_start).filter(
        PerformanceReview.reviewer_user_id == review.reviewer_user_id, PerformanceReview.meeting_start.isnot(None))}
    day = next((d for d in window if d not in taken), window[0])
    start = datetime.combine(day, datetime.min.time()).replace(hour=settings.PERF_REVIEW_MEETING_HOUR)
    if start in {r.meeting_start for r in db.query(PerformanceReview.meeting_start).filter(
            PerformanceReview.reviewer_user_id == review.reviewer_user_id)}:
        start += timedelta(minutes=settings.PERF_REVIEW_MEETING_MINUTES)
    end = start + timedelta(minutes=settings.PERF_REVIEW_MEETING_MINUTES)
    name = f"{employee.first_name} {employee.last_name}".strip()
    try:
        event_id, join_url = performance_teams.book_meeting(
            subject=f"{LEVEL_LABEL[review.level]} review: {name}",
            body_html=(f"<p>{LEVEL_LABEL[review.level]} performance review for {name}, "
                       f"{review.period_start:%d %b} - {review.period_end:%d %b %Y}. "
                       "This meeting is recorded and the recording is kept with the review.</p>"),
            start=start, end=end, timezone=reviewer.timezone or "UTC",
            attendee_emails=[reviewer.UserEmail, employee.email])
        review.meeting_start, review.meeting_end, review.meeting_event_id = start, end, event_id
        review.meeting_join_url, review.status, review.meeting_note = join_url, "SCHEDULED", None
        if join_url:
            performance_teams.record_automatically(join_url)
    except performance_teams.GraphError as exc:
        review.meeting_note = f"Could not book the meeting: {exc}"
        logger.error(f"[Performance] review {review.id}: {review.meeting_note}")


def _fetch_recording(review: PerformanceReview) -> None:
    from app.services import performance_teams

    try:
        data = performance_teams.fetch_recording(review.meeting_join_url, settings.PERF_REVIEW_RECORDING_MAX_BYTES)
    except performance_teams.GraphError as exc:
        review.recording_fetch_error = str(exc)
        logger.error(f"[Performance] review {review.id} recording: {exc}")
        return
    if data is None:
        review.recording_fetch_error = "Teams has no recording for this meeting yet"
        return
    store_recording(review, data, ".mp4", "TEAMS")


def run_performance_reviews(db: Session, today: Optional[date] = None, now: Optional[datetime] = None) -> Dict:
    """Scheduled job performance_reviews. Idempotent per employee, level and period."""
    today = today or date.today()
    now = now or datetime.utcnow()
    result = {"opened": 0, "no_reviewer": 0, "booked": 0, "recordings": 0, "missed": 0, "failed": 0}

    for employee in db.query(Employee).filter(Employee.status.in_(REVIEWED_STATUSES),
                                              Employee.joining_date <= today).all():
        for level in ("MANAGER", "BU_HEAD", "PARTNER"):
            start, _ = period(level, employee, today)
            exists = db.query(PerformanceReview.id).filter(
                PerformanceReview.employee_id == employee.id, PerformanceReview.level == level,
                PerformanceReview.period_start == start).first()
            if exists:
                continue
            reviewer = reviewer_for(db, level, employee)
            if reviewer is None:
                result["no_reviewer"] += 1
                continue
            try:
                _open_review(db, employee, level, reviewer, today)
                db.commit()
                result["opened"] += 1
            except Exception as exc:  # one employee must not stop the others; logged and counted
                db.rollback()
                logger.error(f"[Performance] {employee.id} {level}: {exc}", exc_info=True)
                result["failed"] += 1

    # reviews of people no longer reviewed (notice, exit) are cancelled with their tasks
    for review in db.query(PerformanceReview).join(Employee, Employee.id == PerformanceReview.employee_id).filter(
            PerformanceReview.status.in_(("PENDING", "SCHEDULED")), Employee.status.notin_(REVIEWED_STATUSES)).all():
        review.status = "CANCELLED"
        _close_task(db, review)
    db.commit()

    if settings.PERF_REVIEW_TEAMS_ENABLED:
        for review in db.query(PerformanceReview).filter(PerformanceReview.status == "PENDING",
                                                         PerformanceReview.meeting_note.is_(None)).all():
            employee = db.query(Employee).filter(Employee.id == review.employee_id).first()
            _book(db, review, employee, today)
            db.commit()
            result["booked"] += int(review.status == "SCHEDULED")

    if settings.PERF_REVIEW_FETCH_RECORDINGS:
        for review in db.query(PerformanceReview).filter(
                PerformanceReview.meeting_join_url.isnot(None), PerformanceReview.meeting_end < now,
                PerformanceReview.recording_path.is_(None), PerformanceReview.recording_url.is_(None)).all():
            _fetch_recording(review)
            db.commit()
            result["recordings"] += int(review.recording_path is not None)

    for review in db.query(PerformanceReview).filter(PerformanceReview.status.in_(("PENDING", "SCHEDULED")),
                                                     PerformanceReview.due_date < today).all():
        review.status = "MISSED"
        result["missed"] += 1
    db.commit()
    logger.info(f"[Performance] {result}")
    return result
