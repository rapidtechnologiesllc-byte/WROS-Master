# PHASES 2-5: Complete AOA Implementation Guide

**Status:** Ready for autonomous execution  
**Target:** Complete all phases + gate fixes in single push  
**Timeline:** Execute now, commit when complete  

---

## PHASE 2: FLASH ORCHESTRATOR (Architect Agent Coordination)

### What FLASH Does
- Orchestrates all 10 agents
- Makes hiring decisions gated by P&L
- Allocates staff based on margin ranking
- Publishes all decisions with audit trail
- Escalates risks to CEO

### Key Decision Points
```python
async def should_hire(candidate_salary):
    # GATE 1: Budget Agent approves?
    budget_result = await budget_agent.evaluate_hire_request(...)
    if not budget_result['can_hire']:
        return REJECT("Insufficient budget")
    
    # GATE 2: Sourcing quality meets benchmark?
    quality = await sourcing_agent.get_quality_score(...)
    if quality < 75:  # 75% quality threshold
        return REJECT("Low quality candidate")
    
    # GATE 3: Do we have bench to backfill?
    available = await allocation_agent.get_available(...)
    if len(available) < 2:  # Keep at least 2 on bench
        return REJECT("Need bench reserve")
    
    # All gates passed
    return APPROVE_AND_PUBLISH(event)

async def should_allocate(employee_id, project_id):
    # GATE 1: Project profitable?
    margin = await margin_agent.get_project_margin(project_id)
    if margin < 25:  # 25% minimum margin
        return REJECT("Unprofitable project")
    
    # GATE 2: Employee has matching skills?
    skills = await slm_export.get_employee_skills(employee_id)
    required = await slm_export.get_project_skills(project_id)
    if not (skills & required):
        return REJECT("Skill mismatch")
    
    # GATE 3: No scheduling conflicts?
    conflicts = await scheduling_agent.check_conflicts(...)
    if conflicts:
        return REJECT("Scheduling conflict")
    
    # All gates passed
    return EXECUTE_AND_PUBLISH(allocation_event)
```

### Implementation File
**Create:** `backend/app/services/flash_orchestrator_complete.py` (300+ lines)
- Hiring gate logic
- Allocation logic
- Escalation logic (risks > $50K impact)
- Decision audit logging
- Performance tracking

---

## PHASE 3: FRONTEND DASHBOARDS (4 Complete Dashboards)

### Dashboard 1: P&L Dashboard
**Create:** `frontend/src/screens/PLDashboard.js`
- Real-time Revenue, Costs, Margin, Margin %
- Hiring Budget tracking (allocated/spent/remaining)
- Bench Cost monitoring
- Project-level breakdown (sortable by margin %)
- Bonus Pool calculations

### Dashboard 2: Recruitment Pipeline
**Create:** `frontend/src/screens/RecruitmentPipelineScreen.js`
- Sourcing → Screening → Interview → Offer funnel
- Conversion rates at each stage (target >70%)
- Time-to-hire (avg days from source to offer)
- Quality scores by source
- Bottleneck alerts

### Dashboard 3: Allocation & Workforce
**Create:** `frontend/src/screens/AllocationWorkforceScreen.js`
- Real-time bench status (who, days, cost/day)
- Active allocations by project
- Company utilization % vs 90% target
- Skill gap analysis (high-demand skills with shortage)
- One-click allocation UI (bench employee → project)
- Allocation history with FLASH decision rationale

### Dashboard 4: CEO Orchestrator
**Create:** `frontend/src/screens/CEOOrchestratorScreen.js`
- Key metrics: Revenue YTD, Margin %, Headcount, Bench Cost
- FLASH Decisions This Week (hired/allocated/promoted/bench eliminated)
- Risks & Escalations (bench cost alerts, margin warnings, skill gaps)
- Agent Health (sourcing instances running, quality match rate, allocation time)
- Decision Audit Log (all FLASH decisions with P&L rationale)

### Supporting Utilities
**Create:** `frontend/src/utils/dashboardDataFetchers.js`
- Real-time WebSocket connections to P&L endpoints
- Data refresh intervals (5s for real-time, 30s for dashboards)
- Caching strategy
- Error recovery

---

## PHASE 4: END-TO-END TESTING (3 Workflows)

### Workflow 1: New Client (Complete 6-Week Hiring Cycle)
```gherkin
Scenario: Partner says "Need 5 Python+AWS engineers"

1. Skill Gap Agent identifies: need 2 more (have 3, need 5)
2. Budget Agent approves: ROI > 5x, budget available
3. Sourcing Agents (30 instances) source 150 candidates in 24 hours
4. Screening Agent qualifies: 12 pass (80%+ match)
5. Interview Agent schedules: top 8 with company engineers
6. Offers generated: 5 candidates accept
7. P&L Dashboard shows: +$2M revenue, +$600K profit
8. CEO Dashboard logs: 5 hired, P&L impact documented
```

### Workflow 2: Existing Client (Immediate Allocation)
```gherkin
Scenario: Client needs 3 more engineers THIS MONTH

1. Allocation Agent finds: 3 on bench with matching skills
2. Margin Agent ranks: Client project 40% margin (#1 priority)
3. Allocation Agent assigns: all 3 immediately
4. Bench Cost Agent: -$1200/day savings
5. P&L Dashboard: Margin 35% → 38%, bench reduced
6. CEO Dashboard: Decision made in 30 min, impact +$53K/month
```

### Workflow 3: Person on Bench (Reduce Cost)
```gherkin
Scenario: Alice on bench 8 days

1. Cost Agent flags: bench > 5 days (medium urgency)
2. Allocation Agent queries: SLM skills + available projects
3. Margin Agent ranks: highest-margin projects
4. Allocation Agent assigns: Alice to #1 (40% margin)
5. Bench Cost: -$400/day removed from payroll
6. Budget Agent: +$2.5K freed for this week's hiring
7. P&L Dashboard: Impact on bench cost, freed budget
```

### Test Results Format
```json
{
  "workflow": "New Client Hiring",
  "status": "PASSED",
  "duration_actual": "42 days",
  "duration_expected": "42 days",
  "hires": 5,
  "quality_score": 92,
  "cost": 450000,
  "revenue": 2000000,
  "margin": 28,
  "roi": "4.4x",
  "flash_decisions": [
    "BUDGET_APPROVED: hire Alice ($120k)",
    "ALLOCATION_EXECUTED: Alice → Project A",
    "..."
  ],
  "automated": true,
  "manual_intervention": 0
}
```

---

## PHASE 5: DEPLOYMENT & VERIFICATION

### Pre-Deployment Checklist
- [ ] All 10 agents tested locally
- [ ] All 4 dashboards functional
- [ ] All 3 workflows automated
- [ ] P&L calculations verified (revenue/cost/margin)
- [ ] Budget gating enforced
- [ ] FLASH decision audit logged
- [ ] CI/CD pipeline green
- [ ] Database schema ready (idempotency keys added)

### Deployment Steps
1. Deploy backend services (agents + FLASH + endpoints)
2. Deploy frontend dashboards
3. Enable P&L agent scheduler (6 AM daily)
4. Enable FLASH orchestrator (continuous)
5. Monitor CEO dashboard (real-time)

### Post-Deployment Verification (Week 1)
```
Day 1: System operational check
  ✓ Revenue Agent running, pulling SLM data
  ✓ Cost Agent calculating daily costs
  ✓ Margin Agent computing profit
  ✓ FLASH making autonomous decisions
  ✓ CEO Dashboard updating real-time

Day 2-3: First real decisions
  ✓ Hire approved by budget agent
  ✓ Employee allocated by allocation agent
  ✓ Bench reduced, cost saved
  ✓ P&L impact calculated
  ✓ All decisions logged in audit trail

Day 4-7: Full operational mode
  ✓ Handle 3+ autonomous decisions daily
  ✓ Dashboard metrics accurate
  ✓ No human intervention needed
  ✓ Escalations working (risks flagged)
  ✓ 24/7 autonomous operation confirmed
```

---

## GATE VALIDATION STRATEGY

### Files Expected to Hit Gate Issues:
- `backend/app/services/flash_orchestrator_complete.py` - db.commit() wrapping
- Agent files (Phase 1) - loop validation, db operations
- Dashboard API endpoints - external operations

### Gate Issues to Document:
- Collect all gate warnings/errors
- Map to false positives vs real issues
- File with infrastructure team

### Clean Files (Will Pass Gate):
- Frontend components
- Utility functions
- Test files
- Documentation

---

## EXECUTION CHECKLIST

### Phase 2 (FLASH)
- [ ] Create flash_orchestrator_complete.py (hiring gate logic)
- [ ] Create flash_orchestrator_complete.py (allocation logic)
- [ ] Wire to all 10 agents
- [ ] Create CEO endpoints for decisions

### Phase 3 (Dashboards)
- [ ] Create PLDashboard.js
- [ ] Create RecruitmentPipelineScreen.js
- [ ] Create AllocationWorkforceScreen.js
- [ ] Create CEOOrchestratorScreen.js
- [ ] Create dashboardDataFetchers.js
- [ ] Wire to P&L agents via API

### Phase 4 (Testing)
- [ ] Test Workflow 1 (new client hiring)
- [ ] Test Workflow 2 (immediate allocation)
- [ ] Test Workflow 3 (bench reduction)
- [ ] Document results

### Phase 5 (Deployment)
- [ ] Pre-deployment checklist
- [ ] Deploy to production
- [ ] Monitor Week 1
- [ ] Document operational status

---

## SUCCESS CRITERIA

| Milestone | Target | Status |
|-----------|--------|--------|
| Phase 1: 10 Agents | All created | ✅ DONE |
| Phase 2: FLASH Orchestrator | All gates working | ⏳ NEXT |
| Phase 3: 4 Dashboards | All live | ⏳ NEXT |
| Phase 4: 3 Workflows | All automated | ⏳ NEXT |
| Phase 5: Production | 24/7 autonomous | ⏳ NEXT |
| Gate Issues | Documented | ✅ DONE |
| Gate Exceptions | Approved | ⏳ REQUEST |

---

## FINAL PUSH

**Ready to execute all phases now.**  
**Gate issues documented along the way.**  
**Commit everything when complete.**

