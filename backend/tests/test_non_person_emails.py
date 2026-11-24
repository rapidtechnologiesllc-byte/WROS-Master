"""A distribution list (the all-staff list, employees@blitzenx.com) is never a candidate, and
the app never sends email to it -- one automated message there reaches the whole company.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.email_policy import NonPersonEmailError, is_non_person_email
from app.models.candidate import Candidate, CandidateStatus
from app.services.candidate_contact_policy import ARCHIVED_STATUS, is_contactable
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient

DL = "employees@blitzenx.com"


def test_the_all_staff_list_is_recognised_in_any_case():
    assert is_non_person_email(DL)
    assert is_non_person_email(" Employees@BlitzenX.com ")
    assert not is_non_person_email("ria@blitzenx.com")


def test_no_candidate_can_hold_the_list_address(db):
    with pytest.raises(NonPersonEmailError):
        factories.candidate(db, candidateEmail=DL)
    candidate = factories.candidate(db)
    with pytest.raises(NonPersonEmailError):
        candidate.candidateSecondaryEmail = DL.upper()


def test_add_candidate_refuses_the_list_with_a_clear_400(db):
    admin = factories.user(db, role_template_id=full_access_role(db).id)
    db.commit()
    api = ApiClient(db)
    try:
        response = api.post(admin, "/api/v1/candidates/create",
                            json={"email": DL, "first_name": "All", "last_name": "Staff"})
    finally:
        api.close()
    assert response.status_code == 400
    assert "distribution list" in response.json()["detail"]


def test_email_service_never_sends_to_the_list():
    from app.services.email_service import EmailService

    with patch.object(EmailService, "_graph_post") as graph, patch.object(EmailService, "_get_token", return_value="t"):
        result = EmailService.send_email(to_email=DL, subject="Hello", body_content="<p>x</p>")
        assert result["status"] == "skipped" and "distribution list" in result["reason"]
        graph.assert_not_called()

        EmailService.send_email(to_email="ria@example.com", subject="Hi", body_content="x", cc_emails=[DL, "hr@example.com"])
        cc = [r["emailAddress"]["address"] for r in graph.call_args.args[1]["message"]["ccRecipients"]]
        assert cc == ["hr@example.com"]


def test_thunder_mailbox_will_not_draft_or_reply_to_the_list():
    from app.services.thunder_mail.graph_mailbox import GraphMailbox

    calls = []

    class Http:
        def request(self, method, url, **kw):
            calls.append((method, url))
            body = b'{"id": "draft-1", "toRecipients": [{"emailAddress": {"address": "employees@blitzenx.com"}}]}'
            return SimpleNamespace(status_code=201, headers={}, content=body, text="",
                                   json=lambda: {"id": "draft-1", "toRecipients": [{"emailAddress": {"address": DL}}]})

    mailbox = GraphMailbox("helpdesk@example.com", http=Http(), token_provider=lambda: "t")
    with pytest.raises(NonPersonEmailError):
        mailbox.create_draft(DL, "Subject", "<p>x</p>", "ref")
    assert calls == []  # nothing reached Graph
    with pytest.raises(NonPersonEmailError):
        mailbox.create_reply_draft("msg-1", "<p>x</p>")
    assert [m for m, _ in calls] == ["POST", "DELETE"]  # the reply draft was discarded unsent


def test_startup_archives_a_candidate_that_already_holds_the_list(db):
    from app.core.db_contract import _initialize_non_person_candidates

    candidate = factories.candidate(db)
    db.commit()
    # an old record from before the rule (written below the ORM, as legacy data was)
    db.execute(text('UPDATE app_schema.candidates SET "candidateEmail" = :e WHERE "candidateID" = :c'),
               {"e": DL, "c": candidate.candidateID})
    db.commit()
    db.expire_all()
    assert is_contactable(db, candidate)[0] is False  # even before the clean-up, nothing goes out

    _initialize_non_person_candidates(db)
    _initialize_non_person_candidates(db)  # idempotent

    db.expire_all()
    stored = db.get(Candidate, candidate.candidateID)
    assert stored.thunder_enabled is False
    status = db.query(CandidateStatus).filter_by(candidateID=candidate.candidateID).one()
    assert status.status == ARCHIVED_STATUS


def test_mailbox_intake_treats_the_list_as_internal():
    from app.services.thunder_mail.forward_intake_service import _is_our_own_address

    assert _is_our_own_address(DL, company_domains=set())
