"""Hiring analytics: where hires come from, what each recruiter's candidates became, and open positions
against people who joined. Read from facts only -- the hiring pipeline's stages and their history -- so the
numbers always agree with the candidate pages. The caller sees the candidates and jobs their role lets them
see (the candidate list's own business-unit rule)."""
import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.bu_scope import apply_bu_scope_to_candidate_query
from app.core.visibility import get_user_bu_ids
from app.models.candidate import Candidate
from app.models.hiring_pipeline import CLOSED_STAGES, STAGES, HiringPipeline, HiringPipelineEvent
from app.models.user import Jobs, Users

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 90
MAX_WINDOW_DAYS = 731
OPEN_JOB_STATUSES = ("active", "public")
NO_SOURCE = "Not recorded"
STAGE_INDEX = {stage: index for index, stage in enumerate(STAGES)}
INTERVIEW_FROM, OFFER_FROM, ACCEPTED_FROM, JOINED_FROM = (STAGE_INDEX[s] for s in ("L1", "OFFER", "ACCEPTED", "BENCH"))


class HiringAnalyticsError(ValueError):
    pass


def _window(date_from: Optional[date], date_to: Optional[date], today: date) -> tuple:
    end = date_to or today
    start = date_from or (end - timedelta(days=DEFAULT_WINDOW_DAYS))
    if start > end:
        raise HiringAnalyticsError("The start date is after the end date.")
    if (end - start).days > MAX_WINDOW_DAYS:
        raise HiringAnalyticsError(f"Choose a period of at most {MAX_WINDOW_DAYS} days.")
    return start, end


class _Journey:
    """What became of one candidate: the furthest stage any of their pipelines reached."""
    __slots__ = ("furthest", "joined", "open", "closed", "offer_at", "job_ids")

    def __init__(self):
        self.furthest, self.joined, self.open, self.closed = -1, False, False, False
        self.offer_at: Optional[datetime] = None
        self.job_ids = set()

    def reach(self, stage: Optional[str], when: Optional[datetime] = None) -> None:
        index = STAGE_INDEX.get(stage or "")
        if index is None:
            return
        self.furthest = max(self.furthest, index)
        if index >= OFFER_FROM and when is not None and (self.offer_at is None or when < self.offer_at):
            self.offer_at = when

    @property
    def hired(self) -> bool:
        return self.joined or self.furthest >= JOINED_FROM

    @property
    def rejected(self) -> bool:
        return self.closed and not self.open and not self.hired


def _journeys(db: Session, candidate_ids: List[str]) -> Dict[str, _Journey]:
    journeys: Dict[str, _Journey] = {candidate_id: _Journey() for candidate_id in candidate_ids}
    if not candidate_ids:
        return journeys
    pipelines = db.query(HiringPipeline).filter(HiringPipeline.candidate_id.in_(candidate_ids)).all()
    by_pipeline = {}
    for pipeline in pipelines:
        journey = journeys[pipeline.candidate_id]
        by_pipeline[pipeline.id] = journey
        journey.reach(pipeline.stage, pipeline.stage_entered_at)
        journey.joined = journey.joined or pipeline.employee_id is not None
        if pipeline.job_id:
            journey.job_ids.add(pipeline.job_id)
        if pipeline.closed_at is None:
            journey.open = True
        elif pipeline.stage in CLOSED_STAGES:
            journey.closed = True
    if by_pipeline:
        events = db.query(HiringPipelineEvent.pipeline_id, HiringPipelineEvent.to_stage, HiringPipelineEvent.created_at) \
            .filter(HiringPipelineEvent.pipeline_id.in_(list(by_pipeline))).all()
        for pipeline_id, to_stage, created_at in events:
            by_pipeline[pipeline_id].reach(to_stage, created_at)
    return journeys


def _funnel_row(label: str) -> Dict:
    return {"label": label, "added": 0, "interviewed": 0, "offered": 0, "accepted": 0, "hired": 0, "rejected": 0,
            "_days_to_offer": []}


def _count(row: Dict, candidate: Candidate, journey: _Journey) -> None:
    row["added"] += 1
    row["interviewed"] += journey.furthest >= INTERVIEW_FROM
    row["offered"] += journey.furthest >= OFFER_FROM
    row["accepted"] += journey.furthest >= ACCEPTED_FROM
    row["hired"] += journey.hired
    row["rejected"] += journey.rejected
    if journey.offer_at is not None and candidate.candidateCreatedAt is not None:
        row["_days_to_offer"].append(max((journey.offer_at - candidate.candidateCreatedAt).total_seconds() / 86400, 0))


def _finish(row: Dict) -> Dict:
    days = row.pop("_days_to_offer")
    row["hire_rate_pct"] = round(100 * row["hired"] / row["added"], 1) if row["added"] else None
    row["avg_days_to_offer"] = round(sum(days) / len(days), 1) if days else None
    return row


def _source(candidate: Candidate) -> str:
    raw = (candidate.recruitment_source or candidate.source_channel or "").strip()
    return raw.replace("_", " ").title() if raw else NO_SOURCE


def _positions(db: Session, user: Users) -> List[Dict]:
    """Every open job: positions asked for against people who joined, with who is still in the hiring order."""
    query = db.query(Jobs).filter(Jobs.jobStatus.in_(OPEN_JOB_STATUSES), Jobs.is_deleted.is_(False))
    if user.tenant_id is not None:
        query = query.filter(Jobs.tenant_id == user.tenant_id)
    bu_ids = get_user_bu_ids(db, user)
    if bu_ids is not None:
        query = query.filter(Jobs.business_unit_id.in_(bu_ids))
    jobs = query.all()
    if not jobs:
        return []
    job_ids = [job.jobID for job in jobs]
    pipelines = db.query(HiringPipeline).filter(HiringPipeline.job_id.in_(job_ids)).all()
    hired, offers, in_progress = {}, {}, {}
    for pipeline in pipelines:
        index = STAGE_INDEX.get(pipeline.stage, -1)
        if pipeline.employee_id is not None or index >= JOINED_FROM:
            hired.setdefault(pipeline.job_id, set()).add(pipeline.candidate_id)
        elif pipeline.closed_at is None and index >= OFFER_FROM:
            offers.setdefault(pipeline.job_id, set()).add(pipeline.candidate_id)
        elif pipeline.closed_at is None:
            in_progress.setdefault(pipeline.job_id, set()).add(pipeline.candidate_id)
    rows = []
    for job in jobs:
        positions = job.noOfPositions if job.noOfPositions and job.noOfPositions > 0 else 1
        joined = len(hired.get(job.jobID, ()))
        rows.append({"job_id": job.jobID, "title": job.jobTitle, "positions": positions, "hired": joined,
                     "offers_out": len(offers.get(job.jobID, ())), "in_progress": len(in_progress.get(job.jobID, ())),
                     "still_to_hire": max(positions - joined, 0),
                     "opened_on": job.jobCreatedAt.date() if job.jobCreatedAt else None})
    return sorted(rows, key=lambda r: (-r["still_to_hire"], r["title"] or ""))


def hiring_analytics(db: Session, user: Users, *, date_from: Optional[date] = None, date_to: Optional[date] = None,
                     today: Optional[date] = None) -> Dict:
    start, end = _window(date_from, date_to, today or datetime.utcnow().date())
    query = db.query(Candidate).filter(
        Candidate.candidateCreatedAt >= datetime.combine(start, time.min),
        Candidate.candidateCreatedAt < datetime.combine(end + timedelta(days=1), time.min),
        Candidate.merged_into_id.is_(None),
    )
    if user.tenant_id is not None:
        query = query.filter(Candidate.tenant_id == user.tenant_id)
    candidates = apply_bu_scope_to_candidate_query(db, query, user).all()
    journeys = _journeys(db, [c.candidateID for c in candidates])

    recruiter_ids = {c.assigned_recruiter_id for c in candidates if c.assigned_recruiter_id}
    names = dict(db.query(Users.UserID, Users.UserName).filter(Users.UserID.in_(recruiter_ids)).all()) if recruiter_ids else {}
    totals, sources, recruiters = _funnel_row("All candidates"), {}, {}
    for candidate in candidates:
        journey = journeys[candidate.candidateID]
        _count(totals, candidate, journey)
        source = _source(candidate)
        _count(sources.setdefault(source, _funnel_row(source)), candidate, journey)
        recruiter_id = candidate.assigned_recruiter_id
        row = recruiters.get(recruiter_id)
        if row is None:
            row = _funnel_row(names.get(recruiter_id) or recruiter_id or "No recruiter")
            row["recruiter_id"] = recruiter_id
            recruiters[recruiter_id] = row
        _count(row, candidate, journey)

    positions = _positions(db, user)
    def order(row: Dict) -> tuple:
        return -row["hired"], -row["added"], row["label"]

    return {
        "date_from": start, "date_to": end,
        "totals": _finish(totals),
        "sources": sorted((_finish(r) for r in sources.values()), key=order),
        "recruiters": sorted((_finish(r) for r in recruiters.values()), key=order),
        "positions": positions,
        "position_totals": {key: sum(r[key] for r in positions) for key in ("positions", "hired", "offers_out", "in_progress", "still_to_hire")},
    }
