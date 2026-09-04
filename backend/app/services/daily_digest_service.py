"""
import logging
S-065/HRMS-0465 -- Thunder Daily Digest / Morning Report.

Real architecture adaptations:
- No `thunder_activity_feed` table -- reuses S-061's real activity
  vocabulary (the 8 whitelisted real ConversationEvent types) directly.
  `recruiter_intervention_queue` (S-062) and `candidate_drop_risk`
  (S-060) are real, already-built tables, reused as-is.
- No `interviews` table matching this spec's shape -- the real source
  is `SubmissionInterview` (S-047-052 chain), joined through
  `Submission` for the candidate and `DemandInterviewPanel`/`Employee`
  for the interviewer name (same real chain S-052's own
  `_interviewer_name()` uses; duplicated locally here rather than
  cross-imported, same small-private-helper posture this session has
  used repeatedly).
- No `system_configuration` table -- `digest_enabled` is a real,
  per-recruiter `Users` column (BR-related toggle this story's own UI
  fields table asks for); the send TIME itself (08:00 local) is a
  module constant, not separately admin-configurable -- same
  "code constant, no admin UI yet, documented gap" posture this whole
  session has used for every other missing system_configuration need.
- "For each active recruiter in tenant" has no single clean literal
  recipient list in this codebase (RBAC roles aren't a reliable proxy
  for "owns candidates"). The real, honest signal already established
  and reused throughout S-046/S-057/S-058/S-060/S-062 for "who should
  be notified about this candidate" is `Submission.submitted_by_user_id`
  -- so a digest is personalized per distinct submitted_by_user_id
  found among that recruiter's own candidates' recent activity/queue
  items/interviews, not a blind tenant-wide broadcast.
- WhatsApp delivery is NOT actually sendable in this codebase --
  `notification_service.py`'s own `ChannelNotConfigured` gap (no
  WhatsApp Business API credentials provisioned) applies here exactly
  as it does everywhere else this session. The WhatsApp-formatted text
  is still built for real (Step 3, ready for when a provider exists),
  but only the EMAIL leg (Step 4, a real, working channel) is actually
  dispatched -- logged honestly, not silently faked as sent.
- BR-03 deep links use the real `Settings.FRONTEND_BASE_URL` (same
  constant `candidate_portal_service.py` already uses), pointing at
  `/candidates/{id}?tab=messages`.
"""
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.submission import Submission
from app.models.user import Users
from app.services.activity_feed_service import ACTIVITY_EVENT_TYPES, _candidate_display_name
from app.services.email_service import EmailService

DIGEST_LOCAL_HOUR = 8  # BR-01, module constant -- see docstring
OVERNIGHT_CUTOFF_HOUR = 18  # "since 6 PM yesterday"
TOP_RISKS_COUNT = 3
QUEUE_ITEMS_MAX = 5

def _candidate_link(candidate_id: str) -> str:
    return f"{Settings.FRONTEND_BASE_URL.rstrip('/')}/candidates/{candidate_id}?tab=messages"

def _interviewer_name(db: Session, panel_id: Optional[str]) -> str:
    if not panel_id:
        return "our interviewer"
    panel = db.query(DemandInterviewPanel).filter(DemandInterviewPanel.id == panel_id).first()
    if panel is None:
        return "our interviewer"
    employee = db.query(Employee).filter(Employee.id == panel.employee_id).first()
    if employee is None:
        return "our interviewer"
    return f"{employee.first_name} {employee.last_name}".strip() or "our interviewer"

def _my_candidate_ids(db: Session, recruiter_user_id: str) -> List[str]:
    """Candidates whose most recent real Submission is owned by this
    recruiter -- see module docstring on the recipient-resolution gap."""
    rows = (
        db.query(Submission.candidate_id)
        .filter(Submission.submitted_by_user_id == recruiter_user_id)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]

def _overnight_activity(db: Session, tenant_id: str, candidate_ids: List[str], since: datetime) -> Dict:
    if not candidate_ids:
        return {"summary": "No overnight activity.", "count": 0, "responded": []}

    events = (
        db.query(ConversationEvent, CandidateConversation)
        .join(CandidateConversation, ConversationEvent.conversation_id == CandidateConversation.id)
        .filter(
            CandidateConversation.tenant_id == tenant_id, CandidateConversation.candidate_id.in_(candidate_ids),
            ConversationEvent.event_type.in_(ACTIVITY_EVENT_TYPES), ConversationEvent.created_at >= since,
        )
        .all()
    )
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()}

    type_counts: Dict[str, int] = {}
    responded = []
    for event, conv in events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
        if event.event_type == "candidate_reply":
            candidate = candidates_by_id.get(conv.candidate_id)
            name = _candidate_display_name(candidate)
            body = (event.event_data or {}).get("body", "")[:60]
            responded.append({"candidate_id": conv.candidate_id, "name": name, "summary": body, "link": _candidate_link(conv.candidate_id)})

    parts = []
    if type_counts.get("candidate_reply"):
        parts.append(f"{type_counts['candidate_reply']} candidate repl{'y' if type_counts['candidate_reply'] == 1 else 'ies'}")
    if type_counts.get("STATE_TRANSITION"):
        parts.append(f"{type_counts['STATE_TRANSITION']} state change(s)")
    if type_counts.get("INTERVIEW_CONFIRMED"):
        parts.append(f"{type_counts['INTERVIEW_CONFIRMED']} interview(s) scheduled")
    if type_counts.get("CANDIDATE_GHOSTED"):
        parts.append(f"{type_counts['CANDIDATE_GHOSTED']} ghosting detection(s)")
    if type_counts.get("OFFER_RELEASED"):
        parts.append(f"{type_counts['OFFER_RELEASED']} offer(s) released")

    summary = "Thunder " + (", ".join(parts) + " overnight." if parts else "had no notable overnight activity.")
    return {"summary": summary, "count": sum(type_counts.values()), "responded": responded}

def _needs_attention(db: Session, tenant_id: str, candidate_ids: List[str]) -> List[Dict]:
    if not candidate_ids:
        return []
    items = (
        db.query(RecruiterInterventionQueue)
        .filter(RecruiterInterventionQueue.tenant_id == tenant_id, RecruiterInterventionQueue.candidate_id.in_(candidate_ids), RecruiterInterventionQueue.status == "OPEN")
        .order_by(RecruiterInterventionQueue.priority.asc(), RecruiterInterventionQueue.added_at.asc())
        .limit(QUEUE_ITEMS_MAX)
        .all()
    )
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()}
    return [
        {
            "candidate_id": item.candidate_id,
            "name": _candidate_display_name(candidates_by_id.get(item.candidate_id)),
            "reason": item.queue_reason,
            "detail": item.reason_detail,
            "link": _candidate_link(item.candidate_id),
        }
        for item in items
    ]

def _interviews_today(db: Session, candidate_ids: List[str], recruiter_timezone: str, today_local: date) -> List[Dict]:
    if not candidate_ids:
        return []
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(recruiter_timezone or "Asia/Kolkata")
    day_start_local = datetime.combine(today_local, time.min).replace(tzinfo=tz)
    day_end_local = datetime.combine(today_local, time.max).replace(tzinfo=tz)
    start_utc = day_start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = day_end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    interviews = (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.candidate_id.in_(candidate_ids), SubmissionInterview.superseded_at.is_(None), SubmissionInterview.scheduled_at.between(start_utc, end_utc))
        .order_by(SubmissionInterview.scheduled_at.asc())
        .all()
    )
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()}
    results = []
    for interview in interviews:
        local_time = interview.scheduled_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        results.append({
            "candidate_id": interview.candidate_id,
            "name": _candidate_display_name(candidates_by_id.get(interview.candidate_id)),
            "level": interview.level,
            "local_time": local_time.strftime("%I:%M %p %Z"),
            "interviewer": _interviewer_name(db, interview.panel_id),
            "link": _candidate_link(interview.candidate_id),
        })
    return results

def _top_risks(db: Session, tenant_id: str, candidate_ids: List[str]) -> List[Dict]:
    if not candidate_ids:
        return []
    rows = (
        db.query(CandidateDropRisk)
        .filter(CandidateDropRisk.tenant_id == tenant_id, CandidateDropRisk.candidate_id.in_(candidate_ids))
        .order_by(CandidateDropRisk.drop_risk_score.desc())
        .limit(TOP_RISKS_COUNT)
        .all()
    )
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()}
    from app.services.risk_dashboard_service import _top_risk_signal
    return [
        {
            "candidate_id": row.candidate_id,
            "name": _candidate_display_name(candidates_by_id.get(row.candidate_id)),
            "score": row.drop_risk_score,
            "top_signal": _top_risk_signal(row.risk_signals or {}),
            "link": _candidate_link(row.candidate_id),
        }
        for row in rows
    ]

def generate_daily_digest(db: Session, recruiter_user_id: str, tenant_id: str, *, now: Optional[datetime] = None) -> Dict:
    """Step 2. Never raises internally beyond what callers should catch."""
    recruiter = db.query(Users).filter(Users.UserID == recruiter_user_id).first()
    now = now or datetime.utcnow()
    recruiter_tz = recruiter.timezone if recruiter else "Asia/Kolkata"

    candidate_ids = _my_candidate_ids(db, recruiter_user_id)

    yesterday = (now - timedelta(days=1)).date()
    since = datetime.combine(yesterday, time(hour=OVERNIGHT_CUTOFF_HOUR))

    overnight = _overnight_activity(db, tenant_id, candidate_ids, since)
    needs_attention = _needs_attention(db, tenant_id, candidate_ids)
    interviews_today = _interviews_today(db, candidate_ids, recruiter_tz, now.date())
    top_risks = _top_risks(db, tenant_id, candidate_ids)

    has_content = overnight["count"] > 0 or len(needs_attention) > 0 or len(interviews_today) > 0  # BR-02

    return {
        "recruiter_user_id": recruiter_user_id,
        "date": now.date().isoformat(),
        "overnight_activity": overnight,
        "responded": overnight["responded"],
        "needs_attention": needs_attention,
        "interviews_today": interviews_today,
        "top_risks": top_risks,
        "has_content": has_content,
    }

def format_whatsapp_digest(digest: Dict) -> str:
    """Step 3. Plain text, emoji section headers, WhatsApp-appropriate."""
    lines = [f"📊 *THUNDER MORNING DIGEST — {digest['date']}*", ""]
    lines.append(f"⚡ *Overnight:* {digest['overnight_activity']['summary']}")
    if digest["responded"]:
        responded_str = ", ".join(f"{r['name']} ({r['summary'] or 'replied'})" for r in digest["responded"][:5])
        lines.append(f"📨 *Responded:* {responded_str}")
    if digest["needs_attention"]:
        needs_str = ", ".join(f"{i['name']} ({i['reason'].replace('_', ' ').title()})" for i in digest["needs_attention"])
        lines.append(f"🚨 *Needs You:* {needs_str}")
    if digest["interviews_today"]:
        interviews_str = ", ".join(f"{i['name']} — {i['level']} — {i['local_time']} with {i['interviewer']}" for i in digest["interviews_today"])
        lines.append(f"📅 *Interviews Today:* {interviews_str}")
    if digest["top_risks"]:
        risks_str = ", ".join(f"{r['name']} ({r['score']})" for r in digest["top_risks"])
        lines.append(f"⚠️ *Top Risks:* {risks_str}")
    lines.append("")
    lines.append(f"View full dashboard: {Settings.FRONTEND_BASE_URL.rstrip('/')}/recruiter/risk-dashboard")
    return "\n".join(lines)

def format_email_digest_html(digest: Dict) -> str:
    """Step 4. Simple, real HTML -- BR-03: every candidate name is a link."""

    def link_list(items, formatter):
        if not items:
            return "<p>None.</p>"
        return "<ul>" + "".join(f'<li><a href="{i["link"]}">{formatter(i)}</a></li>' for i in items) + "</ul>"

    html = f"""
    <h2>⚡ Thunder Morning Digest — {digest['date']}</h2>
    <h3>Overnight Activity</h3>
    <p>{digest['overnight_activity']['summary']}</p>
    <h3>Candidates Who Responded</h3>
    {link_list(digest['responded'], lambda r: f"{r['name']} — {r['summary'] or 'replied'}")}
    <h3>Needs Your Attention Today</h3>
    {link_list(digest['needs_attention'], lambda i: f"{i['name']} — {i['reason'].replace('_', ' ').title()}" + (f" ({i['detail']})" if i['detail'] else ""))}
    <h3>Interviews Today</h3>
    {link_list(digest['interviews_today'], lambda i: f"{i['name']} — {i['level']} — {i['local_time']} with {i['interviewer']}")}
    <h3>Top Risks</h3>
    {link_list(digest['top_risks'], lambda r: f"{r['name']} — {r['score']} ({r['top_signal']})")}
    <p><a href="{Settings.FRONTEND_BASE_URL.rstrip('/')}/recruiter/risk-dashboard">View Full Dashboard</a></p>
    <p>-- Thunder, your AI Recruiting Assistant<br/>BlitzenX</p>
    """
    return html

def send_daily_digest(db: Session, recruiter_user_id: str, tenant_id: str) -> Dict:
    """Step 1's per-recruiter body. Never raises."""
    try:
        recruiter = db.query(Users).filter(Users.UserID == recruiter_user_id).first()
        if recruiter is None:
            return {"outcome": "recruiter_not_found"}
        if not recruiter.digest_enabled:
            return {"outcome": "disabled"}

        digest = generate_daily_digest(db, recruiter_user_id, tenant_id)
        if not digest["has_content"]:
            logger.info(f"[DailyDigest] DIGEST_SKIPPED_NO_CONTENT for recruiter {recruiter_user_id!r}")
            return {"outcome": "skipped_no_content"}

        item_count = len(digest["needs_attention"])
        subject = f"⚡ Thunder Morning Digest — {digest['date']} | {item_count} item(s) need your attention"
        html_body = format_email_digest_html(digest)

        email_sent = False
        try:
            result = EmailService.send_email(recruiter.UserEmail, subject, html_body, is_html=True)
            email_sent = result.get("status") == "success"
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[DailyDigest] DIGEST_EMAIL_FAILED for recruiter {recruiter_user_id!r}: {exc}")

        # WhatsApp Business API is not provisioned in this codebase (same
        # gap notification_service.py's own ChannelNotConfigured already
        # documents) -- the text is still built for real, not sent.
        whatsapp_text = format_whatsapp_digest(digest)
        logger.warning(f"[DailyDigest] DIGEST_WHATSAPP_FAILED for recruiter {recruiter_user_id!r}: WhatsApp Business API not provisioned in this codebase.")

        return {"outcome": "sent", "email_sent": email_sent, "whatsapp_sent": False, "whatsapp_text": whatsapp_text}
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[DailyDigest] Failed generating/sending digest for recruiter {recruiter_user_id!r}: {exc}")
        return {"outcome": "failed"}

def run_daily_digest_job(db: Session) -> Dict:
    """Step 1. Runs on a real periodic cadence (every 30 min); fires for
    each recruiter whose local hour is DIGEST_LOCAL_HOUR right now.
    BR-01: local timezone, per real Users.timezone."""

    result = {"processed": 0, "sent": 0, "skipped": 0}
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))

    tenant_ids = {row[0] for row in db.query(CandidateConversation.tenant_id).distinct().all() if row[0]}
    for tenant_id in tenant_ids:
        recruiter_ids = {
            row[0] for row in db.query(Submission.submitted_by_user_id)
            .join(Candidate, Submission.candidate_id == Candidate.candidateID)
            .join(CandidateConversation, CandidateConversation.candidate_id == Candidate.candidateID)
            .filter(CandidateConversation.tenant_id == tenant_id, Submission.submitted_by_user_id.isnot(None))
            .distinct().all()
        }
        for recruiter_id in recruiter_ids:
            result["processed"] += 1
            try:
                recruiter = db.query(Users).filter(Users.UserID == recruiter_id).first()
                if recruiter is None:
                    result["skipped"] += 1
                    continue
                local_hour = now_utc.astimezone(ZoneInfo(recruiter.timezone or "Asia/Kolkata")).hour
                digest_hour = DIGEST_LOCAL_HOUR
                # S-077/HRMS-0477: real per-tenant digest_send_time
                # ("HH:MM"). This job's own cadence is 30-min, so only
                # the hour component is honored -- same precision this
                # check already had pre-S-077, just no longer hardcoded.
                try:
                    from app.services.tenant_ai_config_service import get_tenant_ai_config
                    send_time = get_tenant_ai_config(db, tenant_id).get("digest_send_time")
                    if send_time:
                        digest_hour = int(str(send_time).split(":")[0])
                except Exception:
                    pass
                if local_hour != digest_hour:
                    result["skipped"] += 1
                    continue
                outcome = send_daily_digest(db, recruiter_id, tenant_id)
                if outcome.get("outcome") == "sent":
                    result["sent"] += 1
                else:
                    result["skipped"] += 1
            except Exception as exc:
                logger.error(f"Error: {str(exc)}", exc_info=True)
                logger.error(f"[DailyDigest] Failed processing recruiter {recruiter_id!r}: {exc}")
                result["skipped"] += 1

    return result
