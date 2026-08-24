# Create the markdown content
text = """
# Roles & Permissions – Short Implementation Plan

## 1. Define Roles
Create a **Roles table** to store all system roles.

Example roles:
- Super User
- BU Head
- Hiring Manager
- HR Manager
- HR Operations
- HRBP
- Recruitment Manager
- Recruitment Team Lead
- Recruiter
- Employee
- Consultant
- Candidate

---

## 2. Create Role Attributes
Attributes define **how a role behaves** in the system.

Examples:
- `global_access`
- `bu_restricted`
- `candidate_owner_only`
- `job_owner_only`
- `pipeline_control`
- `interview_control`
- `offer_control`
- `employee_data_access`
- `timesheet_access`
- `payroll_access`

Store these in **role_attributes table**.

---

## Final Goal

Implement **RBAC (Role-Based Access Control)** with:

- Roles
- Attributes
- Permissions
- BU-level security
- Ownership validation
"""

# Roles & Permissions

## Module 1 – Roles, Attributes & Permissions (Final)

---

## 1. Role Definition

A **Role** defines a type of user in the system.

Each role has:
- **Attributes** (behavior flags)
- **Permissions** (what actions they can perform)
- **Scope** (what data they can access)

---

## 2. Database Structure

### 2.1 Roles Table — `roles`

| column | type | description |
|--------|------|-------------|
| id | UUID | primary key |
| name | varchar | role name |
| description | text | description |
| created_at | timestamp | created |
| updated_at | timestamp | updated |

#### Example Records

| id | name |
|----|------|
| 1 | Super User |
| 2 | BU Head |
| 3 | Hiring Manager |
| 4 | HR Manager |
| 5 | HR Operations |
| 6 | HRBP |
| 7 | Recruitment Manager |
| 8 | Recruitment Team Lead |
| 9 | Recruiter |
| 10 | Employee |
| 11 | Consultant |
| 12 | Candidate |

---

## 3. Role Attributes

Attributes define how the role behaves in the system.

| Attribute | Meaning |
|-----------|---------|
| global_access | Can access all BUs |
| bu_restricted | Access limited to BU |
| candidate_owner_only | Can access only candidates they own |
| job_owner_only | Can access only jobs they opened |
| pipeline_control | Can move candidate pipeline |
| interview_control | Can schedule/edit interviews |
| offer_control | Can create/edit offers |
| employee_data_access | Can view employee data |
| timesheet_access | Can manage timesheets |
| payroll_access | Can view payroll |

---

## 4. Role Attributes Table — `role_attributes`

| column | type |
|--------|------|
| id | uuid |
| role_id | FK roles.id |
| attribute_name | varchar |
| attribute_value | boolean |
| created_at | timestamp |

#### Example: Recruiter Attributes

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| candidate_owner_only | false |
| job_owner_only | false |
| pipeline_control | true |
| interview_control | true |
| offer_control | false |

---

## 5. Permissions Table — `permissions`

| column | type |
|--------|------|
| id | uuid |
| name | varchar |
| description | text |

#### Permission Examples

| permission |
|------------|
| candidate.view |
| candidate.edit |
| candidate.create |
| job.view |
| job.create |
| job.edit |
| pipeline.move |
| interview.schedule |
| offer.create |
| offer.approve |
| employee.view |
| employee.edit |

---

## 6. Role Permission Mapping — `role_permissions`

| column | type |
|--------|------|
| role_id | FK |
| permission_id | FK |

---

## 7. Role Definitions With Attributes

### Super User
**Meaning:** Can view/edit everything

| attribute | value |
|-----------|-------|
| global_access | true |
| bu_restricted | false |
| candidate_owner_only | false |
| pipeline_control | true |
| offer_control | true |
| employee_data_access | true |

---

### BU Head
**Meaning:** Access entire BU — cannot access other BUs

| attribute | value |
|-----------|-------|
| global_access | false |
| bu_restricted | true |
| candidate_owner_only | false |
| job_owner_only | false |
| pipeline_control | true |
| offer_control | true |
| employee_data_access | true |

---

### Hiring Manager
**Meaning:** Can only access jobs they opened; can give interview feedback

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| job_owner_only | true |
| pipeline_control | false |
| interview_control | true |
| offer_control | false |

---

### HR Manager
**Meaning:** Full HR control inside BU

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| employee_data_access | true |
| payroll_access | true |
| timesheet_access | true |

---

### HR Operations
**Meaning:** Read-only HR data; can edit only candidates they own

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| employee_data_access | true |
| candidate_owner_only | true |
| pipeline_control | false |

---

### HRBP
**Meaning:** Can only manage candidates they own

| attribute | value |
|-----------|-------|
| candidate_owner_only | true |
| bu_restricted | true |
| pipeline_control | false |

---

### Recruitment Manager
**Meaning:** Full recruitment control for assigned roles

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| pipeline_control | true |
| interview_control | true |
| offer_control | true |

---

### Recruitment Team Lead
**Meaning:** Manage pipelines for assigned roles

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| pipeline_control | true |
| interview_control | true |

---

### Recruiter
**Meaning:** Manage candidates; cannot approve offers

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| pipeline_control | true |
| interview_control | true |
| offer_control | false |

---

### Employee
**Meaning:** Access own data; apply for internal jobs

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| timesheet_access | true |
| payroll_access | true |

---

### Consultant
**Meaning:** Limited employee access

| attribute | value |
|-----------|-------|
| bu_restricted | true |
| timesheet_access | true |
| payroll_access | true |

---

### Candidate
**Meaning:** Only access open jobs; cannot access internal system

| attribute | value |
|-----------|-------|
| global_access | false |
| bu_restricted | false |
| candidate_portal_access | true |

---

## 8. Permission Evaluation Logic

When a user performs an action:

**Step 1** — Fetch user role.

**Step 2** — Fetch role attributes.

**Step 3** — Fetch role permissions.

**Step 4** — Evaluate scope:
```
if role.global_access:
    allow

if role.bu_restricted:
    ensure entity.bu == user.bu
```

**Step 5** — Check ownership:
```
if role.candidate_owner_only:
    ensure candidate.owner_id == user.id
```

---

## 9. Acceptance Criteria

| ID | Criteria |
|----|----------|
| AC-1 | Recruiter in BU-A searches candidates → candidates locked in BU-B pipeline must not appear |
| AC-2 | BU Head sees all candidates in their BU |
| AC-3 | HRBP sees only candidates they own |
| AC-4 | Super User sees everything |

---

## 10. Dependency for Candidate Module

This module enables the next module: **Candidate Management**, which will enforce:

```
candidate.reserved = true
candidate.owner_bu = BU-A
```

Then search logic becomes:
```
if candidate.reserved = true
and candidate.owner_bu != user.bu
hide candidate
```

This ensures:
- Candidates are Org level
- BU independence
- No BU conflict over candidate