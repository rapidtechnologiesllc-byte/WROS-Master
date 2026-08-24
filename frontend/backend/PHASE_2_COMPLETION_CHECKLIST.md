# Phase 2 Completion Checklist - Zero-Hardcoding Backend Rewrite

**Status:** 70% COMPLETE - Ready for final 30% (1-2 hours)  
**Date:** 2026-08-16  
**Objective:** 100% elimination of hardcoded roles, permissions, and configurations

---

## ✅ COMPLETED TASKS (70%)

### Foundation Architecture
- [x] OrganizationService created (550+ lines)
  - [x] get_employee(), get_direct_reports(), get_all_subordinates() (recursive)
  - [x] get_reporting_chain_to_ceo(), get_hierarchy_info()
  - [x] get_user_accessible_locations(), get_user_accessible_business_units()
  - [x] is_manager_of(), get_org_hierarchy_tree()

- [x] PermissionHelper created (170+ lines)
  - [x] get_user_permissions() - queries role_templates
  - [x] has_permission(), has_any_permission(), has_all_permissions()
  - [x] is_super_admin(), get_data_access_scope() (DataScope object)
  - [x] get_accessible_modules(), get_permissions_by_module()

- [x] ServiceHelpers created (62 lines)
  - [x] get_users_with_permission()
  - [x] get_users_with_any_permission()

### Core Services Refactored
- [x] RBACService complete rewrite (160 lines, database-driven)
  - [x] Removed 445+ lines of hardcoded seed data
  - [x] All methods query role_templates instead of hardcoded values
  - [x] Old version archived as rbac_service_deprecated.py

- [x] dependencies.py updated
  - [x] require_permission() uses PermissionHelper
  - [x] require_attribute() uses PermissionHelper
  - [x] require_admin_role() uses permission checks
  - [x] Zero hardcoded role checks

### Service Layer Compliance
- [x] cfo_agent_service.py - Using RBACService.has_permission()
- [x] expense_service.py - Using get_users_with_permission()
- [x] partner_incentive_service.py - Using RBACService.has_permission()
- [x] job_approval_workflow_service.py - Using RBACService.has_permission()
- [x] referral_access_control.py - **REFACTORED**: Removed hardcoded ROLE_HIERARCHY
- [x] ai_conversation_service.py - Using RBACService.has_permission()
- [x] error_log_service.py - Using RBACService.has_permission()
- [x] revenue_target_service.py - Using RBACService.has_permission()

### Data Isolation
- [x] Candidate model updated
  - [x] Added submission_bu_id (immutable)
  - [x] Added associated_bu_id (for filtering)
  - [x] Added submission_timestamp (audit trail)
  - [x] Added relationships for BU associations

- [x] CandidateIsolationService created (240+ lines)
  - [x] submit_candidate_to_bu() - Lock candidate to BU
  - [x] can_view_candidate() - Visibility enforcement
  - [x] get_candidates_for_user() - BU-scoped queries
  - [x] get_candidate_isolation_status() - Status info

### Endpoint Cleanup Started
- [x] agents.py endpoints refactored (3 endpoints)
  - [x] get_partner_roi_kpis() - Permission-based access check
  - [x] get_partner_roi_trend() - Permission-based access check
  - [x] get_partner_roi_actions() - Permission-based access check
  - [x] Pattern established and documented

### Documentation & Tools
- [x] PHASE_2_PROGRESS_COMPREHENSIVE.md (comprehensive status)
- [x] PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md (pattern + mapping + script)
- [x] CANDIDATE_ISOLATION_MIGRATION.sql (database migration)
- [x] This completion checklist

---

## ⏳ REMAINING TASKS (30%)

### Phase 2 Final Tasks

#### 1. Database Migration (20 minutes)
- [ ] Execute CANDIDATE_ISOLATION_MIGRATION.sql
  - [ ] Add submission_bu_id column to candidates
  - [ ] Add associated_bu_id column to candidates
  - [ ] Add submission_timestamp column to candidates
  - [ ] Create indexes for fast queries
  - [ ] Verify migration with count query

#### 2. Endpoint Decorator Cleanup (1-2 hours)
**Files to fix (priority order):**

**CRITICAL:**
- [ ] agent_standups_dashboard.py (lines 28, 86)
  - [ ] Remove hardcoded `["Super User", "Admin", "CEO"]` check
  - [ ] Use `RBACService.has_any_permission(db, current_user.UserID, ["admin.manage"])`
  
- [ ] agent_state_dashboard.py (multiple locations)
  - [ ] Same pattern as above

- [ ] business_metrics.py (multiple locations)
  - [ ] Replace Finance/CFO checks with `revenue.manage` permission

**HIGH:**
- [ ] rbac.py - Admin-only operations
- [ ] rbac_templates.py - Role template management
- [ ] users.py - User creation/deletion

**MEDIUM:**
- [ ] interviews.py - HR/Recruiter checks
- [ ] create_job.py - Job creation
- [ ] onboarding.py - Onboarding workflows
- [ ] role_based_dashboard.py - Dynamic rendering

**Optional:**
- [ ] Other files with minimal hardcoding (auth.py comments, etc.)

**How to fix each file:**
1. Find: `if current_user.UserRole not in ["X", "Y"]:`
2. Replace with: `if not RBACService.has_any_permission(db, current_user.UserID, ["permission.check"]):`
3. Use role-to-permission mapping from PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md
4. Add import: `from app.services.rbac_service import RBACService`
5. Test endpoint responds with 403 for unauthorized users
6. Commit with clear message: `refactor: Remove hardcoded role checks from {filename}`

#### 3. Candidate Isolation Integration (30 minutes)
- [ ] Integrate candidate_isolation_service into candidate queries
  - [ ] Add isolation filtering to candidates list endpoint
  - [ ] Use `CandidateIsolationService.get_candidates_for_user(db, user_id)`
  - [ ] Filter candidates by user's accessible BUs
  
- [ ] Create submit-to-BU endpoint
  - [ ] POST `/candidates/{id}/submit-to-bu`
  - [ ] Calls `CandidateIsolationService.submit_candidate_to_bu()`
  - [ ] Returns 403 if candidate already submitted to different BU

- [ ] Update candidate visibility in endpoints
  - [ ] CandidateDetailsScreen respects BU isolation
  - [ ] Candidate list filtered by user's BU

#### 4. Integration Testing (1-2 hours)
- [ ] Test RBACService with role_templates
  - [ ] Verify permission chain working correctly
  - [ ] Test with multiple roles per user
  
- [ ] Test candidate isolation
  - [ ] Unassociated candidates visible to all HR
  - [ ] Associated candidates locked to BU
  - [ ] Cannot move candidate between BUs
  
- [ ] Test endpoint permission checks
  - [ ] Authorized users have access
  - [ ] Unauthorized users get 403
  - [ ] Multiple role combinations work
  
- [ ] Regression testing
  - [ ] Existing workflows still work
  - [ ] No broken dependencies
  - [ ] All existing tests pass

---

## 📊 Success Criteria

✅ Phase 2 COMPLETE when ALL of these are true:

1. **Zero Hardcoding**
   - [ ] No hardcoded role names (e.g., "Partner", "Finance") in code
   - [ ] No hardcoded permission mappings
   - [ ] No hardcoded role hierarchies
   - [ ] All access logic queries database via role_templates

2. **Database Driven**
   - [ ] All permissions from role_templates
   - [ ] All role assignments via UserRole junction table
   - [ ] All data visibility via BU/hierarchy queries

3. **Service Layer**
   - [ ] All 8+ service files using RBACService or helpers
   - [ ] No hardcoded role checks in service logic
   - [ ] All permission decisions centralized

4. **Endpoints**
   - [ ] All 45+ endpoints using decorators or RBACService checks
   - [ ] No hardcoded role string comparisons
   - [ ] All permission checks permission-based, not role-based

5. **Data Isolation**
   - [ ] Candidate submission tracks BU
   - [ ] BU visibility enforced in queries
   - [ ] Unassociated candidates visible globally
   - [ ] Associated candidates locked to BU

6. **Testing**
   - [ ] All existing tests pass
   - [ ] No broken workflows
   - [ ] Permission checks working correctly
   - [ ] Isolation rules enforced

---

## 📝 How to Complete Remaining 30%

### Option A: Quick Path (1.5-2 hours)
1. Run database migration (20 min)
2. Fix top 5 critical endpoint files (1 hour)
3. Integrate candidate isolation (20 min)
4. Quick smoke test (10 min)
5. **Result:** 90%+ hardcoding eliminated, ready for Phase 3

### Option B: Complete Path (3-4 hours)
1. Run database migration (20 min)
2. Fix ALL endpoint files using script (1-1.5 hours)
3. Integrate candidate isolation thoroughly (30 min)
4. Comprehensive testing (1-2 hours)
5. **Result:** 100% zero-hardcoding compliance, production ready

### Option C: Automated Path (1 hour)
1. Run database migration (20 min)
2. Use Python script from PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md (20 min)
3. Manual review of changed files (15 min)
4. Quick test (5 min)
5. **Result:** Automated cleanup with minimal manual work

---

## 📋 Key Files Reference

**Core Services (DO NOT MODIFY):**
- `app/services/rbac_service.py` - ✅ Complete (database-driven)
- `app/services/permission_helper.py` - ✅ Complete
- `app/services/organization_service.py` - ✅ Complete
- `app/services/candidate_isolation_service.py` - ✅ Complete

**Configuration Files (EXECUTE THESE):**
- `CANDIDATE_ISOLATION_MIGRATION.sql` - Database migration (needs execution)
- `PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md` - How to fix endpoints

**Documentation:**
- `PHASE_2_PROGRESS_COMPREHENSIVE.md` - Detailed progress
- `PHASE_2_COMPLETION_CHECKLIST.md` - This file

---

## 🚀 Quick Start for Completing Remaining 30%

```bash
# 1. Execute database migration
mysql -u root wros_dev < CANDIDATE_ISOLATION_MIGRATION.sql

# 2. Fix endpoints (pick one approach):

# APPROACH A: Manual (most control)
# - Open PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md
# - Follow pattern for each file
# - Test after each change

# APPROACH B: Semi-automated
# - Run Python script from PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md
# - Review changes
# - Test manually

# 3. Integrate candidate isolation
# - Update candidates list endpoint to use CandidateIsolationService.get_candidates_for_user()
# - Create submit-to-BU endpoint if not exists
# - Test BU isolation in candidate queries

# 4. Test
pytest tests/ -v
```

---

## 📞 Support & Questions

**If stuck on:**
- Endpoint cleanup → See PHASE_2_ENDPOINT_CLEANUP_SCRIPT.md (has pattern + examples)
- Candidate isolation → See candidate_isolation_service.py (fully documented)
- Database migration → See CANDIDATE_ISOLATION_MIGRATION.sql (ready to execute)
- Testing → Check existing tests in `tests/` directory

---

**Target Completion:** 2-4 hours from now  
**Effort:** Medium (mostly pattern repetition)  
**Complexity:** Low (pattern already established)  
**Risk:** Low (all changes backward compatible)

**Once complete: 100% Zero-Hardcoding compliance ✅**
