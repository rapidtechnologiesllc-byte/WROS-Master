"""Candidate notices through Thunder (CEO 2026-10-31: "yes all 4 and every future candidate should get
the emails"). An interview cancelled or removed, a released offer withdrawn, and every pipeline
status (the rejection notice once per job) are queued on the Thunder mailbox path with its
guardrails: a real address and email consent, no no-contact period (except the rejection notice),
the candidate-local send window, the mailbox send caps, the tenant's template, once per ref. A
notice that cannot be queued never undoes the action."""
import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.consent import ConsentRecord
from app.models.offer_letter import OfferLetter
from app.models.pipeline_email import PipelineEmail
from app.models.tenant import Tenant
from app.models.user import Interview, InterviewPanel
from app.services.delivery_errors import DeliveryDeferred
from app.services.thunder_mail import candidate_notices as notices
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient, person

ENQUEUE = "app.services.thunder_mail.cadence_service.enqueue_once"
MONDAY_1030_IST = dt.datetime(2026, 11, 2, 5, 0)  # inside the 09-18 candidate-local window
SUNDAY = dt.datetime(2026, 11, 1, 5, 0)


def uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    if session.query(Tenant).filter_by(id=1).first() is None:
        session.add(Tenant(id=1, name="BlitzenX"))
        session.flush()
    notices_seed(session)
    yield session
    session.close()
    outer.rollback()
    connection.close()


def notices_seed(session):
    from app.services.candidate_status_notifications import seed_templates

    seed_templates(session, 1)
    session.flush()


def candidate(db, **kw) -> Candidate:
    c = Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Asha", candidateLastName="R",
                  candidateEmail=kw.pop("email", f"{uid()}@candidate.example.com"), candidatePassword="x",
                  tenant_id=1, timezone="Asia/Kolkata", **kw)
    db.add(c)
    db.commit()
    return c


def interview(db, c: Candidate, status="Cancelled"):
    panel = InterviewPanel(candidate_id=c.candidateID, round_name="Tech")
    db.add(panel)
    db.flush()
    start = dt.datetime(2026, 11, 3, 9, 30)
    row = Interview(panel_id=panel.id, candidate_id=c.candidateID, start_time=start,
                    end_time=start + dt.timedelta(hours=1), status=status)
    db.add(row)
    db.commit()
    return row


def test_a_cancelled_interview_is_queued_once_for_the_next_send_window(db):
    c = candidate(db)
    row = interview(db, c)
    with patch(ENQUEUE, return_value=True) as enqueue:
        email_id = notices.queue_notice(db, c, notices.INTERVIEW_CANCELLED,
                                        notices.interview_ref(row.id, row.start_time, "Tech"), now=SUNDAY)
        again = notices.queue_interview_cancelled(db, c.candidateID, row.id, row.start_time, "Tech")
    assert email_id == f"pe:{notices.INTERVIEW_CANCELLED}:{c.candidateID}:{row.id}:20261103T0930:Tech"
    assert again is None and enqueue.call_count == 1
    task, task_id = enqueue.call_args.args[:2]
    assert task == "send_pipeline_email" and task_id == email_id
    # Sunday -> Monday 09:00 IST (03:30 UTC): 22.5 hours later
    assert enqueue.call_args.kwargs["delay_seconds"] == int(dt.timedelta(hours=22, minutes=30).total_seconds())


def test_no_notice_without_consent_a_real_address_or_inside_a_no_contact_period(db):
    from app.services.candidate_contact_policy import record_rejection

    revoked = candidate(db)
    db.add(ConsentRecord(subject_id=revoked.candidateID, subject_type="candidate", consent_type="email_outreach",
                         consent_given=False, captured_by="candidate_email_reply"))
    placeholder = candidate(db, email=f"x{uid()}@linkedin-pending.blitzenx.com")
    rejected = candidate(db)
    record_rejection(db, rejected, "Not a fit")
    db.commit()
    with patch(ENQUEUE, return_value=True) as enqueue:
        for c in (revoked, placeholder, rejected):
            assert notices.queue_notice(db, c, notices.INTERVIEW_CANCELLED, f"1:20261103T0930:{c.candidateID}") is None
        # the rejection notice is what starts the no-contact period: it still goes
        assert notices.queue_notice(db, rejected, notices.REJECTED, "Rejected:JOB-1") is not None
        assert notices.queue_notice(db, rejected, notices.REJECTED, "Rejected:JOB-1") is None  # once per job
    assert enqueue.call_count == 1


def test_only_a_released_offer_is_withdrawn_to_the_candidate(db):
    c = candidate(db)
    common = dict(candidate_id=c.candidateID, position="Engineer", salary="24 LPA", offer_status="Cancelled",
                  joining_date=dt.date(2026, 12, 1), offer_expire_date=dt.date(2026, 11, 20))
    draft, released = OfferLetter(**common), OfferLetter(released_at=dt.datetime(2026, 10, 30), **common)
    db.add_all([draft, released])
    db.commit()
    with patch(ENQUEUE, return_value=True):
        assert notices.queue_offer_cancelled(db, draft) is None
        email_id = notices.queue_offer_cancelled(db, released)
    row = db.get(PipelineEmail, email_id)
    subject, body = notices.render(db, c, row, "BlitzenX", now=MONDAY_1030_IST)
    assert "BlitzenX" in subject and "Engineer" in body and "Asha" in body and "{{" not in subject + body


def test_at_send_time_the_window_and_caps_defer_and_an_undone_event_sends_nothing(db):
    c = candidate(db)
    row = interview(db, c)
    with patch(ENQUEUE, return_value=True):
        email = db.get(PipelineEmail, notices.queue_interview_cancelled(db, c.candidateID, row.id, row.start_time, "Tech"))
    with pytest.raises(DeliveryDeferred):
        notices.render(db, c, email, "BlitzenX", now=SUNDAY)  # outside the send window
    with patch.object(notices, "cap_retry_at", return_value=MONDAY_1030_IST + dt.timedelta(minutes=20)):
        with pytest.raises(DeliveryDeferred):
            notices.render(db, c, email, "BlitzenX", now=MONDAY_1030_IST)
    subject, body = notices.render(db, c, email, "BlitzenX", now=MONDAY_1030_IST)
    assert subject == "Your interview has been cancelled" and "Tech" in body and "Tuesday 03 November 2026" in body
    row.status = "Scheduled"  # put back on: the cancellation no longer applies
    db.commit()
    with pytest.raises(notices.NotSent):
        notices.render(db, c, email, "BlitzenX", now=MONDAY_1030_IST)


def test_a_status_notice_is_skipped_once_the_candidate_has_moved_on(db):
    c = candidate(db)
    db.add(CandidateStatus(candidateID=c.candidateID, piplineStatus="Interview", status="Active"))
    db.commit()
    with patch(ENQUEUE, return_value=True):
        email_id = notices.queue_status(db, c, "Screening")["email_id"]
    with pytest.raises(notices.NotSent):
        notices.render(db, c, db.get(PipelineEmail, email_id), "BlitzenX", now=MONDAY_1030_IST)


def test_deleting_a_scheduled_interview_tells_the_candidate_and_a_failed_queue_never_undoes_it(db):
    actor = person(db, full_access_role(db), "Recruiter")
    c = candidate(db)
    first, second = interview(db, c, status="Scheduled"), interview(db, c, status="Scheduled")
    api = ApiClient(db)
    try:
        with patch(ENQUEUE, return_value=True) as enqueue, \
                patch("app.services.staff_mail_service.queue_staff_email", return_value=True):
            assert api.delete(actor, f"/api/v1/interviews/{first.id}").status_code == 200
        assert any(call.args[1].startswith(f"pe:{notices.INTERVIEW_CANCELLED}:{c.candidateID}:{first.id}:")
                   for call in enqueue.call_args_list)
        with patch(ENQUEUE, side_effect=RuntimeError("queue down")), \
                patch("app.services.staff_mail_service.queue_staff_email", return_value=True):
            assert api.delete(actor, f"/api/v1/interviews/{second.id}").status_code == 200
    finally:
        api.close()
    assert db.get(Interview, second.id) is None
