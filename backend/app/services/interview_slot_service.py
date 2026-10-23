"""The earliest interview slot that suits both the interviewer and the candidate (flash spec D).

- Windows: the interviewer's and the candidate's business hours in their own time zones
  (settings.INTERVIEW_WORKDAY_START_HOUR..END_HOUR, weekends excluded), intersected, from
  now + INTERVIEW_MIN_LEAD_HOURS to now + INTERVIEW_HORIZON_DAYS.
- Busy: the interviewer's and the candidate's scheduled interviews in WROS, plus the
  interviewer's Outlook busy times when FLASH_USE_GRAPH_CALENDAR is on and Microsoft Graph is
  configured (or a graph_call is passed). A buffer of INTERVIEW_BUFFER_MINUTES follows each
  busy period.
- The slot lasts INTERVIEW_DURATION_MINUTES and starts on an INTERVIEW_SLOT_STEP_MINUTES mark.

Returns naive UTC (the interview storage convention) or None when nothing fits.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.user import Interview, PanelMember, Users
from app.services.calendar_matching_service import (_business_hour_windows_utc, get_interviewer_busy_events,
                                                    invert_busy_to_free)

logger = logging.getLogger(__name__)

Span = Tuple[datetime, datetime]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _intersect(a: List[Span], b: List[Span]) -> List[Span]:
    out = []
    for a_start, a_end in a:
        for b_start, b_end in b:
            start, end = max(a_start, b_start), min(a_end, b_end)
            if start < end:
                out.append((start, end))
    return sorted(out)


def _round_up(value: datetime, minutes: int) -> datetime:
    if minutes <= 1:
        return value.replace(second=0, microsecond=0) + (timedelta(minutes=1) if value.second or value.microsecond
                                                         else timedelta())
    base = value.replace(second=0, microsecond=0)
    extra = (-base.minute) % minutes
    if extra == 0 and (value.second or value.microsecond):
        extra = minutes
    return base + timedelta(minutes=extra)


def graph_enabled() -> bool:
    if not settings.FLASH_USE_GRAPH_CALENDAR:
        return False
    from app.core.graph_auth import GraphServiceAuth

    return GraphServiceAuth.is_configured()


def _db_busy(db: Session, interviewer: Users, candidate: Candidate, start: datetime, end: datetime) -> List[Span]:
    naive_start, naive_end = start.replace(tzinfo=None), end.replace(tzinfo=None)
    theirs = (db.query(Interview.start_time, Interview.end_time)
              .join(PanelMember, PanelMember.panel_id == Interview.panel_id)
              .filter(PanelMember.interviewer_id == interviewer.UserID, Interview.status == "Scheduled",
                      Interview.end_time > naive_start, Interview.start_time < naive_end))
    candidates = (db.query(Interview.start_time, Interview.end_time)
                  .filter(Interview.candidate_id == candidate.candidateID, Interview.status == "Scheduled",
                          Interview.end_time > naive_start, Interview.start_time < naive_end))
    return [(_aware(s), _aware(e)) for s, e in list(theirs) + list(candidates) if s and e]


def next_free_slot(db: Session, interviewer: Users, candidate: Candidate, *, now: datetime,
                   graph_call: Optional[Callable] = None) -> Optional[Span]:
    start = _aware(now) + timedelta(hours=settings.INTERVIEW_MIN_LEAD_HOURS)
    end = _aware(now) + timedelta(days=settings.INTERVIEW_HORIZON_DAYS)
    duration = timedelta(minutes=settings.INTERVIEW_DURATION_MINUTES)
    first_day, last_day = (start - timedelta(days=1)).date(), (end + timedelta(days=1)).date()
    windows = _intersect(
        _business_hour_windows_utc(first_day, last_day, interviewer.timezone or settings.INTERVIEW_DEFAULT_TIMEZONE),
        _business_hour_windows_utc(first_day, last_day, candidate.timezone or settings.INTERVIEW_DEFAULT_TIMEZONE))
    windows = [(max(s, start), min(e, end)) for s, e in windows if max(s, start) < min(e, end)]
    if not windows:
        return None

    busy = _db_busy(db, interviewer, candidate, start, end)
    if graph_call is not None or graph_enabled():
        busy += [(_aware(s), _aware(e)) for s, e in
                 get_interviewer_busy_events(interviewer.UserEmail, start, end, graph_call=graph_call)]

    for window_start, window_end in windows:
        for free_start, free_end in invert_busy_to_free(busy, window_start, window_end):
            slot_start = _round_up(free_start, settings.INTERVIEW_SLOT_STEP_MINUTES)
            if slot_start + duration <= free_end:
                return (slot_start.astimezone(timezone.utc).replace(tzinfo=None),
                        (slot_start + duration).astimezone(timezone.utc).replace(tzinfo=None))
    return None
