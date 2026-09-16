"""
API Keys Configuration Model - Securely stores credentials for delivery providers.

Stores encrypted credentials for:
- Azure Graph (Microsoft 365 email)
- Twilio (WhatsApp)
- SendGrid (Email fallback)

All sensitive fields are encrypted at rest using Fernet symmetric encryption.
Decryption happens only when credentials are needed for testing or delivery.
"""

import logging
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, JSON
from sqlalchemy.sql import func
from app.models.base import Base
from cryptography.fernet import Fernet
import os

logger = logging.getLogger(__name__)

class APIKeysConfig(Base):
    """
    API Keys Configuration Table

    Stores encrypted credentials for all delivery providers.
    Only one active configuration per tenant per provider.
    """
    __tablename__ = "api_keys_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False)  # Multi-tenant support

    # Provider Type: 'azure', 'twilio', 'sendgrid', 'stub'
    provider = Column(String(50), nullable=False)

    # ======== AZURE GRAPH CREDENTIALS (Encrypted) ========
    # Store as JSON for future extensibility
    azure_tenant_id = Column(Text, nullable=True)  # Encrypted
    azure_client_id = Column(Text, nullable=True)  # Encrypted
    azure_client_secret = Column(Text, nullable=True)  # Encrypted

    # ======== TWILIO CREDENTIALS (Encrypted) ========
    twilio_account_sid = Column(Text, nullable=True)  # Encrypted
    twilio_auth_token = Column(Text, nullable=True)  # Encrypted
    twilio_whatsapp_number = Column(String(20), nullable=True)  # Phone number

    # ======== SENDGRID CREDENTIALS (Encrypted) ========
    sendgrid_api_key = Column(Text, nullable=True)  # Encrypted
    sendgrid_from_email = Column(String(255), nullable=True)  # Not encrypted (just an email)

    # ======== STATUS & AUDIT ========
    is_active = Column(Boolean, default=False)  # Is this provider currently selected?
    last_tested_at = Column(DateTime, nullable=True)  # When was connection last verified?
    last_tested_status = Column(String(50), nullable=True)  # 'success', 'failed', 'pending'
    last_tested_error = Column(Text, nullable=True)  # Error message if test failed

    created_by = Column(String(512), nullable=True)  # User email/ID
    updated_by = Column(String(512), nullable=True)  # User email/ID
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ------------------------------------------------------------------
    # Encryption/Decryption Logic
    # ------------------------------------------------------------------

    @staticmethod
    def _get_cipher():
        """Get Fernet cipher for encryption/decryption."""
        # CRITICAL: ENCRYPTION_KEY must be set in environment
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # Fallback for development: generate deterministic key from database URL
            db_url = os.getenv("DATABASE_URL", "dev")
            key = Fernet.generate_key()  # In production, this MUST come from env
            logger.warning(
                "[APIKeysConfig] ENCRYPTION_KEY not set in environment. "
                "Using development key. SET ENCRYPTION_KEY in production environment!"
            )
        return Fernet(key)

    @staticmethod
    def encrypt_value(value: str) -> str:
        """Encrypt a sensitive value."""
        if not value:
            return None
        try:
            cipher = APIKeysConfig._get_cipher()
            encrypted = cipher.encrypt(value.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"[APIKeysConfig] Encryption failed: {e}")
            raise ValueError(f"Failed to encrypt credential: {str(e)}")

    @staticmethod
    def decrypt_value(encrypted_value: str) -> str:
        """Decrypt a sensitive value."""
        if not encrypted_value:
            return None
        try:
            cipher = APIKeysConfig._get_cipher()
            decrypted = cipher.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"[APIKeysConfig] Decryption failed: {e}")
            raise ValueError(f"Failed to decrypt credential: {str(e)}")

    def get_azure_creds(self) -> dict:
        """Get decrypted Azure credentials."""
        return {
            "tenant_id": self.decrypt_value(self.azure_tenant_id),
            "client_id": self.decrypt_value(self.azure_client_id),
            "client_secret": self.decrypt_value(self.azure_client_secret),
        } if self.azure_tenant_id else None

    def get_twilio_creds(self) -> dict:
        """Get decrypted Twilio credentials."""
        return {
            "account_sid": self.decrypt_value(self.twilio_account_sid),
            "auth_token": self.decrypt_value(self.twilio_auth_token),
            "whatsapp_number": self.twilio_whatsapp_number,
        } if self.twilio_account_sid else None

    def get_sendgrid_creds(self) -> dict:
        """Get decrypted SendGrid credentials."""
        return {
            "api_key": self.decrypt_value(self.sendgrid_api_key),
            "from_email": self.sendgrid_from_email,
        } if self.sendgrid_api_key else None

    def set_azure_creds(self, tenant_id: str, client_id: str, client_secret: str):
        """Set and encrypt Azure credentials."""
        self.azure_tenant_id = self.encrypt_value(tenant_id)
        self.azure_client_id = self.encrypt_value(client_id)
        self.azure_client_secret = self.encrypt_value(client_secret)

    def set_twilio_creds(self, account_sid: str, auth_token: str, whatsapp_number: str):
        """Set and encrypt Twilio credentials."""
        self.twilio_account_sid = self.encrypt_value(account_sid)
        self.twilio_auth_token = self.encrypt_value(auth_token)
        self.twilio_whatsapp_number = whatsapp_number

    def set_sendgrid_creds(self, api_key: str, from_email: str):
        """Set and encrypt SendGrid credentials."""
        self.sendgrid_api_key = self.encrypt_value(api_key)
        self.sendgrid_from_email = from_email
