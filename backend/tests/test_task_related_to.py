"""My Tasks says what each task is about (CEO 2026-11-02: "we need to add a related to column to say
which candidate or user it is related to")."""
import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.task_service import create_task
from tests.scope_fixtures import ApiClient, two_bu_world


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def test_my_day_says_which_candidate_a_task_is_about(db):
    w = two_bu_world(db)
    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:8]}", candidateEmail="j@example.com",
                          candidatePassword="h", candidateFirstName="Joss", candidateLastName="Sequeira")
    db.add(candidate)
    db.commit()
    create_task(db, title="Candidate is interested", tenant_id=1, assigned_to_user_id=w.org_user.UserID,
                due_date=datetime.utcnow(), candidate_id=candidate.candidateID)
    create_task(db, title="Plain to-do", tenant_id=1, assigned_to_user_id=w.org_user.UserID, due_date=datetime.utcnow())
    api = ApiClient(db)
    try:
        rows = {t["title"]: t for t in api.get(w.org_user, "/api/v1/tasks/my-day").json()}
    finally:
        api.close()
    assert (rows["Candidate is interested"]["related_kind"], rows["Candidate is interested"]["related_name"]) == \
        ("Candidate", "Joss Sequeira")
    assert rows["Candidate is interested"]["related_link"] == f"/candidates/{candidate.candidateID}"
    assert rows["Plain to-do"]["related_name"] is None
