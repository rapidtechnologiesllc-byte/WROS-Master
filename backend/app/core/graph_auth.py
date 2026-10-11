"""
Microsoft Graph Service Account Authentication
Provides application-only authentication for SharePoint uploads.
This allows candidates without Microsoft accounts to upload documents.
"""

import logging
import requests
from datetime import datetime, timedelta

def _credentials():
    """(tenant, client_id, secret), read when needed -- not at import, which in
    the queue worker ran before .env was loaded and left email "not configured".
    Same placeholder-aware lookup as the delegated (Outlook) flow."""
    import app.core.config  # noqa: F401  (loads backend/.env)
    from app.core.msgraph_session_store import graph_oauth_settings
    s = graph_oauth_settings()
    tenant = s["authority"].rstrip("/").rsplit("/", 1)[-1] if s["authority"] else None
    return tenant, s["client_id"], s["client_secret"]

# Token cache
_token_cache = {
    "access_token": None,
    "expires_at": None
}

logger = logging.getLogger(__name__)

class GraphServiceAuth:
    """
    Microsoft Graph Service Authentication
    Uses client credentials flow (application permissions) instead of delegated permissions.
    This allows the application to access SharePoint on behalf of itself, not a user.
    """
    
    @staticmethod
    def get_access_token(force_refresh: bool = False) -> str:
        """
        Get Microsoft Graph access token using client credentials flow.
        
        Args:
            force_refresh: Force token refresh even if cached token is valid
            
        Returns:
            Access token string
            
        Raises:
            Exception: If token acquisition fails
        """
        # Check if we have a valid cached token
        if not force_refresh and _token_cache["access_token"] and _token_cache["expires_at"]:
            if datetime.utcnow() < _token_cache["expires_at"]:
                logger.info("Using cached Microsoft Graph access token")
                return _token_cache["access_token"]
        
        # Get new token
        logger.info("Acquiring new Microsoft Graph access token")
        
        tenant_id, client_id, client_secret = _credentials()
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(token_url, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            
            if not access_token:
                raise Exception("No access token in response")
            
            # Cache the token (expire 5 minutes early to be safe)
            _token_cache["access_token"] = access_token
            _token_cache["expires_at"] = datetime.utcnow() + timedelta(seconds=expires_in - 300)
            
            logger.info(f"Successfully acquired access token, expires in {expires_in} seconds")
            return access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to acquire access token: {str(e)}")
            raise Exception(f"Failed to authenticate with Microsoft Graph: {str(e)}")
    
    @staticmethod
    def clear_token_cache():
        """Clear the cached token (useful for testing or when token is invalid)"""
        _token_cache["access_token"] = None
        _token_cache["expires_at"] = None
        logger.info("Token cache cleared")
    
    @staticmethod
    def is_configured() -> bool:
        """Check if service account is properly configured"""
        return all(_credentials())


def get_graph_token(force_refresh: bool = False) -> str:
    """Get Microsoft Graph access token (wrapper for EmailService compatibility)"""
    return GraphServiceAuth.get_access_token(force_refresh=force_refresh)
    
    @staticmethod
    def validate_token(access_token: str) -> bool:
        """
        Validate if the access token is still valid by making a test request.
        
        Args:
            access_token: Token to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

# Convenience function
def get_graph_token() -> str:
    """
    Get Microsoft Graph access token for SharePoint operations.
    
    Returns:
        Access token string
        
    Raises:
        Exception: If authentication is not configured or fails
    """
    if not GraphServiceAuth.is_configured():
        raise Exception(
            "Microsoft Graph service account not configured. "
            "Please set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET in .env"
        )
    
    return GraphServiceAuth.get_access_token()
