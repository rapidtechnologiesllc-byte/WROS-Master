"""Pydantic schemas -- Workforce Overview (app.services.workforce_report_service)."""
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel


class WorkforcePerson(BaseModel):
    employee_id: str
    candidate_id: Optional[str] = None
    name: str
    business_unit: Optional[str] = None
    status: str
    buddy_program_status: str
    core_certified: bool
    project: Optional[str] = None
    client: Optional[str] = None
    allocation_end_date: Optional[date] = None
    rolling_off: bool
    open_escalations: int
    notice_period: bool
    group: str
    group_label: str


class WorkforceCount(BaseModel):
    key: str
    label: str
    description: str
    count: int


class WorkforceSelection(WorkforceCount):
    kind: Literal["group", "flag"]
    people: List[WorkforcePerson]


class WorkforceOverviewResponse(BaseModel):
    headcount: int
    roll_off_window_days: int
    groups: List[WorkforceCount]
    flags: List[WorkforceCount]
    # the people behind one number, when ?group= or ?flag= is given
    selection: Optional[WorkforceSelection] = None
