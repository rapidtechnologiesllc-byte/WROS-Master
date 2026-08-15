# Master Routes Quick Reference

## TL;DR Setup (3 steps)

### Step 1: Import in main.py
```python
from app.api.v1.routes_master import setup_master_routes
```

### Step 2: Call setup function
```python
setup_master_routes(app)
```

### Step 3: Start server
```bash
uvicorn app.main:app --reload
```

✅ Done! All 15 endpoints working with auth, validation, tenant isolation, error handling.

---

## 15 Core Story Endpoints at a Glance

| #  | Story | Endpoint | Method | Auth | Tenant | Permission |
|----|-------|----------|--------|------|--------|------------|
| 1  | HRMS-0101 | `/auth/login` | POST | ❌ | - | - |
| 2  | HRMS-0114 | `/users/create-with-roles` | POST | ✅ | ✅ | user.manage |
| 3  | HRMS-0114 | `/rbac/roles` | GET | ✅ | ✅ | role.view |
| 4  | HRMS-0201 | `/candidates/add` | POST | ✅ | ✅ | candidate.create |
| 5  | HRMS-0201 | `/candidates/{id}` | GET | ✅ | ✅ | candidate.view |
| 6  | HRMS-0202 | `/jobs/create` | POST | ✅ | ✅ | job.create |
| 7  | HRMS-0202 | `/jobs/{id}` | GET | ✅ | ✅ | job.view |
| 8  | HRMS-0203 | `/interviews/schedule` | POST | ✅ | ✅ | interview.schedule |
| 9  | HRMS-0203 | `/interviews/{id}/feedback` | POST | ✅ | ✅ | interview.feedback |
| 10 | HRMS-0204 | `/offers/create` | POST | ✅ | ✅ | offer.create |
| 11 | HRMS-0204 | `/offers/{id}/approve` | POST | ✅ | ✅ | offer.approve |
| 12 | HRMS-0205 | `/onboarding/start` | POST | ✅ | ✅ | onboarding.manage |
| 13 | HRMS-0206 | `/employees/convert-from-candidate` | POST | ✅ | ✅ | employee.convert |
| 14 | HRMS-0207 | `/notifications/send` | POST | ✅ | ✅ | notification.send |
| 15 | HRMS-0207 | `/notifications/list` | GET | ✅ | ✅ | notification.view |

**Legend**:
- `Auth` ✅ = requires JWT token in Authorization header
- `Tenant` ✅ = enforces tenant isolation
- Permission = required permission to call endpoint

---

## Common Code Patterns

### Pattern 1: Create Resource with Validation

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

# Schema (validation)
class CreateCandidateRequest(BaseModel):
    first_name: str
    email: EmailStr  # Auto-validated email format
    phone: str
    
# Endpoint
@router.post("/candidates/add", status_code=201)
def create_candidate(
    req: CreateCandidateRequest,                          # Validation
    current_user = Depends(get_current_user),            # Auth
    db: Session = Depends(get_db)                        # Tenant-scoped DB
):
    """Create candidate in current user's business unit."""
    
    # Check duplicate
    existing = db.query(Candidate).filter_by(
        email=req.email,
        tenant_id=current_user.tenant_id
    ).first()
    if existing:
        raise HTTPException(409, "Candidate email already exists")
    
    # Create via safe factory (NEVER raw insert)
    candidate = createCandidateSafe(
        db, 
        current_user.tenant_id, 
        req
    )
    return {"id": candidate.id, "email": candidate.email}
```

### Pattern 2: Get Resource with Tenant Isolation

```python
@router.get("/candidates/{candidate_id}")
def get_candidate(
    candidate_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get candidate (404 if not in user's tenant)."""
    
    candidate = db.query(Candidate).filter_by(
        id=candidate_id,
        tenant_id=current_user.tenant_id
    ).first()
    
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    
    return {
        "id": candidate.id,
        "email": candidate.email,
        "status": candidate.status
    }
```

### Pattern 3: Permission Check

```python
def check_permission(permission: str):
    """Decorator to verify permission before route execution."""
    def verify(user = Depends(get_current_user)):
        if not user.has_permission(permission):
            raise HTTPException(403, f"Requires {permission}")
        return user
    return Depends(verify)

@router.post("/offers/create")
def create_offer(
    req: CreateOfferRequest,
    current_user = Depends(check_permission("offer.create")),
    db: Session = Depends(get_db)
):
    """Create offer (requires offer.create permission)."""
    pass
```

### Pattern 4: Error Handling

```python
from app.api.v1.routes_master import ErrorResponse

@router.post("/interviews/schedule")
def schedule_interview(
    req: ScheduleInterviewRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Schedule interview with comprehensive error handling."""
    
    # 404: Resource not found
    candidate = db.query(Candidate).filter_by(id=req.candidate_id).first()
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    
    # 400: Validation failed
    if candidate.status != "QUALIFIED":
        raise HTTPException(
            400, 
            "Candidate must be QUALIFIED before scheduling interview"
        )
    
    # 409: Conflict with existing state
    if candidate.interview_id:
        raise HTTPException(409, "Interview already scheduled")
    
    # Success
    interview = Interview(
        candidate_id=candidate.id,
        scheduled_at=req.scheduled_at
    )
    db.add(interview)
    db.commit()
    
    return {"interview_id": interview.id, "status": "scheduled"}
```

### Pattern 5: Pagination

```python
from pydantic import BaseModel

class ListCandidatesRequest(BaseModel):
    page: int = 1
    limit: int = 50  # Max 1000

@router.get("/candidates/list")
def list_candidates(
    skip: int = 0,
    limit: int = 50,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List candidates with pagination."""
    
    # Enforce max limit
    if limit > 1000:
        limit = 1000
    
    # Query with automatic tenant filtering
    candidates = db.query(Candidate)\
        .filter_by(tenant_id=current_user.tenant_id)\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    total = db.query(Candidate)\
        .filter_by(tenant_id=current_user.tenant_id)\
        .count()
    
    return {
        "data": candidates,
        "page": skip // limit + 1,
        "limit": limit,
        "total": total
    }
```

---

## Testing Patterns

### Test 1: Authentication Required

```python
import pytest

def test_create_candidate_without_auth():
    """Should return 401 without JWT token."""
    response = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "Jane", "email": "jane@example.com"}
    )
    assert response.status_code == 401
    assert "Authorization" in response.json()["message"]

def test_create_candidate_with_invalid_token():
    """Should return 401 with invalid JWT token."""
    response = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "Jane", "email": "jane@example.com"},
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401
```

### Test 2: Validation

```python
def test_create_candidate_invalid_email():
    """Should return 400 with invalid email format."""
    response = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "Jane", "email": "not-an-email"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code == 422  # FastAPI validation error
    assert "email" in str(response.json())
```

### Test 3: Tenant Isolation

```python
def test_candidate_not_visible_across_tenants():
    """Should return 404 if candidate in different tenant."""
    # Create candidate in tenant1
    response1 = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "Jane", "email": "jane@example.com"},
        headers={"Authorization": f"Bearer {tenant1_token}"}
    )
    candidate_id = response1.json()["id"]
    
    # Try to access from tenant2
    response2 = client.get(
        f"/api/v1/candidates/{candidate_id}",
        headers={"Authorization": f"Bearer {tenant2_token}"}
    )
    assert response2.status_code == 404  # Not found (not "403 forbidden")
```

### Test 4: Permission

```python
def test_create_candidate_without_permission():
    """Should return 403 if user lacks candidate.create permission."""
    # Create user without candidate.create permission
    user = create_test_user(roles=["employee"])  # No recruiter role
    token = create_jwt_token(user)
    
    response = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "Jane", "email": "jane@example.com"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert "candidate.create" in response.json()["message"]
```

### Test 5: Duplicate Detection

```python
def test_create_duplicate_candidate():
    """Should return 409 if candidate email already exists."""
    # Create first candidate
    response1 = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "Jane", "email": "jane@example.com"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response1.status_code == 201
    
    # Try to create duplicate
    response2 = client.post(
        "/api/v1/candidates/add",
        json={"first_name": "John", "email": "jane@example.com"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response2.status_code == 409
    assert "already exists" in response2.json()["message"]
```

---

## HTTP Status Code Cheat Sheet

| Code | When to Use | Example |
|------|-------------|---------|
| 200 | GET successful | `GET /candidates/123` ✅ returns candidate |
| 201 | POST successful | `POST /candidates/add` ✅ creates candidate |
| 204 | DELETE successful | `DELETE /candidates/123` ✅ no response body |
| 400 | Input validation failed | Email format invalid, required field missing |
| 401 | Missing/invalid JWT token | `Authorization` header missing or token expired |
| 403 | Valid JWT but insufficient permission | User lacks `candidate.create` permission |
| 404 | Resource not found (or tenant isolation) | Candidate doesn't exist in user's tenant |
| 409 | Conflict with existing state | Duplicate email, wrong status, circular dependency |
| 422 | Schema validation error | FastAPI automatic (wrong data type) |
| 429 | Rate limit exceeded | Too many requests in 60 second window |
| 500 | Unhandled server error | Database crash, unexpected exception |

---

## Common Mistakes & Fixes

### ❌ WRONG: Raw SQL Insert
```python
# DON'T DO THIS
db.execute("INSERT INTO candidates (email, ...) VALUES (?)")
```

### ✅ RIGHT: Safe Factory
```python
# DO THIS
candidate = createCandidateSafe(db, tenant_id, request)
```

---

### ❌ WRONG: Missing Tenant Check
```python
# DON'T DO THIS
candidate = db.query(Candidate).filter_by(id=id).first()
```

### ✅ RIGHT: Include Tenant Filter
```python
# DO THIS
candidate = db.query(Candidate).filter_by(
    id=id,
    tenant_id=current_user.tenant_id
).first()
```

---

### ❌ WRONG: Leak Resource Existence
```python
# DON'T DO THIS - leaks that resource exists in another tenant
if candidate.tenant_id != current_user.tenant_id:
    raise HTTPException(403, "Forbidden")  # 403 reveals it exists
```

### ✅ RIGHT: Hide Existence
```python
# DO THIS - 404 hides whether resource exists
if not candidate or candidate.tenant_id != current_user.tenant_id:
    raise HTTPException(404, "Not found")
```

---

### ❌ WRONG: No Schema Validation
```python
# DON'T DO THIS
@router.post("/candidates")
def create_candidate(req: dict):
    pass
```

### ✅ RIGHT: Pydantic Schema
```python
# DO THIS
class CreateCandidateRequest(BaseModel):
    email: EmailStr
    phone: str
    
@router.post("/candidates")
def create_candidate(req: CreateCandidateRequest):
    pass
```

---

### ❌ WRONG: Exposing Implementation Details
```python
# DON'T DO THIS
except Exception as e:
    raise HTTPException(500, f"Database error: {str(e)}")  # Leaks internals
```

### ✅ RIGHT: Generic Error Messages
```python
# DO THIS
except Exception as e:
    logger.error(f"Unexpected error: {e}")  # Log it
    raise HTTPException(500, "Internal server error")  # Generic message
```

---

## Deployment Checklist

```
[ ] JWT_PUBLIC_KEY and JWT_PRIVATE_KEY set in production
[ ] DATABASE_URL points to production database
[ ] DEBUG=false in production environment
[ ] CORS_ORIGINS updated for production domain
[ ] Rate limiting configured (500/60s or higher)
[ ] Error logging verified (logs to error_log table)
[ ] Security events logging (audit trail)
[ ] Health check tested: curl http://localhost:8080/health
[ ] API docs disabled (DEBUG=false hides /docs and /redoc)
[ ] SSL/TLS certificate configured
[ ] Database backups configured
[ ] Monitoring and alerting configured
```

---

## Performance Tips

### Tip 1: Use Pagination
```python
# Bad: Loads ALL 100K candidates
candidates = db.query(Candidate).all()

# Good: Paginate (50 per page)
candidates = db.query(Candidate).limit(50).offset(0).all()
```

### Tip 2: Eager Load Relationships
```python
# Bad: N+1 query (1 + len(candidates) queries)
candidates = db.query(Candidate).all()
for c in candidates:
    print(c.job.title)  # Query for EACH candidate

# Good: Eager load (1 query)
from sqlalchemy.orm import joinedload
candidates = db.query(Candidate)\
    .options(joinedload(Candidate.job))\
    .all()
```

### Tip 3: Index Frequently Queried Columns
```python
# In migration or model:
class Candidate(Base):
    email: str = Column(String, index=True, unique=True)
    tenant_id: str = Column(String, index=True)
    status: str = Column(String, index=True)
```

### Tip 4: Cache Static Data
```python
# Bad: Query database on every request
roles = db.query(Role).all()

# Good: Cache in memory (refresh on deploy)
@cache.cached(timeout=3600)
def get_roles():
    return db.query(Role).all()
```

---

## Debug Tips

### Tip 1: Print Request/Response
```python
import json
print(f"Request: {json.dumps(request.json(), indent=2)}")
print(f"User: {current_user.id} (tenant: {current_user.tenant_id})")
print(f"Permission: {current_user.has_permission('candidate.create')}")
```

### Tip 2: Check Database State
```bash
# Connect to local database
sqlite3 wros.db

# Check candidate exists
SELECT * FROM candidates WHERE email = 'jane@example.com';

# Check user roles
SELECT u.id, r.name FROM user_roles u JOIN roles r ON u.role_id = r.id;

# Check tenant
SELECT * FROM business_units;
```

### Tip 3: Decode JWT Token
```python
import jwt
from app.core.config import settings

token = "eyJ0..."
payload = jwt.decode(
    token,
    settings.JWT_PUBLIC_KEY,
    algorithms=["RS256"]
)
print(f"User ID: {payload['sub']}")
print(f"Tenant ID: {payload['tenant_id']}")
print(f"Roles: {payload['roles']}")
```

### Tip 4: Enable Request Logging
```python
# In app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)

# See all SQL queries
export SQLALCHEMY_ECHO=1
```

---

## FAQ

**Q: How do I add a new endpoint?**
A: Create router in `endpoints/newfeature.py`, import in `routes_master.py`, add to `create_master_router()`

**Q: How do I change permission requirements?**
A: Update permission in endpoint's `Depends()` or route definition

**Q: How do I test without auth?**
A: Use public routes or generate valid JWT token in tests

**Q: Why 404 instead of 403 for tenant isolation?**
A: 404 hides existence, 403 reveals resource exists in another tenant

**Q: How do I paginate results?**
A: Use `limit` and `offset` parameters: `?limit=50&offset=0`

**Q: How do I handle file uploads?**
A: Use `UploadFile` in schema, validate size and format

**Q: How do I implement soft delete?**
A: Add `deleted_at` timestamp column, filter where `deleted_at IS NULL`

**Q: How do I implement audit trail?**
A: Log all changes to `audit_log` table with user_id, timestamp, old_value, new_value

---

**Version**: 1.0  
**Last Updated**: 2026-08-15  
**For Help**: See `API_ROUTES_INTEGRATION_GUIDE.md`
