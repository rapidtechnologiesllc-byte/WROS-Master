# Hardcoded Permissions Migration to Role Template System

## Overview
This document maps old hardcoded permission strings to the new database-driven role template system.

**Old System:** Hardcoded permission strings like `require_permission("candidate.view")`
**New System:** Resource + Action using `require_resource_permission("candidates", "view")`

---

## Permission Mapping Reference

### Admin Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `admin.manage` | `admin-settings` | create, edit, delete | Admin settings management |
| `user.manage` | `users` | create, edit, delete | User management |
| `rbac.manage` | `roles-permissions` | create, edit, delete | Role and permission management |
| `organization.manage` | `organization` | create, edit, delete | Organization settings |

### Recruitment Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `candidate.view` | `candidates` | view | View candidates list |
| `candidate.create` | `candidates` | create | Create new candidate |
| `candidate.edit` | `candidates` | edit | Edit candidate details |
| `candidate.delete` | `candidates` | delete | Delete candidate |
| `recruitment.view` | `candidates` | view | View recruitment screens |
| `recruitment.manage` | `submissions` | create, edit, delete | Manage job submissions |
| `job.view` | `jobs` | view | View jobs list |
| `job.manage` | `jobs` | create, edit, delete | Create/edit jobs |
| `interview.manage` | `interviews` | create, edit, delete | Schedule and manage interviews |
| `interview.feedback` | `interviews` | edit | Submit interview feedback |
| `offer.manage` | `offer-letters` | create, edit, delete | Create and manage offers |
| `offer.view` | `offer-letters` | view | View offers |
| `offer.readiness_check` | `offer-letters` | view | Check offer readiness |

### Workforce Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `employee.view` | `employees` | view | View employees list |
| `employee.manage` | `employees` | create, edit, delete | Manage employees |
| `employee.convert` | `employees` | create | Convert candidate to employee |
| `onboarding.manage` | `onboarding` | create, edit, delete | Manage onboarding |
| `allocation.manage` | `allocations` | create, edit, delete | Allocate employees to projects |
| `timesheet.view` | `timesheets` | view | View timesheets |
| `timesheet.approve` | `timesheets` | edit | Approve/reject timesheets |
| `leave.approve` | `leave-management` | edit | Approve leave requests |
| `performance.manage` | `performance-management` | create, edit, delete | Manage performance reviews |

### Sales Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `client.view` | `clients` | view | View clients list |
| `client.manage` | `clients` | create, edit, delete | Manage clients |
| `opportunity.view` | `opportunities` | view | View opportunities |
| `opportunity.manage` | `opportunities` | create, edit, delete | Manage opportunities |
| `proposal.manage` | `proposals` | create, edit, delete | Create proposals |
| `revenue.view` | `revenue` | view | View revenue reports |

### Project Management Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `project.manage` | `projects` | create, edit, delete | Manage projects |
| `project.view` | `projects` | view | View projects |
| `task.manage` | `tasks` | create, edit, delete | Manage tasks |

### Finance Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `invoice.view` | `invoices` | view | View invoices |
| `invoice.manage` | `invoices` | create, edit, delete | Create and approve invoices |
| `expense.manage` | `expenses` | create, edit, delete | Manage expenses |
| `payroll.manage` | `payroll` | create, edit, delete | Manage payroll |
| `reports.financial` | `reports` | view | View financial reports |
| `budget.manage` | `budget-management` | create, edit, delete | Manage budgets |

### Reporting Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `reports.view` | `reports` | view | View reports and analytics |
| `analytics.view` | `analytics` | view | View analytics dashboard |

### System Module
| Old Permission | Resource | Action | Notes |
|---|---|---|---|
| `system.manage` | `system-health` | edit | Manage system configuration |
| `audit.view` | `audit-logs` | view | View audit logs |
| `api.manage` | `api-keys` | create, edit, delete | Manage API keys |

---

## Conversion Guide

### Before (Old System)
```python
@router.get("/candidates")
def list_candidates(db: Session = Depends(get_db), user = Depends(require_permission("candidate.view"))):
    # Logic here
```

### After (New System)
```python
@router.get("/candidates")
def list_candidates(
    db: Session = Depends(get_db), 
    user = Depends(require_resource_permission("candidates", "view"))
):
    # Logic here
```

---

## Backend Endpoints to Update

### interviews.py (8 hardcoded checks → REMOVED, now require nothing for Super User compatibility)
- POST `/panels/create` - interview.manage → require_resource_permission("interviews", "create")
- POST `/schedule` - interview.manage → require_resource_permission("interviews", "create")
- PUT `/update-status` - interview.manage → require_resource_permission("interviews", "edit")
- POST `/feedback/submit` - interview.manage → require_resource_permission("interviews", "edit")
- etc.

### preonboarding.py (1 hardcoded check → REMOVED)
- Manage preboarding → require_resource_permission("onboarding", "edit")

### email.py (7 hardcoded checks → REMOVED)
- Send email endpoints → require_resource_permission("interviews", "edit")

### Other endpoints needing review:
- candidates.py → candidate.* permissions
- jobs.py → job.* permissions
- employees.py → employee.* permissions
- offers.py → offer.* permissions
- clients.py → client.* permissions
- finance.py → finance.* permissions

---

## Frontend Permissions

### Permission Checks in Components
Frontend uses localStorage permission arrays. Need to map hardcoded role/permission checks to new system.

Current pattern in frontend:
```javascript
if (user.roles?.includes('Admin') || user.roles?.includes('Recruiter')) {
    // Show UI
}
```

New pattern:
```javascript
import { hasPermission } from '../utils/permissionsRbac'

if (hasPermission('candidates', 'create')) {
    // Show UI
}
```

### Frontend Locations to Update
- Navigation/routing (show/hide menu items based on resource permissions)
- Form permission guards (enable/disable buttons based on actions)
- Data display (show/hide columns based on view permission)
- Modal access (require edit/delete permission before showing action buttons)

---

## Implementation Strategy

### Phase 1: Backend - Critical Paths (Sprint 1)
1. ✅ Removed hardcoded `interview.manage` checks (16 total)
2. Next: Remove hardcoded checks in candidate endpoints
3. Next: Remove hardcoded checks in employee endpoints

### Phase 2: Backend - All Endpoints (Sprint 2)
1. Replace all `require_permission()` calls with `require_resource_permission()`
2. Update each endpoint with correct resource name and action

### Phase 3: Frontend - Permission Rendering (Sprint 3)
1. Replace hardcoded role checks with `hasPermission(resource, action)`
2. Update navigation to use permission-based rendering
3. Update form/button rendering based on resource actions

### Phase 4: Testing & Verification (Sprint 4)
1. Test all critical user workflows
2. Verify Super User still has access to everything
3. Test role-based access restrictions

---

## Database Verification

Run this to verify all resources are present:

```sql
SELECT m.name as Module, r.name as Resource, r.id, r.enabled
FROM modules m
JOIN resources r ON m.id = r.module_id
WHERE m.tenant_id = 1 AND r.tenant_id = 1
ORDER BY m.name, r.name;
```

Should return 46 total resources across 8 modules.

---

## Notes

- Super User role automatically has all permissions (no database check needed)
- All permission checks now go through `role_template_permission_service.py`
- Old permission strings are no longer used (except for backward compatibility)
- Frontend permission arrays are populated from backend during login
- localStorage stores the permission union of all user roles
