"""
HRMS-0515 -- PerformanceStoreWriter. The one function every story that
needs to log a performance-relevant event should call, rather than
inserting into employee_performance_events directly -- same single-
sanctioned-writer discipline as write_audit_log() and
create_candidate_safe().
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.performance_store import EmployeePerformanceEvent


def write_performance_event(
    db: Session,
    *,
    employee_id: str,
    event_type: str,
    event_data: Optional[dict] = None,
    tenant_id=None,
) -> EmployeePerformanceEvent:
    event = EmployeePerformanceEvent(
        tenant_id=tenant_id, employee_id=employee_id, event_type=event_type,
        event_data=json.dumps(event_data) if event_data is not None else None,
    )
    db.add(event)
    return event
