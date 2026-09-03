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

class EmployeeConversionService:
    @staticmethod
    def create_employee_account(db, *, employee_name, employee_email, business_unit_id, tenant_id, role_ids=None, phone=None):
        existing = db.query(Users).filter(Users.UserEmail == employee_email).first()
        if existing:
            raise ValueError(f"Email {employee_email} already in use")
        password = generate_password()
        user_id = user_id_generator()
        user = Users(UserID=user_id, UserName=employee_name, UserEmail=employee_email, UserPassword=get_password_hash(password), business_unit_id=business_unit_id, tenant_id=tenant_id, UserRole="Employee")
        # Set role_template_id on user directly (use first role from role_ids, or None if not provided)
        if role_ids:
            user.role_template_id = role_ids[0]  # Single role per user (first one if multiple provided)
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def convert_candidate_to_employee(db, candidate, *, joining_date, business_unit_id=None, role_ids=None, employee_email=None, phone=None, first_name=None, last_name=None, employment_type="PERMANENT", tenant_id=None, changed_by=None, job_title=None, **fields):
        if hasattr(candidate, "status") and candidate.status == "CONVERTED_TO_EMPLOYEE":
            raise InvalidCandidateState("Candidate already converted")
        email = employee_email or candidate.candidateEmail
        fn = first_name or getattr(candidate, "candidateFirstName", "Employee") or "Employee"
        ln = last_name or getattr(candidate, "candidateLastName", "") or ""
        tid = tenant_id or getattr(candidate, "tenant_id", 1) or 1
        ph = phone or getattr(candidate, "candidateMobile", None)

        # BU Lifecycle: Preserve candidate's BU assignment on conversion
        # Use provided business_unit_id, or fall back to candidate's associated_bu_id
        final_bu_id = business_unit_id or getattr(candidate, "associated_bu_id", None) or 1

        user = EmployeeConversionService.create_employee_account(db=db, employee_name=f"{fn} {ln}".strip(), employee_email=email, business_unit_id=final_bu_id, tenant_id=tid, role_ids=role_ids, phone=ph)
        if job_title:
            user.job_title = job_title
        fields.pop("delivery_engine", None)
        emp = Employee(tenant_id=tid, candidate_id=candidate.candidateID, first_name=fn, last_name=ln, email=email, phone=ph, joining_date=joining_date, employment_type=employment_type, delivery_engine="SPECIALITY", engine_entry_date=joining_date, wros_user_id=user.UserID, **fields)
        db.add(emp)
        db.flush()
        hist = EmployeeEngineHistory(tenant_id=tid, employee_id=emp.id, from_engine=None, to_engine="SPECIALITY", changed_by=changed_by, reason="Initial hire")
        db.add(hist)
        db.flush()
        candidate.status = "CONVERTED_TO_EMPLOYEE"
        if hasattr(candidate, "candidate_employee_user_id"):
            candidate.candidate_employee_user_id = user.UserID
        db.add(candidate)
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
