"""
API Keys Configuration Schemas
Request/Response models for API keys management endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class AzureGraphCredentials(BaseModel):
    """Azure Graph (Microsoft 365) configuration."""
    tenant_id: str = Field(..., min_length=1, description="Azure AD Tenant ID")
    client_id: str = Field(..., min_length=1, description="Azure AD Application (Client) ID")
    client_secret: str = Field(..., min_length=1, description="Azure AD Client Secret")


class TwilioCredentials(BaseModel):
    """Twilio configuration for WhatsApp delivery."""
    account_sid: str = Field(..., min_length=1, description="Twilio Account SID")
    auth_token: str = Field(..., min_length=1, description="Twilio Auth Token")
    whatsapp_number: str = Field(..., min_length=1, description="WhatsApp Number (e.g., +1234567890)")


class SendGridCredentials(BaseModel):
    """SendGrid configuration for email delivery."""
    api_key: str = Field(..., min_length=1, description="SendGrid API Key")
    from_email: EmailStr = Field(..., description="From Email Address")


class SaveAPIKeysRequest(BaseModel):
    """
    Save/update API keys for one or more providers.
    Only include the provider(s) you want to configure.
    """
    azure: Optional[AzureGraphCredentials] = None
    twilio: Optional[TwilioCredentials] = None
    sendgrid: Optional[SendGridCredentials] = None
    active_provider: str = Field(
        ...,
        description="Which provider is currently active: 'azure', 'twilio', 'sendgrid', 'stub'"
    )


class APIKeyConfigResponse(BaseModel):
    """Response model for saved credentials (WITHOUT sensitive values)."""
    provider: str
    status: str  # 'configured', 'not_configured'
    is_active: bool
    last_tested_at: Optional[datetime]
    last_tested_status: Optional[str]  # 'success', 'failed', 'pending'
    azure_configured: bool = False
    twilio_configured: bool = False
    sendgrid_configured: bool = False


class GetAPIKeysResponse(BaseModel):
    """Get response showing which providers are configured (no secrets)."""
    active_provider: str  # Currently active provider
    providers: List[APIKeyConfigResponse]  # List of all configured providers
    available_providers: List[str]  # ['azure', 'twilio', 'sendgrid', 'stub']


class TestConnectionRequest(BaseModel):
    """Test connection to a specific provider."""
    provider: str = Field(..., description="Provider to test: 'azure', 'twilio', 'sendgrid', 'stub'")


class TestConnectionResponse(BaseModel):
    """Test connection result."""
    status: str  # 'success', 'failed'
    provider: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SaveAPIKeysResponse(BaseModel):
    """Response after saving API keys."""
    status: str  # 'success', 'partial', 'failed'
    message: str
    active_provider: str
    saved_providers: List[str]  # Providers that were successfully saved
    errors: Optional[Dict[str, str]] = None  # Provider -> error message
