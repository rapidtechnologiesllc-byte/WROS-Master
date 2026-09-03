import logging
from app.core.logging import logger
"""Pydantic schemas -- S-219/HRMS-0121 (Multi-Continent Locale & Currency Config)."""

from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class TenantLocaleResponse(BaseModel):
    tenant_id: int
    default_timezone: str
    default_date_format: str
    default_currency: str


class UpdateTenantLocaleRequest(BaseModel):
    default_timezone: Optional[str] = None
    default_date_format: Optional[str] = None
    default_currency: Optional[str] = None
