# Comprehensive Business Unit Audit - ALL Screens & Sub-Screens (2026-08-12)

## Executive Summary
All 53 screens audited. **BU Required: 35 screens** | **BU Not Applicable: 18 screens**

This document maps every screen in WROS to its BU requirement and lists implementation priorities.

---

## Navigation Structure & BU Applicability

### 🎯 SECTION 1: PERSONAL (Universal - No BU Gating)
These are user self-service screens - visible to all logged-in users regardless of role/BU.

| Screen | Path | BU Required? | Notes | Priority |
|--------|------|--------------|-------|----------|
| **Dashboard** | /dashboard | ❌ NO | Welcome page, org-wide view | - |
| **My Tasks** | /my-tasks | ⚠️ OPTIONAL | User's personal tasks (may span BUs) | Medium |
| **My Timesheet** | /my-timesheet | ✅ YES | Employee's timesheet (employee has bu_id) | High |
| **My Expenses** | /my-expenses | ✅ YES | Employee expenses (expense has business_unit_id) | High |

---

### 🎯 SECTION 2: RECRUITMENT
Core hiring funnel. **ALL require BU scoping**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Candidates** | /candidates | ✅ YES | Candidate list + search | ✅ Model updated, need UI filter + column |
| **Jobs** | /jobs | ✅ YES | Job list + creation | ✅ Model has BU, need display + filter |
| **Candidate Review** | /hm-candidate-review | ✅ YES | HM reviews candidates | Auto-filter by candidate's BU |
| **Offer Letters** | /offer-letters | ✅ YES | Offer letter list | ✅ Model updated, need column + filter |
| **Offer Letters (New)** | /offers-listing | ✅ YES | Create new offers | ✅ Model updated, need BU selector |
| **Offer Screen** | /offer | ✅ YES | Individual offer details | Auto-show from candidate's BU |
| **Submissions** | /submissions | ✅ YES | Candidate submissions to jobs | ✅ DONE - auto-assign on POST |
| **Assignments** | /assignments | ✅ YES | Candidate assignments to managers | Auto-filter by candidate's BU |
| **Pre-Onboarding** | /pre-onboarding | ✅ YES | Document collection for new hires | Auto-filter by candidate's BU |
| **HTD Intake** | /htd-intake | ✅ YES | HTD program enrollment | Auto-filter by employee's bu_id |
| **HM Candidate Review** | /hm-candidate-review | ✅ YES | (Alt: Candidate Review) | Auto-filter by candidate's BU |
| **Intervention Queue** | /intervention-queue | ✅ YES | Escalation queue | Auto-filter by candidate's BU |
| **Rehire Approvals** | /rehire-approvals | ✅ YES | Rehire decision gate | Auto-filter by candidate's BU |
| **Bulk Launch** | /bulk-launch | ✅ YES | CSV import + bulk submission | BU selector + validation |
| **Message Templates** | /message-templates | ⚠️ OPTIONAL | Org-wide templates, but can scope to BU | Template library management |
| **Newsletter Screen** | /newsletter | ⚠️ OPTIONAL | Org-wide communication | Can scope send lists by BU |

**Recruitment Subtotals:** 14 screens require BU ✅ | 2 optional ⚠️

---

### 🎯 SECTION 3: WORKFORCE MANAGEMENT
Employee lifecycle + resource management. **ALL require BU scoping**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Employees** | /employees | ✅ YES | Employee list + search | Employee has bu_id, need display + filter |
| **Convert to Employee** | /employee-conversion | ✅ YES | Candidate → Employee flow | ✅ DONE - BU selector + role assignment |
| **Allocations** | /allocations | ✅ YES | Employee project allocation | ✅ Employee has bu_id, need BU filter |
| **Projects** | /projects | ✅ YES | Client projects list | ✅ Project may have BU, need filter |
| **Resource Management** | /resource-management | ✅ YES | Resource pool mgmt | Filter by BU + pool visibility |
| **Core-Pull & Pool Guard** | /core-pull | ✅ YES | Speciality → Core transition | Auto-filter by employee's bu_id |
| **Buddy Program** | /buddy-program | ✅ YES | 30-day onboarding tracking | Auto-filter by employee's bu_id |
| **Utilization & Bench Cost** | /utilization-dashboard | ✅ YES | Bench utilization metrics | Auto-group by employee's bu_id |
| **Demand Confirmation** | /demand-confirmation | ✅ YES | Hiring manager confirms demand | Auto-filter by demand's BU |

**Workforce Subtotals:** 9 screens require BU ✅

---

### 🎯 SECTION 4: SALES & BUSINESS DEVELOPMENT
Pipeline + opportunity management. **ALL require BU scoping**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Client Management** | /client-management | ✅ YES | Client list + CRUD | ✅ Client has business_unit_id, need filter |
| **Opportunity Pipeline** | /opportunity-pipeline | ✅ YES | Sales pipeline Kanban | ✅ Added business_unit_id, need BU filter |
| **Submissions** | /submissions | ✅ YES | (Also in Recruitment) | Already counted above |

**Sales Subtotals:** 2 additional screens (Client + Opportunity) ✅

---

### 🎯 SECTION 5: FINANCE & REPORTING
ALL financial data MUST be BU-scoped. **ALL require BU scoping**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Invoices** | /invoices | ✅ YES | Invoice list + approval | ✅ Added business_unit_id, need BU filter + grouping |
| **Timesheets** | /timesheets | ✅ YES | Timesheet approval list | ✅ Added business_unit_id, need BU filter + column |
| **Revenue** | /revenue | ✅ YES | Revenue by client/employee | Filter by BU + group by BU |
| **Finance Operations** | /finance-operations | ✅ YES | Finance dashboard + reconciliation | Filter all data by BU |
| **Forecast** | /forecast | ✅ YES | Revenue forecast by BU | ✅ Already BU-scoped in backend |
| **Forecast vs Actual** | /forecast-vs-actual | ✅ YES | Actual vs forecast comparison | Group by BU |

**Finance Subtotals:** 6 screens require BU ✅

---

### 🎯 SECTION 6: EXECUTIVE & ANALYTICS
Executive dashboards + KPI tracking. **MOST require BU option or cross-BU view**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Executive Revenue Dashboard** | /executive-revenue-dashboard | ⚠️ OPTIONAL | Exec view - may want cross-BU | Add BU filter/toggle for drill-down |
| **Partner ROI Agent** | /partner-roi | ⚠️ OPTIONAL | Partner's BU performance only | Filter by partner's assigned BU(s) |
| **CEO FY Progress** | /ceo-fy-progress | ⚠️ OPTIONAL | Org-wide FY metrics | Add BU breakdown option |
| **CFO Agent** | /cfo-dashboard | ⚠️ OPTIONAL | CFO finance view (cross-BU) | Default: all BUs, can filter |
| **Risk Dashboard** | /risk-dashboard | ✅ YES | Candidate at-risk tracking | Auto-filter by candidate's BU |
| **Thunder Analytics** | /thunder-analytics | ✅ YES | Thunder agent performance | Filter by BU + show BU breakdown |
| **Executive Signal** | /executive-signal | ⚠️ OPTIONAL | Culture + recognition (org-wide) | Can filter by BU optionally |
| **Admin Weekly Recap** | /admin-weekly-recap | ⚠️ OPTIONAL | Weekly executive summary | Can add BU breakdown |

**Executive Subtotals:** 2 required ✅ | 6 optional ⚠️

---

### 🎯 SECTION 7: ADMIN & CONFIGURATION
System administration. **MOST require BU consideration**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Users & Access Control** | /users-access-control | ✅ YES | User management | ✅ DONE - BU field + multi-role selector |
| **Tenant Locale & Currency** | /tenant-locale | ❌ NO | Org-wide settings (not BU-scoped) | - |
| **AI Configuration** | /tenant-ai-config | ❌ NO | Org-wide Thunder config (not BU-scoped) | - |
| **Ticket Routing & SLA** | /ticket-routing-admin | ⚠️ OPTIONAL | Help desk routing (can be BU-aware) | Optional BU assignment for routing |
| **Admin Settings** | /admin-settings | ❌ NO | Global system settings | - |
| **Error Log** | /error-log | ⚠️ OPTIONAL | System error tracking (can filter by BU context) | Optional BU filter for debugging |
| **Business Units** | /business-units | ❌ NO | BU management (meta-data) | - |

**Admin Subtotals:** 1 required ✅ | 2 optional ⚠️ | 4 not applicable ❌

---

### 🎯 SECTION 8: COLLABORATION & COMMUNICATION
Team communication tools. **SOME require BU context**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Thunder Chat** | /thunder-chat | ⚠️ OPTIONAL | AI recruiter chat | Candidate context auto-includes BU |
| **Public Thunder Chat** | /public-thunder-chat | ⚠️ OPTIONAL | Candidate-facing chat portal | Candidate's BU context shown |
| **Candidate Portal** | /candidate-portal | ✅ YES | Candidate self-service portal | Show candidate their assigned BU |
| **Candidate Search** | /candidate-search | ✅ YES | Full-text search | ✅ Need BU filter in results |
| **Candidate Details Screen** | /candidate/{id} | ✅ YES | Individual candidate profile | ✅ Show business_unit_id + name |
| **Candidate Self-Service** | /candidate-self-service | ⚠️ OPTIONAL | Candidate profile update | Candidate's BU context shown |
| **Candidate Create** | /candidate-create | ✅ YES | Create new candidate | Optional: pre-fill BU if user has one |
| **Job Workspace** | /job/{id} | ✅ YES | Job detail + workspace | ✅ Show job's business_unit_id |
| **Documents** | /documents | ⚠️ OPTIONAL | Document library | Can filter by BU context |
| **Verification** | /verification | ⚠️ OPTIONAL | Document verification | Candidate's BU context shown |
| **Checklist Templates** | /checklist-templates | ⚠️ OPTIONAL | Org-wide templates | Can create BU-specific variants |

**Collaboration Subtotals:** 4 required ✅ | 6 optional ⚠️ | 1 not applicable ❌

---

### 🎯 SECTION 9: INTERVIEW & HIRING PROCESS
Interview tracking + decision workflows. **ALL require BU context**.

| Screen | Path | BU Required? | Current State | Implementation |
|--------|------|--------------|----------------|-----------------|
| **Candidate Review** | /hm-candidate-review | ✅ YES | (Same as Recruitment section) | Already counted |
| **Interview Schedule** | /interview-schedule | ✅ YES | Schedule new interviews | Auto-filter by job's BU |
| **Interview Status** | /interview-status | ✅ YES | Interview status tracking | Auto-filter by candidate's BU |
| **Interview Analytics** | /interview-analytics | ✅ YES | Interview metrics + trends | Group by BU + show BU breakdown |
| **Job Details** | /job/{id} | ✅ YES | Job details + candidates | ✅ Show job's business_unit_id |
| **Active Jobs** | /active-jobs | ✅ YES | Open positions list | ✅ Show business_unit_id + filter |
| **Jobs Overview** | /jobs-overview | ✅ YES | Dashboard of all jobs | ✅ Group by business_unit_id |
| **Matching Jobs** | /matching-jobs | ✅ YES | Jobs matching candidate skills | Auto-filter by candidate's BU |
| **Job Create** | /job-create | ✅ YES | Create new job | ✅ BU is required field (mandatory) |

**Interview Subtotals:** 9 screens require BU ✅

---

## Implementation Summary

### ✅ REQUIRED - Business Unit MUST Apply (35 Screens)
These screens display/manage data that is fundamentally BU-scoped:

**Recruitment (14):**
- Candidates, Jobs, Candidate Review, Offer Letters (both), Submissions, Assignments
- Pre-Onboarding, HTD Intake, Intervention Queue, Rehire Approvals, Bulk Launch
- Plus: Interview Status, Interview Analytics, Candidate Portal

**Workforce (9):**
- Employees, Convert to Employee, Allocations, Projects, Resource Management
- Core-Pull, Buddy Program, Utilization, Demand Confirmation

**Finance & Reporting (6):**
- Invoices, Timesheets, Revenue, Finance Operations, Forecast, Forecast vs Actual

**Sales (2):**
- Client Management, Opportunity Pipeline

**Admin & Access (1):**
- Users & Access Control (✅ ALREADY DONE)

**Executive (2):**
- Risk Dashboard, Thunder Analytics

**Collaboration (4):**
- Candidate Portal, Candidate Search, Candidate Details, Candidate Create, Job Workspace

**Interview (4):**
- Interview Schedule, Interview Status, Interview Analytics, Job Details, Active Jobs, Jobs Overview, Matching Jobs, Job Create

---

### ⚠️ OPTIONAL - Business Unit Context Helpful (18 Screens)
These can benefit from BU context but don't strictly require it:

- My Tasks (may span BUs)
- Message Templates (can scope to BU)
- Newsletter (can scope send lists)
- Executive Revenue Dashboard (exec cross-BU view)
- Partner ROI Agent (partner's BUs)
- CEO FY Progress (can add BU breakdown)
- CFO Agent (cross-BU default, can filter)
- Executive Signal (org-wide, optional BU filter)
- Admin Weekly Recap (can add BU breakdown)
- Ticket Routing (can be BU-aware)
- Error Log (can filter by BU context)
- Thunder Chat (candidate context auto-includes BU)
- Public Thunder Chat (candidate context shown)
- Candidate Self-Service (candidate BU context)
- Documents (can filter by BU context)
- Verification (candidate BU context)
- Checklist Templates (can create BU variants)

---

### ❌ NOT APPLICABLE - Business Unit Does NOT Apply (5 Screens)
These are org-wide system settings/configuration:

- **Dashboard** - Welcome page
- **Tenant Locale & Currency** - Org-wide settings
- **AI Configuration** - Org-wide Thunder config
- **Admin Settings** - Global system config
- **Business Units** - BU meta-data screen itself

---

## Implementation Roadmap

### 🔥 PHASE 1: CRITICAL FINANCE & OPERATIONS (Week 1)
**Must be done first - CEO/CFO blockers**

- [ ] **Invoices Screen** - BU filter + column + grouping
- [ ] **Timesheets Screen** - BU filter + column + approval scoping
- [ ] **Finance Operations** - BU filter on all reconciliation data
- [ ] **Forecast + Forecast vs Actual** - Verify BU grouping works
- [ ] **Revenue Screen** - BU filter + breakdown

**Impact:** Finance can run reports by BU, invoices properly scoped to BU

---

### 🔴 PHASE 2: RECRUITMENT & HIRING (Week 1-2)
**Core business process - highest volume screens**

- [ ] **Candidates List** - BU column + filter dropdown
- [ ] **Jobs List** - BU column + filter + required field in create form
- [ ] **Job Details** - Show business_unit_id prominently
- [ ] **Job Create** - BU as required field (with validation)
- [ ] **Candidate Details** - Show BU assignment + how it was set
- [ ] **Offer Letters** - BU column + filter + grouping
- [ ] **Submissions** - ✅ DONE (auto-assign backend), just verify UI
- [ ] **Interview Schedule/Status** - Auto-filter by job/candidate BU
- [ ] **Bulk Launch** - BU selector + validation in CSV import

**Impact:** All candidates and jobs properly scoped, hiring managers see only their BU data

---

### 🟠 PHASE 3: WORKFORCE MANAGEMENT (Week 2)
**Employee lifecycle - ongoing HR functions**

- [ ] **Employees List** - BU column + filter
- [ ] **Employee Conversion** - ✅ DONE (BU selector in form)
- [ ] **Allocations** - BU filter + show employee's BU in table
- [ ] **Projects** - BU assignment + filter (if project has BU)
- [ ] **Resource Management** - BU filter + pool visibility per BU
- [ ] **Core-Pull Screen** - Auto-filter by employee's bu_id
- [ ] **Buddy Program** - Auto-filter by employee's bu_id
- [ ] **Utilization Dashboard** - Group by BU + show BU breakdown
- [ ] **Demand Confirmation** - Auto-filter by demand's BU

**Impact:** HR can manage employees and resources per BU, prevent cross-BU assignment issues

---

### 🟡 PHASE 4: SALES & EXECUTIVE (Week 3)
**Revenue visibility + executive dashboards**

- [ ] **Client Management** - BU filter + assignment
- [ ] **Opportunity Pipeline** - BU filter + Kanban grouping by BU
- [ ] **Executive Revenue Dashboard** - BU toggle/dropdown (all BUs default)
- [ ] **Partner ROI Agent** - Filter to partner's assigned BU(s)
- [ ] **Risk Dashboard** - BU filter + grouping
- [ ] **Thunder Analytics** - BU filter + breakdown

**Impact:** Sales visibility by BU, executives can see BU-specific performance

---

### 🟢 PHASE 5: OPTIONAL ENHANCEMENTS (Week 4+)
**Nice-to-haves and future optimization**

- [ ] **My Tasks** - Optional BU filter
- [ ] **Message Templates** - BU scope options
- [ ] **Ticket Routing** - BU-aware routing rules
- [ ] **Executive Signal** - BU filter option
- [ ] **Checklist Templates** - BU-specific variants

---

## Database Support Status

### ✅ READY (Already have business_unit_id + FK + Index)
- Users, Jobs, Candidate, Opportunity, EmployeePerformanceEvent, Timesheet, Invoice, Task
- Client, Expense, Employee (bu_id)

### ✅ MODELS & RELATIONSHIPS CONFIGURED
- All models have `business_unit = relationship("BusinessUnit")` defined
- All responses updated to include business_unit_id and business_unit_name

### ✅ API ENDPOINTS READY
- PUT /hr/users/{user_id} - update with BU
- POST /hr/users/{user_id}/assign-bu - assign BU
- POST /submissions - auto-assign candidate BU
- GET /hr/users/search?business_unit=NA - filter by BU

### ⏳ SCHEMAS TO UPDATE
- None critical - responses already include BU info

---

## Frontend Implementation Checklist

### For Each REQUIRED Screen:
- [ ] Add BU column to table/list (if list screen)
- [ ] Add BU filter dropdown (if list screen)
- [ ] Display business_unit_name on detail screens
- [ ] Auto-populate/auto-filter based on context:
  - Candidate screens: filter by candidate.business_unit_id
  - Employee screens: filter by employee.bu_id
  - Job screens: filter by job.business_unit_id
  - Invoice/Timesheet: filter by that entity's business_unit_id
- [ ] Ensure BU is required field in create forms (Jobs)
- [ ] Ensure BU selector in multi-form screens (Job Create, Employee Conversion)

### For Each OPTIONAL Screen:
- [ ] Add BU toggle/filter (doesn't need to be default visible)
- [ ] Clearly label cross-BU data if showing it

---

## UI Pattern Standards

### List Screen with BU Filtering
```
[Search Box] [BU Filter Dropdown] [Status Filter] [Advanced Filters]

| Name | BU | Status | Action |
|------|-------|--------|--------|
```

### Detail Screen with BU Display
```
[Header] Business Unit: [BU Name]
[Other fields...]
```

### Create Form with BU Requirement
```
Job Title: [text input]
Business Unit: [dropdown - REQUIRED]
Department: [dropdown - depends on BU selected]
```

### Auto-Filtering Pattern
```javascript
useEffect(() => {
  if (currentUser?.business_unit_id) {
    // Auto-filter list by user's BU
    setFilter({ business_unit_id: currentUser.business_unit_id })
  }
}, [currentUser?.business_unit_id])
```

---

## Validation Rules for Implementation

1. **No Cross-BU Data Leakage** - All lists must filter by BU context
2. **Required on Creation** - Jobs MUST have business_unit_id selected
3. **Display Always** - BU name always visible on detail screens
4. **Filter Default** - Auto-filter to user's BU if they have one assigned
5. **Immutable Logic** - BU assignment immutable once set (for audit trail)

---

## Risk Mitigations

### Risk: User views competitor's data (wrong BU)
**Mitigation:** Frontend filters + backend enforces scope via tenant_id/business_unit_id

### Risk: BU field required but user doesn't know which to choose
**Mitigation:** Auto-populate from user's own business_unit_id if available

### Risk: Executive wants cross-BU view but can't get it
**Mitigation:** Executive/Finance roles can leave BU filter blank to see all

### Risk: Historical data has no BU assigned
**Mitigation:** Gracefully handle NULL BU values, show "Unassigned" in UI

---

## Testing Checklist

- [ ] List screens filter correctly by BU
- [ ] Detail screens display BU info
- [ ] Create forms accept BU input
- [ ] Auto-filters work for user's BU
- [ ] Cross-BU users (Finance) can see all data
- [ ] Single-BU users can only see their BU data
- [ ] BU-less candidates handled gracefully
- [ ] No 404s or errors with BU filters
- [ ] Performance: BU indices are being used

---

## Commit Strategy

**Commit per screen or screen group:**
- `Impl: Add BU filtering to Candidates list screen`
- `Impl: Add BU management to Employee Conversion screen`
- `Impl: Add BU scoping to all Finance screens`

**No mega-commits** - keep changes focused and reviewable.

---

## Success Criteria

✅ **Done when:**
1. All 35 REQUIRED screens have BU filtering/display
2. All 6 FINANCE screens have BU grouping/reporting
3. Users can only see data for their assigned BU(s)
4. Finance/Executive roles can optionally see all BUs
5. No cross-BU data leakage
6. All tests pass
7. End-to-end workflow: candidate → employee, properly scoped by BU

---

**Total Implementation Effort:** ~80-100 hours
- Frontend: ~60-80 hours (UI updates across 35 screens)
- Testing: ~20 hours (regression + BU-specific scenarios)
- Backend: ✅ DONE (0 additional hours needed)

**Timeline:** 2-3 weeks for Phase 1-3 (critical path), 1-2 weeks for Phase 4-5

