"""
S-219/HRMS-0121 -- Multi-Continent Locale & Currency Config -- API
Endpoints
=========================================================================
Prefix: /tenants
import logging
Tag:    tenants

Genuinely new backend -- no Tenant-config model, service, or REST layer
existed anywhere in this codebase before this. The requirement doc filed
under S-219's own name (S-219_HRMS-1212.docx) is unrelated content
("Analytics Performance Optimization & Caching") -- same doc-corpus
drift already documented elsewhere this session -- so this was built
directly from the canonical sheet's own one-line spec: "Per-tenant:
timezone, date format, currency display (USD/GBP/EUR/INR/CAD). Monetary
fields store in USD base with local display."

Scoped to "me" (the caller's own tenant, resolved server-side from the
JWT) rather than a path param -- there is exactly one tenant a caller
should ever be able to read or change, and a path param would invite a
cross-tenant edit if the RBAC gate below is ever loosened.

No currency-conversion math is implemented -- see tenant_service.py's
own docstring for why (no FX-rate source exists anywhere in this
codebase; a hardcoded rate would be a guessed, immediately-stale number,
worse than not converting at all).

Auth: get_current_internal_user, same posture as every endpoint this
program. No dedicated "Admin/Settings" role gate exists in this
codebase's RBAC beyond that -- flagged, not guessed at, same posture as
every other role gap this session.

Routes:
  GET   /tenants/me/locale    Get this tenant's locale/currency config.
  PATCH /tenants/me/locale    Update it (partial update, any subset of fields).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.tenant import Tenant
from app.models.user import Users
from app.schemas.tenant import TenantLocaleResponse, UpdateTenantLocaleRequest
from app.services.tenant_service import InvalidTenantLocaleField, update_tenant_locale

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _to_response(tenant: Tenant) -> TenantLocaleResponse:
    return TenantLocaleResponse(
        tenant_id=tenant.id, default_timezone=tenant.default_timezone,
        default_date_format=tenant.default_date_format, default_currency=tenant.default_currency,
    )


def _get_current_tenant_or_404(db: Session, current_user: Users) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return tenant


@router.get("/me/locale", response_model=TenantLocaleResponse, summary="Get this tenant's locale/currency config")
def get_tenant_locale(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    tenant = _get_current_tenant_or_404(db, current_user)
    return _to_response(tenant)


@router.patch("/me/locale", response_model=TenantLocaleResponse, summary="Update this tenant's locale/currency config")
def update_tenant_locale_endpoint(
    body: UpdateTenantLocaleRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    tenant = _get_current_tenant_or_404(db, current_user)
    try:
        tenant = update_tenant_locale(
            db, tenant, default_timezone=body.default_timezone,
            default_date_format=body.default_date_format, default_currency=body.default_currency,
        )
    except InvalidTenantLocaleField as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(tenant)
    return _to_response(tenant)
