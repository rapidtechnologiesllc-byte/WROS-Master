"""
HRMS-0102 — client status transition + markup-rate visibility guard.
HRMS-0709 — account manager assignment + client activity timeline.
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.client import Client, ClientContact, ClientHistory, STATUSES_REQUIRING_CONTACT
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.submission import Submission
from app.models.interview_pipeline import SubmissionInterview
from app.services.email_service import EmailService

# BR-02: roles allowed to see markup_rate_pct. CS and recruiters are
# deliberately excluded -- margin data is not their business to see.
MARKUP_VISIBLE_ROLES = {"Super User", "BU Head", "Recruitment Manager", "Director"}


class ClientValidationError(Exception):
    pass


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

    Uses EmailService.send_notification() directly -- the same ad hoc
    notification path already used elsewhere in this codebase (see
    app.api.v1.endpoints.interviews). The requirements docs describe a
    dedicated HRMS-0113 Notification Engine as the one sanctioned
    dispatch point for every internal notification, but nothing under
    that name is actually built in this codebase yet -- swap this call
    for that dispatcher once it exists, don't reimplement it here.
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

    if notify and employee.email:
        active_demands = db.query(Demand).filter(
            Demand.client_id == client.id, Demand.status.in_(("OPEN", "IN_PROGRESS")),
        ).count()
        open_submissions = db.query(Submission).filter(
            Submission.client_id == client.id,
            Submission.status.in_(("SUBMITTED", "SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED", "OFFER_EXTENDED")),
        ).count()
        try:
            EmailService.send_notification(
                to_email=employee.email,
                heading=f"You have been assigned as account manager for {client.company_name}",
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
