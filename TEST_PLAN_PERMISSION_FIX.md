# Test Plan: Zero-Permission Login Fix

**Status**: Code changes complete, but backend endpoints timing out  
**Date**: 2026-09-25  
**Affected Endpoints**: /auth/login, /candidates/add, /jobs/create

---

## Issue: Backend Timeout

The login endpoint (and other endpoints) are timing out, preventing functional testing. This is likely due to:

1. Database connection pooling issue
2. Async handler blocking
3. Memory leak in request handling
4. Stale backend process

**Diagnosis needed**: Check backend logs and restart the service.

---

## Test Plan Once Backend is Responsive

### TEST SCENARIO 1: Zero-Permission User Rejection

**Setup**:
1. Create a test user: `test_zero_perms@test.com`
2. Assign a role template that has NO permissions
3. Attempt login

**Expected Result**:
```
Status: 403 Forbidden
Response: {
  "detail": "Your role template has no permissions assigned. 
             Please contact help desk to assign permissions."
}
```

**Verification**:
- [ ] Login is rejected (not allowed through)
- [ ] Error message is clear and actionable
- [ ] Error is logged with details about the user and role template
- [ ] User is NOT issued a token

**Code Location**: `backend/app/api/v1/endpoints/auth.py:270-280` and `223-232`

---

### TEST SCENARIO 2: Valid User Login (Regression Test)

**Setup**:
1. Use existing admin user: `admin@blitzenx.com`
2. Verify admin has valid permissions
3. Attempt login

**Expected Result**:
```
Status: 200 OK
Response: {
  "entity_type": "user",
  "access_token": "...",
  "user_role": "Admin",
  "permissions": [ ... (multiple permissions) ... ],
  "user_email": "admin@blitzenx.com"
}
```

**Verification**:
- [ ] Login succeeds
- [ ] Access token is issued
- [ ] Permissions list is NOT empty
- [ ] User can proceed to dashboard

---

### TEST SCENARIO 3: Add Candidate Endpoint

**Setup**:
1. Login as admin (from TEST SCENARIO 2)
2. Call POST `/candidates/add`
3. Provide valid candidate data

**Expected Behavior**:
- If admin has `candidates.create` permission → ✅ Should succeed
- If not → ✅ Should return 403 Forbidden

**Test Data**:
```json
{
  "name": "Test Candidate",
  "email": "candidate@test.com",
  "phone": "+1234567890",
  "current_company": "Test Corp",
  "experience_years": 5
}
```

**Verification**:
- [ ] Permission check works at endpoint level
- [ ] Candidate is created with correct data
- [ ] Response includes candidate ID
- [ ] No regression from permission fix

**Code Location**: Check `backend/app/api/v1/endpoints/candidates/` for `@router.post` with permission decorator

---

### TEST SCENARIO 4: Add Job Endpoint

**Setup**:
1. Login as admin
2. Call POST `/jobs/create`
3. Provide valid job data

**Expected Behavior**:
- If admin has `jobs.create` permission → ✅ Should succeed
- If not → ✅ Should return 403 Forbidden

**Test Data**:
```json
{
  "title": "Senior Engineer",
  "description": "Looking for experienced engineer",
  "location": "Remote",
  "salary_range": "100k-150k"
}
```

**Verification**:
- [ ] Permission check works at endpoint level
- [ ] Job is created with correct data
- [ ] Response includes job ID
- [ ] No regression from permission fix

**Code Location**: Check `backend/app/api/v1/endpoints/jobs/` for `@router.post` with permission decorator

---

### TEST SCENARIO 5: MFA Path (Zero Permissions)

**Setup**:
1. Create test user with MFA enabled and zero permissions
2. Attempt login

**Expected Result**:
```
Status: 403 Forbidden
Response: {
  "detail": "Your role template has no permissions assigned..."
}
```

**Verification**:
- [ ] Zero-permission check happens BEFORE MFA flow
- [ ] User is rejected at permission validation, not during MFA
- [ ] Error code is consistent with non-MFA path

**Code Location**: `backend/app/api/v1/endpoints/auth.py:223-232` (MFA path)

---

## Test Execution Steps

### Prerequisites
1. Restart backend service: `cd backend && python -m uvicorn app.main:app --reload --port 8080`
2. Verify backend is responding: `curl http://localhost:8080/health`
3. Ensure database has test data

### Execute Tests

```bash
# Test 1: Zero-permission rejection
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test_zero_perms@test.com","password":"Password123"}'

# Expected: 403 Forbidden

# Test 2: Valid user login
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@blitzenx.com","password":"Admin@123"}'

# Expected: 200 OK with token

# Test 3: Add candidate (using token from Test 2)
TOKEN=$(previous_test_token)
curl -X POST http://localhost:8080/candidates/add \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"test@test.com"}'

# Test 4: Add job
curl -X POST http://localhost:8080/jobs/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Engineer","description":"Test"}'
```

---

## Success Criteria

All tests must pass:

- [x] Code changes in place (`auth.py` permission validation)
- [ ] Zero-permission users rejected at login (403 Forbidden)
- [ ] Valid users can login successfully (200 OK)
- [ ] Add candidate works (creates candidate)
- [ ] Add job works (creates job)
- [ ] No regressions in existing functionality
- [ ] Error messages are clear and actionable

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| All endpoints timeout | Backend process hung | Restart backend |
| Login always fails | Invalid test credentials | Use known user email |
| Candidate/job creation fails | Missing permission | Verify role template has `candidates.create` / `jobs.create` |
| 403 on valid user | Token not in header | Ensure Authorization header format is correct |

---

## Blocked Issues

**Current Status**: BLOCKED ON BACKEND RESPONSIVENESS

1. Backend endpoints (login, candidates, jobs) are timing out
2. Cannot execute tests until backend responds
3. Backend likely needs: restart, debugging, or process investigation

**Next Step**: Investigate why backend endpoints are hanging and restart service.

---

## Code Changes Summary

| File | Change | Validation |
|------|--------|-----------|
| `auth.py:223-232` | Added zero-permission check (MFA path) | ✅ Code reviewed |
| `auth.py:270-280` | Added zero-permission check (normal path) | ✅ Code reviewed |
| `Shell.js:455-525` | Added fallback message for zero-permission users | ✅ Code reviewed |

---

## Once Backend is Working

Run this test sequence:

1. **Permission Validation Test** → Verify zero-permission rejection
2. **Regression Test** → Verify valid users still login
3. **Functional Tests** → Verify add candidate/job work
4. **Integration Test** → Verify full workflow from login to create

If all pass → **DEPLOY TO PRODUCTION**

---

**Test Status**: Code ready, testing blocked by backend timeout issue.

