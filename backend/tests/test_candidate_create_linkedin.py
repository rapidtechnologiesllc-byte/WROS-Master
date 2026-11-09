"""CEO 2026-11-09: the create candidate form takes a LinkedIn profile link. One spelling of the link is
stored, a link that isn't a profile is refused, and a profile already on a candidate is not added twice."""
from unittest.mock import patch

import pytest

from app.models.candidate import Candidate
from tests.test_referral_capture import _create_through_handler, _form, _headers, client, db, world  # noqa: F401

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


def _post(client, world, **extra):
    with patch(ENQUEUE, return_value={"task_id": "t", "message_id": "m"}) as enqueue, \
            patch("app.models.channel_queue.ChannelQueueItem"), patch("app.core.database.SessionLocal"):
        response = client.post("/api/v1/candidates/create", headers=_headers(world.user),
                               json=_form(candidate_source="LinkedIn", **extra))
    return response, enqueue


@pytest.mark.parametrize("typed", ["linkedin.com/in/jane-doe-42/", "https://in.linkedin.com/in/jane-doe-42?trk=x",
                                   "  https://www.linkedin.com/in/jane-doe-42  "])
def test_the_link_is_stored_in_one_spelling(client, world, typed):
    response, enqueue = _post(client, world, linkedin_url=typed)
    assert response.status_code in (200, 201, 202), response.text
    assert enqueue.call_args.kwargs["data"]["linkedin_url"] == "https://www.linkedin.com/in/jane-doe-42"


def test_a_link_that_is_not_a_profile_is_refused(client, world):
    response, enqueue = _post(client, world, linkedin_url="https://www.linkedin.com/company/blitzenx")
    assert response.status_code == 400 and "LinkedIn profile link" in response.json()["detail"]
    enqueue.assert_not_called()


def test_no_link_is_fine(client, world):
    response, enqueue = _post(client, world)
    assert response.status_code in (200, 201, 202), response.text
    assert enqueue.call_args.kwargs["data"]["linkedin_url"] is None


def test_a_profile_already_on_a_candidate_is_not_added_twice(client, db, world):
    existing = _create_through_handler(db, {**_form(), "linkedin_url": "https://www.linkedin.com/in/jane-doe-42"})
    response, enqueue = _post(client, world, linkedin_url="linkedin.com/in/Jane-Doe-42")
    assert response.status_code == 409 and existing.candidateID in response.json()["detail"]
    enqueue.assert_not_called()


def test_the_created_candidate_keeps_the_link(db, world):
    candidate = _create_through_handler(db, {**_form(), "linkedin_url": "https://www.linkedin.com/in/sam-lee"})
    assert db.get(Candidate, candidate.candidateID).linkedin_url == "https://www.linkedin.com/in/sam-lee"
