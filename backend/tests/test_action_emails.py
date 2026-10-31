"""Action emails (CEO 2026-10-31: "every single action if not all of them should trigger an email to
user, candidate, manager and so on"). For each family -- jobs, interviews, offers, submissions,
timesheets, allocations, projects, invoices, employees, candidates -- the internal people on the
record are emailed once each through the staff mail path, never the person who did it; the key is
deterministic (one email per record, event and person); and a failure to queue never undoes the
action. Candidate-facing emails are not sent from here (they go through Thunder)."""
import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.employee_allocation import AllocationChange, EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation
from app.models.hr_assignment import HRAssignment
from app.models.invoice import Invoice
from app.models.offer_letter import OfferLetter
from app.models.project import Project, ProjectMilestone
from app.models.submission import Submission
from app.models.timesheet import Timesheet
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Interview, InterviewPanel, Jobs, PanelMember
from app.services.action_emails import (allocations, candidates, core, employees, interviews, invoices, jobs,
                                        offers, projects, submissions, timesheets)
from tests.scope_fixtures import ApiClient, person, two_bu_world

QUEUE = "app.services.staff_mail_service.queue_staff_email"
HEAD = "app.services.bu_leadership.head_for_client"
EMPLOYEE_HEAD = "app.services.bu_leadership.head_user_id"


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
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def w(db):
    """two_bu_world plus the cast: an actor, a hiring manager, a recruiter, an account manager, a
    BU head, a project manager, an interviewer, a reporting manager and an employee with a login."""
    w = two_bu_world(db)
    for name in ("actor", "hm", "recruiter", "am", "head", "pm", "interviewer", "boss", "staff"):
        setattr(w, name, person(db, w.org_role, name.capitalize()))
    w.client_a.account_manager_user_id = w.am.UserID
    w.client_a.line_type = "CORE"
    w.job_a.hiringManagerID, w.job_a.recuriterID, w.job_a.jobStatus = w.hm.UserID, w.recruiter.UserID, "active"
    w.employee = Employee(tenant_id=1, first_name="Eve", last_name="Staff", email=f"{uuid.uuid4().hex[:8]}@e.test",
                          joining_date=dt.date(2026, 1, 5), wros_user_id=w.staff.UserID,
                          reporting_manager_user_id=w.boss.UserID, status="ACTIVE", bu_id=w.bu_a.id)
    w.candidate = Candidate(candidateID=f"CAN-{uuid.uuid4().hex[:8]}", tenant_id=1, candidateEmail=f"{uuid.uuid4().hex[:8]}@c.test", candidatePassword="x",
                            candidateFirstName="Cara", candidateLastName="Doe", job_id=w.job_a.jobID)
    db.add_all([w.employee, w.candidate])
    db.commit()
    return w


def _mailed(queue) -> dict:
    """user_id -> kwargs of the email queued for them."""
    return {call.args[0].UserID: call.kwargs for call in queue.call_args_list}


# --------------------------------------------------------------------------- core

def test_one_email_per_person_listing_every_role_and_never_the_actor_or_a_leaver(db, w):
    w.pm.terminated_at = dt.datetime.utcnow()
    team = {}
    core.add(team, w.hm.UserID, "Hiring Manager")
    core.add(team, w.hm.UserID, "Recruiter")
    core.add(team, w.actor.UserID, "Created it")
    core.add(team, w.pm.UserID, "Project Manager")
    with patch(QUEUE, return_value=True) as queue:
        assert core.send(db, team, actor_id=w.actor.UserID, key="k-1", subject="s", opening="o") == 1
    mailed = _mailed(queue)
    assert set(mailed) == {w.hm.UserID}
    assert mailed[w.hm.UserID]["key"] == f"k-1-{w.hm.UserID}"
    assert "You are on it as: Hiring Manager, Recruiter." in mailed[w.hm.UserID]["paragraphs"]


def test_a_notify_that_fails_returns_zero_instead_of_raising(db, w):
    with patch(QUEUE, side_effect=RuntimeError("queue down")):
        assert jobs.notify_job_approved(db, w.job_a, actor=w.actor) == 0


# --------------------------------------------------------------------------- jobs

def test_a_new_job_mails_its_hiring_manager_recruiter_and_bu_head_not_its_creator(db, w):
    w.job_a.created_by = w.actor.UserID
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=w.head.UserID):
        jobs.notify_job_created(db, w.job_a, actor_id=w.actor.UserID)
    mailed = _mailed(queue)
    assert set(mailed) == {w.hm.UserID, w.recruiter.UserID, w.head.UserID}
    assert mailed[w.hm.UserID]["key"] == f"job-created-{w.job_a.jobID}-{w.hm.UserID}"
    assert mailed[w.hm.UserID]["link_path"] == f"/jobs/{w.job_a.jobID}/workspace"


def test_editing_a_job_mails_only_the_newly_assigned_people(api, db, w):
    new_recruiter = person(db, w.org_role, "New recruiter")
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.put(w.actor, f"/api/v1/jobs/update_job/{w.job_a.jobID}",
                           json={"recuriter_id": new_recruiter.UserID, "hiring_manager_id": w.hm.UserID})
    assert response.status_code == 200, response.text
    mailed = _mailed(queue)
    assert set(mailed) == {new_recruiter.UserID}  # the hiring manager did not change
    assert mailed[new_recruiter.UserID]["key"] == f"job-assigned-{w.job_a.jobID}-recruiter-{new_recruiter.UserID}"


def test_a_failed_email_never_undoes_a_job_edit(api, db, w):
    new_recruiter = person(db, w.org_role, "New recruiter")
    db.commit()
    with patch(QUEUE, side_effect=RuntimeError("queue down")), patch(HEAD, return_value=None):
        response = api.put(w.actor, f"/api/v1/jobs/update_job/{w.job_a.jobID}",
                           json={"recuriter_id": new_recruiter.UserID})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(Jobs, w.job_a.jobID).recuriterID == new_recruiter.UserID


# --------------------------------------------------------------------------- interviews

def _round(db, w):
    panel = InterviewPanel(candidate_id=w.candidate.candidateID, round_name="Tech", job_id=w.job_a.jobID)
    db.add(panel)
    db.flush()
    db.add(PanelMember(panel_id=panel.id, interviewer_id=w.interviewer.UserID))
    start = dt.datetime(2026, 11, 3, 15, 0)
    interview = Interview(panel_id=panel.id, candidate_id=w.candidate.candidateID, start_time=start,
                          end_time=start + dt.timedelta(hours=1), status="Scheduled")
    db.add(interview)
    db.commit()
    return panel, interview


def test_a_scheduled_interview_mails_the_hiring_manager_and_recruiter(db, w):
    panel, interview = _round(db, w)
    with patch(QUEUE, return_value=True) as queue:
        interviews.notify_interview_scheduled(db, interview, panel, actor=w.recruiter)
    mailed = _mailed(queue)
    # the interviewer has the feedback task's email; the recruiter scheduled it
    assert set(mailed) == {w.hm.UserID}
    assert mailed[w.hm.UserID]["key"] == f"interview-scheduled-{interview.id}-{w.hm.UserID}"


def test_a_new_time_or_a_cancellation_mails_the_interviewers_too(db, w):
    panel, interview = _round(db, w)
    interview.start_time += dt.timedelta(days=1)
    interview.end_time += dt.timedelta(days=1)
    with patch(QUEUE, return_value=True) as queue:
        interviews.notify_interview_changed(db, interview, actor=w.actor, rescheduled=True, cancelled=False)
        interviews.notify_interview_changed(db, interview, actor=w.actor, rescheduled=False, cancelled=False)
    keys = {c.kwargs["key"] for c in queue.call_args_list}
    assert f"interview-rescheduled-{interview.id}-20261104T1500-{w.interviewer.UserID}" in keys
    assert {c.args[0].UserID for c in queue.call_args_list} == {w.interviewer.UserID, w.hm.UserID, w.recruiter.UserID}
    with patch(QUEUE, return_value=True) as queue:
        interviews.notify_interview_changed(db, interview, actor=w.hm, rescheduled=False, cancelled=True)
    assert set(_mailed(queue)) == {w.interviewer.UserID, w.recruiter.UserID}


def test_an_added_interviewer_and_the_round_verdict_are_mailed(db, w):
    panel, _ = _round(db, w)
    member = db.query(PanelMember).filter_by(panel_id=panel.id).one()
    with patch(QUEUE, return_value=True) as queue:
        interviews.notify_panel_member_added(db, member, actor=w.recruiter)
        interviews.notify_round_verdict(db, panel, "PASS", actor=w.hm, rationale="Strong")
    keys = [c.kwargs["key"] for c in queue.call_args_list]
    assert f"interview-panel-member-{member.id}-{w.interviewer.UserID}" in keys
    assert f"interview-verdict-{panel.id}-PASS-{w.recruiter.UserID}" in keys
    assert not any(k.endswith(w.hm.UserID) for k in keys if "verdict" in k)  # the deciding hiring manager


# --------------------------------------------------------------------------- offers

def _offer(db, w, **extra):
    offer = OfferLetter(candidate_id=w.candidate.candidateID, job_id=w.job_a.jobID, position="Engineer", salary="24 LPA",
                        joining_date=dt.date(2026, 12, 1), offer_expire_date=dt.date(2026, 11, 20),
                        hiring_manager_id=w.hm.UserID, reporting_manager_id=w.boss.UserID,
                        created_by=w.actor.UserID, **extra)
    db.add(offer)
    db.commit()
    return offer


def test_an_offer_mails_its_managers_and_recruiter_not_its_creator(db, w):
    offer = _offer(db, w)
    with patch(QUEUE, return_value=True) as queue:
        offers.notify_offer_created(db, offer, actor=w.actor)
    mailed = _mailed(queue)
    assert set(mailed) == {w.hm.UserID, w.boss.UserID, w.recruiter.UserID}
    assert mailed[w.boss.UserID]["key"] == f"offer-created-{offer.id}-{w.boss.UserID}"


def test_the_candidates_answer_mails_everyone_on_the_offer(db, w):
    offer = _offer(db, w, offer_status="Accepted")
    with patch(QUEUE, return_value=True) as queue:
        offers.notify_offer_answered(db, offer, message="Excited!")
    mailed = _mailed(queue)
    assert set(mailed) == {w.hm.UserID, w.boss.UserID, w.recruiter.UserID, w.actor.UserID}
    assert mailed[w.actor.UserID]["key"] == f"offer-answered-accepted-{offer.id}-{w.actor.UserID}"
    assert "Their message: Excited!" in mailed[w.actor.UserID]["paragraphs"]


def test_a_failed_offer_email_leaves_the_offer_as_it_is(db, w):
    offer = _offer(db, w, offer_status="Released")
    with patch(QUEUE, side_effect=RuntimeError("queue down")):
        assert offers.notify_offer_released(db, offer, actor=w.actor) == 0
    db.expire_all()
    assert db.get(OfferLetter, offer.id).offer_status == "Released"


# --------------------------------------------------------------------------- submissions

def test_a_submission_and_each_client_response_mail_the_job_and_client_team(db, w):
    submission = Submission(tenant_id=1, demand_id=w.job_a.jobID, client_id=w.client_a.id,
                            candidate_id=w.candidate.candidateID, submitted_by_user_id=w.actor.UserID)
    db.add(submission)
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=w.head.UserID):
        submissions.notify_submitted(db, submission, actor=w.actor)
    assert set(_mailed(queue)) == {w.hm.UserID, w.recruiter.UserID, w.am.UserID, w.head.UserID}
    submission.status = "SHORTLISTED"
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=w.head.UserID):
        submissions.notify_client_response(db, submission, actor=w.am)
    mailed = _mailed(queue)
    assert w.am.UserID not in mailed and w.actor.UserID in mailed  # the submitter hears the response
    assert mailed[w.actor.UserID]["key"] == f"submission-response-{submission.id}-SHORTLISTED-{w.actor.UserID}"


# --------------------------------------------------------------------------- timesheets

def test_a_dispute_mails_the_employee_their_manager_and_the_client_team(db, w):
    allocation = EmployeeAllocation(tenant_id=1, employee_id=w.employee.id, client_id=w.client_a.id,
                                    demand_id=w.job_a.jobID)
    db.add(allocation)
    db.flush()
    timesheet = Timesheet(tenant_id=1, employee_id=w.employee.id, allocation_id=allocation.id,
                          week_starting_date=dt.date(2026, 10, 19), status="APPROVED")
    db.add(timesheet)
    db.flush()
    dispute = TimesheetDispute(tenant_id=1, timesheet_id=timesheet.id, raised_by="CLIENT", original_hours=40,
                               reason="x" * 60, raised_by_user_id=w.actor.UserID)
    db.add(dispute)
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None), \
            patch(EMPLOYEE_HEAD, return_value=None):
        timesheets.notify_dispute_raised(db, dispute, actor=w.actor)
    mailed = _mailed(queue)
    assert set(mailed) == {w.staff.UserID, w.boss.UserID, w.am.UserID}
    assert mailed[w.staff.UserID]["key"] == f"timesheet-dispute-raised-{dispute.id}-{w.staff.UserID}"


# --------------------------------------------------------------------------- allocations

def test_an_allocation_mails_the_employee_manager_project_manager_and_account_manager(db, w):
    project = Project(tenant_id=1, client_id=w.client_a.id, name="Policy Center", manager_user_id=w.pm.UserID)
    db.add(project)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=w.employee.id, client_id=w.client_a.id,
                                    project_id=project.id, role="Developer")
    db.add(allocation)
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None), \
            patch(EMPLOYEE_HEAD, return_value=w.head.UserID):
        allocations.notify_allocated(db, allocation, actor=w.am)
    mailed = _mailed(queue)
    assert set(mailed) == {w.staff.UserID, w.boss.UserID, w.pm.UserID, w.head.UserID}  # not the AM who did it
    assert mailed[w.pm.UserID]["key"] == f"allocation-created-{allocation.id}-{w.pm.UserID}"
    pending = AllocationChange(tenant_id=1, allocation_id=allocation.id, change_type="EDIT", status="PENDING_APPROVAL",
                               new_values={"utilization_pct": 50}, reason="Half time")
    db.add(pending)
    db.commit()
    with patch(QUEUE, return_value=True) as queue:
        assert allocations.notify_allocation_changed(db, allocation, pending, actor=w.am) == 0
    queue.assert_not_called()  # its approver has the approval task's email


# --------------------------------------------------------------------------- projects

def test_a_project_status_change_mails_the_project_team_and_survives_a_failed_email(api, db, w):
    project = Project(tenant_id=1, client_id=w.client_a.id, name="Billing Center", manager_user_id=w.pm.UserID,
                      created_by=w.actor.UserID, status="PLANNING")
    db.add(project)
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.post(w.actor, f"/api/v1/projects/{project.id}/status", json={"status": "ACTIVE"})
    assert response.status_code == 200, response.text
    mailed = _mailed(queue)
    assert set(mailed) == {w.pm.UserID, w.am.UserID}
    assert mailed[w.pm.UserID]["key"] == f"project-status-{project.id}-ACTIVE-{w.pm.UserID}"
    with patch(QUEUE, side_effect=RuntimeError("queue down")), patch(HEAD, return_value=None):
        response = api.post(w.actor, f"/api/v1/projects/{project.id}/status", json={"status": "ON_HOLD"})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(Project, project.id).status == "ON_HOLD"


def test_a_completed_milestone_mails_its_owner(db, w):
    project = Project(tenant_id=1, client_id=w.client_a.id, name="Claims", manager_user_id=w.pm.UserID)
    db.add(project)
    db.flush()
    milestone = ProjectMilestone(tenant_id=1, project_id=project.id, title="UAT", due_date=dt.date(2026, 11, 1),
                                 owner_employee_id=w.employee.id, delay_days=2)
    db.add(milestone)
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        projects.notify_milestone_completed(db, project, milestone, actor=w.pm)
    mailed = _mailed(queue)
    assert set(mailed) == {w.staff.UserID, w.am.UserID}
    assert "2 day(s) late" in mailed[w.staff.UserID]["paragraphs"][0]


# --------------------------------------------------------------------------- invoices

def test_a_drafted_invoice_mails_an_approver_and_the_project_team(db, w):
    from tests.hiring_fixtures import finance_approver

    approver = finance_approver(db)
    project = Project(tenant_id=1, client_id=w.client_a.id, name="AR", manager_user_id=w.pm.UserID)
    db.add(project)
    db.flush()
    invoice = Invoice(tenant_id=1, project_id=project.id, client_id=w.client_a.id, total_usd_cents=1234500,
                      billing_period_start=dt.date(2026, 10, 1), billing_period_end=dt.date(2026, 10, 31))
    db.add(invoice)
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None), \
            patch("app.services.invoice_service.invoice_approvers", return_value=[approver]):
        invoices.notify_invoice_drafted(db, invoice, actor=w.actor)
    mailed = _mailed(queue)
    assert set(mailed) == {approver.UserID, w.pm.UserID, w.am.UserID}
    assert mailed[approver.UserID]["key"] == f"invoice-drafted-{invoice.id}-{approver.UserID}"
    assert "Total: $12,345.00 (billed in USD)." in mailed[approver.UserID]["paragraphs"]


# --------------------------------------------------------------------------- employees

def test_an_escalation_mails_the_manager_and_bu_head_not_the_employee(api, db, w):
    with patch(QUEUE, return_value=True) as queue, patch(EMPLOYEE_HEAD, return_value=w.head.UserID):
        response = api.post(w.actor, f"/api/v1/employees/{w.employee.id}/escalations",
                            json={"reason": "Client complaint", "severity": "HIGH"})
    assert response.status_code == 201, response.text
    mailed = _mailed(queue)
    assert set(mailed) == {w.boss.UserID, w.head.UserID}
    assert mailed[w.boss.UserID]["key"] == f"employee-escalation-{response.json()['id']}-{w.boss.UserID}"


def test_a_failed_email_never_undoes_an_escalation(api, db, w):
    with patch(QUEUE, side_effect=RuntimeError("queue down")), patch(EMPLOYEE_HEAD, return_value=None):
        response = api.post(w.actor, f"/api/v1/employees/{w.employee.id}/escalations", json={"reason": "Late"})
    assert response.status_code == 201, response.text
    assert db.get(EmployeeEscalation, response.json()["id"]) is not None


def test_a_new_reporting_manager_mails_the_employee_and_both_managers(db, w):
    with patch(QUEUE, return_value=True) as queue, patch(EMPLOYEE_HEAD, return_value=None):
        employees.notify_manager_changed(db, w.employee, actor=w.actor, previous_manager=w.pm.UserID)
    mailed = _mailed(queue)
    assert set(mailed) == {w.staff.UserID, w.boss.UserID, w.pm.UserID}
    assert mailed[w.pm.UserID]["key"] == f"employee-manager-{w.employee.id}-{w.boss.UserID}-{w.pm.UserID}"


# --------------------------------------------------------------------------- candidates

def test_hr_assignment_mails_the_hr_people_and_an_edit_only_the_new_one(api, db, w):
    second = person(db, w.org_role, "Second HR")
    db.commit()
    with patch(QUEUE, return_value=True) as queue:
        response = api.post(w.actor, "/api/v1/hr-assignments/",
                            json={"candidate_id": w.candidate.candidateID, "hr1_id": w.staff.UserID})
    assert response.status_code in (200, 201), response.text
    assignment = db.query(HRAssignment).filter_by(candidate_id=w.candidate.candidateID).one()
    assert set(_mailed(queue)) == {w.staff.UserID}
    assert _mailed(queue)[w.staff.UserID]["key"] == f"candidate-hr-{assignment.id}-{w.staff.UserID}"
    with patch(QUEUE, return_value=True) as queue:
        response = api.patch(w.actor, f"/api/v1/hr-assignments/by-candidate/{w.candidate.candidateID}",
                             json={"hr2_id": second.UserID})
    assert response.status_code == 200, response.text
    assert set(_mailed(queue)) == {second.UserID}


def test_an_auto_assigned_recruiter_is_always_told_and_a_status_change_mails_the_candidates_team(db, w):
    w.candidate.assigned_recruiter_id = w.staff.UserID
    db.commit()
    with patch(QUEUE, return_value=True) as queue:
        candidates.notify_recruiter_assigned(db, w.candidate, actor_id=None)
    assert _mailed(queue)[w.staff.UserID]["key"] == f"candidate-recruiter-{w.candidate.candidateID}-{w.staff.UserID}"
    with patch(QUEUE, return_value=True) as queue:
        candidates.notify_pipeline_status(db, w.candidate, actor=w.staff, old_status="Screening", new_status="Interview")
    mailed = _mailed(queue)
    assert set(mailed) == {w.hm.UserID, w.recruiter.UserID}  # the candidate's recruiter moved them
    assert mailed[w.hm.UserID]["key"] == f"candidate-status-{w.candidate.candidateID}-Interview-{w.hm.UserID}"
