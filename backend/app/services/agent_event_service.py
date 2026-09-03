import logging
from app.core.logging import logger
"""Agent Event Service - Inter-agent communication via structured events."""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean
from app.models.base import Base
import uuid
import json
logger = logging.getLogger(__name__)

class AgentEvent(Base):
    """Structured event for inter-agent communication."""

    __tablename__ = "agent_events"

    event_id = Column(String(50), primary_key=True)
    event_type = Column(String(100), nullable=False)  # "candidate.qualified", "hire.completed", etc.
    source_agent = Column(String(100), nullable=False)  # Which agent created event
    target_agents = Column(Text)  # CSV of agents that should consume this
    entity_id = Column(String(100), nullable=False)  # candidate_id, employee_id, etc.
    entity_type = Column(String(50), nullable=False)  # "candidate", "employee", "job", etc.
    current_state = Column(String(100))  # State before event
    new_state = Column(String(100))  # State after event
    payload = Column(JSON)  # Event data
    confidence = Column(Integer)  # 0-100
    action_required = Column(String(100))  # Next step
    owner = Column(String(100))  # Who owns next action
    deadline = Column(DateTime)  # When action needed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    status = Column(String(50), default="PENDING")  # PENDING, PROCESSED, ESCALATED
    audit_trail = Column(Text)  # JSON array of who consumed/acted


class AgentEventService:
    """Service for publishing and consuming structured agent events."""

    # Event types that trigger inter-agent communication
    EVENT_TYPES = {
        # RECRUITMENT EVENTS
        "candidate.created": ["Thunder", "Recruitment Agent", "KPI Agent"],
        "candidate.qualified": ["Thunder", "Interview Reminder Agent", "KPI Agent"],
        "candidate.screened": ["Thunder", "Interview Reminder Agent"],
        "candidate.interviewed": ["Thunder", "Offer Letter Agent", "KPI Agent"],
        "candidate.offered": ["HR Agent", "Onboarding Agent", "KPI Agent"],
        "candidate.accepted": ["HR Agent", "Onboarding Agent", "Resource Management Agent", "KPI Agent"],

        # HIRING EVENTS
        "hire.completed": ["HR Agent", "Onboarding Agent", "Buddy Program Agent", "KPI Agent"],
        "employee.onboarded": ["Resource Management Agent", "HR Agent", "Performance Agent", "KPI Agent"],
        "employee.assigned_to_project": ["Resource Management Agent", "HR Agent", "KPI Agent"],

        # RESOURCE EVENTS
        "utilization.updated": ["Resource Management Agent", "KPI Agent"],
        "allocation.created": ["Resource Management Agent", "HR Agent", "KPI Agent"],
        "bench.employee": ["Resource Management Agent", "HR Agent", "Training Agent"],

        # FINANCE EVENTS
        "opportunity.created": ["Opportunity Tracker Agent", "CFO Agent", "KPI Agent"],
        "opportunity.closed": ["CFO Agent", "Revenue Recognition Agent", "KPI Agent"],
        "revenue.recognized": ["CFO Agent", "Margin Agent", "EBITDA Agent", "KPI Agent"],
        "invoice.issued": ["Revenue Recognition Agent", "Billing Agent"],
        "payment.received": ["CFO Agent", "Cash Flow Agent", "KPI Agent"],

        # KPI EVENTS
        "target.at_risk": ["KPI Agent", "Risk Agent", "CEO"],
        "forecast.updated": ["Forecast Agent", "KPI Agent", "CEO"],
        "alert.critical": ["Risk Agent", "CEO"],
    }

    @staticmethod
    def publish_event(
        db: Session,
        event_type: str,
        source_agent: str,
        entity_id: str,
        entity_type: str,
        current_state: Optional[str] = None,
        new_state: Optional[str] = None,
        payload: Optional[Dict] = None,
        confidence: int = 85,
        action_required: Optional[str] = None,
        owner: Optional[str] = None,
        deadline: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Publish a structured event for other agents to consume.

        Example:
        - Thunder agent qualifies a candidate
        - Publishes: event_type="candidate.qualified", entity_id=candidate_123
        - Target agents (Interview Reminder, KPI Agent) consume event
        - Interview Reminder schedules interview
        - KPI Agent updates funnel metrics
        """

        try:
            event = AgentEvent(
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type=event_type,
                source_agent=source_agent,
                target_agents=",".join(AgentEventService.EVENT_TYPES.get(event_type, [])),
                entity_id=entity_id,
                entity_type=entity_type,
                current_state=current_state,
                new_state=new_state,
                payload=payload or {},
                confidence=confidence,
                action_required=action_required,
                owner=owner,
                deadline=deadline,
                status="PENDING",
            )

            db.add(event)
            db.commit()

            return {
                "status": "published",
                "event_id": event.event_id,
                "event_type": event_type,
                "source_agent": source_agent,
                "target_agents": event.target_agents.split(",") if event.target_agents else [],
                "entity_id": entity_id,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_pending_events(db: Session, agent_name: str) -> list:
        """Get all pending events that target this agent."""

        try:
            events = db.query(AgentEvent).filter(
                AgentEvent.status == "PENDING",
                AgentEvent.target_agents.like(f"%{agent_name}%"),
            ).all()

            return [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "source_agent": e.source_agent,
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type,
                    "current_state": e.current_state,
                    "new_state": e.new_state,
                    "payload": e.payload,
                    "action_required": e.action_required,
                    "deadline": e.deadline.isoformat() if e.deadline else None,
                }
                for e in events
            ]

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            # CRITICAL FIX: Raise error instead of returning empty list
            raise Exception(f"Failed to get pending events for agent {agent_name}: {str(e)}")

    @staticmethod
    def consume_event(
        db: Session,
        event_id: str,
        consumer_agent: str,
        action_taken: str,
    ) -> Dict[str, Any]:
        """Mark event as consumed by an agent."""

        try:
            event = db.query(AgentEvent).filter(AgentEvent.event_id == event_id).first()

            if not event:
                return {"status": "error", "message": "Event not found"}

            # Append to audit trail
            audit = json.loads(event.audit_trail) if event.audit_trail else []
            audit.append({
                "agent": consumer_agent,
                "action": action_taken,
                "timestamp": datetime.utcnow().isoformat(),
            })

            event.audit_trail = json.dumps(audit)
            event.processed_at = datetime.utcnow()
            event.status = "PROCESSED"

            db.commit()

            return {
                "status": "consumed",
                "event_id": event_id,
                "consumer_agent": consumer_agent,
                "action": action_taken,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            return {"status": "error", "message": str(e)}

    @staticmethod
    def escalate_event(
        db: Session,
        event_id: str,
        reason: str,
        escalate_to: str = "CEO",
    ) -> Dict[str, Any]:
        """Escalate event that needs human decision."""

        try:
            event = db.query(AgentEvent).filter(AgentEvent.event_id == event_id).first()

            if not event:
                return {"status": "error", "message": "Event not found"}

            event.status = "ESCALATED"
            event.owner = escalate_to
            event.action_required = reason

            db.commit()

            return {
                "status": "escalated",
                "event_id": event_id,
                "reason": reason,
                "escalate_to": escalate_to,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            return {"status": "error", "message": str(e)}


# EXAMPLE AGENT WORKFLOWS (How agents talk to each other)

def example_recruitment_workflow():
    """
    How Thunder + HR + Onboarding agents coordinate:

    1. Thunder publishes: "candidate.qualified" event
       └─ Target agents: Recruitment Agent, Interview Reminder, KPI Agent

    2. Interview Reminder consumes event
       └─ Action: Schedule interview for candidate
       └─ Publishes: "candidate.interviewed" event

    3. HR Agent consumes "candidate.interviewed"
       └─ Checks: Is this a good match?
       └─ Action: Send offer if qualified
       └─ Publishes: "candidate.offered" event

    4. Onboarding Agent consumes "candidate.offered"
       └─ Action: Prepare onboarding plan
       └─ Publishes: "candidate.accepted" event when offer signed

    5. KPI Agent consumes ALL events
       └─ Updates: Recruitment funnel metrics
       └─ Calculates: Progress toward 2000 employee target
    """
    pass


def example_resource_workflow():
    """
    How Resource Management + HR + KPI agents coordinate:

    1. Employee onboarded
       └─ HR Agent publishes: "employee.onboarded"

    2. Resource Management consumes "employee.onboarded"
       └─ Action: Assign to project
       └─ Publishes: "employee.assigned_to_project"

    3. KPI Agent consumes all resource events
       └─ Updates: Utilization %, headcount, allocation tracking
       └─ Publishes: "alert.critical" if utilization falls below 70%

    4. CEO consumes "alert.critical"
       └─ Reads alert
       └─ May publish: "resource_reallocation_needed" event
    """
    pass


def example_financial_workflow():
    """
    How Finance agents coordinate:

    1. Opportunity closed
       └─ Opportunity Tracker publishes: "opportunity.closed"

    2. CFO Agent consumes "opportunity.closed"
       └─ Action: Recognize revenue
       └─ Publishes: "revenue.recognized"

    3. Margin Agent consumes "revenue.recognized"
       └─ Calculates: Profitability

    4. KPI Agent consumes all financial events
       └─ Updates: Progress toward $100M revenue target
    """
    pass
