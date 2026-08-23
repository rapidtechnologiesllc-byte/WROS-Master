"""
Agent Orchestration Service - Flash Orchestrator

The ONLY thing that decides what runs when.

Pipeline Architecture (Message Queue Based):
1. Flash puts messages on agent input queues
2. Each agent consumes from input queue, processes, puts output on next queue
3. All progress visible via message queue monitoring

Pipeline:
  Thunder Input Q → Thunder processes (contacts 15) → Recruitment Input Q
  Recruitment Input Q → Recruiter screens → Interview Scheduler Input Q
  Interview Scheduler Input Q → Scheduler books interviews → Hiring Panel Input Q
  Hiring Panel Input Q → Panel interviews → Offer Generator Input Q
  Offer Generator Input Q → Gen creates offers → Thunder Negotiation Input Q
  Thunder Negotiation Input Q → Thunder closes deals → HR Input Q
  HR Input Q → HR creates employee accounts → Onboarding Input Q
  Onboarding Input Q → Onboarding Agent completes workflow → Resource Mgmt Input Q
  Resource Mgmt Input Q → Resource Manager deploys to projects → Success

Message format:
{
  "id": "candidate_123",
  "type": "candidate_engagement",
  "stage": "contacted",  # contacted → qualified → interview_scheduled → interviewed → offer_sent → offer_accepted → hired → onboarded → deployed
  "data": {
    "candidate_id": "...",
    "engagement_data": {...},
    "interview_scores": {...},
    "offer_details": {...},
    etc.
  },
  "timestamp": "2026-08-23T10:00:00Z"
}
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import json
import uuid

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.offer_letter import OfferLetter
from app.models.employee import Employee
from app.api.v1.endpoints.admin_queue import TaskStatus


class AgentQueue:
    """Message queue for agent input/output."""

    _queues = {}  # {queue_name: [messages]}

    @classmethod
    def put_message(cls, queue_name: str, message: Dict) -> str:
        """Put a message on a queue."""
        if queue_name not in cls._queues:
            cls._queues[queue_name] = []

        message_id = str(uuid.uuid4())
        message["_queue_id"] = message_id
        message["_enqueued_at"] = datetime.utcnow().isoformat()

        cls._queues[queue_name].append(message)

        logger.info(f"[Queue] {queue_name} += 1 (now {len(cls._queues[queue_name])})")

        return message_id

    @classmethod
    def get_message(cls, queue_name: str) -> Optional[Dict]:
        """Get next message from queue (FIFO)."""
        if queue_name not in cls._queues or len(cls._queues[queue_name]) == 0:
            return None

        message = cls._queues[queue_name].pop(0)
        message["_dequeued_at"] = datetime.utcnow().isoformat()

        logger.info(f"[Queue] {queue_name} -= 1 (now {len(cls._queues[queue_name])})")

        return message

    @classmethod
    def peek_queue(cls, queue_name: str) -> List[Dict]:
        """Peek at queue without removing messages."""
        return cls._queues.get(queue_name, []).copy()

    @classmethod
    def queue_depth(cls, queue_name: str) -> int:
        """Get queue length."""
        return len(cls._queues.get(queue_name, []))

    @classmethod
    def get_all_queues(cls) -> Dict[str, int]:
        """Get all queue depths."""
        return {name: len(msgs) for name, msgs in cls._queues.items()}


class FlashOrchestrator:
    """
    Flash orchestrates the pipeline.

    Daily rhythm:
    1. 8:00 AM: Get candidate pool from Thunder's backlog
    2. 8:05 AM: Put 15 candidates on Thunder Input Q
    3. 8:30 AM: Check progress (what's in each queue?)
    4. 8:45 AM: Identify bottlenecks (which queue is stuck?)
    5. 9:00 AM: Escalate if needed
    6. Daily: Monitor all queues
    """

    # Queue names
    QUEUES = {
        "thunder_input": "Thunder_Input",
        "recruitment_input": "Recruitment_Input",
        "interview_scheduler_input": "InterviewScheduler_Input",
        "hiring_panel_input": "HiringPanel_Input",
        "offer_generator_input": "OfferGenerator_Input",
        "thunder_negotiation_input": "ThunderNegotiation_Input",
        "hr_input": "HR_Input",
        "onboarding_input": "Onboarding_Input",
        "resource_mgmt_input": "ResourceMgmt_Input",
    }

    @staticmethod
    def initiate_candidate_flow(db: Session, candidate_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Put a candidate on the pipeline.
        Flash puts message on Thunder's input queue.
        """

        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            return {"status": "error", "message": "Candidate not found"}

        # Create pipeline message
        message = {
            "id": f"pipeline_{candidate_id}_{datetime.utcnow().timestamp()}",
            "candidate_id": candidate_id,
            "type": "candidate_pipeline",
            "stage": "thunder_contact",  # First stage
            "data": {
                "candidate_id": candidate_id,
                "candidate_name": candidate.candidate_name,
                "candidate_email": candidate.candidate_email,
                "candidate_phone": candidate.candidate_phone,
                "job_title": candidate.job_title,
            }
        }

        # Put on Thunder's input queue
        queue_id = AgentQueue.put_message(FlashOrchestrator.QUEUES["thunder_input"], message)

        logger.info(f"[Flash] Initiated pipeline for {candidate_id}")

        return {
            "status": "success",
            "message": "Candidate added to pipeline",
            "queue_id": queue_id,
            "pipeline_id": message["id"]
        }

    @staticmethod
    def get_pipeline_status(tenant_id: str) -> Dict[str, Any]:
        """
        Get status of the entire pipeline (all queues).

        Shows which queues are clogged, which items are stuck.
        """

        queue_depths = AgentQueue.get_all_queues()

        # Find bottlenecks
        bottlenecks = []
        for queue_name, depth in queue_depths.items():
            if depth > 5:
                bottlenecks.append({
                    "queue": queue_name,
                    "depth": depth,
                    "issue": "Queue backing up - downstream agent may be slow"
                })

        # Expected flow (if all agents working):
        # Thunder contacts 15 → 6 qualified (40%) → 4 scheduled (60%) → 4 interviewed (100%)
        # → 2 offers (50%) → 1.6 accepted (80%) → 1.6 hired → 1.5 onboarded → 1.5 deployed

        expected_flow = {
            "thunder_input": "15 candidates to contact",
            "recruitment_input": "6 qualified (40% conversion)",
            "interview_scheduler_input": "4 scheduled (60% conversion)",
            "hiring_panel_input": "4 interviews (100% of scheduled)",
            "offer_generator_input": "2 offers (50% conversion)",
            "thunder_negotiation_input": "2 offers ready to close",
            "hr_input": "1-2 accepted offers",
            "onboarding_input": "1-2 new hires onboarding",
            "resource_mgmt_input": "1-2 onboarded employees deploying"
        }

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "queue_status": queue_depths,
            "bottlenecks": bottlenecks,
            "bottleneck_count": len(bottlenecks),
            "health": (
                "🔴 CRITICAL - Multiple queues clogged" if len(bottlenecks) >= 3
                else "🟡 WARNING - Some queues backing up" if len(bottlenecks) >= 1
                else "🟢 HEALTHY - All queues flowing"
            ),
            "expected_flow": expected_flow,
            "recommendation": FlashOrchestrator._get_recommendation(bottlenecks)
        }

    @staticmethod
    def _get_recommendation(bottlenecks: List) -> str:
        """Get Flash's recommendation based on bottlenecks."""

        if not bottlenecks:
            return "Pipeline flowing smoothly. Continue monitoring."

        worst = sorted(bottlenecks, key=lambda x: x["depth"], reverse=True)[0]
        queue_name = worst["queue"]

        if "thunder_input" in queue_name:
            return "Thunder's input queue full - too many candidates queued. Slow down intake."
        elif "recruitment_input" in queue_name:
            return "Recruitment Agent screening slow - check qualifier criteria or assign more reviewers."
        elif "interview_scheduler_input" in queue_name:
            return "Interview Scheduler backed up - hiring managers not available. Check calendar availability."
        elif "hiring_panel_input" in queue_name:
            return "Panel interviews building up - schedule more interview slots."
        elif "offer_generator_input" in queue_name:
            return "Offer Generator slow - check personalization logic or offer approval process."
        elif "thunder_negotiation_input" in queue_name:
            return "Thunder closing offers slow - low acceptance rate. Review offer personalization."
        elif "hr_input" in queue_name:
            return "HR processing slow - employee setup taking time. Check onboarding prerequisites."
        elif "onboarding_input" in queue_name:
            return "Onboarding Agent behind - check 30/60/90 day workflow execution."
        elif "resource_mgmt_input" in queue_name:
            return "Resource Manager deployment slow - check bench or project allocation."

        return "Investigate bottleneck."

    @staticmethod
    def get_queue_item_detail(queue_name: str, index: int = 0) -> Optional[Dict]:
        """Get details of a specific item stuck in a queue."""
        messages = AgentQueue.peek_queue(queue_name)
        if index < len(messages):
            return messages[index]
        return None


class ThunderAgent:
    """
    Thunder AI Recruiter - Stage 1

    Input: Candidate to contact
    Output: Engagement data (contacted, response rate, engagement score)
    Next stage: Recruitment Screener
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 5) -> Dict[str, Any]:
        """Process batch of candidates from input queue."""

        processed = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["thunder_input"])

            if not message:
                break

            candidate_id = message.get("candidate_id")

            # Simulate contacting candidate (in real system: email + WhatsApp)
            engagement_data = {
                "contacted": True,
                "channel": "email",
                "response_received": True,
                "engagement_score": 0.75,  # 1-10 scale
                "interest_level": "high"
            }

            # Put on next queue (Recruitment Screener)
            next_message = {
                **message,
                "stage": "recruitment_screening",
                "thunder_result": engagement_data
            }

            AgentQueue.put_message(
                FlashOrchestrator.QUEUES["recruitment_input"],
                next_message
            )

            processed += 1

        return {
            "agent": "Thunder",
            "processed": processed,
            "messages_moved": f"{FlashOrchestrator.QUEUES['thunder_input']} → {FlashOrchestrator.QUEUES['recruitment_input']}"
        }


class RecruitmentScreenerAgent:
    """
    Recruitment Screener - Stage 2

    Input: Engaged candidates
    Output: Qualified/rejected decision
    Next stage: Interview Scheduler (if qualified)
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 3) -> Dict[str, Any]:
        """Screen candidates from Thunder."""

        qualified = 0
        rejected = 0

        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["recruitment_input"])

            if not message:
                break

            # Simple screening: if engagement > 0.7, qualify
            engagement = message.get("thunder_result", {}).get("engagement_score", 0)

            if engagement > 0.7:
                qualified += 1
                next_message = {
                    **message,
                    "stage": "interview_scheduling",
                    "screening_result": {"status": "qualified", "score": engagement}
                }

                AgentQueue.put_message(
                    FlashOrchestrator.QUEUES["interview_scheduler_input"],
                    next_message
                )
            else:
                rejected += 1
                # Rejected candidates dropped

        return {
            "agent": "Recruitment Screener",
            "qualified": qualified,
            "rejected": rejected,
            "conversion_rate": f"{(qualified / max(qualified + rejected, 1) * 100):.0f}%"
        }


class InterviewSchedulerAgent:
    """
    Interview Scheduler - Stage 3

    Input: Qualified candidates
    Output: Interview scheduled (date/time confirmed)
    Next stage: Hiring Panel
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 2) -> Dict[str, Any]:
        """Schedule interviews with hiring managers."""

        scheduled = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["interview_scheduler_input"])

            if not message:
                break

            # Simulate scheduling
            interview_data = {
                "scheduled": True,
                "interview_date": (datetime.utcnow() + timedelta(days=2)).date().isoformat(),
                "interview_time": "2:00 PM",
                "panel_members": ["hiring_manager@company.com"]
            }

            next_message = {
                **message,
                "stage": "interview_scheduled",
                "interview_details": interview_data
            }

            AgentQueue.put_message(
                FlashOrchestrator.QUEUES["hiring_panel_input"],
                next_message
            )

            scheduled += 1

        return {
            "agent": "Interview Scheduler",
            "interviews_scheduled": scheduled
        }


class HiringPanelAgent:
    """
    Hiring Panel - Stage 4

    Input: Scheduled interviews
    Output: Interview scores & feedback
    Next stage: Offer Generator
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 2) -> Dict[str, Any]:
        """Conduct interviews and provide feedback."""

        interviewed = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["hiring_panel_input"])

            if not message:
                break

            # Simulate interview
            interview_score = 0.75  # Average score (0-1)

            next_message = {
                **message,
                "stage": "offer_generation",
                "interview_result": {
                    "score": interview_score,
                    "feedback": "Strong technical skills, great communication",
                    "recommended": interview_score > 0.6
                }
            }

            if interview_score > 0.5:
                AgentQueue.put_message(
                    FlashOrchestrator.QUEUES["offer_generator_input"],
                    next_message
                )
                interviewed += 1

        return {
            "agent": "Hiring Panel",
            "interviews_completed": interviewed
        }


class OfferGeneratorAgent:
    """
    Offer Generator - Stage 5

    Input: Interview results
    Output: Personalized offer
    Next stage: Thunder (Negotiation)
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 1) -> Dict[str, Any]:
        """Generate personalized offers."""

        offers_created = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["offer_generator_input"])

            if not message:
                break

            # Personalize offer based on Thunder's personal intelligence
            offer = {
                "salary": 120000,
                "benefits": "Standard + remote flexibility",
                "start_date": (datetime.utcnow() + timedelta(days=14)).date().isoformat()
            }

            next_message = {
                **message,
                "stage": "offer_acceptance",
                "offer_details": offer
            }

            AgentQueue.put_message(
                FlashOrchestrator.QUEUES["thunder_negotiation_input"],
                next_message
            )

            offers_created += 1

        return {
            "agent": "Offer Generator",
            "offers_created": offers_created
        }


class ThunderNegotiationAgent:
    """
    Thunder Negotiation - Stage 6

    Input: Generated offers
    Output: Offer accepted (or rejected)
    Next stage: HR (Employee Creation)
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 1) -> Dict[str, Any]:
        """Close offer negotiations."""

        accepted = 0
        rejected = 0

        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["thunder_negotiation_input"])

            if not message:
                break

            # 80% offer acceptance rate
            if datetime.utcnow().timestamp() % 10 > 2:  # 80% probability
                accepted += 1
                next_message = {
                    **message,
                    "stage": "hiring",
                    "offer_status": "accepted"
                }

                AgentQueue.put_message(
                    FlashOrchestrator.QUEUES["hr_input"],
                    next_message
                )
            else:
                rejected += 1

        return {
            "agent": "Thunder (Negotiation)",
            "accepted": accepted,
            "rejected": rejected
        }


class HRAgent:
    """
    HR Agent - Stage 7

    Input: Accepted offers
    Output: Employee account created
    Next stage: Onboarding Agent
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 1) -> Dict[str, Any]:
        """Create employee accounts."""

        created = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["hr_input"])

            if not message:
                break

            # Create employee record
            next_message = {
                **message,
                "stage": "onboarding",
                "employee_created": True
            }

            AgentQueue.put_message(
                FlashOrchestrator.QUEUES["onboarding_input"],
                next_message
            )

            created += 1

        return {
            "agent": "HR Agent",
            "employees_created": created
        }


class OnboardingAgent:
    """
    Onboarding Agent - Stage 8

    Input: New employee accounts
    Output: Onboarding complete (30/60/90)
    Next stage: Resource Manager
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 1) -> Dict[str, Any]:
        """Complete onboarding workflow."""

        onboarded = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["onboarding_input"])

            if not message:
                break

            # Complete onboarding
            next_message = {
                **message,
                "stage": "resource_deployment",
                "onboarding_complete": True
            }

            AgentQueue.put_message(
                FlashOrchestrator.QUEUES["resource_mgmt_input"],
                next_message
            )

            onboarded += 1

        return {
            "agent": "Onboarding Agent",
            "onboarded": onboarded
        }


class ResourceManagerAgent:
    """
    Resource Manager - Stage 9 (Final)

    Input: Onboarded employees
    Output: Deployed to projects (revenue generating)
    """

    @staticmethod
    def process_batch(db: Session, batch_size: int = 1) -> Dict[str, Any]:
        """Deploy employees to projects."""

        deployed = 0
        for _ in range(batch_size):
            message = AgentQueue.get_message(FlashOrchestrator.QUEUES["resource_mgmt_input"])

            if not message:
                break

            # Deploy to project
            deployed_record = {
                **message,
                "stage": "deployed",
                "project_id": "project_123",
                "deployment_date": datetime.utcnow().isoformat(),
                "status": "productive"
            }

            # Done! Remove from queues
            logger.info(f"[Pipeline] COMPLETE: {message.get('candidate_id')} → Deployed")

            deployed += 1

        return {
            "agent": "Resource Manager",
            "deployed": deployed,
            "pipeline_complete": deployed > 0
        }
