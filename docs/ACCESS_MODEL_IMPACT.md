# Access Model Change — Impact Analysis (before any code)

**Date:** 2026-10-13 · **Status:** implemented 2026-10-13 (see "As built" at the end) · **Decision on record:** access = Manage Role permission set ∪ department add-on ∪ personal overrides

All numbers below come from the code in the working tree, production commit `0bcb2d6e`, and the `wros_dev` database. Production data itself was not queried.

---

## 1. What the system actually does today (facts, not intent)

| Concern | Decided by today | Source |
|---|---|---|
| What a user may do (555 gated routes, nav, buttons) | `users.role_template_id` → `role_template_permissions` | `RoleTemplatePermissionService.has_permission` (one choke point) |
| Level (MFA, BU-leader, partner, CEO checks) | `role_templates.hierarchy_level` | `authority.level()` |
| Sees all BUs | `role_templates.org_level_access` | `authority.is_org_level`, `visibility.py`, `bu_scope.py` |
| Function (Recruitment, Finance) | template `specialization` **or** user's department | `authority.in_function` |
| Home dashboard | **job title** → Manage Role level → position code | `authority.position()` |
| Personal overrides | `user_custom_permissions` | 1 file; **0 rows in dev** |

**Finding 1: roles barely differ today.** Startup seeding (`db_contract._initialize_rbac`, identical in prod `0bcb2d6e`) gives every *system* template every resource except `org-roles`. In dev:

| Template | Granted (of 242) | Users |
|---|---|---|
| Recruiter (×2 tenants) | 241 full CRUD | 12 |
| HR Manager, Finance Manager, Manager, User, Ops, "Super User" | 241 full CRUD | 1 |
| Admin, Super Admin | 242 | 2 |
| Partner / BU Head / Sales / Employee | 40 / 37 / 16 / 8 | 7 (Employee) |

A Recruiter can open Finance, P&L and Users & Access Control today, unless an admin revoked those rows in the editor (I can't see prod data).

**Finding 2: two sources of truth disagree.** Almost every template is at level 5, while job titles say CEO or BU Head:

| User | Title (Manage Role) | Template | Today's level | Home dashboard |
|---|---|---|---|---|
| am@blitzenx.com | CEO (L17) | Recruiter | 5 | CEO dashboard (via title) |
| superuser@blitzenx.com | BU Head (L14) | Super Admin | 5 | BU Head only if a named head |
| hr1/hr2/test@blitzenx.com | "HR Manager" (not a Manage Role) | Recruiter | 5 | default |
| recruiter1/2, login-test | "Recruiter" (not a Manage Role) | Recruiter | 5 | default |
| 12 others | none | Recruiter / Employee / Admin / Super User | 2–5 | default |

So **only 2 of 22 users map to one of the 19 Manage Roles**. "Recruiter" and "HR Manager" are functions, not levels. That is exactly why the department add-on is needed.

**Finding 3: there are duplicate templates per tenant.** Templates 1–5 belong to tenant 1 and 6–10 to tenant 3. There are 19 Manage Roles in each of 3 tenants (57 rows), and none of them carries permissions yet.

---

## 2. Blast radius by area

| # | Area | Files / call sites | What changes | Break risk | CI gate coverage |
|---|---|---|---|---|---|
| A | Permission check | 732 call sites in 125 files, all funnelled through `RoleTemplatePermissionService.has_permission` / `get_user_permissions` | One function computes the union instead of reading one template | **High blast, small surface.** A bug locks out or opens all 555 routes at once. | `test_roles_not_names`, `test_navigation_menu` (partial) |
| B | Authority levels | `authority.py` plus 13 callers (MFA, `create_job` BU-leader, `finance_monitoring` CEO, invoices, `core_pull`, `job_approval`, `partner_incentives`, `goals`) | Level comes from the Manage Role, not the template | **Medium.** Behaviour flips for am@ (5→17) and superuser@ (5→14). | `test_authority` |
| C | **Login / MFA** | `auth.py`, `mfa.py`; `MFA_TOTP_MIN_LEVEL=14` | Users at L14+ need TOTP | **High (user-visible).** am@ and superuser@ would be pushed into TOTP enrollment at their next login. | **None.** Gap: needs a test. |
| D | Data scope (BU, org-level) | `visibility.py`, `bu_scope.py`, `data_scope.py`, `revenue_visibility_scope.py` | `org_level_access` moves to Manage Role (CEO/CFO) or stays on the template | Medium: revenue and candidate lists widen or narrow | `test_bu_location_heads`; scope tests partial |
| E | Recruiter pool / round-robin | `recruiter_assignment_service`, `flash_service`, `job_approval_workflow_service` | Needs Recruitment department + candidates edit | **Medium.** Recruiters with no department drop out of auto-assignment and candidate creation stalls. | `test_recruiter_pool` |
| F | Home dashboard | `authority.position/home_dashboard` | Already title-based, so little change | Low | `test_authority`, `test_user_org_seat` |
| G | Navigation `/hr/me/navigation` | `navigation.py`, `init_resources` | Reads the new effective set | Low if A is right | `test_navigation_menu` |
| H | Writers of `role_template_id` | 21 files: `users`, `users_access_control`, `employees`, `employee_conversion_service`, `create_user_with_roles_handler`, `msgraph`, `invoice_service`, `opportunities`, `role_templates`, `security` (JWT), `database`, schemas | Decide whether the field stays (as the add-on) or is derived | Medium. Conversion and user creation must set the Manage Role. | `test_user_org_seat` partial |
| I | JWT payload | `security.create_access_token` carries `role_template_id` | Stale token after a role change, until refresh | Low (server re-reads the DB on each check) | none |
| J | Legacy `UserRole` string | 20 files, mostly dead "architect" services plus display uses | Untouched by this change | None | — |
| K | Frontend | `UserFormPage` (job_title + role_template_id), `UsersAndAccessControl`, `RoleTemplateEditor`, `EmployeeConversionScreen`, `Shell.js`, `Approutes.jsx`, `client.js`, `permissionsRoleTemplate.js`; localStorage `hrms_permissions`, `hrms_authority`, `hrms_roles`, `permission_role`, `hrms_role` | Form: Manage Role (level) + department (add-on) + overrides. Editor: edit permissions per Manage Role. | Medium. Stale localStorage hides or shows menus until re-login. | **None** (no frontend tests in gate) |

---

## 3. Per-user outcome if implemented naïvely (permissions read only from Manage Role)

| Group | Count | Result |
|---|---|---|
| Title maps to a Manage Role (am@ CEO, superuser@ BU Head) | 2 | Gets that role's set; TOTP now required |
| Title is a function (Recruiter, HR Manager) | 6 | **Loses all access** (no Manage Role) |
| No title | 14 | **Loses all access** |

**20 of 22 users would be locked out.** That's why the earlier WIP was parked.

## 4. Safe sequence (recommended)

1. **Additive schema only** (`db_contract` drift, nullable): `org_roles.role_template_id`, `users.org_role_id`. Don't touch or drop `users.role_template_id`.
2. **Backfill, idempotent, at startup.** Each Manage Role gets its own permission template, seeded from today's effective set for its level (nobody loses anything on day 1). Each user gets `org_role_id` from the title where it matches. Users with no match keep their current template as the add-on, so their access is identical.
3. **Switch the choke point (A)** to the union, with a **parity check**: for all 22 users, the effective set before must equal the set after. Ship only at 22/22.
4. **Levels (B/C)** move to the Manage Role, behind a TOTP grace period (enroll on next login, don't block).
5. **UI (K):** the user form gets Manage Role, department add-on and overrides. The Role editor lists the 19 Manage Roles plus department add-ons. Login refreshes localStorage.
6. **Tighten.** Remove the "everything" grants per role in the UI. That's a business step, done by you, not by code.

**Rollback:** steps 1–2 are additive. Reverting the code from step 3 returns to the template path untouched. No destructive migration happens in this release.

**New tests required before shipping:** a parity test (A), a login/MFA level test (C), a recruiter-pool-with-department test (E), and a frontend build plus route-guard smoke test (K).

---

## 5. Business decisions needed (only these)

1. **Day-1 access per Manage Role.** Recommended: identical to today, then tighten in the UI. The alternative is tightening now, which needs you to define 19 roles × 242 resources.
2. **Recruiter / HR Manager people.** Recommended: give each a level (e.g. Consultant / Manager) plus the Recruitment / HR department add-on.
3. **TOTP for am@ and superuser@ once they become L17 / L14.** Recommended: yes, with enroll-on-next-login.

---

## 6. As built (2026-10-13), after architect review

Changes from the plan above, from the architect review:
- **Role permission sets start EMPTY** (no adopting the Partner/BU Head templates, no self-service seed). Taking a role never widens access until an admin fills it.
- **No `users.org_role_id`**: the Job Title already points at the role (renames cascade to holders), so it stays the single pointer.
- **Tenant 2/3 lockout left as is** pending a business decision (OPEN_ITEMS decision 7).
- **Authenticator**: uses max(role level, add-on level).
- Guards: role sets can't be deleted/disabled; editing one needs `org-roles` edit; no self-edit of role/add-on; add-on must be enabled, same tenant, not a role set (users create/update, queue handler, employee conversion).
- Fixed on the way: duplicate resources (canonical row, grants moved, duplicates disabled), grant-only overrides missing from the menu, permission rows written without tenant, tenant-blind Employee default on conversion, `tenant_id` default 1 in the create-user handler, dead `PermissionHelper.get_user_permissions`.

Verification: 187/187 gate tests (10 new); parity over all 22 wros_dev users × every resource × action = 0 lost (7 gained Notifications, the duplicate-resource fix); GET sweep 199 routes, 0 × 5xx from code; frontend build clean; screens checked in the browser.
