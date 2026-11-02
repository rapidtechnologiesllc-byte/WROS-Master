"""Pydantic schemas -- S-205 Business Unit Context Switching."""
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class BUAccessItem(BaseModel):
    business_unit_id: int
    name: str
    continent: Optional[str] = None
    region: Optional[str] = None
    is_default: bool = False
    # how the user relates to it: "Partner", "BU Head (BX-IN)", "Member"; empty for org-level users
    roles: List[str] = []

class MyBUAccessResponse(BaseModel):
    # the business units the user may look at, from their role template (never a separate list)
    access: List[BUAccessItem]
    # org-level users see every business unit, with "All business units" as the default view
    can_view_all_bus: bool
    # the BU the selector narrows this request to (X-Active-BU-Id), when it is inside the scope
    active_business_unit_id: Optional[int] = None

class SwitchBURequest(BaseModel):
    business_unit_id: int
