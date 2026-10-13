# Permission-Based Access Control Pattern Guide

**Last Updated:** 2026-09-01  
**Status:** ENFORCED - All creation/edit/delete operations must follow this pattern

## Overview

This guide ensures consistent permission-based access control across the entire frontend application. Every operation that requires backend authorization must have corresponding frontend protection.

## The Pattern (3 Layers)

### Layer 1: Button/Component Visibility
Hide UI elements when user lacks permission.

```javascript
import { hasPermission } from "../utils/permissionsRoleTemplate";

// Don't show button if user lacks permission
{hasPermission("resource", "create") && (
  <Button onClick={() => navigate("/create-path")}>
    <Plus /> Create Resource
  </Button>
)}
```

### Layer 2: Function Validation
Add runtime check in handler functions.

```javascript
const handleCreate = () => {
  if (!hasPermission("resource", "create")) {
    toast.error("You don't have permission to create resources");
    return;
  }
  // Proceed with creation
  navigate("/create-path");
};
```

### Layer 3: Route Protection
Redirect users without permission away from creation screens.

```javascript
export default function CreateResource() {
  const navigate = useNavigate();
  
  // Redirect if user lacks permission
  useEffect(() => {
    if (!hasPermission("resource", "create")) {
      navigate("/resources");
    }
  }, [navigate]);
  
  // Rest of component...
}
```

## Resource/Action Mapping

| Resource | Create Permission | Edit Permission | Delete Permission |
|----------|-------------------|-----------------|-------------------|
| candidates | `candidates.create` | N/A | N/A |
| jobs | `jobs.create` | N/A | N/A |
| user | `user.create` | `user.edit` | `user.delete` |
| business_unit | `business_unit.create` | `business_unit.edit` | `business_unit.delete` |
| delivery_center | `delivery_center.create` | `delivery_center.edit` | `delivery_center.delete` |

## Checklist for Developers

When adding any create/edit/delete operation:

- [ ] Import `hasPermission` from `../utils/permissionsRoleTemplate`
- [ ] Hide button/UI element: `{hasPermission("resource", "action") && <Button>}`
- [ ] Add validation in handler function
- [ ] Add `useEffect` redirect in create/edit screen
- [ ] Test that:
  - Button is hidden when user lacks permission
  - Handler shows error if accessed anyway
  - Direct URL navigation redirects to list view

## Utilities

### `hasPermission(resource, action)`
Check if user has permission.

```javascript
hasPermission("candidates", "create")  // → true/false
hasPermission("jobs", "edit")         // → true/false
hasPermission("user", "delete")       // → true/false
```

### Permissions Storage
Permissions are stored in `localStorage.hrms_permissions` after login. Sourced from backend JWT token.

## Backend Integration

The backend returns permissions in the login response:

```json
{
  "access_token": "...",
  "permissions": {
    "candidates": {"can_view": true, "can_create": true, ...},
    "jobs": {"can_view": true, "can_create": false, ...},
    ...
  }
}
```

Frontend stores this in localStorage and checks it before rendering.

## Enforcement

- ✅ **UI Layer:** Buttons hidden for unauthorized users
- ✅ **Handler Layer:** Runtime check with user feedback
- ✅ **Route Layer:** Direct URL access redirected to list view
- ✅ **API Layer:** Backend validates permissions (returns 403)

## Files Implementing This Pattern

### ✅ COMPLETE (8 operations protected)
- Dashboard.js (2 operations)
- JobCreate.js (route protection)
- CandidateCreate.js (route protection)
- UsersAndAccessControl.js (3 operations)
- MyReferralsScreen.js (1 operation)

### ⏳ To Audit
- Other admin screens with creation operations
- Report/export operations requiring permissions
- Configuration management screens

## Future Improvements

1. **ESLint Rule:** Automated detection of unprotected navigation
   - Warn on `navigate()` without upstream permission check
   
2. **Code Generator:** Template for protected operations
   - Scaffold with permission checks included
   
3. **Permission Matrix UI:** Show what each role can do
   - Help users understand permission restrictions

## Testing

```javascript
// Test permission hiding
it('hides Create button when user lacks permission', () => {
  localStorage.setItem('hrms_permissions', JSON.stringify({
    candidates: {can_create: false}
  }));
  
  render(<CandidateScreen />);
  expect(screen.queryByText(/Create Candidate/)).not.toBeInTheDocument();
});

// Test redirect
it('redirects to list when accessing create without permission', () => {
  render(<CandidateCreate />);
  expect(navigate).toHaveBeenCalledWith('/candidates');
});
```

## Related Files

- Permission utility: `frontend/src/utils/permissionsRoleTemplate.js`
- Backend RBAC: `backend/app/services/role_template_permission_service.py`
- API: `/api/v1/auth/login` returns permissions in response

---

**Enforcement Date:** 2026-09-01  
**Last Review:** 2026-09-01
