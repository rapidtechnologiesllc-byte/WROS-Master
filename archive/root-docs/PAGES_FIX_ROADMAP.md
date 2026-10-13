# WROS Application - Complete Pages Fix Roadmap

**Goal:** By morning - all pages working end-to-end (genuine data, no dummy values)  
**Strategy:** Fix one page at a time, test in UI, move to next  
**Scope:** Work LOCAL only - don't break working role template/user systems

---

## PAGE AUDIT SUMMARY

### ✅ CORRECTLY WIRED (Backend + Frontend)
These pages have correct API calls and component wiring. They just need TEST DATA:
- **Candidates** - Backend: `/onboarding/hr/get_all_candidates` ✓ → Frontend: calls it correctly ✓
- **Jobs** - Backend endpoint exists ✓ → Frontend calls it ✓
- **Interviews** - Backend endpoint exists ✓ → Frontend calls it ✓

### ⚠️ NEED DATA POPULATION
- **Candidates page** - Shows 0 candidates (need test data)
- **Jobs page** - Shows 0 jobs (need test data)
- **Interviews page** - 500 error on `/bu-context/my-access` endpoint (CRITICAL BLOCKER)
- **Offer Letters** - Likely endpoint missing (404)
- **Executive Dashboards** - Likely missing endpoints or data

### 🔴 CRITICAL BLOCKERS
1. **`/bu-context/my-access` endpoint returns 500** - Blocks Interviews, Workforce, Sales pages
2. **Empty database** - No test data to display
3. **Dummy/hardcoded values** - Some fields show placeholder text (e.g., Job Title: "Job Title")

---

## FIX ROADMAP (Priority Order)

### PHASE 1: Fix Critical Blocker (1-2 hours)
**Page:** Interviews  
**Issue:** 500 error on `/bu-context/my-access` endpoint  
**Fix:**
1. Debug `/bu-context/my-access` endpoint in backend/app/api/v1/endpoints/
2. Check database query, auth dependency, response format
3. Test with: `curl -H "Authorization: Bearer TOKEN" http://localhost:8080/bu-context/my-access`
4. Fix error and test Interviews page loads

**Why:** Blocks 3+ other pages from loading

---

### PHASE 2: Populate Test Data (30 mins)
**Issue:** Database empty - all list pages show 0 items  
**Solution:** Insert test data directly into PostgreSQL

**Using psql:**
```sql
-- Create test candidates
INSERT INTO candidates (id, candidate_name, candidate_email, status, created_at)
VALUES 
  ('c1-uuid', 'Jane Doe', 'jane@test.com', 'Applied', NOW()),
  ('c2-uuid', 'John Smith', 'john@test.com', 'Interview', NOW()),
  ('c3-uuid', 'Alice Johnson', 'alice@test.com', 'Offer', NOW()),
  ... (20+ total)

-- Create test jobs
INSERT INTO jobs (id, job_title, company_name, status, created_at)
VALUES
  ('j1-uuid', 'Senior Engineer', 'BlitzenX', 'Open', NOW()),
  ('j2-uuid', 'Product Manager', 'BlitzenX', 'Open', NOW()),
  ... (10+ total)

-- Create test interviews
INSERT INTO interviews (id, candidate_id, job_id, status, created_at)
VALUES
  ('i1-uuid', 'c1-uuid', 'j1-uuid', 'Scheduled', NOW()),
  ... (15+ total)
```

**Or:** Use Python script to insert via ORM (cleaner)

---

### PHASE 3: Fix Dummy Data (1-2 hours)
**Issue:** Some fields show placeholder text instead of real values  
**Examples:**
- Job Title field shows "Job Title" text
- Other hardcoded defaults

**Fix:**
1. Search codebase for hardcoded values:
   ```bash
   grep -r '"Job Title"' frontend/src/
   grep -r "'Job Title'" frontend/src/
   ```

2. Remove default placeholder text:
   ```javascript
   // BEFORE
   value: "Job Title"  // ❌ Wrong
   
   // AFTER
   value: job?.title || ""  // ✓ Correct
   ```

3. Test each page after fix

---

### PHASE 4: Test & Verify Each Page (30 mins per page)

**Candidates Page:**
- [ ] Navigate to `/candidates`
- [ ] Should show list of 20+ candidates
- [ ] Click candidate → Details load
- [ ] Fields show real data (not "Job Title", etc.)
- [ ] No console errors
- [ ] API call shows 200 status

**Jobs Page:**
- [ ] Navigate to `/jobs`
- [ ] Should show list of 10+ jobs
- [ ] Click job → Details load
- [ ] Fields show real data
- [ ] No console errors
- [ ] API call shows 200 status

**Interviews Page:**
- [ ] Navigate to `/interviews`
- [ ] Should show list of 15+ interviews
- [ ] `/bu-context/my-access` returns 200 (not 500)
- [ ] Interviews display with candidate + job info
- [ ] No console errors

**Offer Letters:**
- [ ] Navigate to `/offer-letters`
- [ ] Should show 3+ offers
- [ ] Each offer shows candidate name, position, salary
- [ ] No 404 errors

**Executive Dashboards (CEO/CFO/Partner):**
- [ ] Navigate to `/ceo-dashboard`, etc.
- [ ] Should show metrics (not empty)
- [ ] Data loads from API (not hardcoded)
- [ ] Charts/widgets display correctly

---

## Detailed Fix Steps

### Fix 1: Debug `/bu-context/my-access` Endpoint

**File:** `backend/app/api/v1/endpoints/bu_context.py` (or similar)

**Steps:**
1. Find the endpoint definition:
   ```bash
   grep -r "bu-context/my-access" backend/app/api/
   ```

2. Check what it does:
   ```python
   @router.get("/my-access")
   def get_my_access(current_user = Depends(...)):
       # Check database query, response format
       # Look for: missing tables, auth issues, type errors
   ```

3. Add debug logging:
   ```python
   logger.info(f"Getting bu-context for user: {current_user.UserID}")
   logger.info(f"Query result: {result}")
   ```

4. Test with curl:
   ```bash
   # Get token first
   TOKEN=$(curl -X POST http://localhost:8080/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"superuser@blitzenx.com","password":"password"}' \
     | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
   
   # Test endpoint
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8080/bu-context/my-access
   ```

5. Check response:
   - 200: Has data (success)
   - 401: Auth failed (check token)
   - 500: Server error (check logs)

---

### Fix 2: Insert Test Data

**Using Direct SQL (psql):**
```bash
psql -U app_user -d wros_dev -c "
INSERT INTO candidates (id, candidate_name, candidate_email, status, tenant_id, created_at)
VALUES ('uuid-1', 'Test Candidate 1', 'test1@example.com', 'Applied', 1, NOW());
"
```

**Or Using Python ORM:**
```python
from app.models import Candidate
from app.core.database import get_db

db = next(get_db())
for i in range(20):
    c = Candidate(
        id=str(uuid.uuid4()),
        candidate_name=f"Candidate {i+1}",
        candidate_email=f"candidate{i+1}@test.com",
        status="Applied",
        tenant_id=1
    )
    db.add(c)
db.commit()
```

---

### Fix 3: Remove Hardcoded Values

**Find all hardcoded text:**
```bash
# Search for dummy values
grep -r '"Job Title"' frontend/src/ --include="*.js" --include="*.jsx"
grep -r "placeholder" frontend/src/ --include="*.js" --include="*.jsx"
grep -r "defaultValue:" frontend/src/ --include="*.js" --include="*.jsx"
```

**Example Fix:**
```javascript
// JobCreate.js - BEFORE (dummy value)
<Input value="Job Title" onChange={...} />

// JobCreate.js - AFTER (real value)
<Input value={jobData.job_title || ""} onChange={...} />
```

---

## Quick Reference: Testing Commands

**Backend Health:**
```bash
curl http://localhost:8080/health
```

**Check API Response:**
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:8080/onboarding/hr/get_all_candidates
```

**Check Database:**
```bash
psql -U app_user -d wros_dev -c "SELECT COUNT(*) FROM candidates;"
```

**Browser Console Errors:**
- Open DevTools (F12)
- Go to Console tab
- Look for red error messages
- Check Network tab for failed requests

---

## Timeline Estimate

| Phase | Task | Est. Time | Status |
|-------|------|-----------|--------|
| 1 | Fix `/bu-context/my-access` endpoint | 1-2 hrs | 🔴 CRITICAL |
| 2 | Populate test data (20+ candidates, 10+ jobs, etc.) | 30 min | ⏳ Pending |
| 3 | Remove hardcoded/dummy values | 1-2 hrs | ⏳ Pending |
| 4 | Test each page end-to-end | 30 min × 6 pages | ⏳ Pending |
| **Total** | | **4-5 hours** | |

---

## Success Criteria

✅ **Page loads without 404/500 errors**  
✅ **Shows real data from API (not dummy text)**  
✅ **Fields display correctly (no "Job Title" placeholder text)**  
✅ **API calls return 200 status**  
✅ **No console errors (F12 → Console tab)**  
✅ **Data persists on page reload**  

---

## Local Development Notes

**DO NOT COMMIT** these changes unless explicitly verified:
- Test data insertion scripts
- Debug logging additions
- Endpoint modifications

**After testing, you can:**
- Commit data population script to repo
- Document test data setup in README
- Add to CI/CD for test environment

---

## Next Steps

1. **NOW:** Focus on `/bu-context/my-access` endpoint (blocks multiple pages)
2. **THEN:** Insert test data into database
3. **THEN:** Fix hardcoded values in forms
4. **FINALLY:** Test all pages end-to-end

Start with Step 1 - the 500 error on `/bu-context/my-access` is the biggest blocker. Once that's fixed, Interviews and other pages will load.

---

**Good luck! By morning, all pages will be working with genuine data.** 🚀
