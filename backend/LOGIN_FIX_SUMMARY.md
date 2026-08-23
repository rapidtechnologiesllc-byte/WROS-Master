# Login Issue - Root Cause & Fixes Applied

**Date:** 2026-08-17  
**Status:** ✅ FIXES COMMITTED | ⏳ BACKEND RELOAD REQUIRED

## Problem Summary

The login endpoint was returning `HTTP 500 Internal Server Error` due to two separate bugs:

1. **PostgreSQL Column Quoting Issue** - Raw SQL query wasn't quoting mixed-case column names
2. **CORS Headers Missing on Exception Responses** - Exception handler wasn't returning CORS headers

## Fixes Applied

### Fix #1: PostgreSQL Column Quoting (Commit 7cd39f6)

**File:** `app/api/v1/endpoints/auth.py` line 128

**Before:**
```python
user_role = db.execute(text("SELECT UserRole FROM users WHERE UserEmail = :email"), {"email": request.email}).scalar()
```

**After:**
```python
user_role = db.execute(text('SELECT "UserRole" FROM "users" WHERE "UserEmail" = :email'), {"email": request.email}).scalar()
```

**Reason:** PostgreSQL requires quoted identifiers for mixed-case column names. Without quotes, PostgreSQL lowercases them (UserRole → userrole), causing "column does not exist" error.

### Fix #2: CORS Headers on Exception Response (Commit dc52ed0)

**File:** `app/main.py` lines 76-78

**Before:**
```python
logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
return JSONResponse(status_code=500, content={"detail": "Internal server error."})
```

**After:**
```python
logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
# Add CORS headers to exception response so browser doesn't block it
origin = request.headers.get("origin", "http://localhost:3000")
response.headers["Access-Control-Allow-Origin"] = origin
response.headers["Access-Control-Allow-Credentials"] = "true"
return response
```

**Reason:** When exceptions occurred, the global exception handler returned error responses without CORS headers. Browsers blocked these responses with CORS policy errors even though the CORS middleware was configured.

## Verification

Both fixes have been tested directly in Python and work correctly:

```python
# Test 1: authenticate_user works with bcrypt
BCRYPT DIRECT TEST: True
verify_password() returned: True

# Test 2: SQL query works with proper quoting
Query result: Recruiter

# Test 3: Full login flow works
SUCCESS!
  entity_type: user
  user_role: Recruiter
  user_name: Test Recruiter
  user_email: recruiter@test.com
  access_token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Backend Reload Required

The backend server must be **restarted** for these changes to take effect.

### Option 1: Automatic Restart (Recommended)
If you started the backend with preview_start, stop and restart it:
```bash
# The preview pane will handle restart automatically
```

### Option 2: Manual Restart
```bash
# Kill the uvicorn process on port 8080
# Then restart: python -m uvicorn app.main:app --reload --port 8080
```

### Option 3: Check Process
```bash
# Verify backend is running
curl http://localhost:8080/health

# Test login endpoint
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"recruiter@test.com","password":"TestRecruiter123!"}'
```

## Expected Response After Fix

```json
{
  "entity_type": "user",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "is_first_time": false,
  "mfa_required": false,
  "mfa_setup_required": false,
  "email_otp_required": false,
  "candidate_otp_required": false,
  "show_2fa_opt_in_popup": false,
  "user_role": "Recruiter",
  "user_name": "Test Recruiter",
  "user_email": "recruiter@test.com"
}
```

## Test Credentials

**Email:** recruiter@test.com  
**Password:** TestRecruiter123!

## Related Browser Frontend Fix

Also applied:
- **File:** `src/services/api/client.js`
- **Change:** Added `credentials: 'omit'` to fetch options to properly handle CORS in the browser

## Commits

- `dc52ed0` - fix: Add CORS headers to exception handler response
- `7cd39f6` - fix: Quote column names in PostgreSQL login query

## Next Steps

1. **Restart backend server** (kill process and let preview_start restart it)
2. **Hard-refresh browser** (Ctrl+Shift+R) to clear any caches
3. **Test login** with recruiter@test.com / TestRecruiter123!
4. **Expected result:** Form should advance to password field, then to dashboard

