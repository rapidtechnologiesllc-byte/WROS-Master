# Authentication & Authorization Architecture

**Last Updated:** 2026-08-19  
**Status:** Production Documentation  
**Risk Level:** CRITICAL - Most defects occur here

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Authentication Flow](#authentication-flow)
3. [Authorization Flow](#authorization-flow)
4. [Database Schema](#database-schema)
5. [JWT Token Structure](#jwt-token-structure)
6. [Role Template System](#role-template-system)
7. [Common Defects & Prevention](#common-defects--prevention)
8. [Testing Strategy](#testing-strategy)
9. [Troubleshooting](#troubleshooting)

---

## System Overview

### Core Principles

1. **Separation of Concerns**
   - **Authentication** = "Who are you?" (Password verification)
   - **Authorization** = "What can you do?" (Permission checking)
   - These happen at DIFFERENT points in the request flow

2. **Database-Driven Access Control**
   - NO hardcoded roles or permissions
   - ALL access rules defined in database tables
   - Change permissions without code deployment

3. **JWT-Based Sessions**
   - Stateless tokens (no server-side session store)
   - Tokens contain UserID (not email) for lookups
   - Each request must present valid token

4. **Multi-Role Support**
   - One user can have multiple roles simultaneously
   - Permissions are UNION of all assigned roles
   - Example: User might be "Recruiter" + "BU Head" + "Partner"

---

## Authentication Flow

### Step 1: Login Request (POST /auth/login)

**Input:**
```json
{
  "email": "recruiter@test.com",
  "password": "TestRecruiter@123"
}
```

**Process:**
```python
# auth.py line 103-212
def unified_login(request: UnifiedLoginRequest, db: Session = Depends(get_db)):
    # 1. Try authenticating as User first
    user = authenticate_user(db, request.email, request.password)
    
    if user:
        # 2. Query UserRole (get actual role from database)
        user_role = db.execute(
            text('SELECT "UserRole" FROM "users" WHERE "UserEmail" = :email'),
            {"email": request.email}
        ).scalar()
        
        # 3. Check if MFA is required (gate off by default)
        if mfa_enforcement_enabled() and role_requires_mfa(user_role):
            # Return mfa_pending token (short-lived, 5 min)
            # User must complete MFA before getting real token
            return pending_token_response
        
        # 4. Create full access token
        access_token = create_access_token(
            data={
                "sub": user.UserID,        # CRITICAL: UserID, not email!
                "email": user.UserEmail,
                "type": "user",            # CRITICAL: "user", not role name!
                "name": user.UserName,
            }
        )
        
        # 5. Return response
        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            user_role=user_role,  # For UI display
            user_name=user.UserName,
            user_email=user.UserEmail,
        )
```

### Step 2: Password Verification

**Location:** `app/core/database.py::authenticate_user()`

```python
def authenticate_user(db: Session, email: str, password: str):
    user = db.query(Users).filter(Users.UserEmail == email).first()
    if not user:
        return None
    
    # CRITICAL: Use bcrypt for password verification
    if not verify_password(password, user.UserPassword):
        return None
    
    return user
```

**Why bcrypt?**
- One-way hashing (cannot reverse)
- Built-in salt + stretching (resistant to rainbow tables)
- Time-consistent comparison (resistant to timing attacks)

**DEFECT RISK:** If password is ever checked as plaintext comparison, you're done for.

### Step 3: Token Creation

**Location:** `app/core/security_local.py::create_access_token()`

**Critical Fields:**
```python
access_token_data = {
    "sub": user.UserID,              # ✅ MUST be UserID (unique)
    "email": user.UserEmail,         # Optional but recommended
    "type": "user",                  # ✅ MUST be "user" (not role!)
    "name": user.UserName,           # Optional, for UI display
    "mfa_pending": False,            # Optional, only for MFA flow
}

# Token expires in 24 hours by default
# Use shorter TTL for sensitive operations
```

**⚠️ CRITICAL MISTAKES THAT BREAK AUTH:**

| Mistake | Impact | Why It Fails |
|---------|--------|------------|
| `"sub": user.UserEmail` | All auth fails with 401 | Dependencies query by UserID, not email |
| `"type": user.UserRole` | All auth fails with 401 | Dependencies check `type == "user"` |
| Missing "sub" field | All auth fails with 401 | Dependencies extract UserID from "sub" |
| Token expires immediately | Users logged out constantly | TTL too short |
| Token never expires | Security vulnerability | TTL too long or missing |

### Step 4: Token Storage (Frontend)

**Location:** `src/pages/AuthPage.js::finishLogin()`

```javascript
localStorage.setItem("hrms_token", data.access_token);
localStorage.setItem("user_info", JSON.stringify(user));
localStorage.setItem("permission_role", user.user_role);
```

**DEFECT RISKS:**
- ❌ Token stored in sessionStorage (lost on browser close)
- ❌ Token stored in cookie without httpOnly flag (XSS vulnerability)
- ❌ Token stored in URL params (visible in history/logs)

---

## Authorization Flow

### Key Concept: Authorization ≠ Login

**Login** happens ONCE and returns a token.

**Authorization** happens on EVERY request to a protected endpoint.

### Step 1: Frontend Makes Authenticated Request

```javascript
// src/services/api/client.js
const withAuthHeaders = (headers = {}) => {
    const token = localStorage.getItem("hrms_token");
    if (token) {
        result.Authorization = `Bearer ${token}`;
    }
    return result;
};

// Example request
apiRequest("/candidates", {
    method: "GET",
    headers: withAuthHeaders()
});
```

### Step 2: Backend Receives Request

**Request arrives with header:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Step 3: Dependency Checks Token

**Example endpoint:**
```python
# app/api/v1/endpoints/candidates.py
@router.get(
    "/candidates",
    dependencies=[Depends(require_resource_permission("candidates", "view"))]
)
def get_candidates(db: Session = Depends(get_db)):
    # This code only runs if permission check passes
    ...
```

**Location:** `app/core/dependencies.py::require_resource_permission()`

```python
def require_resource_permission(resource_name: str, action: str = "view"):
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        # 1. Extract token from header
        token = credentials.credentials  # "eyJhbGciOiJIUzI1NiIs..."
        
        # 2. Decode and verify token signature
        payload = decode_access_token(token)
        # payload = {"sub": "user-123", "type": "user", ...}
        
        # 3. Check if token is mfa_pending (special case)
        if payload.get("mfa_pending"):
            raise HTTPException(
                status_code=403,
                detail="MFA verification required"
            )
        
        # 4. Extract UserID from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # 5. CRITICAL: Query database by UserID
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # 6. Check if super user (bypass all checks)
        if RoleTemplatePermissionService.is_super_user(db, user.UserID, user.tenant_id):
            return user
        
        # 7. Check specific resource permission
        has_permission = RoleTemplatePermissionService.has_permission(
            db, user.UserID, resource_name, action, user.tenant_id
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {action} access to '{resource_name}' required"
            )
        
        return user
    
    return _check
```

### Step 4: Permission Service Checks Database

**Location:** `app/services/role_template_permission_service.py`

```python
class RoleTemplatePermissionService:
    @staticmethod
    def has_permission(db, user_id, resource_name, action, tenant_id):
        """
        Check if user has specific permission on resource.
        
        Flow:
        1. Get all roles assigned to user
        2. For each role, get permissions
        3. Check if any role has (resource, action) permission
        4. Return True if found, False otherwise
        """
        
        # 1. Query user roles
        user_roles = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.tenant_id == tenant_id
        ).all()
        
        if not user_roles:
            return False  # User has no roles
        
        # 2. For each role, check permissions
        for user_role in user_roles:
            role_id = user_role.role_template_id
            
            # Query permission
            permission = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role_id,
                RoleTemplatePermission.resource_name == resource_name,
                RoleTemplatePermission.action == action,
                RoleTemplatePermission.tenant_id == tenant_id
            ).first()
            
            if permission:
                return True  # Found permission, user is authorized
        
        return False  # No role has this permission
```

### Step 5: Request Proceeds or Fails

**If authorized (200 OK):**
```python
def get_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return candidates
```

**If unauthorized (403 Forbidden):**
```python
# Response automatically sent by dependency
HTTP/1.1 403 Forbidden
{
    "detail": "Permission denied: view access to 'candidates' required"
}
```

---

## Database Schema

### Core Tables

#### 1. `users` table
```sql
CREATE TABLE users (
    UserID VARCHAR(36) PRIMARY KEY,
    UserEmail VARCHAR(255) UNIQUE NOT NULL,
    UserPassword VARCHAR(255) NOT NULL,      -- bcrypt hash
    UserName VARCHAR(255),
    UserRole VARCHAR(50),                    -- legacy field
    tenant_id INT,
    business_unit_id VARCHAR(36),            -- user's primary BU
    mfa_enabled BOOLEAN DEFAULT FALSE,
    email_otp_code_hash VARCHAR(255),
    email_otp_expires_at TIMESTAMP,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**DEFECT RISK:** If UserEmail is non-unique, authentication breaks (multiple users with same email).

#### 2. `role_template` table
```sql
CREATE TABLE role_template (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,       -- "Recruiter", "Admin", etc.
    description TEXT,
    tenant_id INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Example data:**
```
id=1, name="Super User", tenant_id=1
id=2, name="Admin", tenant_id=1
id=3, name="Recruiter", tenant_id=1
id=4, name="HR Manager", tenant_id=1
```

#### 3. `user_role` junction table (many-to-many)
```sql
CREATE TABLE user_role (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(36) NOT NULL,
    role_template_id INT NOT NULL,
    business_unit_id VARCHAR(36),            -- optional: BU-specific role
    tenant_id INT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(UserID),
    FOREIGN KEY (role_template_id) REFERENCES role_template(id)
);
```

**Example data:**
```
user_id="user-123", role_template_id=3 (Recruiter)
user_id="user-123", role_template_id=4 (HR Manager)  -- Same user, 2 roles!
user_id="user-456", role_template_id=2 (Admin)
```

**DEFECT RISK:** If a user is assigned the same role twice, you might get duplicate permission checks (inefficiency but not a break).

#### 4. `role_template_permission` table
```sql
CREATE TABLE role_template_permission (
    id INT PRIMARY KEY AUTO_INCREMENT,
    role_template_id INT NOT NULL,
    resource_name VARCHAR(100) NOT NULL,    -- "candidates", "jobs", etc.
    action VARCHAR(50) NOT NULL,             -- "view", "create", "edit", "delete"
    can_view BOOLEAN DEFAULT FALSE,
    can_create BOOLEAN DEFAULT FALSE,
    can_edit BOOLEAN DEFAULT FALSE,
    can_delete BOOLEAN DEFAULT FALSE,
    tenant_id INT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_template_id) REFERENCES role_template(id),
    UNIQUE KEY (role_template_id, resource_name, action)
);
```

**Example data:**
```
role_template_id=3 (Recruiter), resource="candidates", action="view"
role_template_id=3 (Recruiter), resource="candidates", action="create"
role_template_id=3 (Recruiter), resource="candidates", action="edit"
role_template_id=3 (Recruiter), resource="jobs", action="view"
role_template_id=4 (HR Manager), resource="candidates", action="view"
role_template_id=4 (HR Manager), resource="employees", action="edit"
```

**DEFECT RISK:** If duplicate rows exist (same role, resource, action), queries might return multiple rows causing logic errors.

### Relationships Diagram

```
users (1) ←→ (M) user_role (M) ↔ (1) role_template
                                         ↓
                            role_template_permission
                                    (checks what user can do)
```

---

## JWT Token Structure

### Token Format

**Raw Token:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoiYXlhbkBleGFtcGxlLmNvbSIsInR5cGUiOiJ1c2VyIiwibmFtZSI6IkF5YW4gQWdncmF3YWwifQ.x3K2uJ8vQ1pZ0b5...
```

**Decoded Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Decoded Payload:**
```json
{
  "sub": "user-uuid-12345",           // CRITICAL: UserID (not email)
  "email": "ayan@example.com",        // Optional but recommended
  "type": "user",                     // CRITICAL: "user" (not role)
  "name": "Ayan Aggrawal",            // Optional
  "iat": 1692518400,                  // issued at
  "exp": 1692604800                   // expires in 24 hours
}
```

**Decoded Signature:**
```
HMACSHA256(
  base64UrlEncode(header) + "." +
  base64UrlEncode(payload),
  "your-secret-key-here"
)
```

### Token Verification (Every Request)

```python
def decode_access_token(token: str):
    """
    Verify token signature and return payload.
    
    Raises HTTPException if:
    - Signature is invalid (tampered token)
    - Token is expired
    - Token is malformed
    """
    try:
        # Verify signature using SECRET_KEY
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### CRITICAL: Never Trust "type" Field for Authorization

**WRONG:**
```python
if payload.get("type") == "Admin":
    return True  # DON'T DO THIS!
```

**RIGHT:**
```python
# Always query database to verify actual role assignment
user_roles = db.query(UserRole).filter(
    UserRole.user_id == payload["sub"]
).all()

# Check if any role has permission
for role in user_roles:
    if has_permission_in_db(role, resource, action):
        return True
```

**Why?** Token is issued once (at login). If admin removes a role from a user, the token is still valid until expiry. Only database reflects current state.

---

## Role Template System

### How Multi-Role Works

**User:** recruiter@test.com

**Assigned Roles:**
```sql
INSERT INTO user_role VALUES
(null, "user-123", 3, null, 1),  -- Recruiter
(null, "user-123", 4, null, 1);  -- HR Manager
```

**When User Requests /candidates:**

1. Token decoded → user_id = "user-123"
2. Query user_role WHERE user_id="user-123" → returns 2 rows (Recruiter + HR Manager)
3. For Recruiter role: Check if has "candidates.view" → YES
4. User is authorized ✅

**When User Requests /invoices (Finance resource):**

1. Token decoded → user_id = "user-123"
2. Query user_role WHERE user_id="user-123" → returns 2 rows (Recruiter + HR Manager)
3. For Recruiter role: Check if has "invoices.view" → NO
4. For HR Manager role: Check if has "invoices.view" → NO
5. User is NOT authorized ❌

**Result:** Permissions are UNION (any role can grant access)

### Super User Bypass

**Special role:** "Super User" (or wildcard check)

```python
@staticmethod
def is_super_user(db, user_id, tenant_id):
    """
    Check if user has Super User role.
    Super Users bypass all permission checks.
    """
    super_user_role = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Super User",
        RoleTemplate.tenant_id == tenant_id
    ).first()
    
    if not super_user_role:
        return False
    
    user_has_role = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_template_id == super_user_role.id
    ).first()
    
    return bool(user_has_role)
```

**Usage in dependency:**
```python
# Check Super User before checking specific permission
if RoleTemplatePermissionService.is_super_user(db, user_id, tenant_id):
    return user  # Bypass permission check

# Otherwise check specific permission
if not has_permission(...):
    raise HTTPException(403, "Permission denied")
```

**DEFECT RISK:** If Super User check is missing or comes AFTER permission check, it won't work.

---

## Common Defects & Prevention

### DEFECT #1: Token "sub" Contains Email Instead of UserID

**Symptom:** All authenticated requests return 401 Unauthorized

**Root Cause:**
```python
# WRONG
access_token = create_access_token(
    data={"sub": user.UserEmail}  # ❌ WRONG
)

# Dependencies query by UserID
user = db.query(Users).filter(Users.UserID == payload["sub"]).first()
# ↑ Queries by email string, not UUID → No match → None → 401
```

**Prevention:**
```python
# RIGHT
access_token = create_access_token(
    data={"sub": user.UserID}  # ✅ CORRECT
)
```

**Test:** Log the token payload and verify "sub" is a UUID, not an email.

---

### DEFECT #2: Token "type" Contains Role Name Instead of "user"

**Symptom:** All authenticated requests return 401 Unauthorized

**Root Cause:**
```python
# WRONG
access_token = create_access_token(
    data={"type": user.UserRole}  # ❌ WRONG (e.g., "Recruiter")
)

# Dependencies check type
if payload.get("type") == "user":  # ❌ Receives "Recruiter" → False
    user = db.query(Users).filter(Users.UserID == user_id).first()
else:
    user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
    # ↑ Queries Candidate table → No match → 401
```

**Prevention:**
```python
# RIGHT
access_token = create_access_token(
    data={"type": "user"}  # ✅ CORRECT
)
```

**Test:** Log the token payload and verify "type" is exactly "user" (not role name).

---

### DEFECT #3: Dependencies Query by Email Instead of UserID

**Symptom:** All authenticated requests return 401 Unauthorized

**Root Cause:**
```python
# WRONG (in dependencies.py)
user_email = payload.get("sub")  # "recruiter@test.com"
user = db.query(Users).filter(
    Users.UserEmail == user_email  # ❌ WRONG
).first()

# If token was created with UserID in "sub", this won't match
# because "sub" is now "user-123" but we're querying by email
```

**Prevention:**
```python
# RIGHT
user_id = payload.get("sub")  # "user-123"
user = db.query(Users).filter(
    Users.UserID == user_id  # ✅ CORRECT
).first()
```

**Test:** Log both the token payload and the database query to verify they match.

---

### DEFECT #4: Token Expires Too Quickly

**Symptom:** Users get logged out in the middle of work

**Root Cause:**
```python
# WRONG
access_token = create_access_token(
    data={...},
    expires_delta=timedelta(minutes=5)  # ❌ Too short!
)
```

**Prevention:**
```python
# RIGHT (default is 24 hours)
access_token = create_access_token(
    data={...}
    # expires_delta defaults to 24 hours if not specified
)
```

**Testing:**
```python
# Verify expiration time
payload = decode_access_token(token)
exp = payload.get("exp")
now = datetime.utcnow().timestamp()
minutes_until_expiry = (exp - now) / 60
assert minutes_until_expiry > 1000  # Should be ~1440 minutes (24 hours)
```

---

### DEFECT #5: Token Never Expires

**Symptom:** Security vulnerability - revoked users still have access

**Root Cause:**
```python
# WRONG
def create_access_token(data: dict):
    to_encode = data.copy()
    # ❌ No expiration set
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt
```

**Prevention:**
```python
# RIGHT
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)  # Default 24h
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt
```

**Test:** Verify all tokens include an "exp" claim.

---

### DEFECT #6: No Permission Check on Endpoint

**Symptom:** Unauthorized users can access resources they shouldn't

**Root Cause:**
```python
# WRONG
@router.get("/candidates")  # ❌ No permission check!
def get_candidates(db: Session = Depends(get_db)):
    return db.query(Candidate).all()
```

**Prevention:**
```python
# RIGHT - Option 1: Check specific resource
@router.get(
    "/candidates",
    dependencies=[Depends(require_resource_permission("candidates", "view"))]
)
def get_candidates(db: Session = Depends(get_db)):
    return db.query(Candidate).all()

# RIGHT - Option 2: Check user is authenticated (any internal user)
@router.get("/candidates")
def get_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin)
):
    return db.query(Candidate).all()
```

**Test:** Try accessing endpoint without token → should get 401/403.

---

### DEFECT #7: Permission Check Returns Multiple Rows

**Symptom:** Unpredictable behavior (might grant or deny access randomly)

**Root Cause:**
```sql
-- WRONG: Duplicate rows in role_template_permission
INSERT INTO role_template_permission VALUES
(1, 3, 'candidates', 'view', 1),
(2, 3, 'candidates', 'view', 1);  -- ❌ Duplicate!
```

**Prevention:**
```sql
-- Add unique constraint
ALTER TABLE role_template_permission
ADD UNIQUE (role_template_id, resource_name, action, tenant_id);

-- This prevents duplicates
```

**Check:** Query the database and look for duplicates:
```sql
SELECT role_template_id, resource_name, action, COUNT(*)
FROM role_template_permission
GROUP BY role_template_id, resource_name, action
HAVING COUNT(*) > 1;
```

---

### DEFECT #8: MFA Pending Token Used for Regular Requests

**Symptom:** User logs in with MFA → tries to use API → gets 403

**Root Cause:**
```python
# WRONG: Don't check for mfa_pending
if payload.get("mfa_pending"):
    # ❌ Missing check in authorization

# User token has mfa_pending=True, but code doesn't reject it
```

**Prevention:**
```python
# RIGHT: Reject mfa_pending tokens on regular endpoints
async def _check(credentials: HTTPAuthorizationCredentials, db):
    payload = decode_access_token(credentials.credentials)
    
    if payload.get("mfa_pending"):  # ✅ Check this
        raise HTTPException(
            status_code=403,
            detail="MFA verification required"
        )
    
    # Continue with regular auth
```

**Test:**
1. Enable MFA
2. User logs in → gets mfa_pending token
3. Try calling /candidates with that token
4. Should get 403, not 200

---

### DEFECT #9: User Deleted but Token Still Valid

**Symptom:** Deleted user can still access API until token expires

**Root Cause:** Only the token is checked, not whether user still exists

**Prevention:**
```python
# RIGHT: Always verify user exists in database
def require_resource_permission(resource_name: str, action: str = "view"):
    async def _check(credentials, db):
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        
        # Query database every request
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:  # ✅ Check if user was deleted
            raise HTTPException(status_code=401, detail="User not found")
        
        # Continue with permission check
```

**Test:**
1. User logs in → token issued
2. Delete user from database
3. Try calling endpoint with old token
4. Should get 401 (not 200)

---

### DEFECT #10: Role Assigned but No Permissions

**Symptom:** User is assigned role but can't access anything

**Root Cause:**
```sql
-- User assigned to role
INSERT INTO user_role (user_id, role_template_id) VALUES ("user-123", 3);

-- But role has no permissions
SELECT * FROM role_template_permission WHERE role_template_id = 3;
-- Returns: (empty)
```

**Prevention:**
1. When creating a role, also create its permissions
2. Test every role has at least one permission:

```sql
SELECT rt.id, rt.name, COUNT(rtp.id) as permission_count
FROM role_template rt
LEFT JOIN role_template_permission rtp ON rt.id = rtp.role_template_id
GROUP BY rt.id
HAVING permission_count = 0;  -- These roles are broken!
```

---

## Testing Strategy

### Unit Tests

```python
# test_authentication.py

def test_user_login_success():
    user = create_test_user("recruiter@test.com", "Recruiter")
    response = login(email="recruiter@test.com", password="correct_password")
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    
    # Verify token claims
    token = response.json()["access_token"]
    payload = decode_token(token)
    assert payload["sub"] == user.UserID  # ✅ UserID, not email
    assert payload["type"] == "user"       # ✅ "user", not role
    assert "email" in payload             # ✅ Email present

def test_user_login_wrong_password():
    create_test_user("recruiter@test.com", "Recruiter")
    response = login(email="recruiter@test.com", password="wrong_password")
    
    assert response.status_code == 401

def test_token_expires():
    user = create_test_user("recruiter@test.com", "Recruiter")
    token = create_test_token(user, expires_delta=timedelta(seconds=1))
    
    time.sleep(2)  # Wait for expiry
    
    response = api_call("/candidates", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401  # Token expired

def test_permission_check():
    recruiter = create_test_user("recruiter@test.com", "Recruiter")
    admin = create_test_user("admin@test.com", "Admin")
    
    # Recruiter can view candidates
    recruiter_token = login_and_get_token(recruiter)
    response = api_call("/candidates", token=recruiter_token)
    assert response.status_code == 200
    
    # But not invoices (Finance resource)
    response = api_call("/invoices", token=recruiter_token)
    assert response.status_code == 403
    
    # Admin can view invoices
    admin_token = login_and_get_token(admin)
    response = api_call("/invoices", token=admin_token)
    assert response.status_code == 200

def test_deleted_user_token_revoked():
    user = create_test_user("recruiter@test.com", "Recruiter")
    token = login_and_get_token(user)
    
    # Verify token works
    response = api_call("/candidates", token=token)
    assert response.status_code == 200
    
    # Delete user
    db.delete(user)
    db.commit()
    
    # Old token should now fail
    response = api_call("/candidates", token=token)
    assert response.status_code == 401
```

### Integration Tests

```python
# test_auth_flow_end_to_end.py

def test_full_login_to_dashboard_flow():
    # 1. Create user with role
    recruiter = create_test_user("recruiter@test.com", "Recruiter")
    assign_role(recruiter, "Recruiter")
    assign_permission("Recruiter", "candidates", "view")
    
    # 2. Login
    response = login(email="recruiter@test.com", password="password")
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    # 3. Access dashboard (should succeed)
    response = api_call("/candidates", token=token)
    assert response.status_code == 200
    
    # 4. Try finance endpoint (should fail)
    response = api_call("/invoices", token=token)
    assert response.status_code == 403
    
    # 5. Assign Finance permission
    assign_permission("Recruiter", "invoices", "view")
    
    # 6. Try again (should now succeed)
    response = api_call("/invoices", token=token)
    assert response.status_code == 200  # Now has permission!
```

### Manual Testing Checklist

- [ ] User can login with correct password
- [ ] User cannot login with wrong password
- [ ] Token contains correct UserID in "sub" field
- [ ] Token contains "user" in "type" field
- [ ] Token contains "email" field
- [ ] Token expires after 24 hours
- [ ] Expired token gets 401 on API call
- [ ] Missing token gets 401 on API call
- [ ] User assigned to role can access resources for that role
- [ ] User not assigned to role cannot access those resources
- [ ] Super User bypasses all permission checks
- [ ] Deleting user from DB invalidates existing tokens
- [ ] Changing user role in DB is reflected immediately
- [ ] Adding new permission to role works immediately
- [ ] User with multiple roles gets union of permissions

---

## Troubleshooting

### User Gets 401 on Every Request After Login

**Checklist:**
1. [ ] Is token stored in localStorage?
   ```javascript
   console.log(localStorage.getItem("hrms_token"))
   ```

2. [ ] Is token being sent in Authorization header?
   ```javascript
   // Network tab: Check request headers
   Authorization: Bearer eyJhbGc...
   ```

3. [ ] Is token expired?
   ```python
   import jwt
   from datetime import datetime
   payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
   exp = payload.get("exp")
   now = datetime.utcnow().timestamp()
   print(f"Expires in {exp - now} seconds")
   ```

4. [ ] Does token contain correct "sub" (UserID)?
   ```python
   payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
   print(f"sub = {payload['sub']}")
   print(f"type = {payload['type']}")
   # Should be: sub="user-uuid", type="user"
   ```

5. [ ] Does user exist in database?
   ```sql
   SELECT * FROM users WHERE UserID = 'user-uuid';
   ```

6. [ ] Check backend logs for error message:
   ```
   [AUTH-DEBUG] User not found with UserID: user-uuid
   [AUTH-DEBUG] Exception in get_current_user: ...
   ```

---

### User Gets 403 Forbidden on Permitted Endpoint

**Checklist:**
1. [ ] Is role assigned to user?
   ```sql
   SELECT ur.* FROM user_role ur
   WHERE ur.user_id = 'user-uuid';
   ```

2. [ ] Does role have permission?
   ```sql
   SELECT rtp.* FROM role_template_permission rtp
   WHERE rtp.role_template_id = (SELECT id FROM role_template WHERE name = 'Recruiter')
   AND rtp.resource_name = 'candidates'
   AND rtp.action = 'view';
   ```

3. [ ] Are there duplicate permissions?
   ```sql
   SELECT role_template_id, resource_name, action, COUNT(*)
   FROM role_template_permission
   GROUP BY role_template_id, resource_name, action
   HAVING COUNT(*) > 1;
   ```

4. [ ] Check backend logs:
   ```
   [PERMISSION] User user-uuid checking candidates.view
   [PERMISSION] Role "Recruiter" has permission: True
   [PERMISSION] Access granted ✓
   ```

---

### Token Claims Keep Changing

**Possible causes:**
1. Multiple versions of create_access_token() function
   - Search codebase: `def create_access_token`
   - Should only exist in one place

2. Multiple auth endpoints
   - `/auth/login`
   - `/auth/v1/login`
   - `/auth/login/simple`
   - All should use same token format

3. Mismatch between token creation and token verification
   - Search for all places that call `create_access_token()`
   - Verify all pass correct "sub" and "type" fields

---

## Production Deployment Checklist

- [ ] JWT SECRET_KEY is strong (>32 chars) and stored in environment
- [ ] No default SECRET_KEY in code
- [ ] All endpoints with Depends(require_resource_permission(...))
- [ ] No endpoints with Depends(get_current_user) only (need resource check)
- [ ] Token expiration set to 24 hours
- [ ] Database has unique constraint on UserEmail
- [ ] Database has unique constraint on role_template_permission
- [ ] All roles have at least one permission
- [ ] Super User role exists
- [ ] Password hashing uses bcrypt (not plaintext)
- [ ] HTTPS only (HTTP redirected)
- [ ] CORS configured properly (not Access-Control-Allow-Origin: *)
- [ ] All secrets in environment variables
- [ ] Automated tests pass (auth, permission, token tests)
- [ ] Manual testing checklist completed
- [ ] Monitoring alerts for 401/403 spikes

---

## Security Best Practices

1. **Never log tokens** - They're credentials
2. **Never send token in URL** - Use Authorization header only
3. **Never store user password** - Hash with bcrypt
4. **Never trust "type" field in token** - Verify in database every request
5. **Never skip permission check** - Even for "trusted" clients
6. **Never use short token expiration** - Causes constant logouts
7. **Never use infinite token expiration** - Revoked users stay revoked
8. **Never trust client permissions** - Always verify on backend
9. **Never hardcode roles** - Always use database-driven roles
10. **Never assume SuperUser bypass works** - Test it explicitly

---

## Summary

The authentication and authorization system is **database-driven** and **request-time validated**:

- **Login** verifies password and issues a JWT token with UserID
- **Every request** verifies token signature, checks if user exists, and verifies permission
- **Permissions are real-time** - changing a role in the DB immediately affects all users
- **Multi-role support** - users get UNION of all assigned roles' permissions
- **No hardcoding** - all access rules defined in database

The most common defects occur when:
1. Token is created with UserEmail instead of UserID
2. Token is created with UserRole instead of "user"
3. Dependencies query by UserEmail instead of UserID
4. Permission checks are skipped on an endpoint
5. Tokens expire too quickly or never expire

Test thoroughly before production deployment.
