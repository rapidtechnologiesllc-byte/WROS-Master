"""
S-048/HRMS-0448 -- Calendar Matching Engine.

Real architecture adaptations:
- No new `interviews` table. Writes into `SubmissionInterview`
  (app.models.interview_pipeline) -- its own module docstring already
  names this exact story as the one that would populate
  `scheduled_via_graph_event_id`. "status=SCHEDULED" (spec's Step 4)
  maps onto this codebase's real signal: `outcome='PENDING'` (default,
  unaffected) + `scheduled_at` set (not null) -- there is no separate
  literal `status` column to write. Reuses
  `interview_service.get_assigned_interviewer()`/`create_interview()`
  as-is (R-05 L1-before-L2 already enforced there).
- No `job_id` bridge exists on `CandidateAvailabilitySlot` (S-047) --
  a candidate's active `Submission` is resolved by querying for the
  most recent one in `CLIENT_INTERVIEW_REQUESTED` status (the real
  state meaning "client wants to interview them"), falling back to the
  most recent non-terminal submission if none is in that exact status.
  This is a genuine, flagged design decision: a candidate with two
  simultaneous active submissions across different demands would
  ambiguously resolve to "most recent" -- there is no submission_id
  thread from the availability-collection conversation back to a
  specific submission anywhere in this codebase yet. Documented, not
  silently assumed correct.
- No L1/L2 signal exists anywhere upstream of this story (S-047 has no
  concept of interview level) -- defaults to `level="L1"` (first
  round), overridable by a caller that knows better. An L2 interview
  would need its own, separate availability-collection round with its
  own level passed in -- not decided by this story.
- Tenant-ID seam: `CandidateAvailabilitySlot`/`CandidateConversation`
  use `tenant_id String(50)` (UserID-as-tenant), but
  `Submission`/`SubmissionInterview`/`DemandInterviewPanel` use
  `tenant_id Integer FK tenants.id` (the older Phase-2 tenant concept).
  This story sits exactly at that seam -- the candidate-side
  `tenant_id` (String) is used only to look up the candidate's own
  slots; the interview-side `tenant_id` (Integer) comes independently
  from `submission.tenant_id`, never converted from the other.
- Real MS Graph integration already exists (`app/core/graph_auth.py`'s
  `get_graph_token()`, application/client-credentials auth -- no
  per-user OAuth needed) and a real `calendarView` read already lives
  in `app/api/v1/endpoints/msgraph.py` (HR-facing, keyed by
  user_email). This story does NOT refactor that endpoint (out of
  scope, unrelated file, mixed with SharePoint code) -- it makes its
  own minimal Graph `calendarView` REST call here, injectable via
  `graph_call` so no test ever hits a real external API, matching the
  established response_parser_service.py/interview_availability_service.py
  convention. A future cleanup could extract one shared Graph-read
  service; not done unilaterally this late in the same story.
- Interviewer identity/timezone: `DemandInterviewPanel.employee_id` ->
  `Employee.wros_user_id` -> `Users.UserEmail`/`Users.timezone` -- the
  same real fields S-047 already uses for candidates via
  `Candidate.timezone`. No `Employee.timezone` column exists.
- No real free/busy inversion existed anywhere before this story --
  `invert_busy_to_free()` is new. BR-02's "15-min buffer, no
  back-to-back scheduling" is applied AT INVERSION TIME (a free period
  starts 15 min after the busy event immediately before it ends), not
  as extra padding at match time -- this is the only reading that
  reconciles the spec's own TC-001 (interviewer "free 2:30-5pm" matched
  AT 2:30, no visible extra buffer) with TC-002 (interviewer "busy
  until 2:00pm" does NOT match at 2:00, next slot at 2:15 used): TC-001's
  "free 2:30-5pm" is itself the already-buffered free window, TC-002
  demonstrates that same buffering being applied.
- BR-03 (no weekends): enforced by construction -- interviewer
  business-hours windows are only ever generated for non-weekend
  interviewer-local dates in the first place (see
  `_business_hour_windows_utc()`), so no free period, and therefore no
  match, can ever land on an interviewer-local weekend. Candidate-local
  weekend slots can never reach this service to begin with -- S-047's
  own `_validate_slot()` already rejects them at storage time.
- BR-03's holiday half ("check both candidate and interviewer country
  for public holidays via a holiday library") is explicitly NOT built
  -- no holiday-calendar data source, no country field on Candidate or
  Employee/Users (only IANA timezone strings), and no holiday library
  is installed anywhere in this codebase. Same real, honest gap
  S-039/HRMS-0439's `availability_scoring_service.py` already flagged
  for an identical "continent holidays" ask and declined to fake.
  Weekend-only enforcement is what's actually built and tested (also
  all TC-004 the spec itself tests).
- Meeting-link/Graph-event creation is deliberately NOT done by this
  story -- the spec's own dependency table lists HRMS-0449 (Interview
  Confirmation) as firing "fire-and-forget... after record created",
  which reads as HRMS-0449's job, not this one's. `scheduled_at` is set
  for real; `scheduled_via_graph_event_id` stays null (its own model
  docstring already documents null as "scheduled but not yet a Graph
  invite", not a failure state) until a future HRMS-0449 build creates
  the actual calendar invite.
- No-match handling: `CandidateAvailabilitySlot` has no EXPIRED status
  column, only `is_confirmed` -- the spec's own "clear existing
  candidate slots (or mark as EXPIRED)" parenthetical is read as either
  being acceptable; this story hard-deletes the candidate's unconfirmed
  slots on a real no-match, so the candidate is asked fresh rather than
  a stale, already-rejected set of slots being re-matched forever.
- No `INTERVIEW_SCHEDULING` conversation-state enum value exists (same
  fictional 10-state enum every S-041-047 story has already flagged).
  Every step is logged as a real `ConversationEvent`
  (`calendar_match_succeeded`/`calendar_match_failed`/
  `calendar_check_failed`) instead.
- Deliberately NOT wired into a live trigger yet -- same posture S-047
  took. `attempt_calendar_match()` is the real, callable, fully tested
  entry point a future wiring pass would call right after S-047's
  `parse_availability_response()` returns `outcome="slots_sufficient"`.
- `reschedule_count`/`rescheduled_from_interview_id` (S-051/HRMS-0451)
  are optional passthrough params to `create_interview()`, added so
  `interview_reschedule_service` can reuse this exact matching function
  for a reschedule's new interview record instead of duplicating the
  whole matching flow. `supersede_interview_id`, when given, marks that
  interview's `superseded_at` in the exact same commit as the new
  interview's creation -- ONLY on a real match, never on any other
  outcome, so a stalled/failed reschedule attempt never orphans the
  candidate's still-valid old interview.
"""
import os
from datetime import date as date_cls, datetime, time as time_cls, timedelta, timezone as dt_timezone
from typing import Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
from app.models.employee import Employee
from app.models.interview_pipeline import SubmissionInterview
from app.models.submission import Submission
from app.models.user import Users
from app.services.interview_service import L1NotPassed, NoEligibleInterviewer, create_interview, get_assigned_interviewer
from app.services.notification_service import send_notification

MIN_VALID_SLOTS = 2  # matches S-047's own BR-03 threshold
DEFAULT_INTERVIEW_DURATION_MINUTES = int(os.getenv("DEFAULT_INTERVIEW_DURATION_MINUTES", "60"))
SCHEDULING_BUFFER_MINUTES = 15  # BR-02
INTERVIEWER_BUSINESS_HOURS_START = 9  # Step 1
INTERVIEWER_BUSINESS_HOURS_END = 17
WEEKEND_WEEKDAYS = (5, 6)

# Submission statuses that mean "a real, live opportunity, worth scheduling an interview for" -- see module docstring's submission-resolution note.
INTERVIEW_ELIGIBLE_STATUSES = ("CLIENT_INTERVIEW_REQUESTED", "SHORTLISTED", "SUBMITTED")

NO_MATCH_MESSAGE = (
    "We weren't able to find a time that works with our interviewer's schedule from what you shared. "
    "Could you offer 2-3 new time windows over the next couple of weeks?"
)

GraphCall = Callable[[str, datetime, datetime], List[Tuple[datetime, datetime]]]


def _resolve_active_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    """See module docstring's submission-resolution note -- a real,
    flagged simplification, not a guaranteed-correct answer for a
    candidate with multiple simultaneous active submissions."""
    for status in INTERVIEW_ELIGIBLE_STATUSES:
        submission = (
            db.query(Submission)
            .filter(Submission.candidate_id == candidate_id, Submission.status == status)
            .order_by(Submission.submitted_at.desc())
            .first()
        )
        if submission:
            return submission
    return None


def _unconfirmed_slots(db: Session, candidate_id: str, tenant_id: str) -> List[CandidateAvailabilitySlot]:
    return (
        db.query(CandidateAvailabilitySlot)
        .filter(CandidateAvailabilitySlot.tenant_id == tenant_id, CandidateAvailabilitySlot.candidate_id == candidate_id, CandidateAvailabilitySlot.is_confirmed == False)
        .order_by(CandidateAvailabilitySlot.slot_date.asc(), CandidateAvailabilitySlot.slot_start_time.asc())
        .all()
    )


def _slot_to_utc_range(slot: CandidateAvailabilitySlot) -> Tuple[datetime, datetime]:
    tz = ZoneInfo(slot.timezone)
    start_local = datetime.combine(slot.slot_date, slot.slot_start_time, tzinfo=tz)
    end_local = datetime.combine(slot.slot_date, slot.slot_end_time, tzinfo=tz)
    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(dt_timezone.utc)


def _business_hour_windows_utc(start_date: date_cls, end_date: date_cls, tz_name: str) -> List[Tuple[datetime, datetime]]:
    """Step 1 -- one window per non-weekend interviewer-local day.
    BR-03's weekend rule is enforced here, by construction: a weekend
    date never produces a window, so it can never produce a free
    period or a match."""
    tz = ZoneInfo(tz_name)
    windows = []
    d = start_date
    while d <= end_date:
        if d.weekday() not in WEEKEND_WEEKDAYS:
            start_local = datetime.combine(d, time_cls(INTERVIEWER_BUSINESS_HOURS_START, 0), tzinfo=tz)
            end_local = datetime.combine(d, time_cls(INTERVIEWER_BUSINESS_HOURS_END, 0), tzinfo=tz)
            windows.append((start_local.astimezone(dt_timezone.utc), end_local.astimezone(dt_timezone.utc)))
        d += timedelta(days=1)
    return windows


def invert_busy_to_free(
    busy_events_utc: List[Tuple[datetime, datetime]], window_start_utc: datetime, window_end_utc: datetime,
    *, buffer_minutes: int = SCHEDULING_BUFFER_MINUTES,
) -> List[Tuple[datetime, datetime]]:
    """BR-02 -- see module docstring on why the buffer is applied here,
    at inversion time, not at match time."""
    free = []
    cursor = window_start_utc
    for busy_start, busy_end in sorted(busy_events_utc, key=lambda b: b[0]):
        if busy_start <= window_start_utc and busy_end <= window_start_utc:
            continue  # entirely before the window
        if busy_start >= window_end_utc:
            break  # entirely after the window -- nothing more to consider
        if busy_start > cursor:
            free.append((cursor, min(busy_start, window_end_utc)))
        cursor = max(cursor, busy_end + timedelta(minutes=buffer_minutes))
    if cursor < window_end_utc:
        free.append((cursor, window_end_utc))
    return [period for period in free if period[0] < period[1]]


def find_matching_slot(
    candidate_slots: List[CandidateAvailabilitySlot], free_periods_utc: List[Tuple[datetime, datetime]], duration_minutes: int,
) -> Tuple[Optional[datetime], Optional[CandidateAvailabilitySlot]]:
    """AC-2. Returns (matched_start_utc, matched_slot) for the FIRST
    candidate slot (in date/time order) that has enough room in any
    free period, or (None, None)."""
    for slot in candidate_slots:
        slot_start_utc, slot_end_utc = _slot_to_utc_range(slot)
        for free_start, free_end in sorted(free_periods_utc, key=lambda f: f[0]):
            match_start = max(slot_start_utc, free_start)
            match_end = match_start + timedelta(minutes=duration_minutes)
            if match_end <= min(slot_end_utc, free_end):
                return match_start, slot
    return None, None


def _default_graph_call(interviewer_email: str, window_start_utc: datetime, window_end_utc: datetime) -> List[Tuple[datetime, datetime]]:
    import requests
    from app.core.graph_auth import get_graph_token

    access_token = get_graph_token()
    endpoint = (
        f"https://graph.microsoft.com/v1.0/users/{interviewer_email}/calendarView"
        f"?startDateTime={window_start_utc.isoformat()}&endDateTime={window_end_utc.isoformat()}&$orderby=start/dateTime"
    )
    resp = requests.get(endpoint, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    busy = []
    for event in resp.json().get("value", []):
        start_raw, start_tz = event["start"]["dateTime"], event["start"].get("timeZone", "UTC")
        end_raw, end_tz = event["end"]["dateTime"], event["end"].get("timeZone", "UTC")
        start = datetime.fromisoformat(start_raw).replace(tzinfo=ZoneInfo(start_tz) if start_tz != "UTC" else dt_timezone.utc).astimezone(dt_timezone.utc)
        end = datetime.fromisoformat(end_raw).replace(tzinfo=ZoneInfo(end_tz) if end_tz != "UTC" else dt_timezone.utc).astimezone(dt_timezone.utc)
        busy.append((start, end))
    return busy


def get_interviewer_busy_events(
    interviewer_email: str, window_start_utc: datetime, window_end_utc: datetime, *, graph_call: Optional[GraphCall] = None,
) -> List[Tuple[datetime, datetime]]:
    """Step 1. Raises on failure -- caller distinguishes a real
    "couldn't check the calendar" case from a genuine no-overlap."""
    call = graph_call or _default_graph_call
    return call(interviewer_email, window_start_utc, window_end_utc)


def _resolve_interviewer_user(db: Session, panel) -> Optional[Users]:
    employee = db.query(Employee).filter(Employee.id == panel.employee_id).first()
    if employee is None or not employee.wros_user_id:
        return None
    return db.query(Users).filter(Users.UserID == employee.wros_user_id).first()


def _notify_recruiter(db: Session, submission: Submission, message: str) -> None:
    if not submission.submitted_by_user_id:
        return  # no resolvable recipient -- honest no-op, not a fabricated fallback (see module docstring)
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P1", channel_preference="IN_APP", message=message,
        )
    except Exception as exc:
        logger.warning(f"[CalendarMatching] Failed to notify recruiter for submission {submission.id!r}: {exc}")


def attempt_calendar_match(
    db: Session, candidate: Candidate, conversation: CandidateConversation, tenant_id: str,
    *, level: str = "L1", duration_minutes: int = DEFAULT_INTERVIEW_DURATION_MINUTES, graph_call: Optional[GraphCall] = None,
    reschedule_count: int = 0, rescheduled_from_interview_id: Optional[str] = None, supersede_interview_id: Optional[str] = None,
) -> Dict:
    """Never raises. Returns one of:
      {"outcome": "insufficient_slots"}
      {"outcome": "no_open_submission"}
      {"outcome": "no_interviewer_assigned"}
      {"outcome": "calendar_check_failed"}
      {"outcome": "no_match", "message": ...}
      {"outcome": "matched", "interview_id": ..., "scheduled_at_utc": ..., "candidate_local_time": ..., "interviewer_local_time": ...}
    """
    try:
        slots = _unconfirmed_slots(db, candidate.candidateID, tenant_id)
        if len(slots) < MIN_VALID_SLOTS:
            return {"outcome": "insufficient_slots"}

        submission = _resolve_active_submission(db, candidate.candidateID)
        if submission is None:
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="calendar_match_failed", event_data={"reason": "no_open_submission"}, triggered_by="system"))
            db.commit()
            return {"outcome": "no_open_submission"}

        try:
            panel = get_assigned_interviewer(db, demand_id=submission.demand_id, interview_level=level, tenant_id=submission.tenant_id)
        except Exception:
            panel = None
        interviewer_user = _resolve_interviewer_user(db, panel) if panel else None

        if panel is None or interviewer_user is None:
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="calendar_match_failed", event_data={"reason": "no_interviewer_assigned"}, triggered_by="system"))
            db.commit()
            _notify_recruiter(db, submission, f"No interviewer is assigned to review {candidate.candidateFirstName or candidate.candidateID}'s interview -- please assign one.")
            return {"outcome": "no_interviewer_assigned"}

        # Derive the interviewer-LOCAL date range from the candidate
        # slots' actual UTC span, not by reusing candidate-local
        # calendar dates directly -- across a large offset (e.g. US
        # candidate / India interviewer) the "same" calendar date means
        # a completely different absolute time range in each timezone,
        # which would silently produce zero overlapping windows.
        slot_utc_ranges = [_slot_to_utc_range(s) for s in slots]
        overall_start_utc = min(r[0] for r in slot_utc_ranges)
        overall_end_utc = max(r[1] for r in slot_utc_ranges)
        interviewer_tz = ZoneInfo(interviewer_user.timezone or "Asia/Kolkata")
        min_date = overall_start_utc.astimezone(interviewer_tz).date()
        max_date = overall_end_utc.astimezone(interviewer_tz).date()
        windows = _business_hour_windows_utc(min_date, max_date, interviewer_user.timezone or "Asia/Kolkata")

        if not windows:
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="calendar_match_failed", event_data={"reason": "no_weekday_windows"}, triggered_by="system"))
            db.commit()
            return {"outcome": "no_match", "message": NO_MATCH_MESSAGE}

        try:
            busy_events = get_interviewer_busy_events(interviewer_user.UserEmail, windows[0][0], windows[-1][1], graph_call=graph_call)
        except Exception as exc:
            logger.warning(f"[CalendarMatching] Failed to read interviewer calendar for candidate {candidate.candidateID!r}: {exc}")
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="calendar_check_failed", event_data={"reason": str(exc)}, triggered_by="system"))
            db.commit()
            _notify_recruiter(db, submission, f"Couldn't verify the interviewer's calendar for {candidate.candidateFirstName or candidate.candidateID} -- please schedule manually.")
            return {"outcome": "calendar_check_failed"}

        free_periods: List[Tuple[datetime, datetime]] = []
        for window_start, window_end in windows:
            free_periods.extend(invert_busy_to_free(busy_events, window_start, window_end))

        match_start, matched_slot = find_matching_slot(slots, free_periods, duration_minutes)

        if match_start is None:
            db.query(CandidateAvailabilitySlot).filter(
                CandidateAvailabilitySlot.tenant_id == tenant_id, CandidateAvailabilitySlot.candidate_id == candidate.candidateID, CandidateAvailabilitySlot.is_confirmed == False,
            ).delete(synchronize_session=False)
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="calendar_match_failed", event_data={"reason": "no_overlap"}, triggered_by="system"))
            db.commit()
            _notify_recruiter(db, submission, f"No matching interview slot found for {candidate.candidateFirstName or candidate.candidateID} -- candidate has been asked for new availability.")
            return {"outcome": "no_match", "message": NO_MATCH_MESSAGE}

        if supersede_interview_id:
            # S-051/HRMS-0451: only mark the OLD interview superseded in
            # the SAME commit as creating the new one -- the partial
            # unique index (ix_one_current_interview_per_level) requires
            # the old row to no longer be "current" before a second
            # current row for the same submission+level can exist, but
            # the old row must stay untouched on every non-matched
            # outcome above (a stalled/failed reschedule attempt must
            # never silently orphan the candidate's still-valid old
            # interview).
            old_interview = db.query(SubmissionInterview).filter(SubmissionInterview.id == supersede_interview_id).first()
            if old_interview is not None:
                old_interview.superseded_at = datetime.utcnow()
                db.add(old_interview)
                db.flush()  # the UPDATE must land before create_interview()'s INSERT, or the partial unique index rejects it

        interview = create_interview(
            db, tenant_id=submission.tenant_id, submission=submission, level=level, panel=panel, scheduled_at=match_start,
            reschedule_count=reschedule_count, rescheduled_from_interview_id=rescheduled_from_interview_id,
        )
        matched_slot.is_confirmed = True
        db.add(matched_slot)
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="calendar_match_succeeded",
            event_data={"scheduled_at_utc": match_start.isoformat(), "interview_id": interview.id}, triggered_by="system",
        ))
        db.commit()

        return {
            "outcome": "matched",
            "interview_id": interview.id,
            "scheduled_at_utc": match_start,
            "candidate_local_time": match_start.astimezone(ZoneInfo(candidate.timezone or "Asia/Kolkata")),
            "interviewer_local_time": match_start.astimezone(ZoneInfo(interviewer_user.timezone or "Asia/Kolkata")),
        }
    except (L1NotPassed, NoEligibleInterviewer) as exc:
        logger.info(f"[CalendarMatching] Cannot schedule for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "no_interviewer_assigned"}
    except Exception as exc:
        logger.error(f"[CalendarMatching] Unexpected failure matching candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "calendar_check_failed"}
