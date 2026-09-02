"""
Apollo.io MCP Integration for LinkedIn candidate enrichment

Provides functions to search Apollo.io contacts and enrich candidate data
with email, phone, company, title, and critically: open_to_work status.

This module supports both production (real MCP calls) and test (mocked) scenarios.
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def search_apollo_by_linkedin_url(
    linkedin_url: str,
    apollo_mcp_client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Search Apollo.io for a contact by LinkedIn URL.

    Args:
        linkedin_url: Full LinkedIn profile URL (e.g., https://www.linkedin.com/in/prabhu-...)
        apollo_mcp_client: Optional MCP client for making real API calls. If None, raises NotImplementedError.

    Returns:
        Dict with structure:
        {
            'contacts': [{
                'email': 'candidate@example.com',
                'phone_number': '+1-555-0123456',
                'name': 'Candidate Name',
                'company_name': 'Company Inc',
                'title': 'Job Title',
                'open_to_work_status': True,  # CRITICAL: only import if true
                ...  # other Apollo fields
            }]
        }

    Raises:
        NotImplementedError: If apollo_mcp_client is None (Apollo MCP not configured)
        ValueError: If Apollo API call fails or returns invalid data
    """
    if apollo_mcp_client is None:
        raise NotImplementedError(
            "Apollo MCP integration required.\n"
            "Setup steps:\n"
            "1. Go to https://claude.ai/settings/connectors\n"
            "2. Find 'Apollo.io' and click 'Connect'\n"
            "3. Complete OAuth flow to authorize API access\n"
            "4. Restart this backend\n"
            "See backend/LINKEDIN_CANDIDATE_IMPORT.md for details."
        )

    try:
        logger.info(f"[Apollo] Searching for LinkedIn URL: {linkedin_url}")

        # Call Apollo MCP server to search by LinkedIn URL
        # The MCP server handles OAuth token refresh automatically
        result = await apollo_mcp_client.contacts_search({
            "linkedin_url": linkedin_url
        })

        if not result or not result.get('contacts'):
            logger.warning(f"[Apollo] No contacts found for: {linkedin_url}")
            raise ValueError(f"Apollo found no profile matching: {linkedin_url}")

        contact = result['contacts'][0]  # Take first (best match)
        logger.info(
            f"[Apollo] Found contact: {contact.get('name')} "
            f"({contact.get('email')}) - Open to Work: {contact.get('open_to_work_status')}"
        )

        return result

    except ValueError as e:
        # Re-raise value errors (expected failures like "not found")
        logger.warning(f"[Apollo] Search failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[Apollo] API error: {str(e)}", exc_info=True)
        raise ValueError(f"Apollo API call failed: {str(e)}")


def create_mock_apollo_search(
    email: str = "mock@example.com",
    phone: str = "+1-555-0123456",
    full_name: str = "Mock Candidate",
    company: str = "Mock Company Inc",
    title: str = "Software Engineer",
    open_to_work: bool = True
):
    """
    Create a mock Apollo search function for testing.

    Returns an async function that simulates Apollo search response.
    Useful for unit tests and local development.

    Args:
        email: Mock email to return
        phone: Mock phone to return
        full_name: Mock name to return
        company: Mock company to return
        title: Mock job title to return
        open_to_work: Mock open_to_work_status to return

    Returns:
        Async function that returns Apollo-format response
    """

    async def mock_search(search_params: Dict[str, str]) -> Dict[str, Any]:
        logger.info(f"[Apollo Mock] Searching with params: {search_params}")
        return {
            'contacts': [{
                'email': email,
                'phone_number': phone,
                'name': full_name,
                'company_name': company,
                'title': title,
                'open_to_work_status': open_to_work,
                'linkedin_url': search_params.get('linkedin_url'),
            }]
        }

    return mock_search


def create_mock_apollo_not_open_to_work(
    email: str = "passive@example.com",
    phone: str = "+1-555-9999999",
    full_name: str = "Passive Candidate",
    company: str = "Current Company Inc",
    title: str = "Senior Engineer"
):
    """
    Create a mock Apollo search that returns a candidate NOT open to work.

    Useful for testing the open_to_work gate rejection.

    Args:
        email: Mock email to return
        phone: Mock phone to return
        full_name: Mock name to return
        company: Mock company to return
        title: Mock job title to return

    Returns:
        Async function returning Apollo response with open_to_work_status: False
    """

    async def mock_search(search_params: Dict[str, str]) -> Dict[str, Any]:
        logger.info(f"[Apollo Mock] Searching (not open to work) with params: {search_params}")
        return {
            'contacts': [{
                'email': email,
                'phone_number': phone,
                'name': full_name,
                'company_name': company,
                'title': title,
                'open_to_work_status': False,  # KEY: This triggers gate rejection
                'linkedin_url': search_params.get('linkedin_url'),
            }]
        }

    return mock_search


def create_mock_apollo_empty_result():
    """
    Create a mock Apollo search that returns no results (not found).

    Useful for testing ApolloCandidateNotFound exception.

    Returns:
        Async function returning empty contacts list
    """

    async def mock_search(search_params: Dict[str, str]) -> Dict[str, Any]:
        logger.info(f"[Apollo Mock] Searching (no results) with params: {search_params}")
        return {'contacts': []}  # Empty result

    return mock_search
