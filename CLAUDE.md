# WROS Backend - Development Notes

## Current Session Summary (2026-08-07 Continued)

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

**3. AUTOMATIC AI RECRUITER ASSIGNMENT**
- Created `candidate_ai_auto_assignment_service.py`
- Every candidate auto-assigned Thunder upon intake
- Removed manual "Assign AI Recruiter" button concept
- Commit: `1e386c7`

**4. ADMIN PASSWORD RESET FIX**
- New endpoint: `PUT /admin/users/{user_id}/reset-password`
- Does NOT require current password (admin doesn't have it!)
- Fixes logical flaw where admins were asked for unknown password
- UI added to HrUserManagement screen
- Commits: Backend `ef0674c`, Frontend `e825099`

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
