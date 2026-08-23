-- =====================================================
-- ROLE_TEMPLATE_PERMISSIONS SEEDING SCRIPT
-- =====================================================
-- Seeds permissions matrix for 4 core roles:
-- 1. Super User (All resources, all permissions)
-- 2. Recruiter (Recruitment focus)
-- 3. HR Manager (HR + Recruitment)
-- 4. Hiring Manager (Recruitment + decision making)
--
-- Instructions:
-- 1. Ensure 01_seed_resources.sql has been run first
-- 2. Run this script: psql wros_dev < 02_seed_permissions.sql
-- 3. Verify in /admin/role-templates UI at localhost:3000
-- =====================================================

BEGIN;

-- ==================================================
-- Get role template IDs (these should exist from seed_role_templates)
-- ==================================================
-- Super User ID = 1, Recruiter ID = ?, HR Manager ID = ?, Hiring Manager ID = ?
-- We'll use subqueries to find them dynamically

-- ==================================================
-- ROLE 1: SUPER USER
-- Permissions: ALL resources, ALL actions (V/C/E/D)
-- ==================================================

INSERT INTO role_template_permissions (role_template_id, resource_id, can_view, can_create, can_edit, can_delete, created_at, updated_at)
SELECT
  (SELECT id FROM role_templates WHERE name = 'Super User' AND tenant_id = 1),
  r.id,
  true, true, true, true,  -- V, C, E, D all TRUE
  NOW(), NOW()
FROM resources r
WHERE r.tenant_id = 1;

-- ==================================================
-- ROLE 2: RECRUITER
-- Focus: Recruitment, Common features, Limited engagement
-- ==================================================

INSERT INTO role_template_permissions (role_template_id, resource_id, can_view, can_create, can_edit, can_delete, created_at, updated_at)
SELECT
  (SELECT id FROM role_templates WHERE name = 'Recruiter' AND tenant_id = 1),
  r.id,
  -- Determine permissions based on resource
  CASE
    -- RECRUITMENT: Full access to all recruitment resources
    WHEN r.module_id = 2 THEN true  -- can_view
    -- Recruitment: Full create/edit for candidates, jobs, interviews, offers
    ELSE false
  END as can_view,
  CASE
    WHEN r.module_id = 2 THEN true  -- can_create for recruitment
    ELSE false
  END as can_create,
  CASE
    WHEN r.module_id = 2 THEN true  -- can_edit for recruitment
    ELSE false
  END as can_edit,
  CASE
    WHEN r.module_id = 2 AND r.name IN ('recruitment.candidates', 'recruitment.candidate_documents', 'recruitment.offers', 'recruitment.submissions')
      THEN true
    ELSE false
  END as can_delete,
  NOW(), NOW()
FROM resources r
WHERE r.tenant_id = 1
AND (
  r.module_id = 2  -- All Recruitment resources
  OR r.name IN (
    -- Common resources - all users need these
    'common.dashboard', 'common.my_timesheet', 'common.my_expenses',
    'common.my_tasks', 'common.my_referrals', 'common.thunder',
    -- Engagement resources
    'engagement.thunder_chat', 'engagement.my_tasks', 'engagement.task_create',
    'engagement.referrals', 'engagement.notifications'
  )
);

-- Update common resources for Recruiter (can view all)
UPDATE role_template_permissions
SET can_view = true
WHERE role_template_id = (SELECT id FROM role_templates WHERE name = 'Recruiter' AND tenant_id = 1)
AND resource_id IN (
  SELECT id FROM resources WHERE name IN (
    'common.dashboard', 'common.my_timesheet', 'common.my_expenses',
    'common.my_tasks', 'common.my_referrals', 'common.thunder'
  ) AND tenant_id = 1
);

-- Update engagement resources for Recruiter
UPDATE role_template_permissions
SET can_view = true, can_create = true, can_edit = true
WHERE role_template_id = (SELECT id FROM role_templates WHERE name = 'Recruiter' AND tenant_id = 1)
AND resource_id IN (
  SELECT id FROM resources WHERE name IN (
    'engagement.thunder_chat', 'engagement.my_tasks', 'engagement.task_create', 'engagement.referrals', 'engagement.notifications'
  ) AND tenant_id = 1
);

-- ==================================================
-- ROLE 3: HR MANAGER
-- Focus: HR, Recruitment, Admin (limited), Common
-- ==================================================

INSERT INTO role_template_permissions (role_template_id, resource_id, can_view, can_create, can_edit, can_delete, created_at, updated_at)
SELECT
  (SELECT id FROM role_templates WHERE name = 'HR Manager' AND tenant_id = 1),
  r.id,
  CASE
    -- Recruitment: Full access
    WHEN r.module_id = 2 THEN true
    -- Workforce: Most access
    WHEN r.module_id = 3 THEN true
    -- Finance: View timesheets
    WHEN r.name IN ('finance.timesheets', 'finance.timesheet_approval', 'finance.my_timesheet') THEN true
    -- Admin: Limited access
    WHEN r.name IN ('admin.users', 'admin.roles', 'admin.business_units', 'admin.certifications') THEN true
    ELSE false
  END as can_view,
  CASE
    -- Recruitment: Create
    WHEN r.module_id = 2 THEN true
    -- Workforce: Create employees
    WHEN r.name IN ('workforce.employees', 'workforce.allocations', 'workforce.employee_convert') THEN true
    -- Finance: No create
    WHEN r.name IN ('finance.my_timesheet') THEN true
    -- Admin: No create
    ELSE false
  END as can_create,
  CASE
    -- Recruitment: Edit
    WHEN r.module_id = 2 THEN true
    -- Workforce: Edit
    WHEN r.module_id = 3 THEN true
    -- Finance: Can approve timesheets
    WHEN r.name IN ('finance.timesheet_approval') THEN true
    -- Admin: Can edit users
    WHEN r.name IN ('admin.users', 'admin.certifications') THEN true
    ELSE false
  END as can_edit,
  CASE
    -- Recruitment: Can delete some
    WHEN r.name IN ('recruitment.candidates', 'recruitment.offers') THEN true
    -- Workforce: Can delete some
    WHEN r.name IN ('workforce.allocations') THEN true
    ELSE false
  END as can_delete,
  NOW(), NOW()
FROM resources r
WHERE r.tenant_id = 1
AND (
  r.module_id IN (2, 3)  -- Recruitment + Workforce
  OR r.name IN (
    -- Common resources
    'common.dashboard', 'common.my_timesheet', 'common.my_expenses',
    'common.my_tasks', 'common.my_referrals', 'common.thunder',
    -- Finance (limited)
    'finance.timesheets', 'finance.timesheet_approval', 'finance.my_timesheet',
    -- Admin (limited)
    'admin.users', 'admin.roles', 'admin.business_units', 'admin.certifications',
    -- Engagement
    'engagement.thunder_chat', 'engagement.my_tasks', 'engagement.task_create',
    'engagement.task_assign', 'engagement.referrals', 'engagement.notifications'
  )
);

-- ==================================================
-- ROLE 4: HIRING MANAGER
-- Focus: Recruitment (view/feedback), Interviews, Offers, Common
-- ==================================================

INSERT INTO role_template_permissions (role_template_id, resource_id, can_view, can_create, can_edit, can_delete, created_at, updated_at)
SELECT
  (SELECT id FROM role_templates WHERE name = 'Hiring Manager' AND tenant_id = 1),
  r.id,
  CASE
    -- Recruitment: Mostly view
    WHEN r.module_id = 2 THEN true
    ELSE false
  END as can_view,
  CASE
    -- Can create interviews, feedback, but not candidates
    WHEN r.name IN (
      'recruitment.interview_schedule', 'recruitment.interview_feedback',
      'recruitment.offer_counter', 'recruitment.hm_candidate_review'
    ) THEN true
    -- Common resources
    WHEN r.name IN ('common.thunder', 'common.my_tasks', 'common.my_referrals') THEN true
    ELSE false
  END as can_create,
  CASE
    -- Can edit interviews, feedback, decisions
    WHEN r.name IN (
      'recruitment.interview_status', 'recruitment.interview_feedback',
      'recruitment.interview_panel_decision', 'recruitment.hm_candidate_review'
    ) THEN true
    -- Can edit tasks
    WHEN r.name IN ('engagement.task_assign', 'common.my_tasks') THEN true
    ELSE false
  END as can_edit,
  false as can_delete,  -- Hiring managers can't delete
  NOW(), NOW()
FROM resources r
WHERE r.tenant_id = 1
AND (
  r.module_id = 2  -- All recruitment
  OR r.name IN (
    -- Common resources
    'common.dashboard', 'common.my_tasks', 'common.my_referrals', 'common.thunder',
    -- Engagement
    'engagement.thunder_chat', 'engagement.my_tasks', 'engagement.task_create', 'engagement.notifications'
  )
);

-- ==================================================
-- Verify seeding
-- ==================================================

COMMIT;

-- Show summary of permissions seeded
SELECT
  rt.name as role_name,
  COUNT(rtp.id) as permission_count,
  SUM(CASE WHEN rtp.can_view THEN 1 ELSE 0 END) as view_perms,
  SUM(CASE WHEN rtp.can_create THEN 1 ELSE 0 END) as create_perms,
  SUM(CASE WHEN rtp.can_edit THEN 1 ELSE 0 END) as edit_perms,
  SUM(CASE WHEN rtp.can_delete THEN 1 ELSE 0 END) as delete_perms
FROM role_templates rt
LEFT JOIN role_template_permissions rtp ON rt.id = rtp.role_template_id
WHERE rt.tenant_id = 1
AND rt.name IN ('Super User', 'Recruiter', 'HR Manager', 'Hiring Manager')
GROUP BY rt.name
ORDER BY rt.name;

SELECT 'Permissions seeded successfully!' as status;
