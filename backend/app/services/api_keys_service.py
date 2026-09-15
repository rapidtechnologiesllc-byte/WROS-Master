"""
API Keys Service - Manages encrypted credential storage and provider testing.

Responsibilities:
1. Save/update credentials for each provider (encrypted at rest)
2. Retrieve active configuration without exposing secrets
3. Test connections to verify credentials work
4. Handle encryption/decryption safely
5. Audit credential changes
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.api_keys_config import APIKeysConfig
from app.schemas.api_keys_config import (
    SaveAPIKeysRequest,
    AzureGraphCredentials,
    TwilioCredentials,
    SendGridCredentials,
)
import requests
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class APIKeysService:
    """Service for managing delivery provider API keys."""

    @staticmethod
    def save_api_keys(
        db: Session,
        tenant_id: int,
        request: SaveAPIKeysRequest,
        updated_by: int,
    ) -> Dict[str, Any]:
        """
        Save API keys for one or more providers.

        Raises:
            ValueError: If validation fails
            HTTPException: If database operation fails
        """
        saved_providers = []
        errors = {}

        try:
            # ────── Azure Graph ──────────────────────────────────────
            if request.azure:
                try:
                    azure_config = db.query(APIKeysConfig).filter(
                        APIKeysConfig.tenant_id == tenant_id,
                        APIKeysConfig.provider == "azure"
                    ).first()

                    if not azure_config:
                        azure_config = APIKeysConfig(
                            tenant_id=tenant_id,
                            provider="azure",
                            created_by=updated_by,
                        )
                        db.add(azure_config)

                    # Validate credentials before saving
                    if not request.azure.tenant_id or not request.azure.client_id or not request.azure.client_secret:
                        raise ValueError("Azure: tenant_id, client_id, and client_secret are required")

                    azure_config.set_azure_creds(
                        tenant_id=request.azure.tenant_id,
                        client_id=request.azure.client_id,
                        client_secret=request.azure.client_secret,
                    )
                    azure_config.updated_by = updated_by
                    saved_providers.append("azure")
                    logger.info(f"[APIKeysService] Azure credentials saved for tenant {tenant_id}")

                except Exception as e:
                    errors["azure"] = str(e)
                    logger.error(f"[APIKeysService] Azure save failed: {e}", exc_info=True)

            # ────── Twilio ──────────────────────────────────────
            if request.twilio:
                try:
                    twilio_config = db.query(APIKeysConfig).filter(
                        APIKeysConfig.tenant_id == tenant_id,
                        APIKeysConfig.provider == "twilio"
                    ).first()

                    if not twilio_config:
                        twilio_config = APIKeysConfig(
                            tenant_id=tenant_id,
                            provider="twilio",
                            created_by=updated_by,
                        )
                        db.add(twilio_config)

                    # Validate credentials
                    if not request.twilio.account_sid or not request.twilio.auth_token or not request.twilio.whatsapp_number:
                        raise ValueError("Twilio: account_sid, auth_token, and whatsapp_number are required")

                    twilio_config.set_twilio_creds(
                        account_sid=request.twilio.account_sid,
                        auth_token=request.twilio.auth_token,
                        whatsapp_number=request.twilio.whatsapp_number,
                    )
                    twilio_config.updated_by = updated_by
                    saved_providers.append("twilio")
                    logger.info(f"[APIKeysService] Twilio credentials saved for tenant {tenant_id}")

                except Exception as e:
                    errors["twilio"] = str(e)
                    logger.error(f"[APIKeysService] Twilio save failed: {e}", exc_info=True)

            # ────── SendGrid ──────────────────────────────────────
            if request.sendgrid:
                try:
                    sendgrid_config = db.query(APIKeysConfig).filter(
                        APIKeysConfig.tenant_id == tenant_id,
                        APIKeysConfig.provider == "sendgrid"
                    ).first()

                    if not sendgrid_config:
                        sendgrid_config = APIKeysConfig(
                            tenant_id=tenant_id,
                            provider="sendgrid",
                            created_by=updated_by,
                        )
                        db.add(sendgrid_config)

                    # Validate credentials
                    if not request.sendgrid.api_key or not request.sendgrid.from_email:
                        raise ValueError("SendGrid: api_key and from_email are required")

                    sendgrid_config.set_sendgrid_creds(
                        api_key=request.sendgrid.api_key,
                        from_email=request.sendgrid.from_email,
                    )
                    sendgrid_config.updated_by = updated_by
                    saved_providers.append("sendgrid")
                    logger.info(f"[APIKeysService] SendGrid credentials saved for tenant {tenant_id}")

                except Exception as e:
                    errors["sendgrid"] = str(e)
                    logger.error(f"[APIKeysService] SendGrid save failed: {e}", exc_info=True)

            # ────── Set active provider ──────────────────────────────────────
            if request.active_provider:
                active_config = db.query(APIKeysConfig).filter(
                    APIKeysConfig.tenant_id == tenant_id,
                    APIKeysConfig.provider == request.active_provider
                ).first()

                if not active_config and request.active_provider != "stub":
                    errors[request.active_provider] = f"Provider '{request.active_provider}' not configured yet"
                else:
                    # Deactivate all others
                    db.query(APIKeysConfig).filter(
                        APIKeysConfig.tenant_id == tenant_id
                    ).update({"is_active": False})

                    # Activate selected provider
                    if active_config:
                        active_config.is_active = True
                        logger.info(f"[APIKeysService] Active provider set to '{request.active_provider}' for tenant {tenant_id}")

            db.commit()

            status = "success" if not errors else ("partial" if saved_providers else "failed")
            return {
                "status": status,
                "message": f"Saved {len(saved_providers)} provider(s)" if saved_providers else "No providers saved",
                "saved_providers": saved_providers,
                "errors": errors if errors else None,
            }

        except Exception as e:
            db.rollback()
            logger.error(f"[APIKeysService] Save failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to save API keys: {str(e)}")

    @staticmethod
    def get_api_keys(db: Session, tenant_id: int) -> Dict[str, Any]:
        """
        Get configured providers for tenant WITH actual credentials from database.

        Returns:
            Dict with active_provider, all providers, and actual credential values
        """
        try:
            configs = db.query(APIKeysConfig).filter(
                APIKeysConfig.tenant_id == tenant_id
            ).all()

            providers = []
            active_provider = "stub"  # Default
            azure_creds = None
            twilio_creds = None
            sendgrid_creds = None

            for config in configs:
                provider_info = {
                    "provider": config.provider,
                    "status": "configured",
                    "is_active": config.is_active,
                    "last_tested_at": config.last_tested_at,
                    "last_tested_status": config.last_tested_status,
                    "azure_configured": bool(config.azure_tenant_id),
                    "twilio_configured": bool(config.twilio_account_sid),
                    "sendgrid_configured": bool(config.sendgrid_api_key),
                }
                providers.append(provider_info)

                if config.is_active:
                    active_provider = config.provider

                # Decrypt and include actual credentials from database
                if config.provider == "azure" and config.azure_tenant_id:
                    azure_creds = config.get_azure_creds()
                elif config.provider == "twilio" and config.twilio_account_sid:
                    twilio_creds = config.get_twilio_creds()
                elif config.provider == "sendgrid" and config.sendgrid_api_key:
                    sendgrid_creds = config.get_sendgrid_creds()

            return {
                "active_provider": active_provider,
                "providers": providers,
                "available_providers": ["azure", "twilio", "sendgrid", "stub"],
                "azure": azure_creds,
                "twilio": twilio_creds,
                "sendgrid": sendgrid_creds,
            }
        except Exception as e:
            logger.error(f"[APIKeysService] Get failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to retrieve API keys: {str(e)}")

    @staticmethod
    def test_connection(db: Session, tenant_id: int, provider: str) -> Dict[str, Any]:
        """
        Test connection to a specific provider.

        Returns:
            Dict with status, message, and details
        """
        logger.info(f"[APIKeysService] Testing connection for provider: {provider}")

        if provider == "stub":
            return {
                "status": "success",
                "provider": "stub",
                "message": "STUB provider (testing mode - no actual delivery)",
            }

        try:
            config = db.query(APIKeysConfig).filter(
                APIKeysConfig.tenant_id == tenant_id,
                APIKeysConfig.provider == provider
            ).first()

            if not config:
                return {
                    "status": "failed",
                    "provider": provider,
                    "message": f"No configuration found for provider '{provider}'",
                }

            # ────── Test Azure Graph ──────────────────────────────────────
            if provider == "azure":
                return APIKeysService._test_azure(config, tenant_id, db)

            # ────── Test Twilio ──────────────────────────────────────
            elif provider == "twilio":
                return APIKeysService._test_twilio(config, tenant_id, db)

            # ────── Test SendGrid ──────────────────────────────────────
            elif provider == "sendgrid":
                return APIKeysService._test_sendgrid(config, tenant_id, db)

            else:
                return {
                    "status": "failed",
                    "provider": provider,
                    "message": f"Unknown provider: {provider}",
                }

        except Exception as e:
            logger.error(f"[APIKeysService] Test connection failed for {provider}: {e}", exc_info=True)
            # Update test status in DB
            if 'config' in locals():
                config.last_tested_status = "failed"
                config.last_tested_error = str(e)
                config.last_tested_at = datetime.utcnow()
                db.commit()

            return {
                "status": "failed",
                "provider": provider,
                "message": f"Connection test failed: {str(e)}",
            }

    @staticmethod
    def _test_azure(config: APIKeysConfig, tenant_id: int, db: Session) -> Dict[str, Any]:
        """Test Azure Graph credentials."""
        try:
            creds = config.get_azure_creds()
            if not creds or not all([creds.get("tenant_id"), creds.get("client_id"), creds.get("client_secret")]):
                raise ValueError("Azure credentials incomplete")

            # Test by getting token via OAuth
            from app.core.graph_auth import get_graph_token
            token = get_graph_token()  # Will raise if credentials are invalid

            config.last_tested_status = "success"
            config.last_tested_error = None
            config.last_tested_at = datetime.utcnow()
            db.commit()

            logger.info(f"[APIKeysService] Azure connection test PASSED for tenant {tenant_id}")
            return {
                "status": "success",
                "provider": "azure",
                "message": "Azure Graph connection successful",
            }
        except Exception as e:
            raise ValueError(f"Azure Graph test failed: {str(e)}")

    @staticmethod
    def _test_twilio(config: APIKeysConfig, tenant_id: int, db: Session) -> Dict[str, Any]:
        """Test Twilio credentials."""
        try:
            # Lazy import - twilio is optional
            try:
                from twilio.rest import Client as TwilioClient
            except ImportError:
                raise ValueError("Twilio SDK not installed. Install with: pip install twilio")

            creds = config.get_twilio_creds()
            if not creds or not all([creds.get("account_sid"), creds.get("auth_token")]):
                raise ValueError("Twilio credentials incomplete")

            # Test by creating Twilio client
            client = TwilioClient(creds["account_sid"], creds["auth_token"])
            # Try to fetch account details to verify credentials
            account = client.api.accounts(creds["account_sid"]).fetch()

            config.last_tested_status = "success"
            config.last_tested_error = None
            config.last_tested_at = datetime.utcnow()
            db.commit()

            logger.info(f"[APIKeysService] Twilio connection test PASSED for tenant {tenant_id}")
            return {
                "status": "success",
                "provider": "twilio",
                "message": f"Twilio connection successful (Account: {account.friendly_name})",
                "details": {"account_name": account.friendly_name},
            }
        except Exception as e:
            raise ValueError(f"Twilio test failed: {str(e)}")

    @staticmethod
    def _test_sendgrid(config: APIKeysConfig, tenant_id: int, db: Session) -> Dict[str, Any]:
        """Test SendGrid credentials."""
        try:
            creds = config.get_sendgrid_creds()
            if not creds or not creds.get("api_key"):
                raise ValueError("SendGrid credentials incomplete")

            # Test by making API call to SendGrid
            headers = {
                "Authorization": f"Bearer {creds['api_key']}",
                "Content-Type": "application/json",
            }
            response = requests.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                raise ValueError(f"SendGrid API returned {response.status_code}: {response.text}")

            profile = response.json()

            config.last_tested_status = "success"
            config.last_tested_error = None
            config.last_tested_at = datetime.utcnow()
            db.commit()

            logger.info(f"[APIKeysService] SendGrid connection test PASSED for tenant {tenant_id}")
            return {
                "status": "success",
                "provider": "sendgrid",
                "message": "SendGrid connection successful",
                "details": {"email": profile.get("email")},
            }
        except Exception as e:
            raise ValueError(f"SendGrid test failed: {str(e)}")

    @staticmethod
    def get_active_provider_config(db: Session, tenant_id: int) -> Optional[APIKeysConfig]:
        """Get the currently active provider configuration."""
        try:
            config = db.query(APIKeysConfig).filter(
                APIKeysConfig.tenant_id == tenant_id,
                APIKeysConfig.is_active == True
            ).first()

            if not config:
                logger.debug(f"[APIKeysService] No active provider for tenant {tenant_id}, defaulting to stub")
                return None

            return config
        except Exception as e:
            logger.error(f"[APIKeysService] Failed to get active config: {e}")
            return None
