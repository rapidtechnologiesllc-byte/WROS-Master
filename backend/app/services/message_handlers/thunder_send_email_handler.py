"""Message Handler: thunder_send_email

Sends one cadence step (1-4, NURTURE-*, ACK_*) from the Thunder mailbox.
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
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail import cadence_service as cadence
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
        logger.info(f"[ThunderSend] handler_start candidate={candidate_id} seq={seq} step={step}")

        state = db.query(ThunderCadenceState).filter_by(candidate_id=candidate_id).first()
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if state is None or candidate is None:
            raise ValueError(f"No cadence/candidate for {candidate_id}")

        # validation 1: still the planned step (a reply or newer plan supersedes it)
        if state.stage == "STOPPED" or state.cadence_seq != seq or (not is_ack and state.next_step != step):
            logger.info(f"[ThunderSend] superseded candidate={candidate_id} step={step} plan={state.next_step}")
            return _done("superseded", candidate_id, step)

        # validation 2: permission to contact -- the organisation's Thunder kill switch first
        # (deferred, not dropped: the step goes out when Thunder is switched back on)
        from app.services.tenant_ai_config_service import is_thunder_enabled
        if not is_thunder_enabled(db, candidate.tenant_id):
            raise DeliveryDeferred("Thunder is switched off for this organisation", now + timedelta(hours=1))
        if cadence.email_consent_revoked(db, candidate_id):
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

        job = db.query(Jobs).filter(Jobs.jobID == state.job_id).first() if state.job_id else None
        out = db.query(ThunderEmailMessage).filter_by(
            candidate_id=candidate_id, cadence_seq=seq, step=step, direction="OUT").first()
        if out is not None and out.status == "SENT":
            return _done("already_sent", candidate_id, step, thunder_message_id=out.id)

        # validation 4: real content (nurture never sends an empty email)
        extra = {"source_note": cadence.source_note(db, candidate)}
        if step == "1":
            extra["hook"] = cadence.personal_hook(db, candidate)
        if step.startswith("NURTURE"):
            content = cadence.nurture_content(db, candidate, now)
            if content is None:
                cadence.schedule_after_send(state, step, now)
                db.commit()
                logger.info(f"[ThunderSend] nurture skipped for {candidate_id}: nothing new; next {state.next_step}")
                return _done("skipped_no_content", candidate_id, step, next_step=state.next_step)
            extra.update(content)

        try:
            if out is None:
                variant = choose_variant(db, cadence.step_family(step), rng=rng, job_available=job is not None)
                out = ThunderEmailMessage(
                    id=str(uuid.uuid4()), tenant_id=candidate.tenant_id, candidate_id=candidate_id,
                    direction="OUT", status="QUEUED", cadence_seq=seq, step=step, variant_id=variant.id,
                    mailbox=settings.THUNDER_MAILBOX,
                )
                db.add(out)
                db.commit()
            variant = db.query(ThunderOutreachVariant).filter_by(id=out.variant_id).one()
            subject, body = cadence.render(variant, candidate, job, extra)
            out.subject = subject
        except ValueError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise RuntimeError(f"Could not prepare {step} for {candidate_id}: {exc}") from exc

        mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
        if out.graph_message_id is None:
            thread_parent = ThunderSendEmailHandler._thread_parent(db, candidate_id, seq, step)
            if thread_parent:
                ids = mailbox.create_reply_draft(thread_parent, body)
            else:
                ids = mailbox.create_draft(candidate.candidateEmail, subject, body, out.id)
            out.graph_message_id, out.conversation_id, out.internet_message_id = ids
            out.status = "DRAFTED"
            db.commit()
            logger.info(f"[ThunderSend] drafted candidate={candidate_id} step={step} graph_id={out.graph_message_id}")

        if mailbox.is_draft(out.graph_message_id):
            mailbox.send(out.graph_message_id)

        out.status, out.sent_at = "SENT", now
        state.touches_sent += 1
        state.last_outbound_at = now
        cadence.schedule_after_send(state, step, now)
        db.commit()
        logger.info(
            f"[ThunderSend] handler_complete candidate={candidate_id} step={step} "
            f"variant={variant.key} next={state.next_step}@{state.next_action_at}"
        )
        try:
            from app.services.candidate_activity_service import log_thunder_operation
            log_thunder_operation(db, candidate_id, "MESSAGE_SENT", metadata={
                "channel": "email", "step": step, "variant": variant.key,
                "thunder_message_id": out.id, "mailbox": settings.THUNDER_MAILBOX,
            })
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"[ThunderSend] timeline log failed for {candidate_id} (email was sent): {exc}")

        return _done("sent", candidate_id, step, thunder_message_id=out.id, variant=variant.key,
                     message_sent=True, delivery_confirmed=True)

    @staticmethod
    def _thread_parent(db: Session, candidate_id: str, seq: int, step: str) -> Optional[str]:
        """Follow-ups reply in our thread; acks reply to the candidate's email."""
        if step.startswith("ACK_"):
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
        return latest.graph_message_id if latest else None
