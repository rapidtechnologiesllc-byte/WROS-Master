"""
HRMS-0313 -- Employee Conversion Workflow (Phase 3)
Convert accepted candidate to active employee with user account, role assignment, and onboarding.
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.candidate import Candidate
from app.models.employee import Employee, EmploymentHistory
from app.models.user import Users
from app.models.business_unit_context import BusinessUnitContext


class EmployeeConversionService:
    """Manages candidate-to-employee conversion and employee account setup."""

    def convert_candidate_to_employee(
        self,
        db: Session,
        candidate_id: str,
        tenant_id: int,
        employee_name: str,
        employee_email: str,
        bu_context_id: int,
        position_title: str,
        joining_date: datetime,
        employment_type: str = "FULL_TIME",
        salary_usd_cents: int = 0,
        role_ids: list = None
    ) -> dict:
        """Convert candidate to employee and create user account."""
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            return {"status": "error", "message": "Candidate not found"}

        if candidate.status != "OFFER_ACCEPTED":
            return {"status": "error", "message": "Candidate has not accepted offer"}

        # Generate unique employee ID
        employee_id = str(uuid.uuid4())

        # Create user account
        user = Users(
            UserID=employee_id,
            username=employee_email.split('@')[0],
            email=employee_email,
            first_name=employee_name.split()[0] if ' ' in employee_name else employee_name,
            last_name=employee_name.split()[1] if ' ' in employee_name else "",
            tenant_id=tenant_id,
            is_active=True,
            created_at=datetime.utcnow()
        )

        db.add(user)

        # Create employee record
        employee = Employee(
            id=employee_id,
            tenant_id=tenant_id,
            employee_name=employee_name,
            employee_email=employee_email,
            bu_context_id=bu_context_id,
            employment_type=employment_type,
            position=position_title,
            joining_date=joining_date,
            created_at=datetime.utcnow()
        )

        db.add(employee)

        # Create employment history entry
        history = EmploymentHistory(
            id=str(uuid.uuid4()),
            employee_id=employee_id,
            tenant_id=tenant_id,
            employment_type=employment_type,
            position=position_title,
            effective_date=joining_date,
            created_at=datetime.utcnow(),
            change_type="HIRE"
        )

        db.add(history)

        # Update candidate status
        candidate.status = "CONVERTED_TO_EMPLOYEE"
        candidate.candidate_employee_user_id = employee_id

        db.commit()

        return {
            "status": "success",
            "employee_id": employee_id,
            "candidate_id": candidate_id,
            "employee_name": employee_name,
            "employee_email": employee_email,
            "joining_date": joining_date.isoformat(),
            "user_account_created": True,
            "employment_history_created": True
        }

    def assign_roles_to_employee(
        self,
        db: Session,
        employee_id: str,
        tenant_id: int,
        role_ids: List[int]
    ) -> dict:
        """Assign roles to newly converted employee."""
        user = db.query(Users).filter(
            Users.UserID == employee_id,
            Users.tenant_id == tenant_id
        ).first()

        if not user:
            return {"status": "error", "message": "User not found"}

        # Assign roles (implementation depends on RBAC model structure)
        # This is a placeholder - real implementation would use user_roles table
        user.assigned_roles = role_ids
        db.commit()

        return {
            "status": "success",
            "employee_id": employee_id,
            "roles_assigned": role_ids,
            "total_roles": len(role_ids)
        }

    def start_onboarding(
        self,
        db: Session,
        employee_id: str,
        tenant_id: int,
        buddy_employee_id: str = None,
        manager_employee_id: str = None
    ) -> dict:
        """Initialize onboarding process for new employee."""
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.tenant_id == tenant_id
        ).first()

        if not employee:
            return {"status": "error", "message": "Employee not found"}

        # Set onboarding flags
        employee.onboarding_started = True
        employee.onboarding_start_date = datetime.utcnow()
        employee.buddy_employee_id = buddy_employee_id
        employee.manager_employee_id = manager_employee_id

        db.commit()

        return {
            "status": "success",
            "employee_id": employee_id,
            "onboarding_started": True,
            "buddy_assigned": buddy_employee_id is not None,
            "manager_assigned": manager_employee_id is not None,
            "start_date": employee.onboarding_start_date.isoformat()
        }

    def get_employee_summary(
        self,
        db: Session,
        employee_id: str,
        tenant_id: int
    ) -> dict:
        """Get complete employee profile."""
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.tenant_id == tenant_id
        ).first()

        if not employee:
            return None

        user = db.query(Users).filter(
            Users.UserID == employee_id,
            Users.tenant_id == tenant_id
        ).first()

        return {
            "employee_id": employee_id,
            "name": employee.employee_name,
            "email": employee.employee_email,
            "position": employee.position,
            "employment_type": employee.employment_type,
            "joining_date": employee.joining_date.isoformat(),
            "onboarding_status": "STARTED" if employee.onboarding_started else "PENDING",
            "user_account_active": user.is_active if user else False,
            "bu_context_id": employee.bu_context_id,
            "created_at": employee.created_at.isoformat()
        }
