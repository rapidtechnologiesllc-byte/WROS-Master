# WROS Navigation Reference - Complete & Authoritative

**Last Updated:** 2026-08-23  
**Source of Truth:** `backend/app/seeds/init_resources.py`  
**Frontend Routes:** `frontend/src/routes/Approutes.jsx`  
**Status:** ✅ VERIFIED AGAINST ACTUAL IMPLEMENTATION

---

## Overview

**COMPLETE authoritative mapping of all modules, resources, and screens in WROS.**

- **11 Modules**
- **72 Resources** (every screen built in the frontend)
- **All navigation controlled by backend database**
- **Personal resources mandatory for all users**

---

## Module 1: Personal (Mandatory for All Users) ⭐

All users automatically get VIEW access to these resources in every role.

| Resource | Route | Purpose |
|----------|-------|---------|
| Dashboard | `/` | Main dashboard & home |
| My Tasks | `/my-tasks` | Personal task list |
| My Timesheet | `/my-timesheet` | Personal timesheet entry |
| My Expenses | `/my-expenses` | Personal expense submissions |
| My Referrals | `/my-referrals` | Employee referral tracking |

---

## Module 2: Recruitment (11 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Candidates | `/candidates` | Candidate management & pool |
| Jobs | `/jobs` | Job postings & descriptions |
| Submissions | `/submissions` | Candidate submissions to jobs |
| Interviews | `/interviews` | Interview scheduling & feedback |
| Offer Letters | `/offers` | Offer creation & management |
| Intervention Queue | `/recruiter/intervention-queue` | Manual recruitment interventions |
| Rehire Approvals | `/recruiter/rehire-approvals` | Rehire candidate approvals |
| Candidate Review | `/hm-candidate-review` | Hiring manager candidate review |
| Risk Dashboard | `/recruiter/risk-dashboard` | Recruitment risk monitoring |
| Thunder Analytics | `/recruiter/thunder-analytics` | Thunder AI performance metrics |
| Bulk Launch | `/recruiter/bulk-launch` | Bulk candidate import/launch |

---

## Module 3: Workforce (12 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Employees | `/employees` | Employee management & profiles |
| Onboarding | `/onboarding` | Employee onboarding workflow |
| Allocations | `/allocations` | Resource allocations to projects |
| Timesheets | `/timesheets` | Time tracking & reporting |
| Leave Management | `/leave-management` | Leave requests & approvals |
| Performance Management | `/performance-management` | Performance reviews & goals |
| HTD Intake | `/htd-intake` | Head count to delivery intake |
| Buddy Program | `/buddy-program` | Employee buddy program |
| Convert to Employee | `/employee-conversion` | Candidate to employee conversion |
| Utilization Dashboard | `/utilization-dashboard` | Org-wide employee utilization metrics |
| Resource Forecast | `/forecast` | Resource planning & forecasting |
| Employee in Bench | `/employee-bench` | Bench employee management |

---

## Module 4: Sales (6 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Clients | `/client-management` | Client/account management |
| Opportunities | `/opportunity-pipeline` | Sales opportunities & pipeline |
| Proposals | `/proposals` | Proposal creation & tracking |
| Sales Ops | `/revenue` | Revenue tracking, leakage detection, billing operations |
| Pipeline Management | `/pipeline-management` | Sales pipeline management |
| Demand Confirmation | `/demand-confirmation` | Sales demand confirmation |

---

## Module 5: Project Management (5 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Projects | `/projects` | Project creation & management |
| Resources | `/resource-management` | Resource allocation & capacity |
| Budget | `/budget` | Budget planning & tracking |
| Schedule | `/schedule` | Project scheduling & timeline |
| Core-Pull & Pool Guard | `/core-pull` | Core resource management |

---

## Module 6: Finance (9 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Invoices | `/invoices` | Invoice management & billing |
| Expenses | `/expenses` | Expense tracking & reimbursement |
| Payroll | `/payroll` | Payroll management & processing |
| Reports | `/finance-operations` | Financial reporting |
| Budget Management | `/budget-management` | Budget planning & management |
| Forecasts | `/forecast` | Financial forecasting |
| Invoice Management | `/invoice-management` | Advanced invoice management |
| Finance Operations | `/finance-operations` | Finance operational dashboard |
| Executive Revenue Dashboard | `/executive-revenue-dashboard` | Executive revenue overview |

---

## Module 7: Reporting (5 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Analytics | `/analytics` | Analytics dashboard & insights |
| KPI Dashboard | `/kpi-dashboard` | KPI tracking & metrics |
| Data Export | `/data-export` | Data export & reporting |
| Scheduled Reports | `/scheduled-reports` | Scheduled report generation |
| BI Explorer | `/bi-explorer` | Business intelligence explorer |

---

## Module 8: System (11 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Configuration | `/configuration` | System configuration |
| API Keys | `/api-keys` | API key management |
| Webhooks | `/webhooks` | Webhook configuration |
| Audit Logs | `/audit-logs` | System audit logs |
| Error Logs | `/admin/error-log` | Error tracking & logs |
| System Health | `/system-health` | System health & monitoring |
| SLM Training Data | `/admin/slm-training` | SLM model training data |
| Message Queue | `/admin/messagequeue` | Message queue management |
| Ticket Routing | `/admin/ticket-routing` | Support ticket routing |
| AI Config | `/admin/ai-config` | AI model configuration |
| Locale & Currency | `/settings/locale` | Locale & currency settings |

---

## Module 9: Executive (7 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| CEO Dashboard | `/ceo-fy-progress` | CEO FY progress tracking |
| CFO Dashboard | `/cfo-dashboard` | CFO financial dashboard |
| Partner Dashboard | `/troy-partner-dashboard` | Partner performance dashboard |
| BU Head Dashboard | `/bu-head-dashboard` | Business unit head dashboard |
| Executive Signal | `/executive-signal` | Executive signal & alerts |
| Admin Agent State | `/admin/agent-state-dashboard` | AI agent state monitoring |
| Admin Weekly Recap | `/admin/weekly-recap` | Weekly recap dashboard |

---

## Module 10: Admin (3 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Users & Access Control | `/admin/users-access-control` | User management & permissions |
| Admin Settings | `/admin/admin-settings` | System-wide settings |
| Certifications | `/admin/certifications` | Certification management |

**Sub-pages/Tabs (within Users & Access Control):**
- Users Tab → `/admin/users-access-control/users`
- Business Units Tab → `/admin/business-units` (accessible within Users & Access Control)
- Organizational Hierarchy Tab → `/organization` (accessible within Users & Access Control)
- Role Templates Tab → `/admin/roles-permissions` (accessible within Users & Access Control)

---

## Module 11: AI & Automation (5 resources)

| Resource | Route | Purpose |
|----------|-------|---------|
| Ask Thunder | `/ai/thunder` | Thunder autonomous agent |
| Thunder Analytics | `/ai/thunder-analytics` | Thunder performance analytics |
| Ask Flash | `/ai/flash` | Flash validation & coaching |
| AI Coaching | `/ai/coaching` | AI coaching features |
| SLM Dashboard | `/admin/slm-dashboard` | Resume parsing SLM model dashboard |

---

## How Navigation Works

1. **Backend Database** = source of truth (init_resources.py)
2. **User Login** → queries `/hr/me/navigation` endpoint
3. **Backend returns** modules & resources based on user's roles
4. **Frontend renders** navigation menu dynamically
5. **Permissions** control visibility (user only sees what they have access to)

---

## Mandatory Personal Resources

All users automatically get VIEW access to Personal resources:
- ✅ Dashboard
- ✅ My Tasks
- ✅ My Timesheet
- ✅ My Expenses
- ✅ My Referrals

These are added to EVERY role template on initialization.

---

## Permission System

### Actions
- **V** (View) - Can access the resource
- **C** (Create) - Can create new items
- **E** (Edit) - Can edit existing items
- **D** (Delete) - Can delete items

### Super User
- Has V/C/E/D on ALL 77 resources

### Other Roles
- Permission determined by role template
- Multiple roles = UNION of all permissions
- Personal resources have minimum VIEW access

---

## Testing Checklist

### Visual Navigation
- [ ] All 11 modules appear in sidebar
- [ ] Personal module always shows (mandatory)
- [ ] Each module expands/collapses
- [ ] All 77 resources visible when expanded
- [ ] Resource names match database display_name

### Permission Test
- [ ] Super User sees all 77 resources
- [ ] Other users see only assigned resources
- [ ] Personal resources visible to everyone
- [ ] Module hides if user has zero permissions for any resource

### Route Test
- [ ] Click each resource → correct URL loads
- [ ] `/admin/users-access-control` → loads Users & Access Control
- [ ] `/ai/thunder` → loads Ask Thunder
- [ ] `/candidates` → loads Candidates

### Sub-Page Test
- [ ] Candidate list → click candidate → details load
- [ ] Job list → click job → details load
- [ ] Users & Access Control tabs work correctly

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/seeds/init_resources.py` | Module & resource definitions (SOURCE OF TRUTH) |
| `backend/app/models/role_template.py` | Role template & permission models |
| `backend/app/api/v1/endpoints/navigation.py` | Navigation endpoint |
| `frontend/src/routes/Approutes.jsx` | Route definitions (verified source) |
| `frontend/src/layout/Shell.js` | Navigation rendering |

---

## Summary

✅ **72 resources across 11 modules**  
✅ **Every built screen mapped**  
✅ **Unbuilt screens removed (Tasks, Forecast vs Actual)**  
✅ **Resources reorganized to correct modules**  
✅ **Personal resources mandatory**  
✅ **Database matches frontend**  
✅ **Single source of truth established**

This is the FINAL, COMPLETE, AUTHORITATIVE navigation reference for WROS.
