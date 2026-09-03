import logging
from typing import List, Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class TimelineEntryOut(BaseModel):
    id: int
    actor_id: Optional[str] = None
    actor_type: str
    action: str
    description: Optional[str] = None
    created_at: Optional[str] = None

class TimelineResponse(BaseModel):
    total: int
    page: int
    per_page: int
    entries: List[TimelineEntryOut]

class WriteTimelineEntryRequest(BaseModel):
    action: str
    description: Optional[str] = None

class FileUploadOut(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    file_category: str
    original_filename: str
    file_size: int
    scan_status: str
    uploaded_by: Optional[str] = None
    created_at: Optional[str] = None

class FileAccessUrlResponse(BaseModel):
    access_url: Optional[str] = None
