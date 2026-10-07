"""S-313 Employee Conversion Service"""
from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.core.security import get_password_hash
from app.models.candidate import Candidate
from app.models.employee import Employee, EmployeeEngineHistory
from app.models.user import Users
from app.services.email_service import EmailService
import logging
from app.utils.uniq_id_generator import user_id_generator, generate_password
logger = logging.getLogger(__name__)

class InvalidCandidateState(Exception):
    pass

def _default_employee_role_id(db) -> int:
    from app.models.role_template import RoleTemplate
    role = db.query(RoleTemplate).filter(RoleTemplate.name == "User").first()
    if role is None:
        raise ValueError("No role picked and the standard 'User' role template does not exist")
    return role.id


def hired_for_job(db, candidate):
    """The job (requisition) the candidate is being hired for: the job on
    the candidate, else the most recent submission's job."""
    from app.models.user import Jobs
    if getattr(candidate, "job_id", None):
        job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job:
            return job
    from app.models.submission import Submission
    sub = (db.query(Submission).filter(Submission.candidate_id == candidate.candidateID)
           .order_by(Submission.created_at.desc()).first())
    return db.query(Jobs).filter(Jobs.jobID == sub.demand_id).first() if sub else None


def employer_company_for(db, job, bu_id):
    """Employer company: the client's contracting company for a client role,
    else the BU's company when the BU runs in exactly one."""
    if job is not None and job.client is not None and job.client.contracting_company_id:
        return job.client.contracting_company_id
    from app.models.business_unit import BusinessUnitCompany
    companies = [c.company_id for c in db.query(BusinessUnitCompany).filter(BusinessUnitCompany.business_unit_id == bu_id)]
    return companies[0] if len(companies) == 1 else None


class EmployeeConversionService:
    @staticmethod
    def create_employee_account(db, *, employee_name, employee_email, business_unit_id, tenant_id, role_ids=None, phone=None):
        existing = db.query(Users).filter(Users.UserEmail == employee_email).first()
        if existing:
            raise ValueError(f"Email {employee_email} already in use")
        password = generate_password()
        user_id = user_id_generator()
        user = Users(UserID=user_id, UserName=employee_name, UserEmail=employee_email, UserPassword=get_password_hash(password), business_unit_id=business_unit_id, tenant_id=tenant_id, UserRole="Employee")
        # One role per user: the first one picked, else the standard "User" role
        user.role_template_id = role_ids[0] if role_ids else _default_employee_role_id(db)
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def convert_candidate_to_employee(db, candidate, *, joining_date, business_unit_id=None, role_ids=None, employee_email=None, phone=None, first_name=None, last_name=None, employment_type="PERMANENT", tenant_id=None, changed_by=None, job_title=None, company_id=None, **fields):
        """Candidate -> Employee, carrying the chain forward from the job the
        candidate was hired for: business unit, employer company, and (for a
        client role) an ACTIVE allocation to that job's client/project, which
        is what timesheets and invoices hang off. Returns (user, employee);
        employee.conversion_allocation is the allocation or None."""
        if hasattr(candidate, "status") and candidate.status == "CONVERTED_TO_EMPLOYEE":
            raise InvalidCandidateState("Candidate already converted")
        email = employee_email or candidate.candidateEmail
        fn = first_name or getattr(candidate, "candidateFirstName", "Employee") or "Employee"
        ln = last_name or getattr(candidate, "candidateLastName", "") or ""
        tid = tenant_id or getattr(candidate, "tenant_id", 1) or 1
        ph = phone or getattr(candidate, "candidateMobile", None)

        job = hired_for_job(db, candidate)
        final_bu_id = (business_unit_id or (job.business_unit_id if job else None)
                       or getattr(candidate, "associated_bu_id", None) or getattr(candidate, "submission_bu_id", None))
        if not final_bu_id:
            raise ValueError("A business unit is required: pick one, or set it on the candidate's job.")
        final_company_id = company_id or employer_company_for(db, job, final_bu_id)

        user = EmployeeConversionService.create_employee_account(db=db, employee_name=f"{fn} {ln}".strip(), employee_email=email, business_unit_id=final_bu_id, tenant_id=tid, role_ids=role_ids, phone=ph)
        user.job_title = job_title or (job.jobTitle if job else None)
        if final_company_id:
            user.location_id = final_company_id
        fields.pop("delivery_engine", None)
        emp = Employee(tenant_id=tid, candidate_id=candidate.candidateID, first_name=fn, last_name=ln, email=email, phone=ph,
                       joining_date=joining_date, employment_type=employment_type, delivery_engine="SPECIALITY",
                       engine_entry_date=joining_date, wros_user_id=user.UserID, bu_id=final_bu_id,
                       company_id=final_company_id, current_title=user.job_title, **fields)
        db.add(emp)
        db.flush()
        hist = EmployeeEngineHistory(tenant_id=tid, employee_id=emp.id, from_engine=None, to_engine="SPECIALITY", changed_by=changed_by, reason="Initial hire")
        db.add(hist)
        db.flush()
        candidate.status = "CONVERTED_TO_EMPLOYEE"
        # A permanent / fixed-term BlitzenX employee is W2 by definition; this is
        # what makes them submittable to client jobs (submission employment-type gate)
        if employment_type in ("PERMANENT", "FIXED_TERM"):
            candidate.employment_type = "W2_FULLTIME"
        if hasattr(candidate, "candidate_employee_user_id"):
            candidate.candidate_employee_user_id = user.UserID
        db.add(candidate)

        emp.conversion_allocation = None
        if job is not None and job.client_id:
            from app.models.project import Project
            from app.services.demand_service import record_placement
            from app.services.employee_allocation_service import allocate_employee_to_project
            project = db.query(Project).filter(Project.id == job.project_id).first() if job.project_id else None
            emp.conversion_allocation = allocate_employee_to_project(
                db, tenant_id=tid, employee=emp, demand=job, start_date=joining_date,
                project=project, role=job.jobTitle, changed_by=changed_by,
            )
            record_placement(db, job)
            db.flush()
        db.flush()
        if joining_date <= date.today():
            # transition only; the caller commits the whole conversion
            from app.services.employee_service import transition_employee_status
            transition_employee_status(db, emp, "ACTIVE", reason="Joining date reached", changed_by=changed_by)
            if emp.conversion_allocation is not None:
                transition_employee_status(db, emp, "ALLOCATED", reason="Joined onto allocation", changed_by=changed_by)
        return user, emp

    @staticmethod
    def send_welcome_email(db, employee_user, employee_record, temporary_password=None, include_onboarding_link=True):
        try:
            if not temporary_password:
                temporary_password = generate_password()
            date_str = employee_record.joining_date.strftime("%d %B %Y")
            body = f"<p>Welcome {employee_user.UserName}!</p><p>Email: {employee_user.UserEmail}</p><p>Temp Password: {temporary_password}</p><p>Join Date: {date_str}</p>"
            email_html = EmailService._base_html("Welcome to BlitzenX", body)
            EmailService.send_email_direct(to_email=employee_user.UserEmail, to_name=employee_user.UserName, subject="Welcome to BlitzenX", html_body=email_html)
            return True
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Email failed: {str(e)}")
            return False
