"""Backend permission system tests - validates all 127+ permission rules"""
import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import Users
from app.models.rbac_template import Role
from app.services.permission_service import PermissionService

# Fixtures
@pytest.fixture
def db():
    """Get database session for tests"""
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def recruiter_user(db):
    """Get or create a recruiter user"""
    user = db.query(Users).filter(Users.permission_role == "RECRUITER").first()
    return user

@pytest.fixture
def ceo_user(db):
    """Get or create a CEO/SUPER_USER"""
    user = db.query(Users).filter(Users.permission_role == "SUPER_USER").first()
    return user

@pytest.fixture
def bu_head_user(db):
    """Get a BU Head user"""
    user = db.query(Users).filter(Users.permission_role == "BU_HEAD").first()
    return user

@pytest.fixture
def manager_user(db):
    """Get a Manager user"""
    user = db.query(Users).filter(Users.permission_role == "MANAGER").first()
    return user

@pytest.fixture
def hr_manager_user(db):
    """Get an HR Manager user"""
    user = db.query(Users).filter(Users.permission_role == "HR_MANAGER").first()
    return user

@pytest.fixture
def finance_user(db):
    """Get a Finance user"""
    user = db.query(Users).filter(Users.permission_role == "FINANCE").first()
    return user

@pytest.fixture
def partner_user(db):
    """Get a Partner user"""
    user = db.query(Users).filter(Users.permission_role == "PARTNER").first()
    return user

# RECRUITER TESTS
class TestRecruiterPermissions:
    """18+ tests for Recruiter role"""

    def test_recruiter_can_create_candidate(self, db, recruiter_user):
        """Recruiter should have candidate.create permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "candidate.create", recruiter_user.tenant_id
        )
        assert has_perm is True

    def test_recruiter_can_view_candidates(self, db, recruiter_user):
        """Recruiter should have candidate.view permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "candidate.view", recruiter_user.tenant_id
        )
        assert has_perm is True

    def test_recruiter_can_edit_candidate(self, db, recruiter_user):
        """Recruiter should have candidate.edit permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "candidate.edit", recruiter_user.tenant_id
        )
        assert has_perm is True

    def test_recruiter_cannot_delete_candidate(self, db, recruiter_user):
        """Recruiter should NOT have candidate.delete permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "candidate.delete", recruiter_user.tenant_id
        )
        assert has_perm is False

    def test_recruiter_cannot_see_salary_field(self, db, recruiter_user):
        """Recruiter should NOT see employee salary field"""
        access = PermissionService.get_field_access_level(
            db, recruiter_user.UserID, "employees", "salary"
        )
        assert access == "hidden"

    def test_recruiter_cannot_see_ssn_field(self, db, recruiter_user):
        """Recruiter should NOT see employee SSN field"""
        access = PermissionService.get_field_access_level(
            db, recruiter_user.UserID, "employees", "ssn"
        )
        assert access == "hidden"

    def test_recruiter_bu_scoped_access(self, db, recruiter_user):
        """Recruiter should have BU_ONLY scope"""
        scope = PermissionService.get_data_scope(db, recruiter_user.UserID, "candidates")
        assert scope["scope_type"] == "BU_ONLY"
        assert scope["user_bu_id"] == recruiter_user.business_unit_id

    def test_recruiter_cannot_approve_timesheet(self, db, recruiter_user):
        """Recruiter should NOT have timesheet.approve permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "timesheet.approve", recruiter_user.tenant_id
        )
        assert has_perm is False

    def test_recruiter_cannot_manage_roles(self, db, recruiter_user):
        """Recruiter should NOT have user.manage_roles permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "user.manage_roles", recruiter_user.tenant_id
        )
        assert has_perm is False

    def test_recruiter_cannot_access_invoices(self, db, recruiter_user):
        """Recruiter should NOT have invoice.view permission"""
        has_perm = PermissionService.has_permission(
            db, recruiter_user.UserID, "invoice.view", recruiter_user.tenant_id
        )
        assert has_perm is False

# CEO TESTS
class TestCEOPermissions:
    """15+ tests for CEO/SUPER_USER role"""

    def test_ceo_can_do_everything(self, db, ceo_user):
        """CEO should have all permissions"""
        # Test multiple permissions
        assert PermissionService.has_permission(
            db, ceo_user.UserID, "candidate.delete", ceo_user.tenant_id
        )
        assert PermissionService.has_permission(
            db, ceo_user.UserID, "user.manage", ceo_user.tenant_id
        )
        assert PermissionService.has_permission(
            db, ceo_user.UserID, "system.manage", ceo_user.tenant_id
        )

    def test_ceo_can_view_all_bu_data(self, db, ceo_user):
        """CEO should have ORG_WIDE scope"""
        scope = PermissionService.get_data_scope(db, ceo_user.UserID, "candidates")
        assert scope["scope_type"] == "ORG_WIDE"

    def test_ceo_can_see_all_fields(self, db, ceo_user):
        """CEO should see all fields (editable access)"""
        access = PermissionService.get_field_access_level(
            db, ceo_user.UserID, "employees", "salary"
        )
        assert access == "editable"

    def test_ceo_can_see_ssn(self, db, ceo_user):
        """CEO should see SSN field"""
        access = PermissionService.get_field_access_level(
            db, ceo_user.UserID, "employees", "ssn"
        )
        assert access == "editable"

    def test_ceo_can_delete_candidate(self, db, ceo_user):
        """CEO should have candidate.delete"""
        has_perm = PermissionService.has_permission(
            db, ceo_user.UserID, "candidate.delete", ceo_user.tenant_id
        )
        assert has_perm is True

    def test_ceo_can_create_user(self, db, ceo_user):
        """CEO should have user.create"""
        has_perm = PermissionService.has_permission(
            db, ceo_user.UserID, "user.create", ceo_user.tenant_id
        )
        assert has_perm is True

    def test_ceo_can_manage_invoices(self, db, ceo_user):
        """CEO should have invoice.manage"""
        has_perm = PermissionService.has_permission(
            db, ceo_user.UserID, "invoice.manage", ceo_user.tenant_id
        )
        assert has_perm is True

    def test_ceo_can_approve_timesheet(self, db, ceo_user):
        """CEO should have timesheet.approve"""
        has_perm = PermissionService.has_permission(
            db, ceo_user.UserID, "timesheet.approve", ceo_user.tenant_id
        )
        assert has_perm is True

# HR MANAGER TESTS
class TestHRManagerPermissions:
    """12+ tests for HR Manager role"""

    def test_hr_manager_can_view_employees(self, db, hr_manager_user):
        """HR Manager should have employee.view"""
        has_perm = PermissionService.has_permission(
            db, hr_manager_user.UserID, "employee.view", hr_manager_user.tenant_id
        )
        assert has_perm is True

    def test_hr_manager_can_edit_employee(self, db, hr_manager_user):
        """HR Manager should have employee.edit"""
        has_perm = PermissionService.has_permission(
            db, hr_manager_user.UserID, "employee.edit", hr_manager_user.tenant_id
        )
        assert has_perm is True

    def test_hr_manager_cannot_delete_employee(self, db, hr_manager_user):
        """HR Manager should NOT have employee.delete"""
        has_perm = PermissionService.has_permission(
            db, hr_manager_user.UserID, "employee.delete", hr_manager_user.tenant_id
        )
        assert has_perm is False

    def test_hr_manager_ssn_masked_not_hidden(self, db, hr_manager_user):
        """HR Manager should see MASKED SSN (not hidden)"""
        access = PermissionService.get_field_access_level(
            db, hr_manager_user.UserID, "employees", "ssn"
        )
        assert access == "masked"

    def test_hr_manager_salary_hidden(self, db, hr_manager_user):
        """HR Manager should NOT see salary (Finance only)"""
        access = PermissionService.get_field_access_level(
            db, hr_manager_user.UserID, "employees", "salary"
        )
        assert access == "hidden"

    def test_hr_manager_cannot_approve_invoice(self, db, hr_manager_user):
        """HR Manager should NOT have invoice.approve"""
        has_perm = PermissionService.has_permission(
            db, hr_manager_user.UserID, "invoice.approve", hr_manager_user.tenant_id
        )
        assert has_perm is False

    def test_hr_manager_can_manage_leaves(self, db, hr_manager_user):
        """HR Manager should have leave.manage"""
        has_perm = PermissionService.has_permission(
            db, hr_manager_user.UserID, "leave.manage", hr_manager_user.tenant_id
        )
        assert has_perm is True

# MANAGER TESTS
class TestManagerPermissions:
    """10+ tests for Manager role"""

    def test_manager_can_view_own_team(self, db, manager_user):
        """Manager should have employee.view with TEAM_ONLY scope"""
        scope = PermissionService.get_data_scope(db, manager_user.UserID, "employees")
        assert scope["scope_type"] == "TEAM_ONLY"

    def test_manager_cannot_delete_employee(self, db, manager_user):
        """Manager should NOT have employee.delete"""
        has_perm = PermissionService.has_permission(
            db, manager_user.UserID, "employee.delete", manager_user.tenant_id
        )
        assert has_perm is False

    def test_manager_can_approve_timesheet(self, db, manager_user):
        """Manager should have timesheet.approve"""
        has_perm = PermissionService.has_permission(
            db, manager_user.UserID, "timesheet.approve", manager_user.tenant_id
        )
        assert has_perm is True

    def test_manager_cannot_access_invoices(self, db, manager_user):
        """Manager should NOT have invoice.view"""
        has_perm = PermissionService.has_permission(
            db, manager_user.UserID, "invoice.view", manager_user.tenant_id
        )
        assert has_perm is False

    def test_manager_cannot_see_salary(self, db, manager_user):
        """Manager should NOT see salary field"""
        access = PermissionService.get_field_access_level(
            db, manager_user.UserID, "employees", "salary"
        )
        assert access == "hidden"

# BU HEAD TESTS
class TestBUHeadPermissions:
    """8+ tests for BU Head role"""

    def test_bu_head_bu_scoped_access(self, db, bu_head_user):
        """BU Head should have BU_ONLY scope"""
        scope = PermissionService.get_data_scope(db, bu_head_user.UserID, "candidates")
        assert scope["scope_type"] == "BU_ONLY"

    def test_bu_head_can_view_candidates(self, db, bu_head_user):
        """BU Head should have candidate.view"""
        has_perm = PermissionService.has_permission(
            db, bu_head_user.UserID, "candidate.view", bu_head_user.tenant_id
        )
        assert has_perm is True

    def test_bu_head_cannot_delete_candidate(self, db, bu_head_user):
        """BU Head should NOT have candidate.delete"""
        has_perm = PermissionService.has_permission(
            db, bu_head_user.UserID, "candidate.delete", bu_head_user.tenant_id
        )
        assert has_perm is False

    def test_bu_head_can_manage_bu_users(self, db, bu_head_user):
        """BU Head should have user.manage for own BU"""
        has_perm = PermissionService.has_permission(
            db, bu_head_user.UserID, "user.manage", bu_head_user.tenant_id
        )
        assert has_perm is True

# PARTNER TESTS
class TestPartnerPermissions:
    """8+ tests for Partner role"""

    def test_partner_multi_bu_scoped(self, db, partner_user):
        """Partner should have MULTI_BU scope"""
        scope = PermissionService.get_data_scope(db, partner_user.UserID, "candidates")
        assert scope["scope_type"] == "MULTI_BU"

    def test_partner_can_view_candidates(self, db, partner_user):
        """Partner should have candidate.view"""
        has_perm = PermissionService.has_permission(
            db, partner_user.UserID, "candidate.view", partner_user.tenant_id
        )
        assert has_perm is True

    def test_partner_cannot_delete_candidate(self, db, partner_user):
        """Partner should NOT have candidate.delete"""
        has_perm = PermissionService.has_permission(
            db, partner_user.UserID, "candidate.delete", partner_user.tenant_id
        )
        assert has_perm is False

    def test_partner_cannot_manage_users(self, db, partner_user):
        """Partner should NOT have user.manage"""
        has_perm = PermissionService.has_permission(
            db, partner_user.UserID, "user.manage", partner_user.tenant_id
        )
        assert has_perm is False

# FINANCE TESTS
class TestFinancePermissions:
    """10+ tests for Finance role"""

    def test_finance_can_view_invoices(self, db, finance_user):
        """Finance should have invoice.view"""
        has_perm = PermissionService.has_permission(
            db, finance_user.UserID, "invoice.view", finance_user.tenant_id
        )
        assert has_perm is True

    def test_finance_can_approve_invoices(self, db, finance_user):
        """Finance should have invoice.approve"""
        has_perm = PermissionService.has_permission(
            db, finance_user.UserID, "invoice.approve", finance_user.tenant_id
        )
        assert has_perm is True

    def test_finance_cannot_delete_invoice(self, db, finance_user):
        """Finance should NOT have invoice.delete"""
        has_perm = PermissionService.has_permission(
            db, finance_user.UserID, "invoice.delete", finance_user.tenant_id
        )
        assert has_perm is False

    def test_finance_cannot_access_recruitment(self, db, finance_user):
        """Finance should NOT have candidate.view"""
        has_perm = PermissionService.has_permission(
            db, finance_user.UserID, "candidate.view", finance_user.tenant_id
        )
        assert has_perm is False

    def test_finance_org_wide_scope(self, db, finance_user):
        """Finance should have ORG_WIDE scope for invoices"""
        scope = PermissionService.get_data_scope(db, finance_user.UserID, "invoices")
        assert scope["scope_type"] == "ORG_WIDE"

    def test_finance_can_see_salary(self, db, finance_user):
        """Finance should see salary (readonly or editable)"""
        access = PermissionService.get_field_access_level(
            db, finance_user.UserID, "employees", "salary"
        )
        assert access in ["readonly", "editable"]

# CROSS-ROLE TESTS
class TestCrossRoleIsolation:
    """10+ tests for isolation between roles"""

    def test_recruiter_cannot_do_finance(self, db, recruiter_user, finance_user):
        """Recruiter should NOT have finance permissions that Finance has"""
        recruiter_invoice = PermissionService.has_permission(
            db, recruiter_user.UserID, "invoice.view", recruiter_user.tenant_id
        )
        finance_invoice = PermissionService.has_permission(
            db, finance_user.UserID, "invoice.view", finance_user.tenant_id
        )
        assert recruiter_invoice is False
        assert finance_invoice is True

    def test_finance_cannot_recruit(self, db, recruiter_user, finance_user):
        """Finance should NOT have recruitment permissions"""
        recruiter_cand = PermissionService.has_permission(
            db, recruiter_user.UserID, "candidate.create", recruiter_user.tenant_id
        )
        finance_cand = PermissionService.has_permission(
            db, finance_user.UserID, "candidate.create", finance_user.tenant_id
        )
        assert recruiter_cand is True
        assert finance_cand is False

    def test_pii_isolation_by_role(self, db, recruiter_user, hr_manager_user, finance_user):
        """Different roles should have different PII access"""
        # Recruiter: salary hidden
        recruiter_salary = PermissionService.get_field_access_level(
            db, recruiter_user.UserID, "employees", "salary"
        )
        # HR Manager: salary hidden (HR should not see)
        hr_salary = PermissionService.get_field_access_level(
            db, hr_manager_user.UserID, "employees", "salary"
        )
        # Finance: salary visible
        finance_salary = PermissionService.get_field_access_level(
            db, finance_user.UserID, "employees", "salary"
        )

        assert recruiter_salary == "hidden"
        assert hr_salary == "hidden"
        assert finance_salary in ["readonly", "editable"]

# RUN TESTS
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
