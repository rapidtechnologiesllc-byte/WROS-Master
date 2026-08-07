# WROS Frontend - Development Notes

## Current Session Summary (2026-08-07 Continued)

### ✅ COMPLETED THIS SESSION

**1. ALL MODAL CLOSING BUGS FIXED (5 modals)**
- Schedule Interview Modal (src/screens/CandidateDetailsScreen.js:826)
- Reschedule Interview Modal (src/screens/tabs/InterviewsTab.js:556)
- Cancel Interview Modal (src/screens/tabs/InterviewsTab.js:596)
- Submit Feedback Modal (src/screens/tabs/InterviewsTab.js:372)
- Skip Feedback Modal (src/screens/tabs/InterviewsTab.js:415)

**Root Cause:** Modal close functions had guard `if (loading/submitting) return;` but state wasn't set to false before calling close. Fixed by reordering: `setLoading(false)` → `closeModal()`.

**2. PANEL MEMBER DISPLAY ENHANCEMENT**
- InterviewsTab.js: Panel members now display role + business unit name
- Removed placeholder "(local dev)" text
- Shows actual employee metadata from backend
- Commits: `1a8eced`, `b0cdd78`

**3. ADMIN PASSWORD RESET UI**
- HrUserManagement.js: New "Admin: Reset User Password" form
- Does NOT require current password (admin doesn't have it)
- Dropdown to select user
- Calls new backend endpoint: `PUT /admin/users/{user_id}/reset-password`
- Commit: `e825099`

---

## Architecture & Patterns

### Modal Closing Pattern (CORRECT)
When a modal performs async work:
1. Set loading state at START
2. Do async work
3. Show success/error message
4. **SET LOADING FALSE BEFORE CLOSE** (not in finally!)
5. Call close function

❌ WRONG:
```javascript
try {
  setLoading(true);
  await work();
  setTimeout(() => closeModal(), 1000); // still loading=true!
} finally {
  setLoading(false); // too late!
}
```

✅ CORRECT:
```javascript
try {
  setLoading(true);
  await work();
  setLoading(false);
  closeModal(); // now loading=false, close works!
} catch (err) {
  setLoading(false);
}
```

### Panel Member Display Pattern
```javascript
const roleAndBU = [member?.interviewer_role, member?.business_unit_name]
  .filter(Boolean)
  .join(" • ") || "";
return <span>{name} {roleAndBU && <div>{roleAndBU}</div>}</span>;
```

---

## Current Project State

### EPIC-02 Phase 1: ~80% Complete
- Interview scheduling: ✅ All modals fixed
- Panel management: ✅ Display enhanced with role/BU
- Feedback submission: ✅ All modals fixed
- Status: Ready for Phase 2

### Recommended Next Focus
1. **EPIC-02 Phase 1** - Finish 3 remaining stories (this week)
2. **EPIC-01** - Employee conversion pipeline (next week)
3. **EPIC-05** - Timesheet system (week 3)

---

## Known Issues & Workarounds

### Port Management
- **CRITICAL:** Kill stray port 8080 processes at session start
- 8080 is MAIN backend port (not remote dummy)
- Use task manager or `netstat -ano | findstr :8080`

### Login Credentials (Testing)
Current test users for local development:
- superuser@blitzenx.com / Superuser!123 (or use auto-assigned bcrypt hash)
- admin@blitzenx.com / Admin@123
- test@blitzenx.com / Test@123

Database path: OnboardingModule-Backend/local_dev.sqlite3 (resolved to absolute path by backend)

---

## Code Standards (Established 2026-07-23)

- CardBlock pattern for multi-section editable UI (see JobDetails.js, CandidateDetailsScreen.js)
- Modal state management: close guard only prevents races, doesn't prevent close
- All state updates before calling close functions
- No hardcoded values in production-ready stories
- React hooks: useCallback for memoized callbacks, useMemo for derived state

---

## Recent Commits (This Session)

```
e825099 Add admin password reset UI - no current password required
b0cdd78 Fix submit and skip feedback modal closing issues
1a8eced Fix all interview modal closing issues and enhance panel member display
```

---

## Session Discipline

- Complete ONE task thoroughly before next
- NO summary generation without explicit request (saves tokens)
- Code pushed to main after each logical milestone
- Test golden path + edge cases in browser before commit
- No token-wasting auto-summaries
