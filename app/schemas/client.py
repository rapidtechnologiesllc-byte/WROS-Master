from datetime import date
from typing import Optional

from pydantic import BaseModel


class ClientListItem(BaseModel):
    id: str
    company_name: str
    status: str
    business_unit_id: Optional[int] = None
    line_type: Optional[str] = None

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
    # 2026-08-06 redesign: line_type (Core/Specialty) replaces
    # client_type on the create form; industry dropped entirely per
    # Avinash's direct instruction. hiring_manager/timesheet_approver
    # are required -- "every client should have contacts that are
    # hiring manager, timesheet approver."
    line_type: str
    country: Optional[str] = None
    website: str
    billing_currency: str = "USD"
    hiring_manager: ClientContactCreateRequest
    timesheet_approver: ClientContactCreateRequest


class ClientCreateResponse(BaseModel):
    id: str
    company_name: str
    business_unit_id: Optional[int]

    class Config:
        from_attributes = True


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
