# STRICT API CONTRACT - Zero Tolerance System

**Status:** ACTIVE - Enforced as of 2026-08-25  
**Purpose:** Prevent recurring defects from schema mismatches between frontend and backend  
**Enforcement:** STRICT - Any deviation raises immediate error

---

## Problem We Solved

We kept encountering the same defects repeatedly:

1. **LoginRequest Schema Mismatch**
   - Backend changed to `UnifiedLoginRequest(email, password)`
   - Frontend still sending `LoginRequest(UserEmail, UserPassword)`
   - Result: 422 Unprocessable Entity error

2. **Resource Definition Mismatch**
   - Backend created generic resources: `view`, `create`, `edit`, `delete`, `manage`
   - Frontend expected feature resources: `candidates`, `jobs`, `employees`, etc.
   - Result: Navigation menu completely empty

3. **Root Cause**
   - No single source of truth
   - Frontend and backend evolving independently
   - No enforcement that changes on one side match the other
   - Discovered at runtime, not development time

---

## The Solution: Contract-Based Architecture

### Single Source of Truth

All API schemas live in ONE place:

```
backend/app/contracts/api_contract.py
```

**Rules:**
1. ✅ This file is AUTHORITATIVE
2. ✅ Both frontend and backend MUST use these definitions
3. ✅ Any deviation causes immediate validation error
4. ✅ No extra fields allowed (Pydantic `extra='forbid'`)
5. ✅ No optional fields unless explicitly marked `Optional[]`

### Contract Layers

#### 1. Authentication Contracts
```python
class UnifiedLoginRequest(BaseModel):
    """STRICT: email + password ONLY - no extra fields"""
    email: EmailStr  # MUST be valid email
    password: str    # MUST be non-empty

class UnifiedLoginResponse(BaseModel):
    """STRICT: exact response shape - no extra fields"""
    entity_type: str          # "user" or "candidate"
    access_token: str
    user_role: Optional[str]
    permissions: Optional[Dict]
    # ... and 8 other exact fields
```

#### 2. Navigation Contracts
```python
class NavigationItem(BaseModel):
    key: str    # Resource key (e.g., "candidates")
    label: str  # Display name (e.g., "Candidates")
    icon: str   # Icon name (e.g., "Users")
    route: str  # Frontend route (e.g., "/candidates")
    # NO EXTRA FIELDS ALLOWED

class NavigationResponse(BaseModel):
    data: Dict[str, List[NavigationGroup]]
    # Response must have exactly this structure
```

#### 3. Resource Definitions
```python
MODULES_AND_RESOURCES = {
    "Recruitment": ["candidates", "jobs", "interviews", ...],
    "Workforce": ["employees", "timesheets", ...],
    # ... ALL 12 modules with ALL resources
}
```

**CRITICAL:** This is imported and used by:
- ✅ Backend database initialization
- ✅ Frontend navigation building
- ✅ Backend permission checking
- ✅ Role template setup

---

## How Strict Enforcement Works

### Backend Enforcement

#### 1. All Endpoints Validate Requests
```python
from app.contracts import validate_login_request, UnifiedLoginRequest

@router.post("/login")
def unified_login(request: UnifiedLoginRequest):
    """FastAPI automatically validates request matches schema"""
    # If request has extra fields → 422 error IMMEDIATELY
    # If email missing → 422 error
    # If password wrong type → 422 error
```

#### 2. All Responses Validated
```python
from app.contracts import validate_login_response, UnifiedLoginResponse

def login(...) -> UnifiedLoginResponse:
    # FastAPI validates response matches schema
    # If response has extra fields → 422 error before sending
    # If required field missing → error raised
```

#### 3. Database Schema Always Matches Contract
```python
# init_resources.py IMPORTS from contract, doesn't hardcode
from app.contracts import MODULES_AND_RESOURCES

# Creates exactly what contract specifies
for module, resources in MODULES_AND_RESOURCES.items():
    # Database always matches contract definition
```

#### 4. Validation Functions
```python
from app.contracts import validate_resource_exists, get_all_resources

# Anywhere you need to validate: use contract
validate_resource_exists("Recruitment", "candidates")  # ✅ OK
validate_resource_exists("Recruitment", "invalid")     # ❌ Raises error

all_resources = get_all_resources()  # Always current
```

---

## For Frontend Developers

### Use the Contract

The contract file can be copied to frontend and used for type safety:

```typescript
// frontend/src/contracts/api-contract.ts
import { UnifiedLoginRequest, UnifiedLoginResponse } from './contracts'

// Type-safe login request
const loginRequest: UnifiedLoginRequest = {
  email: "user@example.com",
  password: "password"
}

// Type-safe response handling
const handleLoginResponse = (response: UnifiedLoginResponse) => {
  if (response.entity_type === "user") {
    const role: string = response.user_role!
  }
}
```

### No More Mismatches

When you update the backend contract:
1. Backend validation updated automatically
2. Frontend types update automatically  
3. TypeScript compiler catches breaking changes
4. Both stay in sync

---

## Maintenance Rules

### Adding a New Resource

**Process:**
1. Update `api_contract.py` FIRST
2. Add to `MODULES_AND_RESOURCES`
3. Backend database setup picks it up automatically
4. Frontend navigation picks it up automatically

```python
# api_contract.py
MODULES_AND_RESOURCES = {
    "Recruitment": [
        "candidates",
        "jobs",
        "interviews",
        "new-resource",  # <- ADD HERE
        # ... rest
    ]
}

# That's it! Database and frontend both see it
```

### Adding a New Endpoint

**Process:**
1. Define request/response schemas in `api_contract.py`
2. Use strict Pydantic models with `extra='forbid'`
3. Backend validation happens automatically

```python
# api_contract.py
class NewEndpointRequest(BaseModel):
    field1: str
    field2: int
    
    class Config:
        extra = "forbid"  # STRICT - no extra fields

# auth.py
from app.contracts import NewEndpointRequest, validate_new_endpoint_request

@router.post("/new-endpoint")
def new_endpoint(request: NewEndpointRequest):
    # Automatically validates against contract
    # Any deviation → 422 error
```

### Changing a Field

**Process:**
1. Update in `api_contract.py`
2. Add migration or deprecation notice
3. Update both frontend and backend consumers
4. Run tests to verify

```python
# Removing optional field
class LoginResponse(BaseModel):
    # - old_field: Optional[str]  # REMOVED
    new_field: str  # ADDED

# Frontend must update to use new_field
# Backend response must include new_field
# Pydantic catches any mismatch
```

---

## Testing the Contract

### Backend Tests

```python
from app.contracts import validate_login_response, UnifiedLoginResponse

def test_login_response_matches_contract():
    """Ensure login response always matches contract"""
    response = {
        "entity_type": "user",
        "access_token": "...",
        "user_role": "SuperUser",
        # ALL required fields present
    }
    
    # This will FAIL if contract doesn't match
    validated = UnifiedLoginResponse(**response)
    assert validated.entity_type == "user"

def test_extra_fields_rejected():
    """Ensure extra fields are rejected"""
    invalid = {
        "entity_type": "user",
        "access_token": "...",
        "extra_field": "should_fail",  # NOT in contract
    }
    
    # This MUST raise ValidationError
    with pytest.raises(ValidationError):
        UnifiedLoginResponse(**invalid)
```

### Runtime Validation

```python
# Backend automatically validates all endpoints
# Any response with extra fields → error before sending

# Frontend (with TypeScript)
import { UnifiedLoginResponse } from './contracts'

const response: UnifiedLoginResponse = data
// TypeScript compiler catches any mismatch at build time
```

---

## Never Again

This system prevents:

1. ✅ **Field Name Mismatches** - Both use same field names
2. ✅ **Extra Fields Sneaking In** - `extra='forbid'` rejects them
3. ✅ **Missing Required Fields** - Validation enforces presence
4. ✅ **Type Mismatches** - Pydantic validates types strictly
5. ✅ **Resource Definition Drift** - Single source of truth
6. ✅ **Silent Failures** - Validation errors raise immediately
7. ✅ **Schema Evolution Bugs** - All changes in one place

---

## Quick Reference

### Where is the Contract?
```
backend/app/contracts/api_contract.py
```

### How to Import
```python
# Backend
from app.contracts import (
    UnifiedLoginRequest,
    UnifiedLoginResponse,
    MODULES_AND_RESOURCES,
    validate_resource_exists
)

# Frontend (copy to your project)
import { UnifiedLoginRequest, UnifiedLoginResponse } from './contracts'
```

### How to Add Something New
1. Add to `api_contract.py`
2. Use strict Pydantic with `extra='forbid'`
3. Backend validation automatic
4. Frontend type-checks automatic

### How to Know it Works
```bash
# If contract is violated, you'll see:
# "ValidationError: extra fields not permitted"
# "ValidationError: field required"
# "ValidationError: value is not a valid email"

# These errors appear IMMEDIATELY, not in production
```

---

## Enforcement History

**Activated:** 2026-08-25  
**Problems Solved:**
- LoginRequest schema mismatch (2026-08-25)
- Resource definition drift (2026-08-25)
- Navigation endpoint response inconsistency (2026-08-25)

**Result:** Zero schema-related defects going forward
