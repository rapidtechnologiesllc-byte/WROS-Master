# End-to-End Test: CEO Goals → Goal Cascading → Flash Validation

**Status:** Ready to test  
**Timeline:** ~10 minutes  
**Coverage:** Full cycle from CEO goal setting through Flash validation

---

## System Under Test

```
CEO Sets Goal (150 consultants)
    ↓
CEO Agent Validates Cascade Math
    ↓
System Auto-Cascades to Departments
    ├─ Workforce Ops: 150 hires/year (37.5/Q, 12.5/month, 2.4/week, 0.34/day)
    ├─ Partners: $5M each (if revenue goal)
    └─ BU Heads: Revenue targets
    ↓
Departments See Their Targets
    ↓
Tech Leads Submit Weekly Reports
    ↓
Flash Validates Against Cascaded Goals
    ├─ Status: ON_TRACK, SLIGHT_LAG, CRITICAL_LAG, or AHEAD
    ├─ Coaching: Specific actions per status
    └─ Submit Gate: Enabled/Disabled based on progress
```

---

## Test Scenario 1: Happy Path - On Track

### Step 1: CEO Sets Goal

**API Call:**
```bash
curl -X POST http://localhost:8080/goals/strategic \
  -H "Authorization: Bearer $JWT_CEO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "goal_name": "Total Consultants",
    "goal_type": "headcount",
    "target_value": 150,
    "unit": "people",
    "year": 2026,
    "cascade_rules": {
      "workforce_ops": {"formula": "direct_assignment", "target": 150},
      "partner": {"formula": "divide_equal", "count": 3},
      "bu_head": {"formula": "divide_equal", "count": 9}
    }
  }'
```

**Expected Response:**
```json
{
  "strategic_goal": {
    "id": "goal-1693468800",
    "name": "Total Consultants",
    "type": "headcount",
    "target": 150,
    "unit": "people",
    "annual": 150,
    "quarterly": 37.5,
    "monthly": 12.5,
    "weekly": 2.4,
    "daily": 0.34
  },
  "cascaded_to": {
    "workforce_ops": [
      {
        "cascaded_goal_id": "cascade-workforce-1693468800",
        "department": "workforce_ops",
        "annual": 150,
        "quarterly": 37.5,
        "monthly": 12.5,
        "weekly": 2.4,
        "daily": 0.34
      }
    ],
    "partners": [
      {
        "cascaded_goal_id": "cascade-partner-0",
        "partner_id": "partner-A",
        "annual": 50,
        "quarterly": 12.5,
        "monthly": 4.17,
        "weekly": 0.96,
        "daily": 0.137
      },
      ... (partner-B, partner-C)
    ],
    "bu_heads": [
      {
        "cascaded_goal_id": "cascade-bu-0",
        "bu_id": "bu-001",
        "annual": 16.67,
        "quarterly": 4.17,
        "monthly": 1.39,
        "weekly": 0.32,
        "daily": 0.046
      },
      ... (9 BUs total)
    ]
  },
  "message": "Goal 'Total Consultants' created and cascaded to all departments"
}
```

**✓ Verify:** 
- Goal created with correct ID
- Cascades calculated to workforce_ops, partners, bu_heads
- Math is correct (150/4=37.5/Q, 150/12=12.5/month, etc.)

---

### Step 2: CEO Agent Validates Cascade

**API Call:**
```bash
curl -X POST http://localhost:8080/goals/strategic/validate-cascade \
  -H "Authorization: Bearer $JWT_CEO_AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "goal_id": "goal-1693468800",
    "proposed_cascades": {
      "workforce_ops": {"target": 150},
      "partner": {"targets": [50, 50, 50]},
      "bu_head": {"targets": [16.67, 16.67, ...]}
    }
  }'
```

**Expected Response:**
```json
{
  "goal_id": "goal-1693468800",
  "timestamp": "2026-08-23T10:30:00",
  "validation_checks": [
    {
      "check": "Cascade Math Accuracy",
      "status": "PASSED",
      "detail": "All cascade targets calculated correctly"
    },
    {
      "check": "Org Capacity Alignment",
      "status": "WARNING",
      "detail": "Cascade targets realistic given current team size? Review with HR."
    },
    {
      "check": "Historical Pace Analysis",
      "status": "PASSED",
      "detail": "Current pace (87/150 consultants) suggests targets are achievable"
    }
  ],
  "status": "APPROVED",
  "ceo_agent_feedback": "Goal cascade validated. Math is correct. Targets align with current pace. Recommend approval with monthly check-ins to monitor progress.",
  "actions": [
    "Approve cascade and activate for all departments",
    "Send notifications to department heads with new targets",
    "Configure Flash validation to use cascaded goals"
  ]
}
```

**✓ Verify:** CEO Agent approved cascade and identified risks

---

### Step 3: Workforce Ops Sees Cascaded Goal

**API Call:**
```bash
curl -X GET http://localhost:8080/goals/cascaded?department=workforce_ops \
  -H "Authorization: Bearer $JWT_WORKFORCE_OPS_TOKEN"
```

**Expected Response:**
```json
{
  "department": "workforce_ops",
  "cascaded_from": "Total Consultants",
  "cascaded_goals": [
    {
      "cascaded_goal_id": "cascade-workforce-001",
      "strategic_goal_name": "Total Consultants",
      "annual": 150,
      "quarterly": 37.5,
      "monthly": 12.5,
      "weekly": 2.4,
      "daily": 0.34,
      "current_progress": 87,
      "week_num": 33,
      "expected_at_week": 95.5,
      "variance": -8.5,
      "status": "SLIGHT_LAG"
    }
  ]
}
```

**✓ Verify:** Workforce Ops sees their cascaded target (150 hires, not some arbitrary number)

---

### Step 4: Tech Lead Submits Report

**API Call:**
```bash
curl -X POST http://localhost:8080/agents/tech-lead/{tech_lead_id}/validate-progress \
  -H "Authorization: Bearer $JWT_TECH_LEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "commits": 12,
    "pull_requests_created": 8,
    "pull_requests_reviewed": 15,
    "bugs_fixed": 3,
    "features_completed": 2,
    "velocity_points": 45,
    "blockers": [],
    "risks": [],
    "morale": 7,
    "next_week_focus": "Refactor auth module"
  }'
```

**Expected Response (Flash Validation):**
```json
{
  "annual_goal": "150 commits",
  "current_progress": 180,
  "expected_pace": 192,
  "actual_progress": 192,
  "pace_variance": 0,
  "variance_pct": 0,
  "status": "ON_TRACK",
  "feedback": "Great! You're on pace. Expected 192 commits by week 33, you're at 192. Keep it up!",
  "concrete_actions": ["Continue current velocity", "Maintain this week's pace"],
  "requires_confirmation": false,
  "submit_enabled": true
}
```

**✓ Verify:** 
- Flash compared to annual goal (500 commits), not week-over-week
- Status = ON_TRACK
- Submit enabled automatically

---

### Step 5: Tech Lead Submits Report

**API Call:**
```bash
curl -X POST http://localhost:8080/agents/tech-lead/{tech_lead_id}/confirm-and-submit \
  -H "Authorization: Bearer $JWT_TECH_LEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tech_lead_id": "tech-lead-001",
    "confirmed_accurate": true,
    "confirmation_comment": "",
    "challenges_addressed": []
  }'
```

**Expected Response:**
```json
{
  "status": "submitted",
  "tech_lead_id": "tech-lead-001",
  "message": "Report submitted and validated. Queued for manager review.",
  "next_recipient": "Manager",
  "timestamp": "2026-08-23T10:35:00",
  "challenges_addressed": [],
  "confirmation_comment": ""
}
```

**✓ Verify:** Report submitted successfully to Manager

---

## Test Scenario 2: Behind Schedule - CRITICAL_LAG

### Tech Lead Reports Low Activity

**API Call:**
```bash
curl -X POST http://localhost:8080/agents/tech-lead/{tech_lead_id}/validate-progress \
  -H "Authorization: Bearer $JWT_TECH_LEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "commits": 3,
    "pull_requests_created": 2,
    "pull_requests_reviewed": 4,
    "bugs_fixed": 1,
    "features_completed": 0,
    "velocity_points": 15,
    "blockers": ["Waiting on design review", "Database migration blocked"],
    "risks": ["May not hit sprint target"],
    "morale": 4,
    "next_week_focus": "Unblock design, resume feature work"
  }'
```

**Expected Response (Flash Validation):**
```json
{
  "annual_goal": "500 commits",
  "current_progress": 90,
  "expected_pace": 192,
  "actual_progress": 93,
  "pace_variance": -99,
  "variance_pct": -51.6,
  "status": "CRITICAL_LAG",
  "feedback": "CRITICAL: You're 99 commits behind pace. At this rate, you'll hit 360, not 500. You need 150+ commits in the next 20 weeks to recover. This is not a report issue - this is an execution issue. Needs manager discussion.",
  "concrete_actions": [
    "IMMEDIATE: Schedule with your manager to discuss velocity gap",
    "Identify blockers preventing higher velocity (meetings? unclear priorities? tech debt?)",
    "Commit to 150 commits over next 20 weeks with specific deliverables assigned"
  ],
  "requires_confirmation": true,
  "submit_enabled": false
}
```

**✓ Verify:**
- Status = CRITICAL_LAG
- Specific action items provided
- Submit blocked until manager discussion
- Feedback explains the gap: "need 150+ commits in next 20 weeks"

---

### Manager Discussion Required

**API Call (Manager approves after discussion):**
```bash
curl -X POST http://localhost:8080/agents/tech-lead/{tech_lead_id}/confirm-and-submit \
  -H "Authorization: Bearer $JWT_TECH_LEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tech_lead_id": "tech-lead-001",
    "confirmed_accurate": true,
    "confirmation_comment": "Discussed with manager. Design review blocking auth work. Manager unblocking today. Will hit 12/week starting next week.",
    "challenges_addressed": ["Unblock design review", "Database migration priority"]
  }'
```

**Expected Response:**
```json
{
  "status": "submitted_with_action_plan",
  "tech_lead_id": "tech-lead-001",
  "message": "Report submitted with action plan. Manager alerted of catch-up commitment.",
  "manager_notification": true,
  "action_plan": {
    "blocker": "Design review",
    "fix_timeline": "Today",
    "target_commits_next_week": 12,
    "recovery_plan": "Focus on auth module + database migration"
  },
  "timestamp": "2026-08-23T10:40:00"
}
```

**✓ Verify:** 
- Report submitted with action plan
- Manager notified of catch-up commitment
- Flash tracking this person's recovery trajectory

---

## Verification Checklist

✅ **Database Integration:**
- [ ] Goals created in database
- [ ] Cascaded goals created and linked to strategic goal
- [ ] Flash queries cascaded_goals correctly

✅ **Frontend Integration:**
- [ ] CEO Goals screen displays list
- [ ] Click "Edit" opens input field
- [ ] Save triggers API call
- [ ] Cascaded goals display in department dashboards

✅ **CEO Agent Validation:**
- [ ] CEO Agent receives cascade proposal
- [ ] Validates math: 150/3 = 50 per partner ✓
- [ ] Validates alignment: Current pace (87/150) achievable ✓
- [ ] Approves cascade or requests changes

✅ **Goal Cascading:**
- [ ] Workforce Ops sees 150 hires/year (37.5/Q, 12.5/month)
- [ ] Partners see $5M each
- [ ] BU Heads see their revenue piece
- [ ] Goals match the cascade math exactly

✅ **Flash Validation:**
- [ ] Reports compared against cascaded goals, not manual settings
- [ ] Correct status (ON_TRACK, SLIGHT_LAG, CRITICAL_LAG, AHEAD)
- [ ] Specific feedback explaining variance
- [ ] Submit gate works (ON_TRACK = enabled, CRITICAL_LAG = disabled)
- [ ] Confirmation workflow for behind-schedule reports

✅ **Lifecycle Tracking:**
- [ ] Annual, Quarterly, Monthly, Weekly, Daily targets visible
- [ ] Progress shown at each level
- [ ] Bottleneck identified (most constrained level)

---

## Success Criteria

**Test passes if:**

1. ✅ CEO sets goal → Cascades auto-calculate correctly
2. ✅ CEO Agent validates math and approves
3. ✅ Departments see cascaded targets (not manual settings)
4. ✅ Flash validation uses cascaded goals for accuracy
5. ✅ ON_TRACK reports auto-submit, CRITICAL_LAG blocked
6. ✅ Coaching is specific ("need 150 more commits")
7. ✅ End-to-end: Goal → Cascade → Validation → Submit works seamlessly

**If all pass:** System is production-ready for live testing

---

## How to Run Test

### Prerequisites
```bash
# Backend running on localhost:8080
# Frontend running on localhost:3000
# Database seeded with test users:
#   - CEO token (can set strategic goals)
#   - CEO Agent token (can validate cascades)
#   - Workforce Ops token (sees cascaded goals)
#   - Tech Lead token (submits reports)
#   - Manager token (reviews reports)
```

### Execute Test
```bash
# 1. Run test scenario 1 (happy path)
bash test_goals_cascade.sh scenario1

# 2. Run test scenario 2 (critical lag)
bash test_goals_cascade.sh scenario2

# 3. Run full end-to-end in browser
# Open http://localhost:3000
# Login as CEO
# Navigate to "Strategic Goals"
# Set "150 consultants" target
# Verify cascade to Workforce Ops
# Login as Tech Lead
# Submit weekly report
# Verify Flash validation
```

---

## Expected Timeline

- Goal creation: 1 second
- CEO Agent validation: 2 seconds
- Cascade to all departments: <1 second
- Tech lead report submission: 3 seconds
- Flash validation: <1 second
- **Total end-to-end:** ~7 seconds

---

## Known Limitations (v1)

- ⚠️ Mock data (database queries not implemented yet)
- ⚠️ Manual CEO Agent approval (not autonomous yet)
- ⚠️ No historical tracking (will add with database layer)
- ⚠️ No weighted division (equal split only)

---

## Next Phase

After E2E test passes:
1. Wire real database queries
2. Automate CEO Agent validation
3. Add historical tracking for cascade adjustments
4. Implement weighted division formulas

