# PHASE 2: BACKEND ZERO-HARDCODING REWRITE
## Implementation Specification

**Phase Duration:** 2-3 weeks  
**Objective:** Eliminate all hardcoded roles/permissions, implement database-driven architecture  
**Success Criteria:** Zero hardcoded role names, permission strings, or access logic in code

---

## DELIVERABLES

### 1. Organization Service (New Microservice)

**Purpose:** Single source of truth for organizational hierarchy

**Endpoints:**

```
GET /api/organization/employees/{employee_id}
└─ Returns: employee details with hierarchy info
   ├─ id, name, email
   ├─ manager_id (FK to another employee)
   ├─ bu_id, location_id
   ├─ department_id, level
   └─ all_subordinates (recursive query result)

GET /api/organization/hierarchy/{employee_id}
└─ Returns: complete reporting tree
   ├─ direct_reports: []
   ├─ all_subordinates: []
   └─ chain_to_ceo: []

GET /api/organization/business-units/{bu_id}
└─ Returns: BU details
   ├─ id, name, location_id
   ├─ partner_id, bu_head_id
   └─ all_employees: []

GET /api/organization/locations
└─ Returns: all locations (countries)
   ├─ id, country_name
   └─ business_units: []
```

**Database Queries:**

```sql
-- Get employee with all hierarchy info
SELECT e.*, 
       m.name as manager_name,
       bu.name as bu_name,
       loc.country_name
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id
LEFT JOIN business_units bu ON e.bu_id = bu.id
LEFT JOIN locations loc ON e.location_id = loc.id
WHERE e.tenant_id = ? AND e.id = ?;

-- Get all subordinates recursively
WITH RECURSIVE subordinates AS (
  SELECT id, manager_id, 1 as level
  FROM employees
  WHERE manager_id = ? AND tenant_id = ?
  
  UNION ALL
  
  SELECT e.id, e.manager_id, s.level + 1
  FROM employees e
  INNER JOIN subordinates s ON e.manager_id = s.id
  WHERE e.tenant_id = ?
)
SELECT * FROM subordinates;
```

**Implementation Files:**
- `app/services/organization_service.py` - Business logic
- `app/api/v1/endpoints/organization.py` - REST endpoints
- Database migrations for org structure validation

---

### 2. Dynamic Permission System (Core RBAC Rewrite)

**Purpose:** All permissions come from database role_templates, zero hardcoding

**Files to Rewrite:**

#### `app/core/dependencies.py` (CRITICAL)
**Current State:** Hardcoded role checks everywhere
**Target State:** Query database for permissions

**Before:**
```python
# Line 265 - WRONG
is_super_user = (
    (user.UserRole and user.UserRole.lower() in ("super user", "admin"))
    or (user.role and user.role.name and user.role.name.lower() in ("super user", "admin"))
)
```

**After:**
```python
# Query database
def get_user_permissions(user_id: str, db: Session) -> set:
    """Get all permissions for user via role_templates"""
    user_roles = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.tenant_id == current_tenant_id
    ).all()
    
    permissions = set()
    for user_role in user_roles:
        template_accesses = db.query(RoleTemplateModuleAccess).filter(
            RoleTemplateModuleAccess.role_template_id == user_role.role_template_id
        ).all()
        
        for access in template_accesses:
            module = access.module
            permissions.add(f"{module.name}.{access.access_level}")
    
    return permissions

def is_super_user(user_id: str, db: Session) -> bool:
    """Check if user has admin permissions via role template"""
    permissions = get_user_permissions(user_id, db)
    return any(perm.startswith("admin.") for perm in permissions)
```

**Scope:**
- Remove all hardcoded role name checks
- Remove all hardcoded permission string checks
- Implement database queries for all access control
- Apply cascading hierarchy rules

---

#### `app/services/permission_helper.py` (NEW)
**Purpose:** Centralized permission checking utilities

**Functions:**

```python
def get_user_permissions(user_id: str, db: Session) -> Set[str]:
    """Get flattened permission set for user"""
    # Query role_templates, role_template_module_access
    # Return: {'recruitment.manage', 'project.view', ...}

def has_permission(user_id: str, permission: str, db: Session) -> bool:
    """Check if user has specific permission"""
    # Split permission: resource.action
    # Query database
    # Return: True/False

def get_accessible_modules(user_id: str, db: Session) -> List[Module]:
    """Get list of modules user can access"""
    # Query role_template_module_access for user's roles
    # Return: [Module1, Module2, ...]

def get_data_access_scope(user_id: str, db: Session) -> DataScope:
    """Get user's data access scope (BU, Location, Hierarchy)"""
    # Get employee info from Organization Service
    # Calculate accessible BUs, locations, subordinates
    # Return: DataScope object

def get_user_subordinates(user_id: str, db: Session) -> List[str]:
    """Get all subordinates in reporting chain (recursive)"""
    # Query employees.manager_id recursively
    # Return: [emp_id1, emp_id2, ...]
```

---

#### `app/services/rbac_service.py` (REWRITE)
**Purpose:** Dynamic RBAC with role template database lookups

**Current:** Hardcoded role/permission arrays  
**Target:** Database queries only

```python
class RBACService:
    def has_permission(self, user_id: str, resource: str, action: str) -> bool:
        """
        Check if user has permission via role templates.
        
        Query pattern:
        1. Get user's role_templates via user_roles junction
        2. Get role's module_accesses via role_template_module_access
        3. Check if resource.action is in permissions
        4. Apply data scope filters (BU, Location, Hierarchy)
        """
        user_roles = self.db.query(UserRole).filter(
            UserRole.user_id == user_id
        ).all()
        
        for user_role in user_roles:
            accesses = self.db.query(RoleTemplateModuleAccess).filter(
                RoleTemplateModuleAccess.role_template_id == user_role.role_template_id
            ).all()
            
            for access in accesses:
                if f"{access.module.name}.{action}" == f"{resource}.{action}":
                    # Check data scope
                    return self.check_data_scope(user_id, access.data_scope)
        
        return False
```

---

#### `app/api/v1/endpoints/role_based_dashboard.py` (REWRITE)
**Current:** Hardcoded role checks (lines 60, 92, 124, 156)  
**Target:** Permission-based routing

**Before:**
```python
# WRONG - Line 60
if current_user.UserRole not in ["Super User", "Admin", "CEO"]:
    raise HTTPException(403, "CEO dashboard access denied")
```

**After:**
```python
# RIGHT
permissions = get_user_permissions(current_user.id, db)

if not any(perm.startswith("revenue.view") for perm in permissions):
    raise HTTPException(403, "Access denied")

# Route based on permissions
if "revenue.view_pnl" in permissions:
    return get_executive_dashboard(current_user, db)
elif "recruitment.manage" in permissions:
    return get_recruitment_dashboard(current_user, db)
else:
    return get_basic_dashboard(current_user, db)
```

---

### 3. Candidate Isolation Logic (New Feature)

**Purpose:** Implement candidate locking to BU after submission

**Files:**
- `app/models/candidate.py` - Add `associated_bu_id` column
- `app/services/candidate_service.py` - New isolation logic
- `app/api/v1/endpoints/candidates.py` - Query filtering

**Database Changes:**

```sql
ALTER TABLE candidates 
ADD COLUMN associated_bu_id UUID REFERENCES business_units(id);

-- Index for performance
CREATE INDEX idx_candidates_associated_bu ON candidates(associated_bu_id);
CREATE INDEX idx_candidates_unassociated ON candidates(associated_bu_id) 
  WHERE associated_bu_id IS NULL;
```

**Candidate Service Logic:**

```python
def get_recruitment_candidates(recruiter_id: str, db: Session):
    """
    Recruiter sees:
    1. All unassociated candidates (global pool)
    2. All candidates associated with their BU
    """
    recruiter = get_organization_employee(recruiter_id)
    
    # Unassociated (global pool)
    unassociated = db.query(Candidate).filter(
        Candidate.tenant_id == recruiter.tenant_id,
        Candidate.associated_bu_id == None,
        Candidate.status.in_(['sourced', 'screening', 'qualified'])
    ).all()
    
    # BU-associated
    bu_associated = db.query(Candidate).filter(
        Candidate.tenant_id == recruiter.tenant_id,
        Candidate.associated_bu_id == recruiter.bu_id
    ).all()
    
    return unassociated + bu_associated

def submit_candidate_to_job(candidate_id: str, job_id: str, db: Session):
    """When candidate submitted to job, lock them to job's BU"""
    job = db.query(Job).filter(Job.id == job_id).first()
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    # Lock candidate to BU
    if candidate.associated_bu_id is None:
        candidate.associated_bu_id = job.bu_id
        db.commit()
    elif candidate.associated_bu_id != job.bu_id:
        # Candidate already locked to different BU
        raise ValueError(f"Candidate locked to BU {candidate.associated_bu_id}, cannot submit to {job.bu_id}")
```

---

### 4. Query-Time Data Filtering (Everywhere)

**Pattern:** All queries include WHERE clauses for:
- `tenant_id`
- `associated_bu_id` or `bu_id` (if recruited)
- `location_id` (if not cross-location)
- Manager hierarchy (if not global role)

**Example Endpoints:**

```python
@router.get("/candidates")
async def list_candidates(current_user: User, db: Session):
    """Get candidates visible to user"""
    scope = get_data_access_scope(current_user.id, db)
    
    candidates = db.query(Candidate).filter(
        Candidate.tenant_id == scope.tenant_id,
        Candidate.location_id.in_(scope.accessible_locations),
        # IF candidate is associated to a BU, must be accessible
        Candidate.associated_bu_id.in_(scope.accessible_bus) | (Candidate.associated_bu_id == None)
    ).all()
    
    return candidates

@router.get("/employees")
async def list_employees(current_user: User, db: Session):
    """Get employees visible to user"""
    scope = get_data_access_scope(current_user.id, db)
    
    employees = db.query(Employee).filter(
        Employee.tenant_id == scope.tenant_id,
        Employee.bu_id.in_(scope.accessible_bus),
        Employee.location_id.in_(scope.accessible_locations),
        # Manager sees their reports
        Employee.id.in_(scope.subordinates) | (Employee.id == current_user.id)
    ).all()
    
    return employees
```

---

### 5. Endpoint Decorator Cleanup

**Current State:** 45+ hardcoded permission strings in decorators  
**Target:** Remove hardcoding, make decorators permission-aware

**Before:**
```python
@router.get("/cfo/snapshot", 
    dependencies=[Depends(require_permission("CEO"))])
def get_cfo_snapshot(...):
    pass
```

**After:**
```python
@router.get("/cfo/snapshot",
    dependencies=[Depends(require_permission("revenue.view_pnl"))])
def get_cfo_snapshot(...):
    pass
```

**Pattern:**
- Replace role names with permission strings
- Use format: `resource.action`
- Remove all hardcoded role name checks from decorators

---

### 6. Service Layer Database Query Fixes (8 Files)

**Current:** Hardcoded role filters in queries  
**Target:** Dynamic permission-based queries

**Files to Fix:**

1. `app/services/cfo_agent_service.py` (line 172)
   - WRONG: `db.query(Users).filter(Users.UserRole == "Partner")`
   - RIGHT: `get_users_with_permission("revenue.view")`

2. `app/services/expense_service.py` (line 168)
   - WRONG: `db.query(Users).filter(Users.UserRole == "Finance")`
   - RIGHT: `get_users_with_permission("finance.manage")`

3. `app/services/partner_incentive_service.py` (line 33)
   - WRONG: `db.query(Users).filter(Users.UserRole == "Partner")`
   - RIGHT: `get_users_with_permission("partner.manage")`

4. `app/services/job_approval_workflow_service.py` (line 39)
5. `app/services/referral_access_control.py` (line 278)
6. `app/services/ai_conversation_service.py` (line 318)
7. `app/services/error_log_service.py` (line 33)
8. `app/services/revenue_target_service.py` (line 131)

**Implementation Pattern:**

```python
def get_users_with_permission(permission: str, db: Session) -> List[User]:
    """Get all users who have a specific permission via role templates"""
    resource, action = permission.split('.')
    
    return db.query(User).join(
        UserRole, User.id == UserRole.user_id
    ).join(
        RoleTemplate, UserRole.role_template_id == RoleTemplate.id
    ).join(
        RoleTemplateModuleAccess, RoleTemplate.id == RoleTemplateModuleAccess.role_template_id
    ).join(
        Module, RoleTemplateModuleAccess.module_id == Module.id
    ).filter(
        Module.name == resource,
        RoleTemplateModuleAccess.access_level == action
    ).distinct().all()
```

---

## IMPLEMENTATION ORDER

### Week 1

**Day 1-2:**
- [ ] Create Organization Service (separate microservice)
- [ ] Implement employee hierarchy queries
- [ ] Add GET endpoints for BU, Location, Employee

**Day 3-4:**
- [ ] Create `app/services/permission_helper.py`
- [ ] Implement all permission query functions
- [ ] Add unit tests for permission helpers

**Day 5:**
- [ ] Rewrite `app/core/dependencies.py`
- [ ] Remove all hardcoded role checks
- [ ] Wire to Organization Service + permission queries

### Week 2

**Day 1-2:**
- [ ] Rewrite `app/services/rbac_service.py`
- [ ] Rewrite `app/api/v1/endpoints/role_based_dashboard.py`
- [ ] Remove all hardcoded role conditionals

**Day 3-4:**
- [ ] Fix 8 service layer files (cfo_agent, expense, etc.)
- [ ] Replace hardcoded role filters with permission queries
- [ ] Add data scope filtering to all queries

**Day 5:**
- [ ] Implement candidate isolation logic
- [ ] Add `associated_bu_id` column
- [ ] Create candidate submission flow

### Week 3

**Day 1-2:**
- [ ] Cleanup endpoint decorators (45+ files)
- [ ] Replace role names with permission strings
- [ ] Verify all decorators use resource.action format

**Day 3-4:**
- [ ] Add query-time data filtering (all endpoints)
- [ ] Implement get_data_access_scope()
- [ ] Add WHERE clauses for BU, Location, Hierarchy

**Day 5:**
- [ ] Test entire backend
- [ ] Verify zero hardcoded role names in codebase
- [ ] Verify zero hardcoded permission strings (except decorators)

---

## TESTING STRATEGY

### Unit Tests

```python
# Test permission queries
def test_get_user_permissions():
    user = create_test_user(role_template="Recruiter")
    permissions = get_user_permissions(user.id, db)
    assert "recruitment.manage" in permissions

# Test hierarchy cascading
def test_manager_sees_reports():
    manager = create_test_user(level=Manager)
    report1 = create_test_user(manager_id=manager.id)
    report2 = create_test_user(manager_id=manager.id)
    
    subordinates = get_user_subordinates(manager.id, db)
    assert report1.id in subordinates
    assert report2.id in subordinates

# Test candidate isolation
def test_candidate_isolation():
    candidate = create_test_candidate(associated_bu_id=None)
    job = create_test_job(bu_id="BU-1")
    
    submit_candidate_to_job(candidate.id, job.id, db)
    
    candidate = db.query(Candidate).filter(id=candidate.id).first()
    assert candidate.associated_bu_id == "BU-1"
```

### Integration Tests

```python
# Test recruiter access
def test_recruiter_sees_unassociated():
    recruiter = create_recruiter(bu_id="BU-1")
    unassociated = create_candidate(associated_bu_id=None)
    bu2_locked = create_candidate(associated_bu_id="BU-2")
    
    visible = get_recruitment_candidates(recruiter.id, db)
    assert unassociated.id in visible
    assert bu2_locked.id not in visible

# Test manager hierarchy
def test_manager_cannot_see_other_bu():
    manager_bu1 = create_user(bu_id="BU-1", level=Manager)
    employee_bu2 = create_employee(bu_id="BU-2")
    
    visible = list_employees(manager_bu1, db)
    assert employee_bu2.id not in visible
```

---

## SUCCESS CRITERIA

✅ **Zero Hardcoded Role Names**
- Grep: `grep -r "CEO\|CFO\|Recruiter\|Partner" app/` → 0 results (except DB)

✅ **Zero Hardcoded Permission Strings**
- Grep: `grep -r "recruitment.manage\|project.view" app/` → 0 results (except registry)

✅ **All Permissions Query Database**
- Every permission check calls `get_user_permissions()` or `has_permission()`

✅ **Candidate Isolation Working**
- Unassociated candidates visible to all recruiters
- Associated candidates visible only to BU recruiters
- Candidate cannot be submitted to multiple BUs

✅ **Data Scoping Enforced**
- All queries include tenant_id filter
- All queries include BU/Location filter
- Managers see only their reporting chain

✅ **Tests Passing**
- Unit tests: 50+ passing
- Integration tests: 20+ passing
- No regression in existing functionality

---

## ROLLBACK PLAN

If critical issues discovered:
```bash
git revert [commit-hash]
# Revert to last working state
# Identify issue
# Fix and re-test
# Commit again
```

All changes committed atomically to enable easy rollback.

---

**END OF PHASE 2 IMPLEMENTATION SPECIFICATION**

This specification is the detailed implementation guide for Phase 2.
Follow this structure to eliminate all hardcoding from the system.
