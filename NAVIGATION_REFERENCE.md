# WROS Navigation Menu Reference

**Last Updated:** 2026-08-23  
**Purpose:** Reference for navigation menu structure - ONLY modules and resources, not sub-pages

## Navigation Structure

The navigation menu consists of:
- **Module Groups** (main sidebar categories)
  - **Resources** (items within each module that appear in nav menu)
    - Sub-pages (accessed FROM resource view, NOT in nav menu)

## Status Legend
| Status | Meaning |
|--------|---------|
| ✅ | Working - Loads correctly |
| ❌ | Broken - Route doesn't exist or error |
| ⏳ | Untested - Not yet verified |

---

## NAVIGATION MENU ITEMS (Actual Sidebar Menu Only)

### Module: Executive Dashboards
| Resource | URL | Status |
|----------|-----|--------|
| CEO Dashboard | `/ceo-fy-progress` | ✅ Working |
| CFO Dashboard | `/cfo-dashboard` | ⏳ Untested |
| Partner Dashboard | `/troy-partner-dashboard` | ⏳ Untested |
| BU Head Dashboard | `/bu-head-dashboard` | ⏳ Untested |
| Executive Overview | `/executive-overview` | ⏳ Untested |
| KPI Metrics | `/kpi-metrics` | ⏳ Untested |
| Financial Summary | `/financial-summary` | ⏳ Untested |

### Module: Recruitment
| Resource | URL | Status |
|----------|-----|--------|
| Candidates | `/candidates` | ⏳ Untested |
| Jobs | `/jobs` | ⏳ Untested |
| Candidate Review | `/hm-candidate-review` | ⏳ Untested |
| Offer Letters | `/offers` | ⏳ Untested |
| Submissions | `/submissions` | ⏳ Untested |
| Intervention Queue | `/recruiter/intervention-queue` | ⏳ Untested |
| Rehire Approvals | `/recruiter/rehire-approvals` | ⏳ Untested |
| Risk Dashboard | `/recruiter/risk-dashboard` | ⏳ Untested |
| Thunder Analytics | `/recruiter/thunder-analytics` | ⏳ Untested |
| Bulk Launch | `/recruiter/bulk-launch` | ⏳ Untested |

### Module: Workforce
| Resource | URL | Status |
|----------|-----|--------|
| Employees | `/employees` | ⏳ Untested |
| Convert to Employee | `/employee-conversion` | ⏳ Untested |
| HTD Intake | `/htd-intake` | ⏳ Untested |
| Buddy Program | `/buddy-program` | ⏳ Untested |
| BU Head Dashboard | `/bu-head-dashboard` | ⏳ Untested |

### Module: Sales
| Resource | URL | Status |
|----------|-----|--------|
| Client Management | `/client-management` | ⏳ Untested |
| Opportunity Pipeline | `/opportunity-pipeline` | ⏳ Untested |
| Partner ROI Agent | `/partner-roi` | ⏳ Untested |
| Demand Confirmation | `/demand-confirmation` | ⏳ Untested |

### Module: Project Management
| Resource | URL | Status |
|----------|-----|--------|
| Resource Management | `/resource-management` | ⏳ Untested |
| Allocations | `/allocations` | ⏳ Untested |
| Core-Pull & Pool Guard | `/core-pull` | ⏳ Untested |
| Projects | `/projects` | ⏳ Untested |
| Utilization & Bench Cost | `/utilization-dashboard` | ⏳ Untested |
| Resource Forecast | `/forecast` | ⏳ Untested |
| Forecast vs Actual | `/forecast-vs-actual` | ⏳ Untested |

### Module: Finance
| Resource | URL | Status |
|----------|-----|--------|
| Invoices | `/invoices` | ⏳ Untested |
| Invoice Management | `/invoice-management` | ⏳ Untested |
| Timesheets | `/timesheets` | ⏳ Untested |
| Revenue | `/revenue` | ⏳ Untested |
| Executive Revenue Dashboard | `/executive-revenue-dashboard` | ⏳ Untested |
| Finance Operations | `/finance-operations` | ⏳ Untested |

### Module: Admin
| Resource | URL | Status |
|----------|-----|--------|
| Users & Access Control | `/admin/users-access-control` | ⏳ Untested |
| Business Units | `/admin/business-units` | ⏳ Untested |
| Certifications | `/admin/certifications` | ⏳ Untested |
| Error Log | `/admin/error-log` | ⏳ Untested |
| Ticket Routing & SLA | `/admin/ticket-routing` | ⏳ Untested |
| Message Queue | `/admin/messagequeue` | ⏳ Untested |
| AI Configuration | `/admin/ai-config` | ⏳ Untested |
| Locale & Currency | `/settings/locale` | ⏳ Untested |
| Message Templates | `/settings/templates` | ⏳ Untested |
| Resume Parser (SLM) | `/admin/slm-dashboard` | ⏳ Untested |
| SLM Training Data | `/admin/slm-training` | ⏳ Untested |

### Module: Reporting
| Resource | URL | Status |
|----------|-----|--------|
| Analytics Dashboard | `/analytics` | ⏳ Untested |
| BI Explorer | `/bi-explorer` | ⏳ Untested |

### Module: System
| Resource | URL | Status |
|----------|-----|--------|
| Message Queue | `/admin/messagequeue` | ⏳ Untested |

### Module: Engagement & Communications
| Resource | URL | Status |
|----------|-----|--------|
| Executive Signal | `/executive-signal` | ⏳ Untested |

### Module: Human Resources
| Resource | URL | Status |
|----------|-----|--------|
| Training & Certifications | `/training-certification` | ⏳ Untested |

---

## PERSONAL NAVIGATION (Top Right User Menu)

| Item | URL | Status | Issue |
|------|-----|--------|-------|
| Dashboard | `/` | ❌ BROKEN | [BX-HRMS-NAV-001] |
| My Tasks | `/my-tasks` | ❌ BROKEN | [BX-HRMS-NAV-002] |
| My Timesheet | `/my-timesheet` | ❌ BROKEN | [BX-HRMS-NAV-003] |
| My Expenses | `/my-expenses` | ❌ BROKEN | [BX-HRMS-NAV-004] |
| My Referrals | `/my-referrals` | ❌ BROKEN | [BX-HRMS-NAV-005] |

---

## SUB-PAGES (NOT in navigation menu)

These pages are accessed FROM resource views, not shown in sidebar:

### From Candidates Resource
- `/candidates/create` - Add new candidate (button within Candidates view)
- `/candidates/details` - View candidate details (click on candidate row)

### From Jobs Resource
- `/jobs/create` - Create new job (button within Jobs view)
- `/jobs/details` - View job details (click on job row)
- `/jobs/workspace` - Job workspace (accessed from job details)

### From Buddy Program Resource
- `/buddy-program/{recordId}` - Individual buddy record

### From Users & Access Control Resource
- `/admin/users-access-control/users` - Users tab (URL param, not separate nav item)
- `/admin/users-access-control/business-units` - Business Units tab
- `/admin/users-access-control/delivery-centers` - Delivery Centers tab
- `/admin/users-access-control/organizational-hierarchy` - Org Hierarchy tab
- `/admin/users-access-control/role-templates` - Role Templates tab

---

## KEY ARCHITECTURAL POINTS

### ✅ Correct Navigation Structure
- **Modules** appear as collapsible groups in sidebar
- **Resources** appear as items within modules
- **Sub-pages** are accessed FROM resource views (via buttons, clicks, etc.)
- Example: Module "Recruitment" → Resource "Candidates" → Sub-page `/candidates/details`

### ❌ ANTI-PATTERN: Don't do this
- Don't list `/candidates/create` as separate nav item
- Don't list `/candidates/details` as separate nav item
- Don't show "Add Candidate" button in nav menu
- Don't expose internal routes in navigation

### Admin Module Consolidation Issue
Currently showing:
- Business Units (separate nav item)
- Role Templates (separate nav item)
- Certifications (separate nav item)
- Error Logs (separate nav item)
- Users (separate nav item - BROKEN)
- Roles Permissions (separate nav item)
- Organization (separate nav item)

Should show:
- **Users & Access Control** (single nav item)
  - `/admin/users-access-control/users` (tab)
  - `/admin/users-access-control/business-units` (tab)
  - `/admin/users-access-control/role-templates` (tab)
  - etc. (all accessed via tabs/URL params)

---

## TESTING CHECKLIST

When testing navigation:

✅ **DO:**
- Click module to expand/collapse
- Click resource to load main view
- Verify resource loads without errors
- Check URL matches resource route

❌ **DON'T:**
- Look for "Add Candidate" as nav item
- Look for "Candidate Details" as nav item
- Expect sub-page URLs in sidebar
- Try to navigate directly to sub-page routes from menu

---

## Files Reference

- **Navigation Rendering:** `frontend/src/layout/Shell.js`
- **Route Mapping:** `frontend/src/routes/Approutes.jsx`
- **Backend Navigation Endpoint:** `backend/app/api/v1/endpoints/navigation.py`
- **Database Seed:** `backend/app/seeds/init_resources.py`
