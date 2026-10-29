"""Performance: reviews, peer praise and feedback, internal notes (app.services.performance_service).

Gates: an employee's performance on their profile needs employees.view; everything a person does
for themselves or as a peer or reviewer (My Performance, giving praise / feedback, writing the
review their task points to, attaching its recording) needs my-tasks.view, the resource My
Performance shares. Within those, who sees and changes what is decided by the reporting chain and
the HR function (performance_service.Access), never by a role name.
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.models.employee import Employee
from app.models.performance import PerformanceReview
from app.models.user import Users
from app.services import performance_service as perf

router = APIRouter(prefix="/performance", tags=["performance"])


def _employee(db: Session, employee_id: str, user: Users) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == user.tenant_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _review(db: Session, review_id: str, user: Users) -> PerformanceReview:
    review = db.query(PerformanceReview).filter(PerformanceReview.id == review_id,
                                                PerformanceReview.tenant_id == user.tenant_id).first()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.get("/employees/{employee_id}", dependencies=[Depends(require_resource_permission("employees", "view"))])
def employee_performance(employee_id: str, db: Session = Depends(get_db),
                         current_user: Users = Depends(get_current_internal_user)):
    """The Performance tab of an employee's profile, as this viewer may see it."""
    return perf.performance_for(db, current_user, _employee(db, employee_id, current_user))


@router.get("/me", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def my_performance(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    """My Performance: reviews shared with me, praise and feedback about me, and the reviews I owe.
    Someone without an employee record (a leader or admin login) still sees the reviews they owe."""
    employee = db.query(Employee).filter(Employee.wros_user_id == current_user.UserID).first()
    if employee is not None:
        mine = perf.performance_for(db, current_user, employee)
    else:
        mine = {"reviews": [], "feedback": [], "notes": [], "can_add_note": False, "can_give_feedback": False,
                "rating_max": perf.settings.PERF_REVIEW_RATING_MAX, "visibilities": ["EMPLOYEE_AND_CHAIN", "CHAIN_ONLY"]}
    owed = db.query(PerformanceReview).filter(PerformanceReview.reviewer_user_id == current_user.UserID,
                                              PerformanceReview.status.in_(("PENDING", "SCHEDULED", "MISSED"))) \
        .order_by(PerformanceReview.due_date).all()
    people = {e.id: e for e in db.query(Employee).filter(Employee.id.in_({r.employee_id for r in owed}))} if owed else {}
    mine["to_review"] = [{"review_id": r.id, "employee_id": r.employee_id,
                          "employee_name": f"{people[r.employee_id].first_name} {people[r.employee_id].last_name}".strip(),
                          "level_label": perf.LEVEL_LABEL[r.level], "due_date": r.due_date.isoformat(),
                          "status": r.status} for r in owed if r.employee_id in people]
    mine["employee_id"] = employee.id if employee is not None else None
    return mine


@router.get("/colleagues", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def colleagues(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    """Who I can give praise or feedback to: current colleagues (name and title only)."""
    rows = db.query(Employee).filter(Employee.tenant_id == current_user.tenant_id,
                                     Employee.status.in_(perf.REVIEWED_STATUSES + ("NOTICE_PERIOD",)),
                                     (Employee.wros_user_id.is_(None)) | (Employee.wros_user_id != current_user.UserID)) \
        .order_by(Employee.first_name).all()
    return {"colleagues": [{"employee_id": e.id, "name": f"{e.first_name} {e.last_name}".strip(),
                            "title": e.current_title} for e in rows]}


class ReviewWrite(BaseModel):
    rating: Optional[int] = None
    summary: Optional[str] = None
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    goals: Optional[str] = None
    visibility: Optional[str] = None
    complete: bool = False


@router.put("/reviews/{review_id}", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def write_review(review_id: str, body: ReviewWrite, db: Session = Depends(get_db),
                 current_user: Users = Depends(get_current_internal_user)):
    """The reviewer saves the write-up; complete=True finishes it (rating and summary required) and
    shares it as chosen. A completed review is final."""
    review = _review(db, review_id, current_user)
    try:
        perf.write_review(db, review, current_user, body.dict(exclude_unset=True, exclude={"complete"}),
                          complete=body.complete)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except perf.PerformanceRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    logger.info(f"[Performance] review {review.id} saved by {current_user.UserID} (complete={body.complete})")
    employee = db.query(Employee).filter(Employee.id == review.employee_id).first()
    return perf.review_item(review, perf._names(db, [review.reviewer_user_id]), perf.Access(db, current_user, employee))


@router.post("/reviews/{review_id}/recording", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
async def upload_recording(review_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                           current_user: Users = Depends(get_current_internal_user)):
    """The reviewer attaches the session recording (until Teams recordings are fetched automatically)."""
    review = _review(db, review_id, current_user)
    if review.reviewer_user_id != current_user.UserID:
        raise HTTPException(status_code=403, detail="Only the reviewer attaches the recording")
    extension = perf.RECORDING_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=400, detail=f"Upload a video or audio file ({', '.join(sorted(set(perf.RECORDING_TYPES.values())))})")
    try:
        perf.store_recording(review, await file.read(), extension, "UPLOAD")
    except perf.PerformanceRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"review_id": review.id, "recording_source": review.recording_source}


class RecordingLink(BaseModel):
    url: str


@router.put("/reviews/{review_id}/recording-link", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def link_recording(review_id: str, body: RecordingLink, db: Session = Depends(get_db),
                   current_user: Users = Depends(get_current_internal_user)):
    """The reviewer links the recording where it already lives (Teams / Stream / SharePoint)."""
    review = _review(db, review_id, current_user)
    if review.reviewer_user_id != current_user.UserID:
        raise HTTPException(status_code=403, detail="Only the reviewer attaches the recording")
    url = (body.url or "").strip()
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="The recording link must start with https://")
    review.recording_url, review.recording_path, review.recording_source = url, None, "LINK"
    review.recording_fetch_error = None
    db.commit()
    return {"review_id": review.id, "recording_source": review.recording_source}


@router.get("/reviews/{review_id}/recording", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def download_recording(review_id: str, db: Session = Depends(get_db),
                       current_user: Users = Depends(get_current_internal_user)):
    review = _review(db, review_id, current_user)
    employee = db.query(Employee).filter(Employee.id == review.employee_id).first()
    if not perf.Access(db, current_user, employee).can_see_review(review):
        raise HTTPException(status_code=404, detail="Review not found")
    if not review.recording_path or not os.path.exists(review.recording_path):
        raise HTTPException(status_code=404, detail="No recording stored for this review")
    return FileResponse(review.recording_path, filename=os.path.basename(review.recording_path))


class FeedbackCreate(BaseModel):
    kind: str  # PRAISE | FEEDBACK
    body: str
    anonymous: bool = False


@router.post("/employees/{employee_id}/feedback", status_code=201,
             dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def give_feedback(employee_id: str, body: FeedbackCreate, db: Session = Depends(get_db),
                  current_user: Users = Depends(get_current_internal_user)):
    employee = _employee(db, employee_id, current_user)
    try:
        item = perf.add_feedback(db, current_user, employee, body.kind, body.body, body.anonymous)
    except perf.PerformanceRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"id": item.id, "kind": item.kind, "anonymous": item.anonymous}


class NoteCreate(BaseModel):
    body: str


@router.post("/employees/{employee_id}/notes", status_code=201,
             dependencies=[Depends(require_resource_permission("employees", "view"))])
def add_note(employee_id: str, body: NoteCreate, db: Session = Depends(get_db),
             current_user: Users = Depends(get_current_internal_user)):
    employee = _employee(db, employee_id, current_user)
    try:
        note = perf.add_note(db, current_user, employee, body.body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except perf.PerformanceRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return {"id": note.id}
