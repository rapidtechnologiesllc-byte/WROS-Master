"""Pydantic Schemas -- S-074/HRMS-0474 Bulk Candidate Engagement Launch."""
from typing import Dict, List, Optional

from pydantic import BaseModel


class BulkImportResponse(BaseModel):
    imported: int
    skipped_duplicates: int
    errors: List[Dict]
    candidate_ids: List[str]
    message: Optional[str] = None


class BulkEngageRequest(BaseModel):
    candidate_ids: List[str]


class BulkEngageResponse(BaseModel):
    bulk_job_id: str
    total_candidates: int
    estimated_completion_minutes: float


class BulkJobStatusResponse(BaseModel):
    bulk_job_id: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    errors: List[Dict]
