import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class ConfigItem(BaseModel):
    config_key: str
    label: str
    value_type: str
    value: Any
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enum_values: Optional[List[str]] = None


class LocaleConfig(BaseModel):
    default_timezone: str
    default_date_format: str
    default_currency: str


class SettingsPanelResponse(BaseModel):
    AI_THRESHOLDS: List[ConfigItem]
    SLA: List[ConfigItem]
    CHANNELS: List[ConfigItem]
    LOCALE: LocaleConfig


class UpdateConfigValueRequest(BaseModel):
    value: Any


class UpdateLocaleRequest(BaseModel):
    default_timezone: Optional[str] = None
    default_date_format: Optional[str] = None
    default_currency: Optional[str] = None
