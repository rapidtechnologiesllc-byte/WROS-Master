"""Certificates an employee holds (CEO 2026-10-23): EmployeeCertification is the one record --
created, edited and removed from the employee screen, read by the training dashboards. The
current Guidewire level is derived from it (never typed); the target level stays a field."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.db_contract import _guidewire_current_level_to_certificates
from app.models.certification import Certification, EmployeeCertification
from app.models.employee import Employee
from app.services.training_certification_service import get_certification_summary
from tests.scope_fixtures import ApiClient, two_bu_world, uid


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


def _employee(db, bu, **kw):
    e = Employee(tenant_id=1, first_name="Cert", last_name=uid(), email=f"{uid()}@c.test",
                 joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=bu.id, **kw)
    db.add(e)
    db.flush()
    return e


def _cert(db, name, *, guidewire_level=None, validity_months=24):
    cert = Certification(tenant_id=1, cert_name=name, cert_code=f"C-{uid()}", level="Foundation",
                         validity_months=validity_months, guidewire_level=guidewire_level)
    db.add(cert)
    db.flush()
    return cert


def _path(employee, suffix=""):
    return f"/api/v1/employees/{employee.id}/certificates{suffix}"


def test_add_edit_and_remove_a_certificate(db, w, api):
    employee = _employee(db, w.bu_a)
    cert = _cert(db, "PolicyCenter Developer", validity_months=24)
    db.commit()

    res = api.post(w.org_user, _path(employee), json={"certification_id": cert.id, "earned_date": "2026-01-15",
                                                     "issuer": "Guidewire", "cert_number": " PC-42 "})
    assert res.status_code == 201, res.text
    record = res.json()
    assert record["expires_date"] == "2028-01-15"  # the catalog's 24-month validity
    assert record["cert_number"] == "PC-42"

    edited = api.patch(w.org_user, _path(employee, f"/{record['id']}"),
                       json={"expires_date": "2027-06-30", "status": "Revoked"})
    assert edited.status_code == 200 and edited.json()["status"] == "Revoked"
    assert edited.json()["expires_date"] == "2027-06-30"

    listed = api.get(w.org_user, _path(employee)).json()["certificates"]
    assert [r["id"] for r in listed] == [record["id"]]
    assert api.delete(w.org_user, _path(employee, f"/{record['id']}")).status_code == 200
    assert api.get(w.org_user, _path(employee)).json()["certificates"] == []


@pytest.mark.parametrize("body, message", [
    ({"earned_date": "2026-03-01", "expires_date": "2026-02-01"}, "is before earned_date"),
    ({"earned_date": "2026-03-01", "status": "Lost"}, "status must be one of"),
])
def test_an_invalid_certificate_is_a_400(db, w, api, body, message):
    employee = _employee(db, w.bu_a)
    cert = _cert(db, "BillingCenter")
    db.commit()
    res = api.post(w.org_user, _path(employee), json={"certification_id": cert.id, **body})
    assert res.status_code == 400 and message in res.json()["detail"]


def test_unknown_catalog_entry_and_other_bu_are_refused(db, w, api):
    employee, theirs = _employee(db, w.bu_a), _employee(db, w.bu_b)
    cert = _cert(db, "ClaimCenter")
    db.commit()
    assert api.post(w.org_user, _path(employee), json={"certification_id": "nope",
                                                       "earned_date": "2026-01-01"}).status_code == 400
    assert api.post(w.partner_a, _path(theirs), json={"certification_id": cert.id,
                                                      "earned_date": "2026-01-01"}).status_code == 404
    assert api.get(w.partner_a, _path(theirs)).status_code == 404


def test_training_dashboard_counts_what_was_recorded(db, w, api):
    employee = _employee(db, w.bu_a)
    soon = _cert(db, "Expiring soon", validity_months=None)
    db.commit()
    before = get_certification_summary(db, w.bu_a.id)
    in_two_weeks = date.today() + timedelta(days=14)
    api.post(w.org_user, _path(employee), json={"certification_id": soon.id, "earned_date": "2025-01-01",
                                               "expires_date": str(in_two_weeks)})
    after = get_certification_summary(db, w.bu_a.id)
    assert after["total_active"] == before["total_active"] + 1
    assert after["expiring_within_30_days"] == before["expiring_within_30_days"] + 1


def test_current_guidewire_level_comes_from_certificates(db, w, api):
    employee = _employee(db, w.bu_a)
    ace, specialist = _cert(db, "GW ACE", guidewire_level="ACE"), _cert(db, "GW Specialist", guidewire_level="Specialist")
    db.commit()
    api.post(w.org_user, _path(employee), json={"certification_id": ace.id, "earned_date": "2025-01-01"})
    expired = api.post(w.org_user, _path(employee), json={"certification_id": specialist.id,
                                                         "earned_date": "2020-01-01", "expires_date": "2021-01-01"})
    assert api.get(w.org_user, f"/api/v1/employees/{employee.id}").json()["guidewire_certification_current"] == "ACE"

    api.patch(w.org_user, _path(employee, f"/{expired.json()['id']}"), json={"expires_date": "2030-01-01"})
    detail = api.get(w.org_user, f"/api/v1/employees/{employee.id}").json()
    assert detail["guidewire_certification_current"] == "Specialist"
    listed = {e["id"]: e for e in api.get(w.org_user, "/api/v1/employees").json()["employees"]}
    assert listed[employee.id]["guidewire_certification_current"] == "Specialist"


def test_the_target_level_is_set_but_the_current_level_cannot_be_typed(db, w, api):
    employee = _employee(db, w.bu_a)
    db.commit()
    url = f"/api/v1/employees/{employee.id}/certifications"
    ok = api.put(w.org_user, url, json={"guidewire_certification_expected": "Associate"})
    assert ok.status_code == 200 and ok.json()["guidewire_certification_expected"] == "Associate"
    # sending back the derived value (old clients) is accepted; a different one is not
    assert api.put(w.org_user, url, json={"guidewire_certification_current": "None"}).status_code == 200
    typed = api.put(w.org_user, url, json={"guidewire_certification_current": "Specialist"})
    assert typed.status_code == 400 and "comes from the certificates" in typed.json()["detail"]
    assert api.put(w.org_user, url, json={"guidewire_certification_expected": "Guru"}).status_code == 400


def test_options_serve_the_catalog_statuses_and_levels(db, w, api):
    cert = _cert(db, "Jutro", guidewire_level=None)
    db.commit()
    options = api.get(w.org_user, "/api/v1/employees/certification-options").json()
    assert cert.id in {c["id"] for c in options["certifications"]}
    assert options["guidewire_levels"] == ["None", "ACE", "Associate", "Specialist"]
    assert "Active" in options["statuses"]
    catalog = api.get(w.org_user, "/api/v1/admin/certifications/options").json()
    assert catalog["guidewire_levels"] == ["ACE", "Associate", "Specialist"]


def test_typed_levels_become_certificate_records_once(db, w):
    typed = _employee(db, w.bu_a, guidewire_certification_current="Associate",
                      guidewire_certification_expected="Specialist")
    untyped = _employee(db, w.bu_a)
    db.flush()

    made = _guidewire_current_level_to_certificates(db)
    assert made >= 1
    record = db.query(EmployeeCertification).filter(EmployeeCertification.employee_id == typed.id).one()
    assert record.certification.guidewire_level == "Associate" and record.status == "Active"
    assert typed.guidewire_certification_current is None  # retired column cleared
    assert typed.guidewire_certification_expected == "Specialist"  # the target stays
    assert db.query(EmployeeCertification).filter(EmployeeCertification.employee_id == untyped.id).count() == 0

    from app.services.employee_certification_service import current_guidewire_levels
    assert current_guidewire_levels(db, [typed.id]) == {typed.id: "Associate"}
    # a second run finds nothing typed any more
    assert _guidewire_current_level_to_certificates(db) == 0


def test_migration_reuses_the_tenants_own_catalog_entry(db, w):
    own = _cert(db, "Guidewire ACE (ours)", guidewire_level="ACE")
    typed = _employee(db, w.bu_a, guidewire_certification_current="ACE")
    db.flush()
    _guidewire_current_level_to_certificates(db)
    record = db.query(EmployeeCertification).filter(EmployeeCertification.employee_id == typed.id).one()
    assert record.certification_id == own.id
    assert isinstance(record.earned_date, datetime)
