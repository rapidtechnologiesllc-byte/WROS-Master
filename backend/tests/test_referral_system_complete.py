"""Employee referrals: the bonus flow, and who sees which referrals.

Visibility (app.services.referral_access_control) is by role template, always inside the
caller's tenant: org-level and finance see all, staff managers see their business units'
referrals plus their own, everyone else only their own.
"""
from types import SimpleNamespace

import pytest

from app.models.referral import EmployeeReferral
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.services.employee_referral_service import EmployeeReferralService
from app.services.referral_access_control import ReferralAccessControl
from tests import factories


def _grant_edit(db, user, resource_name):
    """Give the user's role template edit on one resource (through the permission matrix)."""
    tenant_id = user.tenant_id
    module = db.query(Module).filter_by(tenant_id=tenant_id, name="referral-test").first()
    if module is None:
        module = Module(tenant_id=tenant_id, name="referral-test", display_name="Referral test")
        db.add(module)
        db.flush()
    resource = db.query(Resource).filter_by(tenant_id=tenant_id, name=resource_name).first()
    if resource is None:
        resource = Resource(tenant_id=tenant_id, module_id=module.id, name=resource_name, display_name=resource_name)
        db.add(resource)
        db.flush()
    role = db.get(RoleTemplate, user.role_template_id)
    db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=tenant_id,
                                  can_view=True, can_edit=True))
    db.flush()


def _staff(db, name, unit=None, tenant_id=1):
    user = factories.user(db, tenant_id=tenant_id, UserName=name, business_unit_id=unit.id if unit else None)
    employee = factories.employee(db, tenant_id=tenant_id, first_name=name, last_name="X",
                                  bu_id=unit.id if unit else None, wros_user_id=user.UserID)
    return SimpleNamespace(user=user, employee=employee)


def _referral(db, by, name):
    db.add(EmployeeReferral(referral_id=f"ref-{factories.uid()}", job_id="job-1", referring_employee_id=by.employee.id,
                            referred_candidate_name=name, referral_status="PENDING",
                            referral_bonus_amount_usd_cents=50000))
    db.flush()


@pytest.fixture
def world(db):
    bu_a, bu_b = factories.business_unit(db), factories.business_unit(db)
    w = SimpleNamespace(alice=_staff(db, "Alice", bu_a), bob=_staff(db, "Bob", bu_a), carol=_staff(db, "Carol", bu_b))
    _referral(db, w.alice, "A1")
    _referral(db, w.bob, "B1")
    _referral(db, w.carol, "C1")
    w.manager = _staff(db, "Mona", bu_a)
    _grant_edit(db, w.manager.user, "employees")
    w.finance = _staff(db, "Fin")
    _grant_edit(db, w.finance.user, "revenue")
    factories.tenant(db, 2)
    _referral(db, _staff(db, "Otto", tenant_id=2), "OTHER-TENANT")
    db.commit()
    return w


def _names(db, staff):
    return {r["referred_candidate_name"] for r in ReferralAccessControl.get_referrals_for_user(db, staff.user)}


def test_an_employee_sees_only_their_own_referrals(db, world):
    assert _names(db, world.alice) == {"A1"}


def test_a_staff_manager_sees_their_business_units_referrals(db, world):
    assert _names(db, world.manager) == {"A1", "B1"}


def test_finance_sees_the_whole_tenant_and_nothing_from_another_tenant(db, world):
    assert _names(db, world.finance) == {"A1", "B1", "C1"}


def test_a_hire_creates_the_bonus_and_finance_marks_it_paid(db, world):
    recorded = EmployeeReferralService.record_referral(
        db, job_id="job-2", referring_employee_id=world.alice.employee.id,
        referred_candidate_email=f"r{factories.uid()}@x.com", referred_candidate_name="Ravi")
    assert recorded["status"] == "recorded", recorded
    hired = EmployeeReferralService.update_referral_status(db, recorded["referral_id"], "HIRED")
    assert hired["status"] == "updated", hired

    def pending():
        return [b for b in EmployeeReferralService.get_pending_bonuses(db) if b["referral_id"] == recorded["referral_id"]]

    assert len(pending()) == 1
    assert EmployeeReferralService.mark_bonus_paid(db, pending()[0]["bonus_id"])["status"] == "paid"
    assert pending() == []
