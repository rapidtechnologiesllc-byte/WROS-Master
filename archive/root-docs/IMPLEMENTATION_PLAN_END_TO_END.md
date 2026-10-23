# End-to-End Implementation Plan: AOA (Agent-Oriented Architecture)

**Status:** Ready to build  
**Goal:** SLM → P&L → FLASH → Thunder fully wired with UI  
**Timeline:** 2 weeks  
**Date:** 2026-09-18

---

## PHASE 1: CORE INTEGRATIONS (Days 1-3)

### Task 1.1: SLM Data Export Services
**What:** Create services that export SLM employee intelligence  
**Files to Create:**
```
backend/app/services/slm_export_service.py
├─ export_performance_scores(date) → {employees: [{id, score, skills, trend}]}
├─ export_available_employees() → real-time event stream
└─ export_utilization_snapshot() → {utilization_pct, bench_employees, bench_cost}
```

**Deliverable:** 
- [ ] SLM export API working
- [ ] P&L importing daily performance data
- [ ] Event-driven availability updates

### Task 1.2: P&L Decision APIs (Resource Agents)
**What:** Create P&L endpoints that agents query  
**Files to Create:**
```
backend/app/services/pl_agents/
├─ revenue_agent.py: queries SLM → calculates revenue
├─ cost_agent.py: queries SLM → calculates costs
├─ margin_agent.py: subscribes to revenue + cost → calculates margin
├─ budget_agent.py: tracks hiring budget, gates hiring decisions
└─ bonus_agent.py: calculates bonus eligibility from revenue + performance

backend/app/api/v1/endpoints/pl_agents/
├─ revenue_queries.py: GET /api/v1/pl/revenue/daily-snapshot
├─ cost_queries.py: GET /api/v1/pl/costs/by-employee, /by-project
├─ margin_queries.py: GET /api/v1/pl/margin/current, /by-project
├─ budget_queries.py: GET /api/v1/pl/budget/can-hire, /remaining
└─ bonus_queries.py: GET /api/v1/pl/bonus/eligible/{employee_id}
```

**Deliverable:**
- [ ] All 5 resource agents wired
- [ ] P&L decision APIs returning real data
- [ ] FLASH can query: can_hire?, margin_ranking?, bonus_eligible?

### Task 1.3: Recruitment Resource Agents
**What:** Create recruitment pipeline agents  
**Files to Create:**
```
backend/app/services/recruitment_agents/
├─ sourcing_agent.py: 30 instances, queries SLM for performance benchmarks
├─ screening_agent.py: evaluates candidates against SLM benchmarks
├─ interview_agent.py: schedules with top performers
├─ offer_agent.py: generates offers based on P&L budget + market
└─ pipeline_agent.py: tracks conversion metrics

backend/app/api/v1/endpoints/recruitment_agents/
└─ pipeline_status.py: GET /api/v1/recruitment/pipeline-status
```

**Deliverable:**
- [ ] Sourcing → Screening → Interview → Offer chain wired
- [ ] Conversion metrics tracked
- [ ] FLASH hiring agent uses pipeline

### Task 1.4: Workforce Resource Agents
**What:** Create allocation & utilization agents  
**Files to Create:**
```
backend/app/services/workforce_agents/
├─ allocation_agent.py: queries P&L margin ranking, SLM availability
├─ utilization_agent.py: tracks actual vs target
├─ scheduling_agent.py: prevents conflicts
├─ skill_gap_agent.py: identifies hiring needs
└─ capacity_agent.py: forecasts future needs

backend/app/api/v1/endpoints/workforce_agents/
├─ allocation.py: POST /api/v1/workforce/allocate
├─ utilization.py: GET /api/v1/workforce/utilization-status
└─ skill_gap.py: GET /api/v1/workforce/skill-gap-analysis
```

**Deliverable:**
- [ ] Allocation agent queries P&L before assigning
- [ ] Utilization agent monitors vs 90% target
- [ ] FLASH allocation decisions using these agents

---

## PHASE 2: FLASH ORCHESTRATOR (Days 4-5)

### Task 2.1: FLASH Decision Engine
**What:** Wire FLASH to use all agents  
**Files to Create/Update:**
```
backend/app/services/flash_orchestrator.py
├─ Should query before hiring decisions:
│  ├─ P&L Budget Agent: can_hire?
│  ├─ Recruitment Pipeline Agent: conversion_rate?
│  └─ Sourcing Agent: candidates_available?
├─ Should query before allocation:
│  ├─ P&L Margin Agent: project_ranking?
│  ├─ Workforce Allocation Agent: conflicts?
│  └─ Workforce Utilization Agent: current_usage?
└─ Should publish decisions as events:
   ├─ hiring.approved
   ├─ allocation.executed
   └─ promotion.recommended
```

**Deliverable:**
- [ ] FLASH calls P&L before every hiring decision
- [ ] FLASH calls Margin Agent before allocation
- [ ] All decisions logged (for audit + CEO reporting)

### Task 2.2: CEO Agent Reporting
**What:** Wire CEO dashboard showing FLASH decisions  
**Files to Create:**
```
backend/app/api/v1/endpoints/ceo_reports.py
├─ GET /api/v1/ceo/executive-summary
│  └─ {revenue, margin, headcount, bench_cost, decisions_made, risks}
├─ GET /api/v1/ceo/flash-decisions-this-week
│  └─ {hired: 5, allocated: 12, promoted: 2, bench_reduced: 8}
└─ POST /api/v1/ceo/escalation-response
   └─ CEO decision on escalated items
```

**Deliverable:**
- [ ] CEO dashboard live
- [ ] Shows impact of FLASH decisions
- [ ] Real-time P&L metrics

---

## PHASE 3: FRONTEND UI DASHBOARDS (Days 6-10)

### Task 3.1: P&L Dashboard
**What:** Show real-time P&L metrics  
**Files to Create:**
```
frontend/src/screens/PLDashboard.js
├─ Real-time P&L: Revenue, Costs, Margin, Margin %
├─ Hiring Budget: Allocated, Spent, Remaining
├─ Bench Cost: Employees on bench, Cost/day, Trend
├─ By Project: Revenue, Cost, Margin % (sortable)
└─ Bonus Eligible: List of employees, amounts, rationale
```

**Deliverable:**
- [ ] Dashboard shows live P&L data
- [ ] Updates as decisions made
- [ ] Shows margin impact of hires/allocations

### Task 3.2: Recruitment Pipeline Dashboard
**What:** Real-time recruitment metrics  
**Files to Create:**
```
frontend/src/screens/RecruitmentDashboard.js
├─ Sourcing: Candidates sourced this week, quality scores
├─ Screening: Qualified %, avg quality score
├─ Interviews: Scheduled, completed, recommendation %
├─ Offers: Generated, acceptance rate
├─ Conversion Funnel: Sourced → Hired conversion rate
└─ Time-to-hire: Average days from sourced to offer
```

**Deliverable:**
- [ ] Pipeline dashboard live
- [ ] Shows conversion rates by stage
- [ ] Bottleneck alerts (if stage <70% conversion)

### Task 3.3: Allocation Dashboard
**What:** Real-time allocation status  
**Files to Create:**
```
frontend/src/screens/AllocationDashboard.js
├─ Bench Status: Who's on bench, days, cost/day
├─ Active Allocations: By project, by employee
├─ Utilization: Company %, by skill, by BU
├─ Skill Gap: High-demand skills, supply shortage
├─ Quick Allocate: Form to allocate bench employee to project
└─ Allocation History: Last 10 allocations, FLASH decision rationale
```

**Deliverable:**
- [ ] Real-time bench visibility
- [ ] One-click allocation UI
- [ ] Shows P&L margin when selecting projects

### Task 3.4: CEO Dashboard (Orchestrator View)
**What:** Show FLASH decisions in real-time  
**Files to Create:**
```
frontend/src/screens/CEODashboard.js
├─ Key Metrics:
│  ├─ Revenue YTD vs Target
│  ├─ Margin % vs Target (25% goal)
│  ├─ Headcount vs Target (1500 goal)
│  └─ Bench Cost vs Budget
├─ FLASH Decisions This Week:
│  ├─ Hired: 5 (names, roles, start dates)
│  ├─ Allocated: 12 (projects, margin impact)
│  ├─ Promoted: 2 (names, new roles, raise impact)
│  └─ Bench Eliminated: 8 (cost savings)
├─ Risks & Escalations:
│  ├─ Bench >$15K/day (ALERT)
│  ├─ Margin <20% (WARNING)
│  └─ Skill gap >5 people (ACTION)
├─ Agent Health:
│  ├─ Sourcing Agent: 30 instances, 2.5K candidates/week
│  ├─ Screening Agent: 70% quality match rate
│  ├─ Allocation Agent: <30 min allocation time
│  └─ P&L Agent: Real-time decisions
└─ Decision Log:
   └─ Audit trail of all FLASH decisions (with P&L rationale)
```

**Deliverable:**
- [ ] CEO dashboard shows autonomous system working
- [ ] Real-time P&L impact of decisions
- [ ] Escalations visible

---

## PHASE 4: END-TO-END TESTING (Days 11-12)

### Test 1: New Client Workflow
```
Scenario: Partner says "I have client needing 5 engineers"
Steps:
1. [ ] Skill Gap Agent identifies: need 2 more Python+AWS engineers
2. [ ] Budget Agent approves: ROI > 5x
3. [ ] Sourcing Agents source 30 candidates in 24 hours
4. [ ] Screening Agent qualifies 8 (>75% match)
5. [ ] Interview Agent schedules with top performers
6. [ ] 5 candidates recommended for hire
7. [ ] Offer Agent generates offers
8. [ ] Within 6 weeks: 2 new engineers + 3 from bench allocated
9. [ ] P&L Dashboard shows: +$2M revenue, +$600K profit, +1.2% margin
10. [ ] CEO Dashboard shows: All decisions logged with margin impact
Expected: Complete in 6 weeks, fully autonomous
```

### Test 2: Current Client Demand Workflow
```
Scenario: Existing client says "Need 3 more engineers this month"
Steps:
1. [ ] Allocation Agent finds: 3 people on bench with matching skills
2. [ ] Margin Agent ranks projects: Client project at 40% margin
3. [ ] Allocation Agent assigns: All 3 immediately
4. [ ] Bench Cost Agent recalculates: -$500/day savings
5. [ ] Budget Agent recalculates: +$2.5K/week hiring budget freed
6. [ ] P&L Dashboard shows: Margin improves 35% → 38%
7. [ ] CEO Dashboard shows: Decision made in 30 minutes, profit +$53K
Expected: Allocated in 30 minutes, zero manual work
```

### Test 3: Person on Bench Workflow
```
Scenario: Alice on bench 8 days
Steps:
1. [ ] Cost Agent flags: Bench >5 days (medium urgency)
2. [ ] Allocation Agent queries: SLM skills + available projects
3. [ ] Margin Agent ranks: Assigns to highest-margin project (40%)
4. [ ] Scheduling Agent verifies: No conflicts
5. [ ] Allocation executed: Alice → Project in 15 minutes
6. [ ] Bench Cost: -$400/day (Alice off bench)
7. [ ] Budget Agent: Freed $2.5K hiring budget this week
8. [ ] P&L Dashboard shows: Bench cost down, margin impact +$150K (8-week project)
Expected: Allocated in 15 minutes, removes bench waste
```

---

## PHASE 5: DEPLOYMENT & VERIFICATION (Days 13-14)

### Deploy Steps:
1. [ ] All services deployed to production
2. [ ] P&L agents running 24/7
3. [ ] FLASH orchestrator running continuously
4. [ ] CEO dashboard live and monitoring
5. [ ] All dashboards connected to real backend data

### Verification:
1. [ ] Login as admin@blitzenx.com
2. [ ] Navigate: Employee Conversion → P&L Tracking working
3. [ ] View: P&L Dashboard → Real metrics displayed
4. [ ] View: CEO Dashboard → Agent decisions logged
5. [ ] Test: One complete workflow (allocation or hiring)
6. [ ] Verify: P&L metrics updated in real-time
7. [ ] Check: No manual interventions needed (fully autonomous)

---

## SUCCESS CRITERIA

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| **Backend P&L System** | Working | ✅ Done | ✅ |
| **Frontend P&L Screens** | Complete | ✅ Done | ✅ |
| **SLM → P&L Integration** | Data flowing | ⏳ TBD | Phase 1 |
| **P&L → FLASH Integration** | Decisions gated | ⏳ TBD | Phase 1 |
| **FLASH → CEO Reporting** | Dashboards live | ⏳ TBD | Phase 2 |
| **UI Dashboards** | 4 dashboards live | ⏳ TBD | Phase 3 |
| **End-to-end Workflows** | All 3 tested | ⏳ TBD | Phase 4 |
| **Autonomous Operation** | Zero manual | ⏳ TBD | Phase 5 |
| **Scale to 1500 @ 25%** | Demonstrated | ⏳ TBD | Ready |

---

## NEXT IMMEDIATE ACTION

**Today:** Start Phase 1 Task 1.1 (SLM Export Services)
- Create `slm_export_service.py`
- Wire to P&L daily imports
- Get real data flowing

**Timeline:** 2 weeks to full end-to-end deployment with UI
