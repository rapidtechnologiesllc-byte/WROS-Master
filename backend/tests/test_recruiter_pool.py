"""Who receives new candidates is decided by function and permission (CEO 2026-10-10:
authority from the role template, never a role-name string): people in a Recruitment
department whose role may work candidates. A legacy "Recruiter" UserRole text counts for
nothing on its own."""
import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.org_structure import Department
from app.services.recruiter_assignment_service import RecruiterAssignmentServiceForCandidates as Pool
from tests.scope_fixtures import person, scoped_role, uid


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _candidate(db):
    candidate = Candidate(candidateID=f"C-{uid()}", candidateEmail=f"{uid()}@pool.test", candidatePassword="x",
                          tenant_id=1)
    db.add(candidate)
    db.flush()
    return candidate


def test_new_candidates_go_to_people_in_recruitment(db):
    # the shared test database may hold other recruiters: assert on eligibility, not on
    # which one the workload weighting picks
    role = scoped_role(db)
    talent = Department(id=f"D-{uid()}", tenant_id=1, name=f"Talent Acquisition {uid()}")
    sales = Department(id=f"D-{uid()}", tenant_id=1, name=f"Key Accounts {uid()}")
    db.add_all([talent, sales])
    db.flush()
    recruiter = person(db, role, "In recruitment")
    recruiter.department_id = talent.id
    titled = person(db, role, "Only the old label")
    titled.UserRole, titled.department_id = "Senior Recruiter", sales.id
    db.flush()

    from app.core import authority
    from app.models.user import Users

    result = Pool.assign_recruiter_to_candidate(_candidate(db).candidateID, 1, db)
    winner = db.query(Users).filter(Users.UserID == result["recruiter_id"]).one()
    assert winner.UserID != titled.UserID
    assert authority.in_function(db, winner, "Recruitment")  # whoever wins is in Recruitment
    assert authority.in_function(db, recruiter, "Recruitment")
    assert not authority.in_function(db, titled, "Recruitment")


def test_sales_payroll_is_the_sales_function_not_a_title(db):
    """A "Sales Engineer" delivering client work is delivery cost; a consultant seated in a
    Business Development department is sales cost (finance_agent P&L)."""
    from datetime import date

    from app.models.business_unit import BusinessUnit
    from app.models.employee import Employee
    from app.services.finance_agent import _payroll_usd
    from app.services.org_structure_service import create_org_node

    from app.core.db_contract import _initialize_org_positions

    _initialize_org_positions(db)  # what startup seeds; a fresh test database has none
    unit = BusinessUnit(tenant_id=1, name=f"BU-{uid()}", display_name="BU")
    bizdev = Department(id=f"D-{uid()}", tenant_id=1, name=f"Business Development {uid()}")
    db.add_all([unit, bizdev])
    db.flush()
    ceo = create_org_node(db, tenant_id=1, name="Top", hierarchy_level=17, specialization="General")
    seller_seat = create_org_node(db, tenant_id=1, name="Seller", hierarchy_level=16, parent_id=ceo.id,
                                  specialization=None, department_id=bizdev.id)

    def worker(title, seat=None, cents=100_00):
        return Employee(tenant_id=1, first_name="W", last_name=uid(), email=f"{uid()}@x.com", bu_id=unit.id,
                        joining_date=date(2025, 1, 1), status="ACTIVE", current_title=title,
                        base_salary_usd_cents=cents, org_node_id=seat.id if seat else None)

    db.add_all([worker("Sales Engineer"), worker("Consultant", seller_seat, 300_00)])
    db.flush()
    assert seller_seat.specialization == "Sales"
    assert _payroll_usd(db, [unit.id], sales=True) == 300
    assert _payroll_usd(db, [unit.id], sales=False) == 100
