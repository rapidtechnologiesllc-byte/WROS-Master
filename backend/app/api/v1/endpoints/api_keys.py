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
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
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
)
async def get_api_keys(
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
)
async def save_api_keys(
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
)
async def test_provider_connection(
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


@router.get(
    "/from-env",
    summary="Load API credentials from environment variables",
)
async def load_from_env(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Load and save API credentials from environment variables (.env file).

    This endpoint reads AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    from the environment and saves them to the database.
    """
    tenant_id = _get_tenant_id(current_user)

    azure_tenant_id = os.getenv("AZURE_TENANT_ID")
    azure_client_id = os.getenv("AZURE_CLIENT_ID")
    azure_client_secret = os.getenv("AZURE_CLIENT_SECRET")

    if not all([azure_tenant_id, azure_client_id, azure_client_secret]):
        return {
            "status": "error",
            "message": "Missing environment variables: AZURE_TENANT_ID, AZURE_CLIENT_ID, or AZURE_CLIENT_SECRET",
            "found": {
                "AZURE_TENANT_ID": bool(azure_tenant_id),
                "AZURE_CLIENT_ID": bool(azure_client_id),
                "AZURE_CLIENT_SECRET": bool(azure_client_secret),
            }
        }

    # Create request object with env credentials
    request = SaveAPIKeysRequest(
        azure={
            "tenant_id": azure_tenant_id,
            "client_id": azure_client_id,
            "client_secret": azure_client_secret,
        },
        active_provider="azure"
    )

    # Save to database
    result = APIKeysService.save_api_keys(
        db=db,
        tenant_id=tenant_id,
        request=request,
        updated_by=current_user.UserID,
    )

    logger.info(f"[api_keys/from-env] Loaded Azure credentials from environment for tenant {tenant_id}")
    return result


@router.get(
    "/status",
    summary="Health check - verify active provider is working",
)
async def get_provider_status(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Quick health check for the currently active delivery provider.

    Returns:
    ```json
    {
      "provider": "azure",
      "status": "healthy",  // or "unknown", "failed"
      "last_tested": "2026-09-15T10:30:00Z",
      "message": "..."
    }
    ```
    """
    tenant_id = _get_tenant_id(current_user)
    config = APIKeysService.get_active_provider_config(db, tenant_id)

    if not config:
        return {
            "provider": None,
            "status": "unconfigured",
            "message": "No delivery provider is currently configured"
        }

    return {
        "provider": config.provider,
        "status": "healthy" if config.last_tested_status == "success" else "unknown",
        "last_tested": config.last_tested_at,
        "last_tested_status": config.last_tested_status,
        "message": config.last_tested_error if config.last_tested_status == "failed" else "Provider is configured and tested",
    }
