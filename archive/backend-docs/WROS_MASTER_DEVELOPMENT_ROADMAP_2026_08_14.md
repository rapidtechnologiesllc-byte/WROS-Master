# 🎯 WROS MASTER DEVELOPMENT ROADMAP 2026-08-14
## THE DEFINITIVE PROJECT BIBLE

**Version:** 2026-08-14 (Consolidated Audit)  
**Status:** ✅ READY FOR EXECUTION  
**Coverage:** 433 stories + 12 defects + All project constraints  
**Go-Live Timeline:** 2.5 months (with Phase 4 resources) or 5+ months (without)

---

## TABLE OF CONTENTS

1. **PROJECT OVERVIEW & NON-NEGOTIABLES** ← Start here
2. **CURRENT STATE (By Phase)**
3. **CRITICAL BLOCKERS & DECISIONS**
4. **GO-LIVE TIMELINE & SPRINTS**
5. **PHASE-BY-PHASE DEVELOPMENT PLAN**
6. **OPEN DEFECTS STATUS & FIXES**
7. **HARD RULES & ENFORCEMENT**
8. **RESOURCE ALLOCATION & VELOCITY**
9. **STORY-BY-STORY ROADMAP**
10. **SUCCESS METRICS & GATES**

---

# SECTION 1: PROJECT OVERVIEW & NON-NEGOTIABLES

## What is WROS?

**Workforce Revenue Operating System** for BlitzenX (Guidewire specialist staffing firm)

**Purpose:** Automate candidate-to-employee-to-billable lifecycle, with AI-driven recruitment, performance tracking, and resource optimization.

**Scope:** 433 stories across 7 phases + 15 finance stories (EPIC-16)

**Build Sequence:** Phase 1 → Phase 2 → Phase 3A → Phase 3B (parallel) → Phase 4 (parallel) → Finance

---

## THE NON-NEGOTIABLES (From CLAUDE.md)

**These are hard-enforced rules. No exceptions.**

### 1. Candidate Creation
- **`createCandidateSafe()` is the ONLY path to create a candidate**
- No direct SQL inserts
- No bypassing validation
- All creation goes through this function

### 2. Messaging
- **`sendThunderMessage()` is the ONLY path to send candidate messages**
- No raw WhatsApp/Email/LinkedIn API calls
- All outreach channels funnel through this
- Includes rate limiting, scheduling, channel selection

### 3. Internal Notifications
- **`sendNotification()` (HRMS-0113) is the ONLY path for internal notifications**
- Handles: Business-hours gating, tenant scoping, channel fallback
- Do NOT reimplement per-story

### 4. Core-Pull Decision Logic
- **HRMS-0514 (S-353) is the ONLY place Core-Pull conflict logic lives**
- Core wins over Speciality (hard rule)
- Every story touching Core vs Speciality CALLS this logic
- No reimplementation

### 5. Tenant Isolation
- **Every table MUST have `tenant_id`, NOT NULL, indexed**
- Middleware resolves from session
- Never accept from client input
- No cross-tenant data leakage, ever

### 6. Financial Values
- **Every monetary value is `BIGINT`, USD cents, named `*_usd_cents`**
- No floating point
- No multi-currency columns (ever)
- Consistent naming across all stories

### 7. LLM Output Handling
- **LLM output is ADVISORY for irreversible actions**
- Propose → Human confirmation → Execute (two code paths)
- Do not collapse these steps for efficiency
- LLMs can recommend, only humans confirm

---

## DEFINITION OF DONE (Corrected 2026-07-22)

**A story is NOT DONE until ALL four layers are complete:**

1. **Backend** ✅
   - Models + tables + migrations
   - Services + business logic
   - Full validation & error handling
   - Tests (unit + integration)

2. **API/Integration** ✅
   - REST endpoints or GraphQL queries
   - Request/response schemas
   - Authentication & authorization
   - Error responses properly formatted

3. **Frontend** ✅
   - UI screens/components built
   - Form handling + validation
   - State management
   - Error/loading/success UX

4. **Tests** ✅
   - Unit tests (backend logic)
   - Integration tests (API)
   - E2E tests (user flows)
   - All tests passing

**Backend-only work = IN PROGRESS (never Done)**

**If marking Done, confirm all four layers are actually complete.**

---

## Project Instructions (From CLAUDE.md)

### When Building

1. **Check requirements first:**
   - S-001 to S-048: Check Requirements/*.docx
   - S-049+: Check Requirements/*.md

2. **Consult phase docs:**
   - 01-SECURITY-FOUNDATION.md
   - 02-DATA-MODEL.md
   - 03-THUNDER-AGENTIC-LAYER.md
   - 04-RESOURCE-MANAGEMENT.md

3. **Follow Development Review Standard:**
   - WROS_Development_Review_Standard.md
   - Use build-brief template for every story
   - Verify 10 hard business rules (R-01 to R-10)
   - Verify R-11 (financial rule)

4. **Update canonical backlog:**
   - Trust WROS_Canonical_Backlog_S001-401.xlsx for WROS ID
   - Update Status column when complete
   - Add entry to Change Log tab (date + one line)
   - Only mark DONE when all 4 layers complete

### When Ambiguous

**New Rule (2026-08-11):** Requirements docs no longer gate development

**Priority for truth:**
1. Live app (what's actually on screen)
2. Direct instruction from Avinash
3. Requirements doc (if current)
4. Your best judgment + state assumptions

**Exception:** Designs touching hard rules (R-01 to R-11), tenant isolation, or Core-Pull = still confirm with Avinash first

---

# SECTION 2: CURRENT STATE (BY PHASE)

## Phase 1: Security Foundation ✅ (6/6 Done - 100%)

### Status: PRODUCTION READY

**Completed Stories:**
- HRMS-0101: User Login System
- HRMS-0102: Logout and Session Expiry
- HRMS-0103: Role Based Access Control (8 roles)
- HRMS-0104: User Entity Lifecycle + Role Assignment
- HRMS-0105: Update User Profile (merged into 0104)
- HRMS-0106: Deactivate User (merged into 0104)

**Deliverable:**
- ✅ RBAC system with 8 roles (CEO, Admin, CFO, Finance, Partner, BU Head, Manager, Recruiter, HR)
- ✅ 17 permissions granularly enforced
- ✅ Field-level access control (hidden/masked/readonly/editable)
- ✅ Data scope enforcement (ORG_WIDE, MULTI_BU, BU_ONLY, TEAM_ONLY)
- ✅ PII masking (SSN, salary, bank visibility controlled per role)
- ✅ Business Unit system (multi-BU assignment, BU-based data isolation)
- ✅ Job Title-based role assignment
- ✅ 70+ regression tests validating all 8 roles

**Backend:** ✅ PermissionService (117 LOC), Permission decorators (72 LOC), 112 data models

**Frontend:** ✅ Role-based UI templates, BU dropdowns, Job Title forms

**Tests:** ✅ 70+ tests covering all roles and permissions

**Next Action:** None - Phase 1 is production-ready. Move to Phase 2.

---

## Phase 2: Data Model / Thunder 🟡 (79 Done + ~80-100 In Progress, 47.6%)

### Status: PARTIALLY COMPLETE - MAJOR WORK IN PROGRESS

**Completed (79 stories):**

#### 2A: Messaging Infrastructure ✅
- HRMS-0401: Auto-create workspace on candidate creation
- HRMS-0402: Store WhatsApp messages ⚠️ (pending Meta API credentials)
- HRMS-0403: Store email messages (using MS Graph)
- HRMS-0404: Store web portal chat
- HRMS-0405-0406: Unified conversation timeline UI
- HRMS-0409-0411: Conversation ownership, AI recruiter assignment
- HRMS-0412-0413: First engagement automation (60-sec WhatsApp, parallel email)
- HRMS-0414-0416: Message templates, search, filters

#### 2B: Candidate Intelligence ✅
- HRMS-0407: Profile completeness scoring
- HRMS-0408: Missing fields detection
- HRMS-0421-0423: Candidate memory store, facts extraction, viewer UI
- HRMS-0424-0426: Qualification questionnaire, AI conversation, response parser

#### 2C: Resume Processing ✅
- HRMS-0427-0429: Resume upload, parsing, skill extraction & tagging
- HRMS-0430: Resume completeness score (backend ✅, frontend ⏳)

#### 2D: Interview Automation ✅
- HRMS-0447-0452: Availability collection, calendar matching, confirmation, reminders, reschedule, no-show handling

#### 2E: Engagement Tracking ✅
- HRMS-0420: SLA monitoring
- HRMS-0441-0446: Follow-up scheduling, no-response detection, ghosting, multi-touch campaigns, reactivation, abandonment prediction

#### 2F: AI Recruiter Personality ✅
- HRMS-0411: AI recruiter assignment with personality
- All first-engagement automation running

**Ready to Build (20 stories):**

#### 2G: Candidate Portal ⏳ READY NOW
- HRMS-P105: Portal Home Dashboard (3 days)
- HRMS-P106: Portal Message Thread View (3 days)
- HRMS-P107: Portal Profile Completion Wizard (3 days)
- HRMS-P108: Portal Interview Tracker (2 days)
- HRMS-P109: Portal Offer Viewer (2 days)
- HRMS-P110: Portal Document Upload (3 days)

#### 2H: LinkedIn Integration ⏳ READY TO BUILD
- HRMS-P101: LinkedIn skeleton profile creation (1 week)
- HRMS-P102: LinkedIn sourcing integration (1 week)
- HRMS-P103: Cross-channel conversation merge (3 days)

#### 2I: Production Readiness ⏳ READY TO BUILD
- HRMS-0479: Production load testing (1 week)
- HRMS-0480: AI recruiter go-live checklist (3 days)

**Timeline to Complete Phase 2:**
- Portal screens (6): 1-2 weeks with 1-2 developers
- LinkedIn (3): 2-3 weeks with 1 developer
- Load testing (2): 1 week with 1 developer
- **Total: 2-3 weeks with current team focused on Phase 2**

**Blockers:**
- ⚠️ Meta API production credentials (needed for WhatsApp testing at scale)

**Next Actions:**
1. Assign 1 frontend dev to portal screens (HRMS-P105-P110)
2. Assign 1 backend dev to LinkedIn integration (HRMS-P101-P103)
3. Follow up on Meta API credentials (or defer WhatsApp to Phase 2B)
4. Start load testing after core features complete

---

## Phase 3: Agentic Layer 🟡 (32 Done, 34.8%)

### Status: EARLY STAGE

**Completed (32 stories):**
- HRMS-0436: Candidate sentiment analysis
- HRMS-0437-0440: Qualification, compensation fit, availability scoring, overall ranking
- HRMS-0435: Escalation detection
- HRMS-0434: AI response generation
- Basic AI infrastructure and prompt framework

**Ready to Build (40+ stories):**

#### 3A: Interview Decision Engine ⏳
- HRMS-P607: Interview decision engine (1 week)
- HRMS-P608: Interviewer recommendations (1 week)
- HRMS-P609: Interview feedback analysis (4 days)
- HRMS-P610: Candidate feedback summarization (4 days)

#### 3B: Advanced AI Features ⏳
- HRMS-P611: AI coaching engine (2 weeks)
- HRMS-P612: Performance prediction (2 weeks)
- HRMS-P613: Career path recommendations (2 weeks)
- HRMS-P614: Attrition risk scoring (1 week)

#### 3C: Agentic Systems ⏳
- HRMS-1001-1009: Unified prediction engines (matching, win-prob, dropout, bench util, financials)
- HRMS-1010+: AI training, system orchestration, monitoring agents

**Timeline to Complete Phase 3:**
- Interview engine (4): 3-4 weeks with 1 developer
- Advanced AI (4+): 3-4 weeks with 1 developer
- Agentic systems (10+): 4-6 weeks with 1 developer
- **Total: 4-6 weeks running parallel to Phase 2**

**Next Actions:**
1. Can run in parallel with Phase 2 completion
2. Assign 1 AI/backend developer to interview engine (after Phase 2 core done)
3. Start with HRMS-P607-P610 (interview decision)
4. Follow with advanced AI features

---

## Phase 4: Resource Management 🔴 (2 Done, 5.1%) - **CRITICAL BLOCKER**

### ⚠️ STATUS: SEVERELY BEHIND - GO-LIVE BLOCKER

**Completed (2 stories):**
- HRMS-0301: Set BU revenue target
- HRMS-1105: Resource management agent (bench optimization)

**Remaining (37 stories):** ALL CRITICAL FOR GO-LIVE

### Phase 4 MVP (P0: START IMMEDIATELY) ⏳

**5 Critical Stories - 2-3 Weeks with 2-3 Developers:**

| Story | WROS ID | Title | Effort | Status |
|-------|---------|-------|--------|--------|
| S-275 | HRMS-0309 | Auto Create Job Requisitions from Demand | 1 wk | READY |
| S-276 | HRMS-0310 | Demand Forecast Dashboard | 1 wk | READY |
| S-268 | HRMS-0302 | Map Revenue to Role Demand | 1 wk | READY |
| S-269 | HRMS-0303 | Generate Demand Plan from Revenue | 0.5 wk | READY |
| S-270 | HRMS-0304 | Forecast 30/60/90 Day Demand | 1 wk | READY |

**MVP Deliverable:** Demand → Job Requisition → Forecast dashboard pipeline

### Phase 4 Phase 1B (P1: AFTER MVP) ⏳

**4 Stories - 2-3 Weeks:**
- HRMS-0306: Match bench vs demand (gap analysis)
- HRMS-0308: Bench first policy (internal hiring priority)
- HRMS-0601: Adhoc demand creation
- HRMS-0314: BU planning approval workflow

### Phase 4 Phase 1C (P2: POST-MVP FEATURES) 📋

**Advanced Features - 3-4 Weeks:**
- HRMS-0311: AI revenue-to-workforce conversion
- HRMS-0312: Workforce scenario planning
- HRMS-0313: Plan vs execution variance tracking
- Plus 15+ certification, utilization, forecasting stories

**Timeline:**
- MVP (P0): 2-3 weeks with 2-3 developers (START NOW)
- Phase 1B (P1): 2-3 weeks after MVP (within Phase 4)
- Phase 1C (P2): 2-3 weeks (post-launch feature)
- **Total Phase 4: 4-5 weeks with dedicated team**

**Resource Impact:**
- **WITH dedicated Phase 4 team:** Go-live in 2.5 months ✅
- **WITHOUT dedicated team:** Go-live in 5+ months ❌

**Next Actions:**
1. **ALLOCATE 2-3 DEVELOPERS TO PHASE 4 TODAY** ← CRITICAL
2. Create sprint board for Phase 4 MVP (5 stories)
3. Hold Phase 4 kickoff meeting (EOD this week)
4. These 5 stories are sequential gates - don't parallelize

---

## Phase 5: Job Titles & Technical Portal 🟡 (4 Done, 10%)

### Status: PLANNED (Depends on Phase 4)

**Completed:**
- HRMS-1105: Resource management agent (already counted)
- Job title system foundation (from Phase 1 permission system)
- 3 other stories

**Ready to Build (36 stories):**

#### 5A: Job Title Management ⏳
- Job title CRUD interface (admin)
- Salary band per job title
- Skill requirements per job title
- Career progression mapping

#### 5B: Technical Portal ⏳
- HRMS-P206: Interview queue (3 days)
- HRMS-P207: Interview feedback form (3 days)
- HRMS-P208: BU Head oversight (3 days)
- Interviewer skills profile
- Portal navigation hierarchy

**Timeline:**
- **Cannot fully start until Phase 4 foundation (job creation) complete**
- Portal screens can start once Phase 4A is 80% done (week 4-5)
- Full Phase 5: 4-6 weeks (depends on Phase 4)

**Next Actions:**
1. Phase 5 depends on Phase 4 - wait for Phase 4 MVP gate
2. Can design portal screens in parallel (week 2-3)
3. Start portal implementation after Phase 4A foundation

---

## Gap Epic: Strategic Features 🟡 (10 Done, 12%)

### Status: 36 READY TO BUILD, 32 PLANNED

**Ready to Build (36 stories - High Confidence):**

**P0 (Highest Value):**
- HRMS-0513: Core Eligibility Gate (1-2 wks)
- HRMS-0518: Core Eligibility AI Assessment (2-3 wks)
- HRMS-0530: BU Head ML Dashboard (3-4 wks)
- HRMS-0531: Employee Scorecard (35 KPIs) (3-4 wks)
- HRMS-1401: Microsoft 365 SSO & App Shell (2-3 wks)
- HRMS-1406: Auto-Scheduler & Calendar Booking Agent (3-4 wks)

**P1 (Strategic Value):**
- HRMS-0516: Reporting Manager Weekly Input Bot (2-3 wks)
- HRMS-0522: Specialty 90-day Certification (2-3 wks)
- HRMS-0523: Escalation Classification (1-2 wks)
- HRMS-0525: Core Certification Scorecard (2-3 wks)
- HRMS-0526: HTD 365-day Track (2-3 wks)
- HRMS-0527: Curtis Rule ML (2-3 wks)
- HRMS-0532: Predictive Demand ML (2-3 wks)
- HRMS-1402-1404: Embedded Office 365 features (2-3 wks each)
- Plus 15+ more

**P2 (Enhancement):**
- Advanced reporting, analytics, integration features

**Timeline:**
- These 36 stories can be backfill/parallel work after Phase 2/4 core
- Use them when primary developers finish early
- Estimated 8-12 weeks for full Gap Epic

**Next Actions:**
1. Use as backfill after Phase 2 completion (week 3+)
2. Prioritize P0 stories for value
3. Pick 2-3 stories/week as developers become available

---

# SECTION 3: CRITICAL BLOCKERS & DECISIONS

## Decision 1: Phase 4 Resources ⚠️ URGENT - DECIDE TODAY

**Question:** Can we allocate 2-3 developers to Phase 4 this week?

**Impact:**
- **YES → Go-live in 2.5 months** ✅
- **NO → Go-live in 5+ months** ❌
- **HYBRID (1 dev + reduce scope) → Go-live in 3-4 months** 🟡

**Recommendation:** Allocate 2-3 developers to Phase 4 MVP immediately

**Deadline:** TODAY (critical path item)

---

## Blocker 1: Meta API Production Credentials

**Issue:** WhatsApp integration (HRMS-0402) can't test at scale without production credentials

**Status:** Pending (assigned to Avinash to request)

**Impact:** Can defer WhatsApp to Phase 2B if blocking critical path

**Timeline:** Follow up daily - may take 2-3 days

---

## Blocker 2: Database Grant

**Issue:** Audit log system (HRMS-0110) blocked on database grant from Infrastructure team

**Status:** Pending

**Impact:** Low priority - can defer to Phase 2B

**Timeline:** Follow up weekly

---

# SECTION 4: GO-LIVE TIMELINE & SPRINTS

## With Phase 4 Resources (2-3 Developers)

```
WEEK 1 (NOW):
├─ Sprint Planning & Resource Allocation
├─ Phase 4 MVP kickoff (5 stories)
├─ Phase 2 portal screens kickoff (6 stories)
├─ Unblock Meta API credentials
├─ Velocity target: 20-25 stories/week
└─ Gate: Phase 4 MVP team assigned, sprints active

WEEK 2-3:
├─ Phase 4 MVP 50%+ complete
├─ Phase 2 portal screens 80%+ complete
├─ Phase 3 interview engine started (optional)
├─ Velocity target: 25-30 stories/week
└─ Gate: Portal screens ship, MVP foundation solid

WEEK 4-5:
├─ Phase 2 COMPLETE ✅ (all 166 stories)
├─ Phase 4 MVP READY FOR TESTING ✅ (5 stories)
├─ Phase 3 interview engine 50% complete
├─ Phase 5 portal screens kickoff
├─ Gap Epic P0 stories start
├─ Velocity target: 25-30 stories/week
└─ Gate 1: Phase 2 complete, core messaging/candidate/interview done

WEEK 6-7:
├─ Phase 4 Phase 1B (P1) in progress
├─ Phase 3 advanced AI features 50%+ complete
├─ Phase 5 technical portal 75%+
├─ Gap Epic P0 complete
├─ Velocity target: 25-30 stories/week
└─ Gate: Phase 4 MVP tested & validated for launch

WEEK 8-9:
├─ Phase 4 COMPLETE ✅ (all 39 stories, full resource management)
├─ Phase 3 core features complete
├─ Phase 5 near complete
├─ Gap Epic P1 stories complete
├─ Velocity target: 20-25 stories/week
└─ Gate 2: All critical paths complete for go-live

WEEK 10:
├─ End-to-end testing
├─ Security review
├─ Performance testing
├─ Production deployment checklist
├─ Go-live approval
└─ Gate 3: READY FOR GO-LIVE ✅

ESTIMATED GO-LIVE: Week 10 (2.5 months from now)
```

---

## Without Phase 4 Resources (Current Trajectory)

```
WEEK 1-2: Phase 2 completion (15-20 stories)
WEEK 3-12: Phase 4 slow progress (9+ weeks with 1 developer)
WEEK 13+: Other phases still blocked

ESTIMATED GO-LIVE: 5+ months from now ❌
Risk Level: CRITICAL - Unacceptable timeline
```

---

# SECTION 5: PHASE-BY-PHASE DEVELOPMENT PLAN

## Detailed Phase 2 Completion Plan (2-3 weeks)

### Portal Screens (6 stories, 1-2 weeks)

**HRMS-P105: Portal Home Dashboard** (3 days)
- Backend: GET /portal/dashboard (returns user profile, quick links, recent activity)
- Frontend: Welcome screen, navigation menu, recent messages, upcoming interviews
- Tests: Dashboard loads correctly, navigation works, data populated
- Acceptance: User sees personalized dashboard on login

**HRMS-P106: Portal Message Thread View** (3 days)
- Backend: GET /portal/messages/:threadId (returns conversation thread)
- Frontend: Message list, reply input, send button, timestamp display
- Tests: Load threads, send replies, update UI on new messages
- Acceptance: User can view full conversation thread and reply

**HRMS-P107: Portal Profile Completion Wizard** (3 days)
- Backend: GET/PUT /portal/profile (read/update profile fields)
- Frontend: Multi-step form (personal info, education, skills, references)
- Tests: Form validation, step navigation, data persistence
- Acceptance: User can complete multi-step wizard and submit

**HRMS-P108: Portal Interview Tracker** (2 days)
- Backend: GET /portal/interviews (returns upcoming/past interviews)
- Frontend: Timeline view, interview details, calendar view
- Tests: Display interviews, date filtering, status badges
- Acceptance: User can see all interviews with status

**HRMS-P109: Portal Offer Viewer** (2 days)
- Backend: GET /portal/offers (returns pending/accepted offers)
- Frontend: Offer details, accept/decline buttons, document links
- Tests: Display offers, action buttons functional
- Acceptance: User can view offer and take action

**HRMS-P110: Portal Document Upload** (3 days)
- Backend: POST /portal/documents (upload & scan for viruses)
- Frontend: File picker, upload progress, success confirmation
- Tests: Upload works, virus scan triggers, error handling
- Acceptance: User can upload documents and see confirmation

### LinkedIn Integration (3 stories, 2-3 weeks)

**HRMS-P101: LinkedIn Skeleton Profile** (4 days)
- Authenticate with LinkedIn OAuth
- Extract basic profile (name, headline, skills)
- Create candidate record with LinkedIn data

**HRMS-P102: LinkedIn Sourcing** (4 days)
- Search LinkedIn API for candidates matching demand
- Bulk import profiles into WROS
- Dedup against existing candidates

**HRMS-P103: Cross-Channel Merge** (3 days)
- Detect duplicate candidates (same person, different channels)
- Merge conversation history
- Unify candidate record

### Production Readiness (2 stories, 1 week)

**HRMS-0479: Production Load Testing** (3 days)
- Test AI recruiter at 1000 concurrent candidates
- Test messaging at peak volume (1000 msgs/min)
- Identify performance bottlenecks
- Document results in deployment guide

**HRMS-0480: Go-Live Checklist** (2 days)
- Migration script for production data
- Rollback procedures
- Deployment steps
- Monitoring setup

---

## Detailed Phase 4 MVP Plan (2-3 weeks)

### HRMS-0309: Auto Create Job Requisitions (1 week)

**Backend:**
- Model: JobRequisition (demand_id, budget, status, created_at, assigned_recruiter)
- Service: create_job_requisition(demand_id) → generates job req from demand
- API: POST /jobs/from-demand
- Logic: Demand → extract requirements → auto-create job req

**Frontend:**
- Button: "Create Job Requisition" in demand detail
- Modal: Confirm job creation, review auto-populated fields
- Success: Job req created, show link to edit

**Tests:**
- Create job from demand validation
- Auto-populated fields correct
- Recruiter assignment
- Permission checks (only HR/Admin)

**Acceptance:** User clicks button, job req created with all demand requirements

### HRMS-0310: Demand Forecast Dashboard (1 week)

**Backend:**
- API: GET /dashboards/demand-forecast
- Data: Demand by month, revenue by role, utilization trend
- Charts: Line (forecast), bar (revenue), status (utilization %)

**Frontend:**
- Dashboard: Demand forecast chart, revenue projection, utilization metrics
- Filters: Date range, business unit, role
- Export: CSV/PDF download

**Tests:**
- Dashboard loads correct data
- Charts render properly
- Filters work
- Export functionality

**Acceptance:** User sees accurate demand forecast and can filter/export

### HRMS-0302: Map Revenue to Role Demand (1 week)

**Backend:**
- Service: map_revenue_to_demand(revenue, distribution_by_role) → creates demands
- Logic: Revenue → Split by role type → Create individual demands
- Validation: Total demand <= available bench + hiring capacity

**Frontend:**
- Form: Enter revenue, select role distribution, preview results
- Submit: Creates demands for each role

**Tests:**
- Revenue split calculations correct
- Demands created with correct amounts
- Validation works (capacity checks)

**Acceptance:** User can input revenue and see demand forecast by role

### HRMS-0303: Generate Demand Plan (0.5 weeks)

**Backend:**
- Service: generate_demand_plan(revenue) → returns complete plan
- Plan includes: Demands by month, hiring schedule, resource needs
- Export: JSON or document format

**Frontend:**
- View: Demand plan display with monthly breakdown
- Export: Generate PDF/Word document

**Tests:**
- Plan generation logic
- Export formatting

**Acceptance:** User can generate demand plan from revenue target

### HRMS-0304: Forecast 30/60/90 Day Demand (1 week)

**Backend:**
- Service: forecast_demand(days: 30|60|90) → returns forecast data
- Calculation: Based on historical pipeline velocity + current opportunities
- Accuracy: Compare actual vs forecast for calibration

**Frontend:**
- Dashboard: 30/60/90 forecast charts
- Metrics: Expected placements, confidence %, risk areas
- Drill-down: See opportunities contributing to forecast

**Tests:**
- Forecast calculations
- Historical data comparison
- Confidence intervals

**Acceptance:** User sees 30/60/90 forecast with confidence levels

---

## Phase 4 MVP Success Criteria

**All 5 stories must ship together as one unit:**

- ✅ Demand created from revenue target
- ✅ Job requisitions auto-created from demands
- ✅ Dashboard shows demand forecast for next 30/60/90 days
- ✅ Recruiters can start hiring from job requisitions
- ✅ All data flows end-to-end (no manual steps)

**Go-Live Gate:** Phase 4 MVP must pass this gate before proceeding to Phase 4 Phase 1B

---

# SECTION 6: OPEN DEFECTS STATUS & FIXES

## 12 Open Defects (From DEFECTS_COMPLETION_STATUS_2026_08_12.md)

### TIER 1: CRITICAL BLOCKERS

#### ✅ DEFECT-1: Work Order / PO Model - COMPLETE
- Status: Fully implemented & committed (2026-08-12)
- Service: work_order_service.py (360 LOC, 9 methods)
- API: 11 routes (POST, GET, PUT, DELETE, state transitions)
- Database: work_orders table (created)
- Tests: Full validation suite
- **Action:** Run migration before deploying

#### 🔄 DEFECT-2: Consolidate Employees + Resource Management Screens
- Status: Analysis complete, implementation pending
- Consolidate: 3 separate screens into 1 unified "Employees" screen
- Required design: Tab structure (List/Allocations/Benchmarks)
- Effort: 2-3 weeks frontend work
- **Action:** Design mockups first, then implement

### TIER 2: HIGH PRIORITY

#### DEFECT-3: BU Head Dashboard - Permissions & Data Isolation
- Status: Partial implementation
- Issue: Dashboard shows wrong data when multiple BUs assigned
- Fix: Filter by selected BU, fix role-based visibility
- Effort: 3-4 days
- **Action:** Prioritize for quality fix

#### DEFECT-4: Client Owner Reassignment Workflow
- Status: Awaiting requirements clarification
- Issue: Can't reassign client owner under certain conditions
- Fix: Define workflow (approval workflow? immediate?)
- Effort: 1-2 weeks
- **Action:** Get requirements from Avinash

#### DEFECT-5: Edit User Modal - Role Persistence
- Status: Partial fix applied
- Issue: Selected role not persisting when saving
- Fix: Verify form submission logic, add tests
- Effort: 2-3 days
- **Action:** Add validation + tests

### TIER 3: MEDIUM PRIORITY

#### DEFECT-6: Job Title Dropdown - Missing Validation
- Status: In progress
- Issue: Can select job title that doesn't exist for BU
- Fix: Add BU-specific job title filtering
- Effort: 2-3 days
- **Action:** Add backend validation

#### DEFECT-7: Business Unit Assignment - Bulk Import
- Status: Partial
- Issue: Bulk import doesn't assign BUs correctly
- Fix: Add BU column to import, validate before insert
- Effort: 3-4 days
- **Action:** Update import logic

#### DEFECT-8: Permission Inheritance - Cascade Updates
- Status: Needs implementation
- Issue: When role permissions change, dependent objects not updated
- Fix: Implement cascade update logic
- Effort: 1 week
- **Action:** Design cascade strategy first

#### DEFECT-9: Audit Log - Data Sensitive Fields
- Status: Blocked (DB grant pending)
- Issue: Audit log records sensitive data (SSN, salary)
- Fix: Mask sensitive fields in audit log
- Effort: 2-3 days (once DB grant approved)
- **Action:** Follow up on DB grant

### TIER 4: NICE-TO-HAVE

#### DEFECT-10: Portal - Mobile Optimization
- Status: Not started
- Issue: Portal looks bad on mobile
- Fix: Add responsive design, test on phones
- Effort: 2-3 weeks
- **Action:** Defer to Phase 2B

#### DEFECT-11: Performance - Interview Pipeline Queries
- Status: Slow queries identified
- Issue: Loading interview history takes 10+ seconds
- Fix: Add indexes, optimize queries
- Effort: 3-4 days
- **Action:** Profile after Phase 2 core complete

#### DEFECT-12: Search - Full-Text Search Not Working
- Status: Not implemented
- Issue: Search only matches exact strings
- Fix: Implement full-text search (PostgreSQL or Elasticsearch)
- Effort: 1-2 weeks
- **Action:** Defer to Gap Epic (Phase 5+)

---

## Defect Prioritization for GO-LIVE

**Must Fix Before Launch:**
1. ✅ DEFECT-1 (already done)
2. 🔄 DEFECT-2 (UI consolidation)
3. DEFECT-3 (BU Dashboard perms)
4. DEFECT-5 (Role persistence)

**Should Fix Before Launch:**
5. DEFECT-6 (Job title validation)
6. DEFECT-7 (BU import)
7. DEFECT-8 (Permission cascade)

**Can Defer (Phase 2B):**
- DEFECT-4, DEFECT-9, DEFECT-10, DEFECT-11, DEFECT-12

---

# SECTION 7: HARD RULES & ENFORCEMENT

## 10 Business Rules (R-01 to R-10) + R-11 (Financial)

**These must be tested against in acceptance criteria.**

### R-01: Candidate Uniqueness
- **Rule:** One candidate per (first+last+email) combination per tenant
- **Enforcement:** Unique index on (tenant_id, first_name, last_name, email)
- **Test:** Try to create duplicate → error (already exists)

### R-02: Work Order Immutability
- **Rule:** PO number and billing rate immutable after creation
- **Enforcement:** Code check in work_order_service.update()
- **Test:** Try to change PO → error (immutable field)

### R-03: Tenant Isolation
- **Rule:** No cross-tenant data visible
- **Enforcement:** Middleware adds WHERE tenant_id = current_tenant to all queries
- **Test:** User A sees only User A's data, not User B's

### R-04: Permission Enforcement
- **Rule:** Users only see/do what their role permits
- **Enforcement:** @require_permission() decorator on all endpoints
- **Test:** Recruiter can't view salary data (hidden field)

### R-05: Core-Pull Resolution
- **Rule:** Core wins over Speciality when both available
- **Enforcement:** HRMS-0514 (S-353) is single source of truth
- **Test:** For same placement, Core candidate always preferred

### R-06: Billing Accuracy
- **Rule:** Invoice = (Rate × Hours) ± adjustments, never manual override
- **Enforcement:** Invoice service does calculation, never accepts manual amount
- **Test:** Try to manually enter amount → error

### R-07: Workflow States
- **Rule:** Candidate only moves through valid state transitions
- **Enforcement:** State machine validates transitions
- **Test:** Try invalid transition → error

### R-08: AI Confirmation Gate
- **Rule:** AI recommendations require human confirmation before executing
- **Enforcement:** Two code paths (recommend vs confirm)
- **Test:** AI proposes action, can't execute until human confirms

### R-09: Bench First Policy
- **Rule:** Always try internal hiring before external sourcing
- **Enforcement:** Job matching engine checks bench first
- **Test:** When demand exists, internal candidate matched first

### R-10: SLA Enforcement
- **Rule:** Candidate response SLAs tracked and alerts triggered
- **Enforcement:** Background job checks candidate age, sends escalation alerts
- **Test:** After X hours no response → escalation alert sent

### R-11: Financial Precision
- **Rule:** All money stored as BIGINT (USD cents), never floating point
- **Enforcement:** xxxxxx_usd_cents naming convention on all fields
- **Test:** Try to enter decimal amount → rounds to nearest cent

---

# SECTION 8: RESOURCE ALLOCATION & VELOCITY

## Recommended Team Structure

```
Phase 4 MVP (CRITICAL)
├─ Lead Backend Developer: 1 FTE
├─ Senior Developer (oversight): 0.5 FTE
└─ QA: 0.5 FTE
└─ Timeline: 2-3 weeks

Phase 2 Completion
├─ Frontend Developer: 1 FTE
├─ Backend Developer: 1 FTE (if LinkedIn heavy)
└─ Timeline: 1-2 weeks

Phase 3 (Parallel)
├─ AI/Backend Developer: 1 FTE
└─ Timeline: 4-6 weeks

Gap Epic (Backfill)
├─ Flexible Developer: 1-2 FTE
└─ Timeline: 8-12 weeks

TOTAL: 4.5-5 FTE core + 1-2 FTE flexible
```

## Velocity Tracking

**Current Team Velocity:** 20-25 stories/week

**With Phase 4 Resources:** 25-30 stories/week (parallel streams)

**Tracking Formula:**
```
Velocity = (Stories Shipped + Tests Passed + Defects Resolved) / Week
Target: 25+ stories/week (weeks 1-9)
Final push: 15-20 stories/week (week 10 - quality focus)
```

## Weekly Metrics to Track

```
PHASE 1: [████████] 100% (Done)
PHASE 2: [░░░░░░░░] → Target 100% by Week 3
PHASE 3: [░░░░░░░░] → Target 50% by Week 6
PHASE 4: [░░░░░░░░] → Target 80%+ by Week 8
PHASE 5: [░░░░░░░░] → Target 25% by Week 8
GAP:     [░░░░░░░░] → Target 30% by Week 8
BUGS:    [0/12 fixed] → Target all Tier 1-2 fixed by Week 8

Test Coverage: ≥85% for backend, ≥75% for frontend
Performance: <500ms API response, <100ms frontend interactions
```

---

# SECTION 9: STORY-BY-STORY ROADMAP

## Sprint 1 (Week 1-2): MVP Foundation

### Phase 4 MVP (START NOW)
- S-275: HRMS-0309 (Auto job requisitions) - 1 dev, full week
- S-276: HRMS-0310 (Demand dashboard) - 1 dev, full week
- S-268: HRMS-0302 (Revenue→Demand) - 1 dev, full week
- S-269: HRMS-0303 (Demand plan) - 1 dev, 3 days
- S-270: HRMS-0304 (30/60/90 forecast) - 1 dev, full week

### Phase 2 Completion (Parallel)
- S-085: HRMS-P105 (Portal home) - 1 dev, 3 days
- S-086: HRMS-P106 (Portal messages) - 1 dev, 3 days
- S-087: HRMS-P107 (Portal profile wizard) - 1 dev, 3 days
- S-088: HRMS-P108 (Portal interviews) - 1 dev, 2 days
- S-089: HRMS-P109 (Portal offers) - 1 dev, 2 days
- S-090: HRMS-P110 (Portal documents) - 1 dev, 3 days

### Defects (Quality Gate)
- DEFECT-3: BU Dashboard permissions - 3-4 days
- DEFECT-5: Role persistence - 2-3 days

**Sprint 1 Velocity Target:** 20-25 stories/week

---

## Sprint 2 (Week 2-3): MVP Validation

### Phase 4 MVP Continued
- Finish any Phase 4 MVP stories
- Begin testing Phase 4 MVP end-to-end

### Phase 2 Completion
- S-081-083: LinkedIn integration (3 stories) - 2-3 weeks
- S-079-080: Load testing (2 stories) - 1 week

### Phase 3 Start (Optional - if capacity)
- S-121: HRMS-P607 (Interview decision) - start design/architecture

**Sprint 2 Velocity Target:** 25-30 stories/week

---

## Sprint 3 (Week 4-5): Phase 2 Complete + Phase 4 MVP Gate

### Phase 2 Final Stories
- Complete any remaining Phase 2 work
- Full end-to-end testing
- Performance validation

### Phase 4 MVP Gate (Must Pass)
- Phase 4 MVP testing complete
- All acceptance criteria verified
- Ready for production deployment

### Phase 3 Start
- S-121-124: Interview decision engine (4 stories) - 3-4 weeks
- S-125-128: Advanced AI features (4 stories) - 3-4 weeks

### Defects
- DEFECT-6, DEFECT-7: Validation issues - 3-4 days each

**Sprint 3 Velocity Target:** 25-30 stories/week

**Gate: Phase 2 Complete ✅ + Phase 4 MVP Ready ✅**

---

## Sprint 4-6 (Week 6-8): Full Execution

### Phase 4 Phase 1B (P1)
- S-272: HRMS-0306 (Bench vs demand) - 1 week
- S-274: HRMS-0308 (Bench first) - 1 week
- S-281: HRMS-0601 (Adhoc demand) - 1 week
- S-280: HRMS-0314 (Planning approval) - 1 week

### Phase 3 Continuation
- Interview engine continued
- Advanced AI features

### Phase 5 Portal Screens
- S-100-103: Technical portal (4 stories) - 2-3 weeks

### Gap Epic P0/P1 (Backfill)
- S-352, S-357, S-374, S-375, etc. - 2-3 stories/week

**Sprint 4-6 Velocity Target:** 25-30 stories/week

---

## Sprint 7-9 (Week 9-10): Go-Live Prep

### Phase 4 Completion
- Finish Phase 4 Phase 1C (P2) features
- All 39 Phase 4 stories complete

### Phase 3 Completion
- All agentic features tested
- Integration validation

### Phase 5 Completion
- All portal screens shipped
- Integration testing

### E2E Testing & Fixes
- End-to-end user journeys
- Performance testing
- Security review
- Bug fixes

### Defect Resolution
- All Tier 1-2 defects fixed
- Performance optimizations

**Sprint 7-9 Velocity Target:** 20-25 stories/week

---

## Sprint 10 (Week 10): Go-Live

### Final Validation
- Smoke tests passing
- Performance benchmarks met
- Security review clear
- Deployment checklist complete

### Deployment
- Production migration script run
- Data validation
- Live deployment
- Monitoring active

**Status: READY FOR GO-LIVE ✅**

---

# SECTION 10: SUCCESS METRICS & GATES

## Weekly Checkpoints

### Week 1 Checkpoint (THIS WEEK)
```
✓ Phase 4 MVP team assigned and active
✓ Phase 2 portal team assigned and active
✓ Sprint boards created with stories
✓ Kickoff meetings held
✓ Metro API credentials requested (or decision made)
✓ Velocity baseline established (20-25 stories/week)
```

### Week 3 Checkpoint
```
✓ Phase 4 MVP 50% complete (foundation solid)
✓ Phase 2 portal 100% complete (all 6 screens shipped)
✓ LinkedIn integration started
✓ Velocity tracking: 25+ stories/week
✓ No critical blockers
```

### Week 5 Checkpoint (Go-Live Gate 1)
```
✓ Phase 2 COMPLETE (all 166 stories done)
✓ Phase 4 MVP COMPLETE and TESTED (5 stories, production ready)
✓ Phase 3 interview engine started (50%+ progress)
✓ Phase 5 kickoff (portal screens 25%+)
✓ All Tier 1 defects fixed
✓ End-to-end testing complete
```

### Week 8 Checkpoint (Go-Live Gate 2)
```
✓ Phase 4 COMPLETE (all 37 stories done)
✓ Phase 3 core features complete (50%+)
✓ Phase 5 technical portal 75%+
✓ Gap Epic P0/P1 complete (25+stories)
✓ All Tier 1-2 defects fixed
✓ Performance testing passed
```

### Week 10 Checkpoint (Go-Live Gate 3)
```
✓ All critical paths complete
✓ E2E testing passed
✓ Security review passed
✓ Performance benchmarks met
✓ Deployment checklist 100% complete
✓ Monitoring & alerting configured
✓ Rollback procedures tested
✓ GO-LIVE APPROVED ✅
```

---

## Key Metrics to Track

```
Code Quality:
├─ Test coverage: ≥85% backend, ≥75% frontend
├─ Defect escape: <5 bugs shipped to production
├─ Build success: 100% CI/CD passing
└─ Code review: All PRs reviewed before merge

Delivery:
├─ Velocity: 25+ stories/week (weeks 1-9)
├─ On-time: 90%+ of sprint goals achieved
├─ Burndown: Smooth slope (no cliff at end)
└─ Defects: All Tier 1-2 fixed, Tier 3+ backlog only

Performance:
├─ API: <500ms response time, p95
├─ Frontend: <100ms interaction latency
├─ Database: <1s query time, p95
└─ Load: ≥1000 concurrent users

Go-Live Readiness:
├─ All critical features: ✅
├─ All acceptance criteria: ✅
├─ Deployment tested: ✅
├─ Rollback procedures: ✅
├─ Monitoring: ✅
└─ Stakeholder approval: ✅
```

---

# APPENDIX: QUICK REFERENCE

## Critical Contacts

- **Phase 4 Resource Decision:** Avinash (TODAY)
- **Meta API Credentials:** Avinash / Ops Team
- **Database Grant:** Infrastructure Team
- **Defect Escalations:** Avinash + Tech Lead

## Key Files

**Backlog:**
- WROS_Canonical_Backlog_S001-401.xlsx (source of truth for story status)

**Phase Docs:**
- 01-SECURITY-FOUNDATION.md
- 02-DATA-MODEL.md
- 03-THUNDER-AGENTIC-LAYER.md
- 04-RESOURCE-MANAGEMENT.md

**Requirements:**
- Requirements/S-*.md (for Phase 2-5)
- Requirements/S-*.docx (for Phase 1, historical)

**Development Standards:**
- CLAUDE.md (project rules)
- WROS_Development_Review_Standard.md (build checklist)

**Implementation Guides:**
- Phase docs (architecture + sequencing)
- API_INTEGRATION_EXAMPLE.md (if exists)
- PRODUCTION_DEPLOYMENT_CHECKLIST.md (if exists)

## Common Commands

```bash
# Start dev server
npm run dev (frontend)
python -m uvicorn app.main:app --reload (backend)

# Run migrations
alembic upgrade head

# Run tests
pytest tests/ (backend)
npm test (frontend)

# Check status
git status
git log --oneline -10
npm run lint (frontend)
black --check . (backend)
```

---

# SIGN-OFF

**Document Status:** ✅ COMPLETE & READY TO EXECUTE

**Prepared By:** Claude Code Audit (2026-08-14)

**Coverage:** 433 stories + 12 defects + All constraints

**Confidence Level:** HIGH (based on model evidence + backlog + project docs)

**Last Updated:** 2026-08-14

**Next Update:** Weekly (after sprint completion)

---

**THIS IS YOUR DEVELOPMENT BIBLE**

**Read it. Live it. Execute it.**

**Questions? See SECTION 1-10 for answers.**

**Ready? Turn to SECTION 4 (Timeline) and SECTION 5 (Phase Plans).**

**Let's ship WROS.** 🚀
