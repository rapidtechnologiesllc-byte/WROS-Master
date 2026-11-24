"""Message Handler: thunder_send_email

Sends one cadence step (1-4, NURTURE-*, ACK_*) from the Thunder mailbox, or one personal email:
an upcoming-role email (ROLE-<id>, role_outreach_service) or a reply a person approved (REPLY-<id>,
reply_draft_service, threaded under the candidate's email). A personal email has its own subject and
body, no template, and leaves the cadence plan untouched.
Anything that prevents sending (credentials, permission, send window, caps,
cooldown) raises DeliveryDeferred: the queue keeps the message PENDING as
"not sent". Draft-then-send is idempotent across retries: the draft id is
committed before sending and checked with is_draft before any resend.

Compensation: nothing is deleted on failure. A draft created but never sent
stays in the mailbox's Drafts folder and is re-used by the next attempt.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage, ThunderOutreachVariant
from app.models.user import Jobs
from app.services.candidate_contact_policy import is_contactable, rejection_cooldown_until
from app.services.delivery_errors import DeliveryDeferred
from app.services.mail_sender import connected_mailbox, mailbox_for_address
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail import cadence_service as cadence
from app.services.thunder_mail import preflight
from app.services.thunder_mail.graph_mailbox import GraphMailbox
from app.services.thunder_mail.variant_selector import choose_variant

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 55
THREADED_STEPS = ("2", "3", "4")


def _done(status: str, candidate_id: str, step: str, **extra) -> Dict[str, Any]:
    return {"status": status, "candidate_id": candidate_id, "step": step, **extra}


class ThunderSendEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None, rng=None) -> Dict[str, Any]:
        payload = message.payload or {}
        candidate_id, step = payload.get("candidate_id"), payload.get("step")
        seq = int(payload.get("cadence_seq") or 1)
        if not candidate_id or not step:
            raise ValueError(f"Message {message.id} missing candidate_id/step")
        now = datetime.utcnow()
        is_ack = step.startswith("ACK_")
        is_details = step.startswith(cadence.DETAILS)
        from app.services import reply_draft_service as personal_mail
        # ROLE-<id> (upcoming-role email) and REPLY-<id> (an approved reply): their own text, no template
        role_outreach = personal_mail.personal_email_for(db, step)
        if personal_mail.is_personal_step(step) and role_outreach is None:
            raise ValueError(f"Message {message.id}: no personal email for step {step}")
        if role_outreach is not None and not personal_mail.ready_to_send(role_outreach):
            return _done("superseded" if role_outreach.status != "SENT" else "already_sent", candidate_id, step)
        logger.info(f"[ThunderSend] handler_start candidate={candidate_id} seq={seq} step={step}")

        state = db.query(ThunderCadenceState).filter_by(candidate_id=candidate_id).first()
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if state is None or candidate is None:
            raise ValueError(f"No cadence/candidate for {candidate_id}")

        # validation 1: still the planned step (a reply or newer plan supersedes it)
        if state.stage == "STOPPED" or state.cadence_seq != seq or (
                not is_ack and role_outreach is None and state.next_step != step):
            logger.info(f"[ThunderSend] superseded candidate={candidate_id} step={step} plan={state.next_step}")
            return _done("superseded", candidate_id, step)

        # validation 2: permission to contact -- the organisation's Thunder kill switch first
        # (deferred, not dropped: the step goes out when Thunder is switched back on)
        from app.services.tenant_ai_config_service import is_thunder_enabled
        if not is_thunder_enabled(db, candidate.tenant_id):
            raise DeliveryDeferred("Thunder is switched off for this organisation", now + timedelta(hours=1))
        if cadence.email_consent_revoked(db, candidate_id):
            if role_outreach is not None:
                role_outreach.status, role_outreach.note = "DISCARDED" if hasattr(role_outreach, "in_message_id")                     else "SKIPPED", "email consent revoked"
            cadence.stop(db, state, candidate, "email consent revoked")
            db.commit()
            return _done("stopped", candidate_id, step, reason="email consent revoked")
        contactable, reason = is_contactable(db, candidate)
        if not contactable:
            until = rejection_cooldown_until(db, candidate_id)
            raise DeliveryDeferred(f"not contactable: {reason}", until or now + timedelta(days=1))

        # validation 3: timing and volume
        if not is_ack:
            slot = cadence.next_send_slot(candidate, now)
            if slot is not None:
                raise DeliveryDeferred("outside candidate-local send window", slot)
            if state.last_outbound_at and now - state.last_outbound_at < timedelta(hours=settings.THUNDER_MIN_GAP_HOURS):
                raise DeliveryDeferred("minimum gap between emails",
                                       state.last_outbound_at + timedelta(hours=settings.THUNDER_MIN_GAP_HOURS))
        cap_retry = cadence.send_cap_retry_at(db, now)
        if cap_retry:
            raise DeliveryDeferred("mailbox send cap reached", cap_retry)

        job_id = state.job_id or candidate.job_id
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first() if job_id else None
        if role_outreach is None and step == "1" and job is None:
            # No job linked: Thunder picks the open role that best fits their skills and title itself,
            # and keeps it for the follow-ups and the answers to their questions
            matched = cadence.matching_open_jobs(db, candidate, limit=1)
            if matched:
                job = matched[0]
                state.job_id = job.jobID
                logger.info(f"[ThunderSend] {candidate_id}: no job linked; matched to {job.jobID} ({job.jobTitle})")
        if role_outreach is None and preflight.is_cold(step):
            # Thunder's check before a cold email: what do we already know about them? (preflight)
            decision = preflight.check(db, candidate, step, job, now)
            preflight.record(db, candidate, step, decision)
            db.commit()
            if decision.action == "WARM":
                return ThunderSendEmailHandler._go_warm(db, state, candidate, step, now)
            if decision.action == "WAIT":
                raise DeliveryDeferred("; ".join(decision.reasons), decision.retry_at)
            if step == "1":
                ThunderSendEmailHandler._withdraw_brief_requests(db, candidate_id)
        out = db.query(ThunderEmailMessage).filter_by(
            candidate_id=candidate_id, cadence_seq=seq, step=step, direction="OUT").first()
        if out is not None and out.status == "SENT":
            return _done("already_sent", candidate_id, step, thunder_message_id=out.id)

        # validation 4: real content (nurture never sends an empty email)
        extra = {"source_note": cadence.source_note(db, candidate)}
        if step == "1":
            extra["hook"] = cadence.personal_hook(db, candidate)
        if is_ack or is_details:
            from app.services.ai_conversation_service import get_missing_fields
            missing = get_missing_fields(candidate, db, include_documents=True)
            if is_details and not missing:
                cadence.plan_after_engagement(db, state, now, missing)
                db.commit()
                logger.info(f"[ThunderSend] details reminder skipped for {candidate_id}: profile complete; "
                            f"next {state.next_step}")
                return _done("skipped_profile_complete", candidate_id, step, next_step=state.next_step)
            extra["fields_request"] = cadence.fields_request_html(missing)
        if step.startswith("NURTURE"):
            content = cadence.nurture_content(db, candidate, now)
            if content is None:
                cadence.schedule_after_send(state, step, now)
                db.commit()
                logger.info(f"[ThunderSend] nurture skipped for {candidate_id}: nothing new; next {state.next_step}")
                return _done("skipped_no_content", candidate_id, step, next_step=state.next_step)
            extra.update(content)

        try:
            if role_outreach is not None:
                variant = None
                if out is None:
                    out = ThunderEmailMessage(
                        id=str(uuid.uuid4()), tenant_id=candidate.tenant_id, candidate_id=candidate_id,
                        direction="OUT", status="QUEUED", cadence_seq=seq, step=step, variant_id=None,
                        mailbox=settings.THUNDER_MAILBOX,
                    )
                    db.add(out)
                    db.commit()
                subject, body = role_outreach.subject, role_outreach.body_html
                out.subject, out.body_text = subject, cadence.plain_text(body)
            elif out is None:
                variant = choose_variant(db, cadence.step_family(step), rng=rng, job_available=job is not None,
                                         role_first=step == "1")
                out = ThunderEmailMessage(
                    id=str(uuid.uuid4()), tenant_id=candidate.tenant_id, candidate_id=candidate_id,
                    direction="OUT", status="QUEUED", cadence_seq=seq, step=step, variant_id=variant.id,
                    mailbox=settings.THUNDER_MAILBOX,
                )
                db.add(out)
                db.commit()
            if role_outreach is None:
                variant = db.query(ThunderOutreachVariant).filter_by(id=out.variant_id).one()
                subject, body = cadence.render(variant, candidate, job, extra)
                out.subject, out.body_text = subject, cadence.plain_text(body)
        except ValueError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise RuntimeError(f"Could not prepare {step} for {candidate_id}: {exc}") from exc

        return ThunderSendEmailHandler._deliver(db, out, state, candidate, step, subject, body, now, mailbox,
                                                variant, is_details, missing if is_details else None, role_outreach)

    @staticmethod
    def _deliver(db: Session, out: ThunderEmailMessage, state: ThunderCadenceState, candidate: Candidate,
                 step: str, subject: str, body: str, now: datetime, mailbox: Optional[GraphMailbox], variant,
                 is_details: bool, missing, role_outreach) -> Dict[str, Any]:
        """Draft (once), send, record and move the plan on. An upcoming-role email leaves the
        cadence plan as it was and marks its RoleOutreach sent."""
        candidate_id = candidate.candidateID
        seq = out.cadence_seq
        if out.graph_message_id is None:
            if role_outreach is not None:
                from app.services.reply_draft_service import thread_parent_of
                parent = thread_parent_of(db, role_outreach)
            else:
                parent = ThunderSendEmailHandler._thread_parent(db, candidate_id, seq, step)
            mailbox = mailbox or ThunderSendEmailHandler._sender(db, candidate, parent)
            out.mailbox = getattr(mailbox, "mailbox", None) or settings.THUNDER_MAILBOX
            # a reply goes in the thread, which lives in the mailbox it started in
            in_thread = parent is not None and (parent.mailbox or "").lower() == out.mailbox.lower()
            if in_thread:
                ids = mailbox.create_reply_draft(parent.graph_message_id, body)
            else:
                ids = mailbox.create_draft(candidate.candidateEmail, subject, body, out.id)
            out.graph_message_id, out.conversation_id, out.internet_message_id = ids
            out.status = "DRAFTED"
            db.commit()
            logger.info(f"[ThunderSend] drafted candidate={candidate_id} step={step} graph_id={out.graph_message_id}")

        else:
            mailbox = mailbox or mailbox_for_address(db, out.mailbox or settings.THUNDER_MAILBOX)
        if mailbox.is_draft(out.graph_message_id):
            mailbox.send(out.graph_message_id)

        out.status, out.sent_at = "SENT", now
        state.touches_sent += 1
        state.last_outbound_at = now
        if role_outreach is not None:
            from app.services.reply_draft_service import mark_personal_sent
            mark_personal_sent(db, role_outreach, out.id, now)
        else:
            cadence.schedule_after_send(state, step, now)
        if is_details:
            db.flush()  # this reminder counts towards the cap
            cadence.plan_after_engagement(db, state, now, missing)
        db.commit()
        logger.info(
            f"[ThunderSend] handler_complete candidate={candidate_id} step={step} "
            f"variant={variant.key if variant else 'personal'} next={state.next_step}@{state.next_action_at}"
        )
        try:
            from app.services.candidate_activity_service import log_thunder_operation
            log_thunder_operation(db, candidate_id, "MESSAGE_SENT", metadata={
                "channel": "email", "step": step, "variant": variant.key if variant else "personal",
                "thunder_message_id": out.id, "mailbox": out.mailbox,
            })
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"[ThunderSend] timeline log failed for {candidate_id} (email was sent): {exc}")

        return _done("sent", candidate_id, step, thunder_message_id=out.id, variant=variant.key if variant else "personal",
                     message_sent=True, delivery_confirmed=True)

    @staticmethod
    def _go_warm(db: Session, state: ThunderCadenceState, candidate: Candidate, step: str, now: datetime) -> Dict:
        from app.services.ai_conversation_service import get_missing_fields

        missing = get_missing_fields(candidate, db, include_documents=True)
        state.stage = "HANDOFF"
        if missing:
            cadence.plan_after_engagement(db, state, now, missing)
            state.next_action_at = now
        else:
            state.next_step, state.next_action_at = None, None
        db.commit()
        if missing:
            cadence.enqueue_send(state)
        logger.info(f"[ThunderSend] {candidate.candidateID}: in conversation, no cold {step}; "
                    f"next {state.next_step or 'none'}")
        return _done("skipped_in_conversation", candidate.candidateID, step, next_step=state.next_step)

    @staticmethod
    def _withdraw_brief_requests(db: Session, candidate_id: str) -> None:
        """Thunder no longer waits for a person to name the role: the open "which role?" requests
        raised for this candidate before 2026-11-10 are closed as it writes the first email."""
        from app.models.task import Task

        closed = db.query(Task).filter(Task.category == "THUNDER_BRIEF", Task.candidate_id == candidate_id,
                                       Task.status.in_(("NEW", "IN_PROGRESS", "ON_HOLD")))             .update({Task.status: "CANCELLED"}, synchronize_session=False)
        if closed:
            db.commit()
            logger.info(f"[ThunderSend] {candidate_id}: {closed} role request task(s) withdrawn")

    @staticmethod
    def _sender(db: Session, candidate: Candidate, parent: Optional[ThunderEmailMessage]) -> GraphMailbox:
        """The thread's own mailbox when it can still be reached; else (a new thread) the
        candidate's recruiter's Outlook when connected, helpdesk copied; else the HRMS mailbox."""
        if parent is not None and parent.mailbox:
            try:
                return mailbox_for_address(db, parent.mailbox)
            except DeliveryDeferred as exc:  # that person disconnected Outlook: a new thread instead
                logger.warning(f"[ThunderSend] {candidate.candidateID}: thread mailbox unavailable ({exc}); "
                               "starting a new thread")
        return connected_mailbox(db, candidate.assigned_recruiter_id) or GraphMailbox(settings.THUNDER_MAILBOX)

    @staticmethod
    def _thread_parent(db: Session, candidate_id: str, seq: int, step: str) -> Optional[ThunderEmailMessage]:
        """Follow-ups reply in our thread; acks and details reminders reply to the candidate's email."""
        if step.startswith("ACK_") or step.startswith(cadence.DETAILS):
            direction = "IN"
        elif step in THREADED_STEPS:
            direction = "OUT"
        else:
            return None
        latest = db.query(ThunderEmailMessage).filter(
            ThunderEmailMessage.candidate_id == candidate_id, ThunderEmailMessage.cadence_seq == seq,
            ThunderEmailMessage.direction == direction, ThunderEmailMessage.graph_message_id.isnot(None),
            ThunderEmailMessage.status.in_(("SENT", "RECEIVED", "PROCESSED")),
        ).order_by(ThunderEmailMessage.created_at.desc()).first()
        return latest
