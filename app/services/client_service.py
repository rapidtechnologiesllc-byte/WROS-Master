"""HRMS-0102 — client status transition + markup-rate visibility guard."""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client, ClientContact, ClientHistory, STATUSES_REQUIRING_CONTACT

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
