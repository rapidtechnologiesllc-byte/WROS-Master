"""CEO 2026-11-04: "THE SAME CANDIDATE GOT created twice": 8910353068 and +918910353068 did not match, and there was
no way to merge the two records."""
import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateMerge, CandidateStatus
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


def test_merge_moves_everything_fills_blanks_and_leaves_one_record(db, w):
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
    assert dup is None  # one person, one record (CEO 2026-11-09)
    assert db.get(CandidateMerge, dup_id).kept_id == kept_id
    assert db.query(CandidateStatus).filter(CandidateStatus.candidateID == dup_id).count() == 0
    assert find_duplicate_candidate(db, email=dup_email)[0].candidateID == kept_id
    note = db.query(CandidateHistory).filter(CandidateHistory.candidateID == kept_id,
                                             CandidateHistory.note.like("Merged Janet Doe%")).one()
    assert "both histories shown here as one" in note.note


def test_the_kept_records_own_status_and_cadence_win_and_the_duplicates_go(db, w):
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
    assert db.query(ThunderCadenceState).filter_by(candidate_id=dup_id).count() == 0


def test_refusals(db, w):
    tenant = w.org_user.tenant_id
    one, two, three = _candidate(db, tenant), _candidate(db, tenant), _candidate(db, tenant)
    with pytest.raises(merge.CandidateMergeError):
        merge.merge_candidates(db, one, one, merged_by=w.org_user.UserID)
    one_id, three_id = one.candidateID, three.candidateID
    merge.merge_candidates(db, one, two, merged_by=w.org_user.UserID)
    db.expire_all()
    assert db.get(Candidate, one_id) is None and db.get(Candidate, three_id) is not None


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
    newer_id, older_id = newer.candidateID, older.candidateID
    opened = api.get(w.org_user, f"/api/v1/candidates/{newer_id}")  # the old link
    assert opened.status_code == 200, opened.text
    assert opened.json()["merged_into_id"] == older_id and opened.json()["candidate_id"] == older_id
    again = api.post(w.org_user, f"/api/v1/candidates/{newer_id}/merge", json={"into_candidate_id": older_id})
    assert again.status_code == 400 and "already merged into" in again.json()["detail"]
    assert db.query(Candidate).filter(Candidate.candidateID.in_([older_id, newer_id])).count() == 1


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
    assert db.query(ThunderCadenceState).filter_by(candidate_id=dup_id).count() == 0


def test_both_emails_stay_primary_and_secondary_and_either_finds_the_record(db, w):
    tenant = w.org_user.tenant_id
    phone = _phone()
    kept = _candidate(db, tenant, mobile=_phone())
    dup = _candidate(db, tenant, mobile=phone)
    kept_id, primary, second = kept.candidateID, kept.candidateEmail, dup.candidateEmail
    merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    db.expire_all()
    kept = db.get(Candidate, kept_id)
    assert kept.candidateEmail == primary and kept.candidateSecondaryEmail == second
    assert kept.candidateSecondaryMobile == phone
    assert find_duplicate_candidate(db, email=second)[0].candidateID == kept_id
    assert find_duplicate_candidate(db, mobile=phone)[0].candidateID == kept_id


def test_a_one_per_candidate_record_is_combined_onto_the_record_kept(db, w):
    from app.models.candidate_engagement_metrics import CandidateEngagementMetrics as Metrics

    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    db.add_all([Metrics(tenant_id=str(tenant), candidate_id=kept.candidateID),
                Metrics(tenant_id=str(tenant), candidate_id=dup.candidateID, avg_response_time_minutes=42)])
    db.commit()
    kept_id, dup_id = kept.candidateID, dup.candidateID
    result = merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    db.expire_all()
    assert db.query(Metrics).filter_by(candidate_id=dup_id).count() == 0
    assert db.query(Metrics).filter_by(candidate_id=kept_id).one().avg_response_time_minutes == 42
    assert result["removed_candidate_id"] == dup_id


def test_a_secondary_email_cannot_belong_to_someone_else(api, db, w):
    tenant = w.org_user.tenant_id
    one, two = _candidate(db, tenant), _candidate(db, tenant)
    taken = api.put(w.org_user, f"/api/v1/candidates/hr/update_candidate/{one.candidateID}", json={"candidate_secondary_email": two.candidateEmail})
    assert taken.status_code == 409, taken.text
    fine = api.put(w.org_user, f"/api/v1/candidates/hr/update_candidate/{one.candidateID}", json={"candidate_secondary_email": "other.address@example.com"})
    assert fine.status_code == 200, fine.text
    assert api.get(w.org_user, f"/api/v1/candidates/{one.candidateID}").json()["candidate_secondary_email"] == "other.address@example.com"


def test_a_removed_records_phone_still_finds_the_record_kept(db, w):
    tenant = w.org_user.tenant_id
    kept = _candidate(db, tenant, mobile=_phone())
    first_dup, second_dup = _candidate(db, tenant, mobile=_phone()), _candidate(db, tenant, mobile=_phone())
    phones = (first_dup.candidateMobile, second_dup.candidateMobile)
    kept_id = kept.candidateID
    merge.merge_candidates(db, first_dup, kept, merged_by=w.org_user.UserID)  # its phone becomes the secondary
    merge.merge_candidates(db, second_dup, db.get(Candidate, kept_id), merged_by=w.org_user.UserID)  # secondary taken
    for phone in phones:
        assert find_duplicate_candidate(db, mobile=f"+91{phone}")[0].candidateID == kept_id


def test_a_merge_into_a_record_merged_away_leads_to_its_record(db, w):
    tenant = w.org_user.tenant_id
    a, b, c = _candidate(db, tenant), _candidate(db, tenant), _candidate(db, tenant)
    a_id, b_id, c_id = a.candidateID, b.candidateID, c.candidateID
    merge.merge_candidates(db, a, b, merged_by=w.org_user.UserID)  # a -> b
    merge.merge_candidates(db, db.get(Candidate, b_id), c, merged_by=w.org_user.UserID)  # b -> c
    assert merge.kept_record_for_id(db, a_id) == c_id and merge.kept_record_for_id(db, b_id) == c_id


def test_a_second_open_pipeline_is_closed_and_kept_with_its_history(db, w):
    from app.models.hiring_pipeline import HiringPipeline, HiringPipelineEvent

    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    for c in (kept, dup):
        pipeline = HiringPipeline(candidate_id=c.candidateID, tenant_id=tenant, stage="L1")
        db.add(pipeline)
        db.flush()
        db.add(HiringPipelineEvent(pipeline_id=pipeline.id, to_stage="L1", trigger="created"))
    db.commit()
    kept_id = kept.candidateID
    merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    pipelines = db.query(HiringPipeline).filter_by(candidate_id=kept_id).all()
    assert len(pipelines) == 2 and sum(1 for p in pipelines if p.closed_at is None) == 1
    assert db.query(HiringPipelineEvent).filter(HiringPipelineEvent.pipeline_id.in_([p.id for p in pipelines])).count() == 2


def test_nothing_changes_when_something_cannot_move(db, w, monkeypatch):
    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    kept_id, dup_id = kept.candidateID, dup.candidateID
    monkeypatch.setattr(merge, "_still_pointing_at", lambda db, cid: {"some_table": 1})
    with pytest.raises(merge.CandidateMergeError, match="some_table"):
        merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    assert db.get(Candidate, dup_id) is not None and db.get(CandidateMerge, dup_id) is None
    assert db.get(Candidate, kept_id) is not None


def test_an_archived_merge_from_before_is_folded_into_one_record(db, w):
    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    db.add_all([CandidateStatus(candidateID=kept.candidateID, status="Active", piplineStatus="Interview"),
                CandidateStatus(candidateID=dup.candidateID, status="Inactive"),
                ThunderCadenceState(candidate_id=kept.candidateID, tenant_id=tenant, stage="ACTIVE", touches_sent=3),
                ThunderCadenceState(candidate_id=dup.candidateID, tenant_id=tenant, stage="STOPPED", touches_sent=3)])
    dup.merged_into_id = kept.candidateID  # how a merge left it before 2026-11-09
    db.commit()
    kept_id, dup_id = kept.candidateID, dup.candidateID
    assert merge.finish_archived_merges(db) == 1
    db.commit()
    db.expire_all()
    assert db.get(Candidate, dup_id) is None and db.get(CandidateMerge, dup_id).kept_id == kept_id
    assert db.query(CandidateStatus).filter_by(candidateID=kept_id).one().status == "Active"
    assert db.query(ThunderCadenceState).filter_by(candidate_id=kept_id).one().touches_sent == 3  # not counted twice
    assert merge.finish_archived_merges(db) == 0


def test_an_older_table_only_the_database_knows_moves_too(db, w):
    from sqlalchemy import text

    db.execute(text('CREATE TABLE app_schema.legacy_merge_probe (id serial PRIMARY KEY, candidate_id varchar(512) '
                    'REFERENCES app_schema.candidates("candidateID"))'))
    tenant = w.org_user.tenant_id
    kept, dup = _candidate(db, tenant), _candidate(db, tenant)
    kept_id, dup_id = kept.candidateID, dup.candidateID
    db.execute(text("INSERT INTO app_schema.legacy_merge_probe (candidate_id) VALUES (:c)"), {"c": dup_id})
    db.commit()
    merge.merge_candidates(db, dup, kept, merged_by=w.org_user.UserID)
    rows = db.execute(text("SELECT candidate_id FROM app_schema.legacy_merge_probe")).scalars().all()
    assert rows == [kept_id] and db.get(Candidate, dup_id) is None
