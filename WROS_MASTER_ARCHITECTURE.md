# BLITZENX WROS - MASTER ARCHITECTURE DOCUMENT

**Version:** 1.0  
**Status:** Architecture Baseline for Implementation  
**Date:** 2026-08-16  
**Purpose:** Single source of truth for all WROS system design decisions

---

## EXECUTIVE SUMMARY

WROS is the **Agentic Enterprise Operating System** for BlitzenX, enabling autonomous operations across:
- Sales & Commercial Pipeline
- Workforce Management & Deployment
- Delivery Execution
- Financial Operations
- Leadership & Succession
- Compliance & Governance

**Strategic Objective:** BlitzenX should operate for 30 days without the CEO without material degradation in revenue, delivery, workforce, client management, or financial control.

**Growth Target:** Scale from current headcount to 1,500 employees by 2030 via 70+ autonomous agents operating within defined authority levels.

**Architecture Principle:** Zero hardcoding. All roles, permissions, modules, and configurations are database-driven via role templates. No role names, permission strings, or module lists hardcoded anywhere in code.

---

## 1. ORGANIZATIONAL STRUCTURE & ACCOUNTABILITY

### 1.1 Corporate Hierarchy

```
BXHolding (Future)
├─ BlitzenX (Today - Operational)
│  ├─ AXION BU (Partner: Troy)
│  │  └─ Hemant (Delivery Lead)
│  └─ PRISM BU (Partner: Curtis)
│     └─ Manian (Delivery Lead)
├─ Poliqs (Today - Operational)
├─ BX Realty (Future)
├─ BX MGA (Future)
└─ BX Life Insurance (Future)

Current Implementation: Single-tenant BlitzenX
Future Implementation: Multi-tenant (BXHolding companies)
```

### 1.2 Employee Hierarchy (Single Reporting Chain)

```
ENTRY LEVEL (Specialized by Department):
├─ Intern Recruiter / Intern Developer / Intern Finance / Intern HR
│
CAREER PATH (Common to all departments):
├─ Consultant
├─ Senior Consultant
├─ Lead Consultant
├─ Manager
├─ Senior Manager
├─ Technical Manager
├─ Associate Director
├─ Director
├─ Principal Architect
├─ Associate Partner (AP)
├─ BU Head (VP)
├─ Senior Vice President (SVP)
├─ Partner (P&L Owner)
└─ CEO (Enterprise Owner)
```

### 1.3 Geographic Structure

**Locations:** Country-based (India, Canada, US, UK)

**Business Unit Structure:**
```
Partner (P&L Owner for multiple locations/BUs)
├─ BU Head (VP) - Location: India (single location, single BU)
├─ BU Head (VP) - Location: Canada (single location, single BU)
├─ BU Head (VP) - Location: US (single location, single BU)
└─ BU Head (VP) - Location: UK (single location, single BU)

Rules:
✅ One Partner can manage multiple BUs across multiple countries
❌ One BU Head manages ONE BU in ONE location only
❌ Employees cannot work across locations (project constraint)
❌ If BU Head needs multiple locations → must be promoted to Partner
```

### 1.4 Partner Accountability Model

**Partner owns the complete equation:**
```
Demand → Revenue → Workforce → Deployment → Delivery → Client Satisfaction → Margin → P&L
```

**Partner is accountable for:**
- Completing BU revenue and profitability targets
- Building commercial pipeline to support workforce plan
- Owning client relationships, expansion, retention
- Ensuring sufficient qualified capacity
- Holding delivery organization accountable for hiring, training, certification, deployment, utilization, quality
- Making timely decisions based on WROS forecasts
- Owning recovery plans when BU falls behind
- Building leadership bench (avoid Partner/CEO dependency)
- Ensuring all functions operate against measurable outcomes

**Workforce Allocation by Hiring Type (Not BU Allocation):**
```
Incremental hiring allocation by sourcing strategy (planning baseline):

LATERAL HIRING: 60% of new hires
├─ Profile: Experienced Guidewire consultants (5+ years Guidewire experience)
├─ Benefit: Immediate productivity, deep Guidewire knowledge, can mentor HTD
├─ Cost: Higher compensation, limited supply in market
└─ Example: Out of 100 hires → 60 Lateral (experienced Guidewire resources)

HTD HIRING: 40% of new hires
├─ Profile: Experienced Java developers (5+ years Java development)
├─ Training: Intensive Guidewire training + mentoring + certification
├─ Benefit: Lower cost, larger talent pool, long-term retention, builds bench
├─ Pipeline: Java Dev → HTD Training → Specialty Work → CORE Certification
└─ Example: Out of 100 hires → 40 HTD (Java devs ready to learn Guidewire)

Strategic Mix Rationale:
├─ 60% Lateral ensures immediate client delivery capacity
├─ 40% HTD builds long-term talent bench and reduces Guidewire market dependency
├─ Combined: Steady-state capability + growth capacity

WROS adjusts based on:
├─ Lateral market availability (harder to find 5+ year Guidewire resources)
├─ HTD conversion success rate (training completion, certification pass rate)
├─ Client demand urgency (immediate need favors Lateral)
├─ Long-term bench strength (future need favors HTD)
├─ Budget constraints (Lateral costs more upfront)
└─ CORE capacity requirements

This allocation applies independently to each BU
├─ AXION hires: 60% Lateral + 40% HTD
├─ PRISM hires: 60% Lateral + 40% HTD
└─ WROS recommends adjustments, Partner remains accountable for final outcome
```

---

## 2. PERMISSION MODEL & DATA ACCESS (Hierarchy-Based Cascading)

### 2.1 Access Rule: Manager Sees Entire Reporting Chain

```
Manager Visibility:
├─ All direct reports
├─ All reports' reports (entire chain down)
├─ All data those reports can access
└─ Department-specific data filtering applies

Director Visibility:
├─ Multiple managers + their entire chains
├─ All reports in the organizational tree
└─ Department-specific data filtering applies

Partner Visibility:
├─ All BUs they own (all locations)
├─ All departments' data (Recruitment, Delivery, HR, Finance, Sales)
├─ All P&L data for their BUs
└─ Filtered by: BU, Location, Partner (P&L ownership)

CEO/SVP Visibility:
├─ Everything (all BUs, all locations, all departments)
├─ Can edit all data
└─ Full enterprise view
```

### 2.2 Department-Based Data Silos (Strict Separation)

**RECRUITMENT Department:**
```
Access:
├─ Candidates (no internal PII, no bill_rate, no KPIs)
├─ Jobs
├─ Interviews (scheduling, feedback for hiring decisions)
├─ Submissions
├─ Intervention Queue (Thunder alerts)

Restricted Access:
❌ Cannot see: bill_rate, delivery KPIs, project allocation details
❌ Cannot see: employee payroll, benefits data
❌ Cannot see: financial/invoicing data

Roles:
├─ Intern Recruiter: Candidates in their BU + location + unassigned
├─ Lead Recruiter: Their team's candidates
├─ Recruitment Manager: Their team + escalations
└─ Senior Manager (Recruitment): Their BU/location or global (by assignment)

Permission: recruitment.view, recruitment.manage, interview.manage
```

**DELIVERY Department:**
```
Access:
├─ Consultants (full profile with bill_rate, KPI, utilization)
├─ Projects (allocation, budget, resource utilization)
├─ Timesheets (project hours, bill rates)
├─ Utilization & capacity tracking
├─ Interview feedback for hiring decisions

Restricted Access:
❌ Cannot see: candidate feedback details (recruitment only)
❌ Cannot see: employee benefits, payroll (HR only)
❌ Cannot see: invoicing details (Finance only)

Roles:
├─ Consultant: Own profile + team names (no PII), own projects
├─ Lead Consultant: Team members + projects, utilization, bill_rate, KPIs
├─ Technical Manager: Team utilization, project performance, resource KPIs
└─ Senior Manager (Delivery): Their team's entire delivery picture

Permission: project.view, project.manage, resource.manage, utilization.view
```

**HR Department:**
```
Access:
├─ Employees (records, profiles, benefits)
├─ Timesheets (time tracking, approval)
├─ Benefits enrollment & management
├─ Pay rates (for compensation planning)
├─ Employee directory (org structure)

Restricted Access:
❌ Cannot see: bill_rate (Delivery only)
❌ Cannot see: candidate feedback (Recruitment only)
❌ Cannot see: invoicing/revenue (Finance only)

Roles:
├─ HRBP (HR Business Partner): Only their assigned BU + location
├─ HR Manager: Multiple HRBPs, local reporting
├─ Workforce Ops Manager: Currently all employees across all BUs (future: BU-level)
└─ Senior Manager (HR): Their BU/location or global (by assignment)

Permission: employee.view, employee.manage, timesheet.manage, hr.manage
```

**SALES Department:**
```
Access:
├─ Opportunities (client projects, deals, pipeline)
├─ Clients (accounts, contacts, relationship tracking)
├─ Demand (job requisitions, forecasting, gap scoring)
├─ Pipeline analytics
├─ Relationship intelligence

Restricted Access:
❌ Cannot see: detailed delivery metrics (Delivery owns this)
❌ Cannot see: timesheet data (HR only)

Roles:
├─ Sales Manager: Their team's opportunities, clients, pipeline
├─ Account Manager: Their assigned accounts
└─ Senior Manager (Sales): Their BU/location or global (by assignment)

Permission: sales.view, sales.manage, opportunity.manage
```

**FINANCE Department:**
```
Access:
├─ Invoicing (client billing, rates)
├─ Expense tracking (recruiting, contractor expenses)
├─ Revenue recognition & P&L
├─ Bill rates (for invoicing context)
├─ Pay rates (for expense calculation)

Restricted Access:
❌ Cannot see: individual employee payroll details beyond role

Roles:
├─ Finance Manager: Their BU/location or global (by assignment)
├─ CFO: All financial data, all BUs, all locations
└─ Senior Manager (Finance): Regional financial oversight

Permission: finance.manage, invoice.manage, revenue.manage
```

### 2.3 Special Role Access

**HRBP (HR Business Partner):**
```
Assignment: Specific BU + Location only
Visibility: Only their assigned BU and location
Access: Employee records, timesheets, benefits for their BU/location
Cannot: Cross-BU access
Reporting: Local HR Manager + potential escalation to Workforce Ops Manager
```

**Workforce Ops Manager:**
```
Current State:
├─ Reports to: Their BU Partner (BU updates) + CEO (org visibility) [Dual track]
├─ Visibility: All employees across all BUs
├─ Approval: Their direct reports' timesheets (not centralized)

Future State (as org grows):
├─ WOPS at each BU level (reports to BU Partner)
├─ Central WOPS reports to CEO (escalation/strategy)
└─ Timesheet responsibility: Manager approves their reports (cascading model)
```

**BU Head (VP):**
```
Visibility: All delivery data in their location + their BU only
Access:
├─ Employees in their BU + location
├─ Projects in their BU
├─ Timesheets for their BU
├─ Candidates being hired for their BU
├─ Financial data for their BU
❌ Cannot: See outside their BU/location
Permission: All at BU scope only
Approval Authority: Final financial approval for hiring, project funding
```

**Partner:**
```
Visibility: All BUs they own (all locations) + complete financial picture
Access:
├─ All departments' data (Recruitment, Delivery, HR, Finance, Sales)
├─ All employees in their BUs
├─ All candidates being hired for their BUs
├─ All projects in their BUs
├─ All revenue and P&L for their BUs
├─ All decisions/escalations in their BUs
Permission: Full P&L ownership, hiring approval, strategic decisions
Approval Authority: Final business decisions, P&L commitment
Role Template Changes: When BU Head → Partner, automatically add P&L access (no code change)
```

**CEO:**
```
Visibility: Everything (all BUs, all locations, all departments, all entities)
Access: Full read/write across all data
Permission: Can override, modify, approve anything
Approval Authority: Enterprise strategic decisions, capital allocation, CEO-level approvals
Goal: Minimize dependencies on CEO (30-day test)
```

### 2.4 Geographic & Organizational Filters (Applied to ALL queries)

Every database query is filtered by:
```
WHERE
  tenant_id = current_user.tenant_id
  AND location_id IN (current_user.accessible_locations)
  AND bu_id IN (current_user.accessible_bus)
  AND department_id IN (current_user.accessible_departments)
  AND (
    -- Manager sees their reporting chain
    created_by_id IN (list_of_all_reports_in_hierarchy)
    OR assigned_to_id IN (list_of_all_reports_in_hierarchy)
    OR user_id = current_user_id
  )
```

---

## 3. NINE-MODULE EMPLOYEE SERVICE ARCHITECTURE

### 3.1 Module Overview

```
EMPLOYEE SERVICE (Internal Operations Portal)
├─ MODULE 1: RECRUITMENT
├─ MODULE 2: WORKFORCE
├─ MODULE 3: HR
├─ MODULE 4: SALES
├─ MODULE 5: PROJECT MANAGEMENT
├─ MODULE 6: FINANCE
├─ MODULE 7: MY REFERRALS
├─ MODULE 8: ADMIN
└─ MODULE 9: EXECUTIVE
```

### 3.2 Module Definitions & Role Access

**MODULE 1: RECRUITMENT**
```
Features:
├─ Jobs (create, manage, post to career portal)
├─ Candidates (sourcing, screening, pipeline)
├─ Interviews (scheduling, feedback, panel management)
├─ Candidate Review (screening decisions)
├─ Intervention Queue (Thunder autonomous alerts)
├─ Feedback for Hiring Decisions (from panel)
├─ Internal Notes (team discussions, decision tracking)
├─ Reports (hiring pipeline analytics, time-to-fill)

Access Matrix:
├─ Recruiter: ✅ Full read/write (their team's work)
├─ Lead Recruiter: ✅ Full read/write (team + escalations)
├─ Recruitment Manager: ✅ Full read/write (their BU/location)
├─ Hiring Manager: ✅ View candidates, receive interview feedback, approve offers
├─ BU Head: ✅ View-only (hiring pipeline for their BU)
├─ Partner: ✅ View-only (hiring for their BUs)
├─ CEO: ✅ View-only (all hiring)
└─ Others: ❌ No access

Permissions: recruitment.view, recruitment.manage, interview.manage

Data Scope: Filtered by BU, Location, Department (Recruitment)
```

**MODULE 2: WORKFORCE**
```
Features:
├─ Employees (records, profiles, org directory)
├─ Timesheets (time tracking, project allocation, approval)
├─ Allocations (assign employees to projects)
├─ Benefits (enrollment, management)
├─ Employee Directory (org structure, reporting hierarchy)
├─ My Timesheet (self-service for employees)
├─ Internal Notes (team discussions, employee context)
├─ Reports (utilization, project allocation, capacity analytics)

Access Matrix:
├─ Employee: ✅ My Timesheet, My Profile (read), My Allocations (read)
├─ Project Manager: ✅ Full read/write (team allocation, utilization)
├─ HRBP: ✅ Read/write (their BU/location employees only)
├─ Workforce Ops Manager: ✅ Full read/write (all employees)
├─ HR Manager: ✅ Full read/write (all employees in scope)
├─ BU Head: ✅ Read/write (BU employees, timesheets, allocations)
├─ Partner: ✅ Read/write (all BU employees)
├─ CFO: ✅ View-only (cost data)
├─ CEO: ✅ Full view (all employees, all BUs)
└─ Others: ❌ No access

Permissions: employee.view, employee.manage, timesheet.manage, project.view

Data Scope: Filtered by BU, Location, Manager hierarchy, Department
```

**MODULE 3: HR**
```
Features:
├─ Offer Letters (creation, customization, templates)
├─ Offer Approval Workflow (hiring manager approval → HR approval → BU Head financial approval)
├─ Employee Conversion (candidate → employee, onboarding)
├─ Onboarding Checklist (pre-boarding tasks, assignments)
├─ Internal Notes (hiring decisions, conversion notes, offer context)
├─ Reports (offer acceptance rate, conversion funnel, time-to-hire)

Access Matrix:
├─ HR Manager: ✅ Full read/write (all offers, conversions)
├─ HRBP: ✅ Manage their BU/location (offer prep)
├─ Hiring Manager: ✅ Approve/reject offer workflow
├─ BU Head: ✅ Financial approval on offers
├─ HR Director: ✅ Strategic HR oversight
├─ CEO: ✅ View-only (key conversions)
└─ Others: ❌ No access

Permissions: hr.manage, offer.manage, employee.manage

Data Scope: Filtered by BU, Location, Department (HR)
```

**MODULE 4: SALES**
```
Features:
├─ Opportunities (client projects, deals, pipeline tracking)
├─ Clients (client accounts, contacts, relationship history)
├─ Demand (job requisitions, demand forecasting, gap scoring)
├─ Pipeline Analytics (weighted pipeline, revenue forecast, hiring implications)
├─ Internal Notes (deal discussions, negotiations, client context)
├─ Reports (pipeline analytics, demand forecasting, client health)

Access Matrix:
├─ Sales Manager: ✅ Full read/write (their opportunities, clients)
├─ Account Manager: ✅ Read/write (assigned accounts only)
├─ Finance Manager: ✅ View-only (opportunity revenue context)
├─ Partner: ✅ Full read/write (their BU opportunities, clients)
├─ CFO: ✅ View-only (pipeline revenue forecast)
├─ CEO: ✅ View-only (all opportunities, all clients)
└─ Others: ❌ No access

Permissions: sales.view, sales.manage, opportunity.manage

Data Scope: Filtered by BU, Location, Sales hierarchy
```

**MODULE 5: PROJECT MANAGEMENT**
```
Features:
├─ Projects (create, manage, milestones, completion tracking)
├─ Project Staffing (assign resources, manage allocations)
├─ Utilization Dashboard (hours by resource, by project, by BU)
├─ Project Completion & Billing (mark complete, pass to Finance)
├─ Resource Performance (individual performance by project)
├─ Internal Notes (project team discussions, decisions)
├─ Reports (project delivery analytics, resource utilization, project health)

Access Matrix:
├─ Project Manager: ✅ Full read/write (assigned projects)
├─ Technical Manager: ✅ Read/write (team projects, resource management)
├─ Resource Manager: ✅ Full read/write (project staffing, allocation)
├─ Finance Manager: ✅ View-only (project completion for invoicing)
├─ BU Head: ✅ Read/write (BU projects)
├─ Partner: ✅ Full read/write (all BU projects)
├─ CEO: ✅ View-only (all projects)
└─ Others: ❌ No access

Permissions: project.manage, resource.manage

Data Scope: Filtered by BU, Location, Project assignment
```

**MODULE 6: FINANCE**
```
Features:
├─ Invoicing (client billing, invoice creation, approval)
├─ Expense Tracking (recruiting costs, contractor expenses, approvals)
├─ Revenue Recognition (recognize revenue as work completes, P&L impact)
├─ Financial Reports (revenue by client, by project, by resource, by BU, by entity)
├─ Bill Rate Management (rates by role, location, BU)
├─ Internal Notes (billing discussions, exceptions, approvals)
├─ Reports (revenue analytics, expense analytics, margin analysis)

Access Matrix:
├─ Finance Manager: ✅ Full read/write (invoices, expenses for scope)
├─ Billing Specialist: ✅ Create/submit invoices
├─ BU Head: ✅ View-only (BU financials)
├─ Partner: ✅ Full read/write (BU financials, P&L)
├─ CFO: ✅ Full read/write (all financials, all BUs)
├─ CEO: ✅ Full view (enterprise financials)
└─ Others: ❌ No access

Permissions: finance.manage, invoice.manage, revenue.manage

Data Scope: Filtered by BU, Location, Entity, Department
```

**MODULE 7: MY REFERRALS**
```
Features:
├─ Browse Open Jobs (public job listings - read-only)
├─ Refer a Friend (submit referral with resume)
├─ My Referrals (track referrals I've submitted, see status)
├─ Referral Status (application progress of referred candidates)

Access Matrix:
├─ All Employees: ✅ Browse jobs, submit referrals, track own
├─ Recruiter: ✅ Manage referrals, provide feedback, track quality
├─ Recruitment Manager: ✅ View-only (referral quality metrics)
└─ ⚠️ CRITICAL: Employees do NOT get recruitment.manage access

Permissions: referral.create, referral.view_own, referral.manage (recruiters only)

Data Scope: Public jobs only, no internal candidate data exposed
```

**MODULE 8: ADMIN**
```
Features:
├─ User Management (create, edit, assign roles)
├─ Role Templates (create/edit role definitions, permissions)
├─ Permissions (configure permission matrix, module access)
├─ Business Units (create, manage, assign managers)
├─ Locations (create, manage, assign to BUs)
├─ System Configuration (settings, integrations, feature flags)
├─ Audit Logs (system activity, decision tracking, compliance)
├─ Tenant Management (multi-tenant support)

Access Matrix:
├─ Super User: ✅ Full read/write
├─ System Admin: ✅ Full read/write
├─ CEO: ✅ View-only (audit logs)
└─ Others: ❌ No access

Permissions: admin.manage, system.manage

Data Scope: All data, no filters
```

**MODULE 9: EXECUTIVE**
```
Features:
├─ CEO FY Progress (hiring KPIs, revenue targets, pipeline health, CEO dependency index)
├─ CFO Financial Dashboard (PNL by BU, by client, by project, margin analysis)
├─ BU Head Dashboard (BU-specific KPIs, team metrics, utilization, delivery health)
├─ Partner ROI Agent (partner profitability, commission tracking, incentives, goals)
├─ Custom Reports (all analytics, custom dashboards, forecasts)

Access Matrix:
├─ CEO: ✅ All dashboards, all BUs, all data
├─ CFO: ✅ Financial dashboards, revenue by BU/client/project
├─ Partner: ✅ Their BU dashboard, their BU financials, their ROI metrics
├─ BU Head: ✅ Their BU dashboard, their BU team metrics
├─ Senior Manager (dept): ✅ Department-specific dashboards (if role template grants)
└─ Super User: ✅ All dashboards

Permissions: revenue.view, revenue.view_pnl, reports.view, executive.view

Data Scope: Filtered by BU (Partner/BU Head view only their scope), Role-based
```

---

## 4. MICROSERVICES ARCHITECTURE (Future Split)

### 4.1 Service Boundaries

**Current:** Monolithic backend (OnboardingModule-Backend)

**Target Architecture (Phase 2-4):**
```
Career Portal (careers.blitzenx.com)
└─ Frontend only
   ├─ Guest: Browse jobs, apply as guest
   └─ Logged-in candidate: Track application progress

API Gateway (Central routing)
├─ /api/career/* → Career Service
├─ /api/wros/* → WROS Service
├─ /api/auth/* → Auth Service
└─ /api/finance/* → Finance Service

WROS Service (Workforce Revenue Operating System Backend)
├─ Owns: Candidates, Jobs, Interviews, Offers, Projects, Clients, Demand
├─ Database: wros_db (PostgreSQL)
├─ Endpoints: 100+ REST APIs
├─ Agents: 40+ WROS agents (Thunder, AI Recruiter, etc.)
└─ Scope: All Recruitment, Delivery, Sales operations

Finance Service (To be built)
├─ Owns: Invoices, Expenses, Revenue Recognition, P&L
├─ Database: finance_db (PostgreSQL)
├─ Endpoints: 20+ REST APIs
├─ Data sync: Via events (ProjectCompleted, RevenueRecognized, etc.)
└─ Scope: All financial operations

Shared Services (Foundation)
├─ Auth Service
│  └─ Handles: Login, JWT, MFA, Session management
│  └─ Database: auth_db (tenant_id, users, sessions)
│
├─ RBAC Service
│  └─ Handles: Role templates, permissions, access control
│  └─ Database: rbac_db (role_templates, permissions, user_roles)
│
├─ Organization Service (Future)
│  └─ Handles: Employees, hierarchy, BU, locations, departments
│  └─ Database: org_db (employees, bu, location, hierarchy)
│
├─ Config Service (Infrastructure)
│  └─ Handles: All configuration (no hardcoding)
│  └─ Database: config_db (modules, permissions, features)
│
└─ Event Bus (Kafka/RabbitMQ)
   └─ Enables: Async cross-service communication via events

Employee Service Frontend (OnboardingModule-Frontend)
├─ Dynamic modules based on role permissions
├─ Calls: WROS APIs, Finance APIs, Auth APIs
├─ Renders: 9 modules based on user role
└─ Responsive to all user hierarchies
```

### 4.2 Data Ownership

| Data Entity | Owned By | Accessed By | Notes |
|---|---|---|---|
| Candidates | WROS | Recruitment, Hiring Manager, BU Head, Partner, CEO | Internal data |
| Jobs | WROS | Recruitment, BU Head, Partner, CEO | Public jobs exposed to Career Portal |
| Interviews | WROS | Recruitment, Hiring Manager, BU Head, Partner, CEO | Feedback visible to hiring chain |
| Offers | WROS | HR, Hiring Manager, BU Head, Partner, CEO | Multi-approval workflow |
| Employees | Organization | All modules (scoped by BU/Location) | HR source of truth |
| Timesheets | Workforce | HR, Project Manager, BU Head, Partner, CEO | Time tracking |
| Projects | WROS | Delivery, Project Manager, Finance, BU Head, Partner, CEO | Project allocation |
| Invoices | Finance | Finance, BU Head, Partner, CFO, CEO | Revenue source |
| Clients | WROS | Sales, Finance, Partner, CEO | Relationship tracking |
| Revenue | Finance | Finance, Partner, CFO, CEO | P&L source of truth |

---

## 5. DATABASE ARCHITECTURE (Zero-Hardcoding)

### 5.1 Multi-Tenancy Design

```sql
-- All tables include tenant_id for multi-tenant isolation
-- Default: tenant_id = 1 (BlitzenX)
-- Future: tenant_id = 2 (Poliqs), 3 (BX Realty), etc.

CREATE TABLE employees (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  location_id UUID NOT NULL,
  bu_id UUID NOT NULL,
  manager_id UUID,  -- FK to another employee (hierarchy)
  first_name VARCHAR,
  last_name VARCHAR,
  email VARCHAR,
  department_id INT,  -- Links to department (Recruitment, Delivery, HR, Finance, Sales)
  pay_rate DECIMAL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  UNIQUE(tenant_id, email)
);

CREATE TABLE locations (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  country_name VARCHAR,  -- India, Canada, US, UK
  created_at TIMESTAMP,
  UNIQUE(tenant_id, country_name)
);

CREATE TABLE business_units (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  location_id UUID NOT NULL,
  partner_id UUID NOT NULL,  -- FK to employee
  bu_head_id UUID,  -- FK to employee (BU Head/VP)
  name VARCHAR,
  p_and_l_owner_id UUID,  -- Partner accountability
  created_at TIMESTAMP,
  UNIQUE(tenant_id, location_id, partner_id)
);

CREATE TABLE departments (
  id INT PRIMARY KEY,
  tenant_id INT NOT NULL,
  name VARCHAR,  -- Recruitment, Delivery, HR, Finance, Sales
  created_at TIMESTAMP,
  UNIQUE(tenant_id, name)
);
```

### 5.2 Role Templates (Database-Driven)

```sql
-- NO hardcoded role names in code
-- All roles defined here via admin UI

CREATE TABLE role_templates (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  name VARCHAR,  -- "Recruiter", "Lead Consultant", "CFO", "BU Head", etc.
  description TEXT,
  department_id INT,  -- Which department owns this role
  level INT,  -- Hierarchy level (1=Intern, 15=CEO, 12=Partner)
  requires_manager_approval BOOLEAN,
  is_system BOOLEAN,  -- System-defined or custom
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  UNIQUE(tenant_id, name)
);

CREATE TABLE modules (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  name VARCHAR,  -- "Recruitment", "Workforce", "HR", "Sales", "Project Management", etc.
  display_name VARCHAR,
  description TEXT,
  icon VARCHAR,
  order_index INT,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  UNIQUE(tenant_id, name)
);

CREATE TABLE module_permissions (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  module_id UUID NOT NULL,
  permission_name VARCHAR,  -- "recruitment.view", "project.manage", etc.
  description TEXT,
  created_at TIMESTAMP,
  UNIQUE(tenant_id, module_id, permission_name)
);

CREATE TABLE role_template_module_access (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  role_template_id UUID NOT NULL,
  module_id UUID NOT NULL,
  access_level VARCHAR,  -- "view", "manage", "approve", "own"
  data_scope VARCHAR,  -- "own", "team", "bu", "location", "global"
  can_create BOOLEAN,
  can_edit BOOLEAN,
  can_delete BOOLEAN,
  created_at TIMESTAMP,
  UNIQUE(tenant_id, role_template_id, module_id)
);

CREATE TABLE user_roles (
  id UUID PRIMARY KEY,
  tenant_id INT NOT NULL,
  user_id UUID NOT NULL,
  role_template_id UUID NOT NULL,
  assigned_at TIMESTAMP,
  assigned_by_id UUID,
  UNIQUE(tenant_id, user_id, role_template_id)
);
```

### 5.3 Permission System (Dynamic, No Hardcoding)

```python
# Backend: NO hardcoded permission checks

# WRONG (Hardcoded):
if user.role == "CEO":
    show_all_data()

# RIGHT (Database-driven):
permissions = get_user_permissions(user.id)
if "revenue.view_pnl" in permissions:
    show_all_data()

# The has_permission function:
def get_user_permissions(user_id: str, tenant_id: int):
    """
    Query database for user's permissions.
    - Get user's role templates
    - Get modules accessible via those roles
    - Apply data scope filters (BU, Location, Manager hierarchy)
    - Return set of permissions
    """
    user_roles = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.tenant_id == tenant_id
    ).all()
    
    permissions = set()
    for role in user_roles:
        module_accesses = db.query(RoleTemplateModuleAccess).filter(
            RoleTemplateModuleAccess.role_template_id == role.role_template_id
        ).all()
        
        for access in module_accesses:
            permissions.add(f"{access.module.name}.{access.access_level}")
    
    return permissions

# Frontend: Dynamic navigation (no hardcoded module list)
def get_user_accessible_modules(user_id: str):
    """
    Query database for user's accessible modules.
    - Get user's role templates
    - Get modules accessible via those roles
    - Filter by user's BU/Location scope
    - Return list of modules to display
    """
    user_roles = db.query(UserRole).filter(...).all()
    
    modules = db.query(Module).join(
        RoleTemplateModuleAccess
    ).filter(
        RoleTemplateModuleAccess.role_template_id.in_([r.role_template_id for r in user_roles])
    ).all()
    
    return modules
```

---

## 6. WROS AGENTIC OPERATING SYSTEM

### 6.1 70+ Agents Across 12 Domains

**DOMAIN 1: ENTERPRISE CONTROL**
- Enterprise Command Agent (Daily operating picture)
- CEO Dependency Agent (Minimize CEO escalations)
- Executive Decision Agent (Decision packages)
- Investment Committee Agent (Investment reviews)
- Enterprise Risk Agent (Operational risk tracking)

**DOMAIN 2: COMMERCIAL ENGINE**
- Market Intelligence Agent
- Account Intelligence Agent
- Opportunity Qualification Agent
- Pipeline Forecast Agent
- Sales Action Agent
- Relationship Intelligence Agent
- Expansion Agent
- Proposal Agent
- Competitive Intelligence Agent

**DOMAIN 3: WORKFORCE INTELLIGENCE**
- Workforce Capacity Agent (Real-time capacity)
- Demand Forecast Agent (2-3 months ahead)
- Skills Intelligence Agent (Skill graph)
- Workforce Matching Agent (Demand → Skills → People)
- Deployment Agent (Execution workflow)
- Utilization Agent
- Bench Management Agent
- Workforce Cost Agent

**DOMAIN 4: SPECIALTY ENGINE** (BXIN Corporate capacity marketplace)
- Specialty Capacity Agent
- Specialty Matching Agent
- Specialty Utilization Agent
- Specialty Rotation Agent
- Specialty Revenue Agent (125% of BXIN cost target)
- Specialty Economics Agent

**DOMAIN 5: HTD / TALENT DEVELOPMENT**
- HTD Intake Agent
- Training Progress Agent
- HTD Performance Agent
- HTD-to-Specialty Agent
- CORE Readiness Agent
- Certification Agent
- Talent Development Agent

**DOMAIN 6: RECRUITING**
- Workforce Recruiting Agent (Demand → Hiring requirements)
- Candidate Sourcing Agent
- Candidate Screening Agent
- Interview Intelligence Agent
- Offer Economics Agent
- Recruiting Pipeline Agent

**DOMAIN 7: DELIVERY**
- Project Health Agent
- Delivery Risk Agent
- Resource Performance Agent
- Client Escalation Agent
- Quality Agent

**DOMAIN 8: FINANCE**
- Revenue Recognition Agent
- Billing Agent
- Margin Agent
- EBITDA Agent
- Cash Flow Agent

**DOMAIN 9: HR / PEOPLE**
- Employee Lifecycle Agent
- Performance Agent
- Retention Risk Agent
- Organizational Health Agent

**DOMAIN 10: LEADERSHIP / SUCCESSION**
- Leadership Intelligence Agent
- Succession Agent
- Key-Person Dependency Agent
- Leadership Performance Agent

**DOMAIN 11: KNOWLEDGE / IP**
- Knowledge Capture Agent
- Knowledge Retrieval Agent
- IP Identification Agent
- Process Optimization Agent

**DOMAIN 12: GOVERNANCE / CONTROL**
- Policy Enforcement Agent
- Data Integrity Agent
- Audit Agent
- Access Control Agent
- Dependency Audit Agent
- Workflow Quality Agent
- Agent Governance Agent

### 6.2 Agent Authority Levels

```
LEVEL 0: OBSERVE
├─ Can: Collect, analyze, classify, monitor, forecast
└─ Cannot: Modify enterprise state

LEVEL 1: RECOMMEND
├─ Can: Produce recommendations, candidate lists, forecasts, risk assessments
└─ Requires: Human approval

LEVEL 2: EXECUTE WITH APPROVAL
├─ Can: Execute action after authorized human approval
└─ Requires: Approval before execution

LEVEL 3: AUTONOMOUS EXECUTION
├─ Can: Execute predefined actions automatically within policy
└─ Requires: Policy boundaries

LEVEL 4: SYSTEM ENFORCEMENT (Deterministic Controls - AI Cannot Override)
├─ Can: Enforce authorization, policy, financial limits, compliance
├─ Enforces: Certification gates, state transitions, data integrity
└─ Cannot: Be overridden by AI agents
```

### 6.3 Agent Communication Architecture

```
Agent → Structured Event → Validation → WROS State → Downstream Agent

Event structure:
├─ event_id
├─ timestamp
├─ originating_agent_id
├─ source (system of record)
├─ entity_id (candidate, employee, project, etc.)
├─ current_state
├─ proposed_state
├─ confidence_score
├─ evidence
├─ action_required
├─ owner (person accountable)
├─ deadline
├─ audit_reference
└─ escalation_path (if needed)
```

### 6.4 WROS Orchestrator

```
Central orchestration layer determines:
├─ Which agent should act
├─ In what sequence
├─ What data it needs
├─ Whether authority exists
├─ Whether human approval required
├─ Whether action changes enterprise state
├─ Whether deterministic validation required

Rule: Agents never arbitrarily invoke each other
All interactions: Policy controlled via orchestrator
```

---

## 7. ACCOUNTABILITY & ESCALATION FRAMEWORK

### 7.1 Accountability Engine

**Every WROS task must have:**
```
Owner → Action → Deadline → Evidence → Outcome

NO Owner:           UNOWNED_WORK           (Auto-escalate)
NO Deadline:        INVALID_WORKFLOW       (Reject)
NO Success Metrics: INVALID_SUCCESS_CRITERIA (Reject)
```

### 7.2 Escalation Structure

**Every escalation must contain:**
1. Problem (clear statement)
2. Evidence (data supporting the problem)
3. Business impact (financial/operational/strategic)
4. Actions already attempted
5. Available options (2-3 alternatives)
6. Recommended option (with rationale)
7. Required decision (what authority is needed)
8. Decision authority (who can decide)
9. Deadline (when decision needed)

**System rejects:** "We have a problem. What should we do?"

**System requires:** "Here is the problem, evidence, options and recommendation. I require your decision because this exceeds my authority."

### 7.3 Human-in-the-Loop Automation

WROS automatically determines event classification:

```
AUTO-EXECUTE
└─ Safe, deterministic, policy-compliant
   Example: Approve timesheet after validation

MANAGER APPROVAL
└─ Requires BU-level authority
   Example: Approve offer letter

EXECUTIVE APPROVAL
└─ Requires enterprise authority
   Example: Approve cross-BU resource movement

HUMAN REVIEW
└─ AI confidence insufficient
   Example: Recommend role for new hire

HARD STOP
└─ Policy/security/data integrity violation
   Example: Data access from unauthorized party
```

---

## 8. ECONOMIC MODEL (Multi-Level P&L)

### 8.1 Simultaneous P&L Calculation

WROS must calculate economics at these levels:
```
├─ Enterprise (BlitzenX)
├─ Entity (BXUS, BXIN)
├─ BU (AXION, PRISM)
├─ Principal (senior resource)
├─ Client (customer)
├─ Project (engagement)
├─ Resource (individual)
├─ Location (country)
├─ Engagement type (Specialty vs CORE)
├─ Specialty (corporate capacity)
└─ Corporate (overhead allocation)
```

### 8.2 Key Questions Answered

```
WHO GENERATED REVENUE?
├─ Resource? Client? Principal? Project?
└─ Entity? (BXUS vs BXIN)

WHO CONSUMED COST?
├─ Employee? Location? BU? Department?
└─ Assignment? Recruiting? Training?

WHO OWNS THE CLIENT?
├─ Principal? Partner? Account Manager?
└─ Entity?

WHO OWNS THE EMPLOYEE?
├─ Hiring Manager? BU Head? Partner?
└─ Entity?

WHERE DID ECONOMIC VALUE ACCRUE?
├─ Client? Project? Resource? Location?
└─ BU? Entity? Corporate?

SPECIALTY REVENUE ATTRIBUTION
├─ Never in AXION or PRISM BU P&L
├─ Always in BXIN Corporate P&L
└─ Track by origin BU, current project, corporate entity
```

---

## 9. THE 30-DAY CEO TEST

### 9.1 CEO Dependency Simulation

WROS continuously simulates: **"If CEO disappeared today, what would stop?"**

**Identify:**
- Decisions waiting on CEO
- Clients dependent on CEO
- Approvals waiting on CEO
- Operational tasks assigned to CEO
- Relationships only CEO owns
- Knowledge only CEO possesses
- Systems requiring CEO intervention

**Objective:** Eliminate unnecessary CEO dependency, not the CEO

---

## 10. THE 1,500-PERSON TEST (2030 Growth)

### 10.1 Quarterly Growth Trajectory

WROS must forecast quarterly:
```
Required Headcount vs Current Headcount vs Forecast Headcount
Required Hiring vs Expected Attrition
Required Revenue vs Required Client Demand
Leadership Capacity vs Management Layers Needed
Capital vs Facilities vs Systems Requirements

Auto-identifies: Ahead/behind trajectory
```

### 10.2 Hiring Type Allocation (Lateral vs HTD)

```
Strategic hiring mix: 60% Lateral / 40% HTD

LATERAL (60%):
├─ Experienced Guidewire consultants (5+ years Guidewire)
├─ Immediate client delivery
├─ High cost, limited market supply
└─ Applied across all BUs

HTD (40%):
├─ Experienced Java developers (5+ years Java)
├─ Convert to Guidewire via intensive training
├─ Lower cost, builds long-term bench
├─ Creates competitive advantage (don't depend on Guidewire market)

WROS adjusts based on:
├─ Lateral market availability
├─ HTD conversion success rate
├─ Client demand urgency
├─ Long-term bench strength
└─ Budget constraints

Applied per-BU (not aggregate):
└─ Each BU's hiring follows 60/40 strategy independently
```

---

## 11. MULTI-TENANCY ARCHITECTURE (Future)

### 11.1 Tenant Isolation

```
BXHolding (Parent)
├─ BlitzenX (Tenant 1)
├─ Poliqs (Tenant 2 - Future)
├─ BX Realty (Tenant 3 - Future)
├─ BX MGA (Tenant 4 - Future)
└─ BX Life Insurance (Tenant 5 - Future)

Database design:
├─ Single database, tenant_id on all tables
├─ Row-level security enforced via tenant_id filter
├─ Shared Auth Service (authenticates across all tenants)
├─ Shared RBAC Service (manages roles per tenant)
└─ Shared Config Service (manages configuration per tenant)

Queries automatically scoped: WHERE tenant_id = current_tenant
```

---

## 12. DEVELOPMENT ROADMAP

### Phase 1: Database Foundation (COMPLETE)
- ✅ PostgreSQL migration (SQLite elimination)
- ✅ 169 tables created and connected
- ✅ RBAC model designed
- ✅ Multi-tenancy architecture planned

### Phase 2: Backend Zero-Hardcoding Rewrite (IN PROGRESS)
- **Duration:** 2-3 weeks
- **Scope:** Eliminate all hardcoded roles/permissions (92 findings → 0)
- **Output:** 
  - Rewrite app/core/dependencies.py
  - Rewrite role-based dashboard service
  - Update endpoint decorators
  - Create permission registry (database-driven)
  - Remove hardcoded role conditionals

### Phase 3: Admin UI Implementation
- **Duration:** 1-2 weeks
- **Scope:** Build UI for complete configuration management
- **Features:**
  - Role Template Management (create/edit roles)
  - Module Management (create/manage modules)
  - Permission Matrix UI (assign permissions)
  - User Role Assignment (assign users to roles)
  - System Configuration (settings, features)

### Phase 4: Frontend Dynamic Rendering
- **Duration:** 1 week
- **Scope:** Make entire UI dynamic based on role templates
- **Features:**
  - Dynamic navigation bar (modules shown based on permissions)
  - Dynamic dashboard routing (role-based landing page)
  - Permission-based component rendering
  - Dynamic form field visibility

### Phase 5: Microservices Split (Optional - Future)
- **Duration:** 3-4 weeks
- **Scope:** Split into independent services
- **Services:**
  - WROS Service (candidate, job, project data)
  - Finance Service (invoicing, expenses, revenue)
  - Auth Service (shared authentication)
  - RBAC Service (shared permission management)

### Phase 6: WROS Agentic Layer
- **Duration:** Ongoing
- **Scope:** Implement 70+ agents across 12 domains
- **Approach:** Iterative - start with critical path agents
  - Thunder autonomous loop (✅ Complete)
  - AI Recruiter matching (✅ Complete)
  - Deployment Agent
  - Workforce Capacity Agent
  - Pipeline Forecast Agent
  - (and 65 more agents...)

---

## 13. KEY ARCHITECTURAL PRINCIPLES

### 13.1 Zero-Hardcoding Mandate

```
❌ NEVER hardcode:
├─ Role names ("CEO", "Recruiter", "BU Head")
├─ Permission strings ("recruitment.manage", "finance.view")
├─ Module names (show module list in code)
├─ User access rules (manager sees reports)
├─ Department-based data filtering
├─ Geographic filters (location, BU)
└─ Service URLs or configurations

✅ ALWAYS use:
├─ Database queries for role templates
├─ Database queries for permissions
├─ Dynamic module loading based on role
├─ Configuration service for settings
├─ Hierarchical permission inheritance
└─ Data scoping via WHERE clauses
```

### 13.2 Hierarchy-Based Permission Cascading

```
✅ Manager automatically sees:
├─ All direct reports
├─ All reports' reports (entire chain)
├─ All data those reports can access
└─ No code changes needed to adjust hierarchy

✅ Department-based data silos:
├─ Recruitment cannot see bill_rate
├─ Delivery cannot see candidate feedback
├─ HR cannot see financial data
└─ Enforced via query filters, not code
```

### 13.3 Database is Source of Truth

```
Role definitions → Database (not code)
Permission assignments → Database (not code)
Module access → Database (not code)
User role assignments → Database (not code)
Hierarchy structure → Database (not code)
Data access scope → Query filters (not code)

Code: "Query database. Render what user can access. Enforce what database allows."
```

### 13.4 Multi-Tenant Ready

```
ALL tables have: tenant_id
ALL queries have: WHERE tenant_id = current_tenant
ALL data is: Logically isolated
ALL features are: Tenant-aware

Future companies added by: Adding rows to tenant table (no code change)
```

---

## 14. REFERENCE & NEXT STEPS

### 14.1 Key Files to Update Before Development

- [ ] `app/models/__init__.py` - Ensure all models imported
- [ ] `app/config/permissions_registry.py` - Create (permission constants only, database-driven)
- [ ] `app/core/database.py` - Verify PostgreSQL only (no SQLite)
- [ ] `app/core/dependencies.py` - Rewrite (permission-based, not role-based)
- [ ] `app/services/permission_helper.py` - Dynamic permission queries
- [ ] `app/services/rbac_service.py` - Database-driven RBAC
- [ ] Frontend: `src/utils/permissions.js` - Dynamic permission checks
- [ ] Frontend: `src/layout/Shell.js` - Dynamic navigation

### 14.2 Implementation Checklist

**Before any development:**
- [ ] Confirm this architecture document
- [ ] Review with team (backend, frontend, devops)
- [ ] Confirm database schema for multi-tenancy
- [ ] Confirm role template structure
- [ ] Confirm permission model

**Phase 2 (Backend Rewrite):**
- [ ] Remove all 92 hardcoded role/permission references
- [ ] Implement dynamic permission queries
- [ ] Implement dynamic role template loading
- [ ] Implement hierarchical permission cascading
- [ ] Implement data scoping filters

**Phase 3 (Admin UI):**
- [ ] Build Role Template Management screen
- [ ] Build Module Management screen
- [ ] Build Permission Matrix UI
- [ ] Build User Role Assignment screen

**Phase 4 (Frontend):**
- [ ] Dynamic navigation based on permissions
- [ ] Dynamic module rendering
- [ ] Dynamic component visibility

### 14.3 Success Metrics

```
✅ Zero hardcoded role names in codebase
✅ Zero hardcoded permission strings (except registry)
✅ All roles configurable via admin UI
✅ All permissions configurable via admin UI
✅ New role created = zero code change
✅ New permission assigned = zero code change
✅ Org hierarchy changes = zero code change
✅ Multi-tenant ready for Phase 2
✅ All 92 findings eliminated
✅ Database-driven architecture achieved
```

---

**END OF MASTER ARCHITECTURE DOCUMENT**

**This document is the single source of truth for all WROS development.**

**Any deviation from this architecture requires explicit approval.**

**No development should begin without this document being reviewed and confirmed by the team.**
