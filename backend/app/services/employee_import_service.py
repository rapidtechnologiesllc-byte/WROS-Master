"""Employee import (CEO 2026-10-22): the one way an employee enters the system outside the hiring
pipeline -- a CSV of current staff, or one person from the Add employee form (POST /employees),
both through plan_rows() and apply_rows() below.

Dry run -> apply:
  dry_run()   parses the file, resolves every row against the tenant (business unit, delivery
              center, role template, manager, job) and returns what each row WOULD do. Nothing is
              written except the batch row that holds the parsed file under its token
              (sha256 of tenant + uploader + rows); nothing is emailed.
  apply()     needs that token and the same file (same hash), from the same uploader, before it
              expires. Every row is re-planned against the database as it is now and applied in
              its own transaction: a bad row is reported and rolled back, the others commit. Applying
              the same file again changes nothing (rows come back "unchanged").

What one row becomes (every row, create or update):
  - a login: the existing Users row with that email is linked, else one is created with no usable
    password (prepare_new_account) and the activation email is queued once, after commit
    (account_activation_service.queue_account_email with a deterministic key);
  - the Employee: business unit, delivery center (employer company), designation, manager,
    employment type (FULLTIME/CONTRACT accepted in the country), billable or not, monthly salary
    (the P&L and bench cost source) and bill rate; Employee.wros_user_id set;
  - the role template: the one named (validate_addon_template), else the tenant's Employee role,
    the same rule as candidate conversion; an org-chart seat under the manager when the
    designation names an org role (else the BU head gets a placement task, as on conversion);
  - existing staff (default yes): Buddy Program GRADUATED, recorded as a GRADUATED
    BuddyProgramRecord whose decision note is "Existing employee imported <date> by <user>" plus
    an audit_log row -- the importer attests, there is no code carve-out in the deployment gate;
  - core_certified (default no): only when the uploader leads the business unit (the same people
    who approve a core-certification request), recorded as an APPROVED CoreCertificationRequest
    decided by the uploader plus an audit_log row;
  - status: joining date in the future -> PRE_JOINING (the joiner job activates them); else ACTIVE,
    then ALLOCATED through employee_allocation_service (every deployment gate applies) when the
    row names a job or project, else BENCH from bench_since (default the joining date) when
    billable; a non-billable employee stays ACTIVE and is never bench.

Authority: the endpoint checks employees.create; every row's business unit must be one the
uploader may assign (data_scope); an allocation row also needs allocations.create.
"""
import csv
import hashlib
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.business_unit import BusinessUnit
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_import import EmployeeImportBatch
from app.models.location import Location
from app.models.role_template import RoleTemplate
from app.models.user import Users

logger = logging.getLogger(__name__)

# (column, required, what goes in it). The one list: the template download, the parser and the
# screen's column help all read it.
IMPORT_COLUMNS: Tuple[Tuple[str, bool, str], ...] = (
    ("first_name", True, "Given name."),
    ("last_name", True, "Family name."),
    ("email", True, "Work email; the key. An existing employee with this email is updated, an existing login is linked."),
    ("employee_code", False, "Your own employee ID (kept as the tenant employee ID)."),
    ("business_unit", True, "Business unit name or code."),
    ("delivery_center", False, "Delivery center / employer company name (e.g. BX-IN). Blank: the business unit's only company."),
    ("country", False, "ISO country code (IN, US). Blank: the delivery center's country."),
    ("joining_date", True, "YYYY-MM-DD. A future date makes the employee pre-joining."),
    ("designation", False, "Job title. When it names an org role the login gets that role and an org-chart seat."),
    ("role_template", False, "Function add-on (role template name). Blank: the tenant's Employee role."),
    ("manager_email", False, "Reporting manager's login email. The employee's org-chart seat goes under the manager's seat "
                             "(the manager needs a seat, or a row earlier or later in this file); the manager approves "
                             "their timesheets."),
    ("employment_type", False, "FULLTIME (default) or CONTRACT; must be accepted in the employee's country."),
    ("billable", False, "yes (default): client-facing, bench when not on a project. no: internal staff, cost is overhead."),
    ("existing_staff", False, "yes (default): already working here, recorded as Buddy Program graduated (audited)."),
    ("core_certified", False, "no (default). yes only if you lead this business unit (recorded as your approval)."),
    ("monthly_salary", True, "Monthly base salary: the cost behind the P&L and bench cost."),
    ("salary_currency", False, "USD (default) or INR (converted at FX_INR_PER_USD)."),
    ("bill_rate_usd_hour", False, "Hourly bill rate in USD. Blank: the job's rate."),
    ("work_location", False, "REMOTE (default), ONSITE or HYBRID."),
    ("skills", False, "Skills separated by ';' or ','."),
    ("bench_since", False, "Not on a project: the day they came off their last one (YYYY-MM-DD). Blank: joining date."),
    ("allocation_job_id", False, "Job ID to allocate the employee to (its client and project are billed)."),
    ("allocation_project", False, "Or a project name with exactly one open job."),
    ("allocation_pct", False, "Allocation percentage (default 100)."),
    ("allocation_start_date", False, "YYYY-MM-DD (default: joining date). Past dates allowed so earlier weeks can be logged."),
    ("allocation_end_date", False, "YYYY-MM-DD, optional."),
)
COLUMN_NAMES = tuple(c[0] for c in IMPORT_COLUMNS)
REQUIRED_COLUMNS = tuple(c[0] for c in IMPORT_COLUMNS if c[1])

EMPLOYMENT_TYPE_TO_MODEL = {"FULLTIME": "PERMANENT", "CONTRACT": "CONTRACT"}
WORK_LOCATIONS = ("REMOTE", "ONSITE", "HYBRID")
YES, NO = {"yes", "y", "true", "1"}, {"no", "n", "false", "0"}

ACTION_CREATE, ACTION_LINK, ACTION_UPDATE, ACTION_UNCHANGED = "create", "link-existing-user", "update", "unchanged"


class ImportFileError(ValueError):
    """The file as a whole cannot be read (encoding, headers, size)."""


class ImportTokenError(ValueError):
    """The token is unknown, expired, someone else's, or the file changed since the dry run."""

    def __init__(self, message: str, status_code: int = 409):
        self.status_code = status_code
        super().__init__(message)


# --------------------------------------------------------------------------- parsing

def template_csv() -> str:
    out = io.StringIO()
    csv.writer(out).writerow(COLUMN_NAMES)
    return out.getvalue()


def parse_csv(content: bytes) -> List[Dict[str, str]]:
    """Rows as {column: stripped text}; unknown or missing required columns fail the whole file."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFileError(f"The file is not UTF-8 text (save it as CSV UTF-8): {exc}") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    if not headers:
        raise ImportFileError("The file is empty: the first line must be the column names.")
    unknown = [h for h in headers if h not in COLUMN_NAMES]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if unknown or missing:
        raise ImportFileError(
            ("Unknown columns: " + ", ".join(unknown) + ". " if unknown else "")
            + ("Missing required columns: " + ", ".join(missing) + ". " if missing else "")
            + "Download the template for the column list.")
    rows = []
    for raw in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k is not None}
        if any(row.values()):
            rows.append({c: row.get(c, "") for c in COLUMN_NAMES})
    if not rows:
        raise ImportFileError("The file has no employee rows.")
    if len(rows) > settings.EMPLOYEE_IMPORT_MAX_ROWS:
        raise ImportFileError(f"{len(rows)} rows: the limit is {settings.EMPLOYEE_IMPORT_MAX_ROWS} per file.")
    return rows


def token_for(tenant_id: int, uploader_id: str, rows: List[Dict[str, str]]) -> str:
    canonical = json.dumps({"tenant": tenant_id, "uploader": uploader_id, "rows": rows}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


# --------------------------------------------------------------------------- resolution

@dataclass
class Spec:
    """One row resolved against the database (ids and objects, not text)."""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    employee_code: Optional[str] = None
    unit: Optional[BusinessUnit] = None
    company: Optional[Location] = None
    country: Optional[str] = None
    joining_date: Optional[date] = None
    designation: Optional[str] = None
    role_template: Optional[RoleTemplate] = None
    manager: Optional[Users] = None
    manager_in_file: Optional[str] = None  # manager is another row of this file, not yet a login (dry run)
    employment_type: str = "PERMANENT"
    billable: bool = True
    existing_staff: bool = True
    core_certified: bool = False
    salary_cents: Optional[int] = None
    bill_rate_cents: Optional[int] = None
    work_location: Optional[str] = None
    skills: Optional[List[str]] = None
    bench_since: Optional[date] = None
    job: Any = None
    allocation_pct: float = 100.0
    allocation_start: Optional[date] = None
    allocation_end: Optional[date] = None
    errors: List[str] = field(default_factory=list)


def _date(value: str, column: str, errors: List[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"{column} '{value}' is not a date in YYYY-MM-DD form.")
        return None


def _flag(value: str, column: str, default: bool, errors: List[str]) -> bool:
    if not value:
        return default
    if value.lower() in YES:
        return True
    if value.lower() in NO:
        return False
    errors.append(f"{column} must be yes or no, got '{value}'.")
    return default


def _money_cents(value: str, column: str, errors: List[str]) -> Optional[int]:
    if not value:
        return None
    try:
        amount = float(value.replace(",", ""))
    except ValueError:
        errors.append(f"{column} '{value}' is not a number.")
        return None
    if amount < 0:
        errors.append(f"{column} cannot be negative.")
        return None
    return round(amount * 100)


class _Lookups:
    """Everything a batch resolves against, read once per batch."""

    def __init__(self, db: Session, uploader: Users):
        from app.core.data_scope import visible_bu_ids

        tid = uploader.tenant_id
        self.db, self.uploader, self.tenant_id = db, uploader, tid
        self.units = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tid).all()
        self.companies = db.query(Location).filter(Location.tenant_id == tid).all()
        self.templates = db.query(RoleTemplate).filter(RoleTemplate.tenant_id == tid).all()
        self.assignable = visible_bu_ids(db, uploader)  # None = every business unit
        self.file_rows: Dict[str, Dict[str, str]] = {}  # email -> row, for managers listed in the same file
        self.applying = False

    def unit(self, text: str) -> Optional[BusinessUnit]:
        key = text.strip().lower()
        for unit in self.units:
            if key in {str(unit.id), (unit.name or "").lower(), (unit.display_name or "").lower(),
                       (unit.bu_code or "").lower()}:
                return unit
        return None

    def company(self, text: str) -> Optional[Location]:
        key = text.strip().lower()
        matches = [c for c in self.companies if key in {c.id.lower(), (c.name or "").lower()}]
        return matches[0] if len(matches) == 1 else None

    def template(self, text: str) -> Optional[RoleTemplate]:
        key = text.strip().lower()
        matches = [t for t in self.templates
                   if key in {str(t.id), (t.name or "").lower(), (t.display_name or "").lower()}]
        return matches[0] if len(matches) == 1 else None


def _resolve(lk: _Lookups, row: Dict[str, str]) -> Spec:
    from app.services import employment_type_policy as policy
    from app.services.employee_conversion_service import employer_company_for

    db, errors = lk.db, []
    spec = Spec(errors=errors)
    spec.first_name, spec.last_name = row["first_name"], row["last_name"]
    spec.email = row["email"].lower()
    for column in REQUIRED_COLUMNS:
        if not row.get(column):
            errors.append(f"{column} is required.")
    if spec.email and ("@" not in spec.email or " " in spec.email):
        errors.append(f"email '{row['email']}' is not an email address.")
    spec.employee_code = row["employee_code"] or None
    spec.designation = row["designation"] or None

    if row["business_unit"]:
        spec.unit = lk.unit(row["business_unit"])
        if spec.unit is None:
            errors.append(f"Business unit '{row['business_unit']}' not found.")
        elif lk.assignable is not None and spec.unit.id not in lk.assignable:
            errors.append(f"You cannot add employees to business unit '{spec.unit.display_name or spec.unit.name}'.")
    if row["delivery_center"]:
        spec.company = lk.company(row["delivery_center"])
        if spec.company is None:
            errors.append(f"Delivery center '{row['delivery_center']}' not found (or the name is not unique).")
    elif spec.unit is not None:
        company_id = employer_company_for(db, None, spec.unit.id)
        spec.company = next((c for c in lk.companies if c.id == company_id), None)
        if spec.company is None:
            errors.append("delivery_center is required: the business unit runs in more than one company (or none).")

    country_text = row["country"] or (spec.company.country if spec.company is not None else None)
    spec.country = policy.country_code(country_text) if country_text else None
    if spec.country is None:
        errors.append(f"Country '{country_text or ''}' is not one we hire in: set country (e.g. IN, US) "
                      "or a delivery center whose country is configured.")

    employment_type = (row["employment_type"] or "FULLTIME").upper()
    if employment_type not in EMPLOYMENT_TYPE_TO_MODEL:
        errors.append(f"employment_type must be FULLTIME or CONTRACT, got '{row['employment_type']}'.")
    elif spec.country is not None and employment_type not in policy.accepted_types(spec.country):
        errors.append(f"{policy.label(employment_type, spec.country)} is not accepted in {spec.country}.")
    else:
        spec.employment_type = EMPLOYMENT_TYPE_TO_MODEL[employment_type]

    spec.joining_date = _date(row["joining_date"], "joining_date", errors)
    spec.billable = _flag(row["billable"], "billable", True, errors)
    spec.existing_staff = _flag(row["existing_staff"], "existing_staff", True, errors)
    spec.core_certified = _flag(row["core_certified"], "core_certified", False, errors)
    if spec.core_certified:
        from app.services.bu_leadership import led_business_units

        if not spec.existing_staff:
            errors.append("core_certified needs existing_staff=yes (the Buddy Program comes first).")
        if spec.unit is not None and spec.unit.id not in led_business_units(db, lk.uploader):
            errors.append("Only a leader of this business unit (its Partner or a BU Head) can import someone "
                          "as Core-certified; leave core_certified=no and approve it on Core certification.")

    salary = _money_cents(row["monthly_salary"], "monthly_salary", errors)
    currency = (row["salary_currency"] or "USD").upper()
    if currency == "USD":
        spec.salary_cents = salary
    elif currency == "INR":
        if not settings.FX_INR_PER_USD:
            errors.append("salary_currency INR needs FX_INR_PER_USD to be configured.")
        elif salary is not None:
            spec.salary_cents = round(salary / settings.FX_INR_PER_USD)
    else:
        errors.append(f"salary_currency must be USD or INR, got '{row['salary_currency']}'.")
    spec.bill_rate_cents = _money_cents(row["bill_rate_usd_hour"], "bill_rate_usd_hour", errors)

    if row["work_location"]:
        if row["work_location"].upper() not in WORK_LOCATIONS:
            errors.append(f"work_location must be one of {', '.join(WORK_LOCATIONS)}.")
        else:
            spec.work_location = row["work_location"].upper()
    if row["skills"]:
        spec.skills = [s.strip() for s in row["skills"].replace(";", ",").split(",") if s.strip()]

    if row["role_template"]:
        template = lk.template(row["role_template"])
        if template is None:
            errors.append(f"Role template '{row['role_template']}' not found (or the name is not unique).")
        else:
            from app.services.role_template_permission_service import validate_addon_template

            try:
                spec.role_template = validate_addon_template(db, template.id, lk.tenant_id)
            except ValueError as exc:
                errors.append(str(exc))
    if row["manager_email"]:
        spec.manager = db.query(Users).filter(func.lower(Users.UserEmail) == row["manager_email"].lower(),
                                              Users.tenant_id == lk.tenant_id).first()
        manager_email = row["manager_email"].strip().lower()
        if manager_email == (row["email"] or "").strip().lower():
            errors.append("An employee cannot be their own manager.")
        elif spec.manager is None and manager_email in lk.file_rows and not lk.applying:
            spec.manager_in_file = manager_email
        elif spec.manager is None and manager_email in lk.file_rows:
            errors.append(f"Manager '{row['manager_email']}' is in this file but their row was not applied.")
        elif spec.manager is None:
            errors.append(f"Manager '{row['manager_email']}' has no login in this company.")

    spec.bench_since = _date(row["bench_since"], "bench_since", errors)
    if spec.bench_since and spec.joining_date and spec.bench_since < spec.joining_date:
        errors.append("bench_since is before the joining date.")
    if spec.bench_since and spec.bench_since > date.today():
        errors.append("bench_since is in the future.")
    _resolve_allocation(lk, row, spec)
    return spec


def _resolve_allocation(lk: _Lookups, row: Dict[str, str], spec: Spec) -> None:
    from app.api.v1.endpoints.allocations import _visible_demands
    from app.core import authority
    from app.models.demand import Demand
    from app.models.project import Project

    errors = spec.errors
    wants = row["allocation_job_id"] or row["allocation_project"]
    if not wants:
        for column in ("allocation_pct", "allocation_start_date", "allocation_end_date"):
            if row[column]:
                errors.append(f"{column} needs allocation_job_id or allocation_project.")
        return
    if not authority.has_permission(lk.db, lk.uploader, "allocations.create"):
        errors.append("You cannot allocate employees (allocations create permission); leave the allocation columns blank.")
        return
    jobs = _visible_demands(lk.db, lk.uploader)
    if row["allocation_job_id"]:
        spec.job = jobs.filter(Demand.jobID == row["allocation_job_id"]).first()
        if spec.job is None:
            errors.append(f"Job '{row['allocation_job_id']}' is not an open client job you can see.")
    else:
        project_ids = [p.id for p in lk.db.query(Project).filter(
            Project.tenant_id == lk.tenant_id, func.lower(Project.name) == row["allocation_project"].lower())]
        candidates = jobs.filter(Demand.project_id.in_(project_ids or [""])).all()
        if len(candidates) != 1:
            errors.append(f"Project '{row['allocation_project']}' has {len(candidates)} open jobs you can see; "
                          "give allocation_job_id instead.")
        else:
            spec.job = candidates[0]
    pct = row["allocation_pct"] or "100"
    try:
        spec.allocation_pct = float(pct)
        if not 0 < spec.allocation_pct <= 100:
            raise ValueError
    except ValueError:
        errors.append(f"allocation_pct must be a number from 1 to 100, got '{pct}'.")
    spec.allocation_start = _date(row["allocation_start_date"], "allocation_start_date", errors) or spec.joining_date
    spec.allocation_end = _date(row["allocation_end_date"], "allocation_end_date", errors)
    if spec.allocation_start and spec.joining_date and spec.allocation_start < spec.joining_date:
        errors.append("allocation_start_date is before the joining date.")
    if spec.allocation_end and spec.allocation_start and spec.allocation_end < spec.allocation_start:
        errors.append("allocation_end_date is before allocation_start_date.")
    if not spec.billable:
        errors.append("A non-billable employee is not allocated to a client job; set billable=yes or drop the allocation.")
    if spec.job is not None:
        from app.services.deployment_readiness_service import CORE, job_line

        if not spec.existing_staff:
            errors.append("Allocation needs existing_staff=yes: a new hire's Buddy Program must be graduated first.")
        if job_line(lk.db, spec.job) == CORE and not spec.core_certified:
            errors.append("This is a Core (direct client) job: the employee must be Core-certified.")
    if spec.bench_since:
        errors.append("bench_since is for employees not on a project; drop it or the allocation.")


# --------------------------------------------------------------------------- planning

def _display(spec: Spec) -> Dict[str, Any]:
    return {
        "business_unit": (spec.unit.display_name or spec.unit.name) if spec.unit else None,
        "business_unit_id": spec.unit.id if spec.unit else None,
        "delivery_center": spec.company.name if spec.company else None,
        "country": spec.country,
        "role_template": (spec.role_template.display_name or spec.role_template.name) if spec.role_template else "Employee (default)",
        "manager": spec.manager.UserEmail if spec.manager else None,
        "billable": spec.billable,
        "existing_staff": spec.existing_staff,
        "core_certified": spec.core_certified,
        "allocation": ({"job_id": spec.job.jobID, "job_title": spec.job.jobTitle, "pct": spec.allocation_pct,
                        "start_date": spec.allocation_start.isoformat() if spec.allocation_start else None}
                       if spec.job is not None else None),
    }


def _employee_fields(spec: Spec) -> Dict[str, Any]:
    """The Employee columns a row sets (None = the row leaves it unchanged on an update)."""
    return {
        "first_name": spec.first_name, "last_name": spec.last_name, "tenant_employee_id": spec.employee_code,
        "bu_id": spec.unit.id if spec.unit else None, "company_id": spec.company.id if spec.company else None,
        "current_title": spec.designation, "employment_type": spec.employment_type,
        "base_salary_usd_cents": spec.salary_cents, "billing_rate_usd_cents": spec.bill_rate_cents,
        "work_location": spec.work_location, "is_billable": spec.billable,
        "current_skills": json.dumps(spec.skills) if spec.skills is not None else None,
        "joining_date": spec.joining_date,
    }


def _changes(employee: Employee, spec: Spec) -> List[str]:
    changes = []
    for column, value in _employee_fields(spec).items():
        if value is not None and getattr(employee, column) != value:
            changes.append(f"{column}: {getattr(employee, column)!r} -> {value!r}")
    if spec.existing_staff and employee.buddy_program_status != "GRADUATED":
        changes.append(f"buddy_program_status: {employee.buddy_program_status} -> GRADUATED (existing staff)")
    if spec.core_certified and not employee.core_certified:
        changes.append("core_certified: False -> True")
    return changes


def _plan_one(lk: _Lookups, number: int, row: Dict[str, str], seen: Dict[str, int]) -> Tuple[Dict, Spec]:
    db = lk.db
    spec = _resolve(lk, row)
    plan: Dict[str, Any] = {"row": number, "email": spec.email,
                            "name": f"{spec.first_name} {spec.last_name}".strip(), **_display(spec)}
    if spec.email in seen:
        spec.errors.append(f"Same email as row {seen[spec.email]}.")
    seen.setdefault(spec.email, number)

    employee = db.query(Employee).filter(Employee.tenant_id == lk.tenant_id,
                                         func.lower(Employee.email) == spec.email).first() if spec.email else None
    user = db.query(Users).filter(func.lower(Users.UserEmail) == spec.email).first() if spec.email else None
    if user is not None and user.tenant_id != lk.tenant_id:
        spec.errors.append("This email has a login in another company.")
    if user is not None:
        linked = db.query(Employee).filter(Employee.wros_user_id == user.UserID).first()
        if linked is not None and (employee is None or linked.id != employee.id):
            spec.errors.append(f"The login {spec.email} already belongs to employee {linked.email}.")

    if employee is None:
        plan["action"] = ACTION_LINK if user is not None else ACTION_CREATE
        plan["login"] = "link existing login" if user is not None else "create login + activation email"
        if spec.joining_date and spec.joining_date > date.today():
            plan["status_after"] = "PRE_JOINING"
        else:
            plan["status_after"] = "ALLOCATED" if spec.job is not None else ("BENCH" if spec.billable else "ACTIVE")
        plan["changes"] = []
    else:
        from app.core.data_scope import visible_bu_ids

        scope = visible_bu_ids(db, lk.uploader)
        if scope is not None and employee.bu_id is not None and employee.bu_id not in scope:
            spec.errors.append("This employee belongs to a business unit outside your scope.")
        if employee.wros_user_id and user is not None and employee.wros_user_id != user.UserID:
            spec.errors.append("This employee is linked to a different login.")
        plan["employee_id"] = employee.id
        changes = _changes(employee, spec)
        login = "keep linked login"
        if not employee.wros_user_id:
            login = "link existing login" if user is not None else "create login + activation email"
            changes.append(f"login: {login}")
        allocation_needed = spec.job is not None and not db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.demand_id == spec.job.jobID,
            EmployeeAllocation.status == "ACTIVE").first()
        if allocation_needed:
            changes.append(f"allocate to {spec.job.jobTitle}")
        plan["changes"] = changes
        plan["action"] = ACTION_UPDATE if changes else ACTION_UNCHANGED
        plan["login"] = login
        plan["status_after"] = "ALLOCATED" if allocation_needed else employee.status
    _check_reporting_line(lk, spec, user, employee, plan)
    plan["errors"] = list(spec.errors)
    return plan, spec


def _seat_level(db: Session, tenant_id: int, user: Optional[Users], designation: Optional[str]) -> Optional[int]:
    """The org level a person sits (or would sit) at: their seat's, else their designation's org role."""
    from app.models.org_structure import OrgNode
    from app.services.org_roles_service import role_for_title

    if user is not None and user.org_node_id:
        node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()
        if node is not None:
            return node.hierarchy_level
    role = role_for_title(db, tenant_id, designation)
    return role.hierarchy_level if role else None


def _check_reporting_line(lk: _Lookups, spec: Spec, user: Optional[Users], employee: Optional[Employee],
                          plan: Dict) -> None:
    """A row naming a manager puts the employee's seat under the manager's seat, so before
    anything is written: the employee needs a level (seat or org-role designation), the manager
    needs a seat (or is placed by another row of this file), and the levels must be a reporting
    line the org chart accepts (OrgHierarchyValidator: one or two levels up)."""
    from app.models.org_structure import OrgNode
    from app.services.org_hierarchy_validator import get_valid_parent_levels
    from app.services.org_structure_service import manager_user_for

    if spec.manager is None and spec.manager_in_file is None:
        return
    db = lk.db
    level = _seat_level(db, lk.tenant_id, user, spec.designation)
    if level is None:
        spec.errors.append(f"Designation '{spec.designation or ''}' is not an org role (Manage Roles), so this employee "
                           "can't be seated under their manager in the org chart.")
        return
    if spec.manager is not None:
        if employee is not None:
            current = manager_user_for(db, employee)
            if current is None or current.UserID != spec.manager.UserID:
                plan["changes"].append(f"manager: {current.UserEmail if current else None} -> {spec.manager.UserEmail}")
                if plan.get("action") == ACTION_UNCHANGED:
                    plan["action"] = ACTION_UPDATE
        node = db.query(OrgNode).filter(OrgNode.id == spec.manager.org_node_id).first() \
            if spec.manager.org_node_id else None
        if node is None:
            spec.errors.append(f"Manager {spec.manager.UserEmail} has no seat in the org chart: place them under "
                               "Organizational Hierarchy first, or include them as a row in this file.")
            return
        manager_level = node.hierarchy_level
    else:
        manager_row = lk.file_rows[spec.manager_in_file]
        manager_level = _seat_level(db, lk.tenant_id, None, manager_row.get("designation"))
        if manager_level is None:
            spec.errors.append(f"Manager {spec.manager_in_file}'s designation in this file is not an org role, so "
                               "they can't be seated for this employee to report to.")
            return
    if manager_level not in get_valid_parent_levels(level):
        spec.errors.append(f"A level {level} employee can't report to a level {manager_level} manager: the org chart "
                           f"allows levels {get_valid_parent_levels(level)}.")


def plan_rows(db: Session, uploader: Users, rows: List[Dict[str, str]]) -> List[Tuple[Dict, Spec]]:
    lk = _Lookups(db, uploader)
    lk.file_rows = _file_rows(rows)
    seen: Dict[str, int] = {}
    return [_plan_one(lk, number, row, seen) for number, row in enumerate(rows, start=2)]  # row 1 is the header


def _file_rows(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {(row.get("email") or "").strip().lower(): row for row in rows if (row.get("email") or "").strip()}


def _manager_first_order(rows: List[Dict[str, str]]) -> List[int]:
    """Row indexes with every manager listed in the file before the people who report to them
    (otherwise file order). A reporting loop inside the file keeps file order; those rows then
    fail on the missing manager seat."""
    index = {(row.get("email") or "").strip().lower(): i for i, row in enumerate(rows)}
    order, state = [], {}

    def visit(i: int) -> None:
        if state.get(i) == "done":
            return
        if state.get(i) == "visiting":
            return  # loop: leave it to the row's own checks
        state[i] = "visiting"
        boss = index.get((rows[i].get("manager_email") or "").strip().lower())
        if boss is not None and boss != i:
            visit(boss)
        state[i] = "done"
        order.append(i)

    for i in range(len(rows)):
        visit(i)
    return order


def _counts(plans: List[Dict]) -> Dict[str, int]:
    counts = {"total": len(plans), "error": 0, ACTION_CREATE: 0, ACTION_LINK: 0, ACTION_UPDATE: 0, ACTION_UNCHANGED: 0}
    for plan in plans:
        if plan["errors"]:
            counts["error"] += 1
        else:
            counts[plan["action"]] += 1
    return counts


def dry_run(db: Session, uploader: Users, content: bytes, *, file_name: Optional[str] = None) -> Dict:
    """Preview: what each row would do. Stores the parsed rows under the token; changes nothing else."""
    rows = parse_csv(content)
    plans = [plan for plan, _ in plan_rows(db, uploader, rows)]
    db.rollback()  # resolution only read; make sure nothing it touched is pending
    token = token_for(uploader.tenant_id, uploader.UserID, rows)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.EMPLOYEE_IMPORT_TOKEN_TTL_MINUTES)
    batch = db.get(EmployeeImportBatch, token)
    if batch is None:
        db.add(EmployeeImportBatch(id=token, tenant_id=uploader.tenant_id, uploaded_by=uploader.UserID,
                                   file_name=file_name, rows=rows, row_count=len(rows), expires_at=expires_at))
    else:
        batch.expires_at = expires_at
    db.commit()
    logger.info(f"[EmployeeImport] dry run by {uploader.UserID}: {_counts(plans)} token={token[:12]}")
    return {"token": token, "expires_at": expires_at.isoformat(), "counts": _counts(plans), "rows": plans}


# --------------------------------------------------------------------------- applying

def _graduate_existing(db: Session, employee: Employee, uploader: Users) -> None:
    from app.core.audit import write_audit_log
    from app.models.buddy_program import BuddyProgramRecord

    today = date.today()
    note = f"Existing employee imported {today.isoformat()} by {uploader.UserName or uploader.UserEmail} ({uploader.UserID})"
    db.add(BuddyProgramRecord(tenant_id=employee.tenant_id, employee_id=employee.id,
                              buddy_engineer_user_id=uploader.UserID, program_start_date=employee.joining_date,
                              expected_end_date=today, actual_end_date=today, status="GRADUATED",
                              bu_head_decision_notes=f"[GRADUATE] {note}"))
    previous = employee.buddy_program_status
    employee.buddy_program_status = "GRADUATED"
    employee.buddy_program_start_date = employee.buddy_program_start_date or employee.joining_date
    employee.buddy_program_graduation_date = today
    write_audit_log(db, entity_type="employee", entity_id=employee.id, action="buddy_graduated_on_import",
                    tenant_id=employee.tenant_id, user_id=uploader.UserID,
                    old_value=json.dumps({"buddy_program_status": previous}),
                    new_value=json.dumps({"buddy_program_status": "GRADUATED", "reason": note}))


def _certify_core(db: Session, employee: Employee, uploader: Users) -> None:
    from app.core.audit import write_audit_log
    from app.models.core_certification import CoreCertificationRequest

    now = datetime.utcnow()
    db.add(CoreCertificationRequest(tenant_id=employee.tenant_id, employee_id=employee.id,
                                    bu_head_user_id=uploader.UserID, status="APPROVED", billable_days=0,
                                    decided_by_user_id=uploader.UserID, decided_at=now))
    employee.core_certified, employee.core_certified_date = True, now.date()
    write_audit_log(db, entity_type="employee", entity_id=employee.id, action="core_certified_on_import",
                    tenant_id=employee.tenant_id, user_id=uploader.UserID,
                    new_value=json.dumps({"core_certified": True,
                                          "reason": f"Existing Core-certified employee imported by {uploader.UserID}"}))


def _login_for(db: Session, spec: Spec, uploader: Users) -> Tuple[Users, bool]:
    """(login, created). An existing login with the email is linked as it is (its role template
    and seat are not touched); otherwise one is created the way candidate conversion does."""
    from app.services.employee_conversion_service import EmployeeConversionService
    from app.services.org_roles_service import role_for_title

    user = db.query(Users).filter(func.lower(Users.UserEmail) == spec.email).first()
    if user is not None:
        return user, False
    user = EmployeeConversionService.create_employee_account(
        db, employee_name=f"{spec.first_name} {spec.last_name}".strip(), employee_email=spec.email,
        business_unit_id=spec.unit.id, tenant_id=uploader.tenant_id,
        role_ids=[spec.role_template.id] if spec.role_template else None)
    role = role_for_title(db, uploader.tenant_id, spec.designation)
    user.job_title = role.name if role else spec.designation
    user.location_id = spec.company.id if spec.company else None
    db.flush()
    return user, True


def _place_login(db: Session, user: Users, spec: Spec) -> None:
    from app.services.employee_conversion_service import place_new_hire
    from app.services.org_roles_service import role_for_title

    role = role_for_title(db, user.tenant_id, spec.designation)
    if spec.manager is not None:
        _seat_under_manager(db, user, spec)
        return
    place_new_hire(db, user, role, None, spec.unit.id, spec.company.id if spec.company else None, False)


def _seat_under_manager(db: Session, user: Users, spec: Spec) -> None:
    """The row's manager is recorded in the org chart: the login's seat goes under the manager's
    (the employee row follows, org_structure_service._sync_employee_reporting). A refusal fails the row."""
    from app.services.org_roles_service import role_for_title
    from app.services.org_structure_service import manager_user_for, place_under_manager

    employee = db.query(Employee).filter(Employee.wros_user_id == user.UserID).first()
    current = manager_user_for(db, employee) if employee is not None else None
    if current is not None and current.UserID == spec.manager.UserID and user.org_node_id:
        return
    role = role_for_title(db, user.tenant_id, spec.designation)
    place_under_manager(db, user, spec.manager, role_level=role.hierarchy_level if role else None,
                        company_id=spec.company.id if spec.company else None)


def _allocate(db: Session, employee: Employee, spec: Spec, uploader: Users) -> None:
    from app.services.employee_allocation_service import allocate_employee_to_project

    allocate_employee_to_project(
        db, tenant_id=employee.tenant_id, employee=employee, demand=spec.job, start_date=spec.allocation_start,
        end_date=spec.allocation_end, utilization_pct=spec.allocation_pct, changed_by=uploader.UserID,
        billing_rate_usd_cents=spec.bill_rate_cents, allow_concurrent=True)


def _apply_create(db: Session, spec: Spec, uploader: Users) -> Tuple[Employee, Users, bool]:
    from app.services.employee_service import create_employee_profile, place_unallocated_joiner, transition_employee_status

    user, created = _login_for(db, spec, uploader)
    fields = {k: v for k, v in _employee_fields(spec).items()
              if v is not None and k not in ("first_name", "last_name", "joining_date")}
    employee = create_employee_profile(
        db, tenant_id=uploader.tenant_id, first_name=spec.first_name, last_name=spec.last_name, email=spec.email,
        joining_date=spec.joining_date, changed_by=uploader.UserID, wros_user_id=user.UserID, **fields)
    if created:
        _place_login(db, user, spec)
    elif spec.manager is not None:
        _seat_under_manager(db, user, spec)
    if spec.existing_staff:
        _graduate_existing(db, employee, uploader)
    if spec.core_certified:
        _certify_core(db, employee, uploader)
    if spec.joining_date <= date.today():
        transition_employee_status(db, employee, "ACTIVE", reason="Imported: joined", changed_by=uploader.UserID)
        if spec.job is not None:
            _allocate(db, employee, spec, uploader)
        else:
            place_unallocated_joiner(db, employee, changed_by=uploader.UserID, bench_since=spec.bench_since)
    elif spec.job is not None:
        _allocate(db, employee, spec, uploader)  # placed before joining: ALLOCATED when the joiner job runs
    from app.services.bench_service import sync_billing_classification

    sync_billing_classification(db, employee)
    return employee, user, created


def _apply_update(db: Session, employee: Employee, spec: Spec, uploader: Users) -> Tuple[Optional[Users], bool]:
    from app.services.bench_service import set_billable, sync_billing_classification

    for column, value in _employee_fields(spec).items():
        if value is not None and column != "is_billable":
            setattr(employee, column, value)
    user, created = None, False
    if not employee.wros_user_id:
        user, created = _login_for(db, spec, uploader)
        employee.wros_user_id = user.UserID
        if created:
            _place_login(db, user, spec)
    if spec.manager is not None and not created:
        db.flush()
        _seat_under_manager(db, db.query(Users).filter(Users.UserID == employee.wros_user_id).first(), spec)
    if spec.existing_staff and employee.buddy_program_status != "GRADUATED":
        _graduate_existing(db, employee, uploader)
    if spec.core_certified and not employee.core_certified:
        _certify_core(db, employee, uploader)
    set_billable(db, employee, spec.billable, changed_by=uploader.UserID)
    if spec.job is not None and not db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.demand_id == spec.job.jobID,
            EmployeeAllocation.status == "ACTIVE").first():
        _allocate(db, employee, spec, uploader)
    sync_billing_classification(db, employee)
    db.add(employee)
    return user, created


def _announce_new_employee(db: Session, employee_id: str) -> None:
    """employee_created_flash for Flash. The employee is already saved: a queue outage is logged
    and the import still stands (fire-and-forget, CLAUDE.md fail-fast exception 3)."""
    from app.services.message_queue_service import MessageQueueService

    employee = db.get(Employee, employee_id)
    try:
        MessageQueueService.enqueue(
            task_name="employee_created_flash", task_id=f"employee_created:{employee.id}", tenant_id=employee.tenant_id,
            data={"employee_id": employee.id, "employee_email": employee.email,
                  "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
                  "created_at": datetime.utcnow().isoformat()})
    except Exception as exc:
        logger.error(f"[EmployeeImport] employee {employee.id} saved; employee_created_flash not queued: {exc}",
                     exc_info=True)


def apply_rows(db: Session, uploader: Users, rows: List[Dict[str, str]], *, only_create: bool = False) -> Dict:
    """Apply each error-free row in its own transaction; activation emails are queued after commit."""
    from app.core.audit import write_audit_log
    from app.services.account_activation_service import queue_account_email

    results, new_logins = [], []
    lk = _Lookups(db, uploader)
    lk.file_rows, lk.applying = _file_rows(rows), True
    seen: Dict[str, int] = {}
    for position in _manager_first_order(rows):
        # planned only now, after every earlier row committed: a manager added above is a login with a seat
        plan, spec = _plan_one(lk, position + 2, rows[position], seen)
        result = {"row": plan["row"], "email": plan["email"], "name": plan["name"], "action": plan["action"],
                  "employee_id": plan.get("employee_id"), "user_id": None, "activation_email_queued": False}
        if only_create and plan["action"] in (ACTION_UPDATE, ACTION_UNCHANGED) and not plan["errors"]:
            plan["errors"] = [f"An employee with email {spec.email} already exists."]
        if plan["errors"]:
            results.append({**result, "status": "skipped", "errors": plan["errors"]})
            continue
        if plan["action"] == ACTION_UNCHANGED:
            results.append({**result, "status": "unchanged", "errors": []})
            continue
        # every earlier row is committed, so a rollback here undoes this row only
        try:
            if plan["action"] in (ACTION_CREATE, ACTION_LINK):
                employee, user, created = _apply_create(db, spec, uploader)
            else:
                employee = db.get(Employee, plan["employee_id"])
                user, created = _apply_update(db, employee, spec, uploader)
            write_audit_log(db, entity_type="employee", entity_id=employee.id, action=f"import_{plan['action']}",
                            tenant_id=uploader.tenant_id, user_id=uploader.UserID,
                            new_value=json.dumps({"row": plan["row"], "changes": plan["changes"]}))
            db.commit()
        except Exception as exc:  # one bad row never stops the others; its own changes roll back
            db.rollback()
            logger.warning(f"[EmployeeImport] row {plan['row']} ({spec.email}) failed: {exc}", exc_info=True)
            results.append({**result, "status": "failed", "errors": [str(exc)]})
            continue
        if created:
            new_logins.append((len(results), user))
        results.append({**result, "status": "applied", "employee_id": employee.id,
                        "user_id": employee.wros_user_id, "errors": []})
    for index, user in new_logins:  # after commit: the email refers to saved rows
        results[index]["activation_email_queued"] = True
        queue_account_email(user, "ACTIVATE", once_key="employee-import")
    for r in results:
        if r["status"] == "applied" and r["action"] in (ACTION_CREATE, ACTION_LINK):
            _announce_new_employee(db, r["employee_id"])
    counts = {"total": len(results)}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    logger.info(f"[EmployeeImport] applied by {uploader.UserID}: {counts}")
    return {"counts": counts, "rows": sorted(results, key=lambda r: r["row"])}


def apply(db: Session, uploader: Users, token: str, content: bytes) -> Dict:
    """Apply a dry-run token to the same file. 404 unknown/someone else's, 410 expired, 409 changed."""
    batch = db.get(EmployeeImportBatch, token)
    if batch is None or batch.uploaded_by != uploader.UserID or batch.tenant_id != uploader.tenant_id:
        raise ImportTokenError("Unknown import token: run the dry run first.", 404)
    if batch.expires_at < datetime.utcnow():
        raise ImportTokenError("This dry run has expired: run it again and review the preview.", 410)
    rows = parse_csv(content)
    if token_for(uploader.tenant_id, uploader.UserID, rows) != token:
        raise ImportTokenError("The file changed since the dry run: run the dry run again on this file.")
    outcome = apply_rows(db, uploader, rows)
    batch = db.get(EmployeeImportBatch, token)
    batch.applied_at, batch.results = datetime.utcnow(), outcome
    db.commit()
    return {"token": token, **outcome}


def row_from_request(db: Session, body) -> Dict[str, str]:
    """The Add employee form as one import row (ids where the form has pickers; the resolver
    accepts ids for business unit, delivery center and role template)."""
    manager_email = ""
    if body.reporting_manager_id:
        manager = db.query(Users).filter(Users.UserID == body.reporting_manager_id).first()
        if manager is None:
            raise ImportFileError(f"Reporting manager {body.reporting_manager_id} not found.")
        manager_email = manager.UserEmail
    employment_type = (body.employment_type or "FULLTIME").upper()
    employment_type = "FULLTIME" if employment_type in ("PERMANENT", "FIXED_TERM") else employment_type
    yes_no = lambda flag: "yes" if flag else "no"  # noqa: E731
    row = {c: "" for c in COLUMN_NAMES}
    row.update({
        "first_name": body.first_name.strip(), "last_name": body.last_name.strip(), "email": body.email.strip(),
        "employee_code": body.employee_code or "", "business_unit": str(body.business_unit_id),
        "delivery_center": body.company_id or "", "country": body.country or "",
        "joining_date": body.joining_date.isoformat(), "designation": body.current_title or "",
        "role_template": str(body.role_template_id) if body.role_template_id else "",
        "manager_email": manager_email, "employment_type": employment_type,
        "billable": yes_no(body.billable), "existing_staff": yes_no(body.existing_staff),
        "core_certified": yes_no(body.core_certified),
        "monthly_salary": f"{body.base_salary_usd_cents / 100:.2f}", "salary_currency": "USD",
        "bill_rate_usd_hour": f"{body.billing_rate_usd_cents / 100:.2f}" if body.billing_rate_usd_cents else "",
        "work_location": body.work_location or "", "skills": ", ".join(body.current_skills or []),
        "bench_since": body.bench_since.isoformat() if body.bench_since else "",
    })
    return row
