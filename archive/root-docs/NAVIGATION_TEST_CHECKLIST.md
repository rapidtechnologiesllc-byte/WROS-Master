# Navigation Testing Checklist - Complete Audit

**Date:** 2026-08-23  
**Purpose:** Systematically test EVERY navigation item to identify defects

---

## Testing Instructions

For each item, click it and check:
- ✅ **Loads** - Page displays without error
- ⚠️ **No Data** - Page loads but shows empty/0 data
- ❌ **Broken** - Blank page, 404, error, or doesn't load

Record any errors seen in browser console.

---

## PERSONAL NAVIGATION (Top Right Menu)

| Item | URL | Status | Notes/Error |
|------|-----|--------|-------------|
| Dashboard | `/` | ❌ BROKEN | - |
| My Tasks | `/my-tasks` | ❌ BROKEN | - |
| My Timesheet | `/my-timesheet` | ❌ BROKEN | - |
| My Expenses | `/my-expenses` | ❌ BROKEN | - |
| My Referrals | `/my-referrals` | ❌ BROKEN | - |

---

## EXECUTIVE DASHBOARDS MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| CEO Dashboard | `/ceo-fy-progress` | ⚠️ NO DATA | Loads page but 0 data |
| CFO Dashboard | `/cfo-dashboard` | ⏳ TEST | [ ] |
| Partner Dashboard | `/troy-partner-dashboard` | ⏳ TEST | [ ] |
| BU Head Dashboard | `/bu-head-dashboard` | ⏳ TEST | [ ] |
| Executive Overview | `/executive-overview` | ⏳ TEST | [ ] |
| KPI Metrics | `/kpi-metrics` | ⏳ TEST | [ ] |
| Financial Summary | `/financial-summary` | ⏳ TEST | [ ] |

---

## RECRUITMENT MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Candidates | `/candidates` | ⏳ TEST | [ ] |
| Jobs | `/jobs` | ⏳ TEST | [ ] |
| Candidate Review | `/hm-candidate-review` | ⏳ TEST | [ ] |
| Offer Letters | `/offers` | ⏳ TEST | [ ] |
| Submissions | `/submissions` | ⏳ TEST | [ ] |
| Intervention Queue | `/recruiter/intervention-queue` | ⏳ TEST | [ ] |
| Rehire Approvals | `/recruiter/rehire-approvals` | ⏳ TEST | [ ] |
| Risk Dashboard | `/recruiter/risk-dashboard` | ⏳ TEST | [ ] |
| Thunder Analytics | `/recruiter/thunder-analytics` | ⏳ TEST | [ ] |
| Bulk Launch | `/recruiter/bulk-launch` | ⏳ TEST | [ ] |

### Recruitment Sub-Pages
| Parent | Sub Page | URL | Status | Notes/Error |
|--------|----------|-----|--------|-------------|
| Candidates | Add Candidate | `/candidates/create` | ⏳ TEST | [ ] |
| Candidates | Candidate Details | `/candidates/details` | ⏳ TEST | [ ] |
| Jobs | Create Job | `/jobs/create` | ⏳ TEST | [ ] |
| Jobs | Job Details | `/jobs/details` | ⏳ TEST | [ ] |
| Jobs | Job Workspace | `/jobs/workspace` | ⏳ TEST | [ ] |

---

## WORKFORCE MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Employees | `/employees` | ⏳ TEST | [ ] |
| Convert to Employee | `/employee-conversion` | ⏳ TEST | [ ] |
| HTD Intake | `/htd-intake` | ⏳ TEST | [ ] |
| Buddy Program | `/buddy-program` | ⏳ TEST | [ ] |
| BU Head Dashboard | `/bu-head-dashboard` | ⏳ TEST | [ ] |

### Workforce Sub-Pages
| Parent | Sub Page | URL | Status | Notes/Error |
|--------|----------|-----|--------|-------------|
| Buddy Program | Buddy Record Details | `/buddy-program/{recordId}` | ⏳ TEST | [ ] |

---

## SALES MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Client Management | `/client-management` | ⏳ TEST | [ ] |
| Opportunity Pipeline | `/opportunity-pipeline` | ⏳ TEST | [ ] |
| Partner ROI Agent | `/partner-roi` | ⏳ TEST | [ ] |
| Demand Confirmation | `/demand-confirmation` | ⏳ TEST | [ ] |

---

## PROJECT MANAGEMENT MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Resource Management | `/resource-management` | ⏳ TEST | [ ] |
| Allocations | `/allocations` | ⏳ TEST | [ ] |
| Core-Pull & Pool Guard | `/core-pull` | ⏳ TEST | [ ] |
| Projects | `/projects` | ⏳ TEST | [ ] |
| Utilization & Bench Cost | `/utilization-dashboard` | ⏳ TEST | [ ] |
| Resource Forecast | `/forecast` | ⏳ TEST | [ ] |
| Forecast vs Actual | `/forecast-vs-actual` | ⏳ TEST | [ ] |

---

## FINANCE MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Invoices | `/invoices` | ⏳ TEST | [ ] |
| Invoice Management | `/invoice-management` | ⏳ TEST | [ ] |
| Timesheets | `/timesheets` | ⏳ TEST | [ ] |
| Revenue | `/revenue` | ⏳ TEST | [ ] |
| Executive Revenue Dashboard | `/executive-revenue-dashboard` | ⏳ TEST | [ ] |
| Finance Operations | `/finance-operations` | ⏳ TEST | [ ] |

---

## ADMIN MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Users & Access Control | `/admin/users-access-control` | ⏳ TEST | [ ] |
| Business Units | `/admin/business-units` | ⏳ TEST | [ ] |
| Certifications | `/admin/certifications` | ⏳ TEST | [ ] |
| Error Log | `/admin/error-log` | ⏳ TEST | [ ] |
| Ticket Routing & SLA | `/admin/ticket-routing` | ⏳ TEST | [ ] |
| Message Queue | `/admin/messagequeue` | ⏳ TEST | [ ] |
| AI Configuration | `/admin/ai-config` | ⏳ TEST | [ ] |
| Locale & Currency | `/settings/locale` | ⏳ TEST | [ ] |
| Message Templates | `/settings/templates` | ⏳ TEST | [ ] |
| Resume Parser (SLM) | `/admin/slm-dashboard` | ⏳ TEST | [ ] |
| SLM Training Data | `/admin/slm-training` | ⏳ TEST | [ ] |

### Admin Sub-Pages (Tabs)
| Parent | Tab Name | URL | Status | Notes/Error |
|--------|----------|-----|--------|-------------|
| Users & Access Control | Users Tab | `/admin/users-access-control/users` | ⏳ TEST | [ ] |
| Users & Access Control | Business Units Tab | `/admin/users-access-control/business-units` | ⏳ TEST | [ ] |
| Users & Access Control | Delivery Centers Tab | `/admin/users-access-control/delivery-centers` | ⏳ TEST | [ ] |
| Users & Access Control | Org Hierarchy Tab | `/admin/users-access-control/organizational-hierarchy` | ⏳ TEST | [ ] |
| Users & Access Control | Role Templates Tab | `/admin/users-access-control/role-templates` | ⏳ TEST | [ ] |

---

## REPORTING MODULE

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Analytics Dashboard | `/analytics` | ⏳ TEST | [ ] |
| BI Explorer | `/bi-explorer` | ⏳ TEST | [ ] |

---

## OTHER MODULES

| Resource | URL | Status | Notes/Error |
|----------|-----|--------|-------------|
| Executive Signal | `/executive-signal` | ⏳ TEST | [ ] |
| Training & Certifications | `/training-certification` | ⏳ TEST | [ ] |

---

## SUMMARY

### Status Counts
- ✅ **Loads:** ___ / 53
- ⚠️ **No Data:** ___ / 53
- ❌ **Broken:** ___ / 53
- ⏳ **Untested:** ___ / 53

### Critical Issues Found
[ List any P0/P1 issues found ]

### Common Errors
[ List any error messages that appear frequently ]

### Missing Components
[ List any routes that don't have matching components ]

---

## Testing Notes

**Date Tested:** ___________  
**Tester:** ___________  
**Browser:** Chrome / Firefox / Safari  
**Backend Status:** Running / Not Running  

### Observations
- [ ] Backend appears to be running
- [ ] All routes respond (no 404s on nav items)
- [ ] Some routes have empty data
- [ ] Console shows JavaScript errors
- [ ] Network requests show API errors

### Next Steps
1. [ ] Identify which items have missing components
2. [ ] Identify which items have API/backend issues
3. [ ] Create GitHub issues for each defect
4. [ ] Assign to appropriate teams for fixes
