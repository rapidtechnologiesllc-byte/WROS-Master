"""S-313 Employee Conversion Service"""
import logging
from datetime import date

from app.models.employee import Employee, EmployeeEngineHistory
from app.models.user import Users
from app.utils.uniq_id_generator import user_id_generator
logger = logging.getLogger(__name__)

class InvalidCandidateState(Exception):
    pass

def _default_employee_role_id(db) -> int:
    """The self-service Employee role (seeded at startup). Never the system "User" role,
    which carries every permission."""
    from app.models.role_template import RoleTemplate
    role = db.query(RoleTemplate).filter(RoleTemplate.name == "Employee", RoleTemplate.enabled.is_(True)).first()
    if role is None:
        raise ValueError("The Employee role template does not exist; it is created at startup (db_contract)")
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


def monthly_salary_from_offer(db, candidate, job):
    """Monthly base salary (USD cents) from the candidate's accepted offer, for this job
    when there is one: an Offer (annual USD), else an accepted OfferLetter (annual CTC in
    INR, converted with FX_INR_PER_USD). None when neither gives a reliable figure."""
    from app.models.offer import Offer

    query = db.query(Offer).filter(Offer.candidate_id == candidate.candidateID,
                                   Offer.status.in_(("ACCEPTED", "SIGNED")))
    if job is not None:
        query = query.filter(Offer.job_id == job.jobID)
    offer = query.order_by(Offer.accepted_at.desc().nullslast(), Offer.created_at.desc()).first()
    if offer and offer.base_salary_usd_cents:
        return round(offer.base_salary_usd_cents / 12)
    return _monthly_usd_from_offer_letter(db, candidate, job)


def _monthly_usd_from_offer_letter(db, candidate, job):
    import re

    from app.core.config import settings
    from app.models.offer_letter import OfferLetter

    query = db.query(OfferLetter).filter(OfferLetter.candidate_id == candidate.candidateID,
                                         OfferLetter.offer_status == "Accepted")
    if job is not None:
        query = query.filter((OfferLetter.job_id == job.jobID) | (OfferLetter.job_id.is_(None)))
    letter = query.order_by(OfferLetter.responded_at.desc().nullslast(), OfferLetter.id.desc()).first()
    if letter is None:
        return None
    digits = re.sub(r"[^0-9.]", "", letter.salary or "")
    if not digits or not settings.FX_INR_PER_USD:
        logger.warning(f"[Conversion] offer letter {letter.id}: salary {letter.salary!r} not converted "
                       f"(FX_INR_PER_USD {'set' if settings.FX_INR_PER_USD else 'not set'}); cost stays unknown")
        return None
    annual_inr = float(digits)
    return round(annual_inr / settings.FX_INR_PER_USD * 100 / 12)


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
        from app.services.account_activation_service import prepare_new_account

        # One role per user: the first one picked, else the standard "User" role
        role_template_id = role_ids[0] if role_ids else _default_employee_role_id(db)
        user = Users(UserID=user_id_generator(), UserName=employee_name, UserEmail=employee_email, UserPassword="!",
                     business_unit_id=business_unit_id, tenant_id=tenant_id, UserRole="Employee",
                     role_template_id=role_template_id)
        # no usable password: the employee sets their own from the activation email (queued after commit)
        prepare_new_account(db, user)
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
        if fields.get("base_salary_usd_cents") is None:
            # without it the employee's cost is unknown and every P&L they touch is incomplete
            fields["base_salary_usd_cents"] = monthly_salary_from_offer(db, candidate, job)
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

