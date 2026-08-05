"""
HRMS-0102 — client status transition + markup-rate visibility guard.
HRMS-0709 — account manager assignment + client activity timeline.
HRMS-0201 — exactly-one-primary-contact rule (see app.models.client's
module docstring for why this extends HRMS-0102 rather than forking it).
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.client import Client, ClientContact, ClientHistory, STATUSES_REQUIRING_CONTACT
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.rbac import BusinessUnit
from app.models.submission import Submission
from app.models.interview_pipeline import SubmissionInterview
from app.models.user import Users
from app.services.notification_service import send_notification

# BR-02: roles allowed to see markup_rate_pct. CS and recruiters are
# deliberately excluded -- margin data is not their business to see.
MARKUP_VISIBLE_ROLES = {"Super User", "BU Head", "Recruitment Manager", "Director"}


class ClientValidationError(Exception):
    pass


class DuplicateClientError(Exception):
    pass


def create_client(
    db: Session,
    *,
    company_name: str,
    created_by_user: Users,
    client_type: str = "DIRECT",
    industry: Optional[str] = None,
    country: Optional[str] = None,
    billing_currency: str = "USD",
) -> Client:
    """The one sanctioned client-creation path (no create path existed
    anywhere in this codebase before this -- the GET-only /clients
    endpoint's own docstring claimed one existed "elsewhere"; it didn't,
    confirmed by grep before writing this).

    BU attribution is LOCKED to the creating user's own business_unit_id
    -- never a caller-supplied field -- per Avinash's 2026-08-05 "client
    attribution locking" rule: a client sourced by someone in AXION
    belongs to AXION, never reassignable across BUs, and the same rule
    cascades to any sales org a Partner hires later (their tree never
    crosses group). A creator with no BU (Super User/CEO/a Corporate
    function) attributes to the "Corporate" BU if that row exists;
    otherwise left unassigned -- same Org-Pool-until-claimed posture the
    Client model's own business_unit_id docstring already establishes,
    never guessed.
    """
    company_name = company_name.strip()
    if not company_name:
        raise ClientValidationError("company_name is required.")

    existing = db.query(Client).filter(Client.company_name == company_name).first()
    if existing:
        raise DuplicateClientError(f"A client named {company_name!r} already exists.")

    business_unit_id = created_by_user.business_unit_id
    if business_unit_id is None:
        corporate_bu = db.query(BusinessUnit).filter(BusinessUnit.name == "Corporate").first()
        business_unit_id = corporate_bu.id if corporate_bu else None

    client = Client(
        company_name=company_name,
        business_unit_id=business_unit_id,
        client_type=client_type,
        industry=industry,
        country=country,
        billing_currency=billing_currency,
        created_by=created_by_user.UserID,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


EDITABLE_CLIENT_FIELDS = {
    "company_name", "company_short_name", "industry", "country", "client_type", "tier",
    "billing_address", "billing_currency", "payment_terms_days",
    "tax_id_client", "contract_start_date", "contract_end_date",
    "contract_url", "nda_signed", "nda_url", "notes",
}


def update_client_details(db: Session, client: Client, updates: dict) -> Client:
    """General "edit client details" path (the gap Avinash flagged
    2026-08-05: no client edit UI/API existed at all). Deliberately
    excludes `business_unit_id` (locked per the attribution rule in
    create_client() -- never editable through a general-purpose update),
    `status` (its own sanctioned path is set_client_status(), which
    enforces BR-01's contact requirement -- bypassing that here would
    let a status change skip the check), and `markup_rate_pct` (BR-02
    confidential -- restricted to MARKUP_VISIBLE_ROLES at read time;
    a write path here would let a broader-access edit endpoint bypass
    that read restriction, so margin changes stay out of scope)."""
    unknown = set(updates) - EDITABLE_CLIENT_FIELDS
    if unknown:
        raise ClientValidationError(f"Not editable via this path: {sorted(unknown)}")

    new_name = updates.get("company_name")
    if new_name is not None and new_name.strip() != client.company_name:
        new_name = new_name.strip()
        if not new_name:
            raise ClientValidationError("company_name cannot be blank.")
        duplicate = (
            db.query(Client)
            .filter(Client.company_name == new_name, Client.id != client.id)
            .first()
        )
        if duplicate:
            raise DuplicateClientError(f"A client named {new_name!r} already exists.")
        updates = {**updates, "company_name": new_name}

    for field, value in updates.items():
        setattr(client, field, value)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def set_client_status(
    db: Session,
    client: Client,
    new_status: str,
    *,
    changed_by: Optional[str] = None,
) -> Client:
    """
    BR-01: cannot set status=ACTIVE without at least one client_contact
    record. Checked here, not just at the API/UI layer, so a direct
    call to this function (the only sanctioned path) can't bypass it.
    """
    if new_status in STATUSES_REQUIRING_CONTACT:
        contact_count = db.query(ClientContact).filter(ClientContact.client_id == client.id).count()
        if contact_count == 0:
            raise ClientValidationError(
                f"Cannot set client status to '{new_status}' without at least one client_contact record."
            )

    old_status = client.status
    history = ClientHistory(
        tenant_id=client.tenant_id,
        client_id=client.id,
        change_type="STATUS",
        old_value=json.dumps({"status": old_status}),
        new_value=json.dumps({"status": new_status}),
        changed_by=changed_by,
    )
    client.status = new_status
    db.add(client)
    db.add(history)
    return client


def serialize_client_for_role(client: Client, role_name: str) -> dict:
    """
    BR-02: markup_rate_pct is confidential -- included only for roles in
    MARKUP_VISIBLE_ROLES. This is the one sanctioned serialization path;
    a route building its own dict by hand risks forgetting the guard.
    """
    data = {
        "id": client.id,
        "company_name": client.company_name,
        "company_short_name": client.company_short_name,
        "industry": client.industry,
        "client_type": client.client_type,
        "tier": client.tier,
        "status": client.status,
        "billing_currency": client.billing_currency,
        "payment_terms_days": client.payment_terms_days,
    }
    if role_name in MARKUP_VISIBLE_ROLES:
        data["markup_rate_pct"] = float(client.markup_rate_pct) if client.markup_rate_pct is not None else None
    return data


def set_primary_contact(db: Session, client: Client, contact: ClientContact) -> ClientContact:
    """
    HRMS-0201 BR-0201-02: exactly one contact per client is Primary at
    any time. Setting a new Primary auto-unsets whichever contact
    previously held it, in the same transaction -- never two Primary
    contacts, even briefly.
    """
    if contact.client_id != client.id:
        raise ValueError(f"Contact {contact.id} does not belong to client {client.id}.")

    db.query(ClientContact).filter(
        ClientContact.client_id == client.id,
        ClientContact.id != contact.id,
        ClientContact.is_primary == True,  # noqa: E712
    ).update({"is_primary": False})

    contact.is_primary = True
    db.add(contact)
    return contact


def assign_account_manager(
    db: Session,
    client: Client,
    employee: Employee,
    *,
    changed_by: Optional[str] = None,
    notify: bool = True,
) -> Client:
    """
    HRMS-0709 BR-01: notifies the newly assigned AM with their current
    active-demand and open-submission counts for this client.

    Routes through app.services.notification_service.send_notification()
    (HRMS-0113) -- the sanctioned single dispatch point, not a direct
    EmailService call. Requires the employee to have a linked WROS user
    account (employee.wros_user_id) since HRMS-0113's recipient is a
    Users row (needed for tenant scoping and business-hours gating); an
    AM with no WROS login is logged and skipped rather than emailed
    directly, since there's no "notify a bare Employee" path in the
    notification engine as specified.
    """
    old_am_id = client.account_manager_employee_id
    if old_am_id == employee.id:
        return client  # no-op, nothing actually changed

    history = ClientHistory(
        tenant_id=client.tenant_id, client_id=client.id, change_type="ACCOUNT_MANAGER",
        old_value=json.dumps({"account_manager_employee_id": old_am_id}),
        new_value=json.dumps({"account_manager_employee_id": employee.id}),
        changed_by=changed_by,
    )
    client.account_manager_employee_id = employee.id
    db.add(client)
    db.add(history)

    if notify:
        recipient = db.query(Users).filter(Users.UserID == employee.wros_user_id).first() \
            if employee.wros_user_id else None

        if recipient is None:
            logger.warning(
                f"[ClientService] Cannot notify AM {employee.id} of assignment to "
                f"client {client.id} -- no linked WROS user account."
            )
        else:
            active_demands = db.query(Demand).filter(
                Demand.client_id == client.id, Demand.status.in_(("OPEN", "IN_PROGRESS")),
            ).count()
            open_submissions = db.query(Submission).filter(
                Submission.client_id == client.id,
                Submission.status.in_(("SUBMITTED", "SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED", "OFFER_EXTENDED")),
            ).count()
            try:
                send_notification(
                    db,
                    calling_context_tenant_id=client.tenant_id,
                    recipient=recipient,
                    priority_tier="P1",
                    channel_preference="EMAIL",
                    message=(
                        f"You have been assigned as account manager for "
                        f"<strong>{client.company_name}</strong>.<br><br>"
                        f"{active_demands} active demand(s), {open_submissions} open submission(s)."
                    ),
                )
            except Exception as exc:
                logger.warning(f"[ClientService] Could not send AM assignment notification: {exc}")

    return client


def get_client_activity_timeline(db: Session, client_id: str) -> List[dict]:
    """
    HRMS-0709 step 2. Aggregates from what actually exists in this
    codebase today: demand-created, candidate-submitted,
    placement-confirmed, and interview-scheduled events. Offer-made /
    invoice-raised / payment-received are NOT included -- the offers
    and invoicing tables don't exist yet (see CLAUDE.md); add them here
    once they land rather than building a second, parallel timeline.
    """
    events: List[dict] = []

    demands = db.query(Demand).filter(Demand.client_id == client_id).all()
    demand_ids = [d.id for d in demands]
    for d in demands:
        events.append({
            "event_type": "DEMAND_CREATED", "date": d.created_at,
            "summary": f"{d.job_title} demand opened", "record_id": d.id,
        })

    submission_ids: List[str] = []
    if demand_ids:
        submissions = db.query(Submission).filter(Submission.demand_id.in_(demand_ids)).all()
        for s in submissions:
            events.append({
                "event_type": "CANDIDATE_SUBMITTED", "date": s.submitted_at,
                "summary": f"Candidate {s.candidate_id} submitted", "record_id": s.id,
            })
            if s.status == "PLACED" and s.client_response_at:
                events.append({
                    "event_type": "PLACEMENT_CONFIRMED", "date": s.client_response_at,
                    "summary": f"Candidate {s.candidate_id} placed", "record_id": s.id,
                })
        submission_ids = [s.id for s in submissions]

    if submission_ids:
        interviews = db.query(SubmissionInterview).filter(
            SubmissionInterview.submission_id.in_(submission_ids),
            SubmissionInterview.scheduled_at.isnot(None),
        ).all()
        for iv in interviews:
            events.append({
                "event_type": "INTERVIEW_SCHEDULED", "date": iv.scheduled_at,
                "summary": f"{iv.level} interview scheduled", "record_id": iv.id,
            })

    events.sort(key=lambda e: e["date"] or datetime.min)
    return events
