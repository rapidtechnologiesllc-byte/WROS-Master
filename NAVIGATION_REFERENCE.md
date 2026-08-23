# WROS Navigation Reference Table

**Last Updated:** 2026-08-23  
**Purpose:** Central reference for all navigation items and their corresponding URLs for frontend testing and BX-HRMS issue tracking

## Status Legend
| Status | Meaning |
|--------|---------|
| ✅ | Working - Loads correctly and displays content |
| ❌ | Broken - Route doesn't exist or returns error/blank page |
| ⏳ | Untested - Not yet verified |
| 🔄 | Partial - Loads but has display/functionality issues |

## Navigation Items by Module

### Dashboard & Personal
| Module | Screen | URL | Status | Issue |
|--------|--------|-----|--------|-------|
| Dashboard | Dashboard | `/` | ❌ BROKEN | [BX-HRMS-NAV-001] Dashboard not loading |
| My Tasks | My Tasks | `/my-tasks` | ❌ BROKEN | [BX-HRMS-NAV-002] My Tasks not loading |
| My Timesheet | My Timesheet | `/my-timesheet` | ❌ BROKEN | [BX-HRMS-NAV-003] My Timesheet not loading |
| My Expenses | My Expenses | `/my-expenses` | ❌ BROKEN | [BX-HRMS-NAV-004] My Expenses not loading |
| My Referrals | My Referrals | `/my-referrals` | ❌ BROKEN | [BX-HRMS-NAV-005] My Referrals not loading |

### Recruitment
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Recruitment | Candidates | `/candidates` | CANDIDATES |
| Recruitment | Add Candidate | `/candidates/create` | CANDIDATE_CREATE |
| Recruitment | Candidate Details | `/candidates/details` | CANDIDATE_DETAILS |
| Recruitment | Jobs | `/jobs` | JOBS |
| Recruitment | Create Job | `/jobs/create` | JOB_CREATE |
| Recruitment | Job Details | `/jobs/details` | JOB_DETAILS |
| Recruitment | Job Workspace | `/jobs/workspace` | JOB_WORKSPACE |
| Recruitment | Candidate Review | `/hm-candidate-review` | HM_CANDIDATE_REVIEW |
| Recruitment | Offer Letters | `/offers` | OFFERS |
| Recruitment | Offer Letters (Listing) | `/offers-listing` | OFFERS_LISTING |
| Recruitment | Submissions | `/submissions` | SUBMISSIONS |
| Recruitment | Intervention Queue | `/recruiter/intervention-queue` | INTERVENTION_QUEUE |
| Recruitment | Rehire Approvals | `/recruiter/rehire-approvals` | REHIRE_APPROVALS |
| Recruitment | Risk Dashboard | `/recruiter/risk-dashboard` | RISK_DASHBOARD |
| Recruitment | Thunder Analytics | `/recruiter/thunder-analytics` | THUNDER_ANALYTICS |
| Recruitment | Bulk Launch | `/recruiter/bulk-launch` | BULK_LAUNCH |

### Workforce & HR
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Workforce | Employees | `/employees` | EMPLOYEES |
| Workforce | Convert to Employee | `/employee-conversion` | EMPLOYEE_CONVERSION |
| Workforce | HTD Intake | `/htd-intake` | HTD_INTAKE |
| Workforce | Buddy Program | `/buddy-program` | BUDDY_PROGRAM |
| Workforce | Buddy Program Details | `/buddy-program/{recordId}` | BUDDY_PROGRAM |
| Workforce | BU Head Dashboard | `/bu-head-dashboard` | BU_HEAD_DASHBOARD |

### Sales & Client Management
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Sales | Client Management | `/client-management` | CLIENT_MANAGEMENT |
| Sales | Opportunity Pipeline | `/opportunity-pipeline` | OPPORTUNITY_PIPELINE |
| Sales | Partner ROI Agent | `/partner-roi` | PARTNER_ROI |
| Sales | Demand Confirmation | `/demand-confirmation` | DEMAND_CONFIRMATION |

### Resource Management & Projects
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Resource Management | Resource Management | `/resource-management` | RESOURCE_MANAGEMENT |
| Resource Management | Allocations | `/allocations` | ALLOCATIONS |
| Resource Management | Core-Pull & Pool Guard | `/core-pull` | CORE_PULL |
| Resource Management | Projects | `/projects` | PROJECTS |
| Resource Management | Utilization & Bench Cost | `/utilization-dashboard` | UTILIZATION_DASHBOARD |
| Resource Management | Resource Forecast | `/forecast` | FORECAST |
| Resource Management | Forecast vs Actual | `/forecast-vs-actual` | FORECAST_VS_ACTUAL |

### Finance & Revenue
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Finance | Invoices | `/invoices` | INVOICES |
| Finance | Invoice Management | `/invoice-management` | INVOICE_MANAGEMENT |
| Finance | Timesheets | `/timesheets` | TIMESHEETS |
| Finance | Revenue | `/revenue` | REVENUE |
| Finance | Revenue Leakage | `/revenue-leakage` | REVENUE_LEAKAGE |
| Finance | Executive Revenue Dashboard | `/executive-revenue-dashboard` | EXECUTIVE_REVENUE_DASHBOARD |
| Finance | Finance Operations | `/finance-operations` | FINANCE_OPERATIONS |

### Executive Dashboards & Reporting
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Executive Dashboards | CEO FY Progress | `/ceo-fy-progress` | CEO_FY_PROGRESS |
| Executive Dashboards | CFO Agent | `/cfo-dashboard` | CFO_DASHBOARD |
| Executive Dashboards | Executive Signal | `/executive-signal` | EXECUTIVE_SIGNAL |
| Executive Dashboards | Admin Weekly Recap | `/admin/weekly-recap` | ADMIN_WEEKLY_RECAP |
| Executive Dashboards | Partner Dashboard | `/troy-partner-dashboard` | TROY_PARTNER_DASHBOARD |
| Executive Dashboards | BI Explorer | `/bi-explorer` | BI_EXPLORER |

### Administration
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Admin | Users & Access Control | `/admin/users-access-control` | USERS_ACCESS_CONTROL |
| Admin | Users & Access Control (Section) | `/admin/users-access-control/{section}` | USERS_ACCESS_CONTROL |
| Admin | Users (Tab) | `/admin/users-access-control/users` | USERS_ACCESS_CONTROL_USERS |
| Admin | Business Units (Tab) | `/admin/users-access-control/business-units` | USERS_ACCESS_CONTROL_BUSINESS_UNITS |
| Admin | Delivery Centers (Tab) | `/admin/users-access-control/delivery-centers` | USERS_ACCESS_CONTROL_DELIVERY_CENTERS |
| Admin | Organizational Hierarchy (Tab) | `/admin/users-access-control/organizational-hierarchy` | USERS_ACCESS_CONTROL_ORG_HIERARCHY |
| Admin | Role Templates (Tab) | `/admin/users-access-control/role-templates` | USERS_ACCESS_CONTROL_ROLE_TEMPLATES |
| Admin | Business Units | `/admin/business-units` | ADMIN_BUSINESS_UNITS |
| Admin | Certifications | `/admin/certifications` | CERTIFICATIONS |
| Admin | Error Log | `/admin/error-log` | ERROR_LOG |
| Admin | Ticket Routing & SLA | `/admin/ticket-routing` | TICKET_ROUTING_ADMIN |
| Admin | Message Queue | `/admin/messagequeue` | MESSAGE_QUEUE_DASHBOARD |
| Admin | AI Configuration | `/admin/ai-config` | TENANT_AI_CONFIG |

### Settings & Configuration
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Settings | Locale & Currency | `/settings/locale` | TENANT_LOCALE |
| Settings | Message Templates | `/settings/templates` | MESSAGE_TEMPLATES |
| Settings | Resume Parser (SLM) | `/admin/slm-dashboard` | SLM_DASHBOARD |
| Settings | SLM Training Data | `/admin/slm-training` | SLM_TRAINING |

### Training & Development
| Module | Screen | URL | Route Key |
|--------|--------|-----|-----------|
| Training | Training & Certifications | `/training-certification` | TRAINING_CERTIFICATION |

---

## Key Points for Issue Tracking

### Users & Access Control (FIXED 2026-08-23)
- **Before Fix:** Navigation had separate hardcoded "users" item routing to `/users` (incorrect)
- **After Fix:** Single entry point "Users & Access Control" routes to `/admin/users-access-control`
- **Sub-sections:** Accessible via URL parameters: `/admin/users-access-control/users`, `/admin/users-access-control/business-units`, etc.
- **No separate navigation items** for Business Units, Delivery Centers, Role Templates, Organizational Hierarchy

### URL Conventions
- **Primary routes:** Top-level items visible in sidebar navigation
- **Sub-routes:** Accessed via URL parameters (`:section` or `:recordId`)
- **Admin routes:** Prefixed with `/admin/`
- **Recruiter routes:** Prefixed with `/recruiter/`
- **Settings routes:** Prefixed with `/settings/`

### Testing the Navigation
To verify all navigation items are working:
1. Login to dashboard
2. Check left sidebar for all module groups
3. Verify each item routes to correct URL
4. Confirm no hardcoded navigation items exist (all should come from backend permission system)
5. Verify Admin module shows only Users & Access Control (not separate users, business units, etc.)

### Referencing in BX-HRMS
When creating issues, use this table to specify exact URLs:

**Example Issue:**
```
BX-HRMS-[ISSUE-ID]: Navigation routing incorrect
- Screen: Users & Access Control
- URL: /admin/users-access-control
- Issue: Admin submenu showing separate Business Units instead of tab
- Expected: All admin sub-items under Users & Access Control
- Reference: See NAVIGATION_REFERENCE.md
```

---

## File Locations

- **Routes Definition:** `frontend/src/utils/Routes.js`
- **Navigation Items:** `frontend/src/layout/navItems.js`
- **Navigation Rendering:** `frontend/src/layout/Shell.js`
- **Permission Mapping:** `frontend/src/layout/Shell.js` (NAV_PERMISSIONS)
- **Approutes:** `frontend/src/routes/Approutes.jsx`
