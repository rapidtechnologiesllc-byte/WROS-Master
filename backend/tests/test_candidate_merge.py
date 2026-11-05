"""CEO 2026-11-04: "THE SAME CANDIDATE GOT created twice": 8910353068 and +918910353068 did not match, and there was
no way to merge the two records."""
import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_history import CandidateHistory
from app.models.thunder_email import ThunderCadenceState
from app.services import candidate_merge_service as merge
from app.services.candidate_service import find_duplicate_candidate
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


@pytest.fixture
def w(db):
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _candidate(db, tenant, first="Jane", last="Doe", email=None, mobile=None, **fields):
    row = Candidate(tenant_id=tenant, candidateID=f"CAN-{uuid.uuid4().hex[:12]}", candidatePassword="h", candidateFirstName=first,
                    candidateLastName=last, candidateEmail=email or f"j{uuid.uuid4().hex[:8]}@example.com",
                    candidateMobile=mobile, **fields)
    db.add(row)
    db.commit()
    return row


def _phone():
    return f"89{uuid.uuid4().int % 100000000:08d}"


def test_a_country_code_does_not_make_a_new_person(db, w):
    phone = _phone()
    existing = _candidate(db, w.org_user.tenant_id, mobile=phone)
    assert find_duplicate_candidate(db, mobile=f"+91{phone}")[0].candidateID == existing.candidateID
    assert find_duplicate_candidate(db, mobile=f"+91 {phone[:5]} {phone[5:]}")[1] == "phone"


def test_merge_moves_everything_fills_blanks_and_archives_the_duplicate(db, w):
    tenant = w.org_user.tenant_id
    kept = _candidate(db, tenant, mobile=_phone(), linkedin_url=None)
    dup = _candidate(db, tenant, first="Janet", mobile=None, linkedin_url="https://linkedin.com/in/jd")
    db.add(CandidateHistory(candidateID=dup.candidateID, event_type="Call", note="spoke", event_at=datetime.utcnow()))
    db.commit()
    dup_id, kept_id, dup_email = dup.candidateID, kept.candidateID, dup.candidateEmail
    result = merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    assert result["kept_candidate_id"] == kept_id
    db.expire_all()
    kept, dup = db.get(Candidate, kept_id), db.get(Candidate, dup_id)
    assert kept.candidateFirstName == "Jane" and kept.linkedin_url == "https://linkedin.com/in/jd"
    assert db.query(CandidateHistory).filter(CandidateHistory.candidateID == kept_id, CandidateHistory.event_type == "Call").count() == 1
    assert db.query(CandidateHistory).filter(CandidateHistory.candidateID == dup_id).count() == 0
    assert dup.merged_into_id == kept_id and dup.thunder_enabled is False
    assert db.query(CandidateStatus).filter(CandidateStatus.candidateID == dup_id).first().status == "Inactive"
    assert find_duplicate_candidate(db, email=dup_email)[0].candidateID == kept_id


def test_a_unique_counterpart_stays_and_the_duplicates_cadence_stops(db, w):
    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    db.add_all([ThunderCadenceState(candidate_id=kept.candidateID, tenant_id=tenant, stage="ACTIVE"),
                ThunderCadenceState(candidate_id=dup.candidateID, tenant_id=tenant, stage="ACTIVE", next_step="2",
                                    next_action_at=datetime.utcnow())])
    db.commit()
    dup_id, kept_id = dup.candidateID, kept.candidateID
    merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    db.expire_all()
    assert db.query(ThunderCadenceState).filter_by(candidate_id=kept_id).one().stage == "ACTIVE"
    left = db.query(ThunderCadenceState).filter_by(candidate_id=dup_id).one()
    assert left.stage == "STOPPED" and left.next_action_at is None


def test_refusals(db, w):
    tenant = w.org_user.tenant_id
    one, two, three = _candidate(db, tenant), _candidate(db, tenant), _candidate(db, tenant)
    with pytest.raises(merge.CandidateMergeError):
        merge.merge_candidates(db, one, one, merged_by=w.org_user.UserID)
    merge.merge_candidates(db, one, two, merged_by=w.org_user.UserID)
    with pytest.raises(merge.CandidateMergeError):
        merge.merge_candidates(db, one, three, merged_by=w.org_user.UserID)


def test_the_api_suggests_the_duplicate_and_merges(api, db, w):
    tenant = w.org_user.tenant_id
    phone = _phone()
    local = f"rajeswar{uuid.uuid4().hex[:6]}"
    older = _candidate(db, tenant, first="Rajeswar", last="Panja", email=f"{local}@gmail.com", mobile=phone)
    newer = _candidate(db, tenant, first="Rajeshwar", last="Panja", email=f"{local}@hotmail.com", mobile=f"+91{phone}")
    found = api.get(w.org_user, f"/api/v1/candidates/{newer.candidateID}/possible-duplicates")
    assert found.status_code == 200, found.text
    assert older.candidateID in [row["id"] for row in found.json()]
    done = api.post(w.org_user, f"/api/v1/candidates/{newer.candidateID}/merge", json={"into_candidate_id": older.candidateID})
    assert done.status_code == 200, done.text
    assert done.json()["kept_candidate_id"] == older.candidateID
    opened = api.get(w.org_user, f"/api/v1/candidates/{newer.candidateID}")
    assert opened.json()["merged_into_id"] == older.candidateID
    again = api.post(w.org_user, f"/api/v1/candidates/{newer.candidateID}/merge", json={"into_candidate_id": older.candidateID})
    assert again.status_code == 400


def test_the_journey_uses_the_candidates_own_organisation(api, db, w):
    candidate = _candidate(db, w.org_user.tenant_id)
    response = api.get(w.org_user, f"/api/v1/candidates/{candidate.candidateID}/journey")
    assert response.status_code == 200, response.text
    assert response.json()["stages"]


def test_the_conversation_on_the_duplicate_carries_to_the_record_kept(db, w):
    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    db.add_all([ThunderCadenceState(candidate_id=kept.candidateID, tenant_id=tenant, stage="ACTIVE", next_step="2", touches_sent=1,
                                    next_action_at=datetime(2026, 11, 11)),
                ThunderCadenceState(candidate_id=dup.candidateID, tenant_id=tenant, stage="HANDOFF", next_step="DETAILS-2", touches_sent=2,
                                    next_action_at=datetime(2026, 11, 19), last_inbound_at=datetime(2026, 11, 4))])
    db.commit()
    kept_id, dup_id = kept.candidateID, dup.candidateID
    merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    db.expire_all()
    state = db.query(ThunderCadenceState).filter_by(candidate_id=kept_id).one()
    assert (state.stage, state.next_step, state.next_action_at) == ("HANDOFF", "DETAILS-2", datetime(2026, 11, 19))
    assert state.touches_sent == 3 and state.last_inbound_at == datetime(2026, 11, 4)
    assert db.query(ThunderCadenceState).filter_by(candidate_id=dup_id).one().stage == "STOPPED"
