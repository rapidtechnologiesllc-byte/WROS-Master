"""Pydantic schemas -- S-205 Business Unit Context Switching."""
from typing import List, Optional

from pydantic import BaseModel


class BUAccessItem(BaseModel):
    business_unit_id: int
    name: str
    continent: Optional[str] = None
    region: Optional[str] = None
    is_default: bool


class MyBUAccessResponse(BaseModel):
    access: List[BUAccessItem]
    can_view_all_bus: bool


class SwitchBURequest(BaseModel):
    business_unit_id: int
