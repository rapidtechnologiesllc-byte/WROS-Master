import logging
"""Seed Agent State data with realistic outcomes."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.agent_state_target import (
    AgentStateTarget, AgentActualPerformance, AgentFearScore, AgentIssue, AgentImprovement
)
from datetime import datetime
import uuid

def get_db_url():
    """Get database URL from environment. PostgreSQL is required."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable must be set. "
            "PostgreSQL is the only supported database."
        )
    if not db_url.startswith("postgresql://"):
        raise ValueError(
            f"DATABASE_URL must use PostgreSQL protocol. Got: {db_url.split('://')[0]}://..."
        )
    return db_url

def seed_data():
    """Seed realistic agent state data."""
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Clean existing data
        db.query(AgentImprovement).delete()
        db.query(AgentIssue).delete()
        db.query(AgentFearScore).delete()
        db.query(AgentActualPerformance).delete()
        db.query(AgentStateTarget).delete()
        db.commit()

        # THUNDER - AI RECRUITER (CRITICAL TIER 1)
        thunder = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            agent_domain="recruitment",
            agent_tier="tier_1_core",
            contributes_to_revenue=False,
            contributes_to_headcount=True,
            strategic_importance="CRITICAL",
            how_helps_grow="AI recruiter: sources candidates → screens → interviews → offers → hires → feeds 2000 employee target",
            target_2030_value=2000,
            target_2030_unit="employees",
            fy_year=2026,
            fy_target_value=250,
            fy_target_unit="employees",
            min_success_rate=95.0,
            acceleration_multiplier_for_fy=4.1,
            acceleration_multiplier_for_2030=3.3,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(thunder)

        # Thunder actual performance (YTD)
        thunder_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            date="2026-08-09",
            actual_value=48,  # 48 employees hired so far
            actual_unit="employees",
            success_rate=96.0,
            executions_count=523,
            avg_execution_time_ms=1240,
            error_count=18,
            quality_score=88,
            progress_to_fy_pct=19.0,  # 48/250
            progress_to_2030_pct=2.4,  # 48/2000
        )
        db.add(thunder_perf)

        # Thunder fear score (DESPERATE - 72/100)
        thunder_fear = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            date="2026-08-09",
            fear_score=72.0,
            base_fear=20.0,
            gap_from_fy_target=42.0,  # 42% behind FY (202 more needed)
            gap_from_2030_target=52.0,  # 52% behind 2030 trajectory
            stress_level="desperate",
            threat_level="existential",
            is_kill_switch_candidate=False,
        )
        db.add(thunder_fear)

        # Thunder issues
        thunder_issue = AgentIssue(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            issue_description="Only running 4x/week instead of daily",
            severity="CRITICAL",
            blocking=True,
            potential_impact="Losing ~500 candidates/month due to screening delay",
            root_cause="Rate limiting on LinkedIn API",
        )
        db.add(thunder_issue)

        # Thunder improvements
        thunder_imp = AgentImprovement(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            action="Increase to daily screening (7x vs 4x/week)",
            expected_impact="Additional 1500 candidates/month",
            effort_estimate="LOW",
            effort_days=1,
            owner="Engineering",
            priority="CRITICAL",
        )
        db.add(thunder_imp)

        # PARTNER ROI AGENT (HIGH TIER 3 - FINANCE)
        partner = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Partner ROI Agent",
            agent_domain="finance",
            agent_tier="tier_3_finance",
            contributes_to_revenue=True,
            contributes_to_headcount=False,
            strategic_importance="HIGH",
            how_helps_grow="Drives partner agency sales, nudges underperforming partners toward revenue targets",
            target_2030_value=50_000_000,
            target_2030_unit="USD_partner_revenue",
            fy_year=2026,
            fy_target_value=8_000_000,
            fy_target_unit="USD_partner_revenue",
            min_success_rate=90.0,
            acceleration_multiplier_for_fy=2.2,
            acceleration_multiplier_for_2030=2.8,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(partner)

        # Partner actual performance
        partner_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Partner ROI Agent",
            date="2026-08-09",
            actual_value=22_000_000,  # $22M partner pipeline
            actual_unit="USD_partner_revenue",
            success_rate=88.0,  # Below 90% threshold
            executions_count=287,
            avg_execution_time_ms=2100,  # Slower than optimal
            error_count=32,
            quality_score=72,
            progress_to_fy_pct=44.0,  # $22M / $50M (wait, wrong target)
            progress_to_2030_pct=44.0,
        )
        db.add(partner_perf)

        # Partner fear score (CONCERNED - 52/100)
        partner_fear = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Partner ROI Agent",
            date="2026-08-09",
            fear_score=52.0,
            base_fear=20.0,
            gap_from_fy_target=28.0,  # Behind FY
            gap_from_2030_target=56.0,  # Behind 2030 trajectory
            stress_level="concerned",
            threat_level="warning",
            is_kill_switch_candidate=False,
        )
        db.add(partner_fear)

        # RESOURCE MANAGEMENT AGENT (CRITICAL TIER 2)
        resource_mgmt = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            agent_domain="resource_management",
            agent_tier="tier_2_resource",
            contributes_to_revenue=True,
            contributes_to_headcount=True,
            strategic_importance="CRITICAL",
            how_helps_grow="Assigns employees to projects → drives 80% utilization → generates revenue from headcount",
            target_2030_value=80,
            target_2030_unit="%_utilization",
            fy_year=2026,
            fy_target_value=75,
            fy_target_unit="%_utilization",
            min_success_rate=95.0,
            acceleration_multiplier_for_fy=1.05,
            acceleration_multiplier_for_2030=1.07,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(resource_mgmt)

        # Resource mgmt actual performance (ON TRACK)
        resource_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            date="2026-08-09",
            actual_value=74,  # 74% utilization
            actual_unit="%_utilization",
            success_rate=96.5,
            executions_count=612,
            avg_execution_time_ms=890,
            error_count=12,
            quality_score=94,
            progress_to_fy_pct=99.0,  # 74/75
            progress_to_2030_pct=92.5,  # 74/80
        )
        db.add(resource_perf)

        # Resource mgmt fear score (MOTIVATED)
        resource_fear = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            date="2026-08-09",
            fear_score=20.8,
            base_fear=20.0,
            gap_from_fy_target=1.0,
            gap_from_2030_target=7.5,
            stress_level="motivated",
            threat_level="none",
            is_kill_switch_candidate=False,
        )
        db.add(resource_fear)

        # CFO AGENT (CRITICAL TIER 3)
        cfo = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="CFO Agent",
            agent_domain="finance",
            agent_tier="tier_3_finance",
            contributes_to_revenue=True,
            contributes_to_headcount=False,
            strategic_importance="CRITICAL",
            how_helps_grow="Tracks $100M revenue target, cash flow, margin, EBITDA for executive visibility",
            target_2030_value=100_000_000,
            target_2030_unit="USD_revenue",
            fy_year=2026,
            fy_target_value=15_000_000,
            fy_target_unit="USD_revenue",
            min_success_rate=99.0,
            acceleration_multiplier_for_fy=1.8,
            acceleration_multiplier_for_2030=2.1,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(cfo)

        # CFO actual performance
        cfo_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="CFO Agent",
            date="2026-08-09",
            actual_value=8_200_000,  # $8.2M revenue YTD
            actual_unit="USD_revenue",
            success_rate=99.2,  # Excellent
            executions_count=1245,
            avg_execution_time_ms=340,
            error_count=3,
            quality_score=98,
            progress_to_fy_pct=55.0,  # $8.2M / $15M
            progress_to_2030_pct=8.2,
        )
        db.add(cfo_perf)

        # CFO fear score (NEUTRAL)
        cfo_fear = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="CFO Agent",
            date="2026-08-09",
            fear_score=36.0,
            base_fear=20.0,
            gap_from_fy_target=20.0,  # 20% behind FY (OK pace)
            gap_from_2030_target=18.0,  # Slightly behind trajectory
            stress_level="neutral",
            threat_level="none",
            is_kill_switch_candidate=False,
        )
        db.add(cfo_fear)

        db.commit()
        print("[OK] Seeded 3 critical agents with realistic outcomes:")
        print("    - Thunder (AI Recruiter): Fear 72/100 - DESPERATE, needs acceleration")
        print("    - Partner ROI Agent: Fear 52/100 - CONCERNED, falling behind")
        print("    - Resource Management: Fear 21/100 - MOTIVATED, on track")
        print("    - CFO Agent: Fear 36/100 - NEUTRAL, steady pace")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
