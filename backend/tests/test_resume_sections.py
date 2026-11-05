"""CEO 2026-11-05: "Based on resume all expereince should there", certifications "not updated from resume", for "all
existing and new candidates". A real layout: employer + dates on a line, title below, a heading per section."""
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateEducationForm, CandidateExperienceForm, CandidateJobApplication
from app.models.candidate_profile_extras import CandidateCertification, CandidateProfileSkill
from app.models.candidate_resume_parsed import PARSER_VERSION, CandidateResumeParsed
from app.services import candidate_resume_intake as intake
from app.services.resume_parser_slm import ResumeSLM
from tests.scope_fixtures import ApiClient, two_bu_world

RESUME = """RAJESWAR PANJA
Senior Technical Manager | Guidewire BillingCenter and Integration Specialist
Kolkata, India | [+91 8910353068] | [rajeswar25@hotmail.com] | [LinkedIn]
PROFESSIONAL SUMMARY
Guidewire technical leader with 14+ years in insurance software.
CORE SKILLS
Guidewire\tBillingCenter, Integration: Integration Gateway, work queues, Rest API
Languages\tGosu, SQL
PROFESSIONAL EXPERIENCE
PwC Acceleration Center\tOct 2022 – Present  |  Bangalore
Senior Manager / Senior Technical Lead
Lead offshore teams across planning and delivery.
Surety Bond Upgrade (Dec 2025 – Present): migrating a client from an AS400 mainframe.
EY GDS\tJul 2021 – Sep 2022  |  Kolkata
Senior Technical Lead / Technical Manager
Gathered requirements in client sessions.
Cognizant\tJun 2014 – Jul 2019  |  Kolkata, Toronto
Associate / Product Specialist – Technical
Propel (2018–19): extended BillingCenter to multiple policies per account.
Tata Consultancy Services\tSep 2011 – Jun 2014  |  Kolkata
Systems Engineer
Early-career software engineering role.
CERTIFICATIONS
Guidewire ACE: BillingCenter 10.0 Configuration (Quasar), 2026
Guidewire Specialist: InsuranceSuite 10.0 (Las Lenas), 2024; BillingCenter 9.0 Configuration, 2018
Sun Certified Programmer: Java SE 6, 2012
EDUCATION
Bachelor's Degree, Netaji Subhash Engineering College (WBUT), 2011
Class XII, Burdwan CMS High School, 2006  |  Class X, Jamalpur Boys' High School, 2004
"""
STACKED = """Jane Doe
jane@example.com
Experience
Senior Developer
Acme Insurance Inc
01/2020 - Present
Built billing integrations.
Developer at Beta Systems, 2016 - 2019
Wrote policy rating.
Skills: Python, SQL, Guidewire
Education
University of Toronto
Master of Science in Computing, 2015
"""


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


def _candidate(db, **fields):
    fields.setdefault("candidateExperience", "8")
    row = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h", candidateFirstName="Jane",
                    candidateLastName="Doe", candidateEmail=f"j{uuid.uuid4().hex[:8]}@example.com", **fields)
    db.add(row)
    db.commit()
    return row


def test_every_job_is_found_with_its_real_dates():
    jobs = ResumeSLM.parse_resume(RESUME)["work_history"]
    assert [j["employer"] for j in jobs] == ["PwC Acceleration Center", "EY GDS", "Cognizant", "Tata Consultancy Services"]
    assert jobs[0]["title"] == "Senior Manager / Senior Technical Lead"
    assert (jobs[0]["start_date"], jobs[0]["end_date"]) == ("2022-10", None)
    assert (jobs[1]["start_date"], jobs[1]["end_date"]) == ("2021-07", "2022-09")
    assert "Surety Bond" in jobs[0]["description"], "a project's dates are not a new job"


def test_stacked_and_single_line_layouts():
    jobs = ResumeSLM.parse_resume(STACKED)["work_history"]
    assert jobs[0]["title"] == "Senior Developer" and jobs[0]["employer"] == "Acme Insurance Inc"
    assert (jobs[0]["start_date"], jobs[0]["end_date"]) == ("2020-01", None)
    assert jobs[1]["title"] == "Developer" and jobs[1]["employer"] == "Beta Systems"
    assert (jobs[1]["start_date"], jobs[1]["end_date"]) == ("2016-01", "2019-01")


def test_every_certification_is_found_whoever_issued_it():
    certs = ResumeSLM.parse_resume(RESUME)["certifications"]
    names = [c["name"] for c in certs]
    assert "Guidewire ACE: BillingCenter 10.0 Configuration (Quasar)" in names
    assert "Guidewire Specialist: BillingCenter 9.0 Configuration" in names
    assert len(certs) == 4
    assert next(c for c in certs if c["name"].startswith("Sun"))["year"] == 2012
    assert next(c for c in certs if c["name"].startswith("Guidewire ACE"))["issuer"] == "Guidewire"


def test_education_and_listed_skills_are_read_as_written():
    parsed = ResumeSLM.parse_resume(RESUME)
    entries = {e["institution"]: e for e in parsed["education"]}
    assert entries["Netaji Subhash Engineering College"]["degree"] == "Bachelor's Degree"
    assert entries["Netaji Subhash Engineering College"]["graduation_year"] == 2011
    assert entries["Burdwan CMS High School"]["degree"] == "Class XII"
    assert len(entries) == 3
    assert {"BillingCenter", "Integration Gateway", "Gosu", "SQL"} <= set(parsed["skills"])
    assert "Go" not in parsed["skills"] and "Java" not in parsed["skills"]
    stacked = ResumeSLM.parse_resume(STACKED)
    assert stacked["education"][0]["institution"] == "University of Toronto"
    assert stacked["education"][0]["degree"].startswith("Master of Science")
    assert {"Python", "SQL", "Guidewire"} <= set(stacked["skills"])


def test_existing_candidates_are_refreshed_and_what_people_typed_stays(db, w):
    candidate = _candidate(db)
    db.add(CandidateResumeParsed(candidate_id=candidate.candidateID, tenant_id="1", raw_text=RESUME, parser_version="1.0",
                                 work_history=[{"employer": "PwC Acceleration Center\tOct 2022 – Present  |  Bangalore",
                                                "title": "Senior Manager / Senior Technical Lead"}],
                                 education=[{"institution": "Burdwan CMS High School", "degree": "as"}],
                                 skills=["Go", "Java"], certifications=[]))
    db.add_all([
        CandidateExperienceForm(candidateID=candidate.candidateID, company_name="PwC Acceleration Center\tOct 2022 – Present  |  Bangalore",
                                job_title="Senior Manager / Senior Technical Lead"),
        CandidateExperienceForm(candidateID=candidate.candidateID, company_name="Typed By Recruiter Ltd", job_title="Consultant"),
        CandidateEducationForm(candidateID=candidate.candidateID, education_institute="Burdwan CMS High School", degree="as"),
        CandidateProfileSkill(candidate_id=candidate.candidateID, name="Go", is_primary=True),
        CandidateProfileSkill(candidate_id=candidate.candidateID, name="Typed Skill", is_primary=False),
    ])
    db.commit()
    assert intake.run_resume_refresh_job(db)["refreshed"] >= 1
    cid = candidate.candidateID
    db.expire_all()
    companies = {r.company_name for r in db.query(CandidateExperienceForm).filter_by(candidateID=cid)}
    assert companies == {"PwC Acceleration Center", "EY GDS", "Cognizant", "Tata Consultancy Services", "Typed By Recruiter Ltd"}
    pwc = db.query(CandidateExperienceForm).filter_by(candidateID=cid, company_name="PwC Acceleration Center").one()
    assert pwc.start_date == date(2022, 10, 1) and pwc.year_of_experience
    assert db.query(CandidateCertification).filter_by(candidate_id=cid).count() == 4
    skills = {r.name for r in db.query(CandidateProfileSkill).filter_by(candidate_id=cid)}
    assert "Go" not in skills and "Typed Skill" in skills and "Gosu" in skills
    degrees = {r.degree for r in db.query(CandidateEducationForm).filter_by(candidateID=cid)}
    assert "as" not in degrees and "Class XII" in degrees
    assert db.query(CandidateResumeParsed).filter_by(candidate_id=cid).one().parser_version == PARSER_VERSION
    intake.run_resume_refresh_job(db)  # nothing left to do: never duplicates
    assert db.query(CandidateExperienceForm).filter_by(candidateID=cid).count() == 5


def test_submitting_sets_the_recruiter_and_the_business_unit(api, db, w):
    candidate = _candidate(db)
    response = api.post(w.org_user, f"/api/v1/jobs/{w.job_a.jobID}/applications/{candidate.candidateID}", json={})
    assert response.status_code == 201, response.text
    db.expire_all()
    row = db.get(Candidate, candidate.candidateID)
    assert row.assigned_recruiter_id == w.org_user.UserID, "no job recruiter: whoever submitted"
    assert row.submission_bu_id == w.bu_a.id
    shown = api.get(w.org_user, f"/api/v1/candidates/{candidate.candidateID}").json()
    assert shown["submission_bu_name"] == w.bu_a.name and shown["assigned_recruiter_id"] == w.org_user.UserID


def test_the_jobs_recruiter_wins_and_a_set_recruiter_is_kept(api, db, w):
    w.job_a.recuriterID = w.partner_a.UserID
    db.commit()
    fresh, assigned = _candidate(db), _candidate(db, assigned_recruiter_id=w.partner_b.UserID)
    for candidate in (fresh, assigned):
        assert api.post(w.org_user, f"/api/v1/jobs/{w.job_a.jobID}/applications/{candidate.candidateID}", json={}).status_code == 201
    db.expire_all()
    assert db.get(Candidate, fresh.candidateID).assigned_recruiter_id == w.partner_a.UserID
    assert db.get(Candidate, assigned.candidateID).assigned_recruiter_id == w.partner_b.UserID


def test_existing_submitted_candidates_are_backfilled(db, w):
    from app.services.candidate_assignment_service import run_submitted_candidates_backfill

    candidate = _candidate(db, created_by_user_id=w.org_user.UserID)
    db.add(CandidateJobApplication(candidate_id=candidate.candidateID, job_id=w.job_a.jobID, application_status="Applied",
                                   applied_at=datetime.utcnow()))
    db.commit()
    assert run_submitted_candidates_backfill(db)["updated"] >= 1
    db.expire_all()
    row = db.get(Candidate, candidate.candidateID)
    assert row.assigned_recruiter_id == w.org_user.UserID and row.submission_bu_id == w.bu_a.id


def test_linkedin_shows_saves_and_is_one_persons(api, db, w):
    one, two = _candidate(db), _candidate(db, linkedin_url="https://www.linkedin.com/in/taken")
    path = f"/api/v1/candidates/hr/update_candidate/{one.candidateID}"
    bad = api.put(w.org_user, path, json={"linkedin_url": "not a profile"})
    assert bad.status_code == 400, bad.text
    taken = api.put(w.org_user, path, json={"linkedin_url": "linkedin.com/in/taken/"})
    assert taken.status_code == 409, taken.text
    fine = api.put(w.org_user, path, json={"linkedin_url": "linkedin.com/in/jane-doe/"})
    assert fine.status_code == 200, fine.text
    assert api.get(w.org_user, f"/api/v1/candidates/{one.candidateID}").json()["linkedin_url"] == "https://www.linkedin.com/in/jane-doe"
    assert two.linkedin_url
