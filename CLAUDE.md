# WROS Backend - Development Notes

## Current Session Summary (2026-08-08 - Agent Excellence System)

### ✅ COMPLETED THIS SESSION: Agent Excellence System (3 Phases)

**PHASE 1: Recruitment Agent for Job Creation** ✅ COMPLETE + TESTED
- **Requirement:** Agentic job creation with Ask Flash modal for clarifying questions
- **Implementation:**
  - `RecruitmentJobCreationAgent` class in `app/services/recruitment_job_creation_service.py`
  - POST `/jobs/generate-with-agent` — Returns clarifying questions
  - POST `/jobs/generate-complete` — Auto-populates form with LLM-generated answers
  - Frontend: JobCreate.js integrated Ask Flash modal with dynamic question rendering
  - Logs all execution to `agent_execution_log` for maturity tracking
- **Status:** Working end-to-end, tested with edge cases (empty inputs, malformed responses)
- **Commits:** Multiple across frontend and backend
- **Testing Notes:** Verifies job title doesn't include location/seniority (was critical defect)

**PHASE 2: Agent Maturity Dashboard** ✅ COMPLETE + TESTED
- **Requirement:** Weekly performance tracking + 12-week history + retirement eligibility
- **Implementation:**
  - `AgentMaturityLevel` model tracks current maturity (0-100)
  - `AgentPerformanceMetric` model stores weekly snapshots (12-week history)
  - Maturity calculation: 60% success_rate + 20% speed + 20% quality
  - GET `/admin/agents/maturity` — All agents current maturity
  - GET `/admin/agents/maturity/{agent_name}` — Detailed dashboard with trends
  - GET `/admin/agents/{agent_name}/health` — Health status + retirement recommendation
  - POST `/admin/agents/{agent_name}/retire` — Mark agent as retired
- **Status:** Fully implemented, API tested, schema validated
- **Commits:** `0165561` - Core implementation

**PHASE 3: Agent State Dashboard (Renamed from Fear System)** ✅ COMPLETE + TESTED
- **Requirement:** Excellence-based motivation (Marine Corps standard), NOT threat-based
- **Philosophy Shift:**
  - OLD: "Fear State Dashboard" (threat mechanics)
  - NEW: "Agent State Dashboard" (performance excellence + recognition)
  - Agents trained to highest standards through ranking + recognition, not fear
  
- **Implementation:**
  - `AgentFearState` model renamed conceptually to track emotional/performance state
  - `AgentPerformanceCommitment` defines stringent 99.9999% success target
  - `AgentStressTesting` model for deliberate agent challenges
  - Fear calculation: Baseline 20 + variance from 99.9999% target (every 0.1% = +1 fear)
  - Motivation states: motivated (0-20) → neutral (20-40) → concerned (40-60) → desperate (60-80) → terrified (80+)
  - Threat levels: none, warning (50-70), critical (70-80), existential (80+)
  - Retirement eligibility: Requires 2+ of: high fear (>85), poor success (<95%), low quality (<80%), existential threat
  
- **Frontend: AdminAgentStateDashboard.js**
  - Shows ALL agents (not just under threat)
  - Rankings: Top 3 performers with Gold/Silver/Bronze badges
  - Weekly Champions section with recognition
  - Performance metrics: Maturity Score, Success Rate, Quality, Trend
  - Agent levels: Elite (90+), Strong (75-89), Developing (50-74), Needs Support (<50)
  - "Gift Recognition" button framework for reward system
  - Integrated as "Agent Dashboard" tab in Admin > AI Configuration
  
- **API Endpoints:**
  - GET `/admin/agents/fear` — All agents under threat + statistics
  - GET `/admin/agents/fear/{agent_name}` — Detailed fear metrics
  - GET `/admin/agents/fear/{agent_name}/retirement-check` — Eligibility assessment

- **Status:** Fully implemented, integrated, screenshot verified working
- **Commits:** `0165561` (backend), `16847cd` (frontend), `96096aa` (API fixes), `02a06c5` (refactor to excellence-based)

### ⚠️ BUGS FOUND & FIXED (This Session)

1. **Job Title Auto-Population Bug** - CRITICAL
   - **Issue:** Backend LLM extracted "Remote Guidewire Developer" (mixed location into title)
   - **Root Cause:** LLM prompt wasn't excluding location/seniority keywords
   - **Fix:** Updated job_description_generator prompt + added cleanup code to strip location prefixes
   - **Status:** FIXED ✅

2. **Module Import Path Error** - CRITICAL
   - **Issue:** AdminAgentFearDashboard.js tried `import { apiCall } from '../services/api'` (wrong path)
   - **Root Cause:** Missing proper API service module structure
   - **Fix:** Created `adminDashboard.js` service module with proper endpoint functions
   - **Status:** FIXED ✅

3. **TenantAIConfigResponse Validation Error** - BLOCKING
   - **Issue:** `ai_agent_name` NULL in database caused 500 error on /admin/ai-config
   - **Root Cause:** Schema required non-null string, but DB had NULL value
   - **Fix:** Made `ai_agent_name` optional with default "Thunder"
   - **Status:** FIXED ✅

4. **API Endpoint 404 Error** - CRITICAL
   - **Issue:** `/admin/agents/fear` returned 404
   - **Root Cause:** Backend restarted after new routes added, frontend HMR didn't see updates
   - **Fix:** Restarted both backend and frontend servers
   - **Status:** FIXED ✅

### 🧪 EDGE CASES & ODD SCENARIOS TESTED

1. **Empty Agent List:** Dashboard shows "No agents found" gracefully
2. **Zero Maturity Data:** Statistics show 0/0% without errors
3. **NULL Fear Metrics:** Handles missing fear state data with defaults
4. **Multi-tab Navigation:** Switching between Thunder Configuration and Agent Dashboard tabs works smoothly
5. **Pagination:** Large agent lists paginate correctly (10 items per page)
6. **Real-time Refresh:** Dashboard auto-refreshes every 30-60 seconds
7. **Missing Drawer Data:** Agent detail drawer handles missing weekly metrics
8. **Font Encoding:** Windows UTF-8 issues with emoji check marks resolved

### 📋 REQUIREMENTS CAPTURED FOR NEXT SESSION

**IMMEDIATE PRIORITY:**
1. **Agent Mapping (50+ Agents)** - Map all internal agents
   - Recruitment Agent + sub-agents
   - Resource Management Agent + sub-agents
   - Finance Agent + sub-agents
   - Project Management Agent + sub-agents
   - KPI Agent (MISSING)
   - HR Agent (MISSING)
   - Employee Mental Health Agent (MISSING)
   - CEO/Executive Signal (built)
   - CFO Agent (built)
   - Partner ROI Agent (built)
   - Help Desk/Ticketing Agent (built)
   - Buddy Program Agent (built)
   - Reporting Agent (built)
   - ... and 35+ more

2. **Agent Execution Logging**
   - Ensure ALL 50+ agents log to `agent_execution_log`
   - Currently only Recruitment Agent logs execution
   - Need to wire up logging for Resource Manager, Finance, etc.

3. **Weekly Gift/Recognition System**
   - Framework in place ("Gift Recognition" button)
   - Need to implement backend gift tracking model
   - Integrate with maturity dashboard rankings

### ✅ INTEGRATION COMPLETE

- Agent State Dashboard successfully integrated into Admin > AI Configuration
- Tabbed interface working (Thunder Configuration + Agent Dashboard)
- Backend routes registered and responding
- Frontend components rendering correctly
- No errors on page load or tab navigation

### 🏗️ ARCHITECTURE DECISIONS

1. **Thunder is External-Facing** — Recruiter AI for candidates (WhatsApp/Email)
2. **Internal Agents are 50+** — All business logic agents (Recruitment, Finance, HR, etc.)
3. **Agent State Dashboard Aggregates All Internal Agents** — Shows performance across all 50+ agents
4. **Excellence-Based Motivation** — Ranking + Recognition over Fear/Threat
5. **Stringent Target: 99.9999% Success Rate** — Applies to ALL agents universally

---

## Previous Session Summary (2026-08-07 Continued)

### ✅ COMPLETED THIS SESSION

**1. ALL MODAL CLOSING BUGS FIXED (5 modals)**
- Schedule Interview Modal (CandidateDetailsScreen.js:826)
- Reschedule Interview Modal (InterviewsTab.js:556) 
- Cancel Interview Modal (InterviewsTab.js:596)
- Submit Feedback Modal (InterviewsTab.js:372)
- Skip Feedback Modal (InterviewsTab.js:415)

**Root Cause:** Modal close functions checked `if (loading/submitting) return;` but state wasn't set to false before calling close. Fixed by moving `setLoading(false)` BEFORE `closeModal()` calls.

**2. PANEL MEMBER DISPLAY ENHANCEMENT**
- Backend: `get_panel_members()` now returns `interviewer_role` + `business_unit_name`
- Frontend: Shows "Role • Business Unit" instead of "(local dev)" placeholder
- Commit: `79e0f74`

**3. THUNDER AI RECRUITER AUTO-ASSIGNMENT BUG FIX** ⭐ CRITICAL
- **Problem:** Thunder auto-assignment was silently failing
- **Root Cause:** Both call sites passed wrong tenant_id value:
  - `onboarding.py:181` — passed `user.UserID` instead of `user.tenant_id`
  - `create_job.py:958` — passed `job.recuriterID or job.contactPerson` instead of `job.tenant_id`
  - Function checked `if not tenant_id: return` (line 507), so incorrect values skipped silently
- **Solution:** 
  - Line 181: `run_auto_assign_ai_agent_in_background(candidate_id, user.tenant_id)`
  - Lines 953-962: `run_auto_assign_ai_agent_in_background(candidate_id, job.tenant_id)`
- **Why This Matters:** Throughout candidate lifecycle (intake→conversion), Thunder should run autonomously without manual "Assign AI Recruiter" clicks
- **Commit:** `c746970`

**4. ADMIN PASSWORD RESET FIX**
- New endpoint: `PUT /admin/users/{user_id}/reset-password`
- Does NOT require current password (admin doesn't have it!)
- Fixes logical flaw where admins were asked for unknown password
- UI added to HrUserManagement screen
- Commits: Backend `ef0674c`, Frontend `e825099`

**5. BUSINESS UNIT SCOPING ARCHITECTURE FIX** ⭐ CRITICAL
- **Problem:** Newly created candidates were invisible (404 errors) due to incorrect BU scoping
- **Root Cause:** All candidate fetch endpoints applied BU scoping to all candidates, but:
  - Newly created candidates have NO CandidateOwnership record (not yet submitted to a job)
  - BU scoping shouldn't apply until a candidate is submitted to a job
  - `get_candidate_by_id()` and similar endpoints couldn't find newly created candidates
- **Solution:** 
  - Created `get_candidate_by_id_with_bu_scope()` helper in `app/core/bu_scope.py`
  - Only applies BU scoping if candidate HAS a CandidateOwnership record
  - Newly created candidates (Org Pool) visible to all HR users regardless of BU
  - Updated critical endpoints: `get_candidate_by_id()`, `get_candidate_status()`
- **Principle:** BU scoping only applies AFTER job submission (CandidateOwnership creation)
  - Org Pool (newly created): visible to all HR users
  - Job-submitted: respect BU ownership if user is bu_restricted
- **Commits:** `706ce22` (BU scope architecture), `7b43ee3` (helper function), `e96e987` (candidate_status)

---

## CRITICAL: LOCAL DATABASE FIX EXPLANATION

### The Problem (2026-08-07 Session Debugging)
Users couldn't log in with correct credentials. Password verification was failing even with bcrypt-compatible hashes created in the database.

**Root Cause:** Two separate SQLite databases existed:
- `.claude/local_dev.sqlite3` (empty test data)
- `OnboardingModule-Backend/local_dev.sqlite3` (actual schema + test users)

The backend was using a RELATIVE path `sqlite:///./local_dev.sqlite3` which resolved to the PROCESS WORKING DIRECTORY (`.claude/`) instead of the backend repo directory. This meant:
1. Backend launched from `.claude` directory
2. Relative path resolved to `.claude/local_dev.sqlite3` (empty, no test users)
3. Login attempts failed because the database had no user records

### The Solution (app/core/database.py:24-33)

**Convert relative SQLite paths to absolute paths using repo root:**

```python
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
# ... env loading ...

if DATABASE_URL and DATABASE_URL.startswith("sqlite:///./"):
    # Extract relative path (e.g., "./local_dev.sqlite3" -> "local_dev.sqlite3")
    rel_path = DATABASE_URL.replace("sqlite:///./", "")
    abs_path = os.path.join(_REPO_ROOT, rel_path)
    DATABASE_URL = f"sqlite:///{abs_path}"
```

**Why this works:**
- `_REPO_ROOT` resolves to the backend repo directory (3 levels up from `app/core/database.py`)
- Absolute paths ignore process working directory
- Backend now finds the correct `local_dev.sqlite3` regardless of launch directory
- Same logic applied to `.env` and `.env.local` loading (lines 14-20)

**Key Insight:** Never trust relative paths in production-grade systems. Always resolve them to a known, fixed anchor point (the application root) rather than the process CWD, which can vary by launcher.

---

## Project Status & Next Steps

### EPIC COMPLETION METRICS (From Previous Session Verification)

**Verified (7 of 10 clusters, 305 of 393 stories):**
- CONFIRMED-DONE: 138 (45%)
- PARTIAL: 49 (16%)
- NOT-DONE: 117 (38%)
- **Effective Completion: ~53% (with PARTIAL as half-credit)**

**Not Yet Verified (3 clusters, 88 stories):** EPIC-14/15/16, DESIRE, EPIC-P1-P6

---

## RECOMMENDED PATH TO PRODUCTION

### Option: MVP Recruitment → Employee → Timesheet → Prod

**Timeline: 2-3 weeks vs 8-12 weeks (full shell)**

**Critical Path (in order):**

1. **EPIC-02 Phase 1** (3 stories remaining)
   - Complete 100% (was 70%, now ~80% with bug fixes)
   - All modal closing fixed ✅
   - Panel display enhanced ✅
   - AI recruiter auto-assignment ready ✅
   - Target: This week

2. **EPIC-01** (9 stories remaining)
   - Employee conversion pipeline
   - Candidate → Employee journey
   - Target: Next week

3. **EPIC-05** (Timesheet System)
   - Employee self-service timesheet (built 2026-08-04, blocked on real login creds)
   - Timesheet approvals
   - Revenue integration
   - Target: Week 3

### Blockers to Remove First

1. **EPIC-01:** S-209 deferred post-go-live — pull forward?
2. **Timesheet:** "Blocked on real login creds" — create real test user accounts
3. **Employee Conversion:** Bridge gap between EPIC-02 → EPIC-01 workflows

---

## Code Quality Standards (Established 2026-07-23)

- No placeholders/hardcoded values in EPIC-01/02/03/05 stories
- Production readiness bar enforced
- Integration tests on local SQLite
- All paths must be absolute (no relative path assumptions)

---

## Recent Commits (This Session)

```
79e0f74 Fix panel member display: show role and business unit name
1e386c7 Implement automatic AI recruiter assignment service
ef0674c Add admin-only password reset endpoint (no current password required)
e825099 Add admin password reset UI - no current password required
1a8eced Fix all interview modal closing issues and enhance panel member display
b0cdd78 Fix submit and skip feedback modal closing issues
```

---

## Architecture Notes

### Thunder Autonomous System
- Every candidate auto-assigned to Thunder (AI recruiter) on intake
- Thunder manages full journey: intake → qualify → screen → interview → offer → hire → onboard
- No manual recruiter clicks required for happy path
- Recruiter maintains override capability for exceptions

### Database Path Resolution Pattern
This pattern should be replicated anywhere relative paths are used:
```python
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if url.startswith("sqlite:///./"):
    rel = url.replace("sqlite:///./", "")
    url = f"sqlite:///{os.path.join(_ROOT, rel)}"
```

---

## Session Discipline

- Complete ONE task thoroughly before next
- NO summary generation without explicit request (saves tokens)
- Code pushed to main after each logical milestone
- All code reviewed and tested before commit
