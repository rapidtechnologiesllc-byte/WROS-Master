import logging
"""Seed realistic performance data for all 50+ agents."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.agent_state_target import AgentActualPerformance
from app.services.agent_registry_service import AGENT_REGISTRY
from datetime import datetime, timedelta
import random
import uuid

db = SessionLocal()

try:
    # Clear old performance data
    db.query(AgentActualPerformance).delete()
    db.commit()

    print("[SEED] Populating performance data for 50+ agents...\n")

    # Performance scenarios (some at target, some behind, some ahead)
    scenarios = [
        # Tier 1 Core (Must be at 90%+ or face kill switch)
        {
            "name": "Thunder",
            "actual": 80,
            "target": 250,
            "success_rate": 93.0,
            "quality": 87.0,
            "executions": 1250,
        },
        {
            "name": "Recruitment Agent",
            "actual": 720,
            "target": 900,
            "success_rate": 96.0,
            "quality": 94.0,
            "executions": 1800,
        },
        {
            "name": "Supervisor Agent",
            "actual": 98,
            "target": 98,
            "success_rate": 98.0,
            "quality": 97.0,
            "executions": 3200,
        },
        {
            "name": "CEO Dependency Agent",
            "actual": 3,
            "target": 5,
            "success_rate": 100.0,
            "quality": 99.0,
            "executions": 150,
        },
        # Tier 2 Resource Management
        {
            "name": "Resource Management Agent",
            "actual": 77,
            "target": 75,
            "success_rate": 97.2,
            "quality": 96.0,
            "executions": 2400,
        },
        {
            "name": "Core-Pull Conflict Agent",
            "actual": 100,
            "target": 100,
            "success_rate": 99.9,
            "quality": 99.0,
            "executions": 5000,
        },
        {
            "name": "Deployment Agent",
            "actual": 85,
            "target": 90,
            "success_rate": 95.0,
            "quality": 93.0,
            "executions": 2000,
        },
        # Tier 3 Finance
        {
            "name": "CFO Agent",
            "actual": 28_500_000,
            "target": 50_000_000,
            "success_rate": 94.0,
            "quality": 92.0,
            "executions": 800,
        },
        {
            "name": "Opportunity Tracker Agent",
            "actual": 28_500_000,
            "target": 15_000_000,
            "success_rate": 96.0,
            "quality": 95.0,
            "executions": 600,
        },
        {
            "name": "Revenue Recognition Agent",
            "actual": 22_000_000,
            "target": 40_000_000,
            "success_rate": 92.0,
            "quality": 90.0,
            "executions": 500,
        },
        {
            "name": "Margin Agent",
            "actual": 4_500_000,
            "target": 8_000_000,
            "success_rate": 91.0,
            "quality": 88.0,
            "executions": 1200,
        },
        {
            "name": "Cash Flow Agent",
            "actual": 1_200_000,
            "target": 2_000_000,
            "success_rate": 90.0,
            "quality": 87.0,
            "executions": 800,
        },
        # Tier 4 HR & People
        {
            "name": "HR Agent",
            "actual": 165,
            "target": 200,
            "success_rate": 96.0,
            "quality": 94.0,
            "executions": 1500,
        },
        {
            "name": "Mental Health Agent",
            "actual": 89,
            "target": 100,
            "success_rate": 94.0,
            "quality": 91.0,
            "executions": 1200,
        },
        {
            "name": "Onboarding Agent",
            "actual": 45,
            "target": 50,
            "success_rate": 95.0,
            "quality": 93.0,
            "executions": 900,
        },
        {
            "name": "Buddy Program Agent",
            "actual": 40,
            "target": 45,
            "success_rate": 93.0,
            "quality": 91.0,
            "executions": 800,
        },
        # Tier 5 KPI & Metrics
        {
            "name": "KPI Agent",
            "actual": 95,
            "target": 100,
            "success_rate": 97.0,
            "quality": 96.0,
            "executions": 3600,
        },
        {
            "name": "Risk Agent",
            "actual": 12,
            "target": 15,
            "success_rate": 92.0,
            "quality": 88.0,
            "executions": 600,
        },
        {
            "name": "Forecast Agent",
            "actual": 85,
            "target": 90,
            "success_rate": 89.0,
            "quality": 85.0,
            "executions": 1800,
        },
        # Tier 6 Support Agents (sample)
        {
            "name": "Interview Reminder Agent",
            "actual": 95,
            "target": 100,
            "success_rate": 97.0,
            "quality": 96.0,
            "executions": 2000,
        },
        {
            "name": "Help Desk Agent",
            "actual": 450,
            "target": 500,
            "success_rate": 93.0,
            "quality": 89.0,
            "executions": 2200,
        },
        {
            "name": "Activity Feed Agent",
            "actual": 3200,
            "target": 3000,
            "success_rate": 98.0,
            "quality": 97.0,
            "executions": 8000,
        },
        {
            "name": "Daily Digest Agent",
            "actual": 1800,
            "target": 2000,
            "success_rate": 96.0,
            "quality": 94.0,
            "executions": 5000,
        },
        {
            "name": "Executive Signal Agent",
            "actual": 120,
            "target": 150,
            "success_rate": 94.0,
            "quality": 91.0,
            "executions": 1200,
        },
    ]

    # Create performance records for known scenarios
    today = datetime.utcnow().date().isoformat()

    for scenario in scenarios:
        perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name=scenario["name"],
            date=today,
            actual_value=scenario["actual"],
            actual_unit=AGENT_REGISTRY.get(scenario["name"], {}).get("fy_target", {}).get("unit", ""),
            success_rate=scenario["success_rate"],
            quality_score=scenario["quality"],
            executions_count=scenario["executions"],
            avg_execution_time_ms=random.randint(500, 5000),
            progress_to_fy_pct=(scenario["actual"] / scenario.get("target", 100) * 100) if scenario.get("target") else 0,
            progress_to_2030_pct=(scenario["actual"] / 2000 * 100) if "headcount" in str(scenario.get("target", "")).lower() else 0,
        )
        db.add(perf)

    # Add remaining agents from registry with default/varied performance
    for agent_name in AGENT_REGISTRY.keys():
        # Skip if already added in scenarios
        if any(s["name"] == agent_name for s in scenarios):
            continue

        # Generate realistic performance data
        actual = random.randint(50, 100)
        target = random.randint(70, 150)
        success_rate = random.uniform(85.0, 99.0)
        quality = random.uniform(80.0, 98.0)
        executions = random.randint(500, 3000)

        perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name=agent_name,
            date=today,
            actual_value=actual,
            actual_unit=AGENT_REGISTRY.get(agent_name, {}).get("fy_target", {}).get("unit", ""),
            success_rate=success_rate,
            quality_score=quality,
            executions_count=executions,
            avg_execution_time_ms=random.randint(500, 4000),
            progress_to_fy_pct=(actual / target * 100) if target > 0 else 0,
            progress_to_2030_pct=random.uniform(1.0, 50.0),
        )
        db.add(perf)

    db.commit()

    # Display summary
    all_perfs = db.query(AgentActualPerformance).all()
    print(f"[OK] Created {len(all_perfs)} agent performance records\n")

    print("Sample agents with performance data:")
    print("-" * 100)
    print(f"{'Agent Name':<35} {'Actual':<12} {'Progress %':<12} {'Success Rate':<15} {'Quality':<12}")
    print("-" * 100)

    for perf in all_perfs[:15]:
        print(f"{perf.agent_name:<35} {perf.actual_value:<12.0f} {perf.progress_to_fy_pct:<11.1f}% {perf.success_rate:<14.1f}% {perf.quality_score:<11.1f}%")

    print(f"... and {len(all_perfs) - 15} more agents\n")

    print("[OK] Agent performance data seeded successfully!")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    db.rollback()
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
