# NEW SESSION PROMPT FOR WROS PROJECT

Copy this into a new Claude Code session to continue work on WROS.

---

## PROJECT CONTEXT

**Project:** WROS (Workforce Revenue Operating System) for BlitzenX  
**Client:** BlitzenX (Guidewire specialist staffing firm)  
**Goal:** Automate candidate-to-employee-to-billable lifecycle with task-driven workflows  
**Total Scope:** 433 stories + 15 finance stories + 12 open defects  
**Current Status:** Phase 1 Done (Security), Phase 2 In Progress (Data Model/Thunder)  

---

## CRITICAL: NEW PHASE SEQUENCE (As of 2026-08-14)

⚠️ **PHASE SEQUENCE CHANGED - Notifications moved to Phase 3, Agentic to Phase 6**

**Correct Sequence:**
```
Phase 1: Security ✅ DONE (6 stories)
Phase 2: Data Model & Thunder (2-3 weeks remaining)
Phase 3: NOTIFICATIONS & TASK WORKFLOWS 🟢 4-5 weeks ← START HERE NEXT
Phase 4: Resource Management (3-4 weeks)
Phase 5: Job Titles & Portals (4-6 weeks)
Phase 6: Agentic Layer (4-6 weeks) ← MOVED TO END
Gap Epic: Strategic Features (8-12 weeks, parallel)

GO-LIVE: ~4.5 months from now
```

**Why Notifications First?**
- Notifications is the BACKBONE (every workflow depends on it)
- Email is THE notification channel (not UI, not Slack)
- Tasks represent DECISION POINTS (where humans must judge)
- Agents later create tasks + send emails (built on Phase 3)

---

## CORE PRINCIPLE: TASKS = HUMAN DECISIONS ONLY

**NOT all events create tasks. Only decision points do.**

### System Does Automatically (No Task Needed)
- Parse resume / extract skills / score completeness
- Run validation / check duplicates
- Send auto-response emails (one-way)
- Trigger background checks / visa checks
- Generate recommendations / AI qualification assessments
- Create work orders / generate offers / set up invoicing

### Human Decides (Create Task)
- **Initial Screening**: Recruiter decides "worth pursuing?"
- **Review Qualification**: Recruiter decides "interview this candidate?"
- **Provide Feedback**: Interviewer decides "hire or no-hire?"
- **Approve Offer**: Manager decides "budget OK? Rate fair?"
- **Review & Decide**: Recruiter decides "what's next?"
- **Confirm Assignment**: Employee decides "ready to start?"

**Task Types: ~20 core decision points** (not 50+)

Each task represents a human decision bottleneck.

---

## KEY DOCUMENTS TO READ

1. **WROS_REVISED_MASTER_ROADMAP_2026_08_14_FINAL.md**  
   → Your bible (phases, timeline, gates, checkpoints)

2. **PHASE_3_NOTIFICATIONS_AND_TASKS_DETAILED_PLAN.md**  
   → Detailed Phase 3 implementation (15 stories, 4-5 weeks)

3. **AUTONOMOUS_VS_HUMAN_DECISIONS_FRAMEWORK.md**  
   → Framework for what system auto-does vs. what needs human tasks

4. **WROS_MASTER_DEVELOPMENT_ROADMAP_2026_08_14.md**  
   → Comprehensive master roadmap (all phases, all rules)

5. **CLAUDE.md**  
   → Project rules, non-negotiables, Definition of Done

---

## NON-NEGOTIABLES (From CLAUDE.md)

**These are hard-enforced. No exceptions.**

1. **`createCandidateSafe()` is the ONLY path** to create a candidate (no direct inserts)
2. **`sendThunderMessage()` is the ONLY path** to send candidate messages (no raw API calls)
3. **`sendNotification()` (HRMS-0113) is the ONLY path** for internal notifications
4. **HRMS-0514 (S-353) is the ONLY place** Core-Pull conflict logic lives (Core wins)
5. **Every table has `tenant_id`**, NOT NULL, indexed (no cross-tenant leakage)
6. **Every monetary value is `BIGINT`, USD cents**, named `*_usd_cents` (no floats)
7. **LLM output is advisory** for irreversible actions (propose → human confirms → execute)

---

## DEFINITION OF DONE (Enforced)

**A story is NOT DONE until ALL four layers are complete:**

1. **Backend** ✅ (models + services + migrations + tests)
2. **API/Integration** ✅ (REST endpoints + auth + error responses)
3. **Frontend** ✅ (UI screens + forms + state management)
4. **Tests** ✅ (unit + integration + E2E)

**Backend-only = IN PROGRESS (never Done)**

---

## CURRENT STATUS

### Phase 1: Security ✅ DONE
- RBAC system with 8 roles, 17 permissions
- Field-level PII masking
- Business Unit system + Job Title-based assignment
- 112 backend models implemented
- Production-ready

### Phase 2: Data Model/Thunder 🟡 IN PROGRESS
- 79 stories done (47.6%)
- Completed: Messaging, candidate intelligence, resume parsing, interviews
- Remaining: Portal screens (6), LinkedIn integration (3), load testing (2)
- Timeline: 2-3 weeks to completion

### Phase 3: Notifications & Tasks 🟢 NOT STARTED (NEXT)
- 15 stories to build
- Task system + email infrastructure
- 20 core decision-point tasks
- Timeline: 4-5 weeks
- **Start after Phase 2 completion**

### Open Defects: 12 Total
- DEFECT-1: ✅ Work Order Model (COMPLETE)
- DEFECT-2 through DEFECT-12: Various (most defer to Phase 2B)

---

## ARCHITECTURE: TASK-DRIVEN WORKFLOWS

**Every workflow follows this pattern:**

```
EVENT (Candidate Created)
    ↓
SYSTEM AUTOMATION (Parse, score, validate, auto-communications)
    ↓
DECISION POINT (Recruiter must decide: worth pursuing?)
    ↓
TASK CREATED + EMAIL SENT (Rich HTML with action button)
    ↓
HUMAN ACTS (Recruiter reviews, clicks link, makes decision)
    ↓
TASK COMPLETED (Status updated, confirmation sent)
    ↓
NEXT AUTOMATION (Based on decision, system continues workflow)
```

---

## PHASE 3 SCOPE (Next Major Work)

### Phase 3A: Task System (2 weeks)
- Task model & database schema
- TaskService (create/read/update/complete)
- API endpoints (GET/POST/PUT)
- Task dashboard UI

### Phase 3B: Email System (2 weeks)
- 30+ HTML email templates (all task types)
- NotificationService (SendGrid/SES integration)
- Async queue (Celery) for reliable delivery
- Reminders & scheduler (24h before due, daily digest)

### Phase 3C: Workflows (1 week)
- Candidate profile completion workflow
- Interview feedback workflow
- Offer approval workflow
- Work order assignment workflow

### Phase 3D: Advanced (1 week)
- Advanced dashboard (filtering, search, bulk actions)
- Daily/weekly digest emails
- Task collaboration (comments, reassignment)

**Total: 15 stories, 4-5 weeks, 5-6 developers**

---

## PHASE 4: RESOURCE MANAGEMENT (After Phase 3)

### Phase 4 MVP (5 stories, 2-3 weeks) - CRITICAL PATH
- HRMS-0309: Auto Create Job Requisitions
- HRMS-0310: Demand Forecast Dashboard
- HRMS-0302: Map Revenue to Role Demand
- HRMS-0303: Generate Demand Plan
- HRMS-0304: Forecast 30/60/90 Days

**GO-LIVE BLOCKER:** These 5 stories are sequential gates. Don't parallelize.

### Full Phase 4 (37 stories, 3-4 weeks total)
- Phase 4 MVP (2-3 weeks)
- Phase 4 P1 (bench matching, bench first policy)
- Phase 4 P2 (advanced forecasting, scenario planning)

---

## WEEKLY SPRINT SEQUENCE (Corrected)

```
Week 1-2:   Phase 2 Completion (Portal + LinkedIn)
            Phase 3 MVP Kickoff (Task Model + Service)

Week 3-4:   Phase 3 Email System (Templates + Notifications)
            Phase 3 Automation (Integrate into workflows)

Week 5:     Phase 3 COMPLETE ✅ (Gate: Must pass before Phase 4)

Week 6-8:   Phase 4 MVP (Resource Management)
            Phase 5 Start (Portal screens)

Week 9-12:  Phase 4 Complete
            Phase 5 Complete
            Phase 6 Agentic Kickoff

Week 13-16: Phase 6 Agentic Layer
            Gap Epic Features

Week 17-19: Go-live Prep + Launch 🚀

TOTAL: ~4.5 months to go-live
```

---

## CRITICAL DECISIONS MADE (2026-08-14)

1. ✅ **Notifications = Phase 3** (moved from Phase 6 agentic)
2. ✅ **Tasks = Decision Points Only** (not all events)
3. ✅ **Agentic = Phase 6** (after task foundation solid)
4. ✅ **Email = THE Channel** (not UI, not Slack)
5. ✅ **~20 Core Tasks** (not 50+ task types)

**These are LOCKED. Don't revisit without explicit decision.**

---

## IMMEDIATE NEXT STEPS (TODAY)

1. **Read Phase 3 Plan** → PHASE_3_NOTIFICATIONS_AND_TASKS_DETAILED_PLAN.md
2. **Understand Decision Framework** → AUTONOMOUS_VS_HUMAN_DECISIONS_FRAMEWORK.md
3. **Allocate Developers** → 5-6 developers to Phase 3
4. **Create Phase 3 Sprint Board** → 15 stories
5. **Kickoff S-1 Today** → Task Model & Database

---

## CONSTRAINTS & RULES

- **No deviation from non-negotiables** (R-01 to R-11)
- **Every story must meet Definition of Done** (all 4 layers)
- **Phase sequence is locked** (notifications first, agentic last)
- **Task = decision point only** (not workflow automation)
- **Email is mandatory** (all tasks trigger emails)
- **Tenant isolation is non-negotiable** (every table has tenant_id)
- **Financial values are BIGINT cents** (no floating point, ever)

---

## RESOURCES

**Canonical Backlog:** `WROS_Canonical_Backlog_S001-401.xlsx`

**Requirements:** 
- S-001 to S-048: `Requirements/S-*.docx` (legacy)
- S-049+: `Requirements/S-*.md` (current format)

**Backend:** `OnboardingModule-Backend/` (112 models implemented)
**Frontend:** `OnboardingModule-Frontend-main/` (React/TypeScript)

**Documentation:**
- Phase docs: `01-SECURITY-FOUNDATION.md` through `04-RESOURCE-MANAGEMENT.md`
- Development standard: `WROS_Development_Review_Standard.md`
- Project rules: `CLAUDE.md`

---

## QUICK REFERENCE: TASK TYPES (~20 Core)

| # | Task | Owner | Decision |
|---|------|-------|----------|
| 1 | Initial Screening | Recruiter | Worth pursuing? |
| 2 | Review Qualification | Recruiter | Interview this candidate? |
| 3 | Prepare for Interview | Interviewer | Read resume, prep questions |
| 4 | Confirm Interview | Candidate | Still available? |
| 5 | Provide Feedback | Interviewer | Hire or no? Why? |
| 6 | Review Feedback & Decide | Recruiter | Next step? |
| 7 | Approve Offer | Manager | Budget OK? Rate fair? |
| 8 | Respond to Offer | Candidate | Accept/decline/negotiate? |
| 9 | Confirm Assignment | Employee | Ready to start? |
| 10 | Prepare Kickoff | Manager | Arrange team meeting |
| 11 | Approve Demand | Manager | Hiring needed? |
| 12 | Match to Demand | Recruiter | Which open role? |
| 13 | Approve Timesheet | Manager | Hours correct? |
| 14 | Approve Invoice | Finance | Send to client? |
| 15 | Review Escalation | Manager | Needs manual review |
| 16 | Manager Approval | Manager | Generic approval gate |
| 17 | HR Approval | HR | HR sign-off needed |
| 18 | Budget Approval | Finance | Budget available? |
| 19 | Performance Review | Manager | Annual review needed |
| 20 | Handle Exception | User | Edge case resolution |

---

## GET STARTED

1. Open `WROS_REVISED_MASTER_ROADMAP_2026_08_14_FINAL.md`
2. Review Phase 3 in detail
3. Read the decision framework
4. Create Phase 3 sprint board
5. Start building Task system (S-1: Task Model)

**Questions?** Check CLAUDE.md or the master roadmap.

**Ready?** Start Phase 3. Let's ship WROS. 🚀
