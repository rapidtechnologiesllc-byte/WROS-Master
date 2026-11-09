"""CEO 2026-11-09: a leader may waive L1 or L2 with a reason on record. The round counts as passed;
every later gate still applies, a No Hire can't be waived away, and only BU Head and above may do it."""
import pytest

from app.models.candidate_history import CandidateHistory
from app.models.hiring_pipeline import HiringPipelineEvent, HiringRoundWaiver
from app.models.task import Task
from app.services import hiring_pipeline_service as pipeline
from tests.test_function_access import _person as _function_person
from tests.test_one_stage_and_landing import _log, _stage, _status, api, person  # noqa: F401 -- fixtures
from tests.test_expense_review_and_pnl import db, w  # noqa: F401 -- fixtures

REASON = "Assessed directly by the client architect on the earlier engagement"


@pytest.fixture
def leader(db, w):
    """Someone whose role template sits at BU Head level, allowed to move the hiring pipeline."""
    from app.core.db_contract import ensure_role
    from app.models.role_template import Module, Resource, RoleTemplate
    from tests.scope_fixtures import uid
    from tests.test_expense_review_and_pnl import _logger

    module = db.query(Module).filter_by(name="Personal", tenant_id=1).first() or \
        Module(name="Personal", display_name="Personal", tenant_id=1)
    db.add(module)
    db.flush()
    for name in ("convert-to-employee", "my-tasks"):
        if db.query(Resource).filter_by(name=name).first() is None:
            db.add(Resource(module_id=module.id, name=name, display_name=name, tenant_id=1))
    db.flush()
    name = f"BU Head {uid()}"
    ensure_role(db, name, {"display_name": name, "description": "test", "hierarchy_level": 14, "org_level_access": False,
                           "permissions": {"ve": ["convert-to-employee"], "vce": ["my-tasks"]}}, 1)
    user = _logger(db, w)
    user.role_template_id = db.query(RoleTemplate).filter_by(name=name, tenant_id=1).one().id
    db.commit()
    return user


def _waive(db, user, person, level, reason=REASON):
    result = pipeline.waive_round(db, person.candidateID, level, reason, user)
    db.commit()
    return result


def test_waiving_both_rounds_reaches_the_offer_stage(db, w, person, leader):
    _log(db, w, person, "Screening")
    _waive(db, leader, person, "L1")
    assert _stage(db, person) == "L2"
    _waive(db, leader, person, "L2")
    assert _stage(db, person) == "OFFER"


def test_the_waiver_is_on_record_with_who_and_why(db, w, person, leader):
    _log(db, w, person, "Screening")
    result = _waive(db, leader, person, "L1")
    row = db.query(HiringRoundWaiver).filter_by(candidate_id=person.candidateID).one()
    assert (row.level, row.reason, row.waived_by_user_id) == ("L1", REASON, leader.UserID)
    history = db.query(CandidateHistory).filter_by(candidateID=person.candidateID, event_type="Interview Round Waived").one()
    assert REASON in history.note
    event = db.query(HiringPipelineEvent).filter_by(pipeline_id=result.id, trigger="waiver").one()
    assert (event.from_stage, event.to_stage, event.ref) == ("L1", "L2", "L1")
    snap = pipeline.snapshot(db, result)
    assert snap["waivers"][0]["level"] == "L1" and snap["waivers"][0]["reason"] == REASON


def test_a_waiver_still_needs_an_offer_before_pre_onboarding(db, w, person, api, leader):
    _log(db, w, person, "Screening")
    _waive(db, leader, person, "L1")
    _waive(db, leader, person, "L2")
    res = api.put(w.org_user, f"/api/v1/status/{person.candidateID}", json={"pipeline_status": "Onboarded"})
    assert res.status_code == 409 and "no offer created yet" in res.json()["detail"]


def test_a_no_hire_cant_be_waived_away(db, w, person, leader):
    _log(db, w, person, "Screening")
    _log(db, w, person, "L1 Interview", "No Hire")
    with pytest.raises(pipeline.WaiverRefused, match="No Hire"):
        _waive(db, leader, person, "L1")


def test_a_passed_round_has_nothing_to_waive(db, w, person, leader):
    _log(db, w, person, "Screening")
    _log(db, w, person, "L1 Interview")
    with pytest.raises(pipeline.WaiverRefused, match="already passed"):
        _waive(db, leader, person, "L1")


def test_the_same_round_is_waived_once(db, w, person, leader):
    _log(db, w, person, "Screening")
    _waive(db, leader, person, "L1")
    with pytest.raises(pipeline.WaiverRefused, match="already waived"):
        _waive(db, leader, person, "L1")


@pytest.mark.parametrize("reason", ["", "   ", "because"])
def test_the_reason_is_required(db, w, person, reason, leader):
    _log(db, w, person, "Screening")
    with pytest.raises(pipeline.WaiverRefused, match="Say why"):
        _waive(db, leader, person, "L1", reason)


def test_only_l1_and_l2_can_be_waived(db, w, person):
    with pytest.raises(pipeline.WaiverRefused, match="Only L1 and L2"):
        _waive(db, leader, person, "SCREEN")


def test_below_bu_head_cannot_waive(db, w, person, api, leader):
    _log(db, w, person, "Screening")
    recruiter = _function_person(db, w, "Recruitment", "recruitment")  # may move the pipeline, but isn't a leader
    res = api.post(recruiter, f"/api/v1/hiring-pipeline/candidate/{person.candidateID}/waive",
                   json={"level": "L1", "reason": REASON})
    assert res.status_code == 403
    assert db.query(HiringRoundWaiver).filter_by(candidate_id=person.candidateID).count() == 0


def test_a_leader_waives_through_the_api(db, w, person, api, leader):
    _log(db, w, person, "Screening")
    res = api.post(leader, f"/api/v1/hiring-pipeline/candidate/{person.candidateID}/waive",
                   json={"level": "l1", "reason": REASON})
    assert res.status_code == 200, res.text
    assert res.json()["stage"] == "L2" and res.json()["waivers"][0]["waived_by"] == leader.UserName
    refused = api.post(leader, f"/api/v1/hiring-pipeline/candidate/{person.candidateID}/waive",
                       json={"level": "L1", "reason": REASON})
    assert refused.status_code == 409 and "already waived" in refused.json()["detail"]


def test_waiving_closes_the_task_to_schedule_that_round(db, w, person, leader):
    _log(db, w, person, "Screening")
    db.add(Task(title="Schedule L1 (technical) interview: Raj", category="INTERVIEW_SCHEDULING",
                candidate_id=person.candidateID, tenant_id=1))
    db.commit()
    _waive(db, leader, person, "L1")
    task = db.query(Task).filter_by(candidate_id=person.candidateID, category="INTERVIEW_SCHEDULING").first()
    assert task.status == "COMPLETED"


def test_a_round_sat_after_a_waiver_can_still_reject(db, w, person, leader):
    _log(db, w, person, "Screening")
    _waive(db, leader, person, "L1")
    _log(db, w, person, "L1 Interview", "No Hire")
    assert _stage(db, person) == "REJECTED"
    assert _status(db, person) in ("Interview", "Rejected")
