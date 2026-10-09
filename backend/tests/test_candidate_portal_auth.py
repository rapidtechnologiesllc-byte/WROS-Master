"""Candidates can use their own routes with a candidate token: portal, offers, checklists,
document uploads. Those routes used to also require a staff (Users) permission, so every
candidate call returned 401. A candidate answers only their own *released* offer, and
staff tokens can't act as a candidate."""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_candidate
from app.core.security import create_access_token
from app.models.candidate import Candidate, CandidateStatus
from app.models.offer_letter import OfferLetter
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Users

STAFF_ONLY = {"role_template_permission_check", "any_internal_user", "admin_role_only"}


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def client(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = db.query(RoleTemplate).filter_by(tenant_id=1, name="Super Admin").first() or \
        RoleTemplate(tenant_id=1, name="Super Admin", display_name="Super Admin", enabled=True)
    db.add(role)
    db.flush()
    hr = Users(UserID=f"HR-{_uid()}", UserName="HR", UserEmail=f"hr{_uid()}@blitzenx.com", UserPassword="x",
               UserRole="admin", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    me = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"me{_uid()}@example.com", candidatePassword="x",
                   candidateFirstName="Mia", candidateLastName="Lee", tenant_id=1)
    other = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"o{_uid()}@example.com", candidatePassword="x",
                      candidateFirstName="Oz", candidateLastName="K", tenant_id=1)
    db.add_all([hr, me, other])
    db.flush()

    def offer(candidate, status):
        row = OfferLetter(candidate_id=candidate.candidateID, position="Engineer", salary="1200000",
                          joining_date=date.today() + timedelta(days=30),
                          offer_expire_date=date.today() + timedelta(days=7), offer_status=status,
                          created_by=hr.UserID)
        db.add(row)
        db.flush()
        return row

    offers = {"released": offer(me, "Released"), "approved": offer(me, "Approved"),
              "others": offer(other, "Released")}
    db.commit()
    return hr, me, offers


def _candidate_headers(candidate):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": candidate.candidateID, "type": "candidate", "tenant_id": 1})}


def _staff_headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _dependency_calls(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependency_calls(dep)


def test_no_route_mixes_candidate_auth_with_a_staff_check():
    """A route can't authenticate a candidate AND require a staff permission: no token
    satisfies both, so the route is dead (this is how the portal returned 401 everywhere)."""
    from app.main import app

    mixed = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        calls = list(_dependency_calls(route.dependant))
        if get_current_candidate in calls and any(
                getattr(c, "__wros_authn__", None) in STAFF_ONLY or "require_" in getattr(c, "__qualname__", "")
                for c in calls):
            mixed.append(f"{sorted(route.methods)} {route.path}")
    assert mixed == []


def test_candidate_reaches_their_own_routes_and_staff_cannot(client, world):
    hr, me, _ = world
    for path in ["/api/v1/portal/home", "/api/v1/offer-letter/my-offers", "/api/v1/portal/offers",
                 "/api/v1/checklist/candidate/my-checklists"]:
        assert client.get(path, headers=_candidate_headers(me)).status_code == 200, path
        assert client.get(path, headers=_staff_headers(hr)).status_code in (401, 403), path


def test_candidate_sees_only_their_visible_offers(client, world):
    _, me, offers = world
    listed = client.get("/api/v1/portal/offers", headers=_candidate_headers(me)).json()
    assert [o["id"] for o in listed["offers"]] == [offers["released"].id]  # not the unreleased one, not others'


def test_portal_accept_moves_offer_to_accepted(client, db, world):
    _, me, offers = world
    with patch("app.services.email_service.EmailService.notify_hr_candidate_responded") as mail:
        response = client.post(f"/api/v1/portal/offers/{offers['released'].id}/respond",
                               headers=_candidate_headers(me), json={"action": "accept", "message": "Excited!"})
    assert response.status_code == 200, response.text
    assert response.json()["offer_status"] == "Accepted" and mail.call_count == 1
    db.expire_all()
    assert db.get(OfferLetter, offers["released"].id).offer_status == "Accepted"
    assert db.query(CandidateStatus).filter_by(candidateID=me.candidateID).one().piplineStatus == "Hired"
    # answered once: a second answer is refused
    again = client.post(f"/api/v1/portal/offers/{offers['released'].id}/respond",
                        headers=_candidate_headers(me), json={"action": "decline"})
    assert again.status_code == 400


def test_candidate_cannot_answer_unreleased_or_someone_elses_offer(client, world):
    _, me, offers = world
    unreleased = client.post(f"/api/v1/portal/offers/{offers['approved'].id}/respond",
                             headers=_candidate_headers(me), json={"action": "accept"})
    assert unreleased.status_code == 400
    others = client.post(f"/api/v1/portal/offers/{offers['others'].id}/respond",
                         headers=_candidate_headers(me), json={"action": "accept"})
    assert others.status_code == 404
    bad = client.post(f"/api/v1/portal/offers/{offers['released'].id}/respond",
                      headers=_candidate_headers(me), json={"action": "maybe"})
    assert bad.status_code == 400


def test_signing_an_unreleased_offer_is_refused(client, world):
    _, me, offers = world
    response = client.post(f"/api/v1/offer-letter/sign/{offers['approved'].id}", headers=_candidate_headers(me),
                           files={"signature": ("sig.png", b"\x89PNG\r\n", "image/png")})
    assert response.status_code == 400, response.text


def test_legacy_respond_route_uses_the_same_rules(client, world):
    _, me, offers = world
    with patch("app.services.email_service.EmailService.notify_hr_candidate_responded"):
        response = client.post("/api/v1/offer-letter/respond", headers=_candidate_headers(me),
                               json={"offer_id": offers["released"].id, "action": "reject"})
    assert response.status_code == 200 and response.json()["offer_status"] == "Rejected"
