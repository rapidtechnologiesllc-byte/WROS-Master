"""
API Keys Management Endpoints
=============================

Manages credentials for email/messaging delivery providers (Azure, Twilio, SendGrid).

Endpoints:
  GET  /api-keys                    - Get configured providers (no secrets)
  POST /api-keys                    - Save/update credentials for one or more providers
  POST /api-keys/test               - Test connection to a provider
  GET  /api-keys/status             - Health check of active provider
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.services.api_keys_service import APIKeysService
from app.schemas.api_keys_config import (
    SaveAPIKeysRequest,
    SaveAPIKeysResponse,
    GetAPIKeysResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-keys", tags=["API Keys Management"])


# ──────────────────────────────────────────────────────────────────────────────
# Authentication & Authorization
# ──────────────────────────────────────────────────────────────────────────────

def _get_tenant_id(current_user: Users) -> int:
    """Extract and validate tenant_id from current user."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="User is not assigned to a tenant"
        )
    return current_user.tenant_id


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=GetAPIKeysResponse,
    summary="Get configured API providers (no secrets)",
    dependencies=[Depends(require_resource_permission("api-keys", "view"))],
)
def get_api_keys(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Retrieve which providers are configured for the current tenant.

    **Response includes:**
    - `active_provider`: Currently selected provider ('azure', 'twilio', 'sendgrid') or null if none configured
    - `providers`: List of all configured providers with status (no credentials exposed)
    - `available_providers`: Full list of available provider options: ['azure', 'twilio', 'sendgrid']

    **Permission required:** `setting:view`
    """
    tenant_id = _get_tenant_id(current_user)
    logger.info(f"[api_keys/GET] Tenant {tenant_id} fetching configured providers")

    result = APIKeysService.get_api_keys(db, tenant_id)
    return GetAPIKeysResponse(**result)


@router.post(
    "",
    response_model=SaveAPIKeysResponse,
    summary="Save/update API credentials for one or more providers",
    dependencies=[Depends(require_resource_permission("api-keys", "edit"))],
)
def save_api_keys(
    request: SaveAPIKeysRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Save or update credentials for one or more delivery providers.

    **Request body:**
    Only include the provider(s) you want to configure. Leave others as `null`.

    ```json
    {
      "azure": {
        "tenant_id": "your-tenant-id",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
      },
      "active_provider": "azure"
    }
    ```

    **Sensitive fields are encrypted at rest** and never exposed in responses.

    **Permission required:** `setting:update`

    **Returns:**
    - `status`: 'success', 'partial', or 'failed'
    - `saved_providers`: List of providers successfully saved
    - `errors`: Dict of provider -> error message (if any failed)
    """
    tenant_id = _get_tenant_id(current_user)
    logger.info(f"[api_keys/POST] Tenant {tenant_id} saving credentials for: {request.model_dump(exclude_none=True, exclude_unset=True).keys()}")

    result = APIKeysService.save_api_keys(
        db=db,
        tenant_id=tenant_id,
        request=request,
        updated_by=current_user.UserID,
    )

    return SaveAPIKeysResponse(**result)


@router.post(
    "/test",
    response_model=TestConnectionResponse,
    summary="Test connection to a provider",
    dependencies=[Depends(require_resource_permission("api-keys", "edit"))],
)
def test_provider_connection(
    request: TestConnectionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Test whether credentials for a specific provider are valid.

    **Request body:**
    ```json
    {
      "provider": "azure"  // or "twilio", "sendgrid"
    }
    ```

    **Testing logic:**
    - **azure**: Makes OAuth token request (validates tenant_id, client_id, client_secret)
    - **twilio**: Fetches account details (validates account_sid, auth_token)
    - **sendgrid**: Calls API /user/profile (validates api_key)

    **Permission required:** `setting:view`

    **Response includes:**
    - `status`: 'success' or 'failed'
    - `message`: Human-readable result
    - `details`: Optional provider-specific info

    **Audit:** Test results are logged with timestamp and stored on config record.
    """
    tenant_id = _get_tenant_id(current_user)
    logger.info(f"[api_keys/test] Tenant {tenant_id} testing provider: {request.provider}")

    result = APIKeysService.test_connection(
        db=db,
        tenant_id=tenant_id,
        provider=request.provider,
    )

    return TestConnectionResponse(**result)


