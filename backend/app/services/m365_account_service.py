"""Microsoft 365 accounts for employees (CEO 2026-11-27): "as we add employee it should create their
microsoft account and assign task to system admin to allocate licensing".

queue_provisioning(user)     -> after commit: one provision_m365_account message per new login with a
                                company mailbox (deterministic id, so a re-sent welcome never queues twice)
provision(db, user)          -> the queue handler's work: find the Microsoft account by the login email,
                                create it when missing, then make sure it has a license. A missing license
                                (or an account HRMS may not create) is one task for IT Admin (the system
                                admin function, app.services.asset_service.it_admin_owner).
run_license_check_job(db)    -> scheduled: closes those tasks itself once Microsoft shows the license, so
                                nobody has to mark them done; a leaver's task is cancelled.
mailbox_pending(db, user_id) -> the account or its license is still being set up: the welcome email waits
                                (it would bounce off a mailbox that does not exist yet).

The temporary Microsoft password is never stored, shown or emailed: IT Admin sets the first sign-in when
assigning the license (Microsoft 365 admin center), and Microsoft makes the person change it.
Needs the Graph application permission User.ReadWrite.All (admin consent) on the HRMS app.
"""
import logging
import re
import secrets
from datetime import datetime
from typing import Optional, Set
from urllib.parse import quote

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.task import Task
from app.models.user import Users

logger = logging.getLogger(__name__)

PROVISION_TASK = "provision_m365_account"
ACCOUNT_TASK_CATEGORY = "M365_ACCOUNT"  # HRMS could not create the account: IT Admin creates it
LICENSE_TASK_CATEGORY = "M365_LICENSE"  # the account exists without a license: IT Admin assigns one
TASK_CATEGORIES = (ACCOUNT_TASK_CATEGORY, LICENSE_TASK_CATEGORY)
OPEN_TASK_STATUSES = ("NEW", "IN_PROGRESS", "ON_HOLD")
GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_TIMEOUT_SECONDS = 15
ADMIN_CENTER_URL = "https://admin.microsoft.com/#/users"


class GraphError(RuntimeError):
    """Graph answered with an error. status 403/400 are answers (a task for IT Admin), 5xx retryable."""

    def __init__(self, status: int, message: str):
        super().__init__(f"Microsoft Graph {status}: {message}")
        self.status = status
        self.message = message


# --------------------------------------------------------------------------- whose mailbox

def company_mail_domains() -> Set[str]:
    """Company mailbox domains: OUTLOOK_REQUIRED_DOMAINS, blank = the HRMS mailbox's domain."""
    domains = {d.strip().lower() for d in (settings.OUTLOOK_REQUIRED_DOMAINS or "").split(",") if d.strip()}
    return domains or {settings.THUNDER_MAILBOX.split("@")[-1].lower()}


def is_company_mailbox(email: Optional[str]) -> bool:
    email = (email or "").strip().lower()
    return "@" in email and email.split("@")[-1] in company_mail_domains()


# --------------------------------------------------------------------------- Graph (application token)

class GraphUsers:
    """The few Graph user calls provisioning needs, with the app-only token."""

    def __init__(self, token: Optional[str] = None):
        if token is None:
            from app.core.graph_auth import get_graph_token

            token = get_graph_token()
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _call(self, method: str, path: str, json_body=None) -> Optional[dict]:
        try:
            response = requests.request(method, f"{GRAPH}{path}", headers=self._headers, json=json_body,
                                        timeout=GRAPH_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as exc:
            raise GraphError(503, f"Microsoft Graph unreachable: {exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            try:
                message = response.json().get("error", {}).get("message") or response.text
            except ValueError:
                message = response.text
            raise GraphError(response.status_code, (message or response.reason)[:300])
        return response.json() if response.content else {}

    def get_user(self, upn: str) -> Optional[dict]:
        return self._call("GET", f"/users/{quote(upn)}?$select=id,userPrincipalName,accountEnabled,assignedLicenses")

    def find_user(self, address: str) -> Optional[dict]:
        """The account whose sign-in name, mail or an alias (proxy address) is this address: existing staff whose
        sign-in name differs from their HRMS email are found, never given a second account."""
        account = self.get_user(address)
        if account is not None:
            return account
        safe = address.replace("'", "''")
        condition = f"mail eq '{safe}' or proxyAddresses/any(p:p eq 'smtp:{safe}')"
        path = ("/users?$count=true&$select=id,userPrincipalName,accountEnabled,assignedLicenses&$filter="
                + quote(condition))
        saved = dict(self._headers)
        self._headers["ConsistencyLevel"] = "eventual"  # Graph needs it for proxyAddresses/any with $count
        try:
            found = (self._call("GET", path) or {}).get("value") or []
        finally:
            self._headers = saved
        return found[0] if found else None

    def create_user(self, body: dict) -> dict:
        return self._call("POST", "/users", body) or {}


def graph_configured() -> bool:
    from app.core.graph_auth import GraphServiceAuth

    return GraphServiceAuth.is_configured()


# --------------------------------------------------------------------------- queueing

def queue_provisioning(user: Users) -> bool:
    """Call after commit. Once ever per login (the message id is the user's)."""
    if not user or not user.UserID or not is_company_mailbox(user.UserEmail):
        return False
    from app.services.thunder_mail.cadence_service import enqueue_once

    return enqueue_once(PROVISION_TASK, f"m365-account-{user.UserID}", {"user_id": user.UserID}, user.tenant_id)


# --------------------------------------------------------------------------- tasks for IT Admin

def task_link(db: Session, user: Users) -> str:
    """In-app path for the person: their employee profile, else the users screen."""
    from app.models.employee import Employee

    employee = db.query(Employee.id).filter(Employee.wros_user_id == user.UserID).first()
    return f"/employees/{employee[0]}" if employee else f"/admin/users-access-control/users?user={user.UserID}"


def _open_tasks(db: Session, user_id: str, categories=TASK_CATEGORIES):
    return db.query(Task).filter(Task.category.in_(categories), Task.subcategory == user_id,
                                 Task.status.in_(OPEN_TASK_STATUSES))


def _open_task(db: Session, user: Users, category: str, title: str, description: str) -> Task:
    """One open task per person and category, refreshed when it already exists."""
    from app.services.asset_service import it_admin_owner, owner_function

    task = _open_tasks(db, user.UserID, (category,)).order_by(Task.id).first()
    if task is not None:
        task.title, task.description = title[:300], description
        return task
    owner = it_admin_owner(db, user.tenant_id)
    function = owner_function(db, user.tenant_id)
    task = Task(title=title[:300], description=description, priority="HIGH", tenant_id=user.tenant_id,
                category=category, subcategory=user.UserID, link=task_link(db, user), assigned_to_user_id=owner,
                department_id=function.id if function is not None else None,
                visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if owner else "ORG_WIDE")
    db.add(task)
    db.flush()
    db.info.setdefault("m365_new_tasks", []).append(task.id)
    if owner is None:
        logger.error(f"[M365] task #{task.id} ({category}) has no owner: nobody is in the "
                     f"{settings.ASSET_OWNER_FUNCTION} function and no CEO is designated")
    return task


def _close_tasks(db: Session, user_id: str, categories=TASK_CATEGORIES, *, done: bool = True) -> int:
    values = {Task.status: "COMPLETED", Task.completed_at: datetime.utcnow()} if done else {Task.status: "CANCELLED"}
    return _open_tasks(db, user_id, categories).update(values, synchronize_session=False)


def notify_new_tasks(db: Session) -> None:
    """Call after commit: email the owner of each task opened by this change. A failed email never undoes
    the task (it is in My Tasks either way)."""
    from app.services.task_notification_service import notify_task_assigned

    for task_id in db.info.pop("m365_new_tasks", []):
        try:
            task = db.get(Task, task_id)
            if task is not None:
                notify_task_assigned(db, task)
        except Exception as exc:
            logger.error(f"[M365] task #{task_id} notice not sent: {exc}", exc_info=True)


def _license_task(db: Session, user: Users, usage_location: Optional[str]) -> Task:
    where = "" if usage_location else (" Set their usage location first (HRMS could not tell their country "
                                       "from their company), or Microsoft refuses the license.")
    return _open_task(
        db, user, LICENSE_TASK_CATEGORY, f"Assign a Microsoft 365 license to {user.UserName or user.UserEmail}",
        f"{user.UserName or user.UserEmail} ({user.UserEmail}) has a Microsoft account but no license, so they "
        f"have no mailbox or Office yet.{where} In the Microsoft 365 admin center ({ADMIN_CENTER_URL}) open "
        f"{user.UserEmail}: Licenses and apps, assign the license; then Reset password and give them their first "
        f"sign-in (Microsoft asks them to change it). HRMS closes this task itself once Microsoft shows the "
        f"license, and their welcome email goes out then.")


# --------------------------------------------------------------------------- provisioning

def _usage_location(db: Session, user: Users) -> Optional[str]:
    """ISO country of the person's company (Microsoft needs it to license them), else None."""
    from app.models.location import Location
    from app.services.employment_type_policy import country_code

    company = db.query(Location).filter(Location.id == user.location_id).first() if user.location_id else None
    return country_code(company.country) if company is not None else None


def _new_account(user: Users, usage_location: Optional[str]) -> dict:
    email = user.UserEmail.strip().lower()
    nickname = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0]) or f"user{user.UserID[-6:]}"
    parts = (user.UserName or "").split()
    body = {
        "accountEnabled": True,
        "displayName": user.UserName or email,
        "mailNickname": nickname[:64],
        "userPrincipalName": email,
        # thrown away: IT Admin sets the first sign-in with the license (module docstring)
        "passwordProfile": {"forceChangePasswordNextSignIn": True,
                            "password": secrets.token_urlsafe(18) + "aA1!"},
    }
    if parts:
        body["givenName"] = parts[0][:64]
        if len(parts) > 1:
            body["surname"] = " ".join(parts[1:])[:64]
    if user.job_title:
        body["jobTitle"] = user.job_title[:128]
    if usage_location:
        body["usageLocation"] = usage_location
    return body


def _account_task(db: Session, user: Users, why: str, status: Optional[int] = None) -> dict:
    """IT Admin makes sure the account exists (HRMS could not). The welcome email is not held for it: HRMS does
    not know the mailbox is missing, only that it could not check (mailbox_pending)."""
    _open_task(db, user, ACCOUNT_TASK_CATEGORY,
               f"Check the Microsoft 365 account of {user.UserName or user.UserEmail}",
               f"{why}. Make sure {user.UserEmail} exists in the Microsoft 365 admin center ({ADMIN_CENTER_URL}) with "
               f"a license, and give {user.UserName or user.UserEmail} their first sign-in"
               + (" (or grant the HRMS app the Microsoft Graph permission User.ReadWrite.All so HRMS does this "
                  "itself)" if status in (401, 403) else "")
               + ". HRMS closes this task itself once Microsoft shows the licensed account.")
    logger.warning(f"[M365] {user.UserID}: {why}")
    return {"status": "account_task", "error": why}


def provision(db: Session, user: Users, graph: Optional[GraphUsers] = None) -> dict:
    """Make sure the person has a licensed Microsoft account. The caller commits, then notify_new_tasks().
    Raises GraphError for a status Microsoft may answer differently later (5xx, throttling)."""
    if not is_company_mailbox(user.UserEmail):
        return {"status": "not_company_mailbox"}
    if user.terminated_at is not None:
        _close_tasks(db, user.UserID, done=False)
        return {"status": "left"}
    graph = graph or GraphUsers()
    usage_location = _usage_location(db, user)
    try:
        account = graph.find_user(user.UserEmail)
    except GraphError as exc:
        if exc.status >= 500 or exc.status == 429:
            raise
        # 401/403/400: HRMS may not read Microsoft accounts; IT Admin checks it, the welcome is not held for it
        return _account_task(db, user, f"HRMS could not look up the Microsoft account: {exc.message}", exc.status)
    created = False
    if account is None:
        try:
            account = graph.create_user(_new_account(user, usage_location))
            created = True
            logger.info(f"[M365] created Microsoft account for {user.UserID} ({user.UserEmail})")
        except GraphError as exc:
            if exc.status >= 500 or exc.status == 429:
                raise
            # 403: HRMS lacks User.ReadWrite.All; 400: e.g. the domain is not verified in Microsoft 365
            return _account_task(db, user, f"HRMS could not create the Microsoft account: {exc.message}", exc.status)
    _close_tasks(db, user.UserID, (ACCOUNT_TASK_CATEGORY,))
    if account.get("assignedLicenses"):
        _close_tasks(db, user.UserID, (LICENSE_TASK_CATEGORY,))
        return {"status": "licensed", "created": created}
    _license_task(db, user, usage_location)
    return {"status": "license_task", "created": created}


def run_license_check_job(db: Session) -> dict:
    """Re-check everyone with an open account/license task; close the ones Microsoft now shows licensed."""
    if not graph_configured():
        return {"checked": 0, "closed": 0, "skipped": "Microsoft Graph not configured"}
    user_ids = {row[0] for row in db.query(Task.subcategory).filter(
        Task.category.in_(TASK_CATEGORIES), Task.status.in_(OPEN_TASK_STATUSES), Task.subcategory.isnot(None))}
    graph = GraphUsers()
    checked = closed = 0
    for user_id in sorted(user_ids):
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is None:
            _close_tasks(db, user_id, done=False)
            continue
        checked += 1
        try:
            result = provision(db, user, graph)
        except GraphError as exc:
            logger.error(f"[M365] license check for {user_id} failed: {exc}")
            db.rollback()
            continue
        closed += result.get("status") in ("licensed", "left")
        db.commit()
        notify_new_tasks(db)
    return {"checked": checked, "closed": closed}


def mailbox_pending(db: Session, user_id: str) -> bool:
    """HRMS knows the person's mailbox does not exist yet: its account is still being created (the message is
    queued or retrying; it gives up after a day), or it was created and has no license. An account HRMS could not
    check (an M365_ACCOUNT task) does not hold the welcome: it may well exist."""
    from app.models.channel_queue import ChannelQueueItem

    queued = db.query(ChannelQueueItem.status).filter(ChannelQueueItem.id == f"m365-account-{user_id}").first()
    if queued is not None and queued[0] in ("PENDING", "PROCESSING", "WAITING_FOR_SLM", "FAILED", "SCHEDULED"):
        return True
    return db.query(_open_tasks(db, user_id, (LICENSE_TASK_CATEGORY,)).exists()).scalar()
