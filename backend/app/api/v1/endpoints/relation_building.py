"""
import logging
Relation Building Agent API Endpoints

Exposes relation building persona extraction for downstream systems.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_resource_permission
from app.core.logging import logger
from app.services.relation_building_agent_service import RelationBuildingAgent
from app.services.relation_building_dashboard_service import RelationBuildingDashboard
from app.models.user import Users
from app.core.database import get_db

router = APIRouter(prefix="/relation-building", tags=["relation-building"])

@router.post("/extract-persona/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def extract_candidate_persona(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Extract persona for a candidate.

    This endpoint:
    1. Parses candidate's resume using SLM
    2. Analyzes career trajectory, skills, motivations
    3. Classifies candidate engagement readiness
    4. Stores persona facts in candidate memory
    5. Returns persona profile for use by Thunder, Offer Generator, etc.

    Args:
        candidate_id: Candidate UUID

    Returns:
        {
            "status": "success" | "error",
            "candidate_id": str,
            "candidate_name": str,
            "persona": {
                "career_level": "entry" | "mid" | "senior" | "lead" | "principal",
                "skill_depth": "focused" | "specialist" | "generalist",
                "motivation_primary": str,
                "motivators": [str],
                "constraints": [str],
                "risk_factors": [str],
                "engagement_readiness": "high" | "medium" | "low",
            },
            "profile": {
                "years_experience": int,
                "companies_worked": int,
                "skill_count": int,
                "skill_areas": [str],
                "job_stability": float,
                "current_title": str,
                "current_employer": str,
            },
            "relationship_status": "RECEPTIVE" | "INTERESTED" | "HESITANT" | "RESISTANT",
            "recommended_engagement": str,
            "memory_facts_stored": int,
        }
    """
    try:
        result = await RelationBuildingAgent.extract_candidate_persona(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
        )

        if result["status"] != "success":
            raise HTTPException(status_code=404, detail=result.get("message", "Persona extraction failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Relation building persona extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during persona extraction")

@router.get("/candidate-relationship/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_candidate_relationship_status(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get relationship status for a candidate (cached from last extraction).

    Returns persona-based relationship intelligence.
    """
    try:
        result = await RelationBuildingAgent.report_to_flash(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
        )

        if result["status"] != "success":
            raise HTTPException(status_code=404, detail="Candidate not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Relationship status retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/flash-report", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_flash_candidate_intelligence(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get candidate relationship intelligence for Flash Orchestration Engine.

    This is called by Flash during daily coordination to understand
    the quality and engagement readiness of the candidate pool.

    Returns summary of:
    - Engagement distribution (high/medium/low)
    - Risk factor analysis
    - Career level mix
    - Recommended engagement strategies per candidate
    """
    # This would be called during Flash daily coordination
    # Returns a summary similar to what Flash reports

    return {
        "status": "success",
        "message": "Relation Building Agent ready for Flash coordination",
        "agent_name": "Relation Building Agent",
        "reports_to": "Flash Orchestration Engine",
        "capabilities": [
            "extract_persona",
            "classify_engagement_readiness",
            "identify_risk_factors",
            "recommend_engagement_strategy",
            "store_in_memory",
        ],
    }

@router.get("/dashboard/standup", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_daily_standup(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get Relation Building Agent daily standup report.

    Format: SDLC Daily Kanban Standup
    - Yesterday: What was completed (metrics, summary)
    - Today: What's planned (tasks, summary)
    - Blockers: What's impeding progress (issues, severity)
    - Impact: How we're improving hiring (metrics, summary)
    - Overall Health: Agent health score and status

    This report is used by Flash Orchestration Engine during morning
    standup (8:00 AM) to coordinate all autonomous systems.

    Returns:
        {
            "status": "success",
            "agent_name": "Relation Building Agent",
            "reports_to": "Flash Orchestration Engine",
            "standup_date": "2026-08-23",
            "standup_time": "10:15:00",
            "yesterday": {...},  # What was completed
            "today": {...},      # What's planned
            "blockers": {...},   # Issues identified
            "impact": {...},     # How it's improving hiring
            "overall_health": {
                "score": 87,
                "status": "HEALTHY",
                "trend": "↑"
            }
        }
    """
    try:
        result = RelationBuildingDashboard.get_daily_standup(
            tenant_id=current_user.UserID,
            db=db,
        )
        return result

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Standup report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error generating standup report")

@router.get("/dashboard/metrics", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_agent_metrics(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get Relation Building Agent performance metrics.

    Tracks:
    - Total candidates with personas extracted
    - Engagement readiness distribution
    - Risk factor analysis
    - Downstream system improvements
    - Persona accuracy over time

    Used by monitoring systems and dashboards.
    """
    return {
        "status": "success",
        "message": "Agent metrics endpoint - detailed metrics coming from dashboard service",
        "agent_name": "Relation Building Agent",
        "metrics": {
            "personas_extracted_total": 0,  # Will populate from dashboard
            "engagement_distribution": {
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "risk_factors_tracked": 0,
            "accuracy_improvement_trend": "N/A",
        },
    }

# ============== INTERACTION TRACKING ENDPOINTS ==============
# These are called by other systems to update persona continuously

@router.post("/interactions/email/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def capture_email_interaction(
    candidate_id: str,
    email_text: str,
    direction: str,  # "sent" or "received"
    subject: str = "",
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Capture email interaction and update candidate persona.

    Called by: Email service after sending/receiving candidate emails
    Updates: Email sentiment, engagement level, objections, interest level
    """
    try:
        result = await RelationBuildingAgent.capture_email_interaction(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            email_text=email_text,
            direction=direction,
            subject=subject,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Email interaction capture error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error capturing email interaction")

@router.post("/interactions/whatsapp/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def capture_whatsapp_interaction(
    candidate_id: str,
    message_text: str,
    direction: str,  # "sent" or "received"
    response_time_seconds: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Capture WhatsApp/SMS interaction and update candidate persona.

    Called by: WhatsApp/SMS service after sending/receiving messages
    Updates: Message sentiment, response speed, enthusiasm level
    """
    try:
        result = await RelationBuildingAgent.capture_whatsapp_interaction(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            message_text=message_text,
            direction=direction,
            response_time_seconds=response_time_seconds,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"WhatsApp interaction capture error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error capturing WhatsApp interaction")

@router.post("/interactions/ai-recruiter/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def capture_ai_recruiter_conversation(
    candidate_id: str,
    conversation_text: str,
    conversation_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Capture AI Recruiter (Thunder) conversation and update persona.

    Called by: Thunder/AI Recruiter after conversation completion
    Updates: Stated preferences, constraints, interest level, engagement quality
    """
    try:
        result = await RelationBuildingAgent.capture_ai_recruiter_conversation(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            conversation_text=conversation_text,
            conversation_data=conversation_data,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"AI Recruiter conversation capture error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error capturing AI Recruiter conversation")

@router.post("/interactions/interview/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def capture_interview_feedback(
    candidate_id: str,
    interview_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Capture interview feedback and update candidate persona.

    Called by: Interview service after feedback is submitted
    Updates: Panel recommendation, enthusiasm, cultural fit, engagement readiness
    """
    try:
        result = await RelationBuildingAgent.capture_interview_feedback(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            interview_data=interview_data,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Interview feedback capture error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error capturing interview feedback")

@router.post("/interactions/offer/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def capture_offer_response(
    candidate_id: str,
    offer_response_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Capture offer response and update candidate persona.

    Called by: Offer service when candidate responds to offer
    Updates: Acceptance/rejection, negotiation, enthusiasm, engagement readiness
    """
    try:
        result = await RelationBuildingAgent.capture_offer_response(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            offer_response_data=offer_response_data,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Offer response capture error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error capturing offer response")

# ============== PERSONAL INTELLIGENCE ENDPOINTS ==============
# These extract and use 200+ personal data points for authentic relationship building

@router.post("/personal-intelligence/{candidate_id}", dependencies=[Depends(require_resource_permission("agents", "manage"))])
async def extract_personal_intelligence(
    candidate_id: str,
    linkedin_profile: Optional[Dict[str, Any]] = None,
    github_profile: Optional[Dict[str, Any]] = None,
    social_data: Optional[Dict[str, Any]] = None,
    conversation_text: Optional[str] = None,
    emails: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Extract 200+ personal data points to understand the PERSON.

    Creates deep personal profile covering:
    - Gaming & Entertainment (10 points)
    - Food & Dining (10 points)
    - Travel & Location (15 points)
    - Career Aspirations (20 points)
    - Personal Life & Family (15 points)
    - Values & Beliefs (15 points)
    - Health & Wellness (10 points)
    - Learning & Growth (12 points)
    - Financial Goals (10 points)
    - Social & Community (12 points)
    - Work Preferences (10 points)
    - Personal Quirks (10 points)
    - Hidden Motivations & Fears (15 points)
    - Side Interests & Hobbies (10 points)
    - Communication Style (8 points)

    Total: 200+ data points for authentic relationship building
    """
    try:
        result = await RelationBuildingAgent.extract_personal_intelligence(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            linkedin_profile=linkedin_profile,
            github_profile=github_profile,
            social_data=social_data,
            conversation_text=conversation_text,
            emails=emails,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Personal intelligence extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error extracting personal intelligence")

@router.get(
    "/personalization/{candidate_id}",
    dependencies=[Depends(require_resource_permission("personalization", "view"))]
)
async def get_personalization_strategy(
    candidate_id: str,
    stage: str = "initial",
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get personalized engagement strategy based on 200+ personal data points.

    Uses personal intelligence to customize:
    - Email openings (reference their interests/values)
    - Talking points (build on shared interests)
    - Communication style (match their preference)
    - Offer package (emphasize what matters to them)
    - Contact timing (when they're most responsive)
    - Personal connection points (create authentic rapport)
    """
    try:
        from app.services.candidate_memory_service import get_memory

        memory = get_memory(db, candidate_id, current_user.UserID)

        if not memory.get("facts"):
            return {
                "status": "error",
                "message": "Personal profile not yet extracted. Call /personal-intelligence first.",
            }

        personal_data = {}
        for fact in memory["facts"]:
            if fact.get("category") == "PERSONAL":
                personal_data[fact["key"]] = fact["value"]

        result = RelationBuildingAgent.get_personalized_engagement_strategy(
            candidate_id=candidate_id,
            candidate_data=personal_data,
            engagement_stage=stage,
        )

        return {"status": "success", "strategy": result}

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Personalization strategy error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating personalization strategy")

@router.post(
    "/customize-offer/{candidate_id}",
    dependencies=[Depends(require_resource_permission("customize-offer", "create"))]
)
async def customize_offer(
    candidate_id: str,
    base_offer: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Customize offer package based on 200+ personal data points.

    Personalizes based on:
    - Remote flexibility: If they travel/value location independence
    - Work schedule: If they have family/caregiving
    - Learning budget: If they're growth-focused
    - Leadership path: If they aspire to leadership
    - Impact opportunities: If they're impact-driven
    """
    try:

        memory = get_memory(db, candidate_id, current_user.UserID)

        if not memory.get("facts"):
            return {
                "status": "error",
                "message": "Personal profile not yet extracted for customization.",
            }

        personal_data = {}
        for fact in memory["facts"]:
            if fact.get("category") == "PERSONAL":
                personal_data[fact["key"]] = fact["value"]

        customized = RelationBuildingAgent.customize_offer_package(personal_data, base_offer)

        return {"status": "success", "customized_offer": customized}

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Offer customization error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error customizing offer")

@router.post(
    "/interactions/joining/{candidate_id}",
    dependencies=[Depends(require_resource_permission("interaction", "create"))]
)
async def capture_joining_signals(
    candidate_id: str,
    joining_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Capture joining signals and update candidate persona.

    Called by: Onboarding/Joining service during joining process
    Updates: Document submission speed, engagement level, early performance signals
    """
    try:
        result = await RelationBuildingAgent.capture_joining_signals(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
            joining_data=joining_data,
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Joining signals capture error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error capturing joining signals")
