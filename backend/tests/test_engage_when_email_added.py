"""A candidate added without an email is engaged by Thunder the moment a real address is added
(CEO 2026-11-02: a new candidate got no Thunder email; the address came after creation and the
contact-change handler looked for the wrong field names)."""
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.tenant import Tenant
from app.services.message_handlers.candidate_data_change_handler import CandidateDataChangeHandler

ENQUEUE = "app.services.thunder_mail.cadence_service.enqueue_once"


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _candidate(db, **extra):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                          candidateFirstName="Rajeswar", candidateLastName="Panja", thunder_enabled=True,
                          candidateEmail=f"r{uuid.uuid4().hex[:6]}@gmail.com", **extra)
    db.add(candidate)
    db.commit()
    return candidate


def _changed(db, candidate, fields):
    message = SimpleNamespace(id="m", payload={"candidate_id": candidate.candidateID, "changed_fields": fields})
    with patch(ENQUEUE, return_value=True) as enqueue:
        result = CandidateDataChangeHandler.process(message, db)
    return result, enqueue


def test_adding_an_email_queues_thunder_engagement_at_once(db):
    candidate = _candidate(db)
    result, enqueue = _changed(db, candidate, ["candidate_mobile", "candidate_email"])
    assert "thunder_engagement_queued" in result["actions_taken"]
    assert enqueue.call_args.args[0] == "engage_candidate_with_thunder"


def test_no_engagement_for_a_candidate_with_thunder_off(db):
    candidate = _candidate(db)
    candidate.thunder_enabled = False
    db.commit()
    result, enqueue = _changed(db, candidate, ["candidate_email"])
    assert enqueue.call_count == 0 and "thunder_engagement_queued" not in result["actions_taken"]
