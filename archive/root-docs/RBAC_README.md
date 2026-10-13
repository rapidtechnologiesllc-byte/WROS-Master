# 🔐 RBAC — Role-Based Access Control

> **Audience:** Backend developers, frontend developers, and new team members.  
> **Base URL prefix:** `/api/v1/rbac`  
> **Auth required on all routes:** Yes — Bearer JWT token in `Authorization` header.

---

## Table of Contents

1. [What is RBAC?](#1-what-is-rbac)
2. [Core Concepts](#2-core-concepts)
3. [Database Models](#3-database-models)
4. [All Permissions (Seed Data)](#4-all-permissions-seed-data)
5. [Predefined Roles](#5-predefined-roles)
6. [How Authentication & Authorization Works](#6-how-authentication--authorization-works)
7. [API Reference — Roles](#7-api-reference--roles)
8. [API Reference — Permissions](#8-api-reference--permissions)
9. [API Reference — User Role & Business Unit](#9-api-reference--user-role--business-unit)
10. [API Reference — Business Units](#10-api-reference--business-units)
11. [Super User Bypass](#11-super-user-bypass)
12. [Frontend Integration Guide](#12-frontend-integration-guide)
13. [Common Errors](#13-common-errors)

---

## 1. What is RBAC?

RBAC (Role-Based Access Control) controls **what actions a logged-in user can perform** in the system.

Instead of hardcoding access rules per user, you:
1. Define **Permissions** (e.g., `candidate.view`, `document.upload`)
2. Create **Roles** (e.g., `HR Manager`, `Recruiter`) and assign permissions to them
3. Assign a **Role** to each user
4. Every API endpoint checks whether the current user's role has the required permission

```
User → has one Role → Role has many Permissions
```

---

## 2. Core Concepts

| Concept | Description | Example |
|---|---|---|
| **Permission** | A named string representing one action | `candidate.view`, `rbac.manage` |
| **Role** | A group of permissions | `HR Manager` |
| **Role Attribute** | Boolean flags attached to a role | `pipeline_control: true` |
| **Business Unit** | An organizational unit a user belongs to | `Engineering`, `Finance` |
| **Super User** | A special user type that bypasses ALL permission checks | `UserRole = "Super User"` |

---

## 3. Database Models

```
roles
  ├── id (PK)
  ├── name          (e.g., "HR Manager")
  └── description

role_attributes
  ├── id
  ├── role_id (FK → roles.id)
  ├── attribute_name   (e.g., "pipeline_control")
  └── attribute_value  (true/false)

permissions
  ├── id
  └── name   (e.g., "candidate.view")

role_permissions  (many-to-many join)
  ├── role_id (FK → roles.id)
  └── permission_id (FK → permissions.id)

users
  ├── UserID
  ├── UserRole       ("Super User", "HR", "Admin", etc.)
  ├── role_id        (FK → roles.id)  ← RBAC role
  └── business_unit_id (FK → business_units.id)

business_units
  ├── id
  ├── name
  └── description
```

---

## 4. All Permissions (Seed Data)

These are the standard permissions seeded into the database. Use the exact string when applying guards on the backend or checking access on the frontend.

| Permission String | What it Allows |
|---|---|
| `rbac.manage` | Create/update/delete roles, permissions, business units; assign roles to users |
| `candidate.view` | View candidate list and details |
| `candidate.create` | Create new candidates |
| `candidate.edit` | Edit candidate information |
| `candidate.delete` | Delete a candidate and all associated records |
| `document.view` | View documents uploaded by candidates |
| `document.upload` | Upload documents on behalf of a candidate (HR) |
| `document.verify` | Mark a document as verified or rejected |
| `interview.manage` | Create, update, schedule, and delete interviews/panels |
| `offer.manage` | Create and send offer letters |
| `onboarding.manage` | Manage the full onboarding workflow |

---

## 5. Predefined Roles

These roles are typically seeded at startup. Each role is a bundle of the permissions above.

| Role Name | Key Permissions |
|---|---|
| **Super User** | Bypasses all checks — full access |
| **HR Manager** | All permissions except `rbac.manage` |
| **Recruiter** | `candidate.view`, `candidate.create`, `candidate.edit`, `interview.manage` |
| **Interviewer** | `candidate.view`, `interview.manage` |
| **Admin** | `rbac.manage` + all HR Manager permissions |

> ⚠️ Actual permissions per role depend on what was seeded in your database. Use `GET /rbac/roles/{role_id}` to inspect a role's permissions at runtime.

---

## 6. How Authentication & Authorization Works

### Step 1 — User logs in
```
POST /api/v1/auth/login
→ Returns: { access_token: "eyJ..." }
```

### Step 2 — Frontend stores the token
Store in memory or `localStorage`. Send on every request:
```http
Authorization: Bearer eyJ...
```

### Step 3 — Backend validates the token
Every protected endpoint:
1. Decodes the JWT and identifies the user
2. Loads the user's `role_id` from the database
3. Checks if the role has the required permission string (e.g., `candidate.view`)
4. If the user is a **Super User** → skips step 3 entirely

### Step 4 — Access granted or denied
- ✅ `200 / 201 / 204` — allowed
- ❌ `403 Forbidden` — logged in but missing permission
- ❌ `401 Unauthorized` — token missing, expired, or invalid

---

## 7. API Reference — Roles

> **Required Permission:** `rbac.manage`

### `GET /rbac/roles`
List all roles.

**Response:**
```json
[
  { "id": 1, "name": "HR Manager", "description": "Full HR access" },
  { "id": 2, "name": "Recruiter", "description": null }
]
```

---

### `POST /rbac/roles`
Create a new role.

**Request body:**
```json
{ "name": "Finance Manager", "description": "Finance team access" }
```

**Response:** `201 Created`
```json
{ "id": 5, "name": "Finance Manager", "description": "Finance team access" }
```

---

### `GET /rbac/roles/{role_id}`
Get a role with its full permissions and attributes.

**Response:**
```json
{
  "id": 1,
  "name": "HR Manager",
  "description": "Full HR access",
  "created_at": "2026-03-01T10:00:00",
  "attributes": [
    { "id": 1, "role_id": 1, "attribute_name": "pipeline_control", "attribute_value": true }
  ],
  "permissions": [
    { "id": 1, "name": "candidate.view", "description": null, "created_at": "..." },
    { "id": 2, "name": "candidate.create", "description": null, "created_at": "..." }
  ]
}
```

---

### `PUT /rbac/roles/{role_id}`
Update a role's name or description.

**Request body:**
```json
{ "name": "Senior HR Manager", "description": "Updated description" }
```

---

### `DELETE /rbac/roles/{role_id}`
Delete a role. Returns `204 No Content`.

---

### `POST /rbac/roles/{role_id}/permissions`
Assign a permission to a role. **Idempotent** (safe to call multiple times).

**Request body:**
```json
{ "permission_id": 3 }
```
Returns `204 No Content`.

---

### `DELETE /rbac/roles/{role_id}/permissions/{permission_id}`
Remove a permission from a role. Returns `204 No Content`.

---

## 8. API Reference — Permissions

> **Required Permission:** `rbac.manage`

### `GET /rbac/permissions`
List all permissions.

**Response:**
```json
[
  { "id": 1, "name": "candidate.view", "description": null, "created_at": "..." },
  { "id": 2, "name": "candidate.create", "description": null, "created_at": "..." }
]
```

---

### `POST /rbac/permissions`
Create a new custom permission.

**Request body:**
```json
{ "name": "report.export", "description": "Allow exporting reports" }
```

Returns `201 Created`.

---

### `DELETE /rbac/permissions/{permission_id}`
Delete a permission. Returns `204 No Content`.

---

## 9. API Reference — User Role & Business Unit

> **Required Permission:** `rbac.manage`

### `GET /rbac/users/{user_id}/permissions`
Get a user's full permission summary based on their assigned role.

**Response:**
```json
{
  "user_id": "USR-abc123",
  "role_id": 1,
  "role_name": "HR Manager",
  "permissions": ["candidate.view", "candidate.create", "document.verify"],
  "attributes": { "pipeline_control": true }
}
```

---

### `GET /rbac/users/{user_id}/role`
Get the role assigned to a user.

**Response:**
```json
{ "id": 1, "name": "HR Manager", "description": "Full HR access" }
```

**Errors:**
- `404` — User not found, or no role assigned

---

### `POST /rbac/users/{user_id}/assign-role`
Assign a role to a user.

**Request body:**
```json
{ "role_id": 2 }
```
Returns `204 No Content`.

---

### `DELETE /rbac/users/{user_id}/role`
Remove the assigned role from a user. Returns `204 No Content`.

---

### `GET /rbac/users/{user_id}/business-unit`
Get the business unit assigned to a user.

**Response:**
```json
{
  "id": 3,
  "name": "Engineering",
  "description": "Engineering division",
  "created_at": "2026-03-01T10:00:00"
}
```

**Errors:**
- `404` — User not found, or no business unit assigned

---

### `POST /rbac/users/set-business-unit`
Assign a business unit to a user.

**Request body:**
```json
{ "user_id": "USR-abc123", "business_unit_id": 3 }
```

**Response:**
```json
{ "user_id": "USR-abc123", "business_unit_id": 3, "message": "Business unit assigned successfully" }
```

---

### `PUT /rbac/users/{user_id}/business-unit`
Update a user's business unit.

**Request body:**
```json
{ "user_id": "USR-abc123", "business_unit_id": 5 }
```

---

## 10. API Reference — Business Units

> **Required Permission:** `rbac.manage`

### `GET /rbac/business-units`
List all business units.

**Response:**
```json
[
  { "id": 1, "name": "HR", "description": null },
  { "id": 2, "name": "Engineering", "description": "Tech team" }
]
```

---

### `POST /rbac/business-units`
Create a new business unit.

**Request body:**
```json
{ "name": "Finance", "description": "Finance division" }
```

Returns `201 Created`. Returns `409 Conflict` if name already exists.

---

### `GET /rbac/business-units/{business_unit_id}`
Get a single business unit by ID.

---

### `PUT /rbac/business-units/{business_unit_id}`
Update a business unit's name or description.

---

### `DELETE /rbac/business-units/{business_unit_id}`
Delete a business unit. Returns `204 No Content`.

---

## 11. Super User Bypass

Any user with `UserRole = "Super User"` in the `users` table **bypasses all permission checks** and can call every API endpoint.

This is the escape hatch for system administrators.

> 🔴 **Never assign Super User role to regular HR or recruiter accounts.**

---

## 12. Frontend Integration Guide

### Checking if the current user has a permission

After login, call the permissions summary endpoint and store the result:

```js
// After login
const res = await fetch(`/api/v1/rbac/users/${userId}/permissions`, {
  headers: { Authorization: `Bearer ${token}` }
});
const { permissions, role_name } = await res.json();

// Store in state/context
setUserPermissions(permissions);  // ["candidate.view", "candidate.create", ...]
setUserRole(role_name);           // "HR Manager"
```

Then use it to **show/hide UI elements**:

```jsx
// Show "Create Candidate" button only if user has permission
{permissions.includes("candidate.create") && (
  <button onClick={createCandidate}>+ New Candidate</button>
)}

// Show "Verify Document" button only for document verifiers
{permissions.includes("document.verify") && (
  <button onClick={verifyDoc}>✔ Verify</button>
)}

// Show RBAC settings page only for admins
{permissions.includes("rbac.manage") && (
  <NavLink to="/admin/rbac">RBAC Settings</NavLink>
)}
```

### Recommended: Create a permission hook

```js
// hooks/usePermission.js
export function usePermission(permission) {
  const { permissions } = useAuth(); // your auth context
  return permissions.includes(permission);
}

// Usage
const canVerify = usePermission("document.verify");
```

### Setting up a user (Admin workflow)

```
1. Create user account (POST /api/v1/auth/register or HR creates)
2. Assign RBAC role:   POST /rbac/users/{user_id}/assign-role  { role_id: 1 }
3. Assign business unit: PUT /rbac/users/{user_id}/business-unit { user_id, business_unit_id: 2 }
```

---

## 13. Common Errors

| HTTP Code | Meaning | Common Cause |
|---|---|---|
| `401 Unauthorized` | Token missing or expired | User not logged in, or token expired |
| `403 Forbidden` | Logged in but no permission | User's role doesn't have the required permission |
| `404 Not Found` | Resource doesn't exist | Wrong role ID, user ID, or permission ID |
| `409 Conflict` | Duplicate name | Role or permission with that name already exists |
| `500 Internal Server Error` | Backend error | Check server logs |

### "I have a valid token but keep getting 403"

1. Check if the user has a role assigned: `GET /rbac/users/{user_id}/role`
2. Check the role's permissions: `GET /rbac/roles/{role_id}`
3. Make sure the required permission string is assigned to that role
4. If the user should have full access, set `UserRole = "Super User"` in the database

---

*Last updated: March 2026 | Backend: FastAPI + SQLAlchemy + SQL Server*
