"""Production operations, piped over SSH by .github/workflows/prod-ops.yml:

    OPS_COMMAND=... venv/bin/python - < backend/scripts/prod_ops.py   (cwd: backend/)

OPS_COMMAND:
  enroll-dry-run   how many existing candidates Thunder would enrol, and why others are excluded
  enroll           enrol up to OPS_LIMIT of them (starts staggered by the hourly send cap)
  smoke-candidate  create a candidate for OPS_EMAIL through the real queue (create_candidate ->
                   engage -> email cadence -> thunder_send_email) and follow it until the first
                   email is sent or held, printing every stage. OPS_TIMEZONE is set on the test
                   candidate so the candidate-local send window doesn't hold the email until morning.

Output masks other people's emails and never echoes a line that mentions a credential.
"""
import os
import re
import sys
import time
import traceback
import uuid
from datetime import datetime

sys.path.insert(0, os.getcwd())

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SECRETISH = re.compile(r"(secret|password|passwd|token|api[_-]?key|database_url)", re.IGNORECASE)
POLL_SECONDS, SMOKE_TIMEOUT = 5, 210


def say(text):
    text = str(text)
    if SECRETISH.search(text):
        text = "<line mentioning a credential: redacted>"
    print(EMAIL.sub("<email>", text), flush=True)


def enroll(dry_run: bool) -> int:
    from app.core.database import SessionLocal
    from app.services.thunder_mail.enrollment_service import enroll_existing_candidates

    limit = int(os.getenv("OPS_LIMIT") or "200")
    db = SessionLocal()
    try:
        result = enroll_existing_candidates(db, limit=limit, dry_run=dry_run)
    finally:
        db.close()
    for key, value in result.items():
        say(f"{key}: {value}")
    return 0


def _stage(db, candidate_id):
    from sqlalchemy import text

    rows = db.execute(text(
        "SELECT type, status, left(coalesce(error, ''), 140), created_at FROM channel_queue_item "
        "WHERE payload->>'candidate_id' = :cid ORDER BY created_at"), {"cid": candidate_id}).fetchall()
    sent = db.execute(text(
        "SELECT step, status, sent_at FROM thunder_email_messages WHERE candidate_id = :cid AND direction = 'OUT' "
        "ORDER BY created_at"), {"cid": candidate_id}).fetchall()
    return [f"queue {r[0]}: {r[1]} {r[2]}".rstrip() for r in rows] + \
           [f"email step {r[0]}: {r[1]} at {r[2]}" for r in sent], sent


def smoke(email: str, timezone: str) -> int:
    from sqlalchemy import text

    from app.core.database import SessionLocal
    from app.models.candidate import Candidate
    from app.models.thunder_email import ThunderCadenceState
    from app.services.message_queue_service import MessageQueueService

    if not email:
        say("OPS_EMAIL is required")
        return 2
    db = SessionLocal()
    try:
        db.execute(text("SET search_path TO app_schema, public"))
        candidate = db.query(Candidate).filter(Candidate.candidateEmail.ilike(email)).first()
        if candidate is None:
            task_id = str(uuid.uuid4())
            MessageQueueService.enqueue(task_name="create_candidate", task_id=task_id, data={
                "candidate_email": email, "candidate_first_name": "Avinash", "candidate_last_name": "Thunder Test",
                "candidate_source": "THUNDER_SMOKE_TEST", "thunder_enabled": True, "tenant_id": 1,
            })
            say(f"[{datetime.utcnow():%H:%M:%S}] queued create_candidate {task_id}")
        else:
            say(f"candidate already exists: {candidate.candidateID} thunder_enabled={candidate.thunder_enabled}")

        deadline, fixed_tz, seen = time.time() + SMOKE_TIMEOUT, False, []
        while time.time() < deadline:
            db.expire_all()
            candidate = db.query(Candidate).filter(Candidate.candidateEmail.ilike(email)).first()
            if candidate is not None and not fixed_tz:
                say(f"[{datetime.utcnow():%H:%M:%S}] candidate {candidate.candidateID} exists")
                candidate.timezone, candidate.thunder_enabled = timezone, True
                db.commit()
                fixed_tz = True
                if db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).first() is None \
                        and not db.execute(text("SELECT 1 FROM channel_queue_item WHERE type = 'engage_candidate_with_thunder' "
                                                "AND payload->>'candidate_id' = :cid"),
                                           {"cid": candidate.candidateID}).first():
                    # an existing candidate that was never engaged: engage it the same way creation does
                    MessageQueueService.enqueue(task_name="engage_candidate_with_thunder",
                                                task_id=f"smoke-engage-{candidate.candidateID}",
                                                data={"candidate_id": candidate.candidateID, "tenant_id": 1})
                    say("queued engage_candidate_with_thunder")
            if candidate is not None:
                # a step held only by the send window before the timezone was set goes now
                db.execute(text(
                    "UPDATE channel_queue_item SET next_retry_at = now() AT TIME ZONE 'utc' WHERE type = 'thunder_send_email' "
                    "AND status = 'PENDING' AND error LIKE 'NOT_SENT: outside candidate-local send window%' "
                    "AND payload->>'candidate_id' = :cid"), {"cid": candidate.candidateID})
                db.commit()
                lines, sent = _stage(db, candidate.candidateID)
                for line in lines:
                    if line not in seen:
                        seen.append(line)
                        say(f"[{datetime.utcnow():%H:%M:%S}] {line}")
                if any(r[1] == "SENT" for r in sent):
                    say("RESULT: first Thunder email SENT")
                    return 0
                if any(("FAILED" in line or "NOT_SENT" in line) for line in lines[-2:]) and time.time() > deadline - 60:
                    break
            time.sleep(POLL_SECONDS)
        say("RESULT: no email sent within the time limit; stages above show where it stopped")
        return 1
    finally:
        db.close()


def main() -> int:
    import importlib
    importlib.import_module("app.models")  # every table known before queries
    command = os.getenv("OPS_COMMAND", "")
    if command == "enroll-dry-run":
        return enroll(dry_run=True)
    if command == "enroll":
        return enroll(dry_run=False)
    if command == "smoke-candidate":
        return smoke(os.getenv("OPS_EMAIL", "").strip(), os.getenv("OPS_TIMEZONE") or "America/Los_Angeles")
    say(f"unknown OPS_COMMAND {command!r}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        for line in traceback.format_exc()[-3000:].splitlines():
            say(line)
        sys.exit(1)
