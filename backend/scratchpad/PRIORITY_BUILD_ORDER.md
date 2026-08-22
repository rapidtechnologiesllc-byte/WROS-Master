# WROS Priority Build Order - Top 35 Stories for Maximum Impact

**Generated:** 2026-08-15  
**Baseline:** 35 immediately buildable stories (0 unmet dependencies)  
**Blocked:** 182 stories (require dependencies to be completed first)

---

## EXECUTIVE SUMMARY

Only **35 of 217 buildable stories** have no unmet dependencies. These 35 are ready to build immediately. The remaining 182 are blocked waiting for enabler stories to be completed.

**Recommended Build Sequence:**
1. **Tier 1 (Critical Enablers)** - 2 stories, ~9 days
2. **Tier 2 (Major Enablers)** - 4 stories, ~8 days  
3. **Tier 3 (Phase 2/3/4 Foundational)** - 8+ stories, ~27 days
4. **Tier 4 (Analytics & Dashboards)** - 15+ stories, ~48 days

This sequence unblocks the maximum number of downstream stories at each step.

---

## TIER 1: CRITICAL ENABLERS (Blocks 5+ stories each)

**Build these first.** These are the highest-impact stories, each enabling 5+ downstream stories to proceed.

| # | Story | WROS ID | Phase | Effort | Epic | Why It Matters |
|---|-------|---------|-------|--------|------|---|
| 1 | S-155 | HRMS-P901 | 2 | 4 days | Boolean Search & AI Search Intelligence | **Blocks 5 stories.** Unblocks search query optimization, saved search features, and search history tracking. Critical for candidate discovery workflows. |
| 2 | S-316 | HRMS-1101 | 5 | 5 days | Agentic Operations Layer | **Blocks 5 stories.** System orchestration backbone—unblocks all AI agent choreography, webhook handlers, and integration workflows. Foundational for Thunder/agentic infrastructure. |

**Subtotal: 2 stories, 9 days effort**

---

## TIER 2: MAJOR ENABLERS (Blocks 3-4 stories each)

Build immediately after Tier 1. These unblock critical workflows in finance, candidate management, and resource allocation.

| # | Story | WROS ID | Phase | Effort | Priority | Blocks | Why It Matters |
|---|-------|---------|-------|--------|----------|--------|---|
| 3 | S-389 | HRMS-1603 | Gap | 2 days | P0 Critical | 3 | **Finance operations.** Manual invoice mark-as-paid unblocks invoice lifecycle completion, AR follow-up, and payment reconciliation workflows. |
| 4 | S-238 | HRMS-0209 | 3 | 3 days | P0 | 3 | **Revenue visibility.** Opportunity forecast calculation enables forecast dashboards, pipeline forecasting, and margin estimation for projects. |
| 5 | S-296 | HRMS-0708 | 4 | 2 days | P0 | 2 | **Talent acquisition.** Convert candidate to employee on joining unblocks onboarding orchestration, payroll sync, and employment lifecycle. |
| 6 | S-121 | HRMS-P303 | 2 | 3 days | P0 | 2 | **Candidate intelligence.** Candidate Relationship Score (CRS) engine unblocks proactive nurture workflows, personalized messaging, and engagement scoring. |
| 7 | S-283 | HRMS-0603 | 4 | 3 days | P0 | 2 | **Staffing automation.** Search internal bench first (instant match) unblocks rapid resource matching, allocation workflows, and bench optimization. |
| 8 | S-294 | HRMS-0706 | 4 | 3 days | P0 | 2 | **Interview orchestration.** Interview panel assignment & calendar sync unblocks interview scheduling, decision tracking, and hiring workflows. |
| 9 | S-301 | HRMS-0803 | 4 | 3 days | P0 | 2 | **Project management.** Resource-to-project allocation unblocks workload tracking, utilization reporting, and project margin calculation. |
| 10 | S-107 | HRMS-P601 | 2 | 4 days | P0 | 2 | **Hiring rules engine.** Experience eligibility logic (<5yr hard rule) unblocks compliance-based candidate filtering and hiring decision UI. |
| 11 | S-120 | HRMS-P302 | 2 | 4 days | P0 | 2 | **Candidate nurture.** Personalized value messaging engine unblocks proactive outreach, goal-based conversations, and engagement campaigns. |

**Subtotal: 9 stories total (including Tier 1), 25 days effort**

---

## TIER 3: FOUNDATIONAL STORIES (Block 1-2 stories each, P0 priority)

Essential Phase 2/3/4 enablers that unlock specific workflows and features.

| # | Story | WROS ID | Phase | Effort | Blocks | Description |
|---|-------|---------|-------|--------|--------|---|
| 12 | S-291 | HRMS-0703 | 4 | 2 days | 1 | Search internal bench before external |
| 13 | S-299 | HRMS-0801 | 4 | 2 days | 1 | Project lifecycle management (create + status) |
| 14 | S-079 | HRMS-0479 | 2 | 3 days | 1 | Production load testing (AI Recruiter) |
| 15 | S-091 | HRMS-P111 | 2 | 3 days | 1 | Magic link authentication (Candidate Portal) |
| 16 | S-145 | HRMS-P809 | 2 | 3 days | 1 | Sub-vendor candidate AI recruiter onboarding |
| 17 | S-115 | HRMS-P609 | 2 | 4 days | 1 | Hiring manager final hire decision UI |
| 18 | S-304 | HRMS-0806 | 4 | 2 days | 1 | Project revenue estimate & margin indicator |
| 19 | S-118 | HRMS-P612 | 2 | 4 days | 1 | Human dependency measurement dashboard |

**Subtotal: 27 stories total (Tiers 1-3), 51 days effort**

---

## TIER 4: HIGH-VALUE DASHBOARDS & ADMIN PORTALS (0 blockers, P0 priority)

No downstream dependencies—can build in parallel. High business value for executive visibility and operational control.

| # | Story | WROS ID | Phase | Effort | Epic |
|---|-------|---------|-------|--------|------|
| 20 | S-097 | HRMS-P202 | 2 | 3 days | Admin Portal – HR Dashboard |
| 21 | S-098 | HRMS-P203 | 2 | 3 days | Admin Portal – Resource Management Dashboard |
| 22 | S-103 | HRMS-P208 | 2 | 3 days | Technical Portal – BU Head Oversight View |
| 23 | S-104 | HRMS-P209 | 2 | 3 days | Org Role Mapping to Portal View |
| 24 | S-108 | HRMS-P602 | 2 | 3 days | Experience Calculation Logic |
| 25 | S-117 | HRMS-P611 | 2 | 3 days | Org Authority Map Configuration |
| 26 | S-328 | HRMS-1203 | 5 | 3 days | CXO Workforce Utilization View |
| 27 | S-096 | HRMS-P201 | 2 | 4 days | Admin Portal – Recruiting Dashboard |
| 28 | S-119 | HRMS-P301 | 2 | 4 days | Career Goal Conversation Engine |
| 29 | S-306 | HRMS-1001 | 5 | 4 days | Unified Prediction Engine (Talent Signals) |
| 30 | S-326 | HRMS-1201 | 5 | 4 days | CXO Revenue Dashboard |
| 31 | S-345 | HRMS-1310 | 5 | 4 days | Webhook Engine & Integration Health Dashboard |
| 32 | S-286 | HRMS-0606 | 4 | 3 days | Auto Schedule Client Interviews – Rapid Mode |
| 33 | S-330 | HRMS-1205 | 5 | 3 days | Recruiter Productivity Dashboard |
| 34 | S-332 | HRMS-1207 | 5 | 3 days | Bench Cost & Aging Analytics Dashboard |
| 35 | S-298 | HRMS-0710 | 4 | 4 days | AI Candidate Ranking per Job |

**Subtotal: 35 stories total, 104 days effort**

---

## BUILD SEQUENCE RECOMMENDATION

### Week 1-2: Tier 1 + Tier 2 High-Impact (Unblock 20+ downstream stories)
- S-155 (Boolean search generation) – 4 days
- S-316 (System orchestration agent) – 5 days
- S-389 (Manual invoice mark-as-paid) – 2 days
- S-238 (Opportunity forecast) – 3 days

**Result:** After this phase, 20+ previously-blocked stories become buildable.

### Week 3-4: Tier 2 Remainder + Tier 3 (Complete foundation)
- S-296, S-121, S-283, S-294, S-301, S-107, S-120 (Tier 2 remainder) – ~20 days
- S-291, S-299, S-079 (Tier 3 sample) – ~7 days

**Result:** Complete critical staffing, finance, and talent workflows.

### Week 5+: Tier 4 (Analytics & Dashboards)
All Tier 4 stories can run in parallel since they have no blockers. Prioritize by business value:
1. **Executive dashboards first:** S-326 (Revenue), S-328 (Workforce Utilization), S-330 (Recruiter Productivity)
2. **Then portal UIs:** S-097, S-098, S-103, S-104 (Admin & technical portals)
3. **Finally integration:** S-345 (Webhook engine), S-306 (Prediction engine)

---

## PHASE DISTRIBUTION

| Phase | Buildable | In Tier 1-4 | Notes |
|-------|-----------|------------|-------|
| **Phase 2** | 107 | 17 | Largest phase; core portal & compliance rules |
| **Phase 3** | 1 | 1 | Opportunity forecast only |
| **Phase 4** | 49 | 9 | Talent engine, project management, staffing |
| **Phase 5** | 47 | 7 | Analytics, dashboards, AI intelligence layer |
| **Gap Epic** | 13 | 1 | Finance & operations (S-389 only) |

---

## EFFORT DISTRIBUTION

| Category | Stories | Total Effort | Avg/Story |
|----------|---------|--------------|-----------|
| Quick wins (≤1 day) | 0 | 0 days | N/A |
| Medium (1-2 days) | 5 | 7 days | 1.4d |
| Complex (>2 days) | 30 | 97 days | 3.2d |
| **Total** | **35** | **104 days** | **3.0d** |

---

## CRITICAL DEPENDENCIES (Manually Verified)

### Stories with NO Unmet Dependencies (Safe to build now):
All 35 Tier 1-4 stories have all dependencies satisfied (either Done or immediately buildable).

### What's Blocking the Other 182?
- 47 stories waiting for S-155 (Boolean search)
- 45 stories waiting for S-316 (System orchestration)
- 35+ stories waiting for Tier 2 enablers
- 55+ stories waiting for Phase 3/4/5 predecessors

Once Tier 1 and Tier 2 are done, approximately **80-100 additional stories** become immediately buildable.

---

## KEY INSIGHTS

1. **System orchestration (S-316) and Boolean search (S-155) are true bottlenecks** – each blocks 5+ stories. Complete these first to unlock the agentic infrastructure.

2. **Phase 2 dominates immediate capacity** – 17 of 35 buildable stories are Phase 2 (portals, compliance rules, candidate engines). These can be built in parallel with Tier 1/2.

3. **Phase 4 staffing workflows cascade downstream** – Don't underestimate dependencies between resource allocation (S-301), bench matching (S-283), and interview scheduling (S-294).

4. **Analytics tier (S-326, S-328, S-330) can build in parallel** – No blockers, high business value for exec visibility.

5. **Estimated completion for Tier 1-4: ~4-5 weeks** (104 days of work, assuming ~5 engineers or 1 engineer ~20 weeks).

---

## NEXT STEPS

1. **Confirm Tier 1 dependencies** with Avinash – verify S-155 and S-316 have no hidden dependencies not captured in the backlog.
2. **Assign Tier 1 stories to highest-capacity engineers** – these are complex stories (4-5 days each) and block everything else.
3. **Parallelize Tier 2 and Phase 2 portals** – while Tier 1 runs, start Tier 2 stories + Phase 2 admin portals (S-097, S-098, etc.).
4. **Plan re-assessment at week 3** – reassess blockers once Tier 1/2 complete, as 80+ new stories will become available.
