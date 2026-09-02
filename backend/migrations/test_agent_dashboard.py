import logging
"""Test Agent Performance Dashboard - Shows all 50+ agents with targets vs achievements."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.services.agent_performance_dashboard_service import AgentPerformanceDashboard

db = SessionLocal()

try:
    print("\n" + "="*120)
    print(" " * 35 + "AGENT PERFORMANCE DASHBOARD - ALL AGENTS")
    print("="*120 + "\n")

    # Get all agents performance
    print("Fetching all agents performance data...\n")
    result = AgentPerformanceDashboard.get_all_agents_performance(db)

    print(f"SUMMARY:")
    print(f"  Total Agents: {result['total_agents']}")
    print(f"  Critical Importance: {result['critical_agents']}")
    print(f"  At-Risk (Fear > 70): {result['at_risk_agents']}")
    print(f"  Healthy (Fear <= 50): {result['healthy_agents']}")

    # Display table header
    print("\n" + "-"*150)
    print(
        f"{'Agent':<30} {'Domain':<20} {'Importance':<15} {'FY Target':<12} {'Achieved':<12} {'Progress':<12} "
        f"{'Gap %':<10} {'Fear':<10} {'Status':<12} {'Acceleration':<12}"
    )
    print("-"*150)

    # Display all agents
    for agent in result["agents"]:
        agent_name = agent["agent_name"][:28]
        domain = agent["domain"][:18]
        importance = agent["strategic_importance"][:13]
        target = f"{agent['fy_target']:.0f}"
        achieved = f"{agent['fy_achieved']:.0f}"
        progress = f"{agent['fy_progress_pct']:.1f}%"
        gap = f"{agent['fy_gap_pct']:.0f}%"
        fear = f"{agent['fear_score']:.0f}"
        status = agent["status"][:10]
        accel = f"{agent['acceleration_multiplier']:.1f}x"

        print(
            f"{agent_name:<30} {domain:<20} {importance:<15} {target:<12} {achieved:<12} {progress:<12} "
            f"{gap:<10} {fear:<10} {status:<12} {accel:<12}"
        )

    print("-"*150)

    # Summary statistics
    print("\n" + "="*120)
    print("STRATEGIC IMPORTANCE BREAKDOWN:")
    print("="*120)

    critical = [a for a in result["agents"] if a["strategic_importance"] == "CRITICAL"]
    high = [a for a in result["agents"] if a["strategic_importance"] == "HIGH"]
    medium = [a for a in result["agents"] if a["strategic_importance"] == "MEDIUM"]
    low = [a for a in result["agents"] if a["strategic_importance"] == "LOW"]

    print(f"\nCRITICAL ({len(critical)} agents) - MUST PERFORM:")
    for agent in critical:
        print(f"  {agent['agent_name']:<35} Fear: {agent['fear_score']:>5.0f} | Progress: {agent['fy_progress_pct']:>6.1f}% | Status: {agent['status']}")

    print(f"\nHIGH ({len(high)} agents) - IMPORTANT:")
    for agent in high[:5]:  # Show top 5
        print(f"  {agent['agent_name']:<35} Fear: {agent['fear_score']:>5.0f} | Progress: {agent['fy_progress_pct']:>6.1f}% | Status: {agent['status']}")
    if len(high) > 5:
        print(f"  ... and {len(high)-5} more HIGH importance agents")

    print(f"\nMEDIUM ({len(medium)} agents)")
    print(f"LOW ({len(low)} agents)")

    # At-risk analysis
    print("\n" + "="*120)
    print("AT-RISK AGENTS (Fear Score > 70) - Need Immediate Attention:")
    print("="*120 + "\n")

    at_risk = AgentPerformanceDashboard.get_at_risk_agents(db)
    if at_risk:
        print(f"Found {len(at_risk)} at-risk agents:\n")
        for agent in at_risk:
            print(f"  {agent['agent_name']:<35}")
            print(f"    FY Target: {agent['fy_target']} | Achieved: {agent['fy_achieved']} | Progress: {agent['fy_progress_pct']:.1f}%")
            print(f"    Fear Score: {agent['fear_score']:.0f}/100 [{agent['status']}]")
            print(f"    Acceleration Needed: {agent['acceleration_multiplier']:.1f}x")
            print()
    else:
        print("No at-risk agents detected!")

    # Healthy analysis
    print("\n" + "="*120)
    print("HEALTHY AGENTS (Fear Score <= 50) - On Track or Exceeding:")
    print("="*120 + "\n")

    healthy = AgentPerformanceDashboard.get_healthy_agents(db)
    print(f"Found {len(healthy)} healthy agents:\n")
    for agent in healthy[:10]:  # Show top 10
        print(f"  {agent['agent_name']:<35} Progress: {agent['fy_progress_pct']:>6.1f}% | Fear: {agent['fear_score']:>5.0f} | Status: {agent['status']}")

    # Progress summary
    print("\n" + "="*120)
    print("COMPANY TARGETS PROGRESS:")
    print("="*120 + "\n")

    progress = AgentPerformanceDashboard.get_progress_summary(db)
    print(f"REVENUE TARGET: ${progress['revenue']['target_display']}")
    print(f"  Achieved: ${progress['revenue']['achieved']:,.0f}")
    print(f"  Progress: {progress['revenue']['progress_pct']:.1f}%")

    print(f"\nHEADCOUNT TARGET: {progress['headcount']['target']} employees")
    print(f"  Achieved: {progress['headcount']['achieved']:.0f}")
    print(f"  Progress: {progress['headcount']['progress_pct']:.1f}%")

    print(f"\nAGENT HEALTH DISTRIBUTION:")
    print(f"  Healthy: {progress['healthy_agents']}/{progress['total_agents']} ({progress['healthy_agents']/progress['total_agents']*100:.0f}%)")
    print(f"  At-Risk: {progress['at_risk_agents']}/{progress['total_agents']} ({progress['at_risk_agents']/progress['total_agents']*100:.0f}%)")
    print(f"  Critical: {progress['critical_agents']}/{progress['total_agents']} (must perform)")

    print("\n" + "="*120)
    print("EXECUTIVE DASHBOARD DATA READY FOR DISPLAY")
    print("="*120 + "\n")

    # Get critical agents
    critical_agents = AgentPerformanceDashboard.get_critical_agents(db)
    print(f"\nCRITICAL AGENTS REQUIRING CEO ATTENTION ({len(critical_agents)} agents):")
    for agent in critical_agents:
        if agent['fear_score'] > 70:
            print(f"  [ALERT] {agent['agent_name']:<30} Fear: {agent['fear_score']:.0f} | Progress: {agent['fy_progress_pct']:.1f}%")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
