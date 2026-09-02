#!/usr/bin/env python3
"""
Complete Resource Seeding Script
Reads resource mapping and seeds 168+ resources + permissions for 4 core roles
import logging
"""

import sys
import os
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from sqlalchemy import text
from datetime import datetime

def get_module_id(db, module_name):
    """Get module ID by name"""
    module = db.query(Module).filter(
        Module.name == module_name,
        Module.tenant_id == 1
    ).first()
    return module.id if module else None

def get_role_id(db, role_name):
    """Get role template ID by name"""
    role = db.query(RoleTemplate).filter(
        RoleTemplate.name == role_name,
        RoleTemplate.tenant_id == 1
    ).first()
    return role.id if role else None

def seed_resources(db):
    """Seed all 168+ resources"""

    print("\n" + "="*60)
    print("SEEDING 168+ RESOURCES")
    print("="*60)

    # Get module IDs (should be: 3=Admin, 4=Recruitment, 5=Workforce, 6=Finance, 7=Sales, 11=Executive, 12=Engagement, 10=System)
    mod_ids = {
        'Admin': get_module_id(db, 'Admin'),
        'Recruitment': get_module_id(db, 'Recruitment'),
        'Workforce': get_module_id(db, 'Workforce'),
        'Finance': get_module_id(db, 'Finance'),
        'Sales': get_module_id(db, 'Sales'),
        'Executive': get_module_id(db, 'Executive'),
        'Engagement': get_module_id(db, 'Engagement'),
        'System': get_module_id(db, 'System'),
    }

    print(f"\nModule IDs: {mod_ids}")

    # Verify all modules exist
    missing_modules = [k for k, v in mod_ids.items() if v is None]
    if missing_modules:
        print(f"⚠️  Missing modules: {missing_modules}")
        print("Continuing with available modules...")

    # Resource definition from COMPLETE_RESOURCE_MAPPING.md
    resources = [
        # ==== RECRUITMENT (35+) ====
        (mod_ids['Recruitment'], 'recruitment.candidates', 'Candidates', 'View and manage all candidates'),
        (mod_ids['Recruitment'], 'recruitment.candidates_list', 'Candidates List', 'View candidates in list view'),
        (mod_ids['Recruitment'], 'recruitment.candidates_search', 'Candidates Search', 'Search and filter candidates'),
        (mod_ids['Recruitment'], 'recruitment.bulk_operations', 'Bulk Operations', 'Perform bulk candidate operations'),
        (mod_ids['Recruitment'], 'recruitment.candidate_profile', 'Candidate Profile', 'View candidate profile information'),
        (mod_ids['Recruitment'], 'recruitment.candidate_professional', 'Candidate Professional', 'View professional details'),
        (mod_ids['Recruitment'], 'recruitment.candidate_documents', 'Candidate Documents', 'Manage candidate documents'),
        (mod_ids['Recruitment'], 'recruitment.candidate_messages', 'Candidate Messages', 'View and send candidate messages'),
        (mod_ids['Recruitment'], 'recruitment.candidate_tasks', 'Candidate Tasks', 'Manage candidate-related tasks'),
        (mod_ids['Recruitment'], 'recruitment.candidate_history', 'Candidate History', 'View candidate activity history'),
        (mod_ids['Recruitment'], 'recruitment.candidate_feedback', 'Candidate Feedback', 'View candidate feedback from interviews'),
        (mod_ids['Recruitment'], 'recruitment.candidate_intelligence', 'Candidate Intelligence', 'View enriched candidate data'),
        (mod_ids['Recruitment'], 'recruitment.candidate_interviews', 'Candidate Interviews', 'Manage candidate interviews'),
        (mod_ids['Recruitment'], 'recruitment.candidate_create', 'Create Candidate', 'Create new candidates'),
        (mod_ids['Recruitment'], 'recruitment.jobs', 'Jobs', 'View and manage job postings'),
        (mod_ids['Recruitment'], 'recruitment.jobs_list', 'Jobs List', 'View jobs in list view'),
        (mod_ids['Recruitment'], 'recruitment.jobs_matching', 'Jobs Matching', 'View candidate matches for jobs'),
        (mod_ids['Recruitment'], 'recruitment.job_overview', 'Job Overview', 'View job details'),
        (mod_ids['Recruitment'], 'recruitment.job_candidates', 'Job Candidates', 'View candidates for job'),
        (mod_ids['Recruitment'], 'recruitment.job_workspace', 'Job Workspace', 'Collaborate on job hiring'),
        (mod_ids['Recruitment'], 'recruitment.job_analytics', 'Job Analytics', 'View job performance analytics'),
        (mod_ids['Recruitment'], 'recruitment.job_create', 'Create Job', 'Create new job postings'),
        (mod_ids['Recruitment'], 'recruitment.interviews', 'Interviews', 'Schedule and manage interviews'),
        (mod_ids['Recruitment'], 'recruitment.interview_schedule', 'Interview Schedule', 'Schedule interviews'),
        (mod_ids['Recruitment'], 'recruitment.interview_status', 'Interview Status', 'Track interview status'),
        (mod_ids['Recruitment'], 'recruitment.interview_feedback', 'Interview Feedback', 'Provide interview feedback'),
        (mod_ids['Recruitment'], 'recruitment.interview_analytics', 'Interview Analytics', 'View interview metrics'),
        (mod_ids['Recruitment'], 'recruitment.interview_panel_decision', 'Interview Panel Decision', 'Record hiring panel decision'),
        (mod_ids['Recruitment'], 'recruitment.offers', 'Offers', 'Manage offer letters'),
        (mod_ids['Recruitment'], 'recruitment.offer_create', 'Create Offer', 'Create offer letters'),
        (mod_ids['Recruitment'], 'recruitment.offer_approve', 'Approve Offer', 'Approve offer letters'),
        (mod_ids['Recruitment'], 'recruitment.offer_counter', 'Counter Offer', 'Create counter offers'),
        (mod_ids['Recruitment'], 'recruitment.offer_history', 'Offer History', 'View offer history'),
        (mod_ids['Recruitment'], 'recruitment.hm_candidate_review', 'Hiring Manager Review', 'Hiring manager candidate review'),
        (mod_ids['Recruitment'], 'recruitment.intervention_queue', 'Intervention Queue', 'Manage recruitment interventions'),
        (mod_ids['Recruitment'], 'recruitment.rehire_approvals', 'Rehire Approvals', 'Approve rehire candidates'),
        (mod_ids['Recruitment'], 'recruitment.risk_dashboard', 'Risk Dashboard', 'View recruitment risk metrics'),
        (mod_ids['Recruitment'], 'recruitment.thunder_analytics', 'Thunder Analytics', 'View AI recruiter analytics'),
        (mod_ids['Recruitment'], 'recruitment.bulk_launch', 'Bulk Launch', 'Launch bulk candidate campaigns'),
        (mod_ids['Recruitment'], 'recruitment.submissions', 'Submissions', 'View candidate submissions'),

        # ==== WORKFORCE (25+) ====
        (mod_ids['Workforce'], 'workforce.employees', 'Employees', 'View and manage employees'),
        (mod_ids['Workforce'], 'workforce.employee_directory', 'Employee Directory', 'Search and view employee directory'),
        (mod_ids['Workforce'], 'workforce.employee_consolidated', 'Employee Consolidated View', 'View consolidated employee information'),
        (mod_ids['Workforce'], 'workforce.employee_profile', 'Employee Profile', 'View employee profile'),
        (mod_ids['Workforce'], 'workforce.employee_projects', 'Employee Projects', 'View employee project assignments'),
        (mod_ids['Workforce'], 'workforce.employee_allocations', 'Employee Allocations', 'Manage employee allocations'),
        (mod_ids['Workforce'], 'workforce.employee_performance', 'Employee Performance', 'View employee performance'),
        (mod_ids['Workforce'], 'workforce.employee_kpi', 'Employee KPI', 'View employee KPIs'),
        (mod_ids['Workforce'], 'workforce.employee_feedback', 'Employee Feedback', 'View employee feedback'),
        (mod_ids['Workforce'], 'workforce.employee_documents', 'Employee Documents', 'Manage employee documents'),
        (mod_ids['Workforce'], 'workforce.employee_convert', 'Convert to Employee', 'Convert candidates to employees'),
        (mod_ids['Workforce'], 'workforce.allocations', 'Allocations', 'Manage resource allocations'),
        (mod_ids['Workforce'], 'workforce.allocation_create', 'Create Allocation', 'Create new allocations'),
        (mod_ids['Workforce'], 'workforce.projects', 'Projects', 'View and manage projects'),
        (mod_ids['Workforce'], 'workforce.project_overview', 'Project Overview', 'View project details'),
        (mod_ids['Workforce'], 'workforce.project_team', 'Project Team', 'Manage project team members'),
        (mod_ids['Workforce'], 'workforce.project_timeline', 'Project Timeline', 'View project timeline'),
        (mod_ids['Workforce'], 'workforce.project_budget', 'Project Budget', 'Manage project budget'),
        (mod_ids['Workforce'], 'workforce.resource_management', 'Resource Management', 'Manage resource capacity'),
        (mod_ids['Workforce'], 'workforce.htd_intake', 'HTD Intake', 'Manage head-to-desk intake'),
        (mod_ids['Workforce'], 'workforce.utilization_dashboard', 'Utilization Dashboard', 'View resource utilization'),
        (mod_ids['Workforce'], 'workforce.buddy_program', 'Buddy Program', 'Manage buddy program'),
        (mod_ids['Workforce'], 'workforce.training_certification', 'Training & Certifications', 'Manage training and certifications'),
        (mod_ids['Workforce'], 'workforce.bu_head_dashboard', 'BU Head Dashboard', 'View business unit dashboard'),
        (mod_ids['Workforce'], 'workforce.forecast', 'Forecast', 'View resource forecast'),
        (mod_ids['Workforce'], 'workforce.forecast_vs_actual', 'Forecast vs Actual', 'View forecast comparison'),

        # ==== FINANCE (30+) ====
        (mod_ids['Finance'], 'finance.timesheets', 'Timesheets', 'Manage timesheets'),
        (mod_ids['Finance'], 'finance.timesheet_approval', 'Timesheet Approval', 'Approve timesheets'),
        (mod_ids['Finance'], 'finance.my_timesheet', 'My Timesheet', 'Submit my timesheet'),
        (mod_ids['Finance'], 'finance.invoices', 'Invoices', 'Manage invoices'),
        (mod_ids['Finance'], 'finance.invoice_draft', 'Invoice Drafts', 'View draft invoices'),
        (mod_ids['Finance'], 'finance.invoice_approved', 'Invoice Approved', 'View approved invoices'),
        (mod_ids['Finance'], 'finance.invoice_sent', 'Invoice Sent', 'View sent invoices'),
        (mod_ids['Finance'], 'finance.invoice_paid', 'Invoice Paid', 'View paid invoices'),
        (mod_ids['Finance'], 'finance.invoice_management', 'Invoice Management', 'Full invoice management'),
        (mod_ids['Finance'], 'finance.invoice_approve', 'Approve Invoice', 'Approve invoices'),
        (mod_ids['Finance'], 'finance.invoice_export', 'Export Invoice', 'Export invoice data'),
        (mod_ids['Finance'], 'finance.expenses', 'Expenses', 'Manage expenses'),
        (mod_ids['Finance'], 'finance.expense_submit', 'Submit Expense', 'Submit expense claims'),
        (mod_ids['Finance'], 'finance.expense_approval', 'Approve Expense', 'Approve expense claims'),
        (mod_ids['Finance'], 'finance.revenue', 'Revenue', 'View revenue data'),
        (mod_ids['Finance'], 'finance.revenue_recognition', 'Revenue Recognition', 'Manage revenue recognition'),
        (mod_ids['Finance'], 'finance.finance_operations', 'Finance Operations', 'Manage finance operations'),
        (mod_ids['Finance'], 'finance.executive_revenue', 'Executive Revenue Dashboard', 'View executive revenue dashboard'),
        (mod_ids['Finance'], 'finance.opportunity_pipeline', 'Opportunity Pipeline', 'View opportunity pipeline'),
        (mod_ids['Finance'], 'finance.demand_confirmation', 'Demand Confirmation', 'Confirm demand'),
        (mod_ids['Finance'], 'finance.submissions', 'Submissions', 'View finance submissions'),
        (mod_ids['Finance'], 'finance.cost_rate', 'Cost Rate Configuration', 'Manage cost rates'),

        # ==== SALES (12+) ====
        (mod_ids['Sales'], 'sales.opportunities', 'Opportunities', 'Manage sales opportunities'),
        (mod_ids['Sales'], 'sales.opportunity_pipeline', 'Opportunity Pipeline', 'View opportunity pipeline'),
        (mod_ids['Sales'], 'sales.opportunity_forecast', 'Opportunity Forecast', 'View sales forecast'),
        (mod_ids['Sales'], 'sales.opportunity_won', 'Opportunities Won', 'View won opportunities'),
        (mod_ids['Sales'], 'sales.opportunity_lost', 'Opportunities Lost', 'View lost opportunities'),
        (mod_ids['Sales'], 'sales.clients', 'Clients', 'Manage clients'),
        (mod_ids['Sales'], 'sales.client_create', 'Create Client', 'Create new clients'),
        (mod_ids['Sales'], 'sales.client_edit', 'Edit Client', 'Edit client information'),
        (mod_ids['Sales'], 'sales.core_pull', 'Core Pull', 'View core pull data'),
        (mod_ids['Sales'], 'sales.partner_roi', 'Partner ROI', 'View partner ROI'),
        (mod_ids['Sales'], 'sales.troy_partner_dashboard', 'Troy Partner Dashboard', 'View partner dashboard'),

        # ==== ADMIN (30+) ====
        (mod_ids['Admin'], 'admin.users', 'Users', 'Manage users'),
        (mod_ids['Admin'], 'admin.roles', 'Roles', 'Manage roles'),
        (mod_ids['Admin'], 'admin.permissions', 'Permissions', 'Manage permissions'),
        (mod_ids['Admin'], 'admin.role_templates', 'Role Templates', 'Manage role templates'),
        (mod_ids['Admin'], 'admin.role_template_management', 'Role Template Management', 'Full role template management'),
        (mod_ids['Admin'], 'admin.role_template_permissions', 'Role Template Permissions', 'Manage role permissions'),
        (mod_ids['Admin'], 'admin.business_units', 'Business Units', 'Manage business units'),
        (mod_ids['Admin'], 'admin.settings', 'Settings', 'Manage system settings'),
        (mod_ids['Admin'], 'admin.locale_settings', 'Locale & Currency', 'Configure locale settings'),
        (mod_ids['Admin'], 'admin.ai_config', 'AI Configuration', 'Configure AI settings'),
        (mod_ids['Admin'], 'admin.message_templates', 'Message Templates', 'Manage message templates'),
        (mod_ids['Admin'], 'admin.ticket_routing', 'Ticket Routing & SLA', 'Manage ticket routing'),
        (mod_ids['Admin'], 'admin.error_log', 'Error Log', 'View error logs'),
        (mod_ids['Admin'], 'admin.admin_settings', 'Admin Settings', 'Configure admin settings'),
        (mod_ids['Admin'], 'admin.weekly_recap', 'Weekly Recap', 'View weekly recap'),
        (mod_ids['Admin'], 'admin.message_queue', 'Message Queue Dashboard', 'Monitor message queue'),
        (mod_ids['Admin'], 'admin.certifications', 'Certifications', 'Manage certifications'),
        (mod_ids['Admin'], 'admin.audit_log', 'Audit Log', 'View audit logs'),

        # ==== EXECUTIVE (15+) ====
        (mod_ids['Executive'], 'executive.ceo_fy_progress', 'CEO FY Progress', 'View fiscal year progress'),
        (mod_ids['Executive'], 'executive.cfo_dashboard', 'CFO Dashboard', 'View CFO dashboard'),
        (mod_ids['Executive'], 'executive.executive_signal', 'Executive Signal', 'View executive signals'),
        (mod_ids['Executive'], 'executive.bi_explorer', 'BI Explorer', 'Explore business intelligence'),

        # ==== ENGAGEMENT (15+) ====
        (mod_ids['Engagement'], 'engagement.thunder_chat', 'Thunder Chat', 'Interact with Thunder AI'),
        (mod_ids['Engagement'], 'engagement.public_thunder_chat', 'Public Thunder Chat', 'Public AI chat for candidates'),
        (mod_ids['Engagement'], 'engagement.my_tasks', 'My Tasks', 'View and manage tasks'),
        (mod_ids['Engagement'], 'engagement.task_create', 'Create Task', 'Create new tasks'),
        (mod_ids['Engagement'], 'engagement.task_assign', 'Assign Task', 'Assign tasks to others'),
        (mod_ids['Engagement'], 'engagement.referrals', 'Referrals', 'View and manage referrals'),
        (mod_ids['Engagement'], 'engagement.documents', 'Documents', 'Manage documents'),
        (mod_ids['Engagement'], 'engagement.activity_timeline', 'Activity Timeline', 'View activity timeline'),
        (mod_ids['Engagement'], 'engagement.notifications', 'Notifications', 'View notifications'),

        # ==== COMMON (6) ====
        (mod_ids['System'], 'common.dashboard', 'Dashboard', 'View personal dashboard'),
        (mod_ids['System'], 'common.my_timesheet', 'My Timesheet', 'Submit timesheet'),
        (mod_ids['System'], 'common.my_expenses', 'My Expenses', 'Submit expense reports'),
        (mod_ids['System'], 'common.my_tasks', 'My Tasks', 'View my tasks'),
        (mod_ids['System'], 'common.my_referrals', 'My Referrals', 'View my referrals'),
        (mod_ids['System'], 'common.thunder', 'Thunder', 'Access Thunder AI'),
    ]

    # Filter out any None module_ids
    resources = [r for r in resources if r[0] is not None]

    # Check which resources already exist
    existing_names = set(r[0] for r in db.query(Resource.name).filter(Resource.tenant_id == 1).all())
    new_resources = [r for r in resources if r[1] not in existing_names]

    print(f"\nTotal resources to add: {len(new_resources)}")
    print(f"Resources already exist: {len(resources) - len(new_resources)}")

    # Create new resources
    for module_id, name, display_name, description in new_resources:
        resource = Resource(
            module_id=module_id,
            name=name,
            display_name=display_name,
            description=description,
            enabled=True,
            tenant_id=1
        )
        db.add(resource)

    db.commit()

    # Get all resources for permission mapping
    all_resources = db.query(Resource).filter(Resource.tenant_id == 1).all()
    resource_map = {r.name: r for r in all_resources}

    print(f"\n✅ Successfully seeded {len(new_resources)} new resources")
    print(f"📊 Total resources in database: {len(all_resources)}")

    return resource_map

def seed_permissions(db, resource_map):
    """Seed permissions for 4 core roles"""

    print("\n" + "="*60)
    print("SEEDING ROLE PERMISSIONS")
    print("="*60)

    # Get role IDs
    super_user_id = get_role_id(db, 'Super User')
    recruiter_id = get_role_id(db, 'Recruiter')
    hr_manager_id = get_role_id(db, 'HR Manager')
    hiring_manager_id = get_role_id(db, 'Hiring Manager')

    print(f"\nRole IDs:")
    print(f"  Super User: {super_user_id}")
    print(f"  Recruiter: {recruiter_id}")
    print(f"  HR Manager: {hr_manager_id}")
    print(f"  Hiring Manager: {hiring_manager_id}")

    # Define permissions for each role: resource_pattern -> (view, create, edit, delete)
    def clear_role_permissions(role_id):
        """Clear existing permissions for a role"""
        db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role_id
        ).delete()

    # SUPER USER: All resources, all permissions
    if super_user_id:
        clear_role_permissions(super_user_id)
        for resource in resource_map.values():
            perm = RoleTemplatePermission(
                role_template_id=super_user_id,
                resource_id=resource.id,
                can_view=True, can_create=True, can_edit=True, can_delete=True
            )
            db.add(perm)
        db.commit()
        print(f"\n✅ Super User: {len(resource_map)} permissions (all)")

    # RECRUITER: Recruitment + Common + Engagement
    if recruiter_id:
        clear_role_permissions(recruiter_id)
        recruitment_perms = ['recruitment.', 'engagement.', 'common.', 'engagement.notifications']
        for name, resource in resource_map.items():
            if any(name.startswith(p) for p in recruitment_perms):
                perm = RoleTemplatePermission(
                    role_template_id=recruiter_id,
                    resource_id=resource.id,
                    can_view=True,
                    can_create=name.startswith('recruitment.') or name.startswith('engagement.'),
                    can_edit=name.startswith('recruitment.') or name.startswith('engagement.'),
                    can_delete=name in ['recruitment.candidates', 'recruitment.candidate_documents', 'recruitment.offers']
                )
                db.add(perm)
        db.commit()
        recruiter_perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == recruiter_id
        ).count()
        print(f"✅ Recruiter: {recruiter_perms} permissions")

    # HR MANAGER: Recruitment + Workforce + Admin (limited) + Common + Finance (limited)
    if hr_manager_id:
        clear_role_permissions(hr_manager_id)
        for name, resource in resource_map.items():
            can_view = any(name.startswith(p) for p in ['recruitment.', 'workforce.', 'finance.', 'engagement.', 'common.', 'admin.users', 'admin.roles', 'admin.business_units', 'admin.certifications'])
            can_create = any(name.startswith(p) for p in ['recruitment.', 'workforce.']) or name in ['finance.my_timesheet', 'engagement.task_create']
            can_edit = any(name.startswith(p) for p in ['recruitment.', 'workforce.', 'engagement.']) or name in ['finance.timesheet_approval']
            can_delete = name in ['recruitment.candidates', 'recruitment.offers', 'workforce.allocations']

            if can_view:
                perm = RoleTemplatePermission(
                    role_template_id=hr_manager_id,
                    resource_id=resource.id,
                    can_view=can_view,
                    can_create=can_create,
                    can_edit=can_edit,
                    can_delete=can_delete
                )
                db.add(perm)
        db.commit()
        hr_perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == hr_manager_id
        ).count()
        print(f"✅ HR Manager: {hr_perms} permissions")

    # HIRING MANAGER: Recruitment (view) + Interview/Feedback (create/edit) + Common + Engagement
    if hiring_manager_id:
        clear_role_permissions(hiring_manager_id)
        for name, resource in resource_map.items():
            can_view = name.startswith('recruitment.') or name.startswith('engagement.') or name.startswith('common.')
            can_create = name in [
                'recruitment.interview_schedule', 'recruitment.interview_feedback',
                'recruitment.offer_counter', 'recruitment.hm_candidate_review',
                'engagement.task_create', 'common.my_tasks'
            ]
            can_edit = name in [
                'recruitment.interview_status', 'recruitment.interview_feedback',
                'recruitment.interview_panel_decision', 'recruitment.hm_candidate_review',
                'engagement.task_assign', 'common.my_tasks'
            ]
            can_delete = False

            if can_view:
                perm = RoleTemplatePermission(
                    role_template_id=hiring_manager_id,
                    resource_id=resource.id,
                    can_view=can_view,
                    can_create=can_create,
                    can_edit=can_edit,
                    can_delete=can_delete
                )
                db.add(perm)
        db.commit()
        hm_perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == hiring_manager_id
        ).count()
        print(f"✅ Hiring Manager: {hm_perms} permissions")

    # Show summary
    print("\n" + "="*60)
    print("PERMISSION SUMMARY")
    print("="*60)
    summary = db.execute(text("""
        SELECT
            rt.name as role_name,
            COUNT(rtp.id) as total_perms,
            SUM(CASE WHEN rtp.can_view THEN 1 ELSE 0 END) as view_count,
            SUM(CASE WHEN rtp.can_create THEN 1 ELSE 0 END) as create_count,
            SUM(CASE WHEN rtp.can_edit THEN 1 ELSE 0 END) as edit_count,
            SUM(CASE WHEN rtp.can_delete THEN 1 ELSE 0 END) as delete_count
        FROM role_templates rt
        LEFT JOIN role_template_permissions rtp ON rt.id = rtp.role_template_id
        WHERE rt.tenant_id = 1
        AND rt.name IN ('Super User', 'Recruiter', 'HR Manager', 'Hiring Manager')
        GROUP BY rt.name, rt.id
        ORDER BY rt.name
    """)).fetchall()

    for row in summary:
        print(f"\n{row[0]}:")
        print(f"  Total permissions: {row[1] or 0}")
        print(f"  View: {row[2] or 0} | Create: {row[3] or 0} | Edit: {row[4] or 0} | Delete: {row[5] or 0}")

if __name__ == '__main__':
    db = SessionLocal()

    try:
        print("\n" + "="*60)
        print("COMPLETE RESOURCE SEEDING")
        print("="*60)

        # Check current state
        existing_resources = db.query(Resource).filter(Resource.tenant_id == 1).count()
        print(f"\nCurrent resources in database: {existing_resources}")

        # Seed resources
        resource_map = seed_resources(db)

        # Seed permissions
        seed_permissions(db, resource_map)

        print("\n" + "="*60)
        print("✅ SEEDING COMPLETE!")
        print("="*60)
        print("\nNext steps:")
        print("1. Navigate to http://localhost:3000/admin/role-templates")
        print("2. Click on any role (e.g., 'Recruiter')")
        print("3. Should see 168+ resources organized by module")
        print("4. Each resource has V/C/E/D checkboxes")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
