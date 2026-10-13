#!/usr/bin/env python3
"""
Test Flash lifecycle validation logic

Simulates week 20 of the year with different scenarios
"""

def get_week_of_year():
    from datetime import datetime
    return datetime.utcnow().isocalendar()[1]

def simulate_cascading_flash_validation(annual_goal, q_target, month_target, week_target, day_target,
                                        q_progress, month_progress, week_progress, day_progress):
    """
    Flash validation across ALL timeframes: Annual → Quarterly → Monthly → Weekly → Daily

    Helps manager see progress at every level and identify where gaps occur
    """

    # Calculate remaining to meet each target
    q_remaining = q_target - q_progress
    month_remaining = month_target - month_progress
    week_remaining = week_target - week_progress
    day_remaining = day_target - day_progress

    # Overall pace status
    annual_status = "ON_TRACK" if q_remaining >= 0 else "CRITICAL_LAG"
    q_status = "ON_TRACK" if q_remaining >= 0 else "CRITICAL_LAG"
    month_status = "ON_TRACK" if month_remaining >= 0 else "CRITICAL_LAG"
    week_status = "ON_TRACK" if week_remaining >= 0 else "CRITICAL_LAG"
    day_status = "ON_TRACK" if day_remaining >= 0 else "CRITICAL_LAG"

    # Bottleneck analysis: which level is most constrained?
    bottleneck = None
    if day_status == "CRITICAL_LAG":
        bottleneck = "TODAY - You need results NOW to stay on pace"
    elif week_status == "CRITICAL_LAG":
        bottleneck = "THIS WEEK - Daily catch-up not enough, need big push"
    elif month_status == "CRITICAL_LAG":
        bottleneck = "THIS MONTH - This week alone can't save you"
    elif q_status == "CRITICAL_LAG":
        bottleneck = "THIS QUARTER - Need sustained effort next few weeks"

    return {
        "annual": {"target": annual_goal, "status": annual_status},
        "quarterly": {"target": q_target, "progress": q_progress, "remaining": q_remaining, "status": q_status},
        "monthly": {"target": month_target, "progress": month_progress, "remaining": month_remaining, "status": month_status},
        "weekly": {"target": week_target, "progress": week_progress, "remaining": week_remaining, "status": week_status},
        "daily": {"target": day_target, "progress": day_progress, "remaining": day_remaining, "status": day_status},
        "bottleneck": bottleneck
    }

def simulate_flash_validation(week_num, annual_goal, cumulative_progress, this_week_commits):
    """Simulate Flash validation logic"""

    # Expected pace by this week
    expected_by_this_week = (annual_goal // 52) * week_num

    # Total progress with this week's commits
    total_progress_with_this_week = cumulative_progress + this_week_commits

    # Variance calculation
    pace_variance = total_progress_with_this_week - expected_by_this_week
    variance_pct = (pace_variance / expected_by_this_week * 100) if expected_by_this_week > 0 else 0

    # Status determination
    if pace_variance >= 0:
        status = "ON_TRACK" if variance_pct < 5 else "AHEAD"
        submit_enabled = True
    elif pace_variance > -10:
        status = "SLIGHT_LAG"
        submit_enabled = False
    else:
        status = "CRITICAL_LAG"
        submit_enabled = False

    # Flash feedback
    if status == "ON_TRACK":
        feedback = f"Great! You're on pace. Expected {expected_by_this_week} commits by week {week_num}, you're at {total_progress_with_this_week}. Keep it up!"
        actions = ["Continue current velocity", "Maintain this week's pace"]

    elif status == "SLIGHT_LAG":
        behind = expected_by_this_week - total_progress_with_this_week
        feedback = f"You're {behind} commits behind schedule. To reach {annual_goal} for the year, you need to catch up. You're reporting {this_week_commits} this week — good, but you need 10-15 more to get back on pace."
        actions = [
            f"Next week, target {this_week_commits + behind // 2} commits to start catching up",
            "Review blockers with your manager — what's slowing velocity?",
            "Identify 2-3 quick wins for next week to bridge the gap"
        ]

    elif status == "CRITICAL_LAG":
        behind = expected_by_this_week - total_progress_with_this_week
        feedback = f"CRITICAL: You're {behind} commits behind pace. At this rate, you'll miss the {annual_goal} goal. Reporting {this_week_commits} this week is not enough. You need {behind + 15} commits next week to recover."
        actions = [
            f"IMMEDIATE: Schedule with your manager to discuss velocity gap (need {behind} catch-up)",
            "Identify blockers preventing higher velocity (meetings? unclear priorities? technical debt?)",
            f"Commit to {behind + 15} commits next week with specific deliverables assigned today"
        ]

    else:  # AHEAD
        ahead = total_progress_with_this_week - expected_by_this_week
        feedback = f"Excellent! You're {ahead} commits AHEAD of pace. At {this_week_commits} this week, you're crushing it. Maintain this and you'll exceed the {annual_goal} target."
        actions = ["Maintain current velocity", "Document what's working well", "Help teammates accelerate"]

    return {
        "annual_goal": f"{annual_goal} commits",
        "expected_pace": expected_by_this_week,
        "actual_progress": total_progress_with_this_week,
        "variance": pace_variance,
        "status": status,
        "submit_enabled": submit_enabled,
        "feedback": feedback,
        "actions": actions
    }

# Test cascading Flash validation (Workforce Ops example: 100 hires/year)
print("=" * 80)
print("CASCADING FLASH VALIDATION - Workforce Operations (100 Hires/Year Goal)")
print("=" * 80)
print("\nGoal Hierarchy:")
print("  Annual: 100 hires")
print("  Q1-Q4: 25 hires each")
print("  Monthly (Aug): 8.3 hires")
print("  Weekly (Week of Aug 20): 1.9 hires")
print("  Daily: 0.27 hires (roughly 1 every 3 days)")

print("\n" + "=" * 80)
print("SCENARIO A: On Track Across All Levels")
print("=" * 80)
result = simulate_cascading_flash_validation(
    annual_goal=100,
    q_target=25,
    month_target=8.3,
    week_target=1.9,
    day_target=0.27,
    q_progress=12.5,    # Halfway through Q1
    month_progress=4.5, # Halfway through month
    week_progress=1.0,  # Halfway through week
    day_progress=0.2    # Good for today
)
print(f"Annual Goal: {result['annual']['target']} hires")
print(f"\n[OK] QUARTERLY: {result['quarterly']['progress']} / {result['quarterly']['target']} (Need {result['quarterly']['remaining']:.1f} more)")
print(f"[OK] MONTHLY: {result['monthly']['progress']} / {result['monthly']['target']} (Need {result['monthly']['remaining']:.1f} more)")
print(f"[OK] WEEKLY: {result['weekly']['progress']} / {result['weekly']['target']} (Need {result['weekly']['remaining']:.1f} more)")
print(f"[OK] TODAY: {result['daily']['progress']} / {result['daily']['target']} (On pace!)")
print(f"\nFlash Says: You're on pace across all timeframes. Keep the momentum!")
if result['bottleneck']:
    print(f"[WARNING] Bottleneck: {result['bottleneck']}")

print("\n" + "=" * 80)
print("SCENARIO B: Behind at Monthly & Weekly Levels")
print("=" * 80)
result = simulate_cascading_flash_validation(
    annual_goal=100,
    q_target=25,
    month_target=8.3,
    week_target=1.9,
    day_target=0.27,
    q_progress=12.5,    # Q1 still okay
    month_progress=2.0, # BEHIND in current month (need 6.3 more)
    week_progress=0.3,  # BEHIND this week (need 1.6 more)
    day_progress=0.0    # Nothing today
)
print(f"Annual Goal: {result['annual']['target']} hires")
print(f"\n✓ QUARTERLY: {result['quarterly']['progress']} / {result['quarterly']['target']} (Need {result['quarterly']['remaining']:.1f} more)")
print(f"✗ MONTHLY: {result['monthly']['progress']} / {result['monthly']['target']} (NEED {result['monthly']['remaining']:.1f} MORE!)")
print(f"✗ WEEKLY: {result['weekly']['progress']} / {result['weekly']['target']} (NEED {result['weekly']['remaining']:.1f} MORE!)")
print(f"✗ TODAY: {result['daily']['progress']} / {result['daily']['target']} (BEHIND PACE!)")
print(f"\nFlash Says: You're off pace at daily and weekly levels. This month won't recover without action TODAY.")
if result['bottleneck']:
    print(f"⚠️  CRITICAL BOTTLENECK: {result['bottleneck']}")
    print(f"\nFlash Action Required:")
    print(f"  1. Schedule candidate interviews TODAY (need at least 1 hire)")
    print(f"  2. Fast-track offers in pipeline (activate 2-3 candidates)")
    print(f"  3. Extend recruiting team if needed to hit {result['month_target']:.1f} for month")

print("\n" + "=" * 80)
print("SCENARIO C: Critical Lag at All Levels")
print("=" * 80)
result = simulate_cascading_flash_validation(
    annual_goal=100,
    q_target=25,
    month_target=8.3,
    week_target=1.9,
    day_target=0.27,
    q_progress=5.0,     # WAY BEHIND in Q1
    month_progress=0.5, # Barely started this month
    week_progress=0.0,  # Nothing this week
    day_progress=0.0    # Nothing today
)
print(f"Annual Goal: {result['annual']['target']} hires")
print(f"\n✗ QUARTERLY: {result['quarterly']['progress']} / {result['quarterly']['target']} (NEED {result['quarterly']['remaining']:.1f} MORE!)")
print(f"✗ MONTHLY: {result['monthly']['progress']} / {result['monthly']['target']} (NEED {result['monthly']['remaining']:.1f} MORE!)")
print(f"✗ WEEKLY: {result['weekly']['progress']} / {result['weekly']['target']} (NEED {result['weekly']['remaining']:.1f} MORE!)")
print(f"✗ TODAY: {result['daily']['progress']} / {result['daily']['target']} (NEED {result['daily']['remaining']:.1f} MORE!)")
print(f"\nFlash Says: CRITICAL - You're behind at EVERY level. The yearly goal of {result['annual']['target']} is at risk.")
if result['bottleneck']:
    print(f"⚠️  CRITICAL BOTTLENECK: {result['bottleneck']}")
    print(f"\nFlash ESCALATION:")
    print(f"  RED ALERT: 100-hire goal requires immediate intervention")
    print(f"  Missing {result['quarterly']['remaining']:.0f} hires just for Q1 ({result['quarterly']['target']} target)")
    print(f"  Recommend: Emergency staffing review, process acceleration, extended recruiter hours")
    print(f"  Manager escalation: Schedule with BU Head TODAY")

# Test scenarios
print("\n\n" + "=" * 80)
print("ORIGINAL FLASH VALIDATION TEST - Week 20 of 2026")
print("=" * 80)

print("\n" + "=" * 80)
print("SCENARIO 1: CRITICAL_LAG (Way behind)")
print("=" * 80)
result = simulate_flash_validation(
    week_num=20,
    annual_goal=500,
    cumulative_progress=50,  # Only 50 commits through week 19
    this_week_commits=5      # Only 5 this week
)
print(f"Annual Goal: {result['annual_goal']}")
print(f"Expected by Week 20: {result['expected_pace']}")
print(f"Actual: {result['actual_progress']}")
print(f"Variance: {result['variance']} commits")
print(f"Status: {result['status']}")
print(f"Submit Enabled: {result['submit_enabled']}")
print(f"\nFlash Feedback:\n{result['feedback']}")
print(f"\nConrete Actions:")
for i, action in enumerate(result['actions'], 1):
    print(f"  {i}. {action}")

print("\n" + "=" * 80)
print("SCENARIO 2: SLIGHT_LAG (A little behind)")
print("=" * 80)
result = simulate_flash_validation(
    week_num=20,
    annual_goal=500,
    cumulative_progress=160,  # 160 commits through week 19 (close to pace)
    this_week_commits=8       # 8 this week (below expected 10)
)
print(f"Annual Goal: {result['annual_goal']}")
print(f"Expected by Week 20: {result['expected_pace']}")
print(f"Actual: {result['actual_progress']}")
print(f"Variance: {result['variance']} commits")
print(f"Status: {result['status']}")
print(f"Submit Enabled: {result['submit_enabled']}")
print(f"\nFlash Feedback:\n{result['feedback']}")
print(f"\nConcrete Actions:")
for i, action in enumerate(result['actions'], 1):
    print(f"  {i}. {action}")

print("\n" + "=" * 80)
print("SCENARIO 3: ON_TRACK (Exactly on pace)")
print("=" * 80)
result = simulate_flash_validation(
    week_num=20,
    annual_goal=500,
    cumulative_progress=180,  # 180 commits through week 19 (on pace)
    this_week_commits=10      # 10 this week (exactly expected)
)
print(f"Annual Goal: {result['annual_goal']}")
print(f"Expected by Week 20: {result['expected_pace']}")
print(f"Actual: {result['actual_progress']}")
print(f"Variance: {result['variance']} commits")
print(f"Status: {result['status']}")
print(f"Submit Enabled: {result['submit_enabled']}")
print(f"\nFlash Feedback:\n{result['feedback']}")
print(f"\nConcrete Actions:")
for i, action in enumerate(result['actions'], 1):
    print(f"  {i}. {action}")

print("\n" + "=" * 80)
print("SCENARIO 4: AHEAD (Exceeding pace)")
print("=" * 80)
result = simulate_flash_validation(
    week_num=20,
    annual_goal=500,
    cumulative_progress=220,  # 220 commits through week 19 (ahead of pace)
    this_week_commits=15      # 15 this week (ahead of expected 10)
)
print(f"Annual Goal: {result['annual_goal']}")
print(f"Expected by Week 20: {result['expected_pace']}")
print(f"Actual: {result['actual_progress']}")
print(f"Variance: {result['variance']} commits (AHEAD)")
print(f"Status: {result['status']}")
print(f"Submit Enabled: {result['submit_enabled']}")
print(f"\nFlash Feedback:\n{result['feedback']}")
print(f"\nConcrete Actions:")
for i, action in enumerate(result['actions'], 1):
    print(f"  {i}. {action}")

print("\n" + "=" * 80)
print("SUMMARY: Flash Validation Logic")
print("=" * 80)
print("""
Flash Validation Rules:
1. Annual Goal: Each role has a goal (Tech Lead: 500 commits, Workforce Ops: 100 hires, Partner: $5M revenue)
2. Expected Pace: Annual Goal ÷ 52 weeks × Week Number
3. Actual Progress: Year-to-date cumulative + this week's reported amount
4. Variance: Actual - Expected

Status Determination:
- ON_TRACK: Variance ≥ 0 AND < 5% (within 5% of pace)
- AHEAD: Variance ≥ 0 AND ≥ 5% (more than 5% ahead)
- SLIGHT_LAG: Variance between -10 and 0 (small gap)
- CRITICAL_LAG: Variance < -10 (significant gap)

Submit Button:
- ON_TRACK/AHEAD: Submit Enabled ✓ (Flash approves, proceed)
- SLIGHT_LAG: Submit Disabled ✗ (Flash challenges, requires confirmation)
- CRITICAL_LAG: Submit Disabled ✗ (Flash blocks, requires manager discussion)

Flash Coaching:
- Provides specific feedback on why status is concerning
- Lists concrete actions to catch up or maintain pace
- Different messaging for each status to drive behavior change
- Escalates responsibility (manager discussion for critical lag)
""")
