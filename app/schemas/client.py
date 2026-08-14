from datetime import date
from typing import Optional

from pydantic import BaseModel


class ClientListItem(BaseModel):
    id: str
    company_name: str
    status: str
    business_unit_id: Optional[int] = None
    # 2026-08-12, Avinash: BU wasn't visible anywhere in Client Management
    # UI despite business_unit_id already being the real P&L-mapping
    # mechanism (every Opportunity/Demand/revenue figure under a client
    # inherits BU by joining through here -- see revenue_visibility_scope.py).
    # Resolved name so the UI doesn't have to show/cross-reference a raw ID.
    business_unit_name: Optional[str] = None
    # "Client Owner" -- the field already exists (account_manager_employee_id,
    # HRMS-0709) but was never surfaced in any screen. Same pattern as
    # Opportunity.owner_employee_id.
    account_manager_employee_id: Optional[str] = None
    account_manager_name: Optional[str] = None
    line_type: Optional[str] = None
    # Not shown/edited anywhere -- exposed only so the Create Job screen
    # can derive Internal (BlitzenX) vs External without a per-client
    # fetch. See JobCreate.js's client-selection effect.
    website: Optional[str] = None

    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    clients: list[ClientListItem]


class ClientContactCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None


class ClientCreateRequest(BaseModel):
    company_name: str
    # 2026-08-07 redesign, per Avinash's live-testing feedback (real
    # JobDiva client record shown as reference: contacts are their own
    # tab, not a field that blocks creating the company record):
    # hiring_manager/timesheet_approver are now OPTIONAL at creation.
    # They're still required before a client can go status=ACTIVE --
    # see client_service.STATUSES_REQUIRING_CONTACT / set_client_status()
    # -- captured via POST /clients/{client_id}/contacts as a separate
    # step instead of blocking the create form.
    # 2026-08-07 further: website is now OPTIONAL (prospect clients
    # may not have a website yet). line_type defaults to CORE.
    line_type: str = "CORE"
    country: Optional[str] = None
    website: Optional[str] = None
    billing_currency: str = "USD"
    hiring_manager: Optional[ClientContactCreateRequest] = None
    timesheet_approver: Optional[ClientContactCreateRequest] = None


class ClientCreateResponse(BaseModel):
    id: str
    company_name: str
    business_unit_id: Optional[int]

    class Config:
        from_attributes = True


class ClientContactAddRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    role_type: str


class ClientContactResponse(BaseModel):
    id: str
    client_id: str
    name: str
    title: Optional[str] = None
    email: str
    phone: Optional[str] = None
    role_type: str
    is_primary: bool

    class Config:
        from_attributes = True


class ClientContactsListResponse(BaseModel):
    contacts: list[ClientContactResponse]


class ClientDetailResponse(BaseModel):
    id: str
    company_name: str
    company_short_name: Optional[str]
    industry: Optional[str]
    country: Optional[str]
    client_type: str
    line_type: Optional[str]
    website: Optional[str]
    tier: str
    status: str
    business_unit_id: Optional[int]
    business_unit_name: Optional[str] = None
    account_manager_employee_id: Optional[str] = None
    account_manager_name: Optional[str] = None
    account_manager_id: Optional[str] = None  # Account manager from users table
    account_manager_user_name: Optional[str] = None  # Display name for user-based account manager
    client_owner_id: Optional[str] = None  # Sales contact who opened the account (from users table)
    client_owner_name: Optional[str] = None  # Display name for user-based client owner
    billing_address: Optional[str]
    billing_currency: str
    payment_terms_days: int
    tax_id_client: Optional[str]
    contract_start_date: Optional[date]
    contract_end_date: Optional[date]
    contract_url: Optional[str]
    nda_signed: bool
    nda_url: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ClientUpdateRequest(BaseModel):
    # Routed separately to client_service.assign_account_manager() (real
    # audit-history + notification side effects), not through the generic
    # update_client_details() path -- see update_client_endpoint().
    account_manager_employee_id: Optional[str] = None
    account_manager_id: Optional[str] = None  # Account manager from users table
    client_owner_id: Optional[str] = None     # Sales contact who opened the account (from users table)
    company_name: Optional[str] = None
    company_short_name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    client_type: Optional[str] = None
    line_type: Optional[str] = None
    website: Optional[str] = None
    tier: Optional[str] = None
    billing_address: Optional[str] = None
    billing_currency: Optional[str] = None
    payment_terms_days: Optional[int] = None
    tax_id_client: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    contract_url: Optional[str] = None
    nda_signed: Optional[bool] = None
    nda_url: Optional[str] = None
    notes: Optional[str] = None
