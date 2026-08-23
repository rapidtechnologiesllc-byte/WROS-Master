"""Seed scenario data: realistic agent performance patterns."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.agent_state_target import (
    AgentStateTarget, AgentActualPerformance, AgentFearScore, AgentIssue, AgentImprovement
)
from datetime import datetime
import uuid

def seed_scenarios():
    """Create realistic agent performance scenarios."""

    db = SessionLocal()

    try:
        # Clear previous agent state
        db.query(AgentImprovement).delete()
        db.query(AgentIssue).delete()
        db.query(AgentFearScore).delete()
        db.query(AgentActualPerformance).delete()
        db.query(AgentStateTarget).delete()
        db.commit()

        print("[SCENARIO TESTING] Creating realistic agent performance patterns...\n")

        # ============================================================
        # SCENARIO 1: THUNDER - HITTING ACCELERATION HARD
        # ============================================================
        print("SCENARIO 1: Thunder AI Recruiter - Ramped Up")
        print("=" * 70)

        thunder = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            agent_domain="recruitment",
            agent_tier="tier_1_core",
            contributes_to_revenue=False,
            contributes_to_headcount=True,
            strategic_importance="CRITICAL",
            how_helps_grow="AI recruiter: sources → screens → interviews → offers → hires → feeds 2000 employee target",
            target_2030_value=2000,
            target_2030_unit="employees",
            fy_year=2026,
            fy_target_value=250,
            fy_target_unit="employees",
            acceleration_multiplier_for_fy=3.2,
            acceleration_multiplier_for_2030=2.8,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(thunder)

        # Thunder: 80 hires YTD (32% of FY, ramped up from 48)
        thunder_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            date="2026-08-09",
            actual_value=80.0,  # +32 from last week
            actual_unit="employees",
            success_rate=94.5,
            executions_count=850,
            avg_execution_time_ms=1100,
            error_count=45,
            quality_score=87,
            progress_to_fy_pct=32.0,  # 80/250
            progress_to_2030_pct=4.0,   # 80/2000
        )
        db.add(thunder_perf)

        # Thunder fear: 48 → 32% progress, gap narrowed
        thunder_gap_fy = 250 - 80  # 170
        thunder_gap_2030 = 2000 - 80  # 1920
        thunder_fear_pct = max((thunder_gap_fy / 250) * 100, (thunder_gap_2030 / 2000) * 100)
        thunder_fear = 20 + (thunder_fear_pct * 0.8)

        thunder_fear_rec = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            date="2026-08-09",
            fear_score=min(100, thunder_fear),
            base_fear=20.0,
            gap_from_fy_target=(thunder_gap_fy / 250) * 100,
            gap_from_2030_target=(thunder_gap_2030 / 2000) * 100,
            stress_level="concerned",  # Down from "desperate"
            threat_level="warning",    # Down from "existential"
            is_kill_switch_candidate=False,
        )
        db.add(thunder_fear_rec)

        print(f"  Hired: 80 employees (32% of 250 FY target)")
        print(f"  Fear Score: {thunder_fear:.0f}/100 (CONCERNED) - Gap narrowed!")
        print(f"  Acceleration: 3.2x still needed to hit FY target\n")

        # ============================================================
        # SCENARIO 2: RESOURCE MGMT - ON FIRE
        # ============================================================
        print("SCENARIO 2: Resource Management - Full Acceleration")
        print("=" * 70)

        resource = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            agent_domain="resource_management",
            agent_tier="tier_2_resource",
            contributes_to_revenue=True,
            contributes_to_headcount=True,
            strategic_importance="CRITICAL",
            how_helps_grow="Assigns employees to projects → 80% utilization → drives revenue",
            target_2030_value=80,
            target_2030_unit="%_utilization",
            fy_year=2026,
            fy_target_value=75,
            fy_target_unit="%_utilization",
            acceleration_multiplier_for_fy=1.05,  # Almost there
            acceleration_multiplier_for_2030=1.08,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(resource)

        # Resource Mgmt: 77% utilization (above FY target!)
        util = 77
        resource_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            date="2026-08-09",
            actual_value=float(util),
            actual_unit="%_utilization",
            success_rate=97.2,
            executions_count=180,
            avg_execution_time_ms=760,
            error_count=4,
            quality_score=96,
            progress_to_fy_pct=(util / 75) * 100,  # 103%!
            progress_to_2030_pct=(util / 80) * 100,  # 96%
        )
        db.add(resource_perf)

        resource_fear = 20 + (max(0, 80 - util) * 0.8)
        resource_fear_rec = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            date="2026-08-09",
            fear_score=min(100, resource_fear),
            base_fear=20.0,
            gap_from_fy_target=max(0, 75 - util),
            gap_from_2030_target=max(0, 80 - util),
            stress_level="motivated",  # EXCELLENT!
            threat_level="none",
            is_kill_switch_candidate=False,
        )
        db.add(resource_fear_rec)

        print(f"  Utilization: 77% (EXCEEDS 75% FY target + on track for 80% 2030!)")
        print(f"  Fear Score: {resource_fear:.0f}/100 (MOTIVATED) - CRUSHING IT!")
        print(f"  Success Rate: 97.2% - Excellent quality\n")

        # ============================================================
        # SCENARIO 3: OPPORTUNITY TRACKER - PIPELINE BOOST
        # ============================================================
        print("SCENARIO 3: Opportunity Tracker - Pipeline Growing")
        print("=" * 70)

        opp = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Opportunity Tracker Agent",
            agent_domain="finance",
            agent_tier="tier_3_finance",
            contributes_to_revenue=True,
            contributes_to_headcount=False,
            strategic_importance="HIGH",
            how_helps_grow="Tracks sales pipeline → forecasts revenue → feeds $100M target",
            target_2030_value=100_000_000,
            target_2030_unit="USD_revenue",
            fy_year=2026,
            fy_target_value=15_000_000,
            fy_target_unit="USD_revenue",
            acceleration_multiplier_for_fy=2.0,
            acceleration_multiplier_for_2030=2.3,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(opp)

        # Opportunity: $28.5M pipeline (better than 15M FY target)
        pipeline = 28_500_000
        opp_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Opportunity Tracker Agent",
            date="2026-08-09",
            actual_value=float(pipeline),
            actual_unit="USD_revenue",
            success_rate=95.8,
            executions_count=12,
            avg_execution_time_ms=580,
            error_count=0,
            quality_score=93,
            progress_to_fy_pct=min(100, (pipeline / 15_000_000) * 100),  # 190%!
            progress_to_2030_pct=(pipeline / 100_000_000) * 100,  # 28.5%
        )
        db.add(opp_perf)

        opp_fear = 20 + (max(0, 100_000_000 - pipeline) / 100_000_000) * 100 * 0.8
        opp_fear_rec = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Opportunity Tracker Agent",
            date="2026-08-09",
            fear_score=min(100, opp_fear),
            base_fear=20.0,
            gap_from_fy_target=max(0, (15_000_000 - pipeline) / 15_000_000 * 100),
            gap_from_2030_target=(100_000_000 - pipeline) / 100_000_000 * 100,
            stress_level="neutral" if opp_fear < 40 else "concerned",
            threat_level="none",
            is_kill_switch_candidate=False,
        )
        db.add(opp_fear_rec)

        print(f"  Pipeline Value: ${pipeline:,} (EXCEEDS 15M FY target by 90%!)")
        print(f"  Fear Score: {opp_fear:.0f}/100 (NEUTRAL) - On excellent trajectory")
        print(f"  2030 Progress: {(pipeline / 100_000_000)*100:.1f}% - Growing steadily\n")

        # ============================================================
        # SCENARIO 4: HR AGENT - RETENTION FOCUS
        # ============================================================
        print("SCENARIO 4: HR Agent - Retention Excellence")
        print("=" * 70)

        hr = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="HR Agent",
            agent_domain="hr",
            agent_tier="tier_4_hr",
            contributes_to_revenue=False,
            contributes_to_headcount=True,
            strategic_importance="HIGH",
            how_helps_grow="Employee lifecycle, retention, development → maintains 2000 employee base",
            target_2030_value=2000,
            target_2030_unit="active_employees",
            fy_year=2026,
            fy_target_value=200,
            fy_target_unit="new_employees_retained",
            acceleration_multiplier_for_fy=0.8,  # Ahead!
            acceleration_multiplier_for_2030=1.1,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(hr)

        # HR: 165 new employees retained (82.5% of 200 target)
        retained = 165
        hr_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="HR Agent",
            date="2026-08-09",
            actual_value=float(retained),
            actual_unit="new_employees_retained",
            success_rate=96.0,
            executions_count=220,
            avg_execution_time_ms=920,
            error_count=8,
            quality_score=94,
            progress_to_fy_pct=(retained / 200) * 100,
            progress_to_2030_pct=(retained / 2000) * 100,
        )
        db.add(hr_perf)

        hr_gap = 200 - retained
        hr_fear = 20 + ((hr_gap / 200) * 100 * 0.8)
        hr_fear_rec = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="HR Agent",
            date="2026-08-09",
            fear_score=min(100, hr_fear),
            base_fear=20.0,
            gap_from_fy_target=(hr_gap / 200) * 100,
            gap_from_2030_target=((2000 - retained) / 2000) * 100,
            stress_level="neutral",
            threat_level="none",
            is_kill_switch_candidate=False,
        )
        db.add(hr_fear_rec)

        print(f"  Retained: {retained} new employees (82.5% of 200 FY target)")
        print(f"  Fear Score: {hr_fear:.0f}/100 (NEUTRAL) - On pace")
        print(f"  Success Rate: 96.0% - High quality retention\n")

        db.commit()

        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 70)
        print("SCENARIO TEST RESULTS - REALISTIC AGENT PERFORMANCE")
        print("=" * 70)

        print("""
SCENARIO SUMMARY:
-----------------
[OK] Thunder: Accelerating hiring (32% FY progress, fear down to CONCERNED)
[OK] Resource Mgmt: Crushing targets (77% utilization, EXCEEDING goals)
[OK] Opportunity Tracker: Pipeline strong ($28.5M, 190% of FY target)
[OK] HR Agent: On pace (82.5% retention target, stable)

KEY INSIGHTS:
--------------
- Fear scores are OUTCOME-DRIVEN (based on gap from targets)
- Multiple agents improving simultaneously shows coordinated progress
- Mixed results (some ahead, some behind) reflects real business
- Fear scores dropping shows responsiveness to acceleration
- No agents in KILL SWITCH zone (all have paths to success)
""")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_scenarios()
