# Permission System Hardening - Complete End-to-End Fix Plan

**Status:** Phase 1 COMPLETE (13 violations fixed), Phase 2-3 READY FOR EXECUTION  
**Last Updated:** 2026-09-04  
**Scope:** Fix 125+ endpoints + 30+ hard-coded strings + 50+ resource names

---

## What Was Already Fixed (CRITICAL - Complete)

✅ **Commit b244ab53** - Permission System Hardening Foundation
- Fixed `timesheets.py`: 11 endpoints migrated from `@require_permission` decorator → `dependencies=[Depends(...)]`
- Fixed `users_access_control.py`: 4 endpoints migrated from `@require_action_permission` decorator → `dependencies=[Depends(...)]`
- Expanded `permission_registry.py`: Added 5 new resources (timesheets, invoices, opportunities, clients, business_units)
- Created `Permissions` constants: 20 new constants for data-driven permission checks

---

## What Remains (HIGH Priority)

### Phase 2A: Add Permission Checks to 125+ Unprotected Endpoints

**Current Pattern (WRONG):**
```python
@router.get("/endpoint")
def get_endpoint(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    # Any authenticated user can access - NO role-based control!
```

**Required Pattern (RIGHT):**
```python
@router.get(
    "/endpoint",
    dependencies=[
        Depends(get_current_internal_user),
        Depends(require_role_template_permission(*Permissions.RESOURCE_ACTION))
    ]
)
def get_endpoint(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    # Only users with RESOURCE_ACTION permission can access
```

**Endpoint Files to Update (130 files):**
1. abandonment_scoring.py - 1 endpoint
2. activity_feed.py - 2 endpoints
3. activity_timeline.py - 3 endpoints
4. admin_queue.py - 2 endpoints
5. agent_config.py - 4 endpoints
6. agent_maturity.py - 6 endpoints
7. agent_pyramid_reporting.py - 8 endpoints
... and 120+ more files

**Total Endpoints Needing Fixes:** 200+

---

### Phase 2B: Replace Hard-Coded Permission Strings with Constants

**Files with hard-coded strings to replace:**
- candidates.py: 5 instances of `"candidates"`, `"create"`, `"view"`
- jobs.py: 3 instances of hard-coded permission checks
- projects.py: 2 instances (already partially fixed)
- employees.py: 4 instances
- interviews.py: 2 instances
- invoices.py: 3 instances
- And 20+ more files

**Current (WRONG):**
```python
require_role_template_permission("candidates", "can_view")  # Magic string!
```

**Required (RIGHT):**
```python
require_role_template_permission(*Permissions.CANDIDATES_VIEW)  # Constant from registry!
```

**Total Hard-Coded Strings:** 30+

---

### Phase 2C: Replace Hard-Coded Resource Names

**Current (WRONG):**
```python
permission_service.check_permission(
    user,
    resource="candidates",  # Hard-coded!
    action="view",           # Hard-coded!
)
```

**Required (RIGHT):**
```python
permission_service.check_permission(
    user,
    resource=Permissions.CANDIDATES_VIEW[0],  # From constant
    action=Permissions.CANDIDATES_VIEW[1],    # From constant
)
```

**Total Hard-Coded Resource Names:** 50+ instances across:
- service layer functions
- initialization scripts
- data scoping logic
- permission composition logic

---

## Execution Plan (Sequential)

### Step 1: Complete Permission Registry (30 minutes)
File: `backend/app/core/permission_registry.py`

Add ALL missing resources and constants:
- ✅ candidates, jobs, interviews (DONE)
- ✅ projects, employees, timesheets (DONE)
- ✅ invoices, opportunities, clients, business_units (DONE)
- ⏳ Add: agents, dashboards, reports, configuration, notifications, integrations
- ⏳ Add: 40+ more resource types found in endpoint files

### Step 2: Scan All 130 Endpoint Files (15 minutes)
Create a mapping of:
```
File → Endpoints → Required Permission Resource
abandonment_scoring.py → GET /scoring → AGENTS_VIEW
activity_timeline.py → GET /timeline → REPORTS_VIEW
...etc
```

**Script:**
```bash
for file in backend/app/api/v1/endpoints/*.py; do
  endpoints=$(grep -c "@router\." "$file")
  if [ "$endpoints" -gt 0 ]; then
    echo "$(basename $file) → $endpoints endpoints"
  fi
done | sort
```

### Step 3: Add Permission Checks to All Endpoints (4-6 hours)
For each file with 2+ endpoints:
1. Add import: `from app.core.permission_registry import Permissions`
2. For each `@router.get/@router.post/@router.put/@router.delete`:
   - Extract resource type from endpoint path/purpose
   - Add to `dependencies` array: `Depends(require_role_template_permission(...))`
   - Add the appropriate Permissions constant to registry if missing

**Pattern per endpoint:**
```python
# GET /candidates → needs CANDIDATES_VIEW
@router.get(
    "/candidates",
    dependencies=[
        Depends(get_current_internal_user),
        Depends(require_role_template_permission(*Permissions.CANDIDATES_VIEW))
    ]
)

# POST /candidates → needs CANDIDATES_CREATE
@router.post(
    "/candidates",
    dependencies=[
        Depends(get_current_internal_user),
        Depends(require_role_template_permission(*Permissions.CANDIDATES_CREATE))
    ]
)
```

### Step 4: Replace All Hard-Coded Strings (2-3 hours)
For each file with hard-coded permission strings:
1. Find: `require_role_template_permission("resource", "action")`
2. Replace with: `require_role_template_permission(*Permissions.RESOURCE_ACTION)`
3. Verify constant exists in permission_registry.py

**Search pattern:**
```bash
grep -r 'require_role_template_permission("' backend/app/
```

### Step 5: Replace Hard-Coded Resource Names (2 hours)
For each service/logic file with resource name strings:
1. Find: `resource="candidates"` or `resource='jobs'`
2. Replace with: `resource=Permissions.RESOURCE_ACTION[0]` (or create constant)
3. Same for action names

**Search pattern:**
```bash
grep -r 'resource=' backend/app/services/ backend/app/core/
grep -r 'action=' backend/app/services/ backend/app/core/
```

### Step 6: Comprehensive Testing (3-4 hours)
- [ ] All Python files compile without errors
- [ ] All permission constants validate against registry
- [ ] All endpoints have permission checks
- [ ] No hard-coded permission strings remain
- [ ] No hard-coded resource names remain
- [ ] Gate approval for all files
- [ ] Integration test: Create user, assign roles, verify 403 on unauthorized endpoints

---

## Resource Mapping (Complete Reference)

### Agent Resources
- AGENTS_VIEW, AGENTS_CREATE, AGENTS_EDIT, AGENTS_DELETE
- AGENT_CONFIG_VIEW, AGENT_CONFIG_EDIT
- AGENT_PERFORMANCE_VIEW, AGENT_ACCOUNTABILITY_VIEW

### Recruitment Resources
- CANDIDATES_VIEW, CANDIDATES_CREATE, CANDIDATES_EDIT, CANDIDATES_DELETE
- JOBS_VIEW, JOBS_CREATE, JOBS_EDIT, JOBS_DELETE
- INTERVIEWS_VIEW, INTERVIEWS_CREATE, INTERVIEWS_EDIT, INTERVIEWS_DELETE
- OFFERS_VIEW, OFFERS_CREATE, OFFERS_EDIT, OFFERS_DELETE

### HR/Operations Resources
- EMPLOYEES_VIEW, EMPLOYEES_CREATE, EMPLOYEES_EDIT, EMPLOYEES_DELETE
- TIMESHEETS_VIEW, TIMESHEETS_CREATE, TIMESHEETS_EDIT, TIMESHEETS_DELETE
- PROJECTS_VIEW, PROJECTS_CREATE, PROJECTS_EDIT, PROJECTS_DELETE
- ALLOCATIONS_VIEW, ALLOCATIONS_CREATE, ALLOCATIONS_EDIT, ALLOCATIONS_DELETE

### Finance Resources
- INVOICES_VIEW, INVOICES_CREATE, INVOICES_EDIT, INVOICES_DELETE
- REVENUE_VIEW, REVENUE_EDIT
- EXPENSES_VIEW, EXPENSES_CREATE, EXPENSES_EDIT, EXPENSES_DELETE

### Sales/Pipeline Resources
- OPPORTUNITIES_VIEW, OPPORTUNITIES_CREATE, OPPORTUNITIES_EDIT, OPPORTUNITIES_DELETE
- CLIENTS_VIEW, CLIENTS_CREATE, CLIENTS_EDIT, CLIENTS_DELETE
- BUSINESS_UNITS_VIEW, BUSINESS_UNITS_CREATE, BUSINESS_UNITS_EDIT, BUSINESS_UNITS_DELETE

### Dashboards/Reports Resources
- DASHBOARDS_VIEW, DASHBOARDS_CREATE, DASHBOARDS_EDIT, DASHBOARDS_DELETE
- REPORTS_VIEW, REPORTS_CREATE, REPORTS_EDIT, REPORTS_DELETE
- ANALYTICS_VIEW, ANALYTICS_EDIT

### Configuration Resources
- ROLE_TEMPLATES_VIEW, ROLE_TEMPLATES_CREATE, ROLE_TEMPLATES_EDIT, ROLE_TEMPLATES_DELETE
- SYSTEM_CONFIG_VIEW, SYSTEM_CONFIG_EDIT
- NOTIFICATIONS_VIEW, NOTIFICATIONS_EDIT

---

## Implementation Checklist

### Phase 2A: Complete Permission Registry
- [ ] Add 40+ missing resource definitions to RESOURCES dict
- [ ] Create 160+ missing Permissions constants
- [ ] Verify all constants map to valid resources
- [ ] Update PERMISSION_GROUPS with complete role-based permission sets

### Phase 2B: Add Permission Checks to All Endpoints
- [ ] agents*.py files (8 files, 30+ endpoints)
- [ ] candidate*.py files (8 files, 25+ endpoints)
- [ ] interview*.py files (3 files, 10+ endpoints)
- [ ] job*.py files (2 files, 8+ endpoints)
- [ ] project*.py files (2 files, 10+ endpoints)
- [ ] employee*.py files (3 files, 12+ endpoints)
- [ ] invoice*.py files (3 files, 8+ endpoints)
- [ ] dashboard*.py files (6 files, 15+ endpoints)
- [ ] report*.py files (4 files, 12+ endpoints)
- [ ] admin/config files (5 files, 10+ endpoints)
- [ ] All remaining 85+ files

### Phase 2C: Replace All Hard-Coded Strings
- [ ] Scan all 130 endpoint files
- [ ] Replace all `"resource"` strings with constants
- [ ] Replace all `"action"` strings with constants
- [ ] Update service layer functions
- [ ] Update initialization scripts

### Phase 2D: Replace All Hard-Coded Resource Names
- [ ] Scan all service files (50+ files)
- [ ] Replace resource name assignments
- [ ] Replace resource name comparisons
- [ ] Update data scoping logic
- [ ] Update permission composition logic

### Phase 3: Testing & Validation
- [ ] All Python files compile
- [ ] All permission constants valid
- [ ] Gate approval for all changes
- [ ] Integration testing
- [ ] End-to-end permission enforcement verification

---

## Estimated Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Fix CRITICAL violations (timesheets, users_access_control) | 45 min | ✅ DONE |
| 2A | Complete permission registry | 30 min | ⏳ READY |
| 2B | Add permission checks to 200+ endpoints | 4-6 hrs | ⏳ READY |
| 2C | Replace 30+ hard-coded strings | 2-3 hrs | ⏳ READY |
| 2D | Replace 50+ resource names | 2 hrs | ⏳ READY |
| 3 | Testing & validation | 3-4 hrs | ⏳ READY |
| **TOTAL** | **End-to-end bulletproof fix** | **12-16 hrs** | |

---

## Success Criteria

✅ **When Complete:**
- [ ] Zero unprotected endpoints (all have permission checks)
- [ ] Zero hard-coded permission strings (all use Permissions constants)
- [ ] Zero hard-coded resource names (all use Permissions constants)
- [ ] All 200+ endpoints properly gated by role template permissions
- [ ] Admin can modify ALL permissions via role templates UI
- [ ] Zero dependencies on code changes for permission modifications
- [ ] Gate passes all 130 endpoint files
- [ ] 403 Forbidden returned when user lacks permission
- [ ] 200 OK when user has proper permission
- [ ] Audit trail shows which user accessed which resource with which permission

---

## Notes

- **Data-Driven Architecture:** Every permission check reads from `role_template_permissions` table
- **Admin Control:** All permissions configurable via UI (no code changes)
- **Single Source of Truth:** Permissions constants = only place resource/action names appear
- **Production Ready:** Every endpoint properly enforced before production deployment

---

## Start Execution?

Ready to proceed with Phase 2A-D. This is a comprehensive end-to-end hardening that will bulletproof the entire system.

**Next Action:** Begin Phase 2A (Permission Registry completion) or Phase 2B (endpoint hardening) based on priority.
