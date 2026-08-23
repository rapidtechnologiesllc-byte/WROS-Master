"""
Pipeline Orchestration API - Trigger and monitor 8-agent hiring pipeline.

Endpoints:
- POST /pipeline/start/{candidate_id} - Start pipeline for a candidate
- GET /pipeline/status - See all queues (bottleneck visibility)
- POST /pipeline/execute-agents - Run all agents for 1 cycle
- GET /pipeline/queue/{queue_name} - Peek at specific queue
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_recruiter
from app.services.agent_orchestration_service import (
    FlashOrchestrator,
    ThunderAgent,
    RecruitmentScreenerAgent,
    InterviewSchedulerAgent,
    HiringPanelAgent,
    OfferGeneratorAgent,
    ThunderNegotiationAgent,
    HRAgent,
    OnboardingAgent,
    ResourceManagerAgent,
    AgentQueue,
)
from app.core.logging import logger

router = APIRouter(prefix="/pipeline", tags=["pipeline-orchestration"])


@router.post("/start/{candidate_id}")
async def start_candidate_pipeline(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter),
):
    """
    Start the 8-agent pipeline for a candidate.

    Flash puts candidate on Thunder's input queue.
    All subsequent agents consume from their input queue.
    """
    try:
        result = FlashOrchestrator.initiate_candidate_flow(
            db=db,
            candidate_id=candidate_id,
            tenant_id=current_user.tenant_id
        )

        return {
            "status": "success",
            "message": "Candidate added to pipeline",
            "data": result,
            "next_step": "Execute agents to process through pipeline (POST /pipeline/execute-agents)",
            "monitor_at": "/pipeline/status"
        }

    except Exception as e:
        logger.error(f"Error starting pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_pipeline_status(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter),
):
    """
    Get complete pipeline status - which queues have items, which are clogged.

    Shows:
    - Each queue depth (how many items waiting)
    - Bottlenecks (queues backing up)
    - Flash's recommendation (what to fix)
    """
    try:
        status = FlashOrchestrator.get_pipeline_status(current_user.tenant_id)

        return {
            "status": "success",
            "data": status,
            "how_to_read": {
                "queue_status": "Number of messages in each queue (higher = more backed up)",
                "bottlenecks": "Queues with >5 items (agent falling behind)",
                "health": "🟢 HEALTHY (flowing) vs 🟡 WARNING (slow) vs 🔴 CRITICAL (stuck)",
                "recommendation": "What Flash recommends fixing"
            }
        }

    except Exception as e:
        logger.error(f"Error getting pipeline status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-agents")
async def execute_all_agents(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter),
):
    """
    Execute all 8 agents for 1 cycle.

    Flash orchestrates:
    1. Thunder processes 5 candidates from input queue
    2. Recruitment Screener screens 3 from Thunder's output
    3. Interview Scheduler schedules 2 from Recruitment output
    4. Hiring Panel interviews 2 scheduled
    5. Offer Generator creates 1 offer
    6. Thunder Negotiation closes 1 offer
    7. HR creates 1 employee account
    8. Onboarding completes 1 workflow
    9. Resource Manager deploys 1 employee

    One execution cycle = one candidate potentially making it 1-2 stages forward.
    """
    try:
        results = {
            "status": "success",
            "timestamp": str(__import__("datetime").datetime.utcnow()),
            "cycle": "Flash orchestration cycle",
            "agents": []
        }

        # Execute each agent in sequence
        thunder_result = ThunderAgent.process_batch(db, batch_size=5)
        results["agents"].append(thunder_result)

        screener_result = RecruitmentScreenerAgent.process_batch(db, batch_size=3)
        results["agents"].append(screener_result)

        scheduler_result = InterviewSchedulerAgent.process_batch(db, batch_size=2)
        results["agents"].append(scheduler_result)

        panel_result = HiringPanelAgent.process_batch(db, batch_size=2)
        results["agents"].append(panel_result)

        offer_result = OfferGeneratorAgent.process_batch(db, batch_size=1)
        results["agents"].append(offer_result)

        negotiation_result = ThunderNegotiationAgent.process_batch(db, batch_size=1)
        results["agents"].append(negotiation_result)

        hr_result = HRAgent.process_batch(db, batch_size=1)
        results["agents"].append(hr_result)

        onboarding_result = OnboardingAgent.process_batch(db, batch_size=1)
        results["agents"].append(onboarding_result)

        resource_result = ResourceManagerAgent.process_batch(db, batch_size=1)
        results["agents"].append(resource_result)

        # Calculate throughput
        total_started = thunder_result.get("processed", 0)
        total_deployed = resource_result.get("deployed", 0)

        results["summary"] = {
            "cycle_throughput": f"{total_deployed} candidate(s) completed full pipeline",
            "started": total_started,
            "deployed": total_deployed,
            "efficiency": f"{(total_deployed / max(total_started, 1) * 100):.0f}%" if total_started > 0 else "N/A"
        }

        results["next_step"] = "Check /pipeline/status to see bottlenecks"

        return results

    except Exception as e:
        logger.error(f"Error executing agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{queue_name}")
async def peek_queue(
    queue_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter),
):
    """
    Peek at a specific queue - see what's stuck waiting.

    Use this to investigate bottlenecks:
    - If Thunder_Input has 20 items → too many contacts queued
    - If Recruitment_Input has 15 items → screener is slow
    - If HiringPanel_Input has 5 items → panel not interviewing fast enough
    """
    try:
        messages = AgentQueue.peek_queue(queue_name)

        return {
            "status": "success",
            "queue": queue_name,
            "depth": len(messages),
            "messages": messages,
            "interpretation": {
                "Thunder_Input": "Candidates waiting to be contacted",
                "Recruitment_Input": "Engaged candidates waiting to be screened",
                "InterviewScheduler_Input": "Qualified candidates waiting for interview scheduling",
                "HiringPanel_Input": "Scheduled interviews waiting to be conducted",
                "OfferGenerator_Input": "Interview results waiting for offer generation",
                "ThunderNegotiation_Input": "Offers waiting for candidate negotiation/close",
                "HR_Input": "Accepted offers waiting for employee account creation",
                "Onboarding_Input": "New employees waiting for onboarding",
                "ResourceMgmt_Input": "Onboarded employees waiting for project deployment"
            }
        }

    except Exception as e:
        logger.error(f"Error peeking queue {queue_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run-demo")
async def run_demo_pipeline(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter),
):
    """
    DEMO: Show the complete pipeline working end-to-end.

    Simulates:
    1. Add 5 candidates to Thunder queue
    2. Run 10 agent cycles to process them through pipeline
    3. Show final status (how many made it to deployment)
    """
    try:
        # Get 5 candidates from database
        from app.models.candidate import Candidate

        candidates = db.query(Candidate).filter(
            Candidate.tenant_id == current_user.tenant_id
        ).limit(5).all()

        if not candidates:
            return {
                "status": "error",
                "message": "No candidates found in database. Add candidates first."
            }

        demo_result = {
            "status": "running_demo",
            "candidates_added": 0,
            "cycles": 10,
            "demo_steps": []
        }

        # Step 1: Add candidates to pipeline
        for candidate in candidates:
            result = FlashOrchestrator.initiate_candidate_flow(
                db=db,
                candidate_id=candidate.candidateID,
                tenant_id=current_user.tenant_id
            )
            if result.get("status") == "success":
                demo_result["candidates_added"] += 1

        demo_result["demo_steps"].append({
            "step": 1,
            "action": f"Added {demo_result['candidates_added']} candidates to Thunder queue",
            "queue_status": AgentQueue.get_all_queues()
        })

        # Step 2: Run 10 cycles of agent execution
        for cycle in range(10):
            thunder_res = ThunderAgent.process_batch(db, 3)
            screen_res = RecruitmentScreenerAgent.process_batch(db, 2)
            sched_res = InterviewSchedulerAgent.process_batch(db, 1)
            panel_res = HiringPanelAgent.process_batch(db, 1)
            offer_res = OfferGeneratorAgent.process_batch(db, 1)
            neg_res = ThunderNegotiationAgent.process_batch(db, 1)
            hr_res = HRAgent.process_batch(db, 1)
            onboard_res = OnboardingAgent.process_batch(db, 1)
            resource_res = ResourceManagerAgent.process_batch(db, 1)

            demo_result["demo_steps"].append({
                "cycle": cycle + 1,
                "agents_executed": [
                    f"Thunder: {thunder_res.get('processed', 0)}",
                    f"Screener: {screen_res.get('qualified', 0)} qualified",
                    f"Scheduler: {sched_res.get('interviews_scheduled', 0)} scheduled",
                    f"Panel: {panel_res.get('interviews_completed', 0)} interviewed",
                    f"Offer: {offer_res.get('offers_created', 0)} offers",
                    f"Negotiation: {neg_res.get('accepted', 0)} accepted",
                    f"HR: {hr_res.get('employees_created', 0)} hired",
                    f"Onboarding: {onboard_res.get('onboarded', 0)} onboarded",
                    f"Resource: {resource_res.get('deployed', 0)} deployed"
                ],
                "deployed_this_cycle": resource_res.get("deployed", 0),
                "queue_status": AgentQueue.get_all_queues()
            })

        # Final status
        final_status = FlashOrchestrator.get_pipeline_status(current_user.tenant_id)

        demo_result["final_status"] = final_status
        demo_result["conclusion"] = {
            "total_candidates_started": demo_result["candidates_added"],
            "queues_remaining": sum(AgentQueue.get_all_queues().values()),
            "health": final_status["health"],
            "recommendation": final_status["recommendation"]
        }

        return demo_result

    except Exception as e:
        logger.error(f"Error running demo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
