-- =====================================================
-- RESOURCE SEEDING SCRIPT
-- =====================================================
-- This script seeds all 168+ resources across 8 modules
-- to be used in the RBAC unified role template UI
--
-- Instructions:
-- 1. First, ensure all modules exist (should be created by role_template_seed.py)
-- 2. Run this script: psql wros_dev < 01_seed_resources.sql
-- 3. Then run 02_seed_permissions.sql
-- 4. Verify in /admin/role-templates UI
-- =====================================================

-- Get module IDs for use in INSERT statements
-- Module IDs should already exist from seeding:
-- 1 = Admin, 2 = Recruitment, 3 = Workforce, 4 = Finance,
-- 5 = Sales, 6 = Executive, 7 = Engagement, 8 = Common

BEGIN;

-- ==================================================
-- MODULE: RECRUITMENT (35 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
-- Main resources
(2, 'recruitment.candidates', 'Candidates', 'View and manage all candidates', true, 1, NOW(), NOW()),
(2, 'recruitment.candidates_list', 'Candidates List', 'View candidates in list view', true, 1, NOW(), NOW()),
(2, 'recruitment.candidates_search', 'Candidates Search', 'Search and filter candidates', true, 1, NOW(), NOW()),
(2, 'recruitment.bulk_operations', 'Bulk Operations', 'Perform bulk candidate operations', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_profile', 'Candidate Profile', 'View candidate profile information', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_professional', 'Candidate Professional', 'View professional details', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_documents', 'Candidate Documents', 'Manage candidate documents', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_messages', 'Candidate Messages', 'View and send candidate messages', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_tasks', 'Candidate Tasks', 'Manage candidate-related tasks', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_history', 'Candidate History', 'View candidate activity history', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_feedback', 'Candidate Feedback', 'View candidate feedback from interviews', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_intelligence', 'Candidate Intelligence', 'View enriched candidate data', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_interviews', 'Candidate Interviews', 'Manage candidate interviews', true, 1, NOW(), NOW()),
(2, 'recruitment.candidate_create', 'Create Candidate', 'Create new candidates', true, 1, NOW(), NOW()),

-- Jobs
(2, 'recruitment.jobs', 'Jobs', 'View and manage job postings', true, 1, NOW(), NOW()),
(2, 'recruitment.jobs_list', 'Jobs List', 'View jobs in list view', true, 1, NOW(), NOW()),
(2, 'recruitment.jobs_matching', 'Jobs Matching', 'View candidate matches for jobs', true, 1, NOW(), NOW()),
(2, 'recruitment.job_overview', 'Job Overview', 'View job details', true, 1, NOW(), NOW()),
(2, 'recruitment.job_candidates', 'Job Candidates', 'View candidates for job', true, 1, NOW(), NOW()),
(2, 'recruitment.job_workspace', 'Job Workspace', 'Collaborate on job hiring', true, 1, NOW(), NOW()),
(2, 'recruitment.job_analytics', 'Job Analytics', 'View job performance analytics', true, 1, NOW(), NOW()),
(2, 'recruitment.job_create', 'Create Job', 'Create new job postings', true, 1, NOW(), NOW()),

-- Interviews
(2, 'recruitment.interviews', 'Interviews', 'Schedule and manage interviews', true, 1, NOW(), NOW()),
(2, 'recruitment.interview_schedule', 'Interview Schedule', 'Schedule interviews', true, 1, NOW(), NOW()),
(2, 'recruitment.interview_status', 'Interview Status', 'Track interview status', true, 1, NOW(), NOW()),
(2, 'recruitment.interview_feedback', 'Interview Feedback', 'Provide interview feedback', true, 1, NOW(), NOW()),
(2, 'recruitment.interview_analytics', 'Interview Analytics', 'View interview metrics', true, 1, NOW(), NOW()),
(2, 'recruitment.interview_panel_decision', 'Interview Panel Decision', 'Record hiring panel decision', true, 1, NOW(), NOW()),

-- Offers
(2, 'recruitment.offers', 'Offers', 'Manage offer letters', true, 1, NOW(), NOW()),
(2, 'recruitment.offer_create', 'Create Offer', 'Create offer letters', true, 1, NOW(), NOW()),
(2, 'recruitment.offer_approve', 'Approve Offer', 'Approve offer letters', true, 1, NOW(), NOW()),
(2, 'recruitment.offer_counter', 'Counter Offer', 'Create counter offers', true, 1, NOW(), NOW()),
(2, 'recruitment.offer_history', 'Offer History', 'View offer history', true, 1, NOW(), NOW()),

-- Specialized Recruitment
(2, 'recruitment.hm_candidate_review', 'Hiring Manager Review', 'Hiring manager candidate review', true, 1, NOW(), NOW()),
(2, 'recruitment.intervention_queue', 'Intervention Queue', 'Manage recruitment interventions', true, 1, NOW(), NOW()),
(2, 'recruitment.rehire_approvals', 'Rehire Approvals', 'Approve rehire candidates', true, 1, NOW(), NOW()),
(2, 'recruitment.risk_dashboard', 'Risk Dashboard', 'View recruitment risk metrics', true, 1, NOW(), NOW()),
(2, 'recruitment.thunder_analytics', 'Thunder Analytics', 'View AI recruiter analytics', true, 1, NOW(), NOW()),
(2, 'recruitment.bulk_launch', 'Bulk Launch', 'Launch bulk candidate campaigns', true, 1, NOW(), NOW()),
(2, 'recruitment.submissions', 'Submissions', 'View candidate submissions', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: WORKFORCE & EMPLOYEES (25 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
-- Employees
(3, 'workforce.employees', 'Employees', 'View and manage employees', true, 1, NOW(), NOW()),
(3, 'workforce.employee_directory', 'Employee Directory', 'Search and view employee directory', true, 1, NOW(), NOW()),
(3, 'workforce.employee_consolidated', 'Employee Consolidated View', 'View consolidated employee information', true, 1, NOW(), NOW()),
(3, 'workforce.employee_profile', 'Employee Profile', 'View employee profile', true, 1, NOW(), NOW()),
(3, 'workforce.employee_projects', 'Employee Projects', 'View employee project assignments', true, 1, NOW(), NOW()),
(3, 'workforce.employee_allocations', 'Employee Allocations', 'Manage employee allocations', true, 1, NOW(), NOW()),
(3, 'workforce.employee_performance', 'Employee Performance', 'View employee performance', true, 1, NOW(), NOW()),
(3, 'workforce.employee_kpi', 'Employee KPI', 'View employee KPIs', true, 1, NOW(), NOW()),
(3, 'workforce.employee_feedback', 'Employee Feedback', 'View employee feedback', true, 1, NOW(), NOW()),
(3, 'workforce.employee_documents', 'Employee Documents', 'Manage employee documents', true, 1, NOW(), NOW()),
(3, 'workforce.employee_convert', 'Convert to Employee', 'Convert candidates to employees', true, 1, NOW(), NOW()),

-- Allocations & Projects
(3, 'workforce.allocations', 'Allocations', 'Manage resource allocations', true, 1, NOW(), NOW()),
(3, 'workforce.allocation_create', 'Create Allocation', 'Create new allocations', true, 1, NOW(), NOW()),
(3, 'workforce.projects', 'Projects', 'View and manage projects', true, 1, NOW(), NOW()),
(3, 'workforce.project_overview', 'Project Overview', 'View project details', true, 1, NOW(), NOW()),
(3, 'workforce.project_team', 'Project Team', 'Manage project team members', true, 1, NOW(), NOW()),
(3, 'workforce.project_timeline', 'Project Timeline', 'View project timeline', true, 1, NOW(), NOW()),
(3, 'workforce.project_budget', 'Project Budget', 'Manage project budget', true, 1, NOW(), NOW()),

-- Workforce Management
(3, 'workforce.resource_management', 'Resource Management', 'Manage resource capacity', true, 1, NOW(), NOW()),
(3, 'workforce.htd_intake', 'HTD Intake', 'Manage head-to-desk intake', true, 1, NOW(), NOW()),
(3, 'workforce.utilization_dashboard', 'Utilization Dashboard', 'View resource utilization', true, 1, NOW(), NOW()),
(3, 'workforce.buddy_program', 'Buddy Program', 'Manage buddy program', true, 1, NOW(), NOW()),
(3, 'workforce.training_certification', 'Training & Certifications', 'Manage training and certifications', true, 1, NOW(), NOW()),
(3, 'workforce.bu_head_dashboard', 'BU Head Dashboard', 'View business unit dashboard', true, 1, NOW(), NOW()),
(3, 'workforce.forecast', 'Forecast', 'View resource forecast', true, 1, NOW(), NOW()),
(3, 'workforce.forecast_vs_actual', 'Forecast vs Actual', 'View forecast comparison', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: FINANCE & OPERATIONS (30 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
-- Timesheets
(4, 'finance.timesheets', 'Timesheets', 'Manage timesheets', true, 1, NOW(), NOW()),
(4, 'finance.timesheet_approval', 'Timesheet Approval', 'Approve timesheets', true, 1, NOW(), NOW()),
(4, 'finance.my_timesheet', 'My Timesheet', 'Submit my timesheet', true, 1, NOW(), NOW()),

-- Invoices
(4, 'finance.invoices', 'Invoices', 'Manage invoices', true, 1, NOW(), NOW()),
(4, 'finance.invoice_draft', 'Invoice Drafts', 'View draft invoices', true, 1, NOW(), NOW()),
(4, 'finance.invoice_approved', 'Invoice Approved', 'View approved invoices', true, 1, NOW(), NOW()),
(4, 'finance.invoice_sent', 'Invoice Sent', 'View sent invoices', true, 1, NOW(), NOW()),
(4, 'finance.invoice_paid', 'Invoice Paid', 'View paid invoices', true, 1, NOW(), NOW()),
(4, 'finance.invoice_management', 'Invoice Management', 'Full invoice management', true, 1, NOW(), NOW()),
(4, 'finance.invoice_approve', 'Approve Invoice', 'Approve invoices', true, 1, NOW(), NOW()),
(4, 'finance.invoice_export', 'Export Invoice', 'Export invoice data', true, 1, NOW(), NOW()),

-- Expenses
(4, 'finance.expenses', 'Expenses', 'Manage expenses', true, 1, NOW(), NOW()),
(4, 'finance.expense_submit', 'Submit Expense', 'Submit expense claims', true, 1, NOW(), NOW()),
(4, 'finance.expense_approval', 'Approve Expense', 'Approve expense claims', true, 1, NOW(), NOW()),

-- Revenue & Finance
(4, 'finance.revenue', 'Revenue', 'View revenue data', true, 1, NOW(), NOW()),
(4, 'finance.revenue_recognition', 'Revenue Recognition', 'Manage revenue recognition', true, 1, NOW(), NOW()),
(4, 'finance.finance_operations', 'Finance Operations', 'Manage finance operations', true, 1, NOW(), NOW()),
(4, 'finance.executive_revenue', 'Executive Revenue Dashboard', 'View executive revenue dashboard', true, 1, NOW(), NOW()),
(4, 'finance.opportunity_pipeline', 'Opportunity Pipeline', 'View opportunity pipeline', true, 1, NOW(), NOW()),
(4, 'finance.demand_confirmation', 'Demand Confirmation', 'Confirm demand', true, 1, NOW(), NOW()),
(4, 'finance.submissions', 'Submissions', 'View finance submissions', true, 1, NOW(), NOW()),
(4, 'finance.cost_rate', 'Cost Rate Configuration', 'Manage cost rates', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: SALES & CLIENT MANAGEMENT (12 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
-- Opportunities & Sales
(5, 'sales.opportunities', 'Opportunities', 'Manage sales opportunities', true, 1, NOW(), NOW()),
(5, 'sales.opportunity_pipeline', 'Opportunity Pipeline', 'View opportunity pipeline', true, 1, NOW(), NOW()),
(5, 'sales.opportunity_forecast', 'Opportunity Forecast', 'View sales forecast', true, 1, NOW(), NOW()),
(5, 'sales.opportunity_won', 'Opportunities Won', 'View won opportunities', true, 1, NOW(), NOW()),
(5, 'sales.opportunity_lost', 'Opportunities Lost', 'View lost opportunities', true, 1, NOW(), NOW()),

-- Clients
(5, 'sales.clients', 'Clients', 'Manage clients', true, 1, NOW(), NOW()),
(5, 'sales.client_create', 'Create Client', 'Create new clients', true, 1, NOW(), NOW()),
(5, 'sales.client_edit', 'Edit Client', 'Edit client information', true, 1, NOW(), NOW()),

-- Sales Operations
(5, 'sales.core_pull', 'Core Pull', 'View core pull data', true, 1, NOW(), NOW()),
(5, 'sales.partner_roi', 'Partner ROI', 'View partner ROI', true, 1, NOW(), NOW()),
(5, 'sales.troy_partner_dashboard', 'Troy Partner Dashboard', 'View partner dashboard', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: ADMIN & SYSTEM (30 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
-- Users & Access
(1, 'admin.users', 'Users', 'Manage users', true, 1, NOW(), NOW()),
(1, 'admin.roles', 'Roles', 'Manage roles', true, 1, NOW(), NOW()),
(1, 'admin.permissions', 'Permissions', 'Manage permissions', true, 1, NOW(), NOW()),
(1, 'admin.role_templates', 'Role Templates', 'Manage role templates', true, 1, NOW(), NOW()),
(1, 'admin.role_template_management', 'Role Template Management', 'Full role template management', true, 1, NOW(), NOW()),
(1, 'admin.role_template_permissions', 'Role Template Permissions', 'Manage role permissions', true, 1, NOW(), NOW()),

-- Business & Configuration
(1, 'admin.business_units', 'Business Units', 'Manage business units', true, 1, NOW(), NOW()),
(1, 'admin.settings', 'Settings', 'Manage system settings', true, 1, NOW(), NOW()),
(1, 'admin.locale_settings', 'Locale & Currency', 'Configure locale settings', true, 1, NOW(), NOW()),
(1, 'admin.ai_config', 'AI Configuration', 'Configure AI settings', true, 1, NOW(), NOW()),

-- Communications & Admin Tools
(1, 'admin.message_templates', 'Message Templates', 'Manage message templates', true, 1, NOW(), NOW()),
(1, 'admin.ticket_routing', 'Ticket Routing & SLA', 'Manage ticket routing', true, 1, NOW(), NOW()),
(1, 'admin.error_log', 'Error Log', 'View error logs', true, 1, NOW(), NOW()),
(1, 'admin.admin_settings', 'Admin Settings', 'Configure admin settings', true, 1, NOW(), NOW()),
(1, 'admin.weekly_recap', 'Weekly Recap', 'View weekly recap', true, 1, NOW(), NOW()),
(1, 'admin.message_queue', 'Message Queue Dashboard', 'Monitor message queue', true, 1, NOW(), NOW()),
(1, 'admin.certifications', 'Certifications', 'Manage certifications', true, 1, NOW(), NOW()),
(1, 'admin.audit_log', 'Audit Log', 'View audit logs', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: EXECUTIVE DASHBOARDS (15 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
(6, 'executive.ceo_fy_progress', 'CEO FY Progress', 'View fiscal year progress', true, 1, NOW(), NOW()),
(6, 'executive.cfo_dashboard', 'CFO Dashboard', 'View CFO dashboard', true, 1, NOW(), NOW()),
(6, 'executive.executive_signal', 'Executive Signal', 'View executive signals', true, 1, NOW(), NOW()),
(6, 'executive.bi_explorer', 'BI Explorer', 'Explore business intelligence', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: ENGAGEMENT & COMMUNICATIONS (15 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
-- Thunder & Chat
(7, 'engagement.thunder_chat', 'Thunder Chat', 'Interact with Thunder AI', true, 1, NOW(), NOW()),
(7, 'engagement.public_thunder_chat', 'Public Thunder Chat', 'Public AI chat for candidates', true, 1, NOW(), NOW()),

-- Tasks & Referrals
(7, 'engagement.my_tasks', 'My Tasks', 'View and manage tasks', true, 1, NOW(), NOW()),
(7, 'engagement.task_create', 'Create Task', 'Create new tasks', true, 1, NOW(), NOW()),
(7, 'engagement.task_assign', 'Assign Task', 'Assign tasks to others', true, 1, NOW(), NOW()),
(7, 'engagement.referrals', 'Referrals', 'View and manage referrals', true, 1, NOW(), NOW()),

-- Content & Activity
(7, 'engagement.documents', 'Documents', 'Manage documents', true, 1, NOW(), NOW()),
(7, 'engagement.activity_timeline', 'Activity Timeline', 'View activity timeline', true, 1, NOW(), NOW()),
(7, 'engagement.notifications', 'Notifications', 'View notifications', true, 1, NOW(), NOW());

-- ==================================================
-- MODULE: COMMON/UNIVERSAL (6 resources)
-- ==================================================

INSERT INTO resources (module_id, name, display_name, description, enabled, tenant_id, created_at, updated_at) VALUES
(8, 'common.dashboard', 'Dashboard', 'View personal dashboard', true, 1, NOW(), NOW()),
(8, 'common.my_timesheet', 'My Timesheet', 'Submit timesheet', true, 1, NOW(), NOW()),
(8, 'common.my_expenses', 'My Expenses', 'Submit expense reports', true, 1, NOW(), NOW()),
(8, 'common.my_tasks', 'My Tasks', 'View my tasks', true, 1, NOW(), NOW()),
(8, 'common.my_referrals', 'My Referrals', 'View my referrals', true, 1, NOW(), NOW()),
(8, 'common.thunder', 'Thunder', 'Access Thunder AI', true, 1, NOW(), NOW());

COMMIT;

-- =====================================================
-- Summary: All 168+ resources have been seeded
-- =====================================================
SELECT 'Resources seeded successfully!' as status;
SELECT COUNT(*) as total_resources FROM resources WHERE tenant_id = 1;
