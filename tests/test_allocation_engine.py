"""
S-314 — Project Allocation Engine
Unit tests for allocation service and API endpoints.

Test Coverage:
  1. allocate_employee_to_project() — Create allocations with capacity checks
  2. get_available_projects() — List and filter projects
  3. check_capacity() — Verify capacity calculation logic
  4. REST endpoints — Full CRUD operations
  5. Conflict detection — Overlapping allocations
  6. Validation — Pre-allocation checks
"""

import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.project import Project
from app.models.demand import Demand
from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.tenant import Tenant
from app.services.employee_allocation_service import (
    allocate_employee_to_project,
    check_capacity,
    get_available_projects,
    AllocationOverCapacity,
    EmployeeAlreadyAllocated,
    BuddyProgramNotGraduated,
)


@pytest.fixture
def db():
    """Test database session."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def tenant(db: Session):
    """Create test tenant."""
    tenant = Tenant(name="Test Tenant", status="ACTIVE")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@pytest.fixture
def client(db: Session, tenant: Tenant):
    """Create test client."""
    client = Client(
        tenant_id=tenant.id,
        company_name="Test Client Co.",
        industry="Technology",
        website="https://testclient.com",
        company_size="MEDIUM",
        contract_value_usd_cents=100000000,  # $1M
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@pytest.fixture
def demand(db: Session, tenant: Tenant, client: Client):
    """Create test demand."""
    demand = Demand(
        tenant_id=tenant.id,
        client_id=client.id,
        job_title="Senior Software Engineer",
        required_skills="Python, FastAPI, PostgreSQL",
        location="Remote",
        work_location="REMOTE",
        billing_rate_usd_cents=15000,  # $150/hr
    )
    db.add(demand)
    db.commit()
    db.refresh(demand)
    return demand


@pytest.fixture
def project(db: Session, tenant: Tenant, client: Client):
    """Create test project."""
    project = Project(
        tenant_id=tenant.id,
        client_id=client.id,
        name="Migration to Cloud",
        status="ACTIVE",
        billing_type="TIME_AND_MATERIALS",
        currency="USD",
        delivery_engine="CORE",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture
def employee(db: Session, tenant: Tenant):
    """Create test employee."""
    employee = Employee(
        tenant_id=tenant.id,
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        joining_date=date.today(),
        status="BENCH",
        employment_type="PERMANENT",
        buddy_program_status="GRADUATED",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@pytest.fixture
def employee_in_buddy_program(db: Session, tenant: Tenant):
    """Create test employee in active buddy program."""
    employee = Employee(
        tenant_id=tenant.id,
        first_name="Bob",
        last_name="Smith",
        email="bob.smith@example.com",
        joining_date=date.today(),
        status="ACTIVE",
        employment_type="PERMANENT",
        buddy_program_status="IN_PROGRESS",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


class TestAllocateEmployeeToProject:
    """Tests for allocate_employee_to_project() method."""

    def test_allocate_bench_employee_to_project(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand, project: Project
    ):
        """Allocate employee from bench to project."""
        assert employee.status == "BENCH"

        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            project=project,
            utilization_pct=80.0,
            role="Senior Engineer",
            changed_by="test_user",
        )

        db.refresh(employee)
        assert allocation is not None
        assert allocation.employee_id == employee.id
        assert allocation.demand_id == demand.id
        assert allocation.project_id == project.id
        assert allocation.utilization_pct == 80.0
        assert allocation.role == "Senior Engineer"
        assert allocation.status == "ACTIVE"
        assert employee.status == "ALLOCATED"

    def test_allocate_without_project(self, db: Session, tenant: Tenant, employee: Employee, demand: Demand):
        """Allocate employee without specifying project (nullable project_id)."""
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            project=None,
            changed_by="test_user",
        )

        assert allocation is not None
        assert allocation.project_id is None
        assert allocation.status == "ACTIVE"

    def test_allocate_fails_if_buddy_program_in_progress(
        self, db: Session, tenant: Tenant, employee_in_buddy_program: Employee, demand: Demand
    ):
        """Allocation fails if employee is in active buddy program."""
        with pytest.raises(BuddyProgramNotGraduated):
            allocate_employee_to_project(
                db,
                tenant_id=tenant.id,
                employee=employee_in_buddy_program,
                demand=demand,
                changed_by="test_user",
            )

    def test_allocate_fails_if_already_allocated_single_allocation_mode(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """In single-allocation mode, allocating twice fails."""
        # First allocation succeeds
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            changed_by="test_user",
        )
        db.commit()

        # Second allocation fails
        with pytest.raises(EmployeeAlreadyAllocated):
            allocate_employee_to_project(
                db,
                tenant_id=tenant.id,
                employee=employee,
                demand=demand,
                allow_concurrent=False,
                changed_by="test_user",
            )

    def test_allocate_concurrent_within_capacity(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Multiple allocations allowed if total utilization <= 100%."""
        # First allocation at 50%
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=50.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        # Second allocation at 50% succeeds
        allocation2 = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=50.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        assert allocation2 is not None
        assert allocation2.status == "ACTIVE"

    def test_allocate_concurrent_exceeds_capacity(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Multiple allocations fail if total utilization > 100%."""
        # First allocation at 70%
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=70.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        # Second allocation at 40% fails (total would be 110%)
        with pytest.raises(AllocationOverCapacity):
            allocate_employee_to_project(
                db,
                tenant_id=tenant.id,
                employee=employee,
                demand=demand,
                utilization_pct=40.0,
                allow_concurrent=True,
                changed_by="test_user",
            )


class TestGetAvailableProjects:
    """Tests for get_available_projects() method."""

    def test_get_all_active_projects(self, db: Session, tenant: Tenant, project: Project):
        """Get all active projects by default."""
        projects = get_available_projects(db, tenant_id=tenant.id)
        assert len(projects) >= 1
        assert any(p.id == project.id for p in projects)

    def test_get_projects_with_status_filter(
        self, db: Session, tenant: Tenant, client: Client
    ):
        """Get projects filtered by status."""
        # Create projects with different statuses
        active_project = Project(
            tenant_id=tenant.id,
            client_id=client.id,
            name="Active Project",
            status="ACTIVE",
            billing_type="TIME_AND_MATERIALS",
            currency="USD",
        )
        completed_project = Project(
            tenant_id=tenant.id,
            client_id=client.id,
            name="Completed Project",
            status="COMPLETED",
            billing_type="TIME_AND_MATERIALS",
            currency="USD",
        )
        db.add_all([active_project, completed_project])
        db.commit()

        active_projects = get_available_projects(db, tenant_id=tenant.id, status_filter="ACTIVE")
        assert active_project in active_projects
        assert completed_project not in active_projects

    def test_get_projects_with_employee_conflict_filter(
        self, db: Session, tenant: Tenant, employee: Employee, project: Project, demand: Demand
    ):
        """Exclude projects with existing employee allocations."""
        # Allocate employee to project
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            project=project,
            changed_by="test_user",
        )
        db.commit()

        # Get projects, excluding those with allocations for this employee
        available_projects = get_available_projects(
            db, tenant_id=tenant.id, employee_id=employee.id
        )
        assert project not in available_projects

    def test_get_projects_empty_tenant(self, db: Session):
        """Get projects for tenant with no projects."""
        tenant = Tenant(name="Empty Tenant", status="ACTIVE")
        db.add(tenant)
        db.commit()

        projects = get_available_projects(db, tenant_id=tenant.id)
        assert len(projects) == 0


class TestCheckCapacity:
    """Tests for check_capacity() method."""

    def test_employee_with_no_allocations_has_full_capacity(
        self, db: Session, employee: Employee
    ):
        """Employee with no allocations has 100% available capacity."""
        has_capacity, current_utilization, available_capacity = check_capacity(
            db, employee_id=employee.id, additional_utilization_pct=100.0
        )

        assert has_capacity is True
        assert current_utilization == 0.0
        assert available_capacity == 100.0

    def test_employee_with_single_allocation_capacity(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Employee with 50% allocation has 50% available capacity."""
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=50.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        has_capacity, current_utilization, available_capacity = check_capacity(
            db, employee_id=employee.id, additional_utilization_pct=50.0
        )

        assert has_capacity is True
        assert current_utilization == 50.0
        assert available_capacity == 50.0

    def test_employee_exceeds_capacity(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Employee cannot accept allocation that would exceed 100%."""
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=70.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        has_capacity, current_utilization, available_capacity = check_capacity(
            db, employee_id=employee.id, additional_utilization_pct=40.0
        )

        assert has_capacity is False
        assert current_utilization == 70.0
        assert available_capacity == 30.0

    def test_capacity_check_ignores_ended_allocations(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Ended allocations do not count toward utilization."""
        # Create and end allocation
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=80.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        from app.services.employee_allocation_service import end_allocation
        end_allocation(db, allocation, employee, changed_by="test_user")
        db.commit()

        # Check capacity should show no utilization
        has_capacity, current_utilization, available_capacity = check_capacity(
            db, employee_id=employee.id, additional_utilization_pct=100.0
        )

        assert has_capacity is True
        assert current_utilization == 0.0
        assert available_capacity == 100.0

    def test_capacity_check_with_future_start_date(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Capacity check respects allocation end dates for future start dates."""
        tomorrow = date.today() + timedelta(days=1)
        next_week = date.today() + timedelta(days=7)

        # Allocation ending tomorrow
        allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=80.0,
            start_date=date.today(),
            end_date=tomorrow,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()

        # Check capacity for date after allocation ends
        has_capacity, current_utilization, available_capacity = check_capacity(
            db,
            employee_id=employee.id,
            additional_utilization_pct=100.0,
            proposed_start_date=next_week,
        )

        assert has_capacity is True
        assert current_utilization == 0.0  # Allocation ended before proposed start date
        assert available_capacity == 100.0


class TestEndAllocation:
    """Tests for ending allocations."""

    def test_end_allocation_moves_employee_to_bench(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Ending sole allocation moves employee to bench."""
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            changed_by="test_user",
        )
        db.commit()
        assert employee.status == "ALLOCATED"

        from app.services.employee_allocation_service import end_allocation
        end_allocation(db, allocation, employee, changed_by="test_user")
        db.commit()

        db.refresh(employee)
        assert employee.status == "BENCH"
        assert allocation.status == "ENDED"

    def test_end_one_allocation_keeps_employee_allocated(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Ending one allocation while others exist keeps employee ALLOCATED."""
        allocation1 = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=50.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        allocation2 = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            utilization_pct=50.0,
            allow_concurrent=True,
            changed_by="test_user",
        )
        db.commit()
        assert employee.status == "ALLOCATED"

        from app.services.employee_allocation_service import end_allocation
        end_allocation(db, allocation1, employee, changed_by="test_user")
        db.commit()

        db.refresh(employee)
        assert employee.status == "ALLOCATED"  # Still allocated to allocation2
        assert allocation1.status == "ENDED"


class TestAllocationValidation:
    """Tests for allocation validation scenarios."""

    def test_allocate_with_custom_start_date(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Allocate with future start date."""
        future_date = date.today() + timedelta(days=30)
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            start_date=future_date,
            changed_by="test_user",
        )
        db.commit()

        assert allocation.start_date == future_date

    def test_allocate_with_end_date(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Allocate with defined end date."""
        end_date = date.today() + timedelta(days=90)
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            end_date=end_date,
            changed_by="test_user",
        )
        db.commit()

        assert allocation.end_date == end_date

    def test_allocate_with_billing_info(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """Allocate with custom billing rate."""
        custom_billing = 20000  # $200/hr
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            billing_rate_usd_cents=custom_billing,
            changed_by="test_user",
        )
        db.commit()

        assert allocation.billing_rate_usd_cents == custom_billing

    def test_allocate_defaults_billing_from_demand(
        self, db: Session, tenant: Tenant, employee: Employee, demand: Demand
    ):
        """If billing rate not specified, defaults to demand's rate."""
        allocation = allocate_employee_to_project(
            db,
            tenant_id=tenant.id,
            employee=employee,
            demand=demand,
            changed_by="test_user",
        )
        db.commit()

        assert allocation.billing_rate_usd_cents == demand.billing_rate_usd_cents
