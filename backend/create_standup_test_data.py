#!/usr/bin/env python
import logging
"""Create test data for Agent Standups Dashboard demonstration."""

from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.agent_execution_log import AgentExecutionLog

def create_agent_standups_test_data():
    """Create realistic agent execution logs for standup demonstration."""
    db = SessionLocal()

    try:
        # Get yesterday's date
        yesterday = datetime.utcnow().date()

        # Define sample agents and their execution patterns
        agents_data = {
            # Tier 1: Core Recruiting (should be healthy)
            "Thunder": {
                "executions": 25,
                "success_rate": 96,
                "avg_duration": 1200,  # 1.2 seconds
                "tier": "tier_1_core"
            },
            "Recruitment Agent": {
                "executions": 18,
                "success_rate": 94,
                "avg_duration": 950,
                "tier": "tier_1_core"
            },
            "Supervisor Agent": {
                "executions": 12,
                "success_rate": 98,
                "avg_duration": 800,
                "tier": "tier_1_core"
            },
            # Tier 2: Resource Management (some running)
            "Resource Management Agent": {
                "executions": 8,
                "success_rate": 87,  # Slightly degraded
                "avg_duration": 2100,
                "tier": "tier_2_resource"
            },
            "Core-Pull Conflict Agent": {
                "executions": 5,
                "success_rate": 80,  # At threshold
                "avg_duration": 1500,
                "tier": "tier_2_resource"
            },
            # Tier 3: Finance (critical tier)
            "CFO Agent": {
                "executions": 3,
                "success_rate": 100,
                "avg_duration": 2400,
                "tier": "tier_3_finance"
            },
            "CEO/FY Progress Agent": {
                "executions": 2,
                "success_rate": 100,
                "avg_duration": 1800,
                "tier": "tier_3_finance"
            },
            "Partner ROI Agent": {
                "executions": 4,
                "success_rate": 75,  # Failing
                "avg_duration": 2800,
                "tier": "tier_3_finance",
                "has_error": True
            },
            # Tier 4: HR & Employee
            "Onboarding Agent": {
                "executions": 6,
                "success_rate": 100,
                "avg_duration": 1100,
                "tier": "tier_4_hr"
            },
            "HR Agent": {
                "executions": 5,
                "success_rate": 92,
                "avg_duration": 1400,
                "tier": "tier_4_hr"
            },
            "Employee Mental Health Agent": {
                "executions": 3,
                "success_rate": 100,
                "avg_duration": 900,
                "tier": "tier_4_hr"
            },
            "Buddy Program Agent": {
                "executions": 4,
                "success_rate": 100,
                "avg_duration": 800,
                "tier": "tier_4_hr"
            },
            # Tier 5: KPI
            "KPI Agent": {
                "executions": 1,
                "success_rate": 100,
                "avg_duration": 3200,
                "tier": "tier_5_kpi"
            },
            # Tier 6: Support
            "Engagement/Outreach Agent": {
                "executions": 15,
                "success_rate": 93,
                "avg_duration": 950,
                "tier": "tier_6_support"
            },
            "Interview Reminder Agent": {
                "executions": 9,
                "success_rate": 100,
                "avg_duration": 600,
                "tier": "tier_6_support"
            },
            "Activity Feed Agent": {
                "executions": 20,
                "success_rate": 95,
                "avg_duration": 550,
                "tier": "tier_6_support"
            },
            "Executive Signal Agent": {
                "executions": 7,
                "success_rate": 98,
                "avg_duration": 1200,
                "tier": "tier_6_support"
            },
        }

        # Create execution logs for each agent
        logs_created = 0

        for agent_name, config in agents_data.items():
            executions = config["executions"]
            success_rate = config["success_rate"]
            avg_duration = config["avg_duration"]
            success_count = int(executions * success_rate / 100)

            for i in range(executions):
                # Spread executions throughout yesterday
                hour = (i % 24)
                minute = (i * 7) % 60
                execution_time = datetime.combine(
                    yesterday,
                    datetime.min.time()
                ) + timedelta(hours=hour, minutes=minute)

                # Alternate successes and failures
                is_success = i < success_count

                log = AgentExecutionLog(
                    tenant_id="blitzenx",
                    agent_name=agent_name,
                    action_taken=f"sample_action_{i}",
                    duration_ms=avg_duration + (i % 500) - 250,  # Vary slightly
                    success=is_success,
                    error_message=f"Sample error for {agent_name}" if not is_success and config.get("has_error") else None,
                    execution_at=execution_time,
                    action_data={"sample_key": f"sample_value_{i}"}
                )
                db.add(log)
                logs_created += 1

        db.commit()
        print("[OK] Created {} agent execution logs for testing".format(logs_created))
        print("[OK] Test data spans all 17 agents across 6 tiers")
        print("[OK] Date: {}".format(yesterday))
        print("\n[INFO] Visit the Agent Standups Dashboard to see:")
        print("   - Daily standup report with all agents reporting")
        print("   - Tier-based health summary")
        print("   - Critical focus areas for CEO")
        print("   - Scrum of Scrums coordination data")

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        print("[ERROR] Error creating test data: {}".format(e))
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_agent_standups_test_data()
