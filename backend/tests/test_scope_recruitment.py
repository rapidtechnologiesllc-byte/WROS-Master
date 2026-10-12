"""Business-unit visibility, recruitment slice: jobs (demands), candidates, submissions,
interviews and offers. Partner A must never see or touch BU B's records; records not yet
assigned to a BU (a job without a BU, a candidate in the Org Pool) stay visible to all;
org-level users see everything (CEO 2026-10-12). Relates to #394."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ownership import POOL_BU, CandidateOwnership
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs
from tests.scope_fixtures import ApiClient, ids, two_bu_world, uid


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
    world = two_bu_world(db)
    world.job_a.jobStatus = world.job_b.jobStatus = "active"
    world.job_u = Jobs(tenant_id=1, jobTitle="Unassigned job", jobDescription="d", jobSkills="x", jobExperience="5",
                       jobLocation="Remote", jobStatus="active")
    world.cand_a = _candidate(db, world.bu_a)
    world.cand_b = _candidate(db, world.bu_b)
    world.cand_u = _candidate(db, None)  # Org Pool: no BU owns it yet
    db.add(world.job_u)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _candidate(db, bu) -> Candidate:
    candidate = Candidate(candidateID=f"C-{uid()}", candidateEmail=f"{uid()}@cand.scope.test", candidatePassword="x",
                          candidateFirstName="Cand", candidateLastName=uid(), tenant_id=1)
    db.add(candidate)
    db.flush()
    if bu is not None:
        db.add(CandidateOwnership(candidateID=candidate.candidateID, pool_status=POOL_BU, owned_by_bu_id=bu.id,
                                  owned_by_bu_name=bu.name, bu_owned_since=datetime.utcnow()))
        db.flush()
    return candidate


# --------------------------------------------------------------------------- jobs

def test_job_lists_show_own_bu_and_unassigned_only(w, api):
    for path in ("/api/v1/jobs/all", "/api/v1/jobs/active-jobs", "/api/v1/jobs/filter"):
        mine = ids(api.get(w.partner_a, path).json(), "job_id")
        assert w.job_a.jobID in mine and w.job_u.jobID in mine, path
        assert w.job_b.jobID not in mine, path
        everything = ids(api.get(w.org_user, path).json(), "job_id")
        assert {w.job_a.jobID, w.job_b.jobID, w.job_u.jobID} <= everything, path


def test_job_filter_cannot_pick_another_bu(w, api):
    picked = ids(api.get(w.partner_a, f"/api/v1/jobs/filter?business_unit={w.bu_b.id}").json(), "job_id")
    assert w.job_b.jobID not in picked
    assert w.job_b.jobID in ids(api.get(w.org_user, f"/api/v1/jobs/filter?business_unit={w.bu_b.id}").json(),
                                "job_id")


def test_my_jobs_follow_the_bus_a_partner_leads(w, api):
    mine = ids(api.get(w.partner_a, "/api/v1/jobs/my-jobs").json(), "job_id")
    assert w.job_a.jobID in mine and w.job_b.jobID not in mine


def test_other_bus_job_is_not_found(w, api):
    assert api.get(w.partner_a, f"/api/v1/jobs/job-details/{w.job_b.jobID}").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/jobs/job-details/{w.job_a.jobID}").status_code == 200
    assert api.get(w.partner_a, f"/api/v1/jobs/job-details/{w.job_u.jobID}").status_code == 200
    assert api.get(w.org_user, f"/api/v1/jobs/job-details/{w.job_b.jobID}").status_code == 200
    assert api.get(w.partner_a, f"/api/v1/jobs/{w.job_b.jobID}/applications").status_code == 404
    assert api.get(w.partner_a,
                   f"/api/v1/demand-confirmation/demands/{w.job_b.jobID}/calls").status_code == 404
    assert api.get(w.partner_a,
                   f"/api/v1/demand-confirmation/demands/{w.job_a.jobID}/calls").status_code == 200


def test_cannot_edit_delete_or_approve_another_bus_job(db, w, api):
    from app.core.csrf_protection import generate_csrf_token

    assert api.put(w.partner_a, f"/api/v1/jobs/update_job/{w.job_b.jobID}",
                   json={"job_title": "taken"}).status_code == 404
    assert api.delete(w.partner_a, f"/api/v1/jobs/delete_job/{w.job_b.jobID}").status_code == 404
    w.job_b.jobStatus = "pending_approval"
    db.commit()
    approve = api.client.post(f"/api/v1/jobs/{w.job_b.jobID}/approve",
                              headers={**api.headers(w.partner_a), "X-CSRF-Token": generate_csrf_token()})
    assert approve.status_code == 404
    db.refresh(w.job_b)
    assert w.job_b.jobTitle == "Job B" and w.job_b.jobStatus == "pending_approval"


def test_cannot_move_a_job_into_another_bu(db, w, api):
    moved = api.put(w.partner_a, f"/api/v1/jobs/update_job/{w.job_a.jobID}", json={"business_unit": w.bu_b.id})
    assert moved.status_code == 403
    to_client = api.put(w.partner_a, f"/api/v1/jobs/update_job/{w.job_a.jobID}", json={"client_id": w.client_b.id})
    assert to_client.status_code == 403
    db.refresh(w.job_a)
    assert w.job_a.business_unit_id == w.bu_a.id and w.job_a.client_id == w.client_a.id
    body = {"job_title": "New", "job_description": "d", "job_skills": "x", "job_experience": "5",
            "job_location": "Remote", "company_type": "contract", "company_name": "", "job_status": "active",
            "business_unit": w.bu_b.id}
    assert api.post(w.partner_a, "/api/v1/jobs/create_job", json=body).status_code == 403


# --------------------------------------------------------------------------- candidates

def test_candidate_list_shows_own_bu_and_org_pool(w, api):
    mine = ids(api.get(w.partner_a, "/api/v1/candidates/all").json(), "candidateID")
    assert w.cand_a.candidateID in mine and w.cand_u.candidateID in mine
    assert w.cand_b.candidateID not in mine
    everything = ids(api.get(w.org_user, "/api/v1/candidates/all").json(), "candidateID")
    assert {w.cand_a.candidateID, w.cand_b.candidateID, w.cand_u.candidateID} <= everything


def test_other_bus_candidate_is_not_found(w, api):
    b = w.cand_b.candidateID
    assert api.get(w.partner_a, f"/api/v1/candidates/{b}").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/candidates/hr/candidate/{b}/contacts").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/candidates/hr/candidate/{w.cand_a.candidateID}/contacts").status_code == 200
    assert api.get(w.org_user, f"/api/v1/candidates/hr/candidate/{b}/contacts").status_code == 200
    assert api.put(w.partner_a, f"/api/v1/candidates/hr/update_candidate/{b}",
                   json={"candidate_first_name": "x"}).status_code == 404
    assert api.patch(w.partner_a, f"/api/v1/candidates/{b}/thunder-config",
                     json={"thunder_enabled": False}).status_code == 404
    assert api.delete(w.partner_a, f"/api/v1/candidates/{b}").status_code == 404


def test_candidate_pool_cannot_pick_another_bu(w, api):
    mine = ids(api.get(w.partner_a, f"/api/v1/candidate-pool/?bu_id={w.bu_b.id}").json(), "candidate_id")
    assert w.cand_b.candidateID not in mine
    own = ids(api.get(w.partner_a, f"/api/v1/candidate-pool/?bu_id={w.bu_a.id}").json(), "candidate_id")
    assert own == {w.cand_a.candidateID}
    theirs = ids(api.get(w.org_user, f"/api/v1/candidate-pool/?bu_id={w.bu_b.id}").json(), "candidate_id")
    assert theirs == {w.cand_b.candidateID}


# --------------------------------------------------------------------------- submissions

def _submissions(db, w):
    from app.models.submission import Submission

    sub_a = Submission(tenant_id=1, demand_id=w.job_a.jobID, client_id=w.client_a.id,
                       candidate_id=w.cand_a.candidateID)
    sub_b = Submission(tenant_id=1, demand_id=w.job_b.jobID, client_id=w.client_b.id,
                       candidate_id=w.cand_b.candidateID)
    db.add_all([sub_a, sub_b])
    db.commit()
    return sub_a, sub_b


def test_submissions_follow_their_job(db, w, api):
    sub_a, sub_b = _submissions(db, w)
    mine = ids(api.get(w.partner_a, "/api/v1/submissions").json())
    assert sub_a.id in mine and sub_b.id not in mine
    assert {sub_a.id, sub_b.id} <= ids(api.get(w.org_user, "/api/v1/submissions").json())
    assert not ids(api.get(w.partner_a, f"/api/v1/submissions?demand_id={w.job_b.jobID}").json()) & {sub_b.id}
    response = api.post(w.partner_a, f"/api/v1/submissions/{sub_b.id}/client-response",
                        json={"new_status": "CLIENT_REJECTED"})
    assert response.status_code == 404
    submit = api.post(w.partner_a, "/api/v1/submissions/",
                      json={"demand_id": w.job_b.jobID, "candidate_id": w.cand_u.candidateID})
    assert submit.status_code == 404
    submit = api.post(w.partner_a, "/api/v1/submissions/",
                      json={"demand_id": w.job_a.jobID, "candidate_id": w.cand_b.candidateID})
    assert submit.status_code == 404


# --------------------------------------------------------------------------- interviews

def _interviews(db, w):
    start = datetime.utcnow() + timedelta(days=2)
    panel_a = InterviewPanel(candidate_id=w.cand_a.candidateID, job_id=w.job_a.jobID, round_name="L1")
    panel_b = InterviewPanel(candidate_id=w.cand_b.candidateID, job_id=w.job_b.jobID, round_name="L1")
    db.add_all([panel_a, panel_b])
    db.flush()
    iv_a = Interview(panel_id=panel_a.id, candidate_id=w.cand_a.candidateID, start_time=start,
                     end_time=start + timedelta(hours=1), status="Scheduled")
    iv_b = Interview(panel_id=panel_b.id, candidate_id=w.cand_b.candidateID, start_time=start,
                     end_time=start + timedelta(hours=1), status="Scheduled")
    db.add_all([iv_a, iv_b])
    db.flush()
    fb_b = InterviewFeedback(interview_id=iv_b.id, interviewer_id=w.partner_b.UserID, technical_score=4,
                             communication_score=4, problem_solving_score=4, culture_fit_score=4,
                             recommendation="Hire")
    db.add(fb_b)
    db.commit()
    return panel_a, panel_b, iv_a, iv_b, fb_b


def test_interview_lists_follow_candidate_and_job(db, w, api):
    panel_a, panel_b, iv_a, iv_b, _ = _interviews(db, w)
    mine = ids(api.get(w.partner_a, "/api/v1/interviews").json())
    assert iv_a.id in mine and iv_b.id not in mine
    assert {iv_a.id, iv_b.id} <= ids(api.get(w.org_user, "/api/v1/interviews").json())
    panels = ids(api.get(w.partner_a, "/api/v1/interviews/panels").json())
    assert panel_a.id in panels and panel_b.id not in panels
    assert {panel_a.id, panel_b.id} <= ids(api.get(w.org_user, "/api/v1/interviews/panels").json())


def test_interview_statistics_count_only_visible_interviews(db, w, api):
    _interviews(db, w)
    mine = api.get(w.partner_a, "/api/v1/interviews/statistics")
    everything = api.get(w.org_user, "/api/v1/interviews/statistics")
    assert mine.status_code == 200 and everything.status_code == 200
    assert everything.json()["total_interviews"] - mine.json()["total_interviews"] >= 1
    assert everything.json()["total_feedback"] - mine.json()["total_feedback"] >= 1


def test_other_bus_interview_records_are_not_found(db, w, api):
    panel_a, panel_b, iv_a, iv_b, fb_b = _interviews(db, w)
    for path in (f"/api/v1/interviews/{iv_b.id}", f"/api/v1/interviews/panels/{panel_b.id}",
                 f"/api/v1/interviews/panel-members/{panel_b.id}",
                 f"/api/v1/interviews/feedback/interview/{iv_b.id}", f"/api/v1/interviews/feedback/{fb_b.id}",
                 f"/api/v1/interviews/candidate-history/{w.cand_b.candidateID}",
                 f"/api/v1/interviews/candidates/{w.cand_b.candidateID}/verdicts"):
        assert api.get(w.partner_a, path).status_code == 404, path
        assert api.get(w.org_user, path).status_code == 200, path
    assert api.get(w.partner_a, f"/api/v1/interviews/{iv_a.id}").status_code == 200


def test_cannot_change_another_bus_interview(db, w, api):
    panel_a, panel_b, iv_a, iv_b, fb_b = _interviews(db, w)
    assert api.put(w.partner_a, f"/api/v1/interviews/{iv_b.id}", json={"status": "Cancelled"}).status_code == 404
    assert api.delete(w.partner_a, f"/api/v1/interviews/{iv_b.id}").status_code == 404
    assert api.delete(w.partner_a, f"/api/v1/interviews/panels/{panel_b.id}").status_code == 404
    assert api.put(w.partner_a, f"/api/v1/interviews/feedback/{fb_b.id}", json={"comments": "x"}).status_code == 404
    assert api.delete(w.partner_a, f"/api/v1/interviews/feedback/{fb_b.id}").status_code == 404
    assert api.put(w.partner_a, f"/api/v1/interviews/panels/{panel_b.id}/level",
                   json={"level": "L2"}).status_code == 404
    created = api.post(w.partner_a, "/api/v1/interviews/panels/create",
                       json={"candidate_id": w.cand_b.candidateID, "round_name": "L1"})
    assert created.status_code == 404
    created = api.post(w.partner_a, "/api/v1/interviews/panels/create",
                       json={"candidate_id": w.cand_u.candidateID, "round_name": "L1", "job_id": w.job_b.jobID})
    assert created.status_code == 404
    db.refresh(iv_b)
    assert iv_b.status == "Scheduled"


def test_rehire_reviews_follow_candidate_and_job(db, w, api):
    from app.models import InterviewRehireReview

    def review(candidate, job):
        row = InterviewRehireReview(candidate_id=candidate.candidateID, job_id=job.jobID, round_name="L1",
                                    justification="new skills", status="PENDING_HM_APPROVAL")
        db.add(row)
        return row

    review_a, review_b = review(w.cand_a, w.job_a), review(w.cand_b, w.job_b)
    db.commit()
    mine = ids(api.get(w.partner_a, "/api/v1/interviews/rehire-reviews").json())
    assert review_a.id in mine and review_b.id not in mine
    assert {review_a.id, review_b.id} <= ids(api.get(w.org_user, "/api/v1/interviews/rehire-reviews").json())
    decided = api.post(w.partner_a, f"/api/v1/interviews/rehire-reviews/{review_b.id}/decide",
                       json={"decision": "reject"})
    assert decided.status_code == 404
    db.refresh(review_b)
    assert review_b.status == "PENDING_HM_APPROVAL"
    # the decide body the UI sends ({decision, note}) is accepted -- it used to 422 because
    # the HM review list's `candidates` field had been pasted into this request schema
    own = api.post(w.partner_a, f"/api/v1/interviews/rehire-reviews/{review_a.id}/decide",
                   json={"decision": "reject", "note": "not yet"})
    assert own.status_code == 200, own.text
    assert own.json()["status"] == "REJECTED"


def test_hm_review_list_returns_its_candidates(w, api):
    response = api.get(w.partner_a, "/api/v1/interviews/hm-review/my-candidates")
    assert response.status_code == 200, response.text
    assert "candidates" in response.json()


# --------------------------------------------------------------------------- offers

def test_offers_follow_candidate_and_job(db, w, api):
    from app.models.offer import Offer

    def offer(candidate, job):
        row = Offer(id=f"OF-{uid()}", tenant_id=1, candidate_id=candidate.candidateID, job_id=job.jobID,
                    created_by_user_id=w.org_user.UserID, position_title="Engineer", base_salary_usd_cents=100,
                    expected_start_date=date.today(), benefits={})
        db.add(row)
        return row

    offer_a, offer_b = offer(w.cand_a, w.job_a), offer(w.cand_b, w.job_b)
    db.commit()
    mine = ids(api.get(w.partner_a, "/api/v1/offers?limit=100").json())
    assert offer_b.id not in mine
    assert offer_a.id in ids(api.get(w.partner_a, f"/api/v1/offers?job_id={w.job_a.jobID}").json())
    assert offer_b.id in ids(api.get(w.org_user, f"/api/v1/offers?job_id={w.job_b.jobID}").json())
    assert not ids(api.get(w.partner_a, f"/api/v1/offers?job_id={w.job_b.jobID}").json())
    assert not ids(api.get(w.partner_a, f"/api/v1/offers?candidate_id={w.cand_b.candidateID}").json())


def test_offer_letters_follow_candidate_and_job(db, w, api):
    from app.models.offer_letter import OfferLetter

    def letter(candidate, job):
        row = OfferLetter(candidate_id=candidate.candidateID, job_id=job.jobID, position="Engineer", salary="1",
                          joining_date=date.today(), offer_expire_date=date.today() + timedelta(days=7),
                          offer_status="Pending", approval_status="AwaitingApproval",
                          hiring_manager_id=w.partner_a.UserID)
        db.add(row)
        return row

    ol_a, ol_b = letter(w.cand_a, w.job_a), letter(w.cand_b, w.job_b)
    db.commit()
    mine = ids(api.get(w.partner_a, "/api/v1/offer-letter/all").json())
    assert ol_a.id in mine and ol_b.id not in mine
    assert {ol_a.id, ol_b.id} <= ids(api.get(w.org_user, "/api/v1/offer-letter/all").json())
    pending = ids(api.get(w.partner_a, "/api/v1/offer-letter/pending-approval").json())
    assert ol_a.id in pending and ol_b.id not in pending
    assert api.get(w.partner_a, f"/api/v1/offer-letter/{ol_b.id}").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/offer-letter/{ol_a.id}").status_code == 200
    assert api.get(w.org_user, f"/api/v1/offer-letter/{ol_b.id}").status_code == 200
    assert api.get(w.partner_a, f"/api/v1/offer-letter/pending-approval/by-job/{w.job_b.jobID}").status_code == 404
    assert api.post(w.partner_a, f"/api/v1/offer-letter/cancel/{ol_b.id}", json={}).status_code == 404
    assert api.put(w.partner_a, f"/api/v1/offer-letter/update/{ol_b.id}", json={"salary": "2"}).status_code == 404
    assert api.post(w.partner_a, f"/api/v1/offer-letter/release/{ol_b.id}").status_code == 404
    moved = api.put(w.partner_a, f"/api/v1/offer-letter/update/{ol_a.id}", json={"job_id": w.job_b.jobID})
    assert moved.status_code == 404
    db.refresh(ol_a)
    db.refresh(ol_b)
    assert ol_b.offer_status == "Pending" and ol_b.salary == "1" and ol_a.job_id == w.job_a.jobID
