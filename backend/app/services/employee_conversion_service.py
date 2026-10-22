"""S-313 Employee Conversion Service"""
import logging
from datetime import date

from app.models.employee import Employee, EmployeeEngineHistory
from app.models.user import Users
from app.utils.uniq_id_generator import user_id_generator
logger = logging.getLogger(__name__)

class InvalidCandidateState(Exception):
    pass

def _default_employee_role_id(db, tenant_id) -> int:
    """The tenant's self-service Employee role (seeded at startup). Never the system "User"
    role, which carries every permission."""
    from app.models.role_template import RoleTemplate
    role = db.query(RoleTemplate).filter(RoleTemplate.name == "Employee", RoleTemplate.tenant_id == tenant_id,
                                         RoleTemplate.enabled.is_(True)).first()
    if role is None:
        raise ValueError(f"Tenant {tenant_id} has no Employee role template; pick a function add-on for the employee")
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


def place_new_hire(db, user, role, parent_node_id, bu_id, company_id, require_seat):
    """Connect the new hire to the org chart: their role's level, reporting to the given seat
    or -- autonomously -- to the BU head of their business unit in their employer company.
    On the conversion screen (require_seat) a placement the reporting rules refuse fails the
    conversion; on the autonomous path the employee is still created and their BU head (or
    HR) gets a task to place them, so nobody is silently left out of the organization."""
    from app.models.business_unit import BusinessUnitLocationHead
    from app.services.org_structure_service import place_user_in_org

    head_user_id = None
    if not parent_node_id and company_id:
        head = db.query(BusinessUnitLocationHead).filter(BusinessUnitLocationHead.business_unit_id == bu_id,
                                                         BusinessUnitLocationHead.company_id == company_id).first()
        head_user_id = head.head_user_id if head else None
        boss = db.query(Users).filter(Users.UserID == head_user_id).first() if head_user_id else None
        parent_node_id = boss.org_node_id if boss else None
    problem = None
    if role is None:
        problem = "no org role matches their position"
    elif not parent_node_id and role.hierarchy_level < 17:
        problem = "no supervisor seat was given and their BU has no BU head seated for their company"
    else:
        try:
            place_user_in_org(db, user, hierarchy_level=role.hierarchy_level, specialization=None,
                              parent_id=parent_node_id, company_id=company_id, department_id=user.department_id)
            return
        except ValueError as exc:
            problem = str(exc)
    if require_seat:
        raise ValueError(f"Cannot place {user.UserName} in the org chart: {problem}")
    from app.services.task_service import create_task

    create_task(db, title=f"Place {user.UserName} in the org chart",
                description=(f"{user.UserName} joined as an employee but is not connected to the organization: "
                             f"{problem}. Edit the user to give them a role and who they report to."),
                priority="HIGH", tenant_id=user.tenant_id, assigned_to_user_id=head_user_id,
                category="ORG_PLACEMENT",
                visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if head_user_id else "ORG_WIDE")
    logger.warning(f"[Conversion] {user.UserID} not placed in the org chart: {problem}")


class EmployeeConversionService:
    @staticmethod
    def create_employee_account(db, *, employee_name, employee_email, business_unit_id, tenant_id, role_ids=None, phone=None):
        existing = db.query(Users).filter(Users.UserEmail == employee_email).first()
        if existing:
            raise ValueError(f"Email {employee_email} already in use")
        from app.services.account_activation_service import prepare_new_account

        # One function add-on per user: the one picked, else the tenant's self-service Employee role
        from app.services.role_template_permission_service import validate_addon_template
        role_template_id = (validate_addon_template(db, role_ids[0], tenant_id).id if role_ids
                            else _default_employee_role_id(db, tenant_id))
        user = Users(UserID=user_id_generator(), UserName=employee_name, UserEmail=employee_email, UserPassword="!",
                     business_unit_id=business_unit_id, tenant_id=tenant_id, UserRole="Employee",
                     role_template_id=role_template_id)
        # no usable password: the employee sets their own from the activation email (queued after commit)
        prepare_new_account(db, user)
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def convert_candidate_to_employee(db, candidate, *, joining_date, business_unit_id=None, role_ids=None, employee_email=None, phone=None, first_name=None, last_name=None, employment_type="PERMANENT", tenant_id=None, changed_by=None, job_title=None, company_id=None, org_role=None, parent_node_id=None, require_seat=False, **fields):
        """Candidate -> Employee + system user, carrying the business unit and employer company
        forward from the job the candidate was hired for. A new hire joins the BENCH: they reach a
        client only through submission -> client selection -> client onboarding -> PLACED, which
        is where the project allocation is made. Returns (user, employee);
        employee.conversion_allocation is always None (kept for the response shape)."""
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
        # The posting title stays on the employee record; the login's Job Title is an org role
        posting_title = job_title or (job.jobTitle if job else None)
        from app.services.org_roles_service import require_role, role_for_title

        role = require_role(db, tid, org_role) if (org_role or require_seat) else role_for_title(db, tid, posting_title)
        # no matching role: keep the posting title rather than a blank one (placement task follows)
        user.job_title = role.name if role else posting_title
        if final_company_id:
            user.location_id = final_company_id
        fields.pop("delivery_engine", None)
        if fields.get("base_salary_usd_cents") is None:
            # without it the employee's cost is unknown and every P&L they touch is incomplete
            fields["base_salary_usd_cents"] = monthly_salary_from_offer(db, candidate, job)
        emp = Employee(tenant_id=tid, candidate_id=candidate.candidateID, first_name=fn, last_name=ln, email=email, phone=ph,
                       joining_date=joining_date, employment_type=employment_type, delivery_engine="SPECIALITY",
                       engine_entry_date=joining_date, wros_user_id=user.UserID, bu_id=final_bu_id,
                       company_id=final_company_id, current_title=posting_title, **fields)
        db.add(emp)
        db.flush()
        place_new_hire(db, user, role, parent_node_id, final_bu_id, final_company_id, require_seat)
        hist = EmployeeEngineHistory(tenant_id=tid, employee_id=emp.id, from_engine=None, to_engine="SPECIALITY", changed_by=changed_by, reason="Initial hire")
        db.add(hist)
        db.flush()
        candidate.status = "CONVERTED_TO_EMPLOYEE"
        # A BlitzenX employee's employment type is known once they join: permanent / fixed-term is
        # FULLTIME, a contract employee CONTRACT (labelled "W2 ..." in the US). With the country
        # (when the profile has none: the delivery company they join, else their profile
        # location) it is what the client-submission employment-type gate reads
        if employment_type in ("PERMANENT", "FIXED_TERM"):
            candidate.employment_type = "FULLTIME"
        elif employment_type == "CONTRACT":
            candidate.employment_type = "CONTRACT"
        if not candidate.country:
            from app.models.location import Location
            from app.services.employment_type_policy import country_code

            company = db.query(Location).filter(Location.id == final_company_id).first() if final_company_id else None
            candidate.country = (country_code(company.country) if company else None) \
                or country_code(candidate.candidateCurrentLocation)
        if hasattr(candidate, "candidate_employee_user_id"):
            candidate.candidate_employee_user_id = user.UserID
        db.add(candidate)

        emp.conversion_allocation = None
        db.flush()
        if joining_date <= date.today():
            # transition only; the caller commits the whole conversion
            from app.services.employee_service import transition_employee_status
            from app.services.employee_service import place_unallocated_joiner

            transition_employee_status(db, emp, "ACTIVE", reason="Joining date reached", changed_by=changed_by)
            place_unallocated_joiner(db, emp, changed_by=changed_by)
        return user, emp

