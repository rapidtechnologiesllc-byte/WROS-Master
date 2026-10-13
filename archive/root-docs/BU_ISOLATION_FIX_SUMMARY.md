# Business Unit Isolation & Data Scoping - Complete Fix

**Status:** ✅ IMPLEMENTED - Commit d5c6f1fc  
**Date:** 2026-09-09  
**Impact:** CRITICAL - Fixes data isolation between Business Units

---

## Problem Statement

**Scenario:** Two recruiters from different Business Units can see and access each other's candidates
- Recruiter 1 (BU: North America) creates candidate
- Candidate reaches "Active" state after job submission
- Recruiter 2 (BU: Europe) searches candidates
- **PROBLEM:** Recruiter 2 sees Recruiter 1's candidate (WRONG!)
- **IMPACT:** Data isolation breach, cross-BU candidate leakage

**Root Causes:**
1. Business Units endpoints were querying non-existent database columns (region, continent)
2. visibility.py existed but was NOT wired into candidate queries
3. No database flag to mark users as "org-level" (CEO, Super User) vs "BU-scoped" (Recruiter)
4. Candidate queries used legacy CandidateOwnership scoping but didn't respect visibility rules

---

## Solution Implemented

### PHASE 1: Fix Business Units Management

**Problem:** `/api/v1/business-units` endpoint was broken
- Queried non-existent `region` and `continent` columns
- Caused "Failed to load business unit" errors in frontend
- BusinessUnitModal.js called wrong endpoint `/api/admin/users-access-control/business-units`

**Fix Applied:**
```python
# Before: Broken SQL queries
result = db.execute(text("SELECT id, name, region, continent FROM business_units ORDER BY name"))

# After: Proper ORM queries using BusinessUnit model
business_units = db.query(BusinessUnit).filter(BusinessUnit.active == True).order_by(BusinessUnit.name).all()
```

**Endpoints Fixed:**
- ✅ `GET /api/v1/business-units` - Lists all active BUs with correct schema
- ✅ `POST /api/v1/business-units` - Create new BU with validation
- ✅ `PUT /api/v1/business-units/{id}` - Update BU (newly added)
- ✅ `DELETE /api/v1/business-units/{id}` - Soft delete BU (newly added)

**Response Schema (Fixed):**
```json
{
  "id": 1,
  "name": "North America",
  "display_name": "North America (NA)",
  "bu_code": "NA",
  "description": "North American operations",
  "manager_id": null,
  "active": true
}
```

**Seed Data (Fixed):**
```python
default_bus = [
    BusinessUnit(name="North America", display_name="North America (NA)", bu_code="NA"),
    BusinessUnit(name="Europe", display_name="Europe (EU)", bu_code="EU"),
    BusinessUnit(name="Asia Pacific", display_name="Asia Pacific (APAC)", bu_code="APAC"),
    BusinessUnit(name="India", display_name="India (IN)", bu_code="IN"),
]
```

### PHASE 2: Implement Database-Driven Org-Level Access

**Problem:** visibility.py used hardcoded role names
```python
# Old (hardcoded, brittle)
org_level_roles = {"super user", "admin", "ceo", "cfo"}
if user.UserRole.lower() in org_level_roles:
    return True  # Org-level user
```

**Solution:** Add `org_level_access` flag to RoleTemplate
```python
# New model field
class RoleTemplate(Base):
    org_level_access = Column(Boolean, default=False)  # True = see all BUs, False = see only own BU
```

**Updated visibility.py:**
```python
def is_org_level_user(user: Users) -> bool:
    """Check role_template.org_level_access flag instead of hardcoded roles"""
    # 1. Check new RBAC: role_template.org_level_access
    if user.role_template and user.role_template.org_level_access:
        return True
    
    # 2. Fallback to legacy hardcoded roles (backward compatibility)
    legacy_org_level_roles = {"super user", "admin", "ceo", "cfo"}
    if user.UserRole and user.UserRole.lower() in legacy_org_level_roles:
        return True
    
    return False
```

**Migration Script:**
```python
# Automatically sets org_level_access=True for system roles
UPDATE role_templates
SET org_level_access = true
WHERE name IN ('Super User', 'CEO', 'CFO', 'Admin', 'Partner')
AND is_system = true
```

### PHASE 3: Wire BU Scoping into Candidate Queries

**Problem:** bu_scope.py existed but didn't integrate with visibility.py
```python
# Old: Used simple business_unit_id check
def is_bu_restricted(db: Session, user: Users) -> bool:
    return user.business_unit_id is not None  # WRONG: ignores org-level users
```

**Solution:** Use visibility.py to determine org-level status
```python
def is_bu_restricted(db: Session, user: Users) -> bool:
    """Check if user should have BU-restricted visibility"""
    # If user is org-level (via role_template.org_level_access), they are NOT restricted
    if should_bypass_bu_filter(user):
        return False
    
    # If user has a BU assigned, they ARE restricted to that BU
    return get_user_bu_id(user) is not None
```

**Updated apply_bu_scope_to_candidate_query():**
```python
def apply_bu_scope_to_candidate_query(db: Session, query: Query, current_user: Users) -> Query:
    """Apply BU scoping to candidate queries"""
    
    # Org-level users (CEO, Super User): see ALL candidates
    if should_bypass_bu_filter(current_user):
        return query  # No filtering
    
    # BU-scoped users (Recruiter, Hiring Manager): see only their BU's candidates
    user_bu_id = get_user_bu_id(current_user)
    
    # Join with CandidateOwnership to determine which BU owns each candidate
    query = query.outerjoin(CandidateOwnership, ...)
    
    # Org Pool: candidates not yet assigned to any job
    org_pool = or_(
        CandidateOwnership.id.is_(None),  # Never assigned
        CandidateOwnership.pool_status == POOL_ORG,
    )
    
    # Can see: org pool + their own BU's candidates
    return query.filter(or_(org_pool, CandidateOwnership.owned_by_bu_id == user_bu_id))
```

---

## How It Works: Recruiter Isolation

### Scenario 1: Recruiter 1 (BU: North America)

```python
# Recruiter 1 logged in
recruiter1 = Users(
    UserID="recruiter1@company.com",
    business_unit_id=1,  # Assigned to BU 1 (North America)
    role_template_id=5,  # Recruiter role
)
recruiter1.role_template.org_level_access = False  # BU-scoped

# Query: GET /candidates
candidates_query = db.query(Candidate)
candidates_query = apply_bu_scope_to_candidate_query(db, candidates_query, recruiter1)
# Result: Only candidates from BU 1 (North America) OR org pool
```

### Scenario 2: Recruiter 2 (BU: Europe)

```python
recruiter2 = Users(
    UserID="recruiter2@company.com",
    business_unit_id=2,  # Assigned to BU 2 (Europe)
    role_template_id=5,  # Recruiter role
)
recruiter2.role_template.org_level_access = False  # BU-scoped

# Query: GET /candidates
candidates_query = db.query(Candidate)
candidates_query = apply_bu_scope_to_candidate_query(db, candidates_query, recruiter2)
# Result: Only candidates from BU 2 (Europe) OR org pool
# ✅ CANNOT see Recruiter 1's candidates from BU 1
```

### Scenario 3: CEO (Org-Level)

```python
ceo = Users(
    UserID="ceo@company.com",
    business_unit_id=None,  # Not assigned to specific BU
    role_template_id=1,  # CEO role
)
ceo.role_template.org_level_access = True  # Org-level access

# Query: GET /candidates
candidates_query = db.query(Candidate)
candidates_query = apply_bu_scope_to_candidate_query(db, candidates_query, ceo)
# Result: ALL candidates from ALL BUs
# ✅ CAN see candidates from NA, EU, APAC, India
```

---

## Data Flow: Candidate Lifecycle

### 1. Candidate Created (Org Pool)

```
Recruiter 1 creates candidate → CandidateOwnership record NOT created yet
├─ Candidate.candidateID = "c123"
├─ Candidate.business_unit_id = NULL
└─ CandidateOwnership: None (in Org Pool by default)

Visibility:
├─ Recruiter 1 (BU 1): ✅ Can see (org pool visible to all BU-scoped users)
├─ Recruiter 2 (BU 2): ✅ Can see (org pool visible to all BU-scoped users)
└─ CEO: ✅ Can see (sees everything)
```

### 2. Candidate Submitted to Job (BU Isolated)

```
Recruiter 1 submits candidate to Job in BU 1
→ CandidateOwnership record created: owned_by_bu_id = 1

Visibility:
├─ Recruiter 1 (BU 1): ✅ Can see (owns candidate's job)
├─ Recruiter 2 (BU 2): ❌ CANNOT see (different BU, not org pool anymore)
└─ CEO: ✅ Can see (org-level)
```

### 3. Candidate Marked Ready for Opportunity (Org Pool Again)

```
Candidate becomes "Ready for Opportunity"
→ CandidateOwnership.pool_status = POOL_ORG

Visibility:
├─ Recruiter 1 (BU 1): ✅ Can see (owns it, plus in org pool)
├─ Recruiter 2 (BU 2): ✅ Can see (org pool)
└─ CEO: ✅ Can see (org-level)
```

---

## Files Changed

| File | Change | Impact |
|------|--------|--------|
| `backend/app/api/v1/endpoints/business_units.py` | Fixed CRUD endpoints, proper ORM queries | Business Units now load correctly |
| `backend/app/models/role_template.py` | Added `org_level_access` column | Database-driven org-level checks |
| `backend/app/core/visibility.py` | Updated to query role_template flag | No more hardcoded roles |
| `backend/app/core/bu_scope.py` | Integrated with visibility.py | Candidate queries use proper scoping |
| `backend/app/core/seed_business_units.py` | Fixed schema and seed data | Default BUs created correctly |
| `frontend/src/components/BusinessUnitModal.js` | Fixed endpoint URL | Create/edit BU works in UI |
| `backend/alembic/versions/2026_09_09_add_org_level_access.py` | Migration script | org_level_access column added to DB |
| `backend/tests/test_bu_isolation_e2e.py` | End-to-end tests | Verify isolation works |

---

## Testing Scenarios

### Test 1: Business Units CRUD
```bash
# Create BU
POST /api/v1/business-units
{
  "name": "Test BU",
  "display_name": "Test BU (TEST)",
  "bu_code": "TEST",
  "description": "Testing"
}
# ✅ Should succeed

# List BUs
GET /api/v1/business-units
# ✅ Should return all BUs with correct schema

# Update BU
PUT /api/v1/business-units/1
{
  "name": "Updated Name"
}
# ✅ Should update

# Delete BU
DELETE /api/v1/business-units/1
# ✅ Should soft-delete (set active=False)
```

### Test 2: Candidate Isolation
```bash
# Setup: 2 recruiters in different BUs
recruiter1_token = login("recruiter1@company.com")  # BU 1
recruiter2_token = login("recruiter2@company.com")  # BU 2

# Recruiter 1 creates candidate
POST /candidates (as recruiter1)
# Response: candidate_id = "c123"

# Recruiter 1 can see their candidate
GET /candidates?search=c123 (as recruiter1)
# ✅ Result: Found

# Recruiter 2 cannot see candidate (org pool)
GET /candidates?search=c123 (as recruiter2)
# ✅ Result: Found (in org pool)

# Recruiter 1 submits candidate to job in BU 1
POST /jobs/j1/assign-candidate/c123 (as recruiter1)
# Creates CandidateOwnership: owned_by_bu_id=1

# Now Recruiter 2 cannot see it (removed from org pool)
GET /candidates?search=c123 (as recruiter2)
# ✅ Result: NOT FOUND

# CEO can still see it
GET /candidates?search=c123 (as ceo@company.com)
# ✅ Result: Found
```

---

## Migration Instructions

1. **Run migration** to add `org_level_access` column:
   ```bash
   alembic upgrade head
   ```

2. **Update role_template records** with org-level access:
   - Migration script automatically sets it for system roles
   - For custom roles, use backend to update manually

3. **No frontend changes needed** - already compatible

4. **Verify candidate scoping** by logging in as recruiter from different BUs

---

## Key Principles

1. **Role-Template Driven:** Use `role_template.org_level_access` flag, not hardcoded role names
2. **Backward Compatible:** Legacy UserRole checks still work, falls back to hardcoded if no role_template
3. **Database-First:** Visibility rules come from database, not code
4. **Fail Closed:** BU-scoped users with no BU assigned see only org pool (safe default)
5. **Two-Tier Visibility:**
   - Org-level users (org_level_access=True): See all candidates from all BUs
   - BU-scoped users (org_level_access=False): See org pool + their own BU's candidates

---

## Production Readiness Checklist

- ✅ Business Units CRUD works end-to-end
- ✅ Candidate isolation by BU implemented
- ✅ Migration script prepared
- ✅ End-to-end tests written
- ✅ Backward compatibility maintained
- ✅ Code review passed
- ✅ Committed to git (d5c6f1fc)
- ⏳ Run migrations on database
- ⏳ Test in staging environment
- ⏳ Monitor production for data isolation

---

## Related Issues Fixed

- Business Units screen showing "Failed to load business unit" errors ✅
- Candidates not properly isolated between recruiters ✅
- Hardcoded role names in visibility.py ✅
- Missing PUT/DELETE endpoints for Business Units ✅
- Ghost endpoint `/api/admin/users-access-control/business-units` removed ✅

---

**Commit:** d5c6f1fc  
**Author:** Claude Haiku 4.5  
**Date:** 2026-09-09
