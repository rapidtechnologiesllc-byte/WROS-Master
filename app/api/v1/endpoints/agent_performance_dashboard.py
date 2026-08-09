"""Agent Performance Dashboard API - All 50+ agents with targets vs achievements."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.services.agent_performance_dashboard_service import AgentPerformanceDashboard
# from app.core.dependencies import get_current_user_or_none  # TODO: Implement auth

router = APIRouter(prefix="/dashboard/agents", tags=["agent-dashboard"])


@router.get("/all", dependencies=[Depends(require_permission("agent.view"))])
def get_all_agents_performance(
    db: Session = Depends(get_db),
):
    """
    Get performance for ALL 50+ agents.

    **Response includes:**
    - Agent name, domain, tier, strategic importance
    - FY target, achieved value, progress %
    - 2030 target, progress %
    - Gap (target - achieved)
    - Fear score (0-100)
    - Status (MOTIVATED, NEUTRAL, CONCERNED, DESPERATE, TERRIFIED)
    - Acceleration multiplier (how much faster needed)

    **Sorted by:** Strategic importance (CRITICAL first), then by fear score (highest risk first)

    **Example:**
    ```json
    {
      "total_agents": 50,
      "critical_agents": 15,
      "at_risk_agents": 8,
      "healthy_agents": 27,
      "agents": [
        {
          "agent_name": "Thunder",
          "domain": "recruitment",
          "strategic_importance": "CRITICAL",
          "fy_target": 250,
          "fy_achieved": 80,
          "fy_progress_pct": 32.0,
          "fear_score": 97.0,
          "status": "TERRIFIED",
          "acceleration_multiplier": 3.1
        },
        ...
      ]
    }
    ```
    """
    return AgentPerformanceDashboard.get_all_agents_performance(db)


@router.get("/by-tier/{tier}", dependencies=[Depends(require_permission("agent.view"))])
def get_agents_by_tier(
    tier: str,
    db: Session = Depends(get_db),
):
    """Get agents by tier."""
    agents = AgentPerformanceDashboard.get_agents_by_tier(db, tier)
    return {
        "status": "retrieved",
        "tier": tier,
        "agent_count": len(agents),
        "agents": agents,
    }


@router.get("/by-domain/{domain}", dependencies=[Depends(require_permission("agent.view"))])
def get_agents_by_domain(
    domain: str,
    db: Session = Depends(get_db),
):
    """Get agents by domain (recruitment, resource management, finance, etc.)."""
    agents = AgentPerformanceDashboard.get_agents_by_domain(db, domain)
    return {
        "status": "retrieved",
        "domain": domain,
        "agent_count": len(agents),
        "agents": agents,
    }


@router.get("/at-risk", dependencies=[Depends(require_permission("agent.view"))])
def get_at_risk_agents(
    db: Session = Depends(get_db),
):
    """
    Get agents with fear_score > 70 (DESPERATE or TERRIFIED).

    These agents need immediate intervention:
    - DESPERATE (60-70): Major gap, intervention needed
    - TERRIFIED (80+): Existential threat, escalate to leadership

    **Use this for:** CEO alerts, intervention queue, leadership escalations
    """
    agents = AgentPerformanceDashboard.get_at_risk_agents(db)
    return {
        "status": "retrieved",
        "at_risk_count": len(agents),
        "agents": agents,
    }


@router.get("/healthy", dependencies=[Depends(require_permission("agent.view"))])
def get_healthy_agents(
    db: Session = Depends(get_db),
):
    """
    Get agents with fear_score <= 50 (MOTIVATED or NEUTRAL).

    These agents are performing well and on track.

    **Use this for:** Benchmarking, best practices, recognition
    """
    agents = AgentPerformanceDashboard.get_healthy_agents(db)
    return {
        "status": "retrieved",
        "healthy_count": len(agents),
        "agents": agents,
    }


@router.get("/critical", dependencies=[Depends(require_permission("agent.view"))])
def get_critical_agents(
    db: Session = Depends(get_db),
):
    """
    Get CRITICAL strategic importance agents only.

    These are the agents that directly drive $100M revenue and 2000 headcount targets:
    - Thunder, Recruitment Agent, Resource Management Agent, CFO Agent, etc.

    **Use this for:** CEO dashboard, board reporting, executive decisions
    """
    agents = AgentPerformanceDashboard.get_critical_agents(db)
    return {
        "status": "retrieved",
        "critical_count": len(agents),
        "agents": agents,
    }


@router.get("/summary", dependencies=[Depends(require_permission("agent.view"))])
def get_progress_summary(
    db: Session = Depends(get_db),
):
    """
    Get summary of progress toward company targets.

    **Returns:**
    - $100M revenue: Current vs Target progress
    - 2000 headcount: Current vs Target progress
    - Agent health distribution

    **Example:**
    ```json
    {
      "revenue": {
        "target": "$100M",
        "achieved": "$28.5M",
        "progress_pct": 28.5
      },
      "headcount": {
        "target": 2000,
        "achieved": 119,
        "progress_pct": 5.95
      },
      "total_agents": 50,
      "critical_agents": 15,
      "at_risk_agents": 8,
      "healthy_agents": 27
    }
    ```
    """
    return AgentPerformanceDashboard.get_progress_summary(db)


@router.get("/dashboard/executive", dependencies=[Depends(require_permission("agent.view"))])
def get_executive_dashboard(
    db: Session = Depends(get_db),
):
    """
    Get comprehensive executive dashboard showing all agents and progress.

    **Sections:**
    1. Company Targets Progress ($100M / 2000 headcount)
    2. Critical Agents Performance (15 agents)
    3. At-Risk Agents (need intervention)
    4. Healthy Agents (on track)
    5. Agent Distribution by Tier and Domain
    6. Top Performers (lowest fear scores)
    7. Struggling Agents (highest fear scores)
    """
    all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)
    at_risk = AgentPerformanceDashboard.get_at_risk_agents(db)
    healthy = AgentPerformanceDashboard.get_healthy_agents(db)
    critical = AgentPerformanceDashboard.get_critical_agents(db)
    progress = AgentPerformanceDashboard.get_progress_summary(db)

    # Top performers (lowest fear, highest progress)
    top_performers = sorted(
        all_agents["agents"],
        key=lambda x: (-x.get("fy_progress_pct", 0), x.get("fear_score", 100))
    )[:10]

    # Struggling agents (highest fear)
    struggling = sorted(
        all_agents["agents"],
        key=lambda x: -x.get("fear_score", 0)
    )[:10]

    return {
        "status": "retrieved",
        "dashboard": "Executive Agent Performance",
        "timestamp": "",
        "progress": progress,
        "critical_agents": {
            "count": len(critical),
            "agents": critical,
        },
        "at_risk_agents": {
            "count": len(at_risk),
            "agents": at_risk[:10],  # Show top 10 most at-risk
        },
        "healthy_agents": {
            "count": len(healthy),
            "agents": healthy[:10],  # Show top 10 healthiest
        },
        "top_performers": {
            "count": len(top_performers),
            "agents": top_performers,
        },
        "struggling_agents": {
            "count": len(struggling),
            "agents": struggling,
        },
        "all_agents": {
            "count": len(all_agents["agents"]),
            "agents": all_agents["agents"],  # Full list for detailed view
        },
    }
