"""Message Handler: thunder_process_inbound_email

A candidate emailed the Thunder mailbox (reply or new thread). Classify it,
credit the A/B variant of the touch that earned it, re-plan the cadence, open
a recruiter task where a human must act, and queue any acknowledgement.

A reply that keeps the conversation going also completes the profile: any missing
details it contains are read out (the profile-completion extractor) and saved, and
the acknowledgement asks for whatever is still missing. Reading the details is
best effort: when it fails the recruiter task says so and the reply is still handled.

Compensation: classification runs before any state write; a failure in the
write phase rolls back and the message is retried with the same input.
"""
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage
from app.models.user import Jobs
from app.services.ai_conversation_service import extract_fields_from_reply, get_missing_fields, merge_fields_to_db
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail import cadence_service as cadence
from app.services.thunder_mail.reply_classifier import classify_reply

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 75
# Replies that end or pause the conversation: no details are read and none are asked for
STOP_INTENTS = ("UNSUBSCRIBE", "HOSTILE", "AUTO", "NOT_NOW", "NOT_INTERESTED")


def profile_note(saved: List[str], missing: List[Dict[str, str]], error: Optional[str],
                 ack_step: Optional[str]) -> str:
    """What the reply did to the profile, for the recruiter's task."""
    lines = []
    if saved:
        lines.append("Saved from this reply: " + ", ".join(saved))
    if error:
        lines.append(f"Profile details in this reply could not be read automatically ({error}): check the email.")
    if missing:
        asked = " (Thunder asked for them in its reply)" if ack_step else ""
        lines.append("Still missing: " + ", ".join(m["label"] for m in missing) + asked)
    return "\n".join(lines)


class ThunderInboundEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, llm_call: Optional[Callable] = None,
                field_llm_call: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
        payload = message.payload or {}
        row_id = payload.get("thunder_message_id")
        if not row_id:
            raise ValueError(f"Message {message.id} missing thunder_message_id")
        logger.info(f"[ThunderInbound] handler_start message={row_id}")

        row = db.query(ThunderEmailMessage).filter_by(id=row_id, direction="IN").first()
        if row is None:
            raise ValueError(f"Inbound email {row_id} not found")
        if row.status == "PROCESSED":
            return {"status": "already_processed", "thunder_message_id": row_id, "intent": row.intent}

        candidate = db.query(Candidate).filter(Candidate.candidateID == row.candidate_id).first()
        if candidate is None:
            raise ValueError(f"Candidate {row.candidate_id} for inbound {row_id} not found")

        result = classify_reply(db, row.tenant_id, row.candidate_id, row.subject, row.body_text,
                                payload.get("headers"), llm_call=llm_call)
        logger.info(f"[ThunderInbound] classified message={row_id} intent={result.intent} source={result.source}")
        extracted, extraction_error = ThunderInboundEmailHandler._read_profile_details(
            db, candidate, row, result.intent, field_llm_call)

        try:
            state = db.query(ThunderCadenceState).filter_by(candidate_id=row.candidate_id).with_for_update().one()
            credited = db.query(ThunderEmailMessage).filter(
                ThunderEmailMessage.candidate_id == row.candidate_id, ThunderEmailMessage.direction == "OUT",
                ThunderEmailMessage.status == "SENT", ThunderEmailMessage.sent_at <= row.received_at,
            ).order_by(ThunderEmailMessage.sent_at.desc()).first()
            job = db.query(Jobs).filter(Jobs.jobID == state.job_id).first() if state.job_id else None
            previous_stage = state.stage
            saved = merge_fields_to_db(candidate.candidateID, extracted, db)["updated"] if extracted else []
            still_missing = get_missing_fields(candidate, db) if result.intent not in STOP_INTENTS else []
            actions = cadence.apply_reply(db, state, candidate, result.intent, result.erasure_requested,
                                          job, datetime.utcnow(), missing_fields=still_missing)

            row.intent, row.intent_confidence, row.intent_source = result.intent, result.confidence, result.source
            row.credited_out_id = credited.id if credited and result.intent != "AUTO" else None
            row.status, row.processed_at = "PROCESSED", datetime.utcnow()
            row.step = actions["ack_step"]
            if actions["handoff"]:
                ThunderInboundEmailHandler._handoff_task(db, candidate, row, actions["handoff"], profile_note(
                    saved, still_missing, extraction_error, actions["ack_step"]))
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"[ThunderInbound] write phase failed for {row_id}: {exc}", exc_info=True)
            raise RuntimeError(f"Inbound processing failed for {row_id}: {exc}") from exc

        logger.info(
            f"[ThunderInbound] handler_complete message={row_id} candidate={row.candidate_id} "
            f"stage {previous_stage}->{state.stage} next={state.next_step}@{state.next_action_at}"
        )
        if actions["ack_step"]:
            cadence.enqueue_once(
                cadence.SEND_TASK, cadence.send_task_id(state.candidate_id, state.cadence_seq, actions["ack_step"]),
                {"candidate_id": state.candidate_id, "cadence_seq": state.cadence_seq,
                 "step": actions["ack_step"], "tenant_id": state.tenant_id},
                state.tenant_id,
            )
        try:
            from app.services.candidate_activity_service import log_email_received
            log_email_received(db, row.candidate_id, row.subject, row.body_text)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"[ThunderInbound] timeline log failed for {row_id} (reply was processed): {exc}")

        return {"status": "processed", "thunder_message_id": row_id, "intent": result.intent,
                "stage": state.stage, "ack_step": actions["ack_step"], "handoff": bool(actions["handoff"]),
                "fields_saved": saved, "fields_missing": [f["field"] for f in still_missing]}

    @staticmethod
    def _read_profile_details(db: Session, candidate: Candidate, row: ThunderEmailMessage, intent: str,
                              llm_call: Optional[Callable[[str], str]]) -> Tuple[Dict[str, Any], Optional[str]]:
        """(field -> value read from the reply, error). Runs before the write phase (an LLM call);
        a failure is returned, not raised: the reply is still classified and handed off."""
        if intent in STOP_INTENTS or not (row.body_text or "").strip():
            return {}, None
        missing = get_missing_fields(candidate, db)
        if not missing:
            return {}, None
        try:
            return extract_fields_from_reply(row.body_text, missing, llm_call=llm_call), None
        except Exception as exc:
            logger.error(f"[ThunderInbound] could not read profile details from {row.id}: {exc}", exc_info=True)
            return {}, str(exc)

    @staticmethod
    def _handoff_task(db: Session, candidate: Candidate, row: ThunderEmailMessage, title: str, note: str) -> None:
        from app.services.task_service import create_task

        name = " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName]))
        task = create_task(
            db, title=f"{title}: {name or candidate.candidateEmail}"[:255],
            description=(
                f"Thunder classified this email as {row.intent} ({row.intent_source}).\n"
                + (f"{note}\n" if note else "") +
                f"From: {row.from_address}\nSubject: {row.subject}\n\n{(row.body_text or '')[:1500]}"
            ),
            priority="HIGH", category="THUNDER_REPLY", tenant_id=candidate.tenant_id,
            assigned_to_user_id=candidate.assigned_recruiter_id, due_date=datetime.utcnow(),
            candidate_id=candidate.candidateID, link=f"/candidates/{candidate.candidateID}",
        )
