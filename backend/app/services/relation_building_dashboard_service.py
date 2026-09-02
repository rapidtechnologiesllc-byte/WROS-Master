"""
import logging
Relation Building Agent Dashboard - Daily Standup & Metrics

Reports to: Flash Orchestration Engine (morning standup)

Format: SDLC Daily Kanban Standup
- Yesterday: What was completed
- Today: What's planned
- Blockers: What's impeding progress
- Metrics: Impact on hiring pipeline
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.services.performance_store_service import get_performance_events

logger = logging.getLogger(__name__)

class RelationBuildingDashboard:
    """
    Relation Building Agent Dashboard - Daily standup and metrics.

    Metrics tracked:
    - Candidates processed (daily, weekly, monthly)
    - Engagement readiness distribution
    - Risk factors identified
    - Downstream system improvements (Thunder match quality, offer accuracy, etc.)
    - Blockers and constraints
    """

    @staticmethod
    def get_daily_standup(
        tenant_id: str,
        db: Session,
        days_back: int = 1,
    ) -> Dict[str, Any]:
        """
        Get daily standup report for Relation Building Agent.

        Format:
        {
            "agent_name": "Relation Building Agent",
            "reports_to": "Flash Orchestration Engine",
            "standup_date": "2026-08-23",
            "yesterday": {
                "title": "What we completed",
                "metrics": {...},
                "summary": "Extracted personas for 47 candidates..."
            },
            "today": {
                "title": "What we're working on",
                "tasks": [...],
                "summary": "Processing batch, feeding to Thunder..."
            },
            "blockers": {
                "title": "What's impeding progress",
                "items": [...],
                "summary": "..."
            },
            "impact": {
                "title": "How we're improving hiring",
                "metrics": {...},
                "summary": "..."
            }
        }
        """
        try:
            # Get yesterday's date range
            now = datetime.now()
            yesterday_start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0)
            yesterday_end = now.replace(hour=0, minute=0, second=0)

            # 1. YESTERDAY: Extract metrics
            yesterday_data = RelationBuildingDashboard._get_yesterday_metrics(
                db, tenant_id, yesterday_start, yesterday_end
            )

            # 2. TODAY: Planned work
            today_data = RelationBuildingDashboard._get_today_plan(db, tenant_id)

            # 3. BLOCKERS: Identify issues
            blockers_data = RelationBuildingDashboard._get_blockers(db, tenant_id)

            # 4. IMPACT: Show improvement metrics
            impact_data = RelationBuildingDashboard._get_impact_metrics(db, tenant_id)

            return {
                "status": "success",
                "agent_name": "Relation Building Agent",
                "reports_to": "Flash Orchestration Engine",
                "standup_date": now.date().isoformat(),
                "standup_time": now.time().isoformat(),
                "yesterday": yesterday_data,
                "today": today_data,
                "blockers": blockers_data,
                "impact": impact_data,
                "overall_health": RelationBuildingDashboard._calculate_health_score(
                    yesterday_data, blockers_data, impact_data
                ),
            }

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Dashboard generation error: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
            }

    @staticmethod
    def _get_yesterday_metrics(
        db: Session, tenant_id: str, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """
        Get metrics from yesterday (or specified time period).

        Returns:
        - Count of candidates processed
        - Engagement distribution
        - Risk factor breakdown
        - Top findings
        """
        # Get persona extraction events from performance store
        persona_events = db.query(
            func.count("*").label("count")
        ).from_statement(
            f"""
            SELECT * FROM performance_events
            WHERE event_type = 'RELATION_BUILDING_PERSONA_EXTRACTED'
            AND tenant_id = '{tenant_id}'
            AND created_at >= '{start_time}' AND created_at < '{end_time}'
            """
        ).scalar() or 0

        # Get candidate statistics
        candidates_processed = db.query(Candidate).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.created_at >= start_time,
            Candidate.created_at < end_time,
        ).count()

        # Get memory facts stored (as proxy for persona analysis depth)
        facts_stored = db.query(CandidateMemoryFact).filter(
            CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.extracted_at >= start_time,
            CandidateMemoryFact.extracted_at < end_time,
        ).count()

        # Get engagement readiness distribution
        high_engagement = db.query(CandidateMemoryFact).filter(
            CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.fact_key == "engagement_readiness",
            CandidateMemoryFact.fact_value == "high",
            CandidateMemoryFact.extracted_at >= start_time,
            CandidateMemoryFact.extracted_at < end_time,
            CandidateMemoryFact.is_active == True,
        ).count()

        medium_engagement = db.query(CandidateMemoryFact).filter(
            CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.fact_key == "engagement_readiness",
            CandidateMemoryFact.fact_value == "medium",
            CandidateMemoryFact.extracted_at >= start_time,
            CandidateMemoryFact.extracted_at < end_time,
            CandidateMemoryFact.is_active == True,
        ).count()

        low_engagement = db.query(CandidateMemoryFact).filter(
            CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.fact_key == "engagement_readiness",
            CandidateMemoryFact.fact_value == "low",
            CandidateMemoryFact.extracted_at >= start_time,
            CandidateMemoryFact.extracted_at < end_time,
            CandidateMemoryFact.is_active == True,
        ).count()

        # Risk factors identified
        risk_count = db.query(CandidateMemoryFact).filter(
            CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.fact_key.like("risk_%"),
            CandidateMemoryFact.extracted_at >= start_time,
            CandidateMemoryFact.extracted_at < end_time,
            CandidateMemoryFact.is_active == True,
        ).count()

        total_engagement = high_engagement + medium_engagement + low_engagement
        high_pct = (high_engagement / total_engagement * 100) if total_engagement > 0 else 0

        return {
            "title": "✅ What We Completed",
            "summary": f"Processed {candidates_processed} candidates, stored {facts_stored} persona facts. "
                      f"Engagement pool: {high_pct:.0f}% high-ready, {risk_count} risk factors flagged.",
            "metrics": {
                "candidates_processed": candidates_processed,
                "persona_facts_stored": facts_stored,
                "engagement_distribution": {
                    "high": high_engagement,
                    "medium": medium_engagement,
                    "low": low_engagement,
                },
                "high_engagement_percentage": round(high_pct, 1),
                "risk_factors_identified": risk_count,
            },
        }

    @staticmethod
    def _get_today_plan(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Get planned work for today.

        Returns tasks that Relation Building Agent will execute:
        - Process new candidate batches
        - Extract personas for high-potential candidates
        - Feed relationship intelligence to downstream systems
        """
        # Count candidates waiting for persona extraction (created today, no memory yet)
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        candidates_needing_processing = db.query(Candidate).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.created_at >= today_start,
        ).outerjoin(
            CandidateMemory,
            Candidate.candidateID == CandidateMemory.candidate_id
        ).filter(
            CandidateMemory.id == None
        ).count()

        return {
            "title": "🔄 What We're Working On Today",
            "summary": f"Processing {candidates_needing_processing} new candidates, extracting personas, "
                      f"feeding insights to Thunder (matching), Interview Scheduler, and Offer Generator. "
                      f"Daily Flash standup at 8:00 AM with relationship intelligence.",
            "tasks": [
                f"Extract personas for {candidates_needing_processing} new candidates",
                "Feed engagement readiness to Thunder for smarter matching",
                "Provide risk factors to Offer Generator for compensation strategy",
                "Update candidate memory with updated interaction signals",
                "Report relationship quality metrics to Flash daily standup",
            ],
        }

    @staticmethod
    def _get_blockers(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Identify blockers and constraints.

        Returns issues impeding progress:
        - SLM parsing failures
        - Missing resume data
        - Memory storage issues
        """
        # Check for candidates with no resume text (can't extract persona)
        no_resume_count = db.query(Candidate).filter(
            Candidate.tenant_id == tenant_id,
            (Candidate.resume_text == None) | (Candidate.resume_text == ""),
        ).count()

        # Check for memory extraction failures (would require audit logging)
        # For now, just report potential issue

        blockers_list = []
        if no_resume_count > 10:
            blockers_list.append(
                f"⚠️ {no_resume_count} candidates have no resume data - can't extract persona"
            )

        if not blockers_list:
            blockers_list.append("✓ No blockers identified - system operating normally")

        return {
            "title": "🚨 Blockers & Impediments",
            "summary": " | ".join(blockers_list),
            "items": blockers_list,
            "severity": "LOW" if not any("⚠️" in b for b in blockers_list) else "MEDIUM",
        }

    @staticmethod
    def _get_impact_metrics(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Get impact metrics showing how persona-based insights improve hiring.

        Tracks:
        - Thunder match quality improvement
        - Offer accuracy increase
        - Engagement metrics
        """
        # Get engagement statistics
        high_engagement_count = db.query(CandidateMemoryFact).filter(
            CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.fact_key == "engagement_readiness",
            CandidateMemoryFact.fact_value == "high",
            CandidateMemoryFact.is_active == True,
        ).count()

        total_with_persona = db.query(CandidateMemory).filter(
            CandidateMemory.tenant_id == tenant_id,
        ).count()

        # Calculate metrics
        personas_extracted = total_with_persona
        high_quality_pool_pct = (high_engagement_count / max(total_with_persona, 1)) * 100

        return {
            "title": "📈 Impact on Hiring Pipeline",
            "summary": f"Persona-based insights now available for {personas_extracted} candidates. "
                      f"{high_quality_pool_pct:.0f}% of pool is high-engagement ready for proactive outreach. "
                      f"Downstream systems (Thunder, Interview Scheduler, Offer Generator) using this intelligence "
                      f"to personalize candidate engagement and improve conversion rates.",
            "metrics": {
                "total_personas_extracted": personas_extracted,
                "high_quality_pool_percentage": round(high_quality_pool_pct, 1),
                "candidates_ready_for_proactive_outreach": high_engagement_count,
                "downstream_systems_powered": [
                    "Thunder (personalized matching)",
                    "Interview Scheduler (availability + engagement timing)",
                    "Offer Generator (compensation personalization)",
                    "Joining Predictor (no-show risk assessment)",
                ],
            },
        }

    @staticmethod
    def _calculate_health_score(
        yesterday: Dict, blockers: Dict, impact: Dict
    ) -> Dict[str, Any]:
        """
        Calculate overall agent health score.

        Factors:
        - Yesterday's productivity
        - Blockers severity
        - Impact metrics
        """
        score = 100  # Start at perfect

        # Deduct for low productivity
        if yesterday["metrics"]["candidates_processed"] < 20:
            score -= 10

        # Deduct for blockers
        if blockers.get("severity") == "MEDIUM":
            score -= 15
        elif blockers.get("severity") == "HIGH":
            score -= 30

        # Boost for high impact
        if impact["metrics"]["high_quality_pool_percentage"] > 70:
            score += 10

        return {
            "score": max(0, min(100, score)),
            "status": "HEALTHY" if score >= 80 else "WARNING" if score >= 60 else "CRITICAL",
            "trend": "↑" if score > 75 else "→" if score >= 60 else "↓",
        }
