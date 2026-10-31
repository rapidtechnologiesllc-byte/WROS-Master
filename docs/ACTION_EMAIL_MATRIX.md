# Action email matrix

Every state-changing route in `backend/app/api/v1/endpoints/` (2026-10-31): who is involved, whether anyone is emailed, which path sends it. Internal emails are `backend/app/services/action_emails/` (staff mail path); candidate emails go through Thunder only.

| File | Action | Who is involved | Email before this PR | Path | After this PR |
|---|---|---|---|---|---|
| `activity_feed.py` | PATCH `/{activity_id}/read` | actor only (read marks) | no | - | not needed |
| `activity_feed.py` | PATCH `/read-all` | actor only (read marks) | no | - | not needed |
| `activity_timeline.py` | POST `/activity-timeline/{entity_type}/{entity_id}` | actor; record owner | no | - | no (timeline note / file; see CEO list) |
| `activity_timeline.py` | POST `/file-uploads/{entity_type}/{entity_id}` | actor; record owner | no | - | no (timeline note / file; see CEO list) |
| `agent_config.py` | POST `/` | admin only | no | - | not needed (config) |
| `agent_config.py` | PUT `/{agent_id}` | admin only | no | - | not needed (config) |
| `agent_config.py` | DELETE `/{agent_id}` | admin only | no | - | not needed (config) |
| `agent_standups_dashboard.py` | POST `/provide-feedback/{agent_name}` | CEO -> agent | no | - | not needed (agent feedback) |
| `ai_agent.py` | PATCH `/memory/{candidate_id}/facts/{fact_id}` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/webhook/email-reply` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/poll/{candidate_id}` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/conversations/{conversation_id}/send` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/conversations/{conversation_id}/take-over` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/conversations/{conversation_id}/hand-back` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/conversations/{conversation_id}/thunder-pause` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | POST `/conversations/{conversation_id}/thunder-resume` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_agent.py` | DELETE `/assign/{candidate_id}` | candidate; recruiter | candidate: yes | Thunder (candidate) | candidate path unchanged (Thunder) |
| `ai_recruiter_assignment.py` | PATCH `/admin/tenant/thunder-enabled` | admin only | no | - | not needed (tenant config) |
| `allocations.py` | POST `/` | employee; manager; BU head; project manager; client team | below-floor approver: task | task email (task_notification_service) | **NEW** action_emails.allocations.notify_allocated |
| `allocations.py` | POST `/{allocation_id}/end` | same | no | - | **NEW** action_emails.allocations.notify_allocation_ended |
| `allocations.py` | PUT `/{allocation_id}/renewal` | renewal owner (actor) | renewal alerts job | task email (task_notification_service) | unchanged |
| `allocations.py` | POST `/margin-preview` | actor only | no | - | not needed (preview) |
| `allocations.py` | POST `/changes/{change_id}/approve` | requester; allocation team | no | - | **NEW** action_emails.allocations.notify_margin_decision |
| `allocations.py` | POST `/changes/{change_id}/reject` | requester; allocation team | no | - | **NEW** action_emails.allocations.notify_margin_decision |
| `allocations.py` | PATCH `/{allocation_id}` | same | below-floor approver: task | task email (task_notification_service) | **NEW** action_emails.allocations.notify_allocation_changed (applied edits) |
| `allocations.py` | PUT `/{allocation_id}/client-billing` | account manager; finance | no | - | follow-up |
| `api_keys.py` | POST `/` | admin only | no | - | not needed (config) |
| `api_keys.py` | POST `/test` | admin only | no | - | not needed (config) |
| `ats.py` | POST `/rescore` | actor | no | - | not needed (rescore) |
| `auth.py` | POST `/v1/signup` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `auth.py` | POST `/validate-email` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `auth.py` | POST `/login` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `auth.py` | POST `/v1/refresh` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `auth.py` | POST `/reset-password` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `auth.py` | POST `/activate` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `auth.py` | POST `/forgot-password` | the user themself | yes (OTP / reset) | EmailService direct (Graph, no retry) | unchanged |
| `bgv.py` | POST `/{bgv_id}/start` | candidate; HR; recruiter | pipeline event | hiring_pipeline notify | follow-up: BGV family (not in this PR) |
| `bgv.py` | POST `/{bgv_id}/verdict` | candidate; HR; recruiter | pipeline event | hiring_pipeline notify | follow-up: BGV family (not in this PR) |
| `bgv.py` | POST `/{bgv_id}/waive` | candidate; HR; recruiter | pipeline event | hiring_pipeline notify | follow-up: BGV family (not in this PR) |
| `bgv.py` | POST `/webhook/{vendor}` | candidate; HR; recruiter | pipeline event | hiring_pipeline notify | follow-up: BGV family (not in this PR) |
| `buddy_program.py` | POST `/records` | employee; buddy; manager | partly | notification_service.send_notification | follow-up: buddy family |
| `buddy_program.py` | POST `/records/{record_id}/scores` | employee; buddy; manager | partly | notification_service.send_notification | follow-up: buddy family |
| `buddy_program.py` | POST `/records/{record_id}/graduate` | employee; buddy; manager | partly | notification_service.send_notification | follow-up: buddy family |
| `buddy_program.py` | POST `/records/{record_id}/extend` | employee; buddy; manager | partly | notification_service.send_notification | follow-up: buddy family |
| `buddy_program.py` | POST `/records/{record_id}/exit` | employee; buddy; manager | partly | notification_service.send_notification | follow-up: buddy family |
| `bulk_engagement.py` | POST `/candidates/bulk-import` | candidates | candidate: yes | Thunder (candidate) | unchanged (Thunder) |
| `bulk_engagement.py` | POST `/candidates/bulk-engage` | candidates | candidate: yes | Thunder (candidate) | unchanged (Thunder) |
| `bulk_engagement.py` | DELETE `/candidates/bulk-import/{job_id}/cancel` | candidates | candidate: yes | Thunder (candidate) | unchanged (Thunder) |
| `bu_context.py` | POST `/switch` | actor only | no | - | not needed (view switch) |
| `bu_context.py` | POST `/all-bus` | actor only | no | - | not needed (view switch) |
| `candidates.py` | POST `/change_password` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/candidate-form/` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/education-form/` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/experience-form/` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/aadhar-form/` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/pan-form/` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/education/add` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | PUT `/education/{education_id}` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | DELETE `/education/{education_id}` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | POST `/experience/add` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | PUT `/experience/{experience_id}` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidates.py` | DELETE `/experience/{experience_id}` | candidate (self-service forms) | no | - | candidate list (CEO decision) |
| `candidate_history.py` | POST `/{candidate_id}` | recruiter | no | - | not needed (history note) |
| `candidate_portal.py` | PATCH `/profile` | candidate (actor); recruiter; HR | partly | EmailService direct (Graph, no retry) | offer answer: NEW offers.notify_offer_answered |
| `candidate_portal.py` | POST `/interviews/{interview_id}/reschedule-request` | candidate (actor); recruiter; HR | partly | EmailService direct (Graph, no retry) | offer answer: NEW offers.notify_offer_answered |
| `candidate_portal.py` | POST `/offers/{offer_id}/respond` | candidate (actor); recruiter; HR | partly | EmailService direct (Graph, no retry) | offer answer: NEW offers.notify_offer_answered |
| `candidate_portal.py` | POST `/onboarding/documents/{doc_id}` | candidate (actor); recruiter; HR | partly | EmailService direct (Graph, no retry) | offer answer: NEW offers.notify_offer_answered |
| `candidate_status.py` | PUT `/{candidate_id}` | recruiter; HR; hiring manager; candidate | candidate: status email | Thunder (candidate) | staff: **NEW** action_emails.candidates.notify_pipeline_status |
| `cascade_prediction.py` | POST `/evaluate` | system | no | - | not needed |
| `certifications_admin.py` | POST `/create` | admin; employee | no | - | follow-up: certification target assigned |
| `certifications_admin.py` | POST `/assign-target` | admin; employee | no | - | follow-up: certification target assigned |
| `checklists.py` | POST `/hr/assign` | candidate; HR | no | - | follow-up: onboarding checklist family |
| `checklists.py` | PUT `/hr/candidate-item/{item_id}/complete` | candidate; HR | no | - | follow-up: onboarding checklist family |
| `checklists.py` | PATCH `/candidate/item/{item_id}/complete` | candidate; HR | no | - | follow-up: onboarding checklist family |
| `checklist_templates.py` | POST `/hr/templates` | admin only | no | - | not needed (config) |
| `checklist_templates.py` | PUT `/hr/templates/{template_id}` | admin only | no | - | not needed (config) |
| `checklist_templates.py` | DELETE `/hr/templates/{template_id}` | admin only | no | - | not needed (config) |
| `checklist_templates.py` | POST `/hr/templates/{template_id}/items` | admin only | no | - | not needed (config) |
| `checklist_templates.py` | PUT `/hr/templates/{template_id}/items/{item_id}` | admin only | no | - | not needed (config) |
| `checklist_templates.py` | DELETE `/hr/templates/{template_id}/items/{item_id}` | admin only | no | - | not needed (config) |
| `clients.py` | POST `/` | Client Owner; account manager; BU head | client-owner PR | staff mail (queue_staff_email) | client-owner PR #444 (not deployed: Troy case) |
| `clients.py` | POST `/{client_id}/contacts` | Client Owner; account manager; BU head | client-owner PR | staff mail (queue_staff_email) | client-owner PR #444 |
| `clients.py` | PATCH `/{client_id}` | new Client Owner; new account manager | client-owner PR: owner only | staff mail (queue_staff_email) | client-owner PR; account manager change still silent (follow-up) |
| `client_onboarding.py` | POST `/{onboarding_id}/confirm-start` | employee; account manager | yes | notify (staff) | unchanged |
| `client_timesheet_approval.py` | POST `/view` | client contact (actor); employee; approver | yes | staff mail (queue_staff_email) | unchanged |
| `client_timesheet_approval.py` | POST `/approve` | client contact (actor); employee; approver | yes | staff mail (queue_staff_email) | unchanged |
| `client_timesheet_approval.py` | POST `/reject` | client contact (actor); employee; approver | yes | staff mail (queue_staff_email) | unchanged |
| `core_certification.py` | POST `/requests/{request_id}/approve` | employee; delivery lead | yes | notification_service.send_notification | unchanged (held P1/P2 until notification_release lands) |
| `core_certification.py` | POST `/requests/{request_id}/close` | employee; delivery lead | yes | notification_service.send_notification | unchanged (held P1/P2 until notification_release lands) |
| `core_pull.py` | POST `/events/{event_id}/execute` | employee; BU head; account manager | yes | notification_service.send_notification | unchanged (held P1/P2 until notification_release lands) |
| `core_pull.py` | POST `/events/{event_id}/override` | employee; BU head; account manager | yes | notification_service.send_notification | unchanged (held P1/P2 until notification_release lands) |
| `core_pull.py` | POST `/replacement-plans` | employee; BU head; account manager | yes | notification_service.send_notification | unchanged (held P1/P2 until notification_release lands) |
| `cost_rate.py` | POST `/cost-rate-configs` | finance (actor) | no | - | not needed (finance ledger) |
| `cost_rate.py` | POST `/reserve-fund/entries` | finance (actor) | no | - | not needed (finance ledger) |
| `cost_rate.py` | POST `/intercompany-settlements` | finance (actor) | no | - | not needed (finance ledger) |
| `cost_rate.py` | POST `/intercompany-settlements/{settlement_id}/link-companies` | finance (actor) | no | - | not needed (finance ledger) |
| `cost_rate.py` | POST `/bank-transactions` | finance (actor) | no | - | not needed (finance ledger) |
| `cost_rate.py` | POST `/bank-transactions/{transaction_id}/match` | finance (actor) | no | - | not needed (finance ledger) |
| `create_job.py` | POST `/generate_job_description` | actor only | no | - | not needed (AI draft) |
| `create_job.py` | POST `/generate-with-agent` | actor only | no | - | not needed (AI draft) |
| `create_job.py` | POST `/generate-complete` | actor only | no | - | not needed (AI draft) |
| `create_job.py` | POST `/create_job` | hiring manager; recruiter; BU head | no | - | **NEW** action_emails.jobs.notify_job_created (in the job_created_flash handler) |
| `create_job.py` | POST `/{job_id}/approve` | creator; hiring manager; recruiter; BU head | no | - | **NEW** action_emails.jobs.notify_job_approved |
| `create_job.py` | PUT `/update_job/{job_id}` | new hiring manager; new recruiter | no | - | **NEW** action_emails.jobs.notify_job_assignees |
| `create_job.py` | DELETE `/delete_job/{job_id}` | hiring manager; recruiter; creator; BU head | no | - | **NEW** action_emails.jobs.notify_job_deleted |
| `create_job.py` | POST `/post-on-linkedin` | actor | no | - | not needed (external post) |
| `create_job.py` | POST `/{job_id}/apply` | candidate (actor); recruiter | no | - | follow-up: application to recruiter |
| `create_job.py` | POST `/{job_id}/applications/{candidate_id}` | recruiter; hiring manager | no | - | follow-up: application family |
| `create_job.py` | DELETE `/{job_id}/applications/{candidate_id}` | recruiter; hiring manager | no | - | follow-up: application family |
| `defect_reporting.py` | POST `/defects/report` | reporter; support | no | - | not needed (ticket log) |
| `demand_confirmation.py` | POST `/demands/{demand_id}/confirm-sow` | employee; account manager; BU head | yes | notification_service.send_notification | unchanged |
| `demand_confirmation.py` | POST `/demands/{demand_id}/employees/{employee_id}/schedule-call` | employee; account manager; BU head | yes | notification_service.send_notification | unchanged |
| `demand_confirmation.py` | POST `/calls/{call_id}/confirm-fit` | employee; account manager; BU head | yes | notification_service.send_notification | unchanged |
| `demand_confirmation.py` | POST `/calls/{call_id}/trigger-release` | employee; account manager; BU head | yes | notification_service.send_notification | unchanged |
| `desire_intelligence.py` | POST `/candidates/{candidate_id}/desire-intelligence/refresh` | system | no | - | not needed |
| `documents.py` | POST `/upload/resume` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/pan` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/aadhar` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/education` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/experience` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/salary-slip` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/bank-statement` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | POST `/upload/uan-pf` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `documents.py` | PATCH `/verify/{document_id}` | candidate; HR | task on verify | task email (task_notification_service) | unchanged |
| `email.py` | POST `/send` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email.py` | POST `/send-with-attachments` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email.py` | POST `/notify/event` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email.py` | POST `/interview/invite/{interview_id}` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email.py` | POST `/interview/cancel/{interview_id}` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email.py` | POST `/interview/invite/custom` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email.py` | POST `/login-credentials/{candidate_id}` | explicit recipient | yes (it is a send) | EmailService direct (Graph, no retry) | unchanged |
| `email_templates.py` | PUT `/{stage}` | admin only | no | - | not needed (config) |
| `employees.py` | POST `/` | manager; BU head; employee | employee: activation | account email | **NEW** action_emails.employees.notify_employee_created |
| `employees.py` | POST `/import/dry-run` | actor only | no | - | not needed (dry run) |
| `employees.py` | POST `/import/apply` | imported employees; managers | employees: activation | account email | follow-up: one digest per manager (bulk) |
| `employees.py` | PUT `/{employee_id}/organization` | employee; new BU head | no | - | follow-up |
| `employees.py` | PUT `/{employee_id}/photo/{kind}` | employee | no | - | not needed |
| `employees.py` | PUT `/{employee_id}/manager` | employee; new and old manager | no | - | **NEW** action_emails.employees.notify_manager_changed |
| `employees.py` | PATCH `/{employee_id}` | employee | no | - | follow-up: profile edit by someone else |
| `employees.py` | PUT `/{employee_id}/htd` | employee; manager | no | - | follow-up |
| `employees.py` | POST `/{employee_id}/employment` | employee; manager; BU head | no | - | **NEW** action_emails.employees.notify_employment_changed |
| `employees.py` | PUT `/{employee_id}/billable` | employee; manager | no | - | follow-up |
| `employees.py` | PUT `/{employee_id}/certifications` | employee; reporting manager | no | - | follow-up: certificate records (low value) |
| `employees.py` | POST `/{employee_id}/certificates` | employee; reporting manager | no | - | follow-up: certificate records (low value) |
| `employees.py` | PATCH `/{employee_id}/certificates/{record_id}` | employee; reporting manager | no | - | follow-up: certificate records (low value) |
| `employees.py` | DELETE `/{employee_id}/certificates/{record_id}` | employee; reporting manager | no | - | follow-up: certificate records (low value) |
| `employees.py` | POST `/utilization/recompute` | system | no | - | not needed |
| `employees.py` | POST `/{employee_id}/mark-bench` | employee; manager; BU head | no | - | **NEW** action_emails.employees.notify_marked_bench |
| `employees.py` | POST `/{employee_id}/remove-from-bench` | employee; manager | no | - | follow-up |
| `employees.py` | POST `/{employee_id}/escalations` | manager; BU head | no | - | **NEW** action_emails.employees.notify_escalation_raised |
| `employees.py` | POST `/escalations/{escalation_id}/resolve` | raiser; manager; BU head | no | - | **NEW** action_emails.employees.notify_escalation_resolved |
| `employee_conversion.py` | POST `/convert-candidate` | new employee; HR | yes (activation) | account email queue | unchanged |
| `employee_conversion.py` | POST `/{employee_id}/resend-activation` | new employee; HR | yes (activation) | account email queue | unchanged |
| `employee_milestones.py` | POST `/` | employee; manager | no | - | follow-up: milestone family |
| `executive_signal.py` | POST `/feedback-cycles` | employees; CEO | partly | EmailService direct (Graph, no retry) | unchanged |
| `executive_signal.py` | POST `/feedback-cycles/{cycle_id}/close` | employees; CEO | partly | EmailService direct (Graph, no retry) | unchanged |
| `executive_signal.py` | POST `/recognition/birthday-drafts` | employees; CEO | partly | EmailService direct (Graph, no retry) | unchanged |
| `executive_signal.py` | POST `/recognition/{draft_id}/approve` | employees; CEO | partly | EmailService direct (Graph, no retry) | unchanged |
| `executive_signal.py` | POST `/recognition/{draft_id}/reject` | employees; CEO | partly | EmailService direct (Graph, no retry) | unchanged |
| `executive_signal.py` | POST `/concerns` | employees; CEO | partly | EmailService direct (Graph, no retry) | unchanged |
| `expenses.py` | POST `/expenses` | manager | manager task | task email (task_notification_service) | unchanged |
| `expenses.py` | POST `/expenses/{expense_id}/manager-approve` | employee; manager; finance | partly (manager task) | EmailService direct (Graph, no retry) / task email (task_notification_service) | follow-up: expense decisions to the employee |
| `expenses.py` | POST `/expenses/{expense_id}/manager-reject` | employee; manager; finance | partly (manager task) | EmailService direct (Graph, no retry) / task email (task_notification_service) | follow-up: expense decisions to the employee |
| `expenses.py` | POST `/expenses/{expense_id}/approve` | employee | yes | EmailService direct (Graph, no retry) | follow-up: move to staff mail |
| `expenses.py` | POST `/expenses/{expense_id}/mark-paid` | employee | no | - | follow-up |
| `expenses.py` | POST `/expenses/{expense_id}/receipt` | employee; manager; finance | partly (manager task) | EmailService direct (Graph, no retry) / task email (task_notification_service) | follow-up: expense decisions to the employee |
| `flash.py` | POST `/` | actor only (assistant) | no | - | not needed |
| `flash.py` | POST `/conversation/reset` | actor only (assistant) | no | - | not needed |
| `flash.py` | POST `/conversation/read` | actor only (assistant) | no | - | not needed |
| `flash.py` | POST `/workflows/open` | actor only (assistant) | no | - | not needed |
| `goals_management.py` | PUT `/fy-settings` | admin / CEO | no | - | not needed (targets config) |
| `goals_management.py` | PUT `/targets` | admin / CEO | no | - | not needed (targets config) |
| `goals_management.py` | PUT `/fy-targets/{metric}` | admin / CEO | no | - | not needed (targets config) |
| `hiring_pipeline.py` | POST `/candidate/{candidate_id}/screen` | candidate; HR | candidate: yes | Thunder (candidate) | unchanged |
| `hiring_pipeline.py` | POST `/candidate/{candidate_id}/evaluate` | candidate; HR | candidate: yes | Thunder (candidate) | unchanged |
| `hiring_pipeline.py` | POST `/preboarding-documents/{doc_id}/review` | candidate; HR | candidate: yes | Thunder (candidate) | unchanged |
| `hr_assignments.py` | POST `/` | HR 1; HR 2 | no | - | **NEW** action_emails.candidates.notify_hr_assigned (new HR only) |
| `hr_assignments.py` | PATCH `/by-candidate/{candidate_id}` | HR 1; HR 2 | no | - | **NEW** action_emails.candidates.notify_hr_assigned (new HR only) |
| `hr_assignments.py` | DELETE `/by-candidate/{candidate_id}` | removed HR | no | - | follow-up |
| `htd_intake_pause.py` | POST `/calculate-monthly-metric` | system / admin | no | - | not needed |
| `htd_intake_pause.py` | POST `/check-breach` | system / admin | no | - | not needed |
| `htd_intake_pause.py` | POST `/resume` | system / admin | no | - | not needed |
| `internal.py` | POST `/notes/{candidate_id}` | recruiter | no | - | not needed (internal note) |
| `intervention_queue.py` | POST `/{queue_item_id}/take-over` | recruiter (actor) | no | - | not needed (takes over own queue item) |
| `intervention_queue.py` | POST `/{queue_item_id}/resolve` | recruiter (actor) | no | - | not needed (takes over own queue item) |
| `interviews.py` | POST `/panels/create` | recruiter | no | - | covered when interviewers are added / scheduled |
| `interviews.py` | DELETE `/panels/{panel_id}` | interviewers | no | - | follow-up |
| `interviews.py` | PUT `/panels/{panel_id}/level` | recruiter (actor) | no | - | not needed (round metadata) |
| `interviews.py` | POST `/panels/{panel_id}/verdict` | recruiters; interviewers | no | - | **NEW** action_emails.interviews.notify_round_verdict |
| `interviews.py` | POST `/rehire-reviews/{review_id}/decide` | requester | no | - | follow-up: rehire decision to requester |
| `interviews.py` | POST `/panel-members/assign` | interviewer | only if a round is scheduled (task) | task email (task_notification_service) | **NEW** action_emails.interviews.notify_panel_member_added |
| `interviews.py` | DELETE `/panel-members/{member_id}` | removed interviewer | no | - | follow-up |
| `interviews.py` | POST `/create` | hiring manager; recruiters; interviewers; candidate | interviewers: task; candidate: invite | task email (task_notification_service) / Thunder (candidate) | **NEW** action_emails.interviews.notify_interview_scheduled |
| `interviews.py` | PUT `/{interview_id}` | interviewers; hiring manager; recruiters; candidate | candidate re-invite | Thunder (candidate) | **NEW** action_emails.interviews.notify_interview_changed (new time / cancelled) |
| `interviews.py` | DELETE `/{interview_id}` | interviewers; hiring manager; recruiters | no | - | **NEW** action_emails.interviews.notify_interview_deleted |
| `interviews.py` | POST `/feedback/submit` | hiring manager; BU head; panel; HR | yes | EmailService direct (Graph, no retry) | unchanged (follow-up: move to staff mail) |
| `interviews.py` | PUT `/feedback/{feedback_id}` | interviewer (actor) | no | - | not needed (own feedback) |
| `interviews.py` | DELETE `/feedback/{feedback_id}` | interviewer | no | - | not needed |
| `invoices.py` | POST `/generate` | finance approver; project manager; client team | no | - | **NEW** action_emails.invoices.notify_invoice_drafted |
| `invoices.py` | POST `/{invoice_id}/approve` | project manager; client team | no | - | **NEW** action_emails.invoices.notify_invoice_approved |
| `invoices.py` | POST `/{invoice_id}/send` | client accounts contact | yes (the invoice) | invoice delivery | unchanged |
| `invoices.py` | POST `/{invoice_id}/record-external-delivery` | finance (actor) | no | - | not needed |
| `invoices.py` | POST `/{invoice_id}/mark-paid` | project manager; client team | no | - | **NEW** action_emails.invoices.notify_invoice_paid |
| `invoices.py` | POST `/{invoice_id}/record-payment` | project manager; client team | no | - | **NEW** action_emails.invoices.notify_invoice_paid (same key) |
| `learning_dashboard.py` | POST `/cycle` | system | no | - | not needed |
| `linkedin_candidate_pipeline.py` | POST `/linkedin-queue` | candidate; recruiter | candidate: yes | Thunder (candidate) | unchanged |
| `linkedin_candidate_pipeline.py` | PUT `/{pipeline_id}/status` | candidate; recruiter | candidate: yes | Thunder (candidate) | unchanged |
| `linkedin_candidate_pipeline.py` | POST `/{pipeline_id}/complete-import` | candidate; recruiter | candidate: yes | Thunder (candidate) | unchanged |
| `margin_policies.py` | POST `/` | admin only | no | - | not needed (config) |
| `margin_policies.py` | PUT `/{policy_id}` | admin only | no | - | not needed (config) |
| `margin_policies.py` | DELETE `/{policy_id}` | admin only | no | - | not needed (config) |
| `message_queue.py` | POST `/{message_id}/retry` | admin only | no | - | not needed (ops) |
| `message_queue.py` | POST `/{message_id}/stop-and-retry` | admin only | no | - | not needed (ops) |
| `message_queue.py` | POST `/{message_id}/fail` | admin only | no | - | not needed (ops) |
| `message_queue.py` | POST `/retry-failed` | admin only | no | - | not needed (ops) |
| `message_templates.py` | POST `/{template_key}` | admin only | no | - | not needed (config) |
| `message_templates.py` | POST `/{template_id}/activate` | admin only | no | - | not needed (config) |
| `mfa.py` | POST `/setup` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/setup/confirm` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/verify` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/email/resend` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/email/verify` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/candidate/opt-in` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/candidate/email/resend` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `mfa.py` | POST `/candidate/email/verify` | the user themself | yes (OTP) | EmailService direct (Graph, no retry) | unchanged |
| `msgraph.py` | POST `/unlink` | explicit recipient | yes (it is a send) | Graph | unchanged |
| `msgraph.py` | POST `/mail/send` | explicit recipient | yes (it is a send) | Graph | unchanged |
| `msgraph.py` | POST `/calendar/schedule` | explicit recipient | yes (it is a send) | Graph | unchanged |
| `msgraph.py` | POST `/service/calendar/schedule` | explicit recipient | yes (it is a send) | Graph | unchanged |
| `my_timesheet.py` | PUT `/timesheet/{timesheet_id}/entries` | employee (actor); approver | submit: yes | staff mail (queue_staff_email) | unchanged (own hours; submit mails the approver) |
| `my_timesheet.py` | POST `/timesheet/{timesheet_id}/submit` | employee (actor); approver | submit: yes | staff mail (queue_staff_email) | unchanged (own hours; submit mails the approver) |
| `newsletter.py` | POST `/subscribe` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `newsletter.py` | DELETE `/unsubscribe/{email}` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `newsletter.py` | POST `/create` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `newsletter.py` | PUT `/update/{newsletter_id}` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `newsletter.py` | POST `/schedule/{newsletter_id}` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `newsletter.py` | POST `/send/{newsletter_id}` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `newsletter.py` | DELETE `/delete/{newsletter_id}` | subscribers | yes (send) | EmailService direct (Graph, no retry) | unchanged |
| `notifications.py` | POST `/{notification_id}/mark-read` | actor only | no | - | not needed |
| `offer_letters.py` | POST `/respond` | everyone on the offer | creator only | EmailService direct (Graph, no retry) | **NEW** action_emails.offers.notify_offer_answered |
| `offer_letters.py` | POST `/create` | hiring manager; reporting manager; recruiters | no | - | **NEW** action_emails.offers.notify_offer_created |
| `offer_letters.py` | POST `/cancel/{offer_id}` | everyone on the offer; candidate | no | - | staff: **NEW** action_emails.offers.notify_offer_cancelled |
| `offer_letters.py` | PUT `/update/{offer_id}` | hiring manager | no | - | follow-up (edits before generation) |
| `offer_letters.py` | POST `/generate/{offer_id}` | hiring manager | yes | EmailService direct (Graph, no retry) | **NEW** action_emails.offers.notify_offer_awaiting_approval (staff mail) |
| `offer_letters.py` | POST `/approve/{offer_id}` | creator; recruiters; reporting manager | creator only | EmailService direct (Graph, no retry) | **NEW** action_emails.offers.notify_offer_decided (staff mail) |
| `offer_letters.py` | POST `/release/{offer_id}` | candidate; hiring manager; reporting manager; creator; recruiters | candidate only | Thunder (candidate) | staff: **NEW** action_emails.offers.notify_offer_released |
| `offer_letters.py` | POST `/sign/{offer_id}` | everyone on the offer | creator only | EmailService direct (Graph, no retry) | **NEW** action_emails.offers.notify_offer_answered |
| `offer_letters.py` | POST `/salary-structure` | actor only | no | - | not needed (calculator) |
| `offer_letters.py` | POST `/salary-structure/details` | actor only | no | - | not needed (calculator) |
| `opportunities.py` | POST `/` | Client Owner; account manager; BU head | client-owner PR (create) | staff mail (queue_staff_email) | client-owner PR |
| `opportunities.py` | POST `/{opportunity_id}/transition` | opportunity Client Owner; account manager | no | - | follow-up (client-owner PR family) |
| `opportunities.py` | POST `/{opportunity_id}/role-demand` | Client Owner; account manager; BU head | client-owner PR (create) | staff mail (queue_staff_email) | client-owner PR |
| `org_structure.py` | POST `/nodes` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | PATCH `/nodes/{org_node_id}` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | DELETE `/nodes/{org_node_id}` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | POST `/departments` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | PUT `/departments/{department_id}` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | DELETE `/departments/{department_id}` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | POST `/roles` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `org_structure.py` | PUT `/roles/{role_id}` | admin; seated people | no | - | follow-up: seat change to the person seated |
| `partner_incentives.py` | POST `/rules` | finance; partner | no | - | not needed (calculation) |
| `partner_incentives.py` | POST `/partners/{partner_user_id}/calculate-revenue-share` | finance; partner | no | - | not needed (calculation) |
| `performance.py` | PUT `/reviews/{review_id}` | employee; reviewer | no | - | follow-up: performance review family |
| `performance.py` | POST `/reviews/{review_id}/recording` | employee; reviewer | no | - | follow-up: performance review family |
| `performance.py` | PUT `/reviews/{review_id}/recording-link` | employee; reviewer | no | - | follow-up: performance review family |
| `performance.py` | POST `/employees/{employee_id}/feedback` | employee; reviewer | no | - | follow-up: performance review family |
| `performance.py` | POST `/employees/{employee_id}/notes` | employee; reviewer | no | - | follow-up: performance review family |
| `portal_messages.py` | POST `/{conversation_id}/messages` | candidate; recruiter | candidate: yes | portal | unchanged |
| `projects.py` | POST `/` | project manager; client team | no | - | **NEW** action_emails.projects.notify_project_created |
| `projects.py` | PATCH `/{project_id}` | new project manager | no | - | **NEW** action_emails.projects.notify_project_manager_changed |
| `projects.py` | POST `/{project_id}/status` | project team | no | - | **NEW** action_emails.projects.notify_project_status |
| `projects.py` | POST `/{project_id}/milestones` | project team; milestone owner | no | - | **NEW** action_emails.projects.notify_milestone_created |
| `projects.py` | POST `/{project_id}/milestones/{milestone_id}/complete` | project team; milestone owner | no | - | **NEW** action_emails.projects.notify_milestone_completed |
| `public_chat.py` | POST `/start` | anonymous visitor | no | - | not needed |
| `public_chat.py` | POST `/message` | anonymous visitor | no | - | not needed |
| `resource_management.py` | POST `/scan` | BU head; employee | partly | notification_service.send_notification | unchanged |
| `resource_management.py` | POST `/recommendations/{recommendation_id}/pursue` | BU head; employee | partly | notification_service.send_notification | unchanged |
| `resource_management.py` | POST `/recommendations/{recommendation_id}/approve` | BU head; employee | partly | notification_service.send_notification | unchanged |
| `resource_management.py` | POST `/recommendations/{recommendation_id}/reject` | BU head; employee | partly | notification_service.send_notification | unchanged |
| `revenue.py` | POST `/leakage/scan` | finance | no | - | not needed (scans / reasons) |
| `revenue.py` | POST `/leakage/{flag_id}/log-reason` | finance | no | - | not needed (scans / reasons) |
| `revenue.py` | POST `/reconciliation/scan` | finance | no | - | not needed (scans / reasons) |
| `revenue.py` | POST `/reconciliation/alerts/{alert_id}/resolve` | finance | no | - | not needed (scans / reasons) |
| `revenue_targets.py` | POST `/revenue-targets/bu` | CEO / finance | no | - | not needed (targets) |
| `risk_dashboard.py` | POST `/dashboard/candidates/{candidate_id}/add-to-queue` | recruiter | no | - | not needed |
| `role_templates.py` | POST `/` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | PUT `/{template_id}` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | POST `/{template_id}/grant-permission` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | POST `/{template_id}/revoke-permission` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | DELETE `/{template_id}` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | POST `/{template_id}/toggle-status` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | POST `/business-units` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | PUT `/business-units/{bu_id}` | admin only | no | - | not needed (RBAC config) |
| `role_templates.py` | DELETE `/business-units/{bu_id}` | admin only | no | - | not needed (RBAC config) |
| `submissions.py` | POST `/` | submitter; hiring manager; recruiters; client team | no | - | **NEW** action_emails.submissions.notify_submitted |
| `submissions.py` | POST `/` | submitter; hiring manager; recruiters; client team | no | - | **NEW** action_emails.submissions.notify_submitted |
| `submissions.py` | POST `/{submission_id}/client-response` | submitter; hiring manager; recruiters; client team | no | - | **NEW** action_emails.submissions.notify_client_response |
| `system_diagnostics.py` | POST `/health/cache-invalidate` | admin | no | - | not needed |
| `tasks.py` | POST `/{task_id}/updates` | assignee; creator; manager | yes | task email (task_notification_service) | unchanged (task PR #439) |
| `tasks.py` | POST `/` | assignee; creator; manager | yes | task email (task_notification_service) | unchanged (task PR #439) |
| `tasks.py` | POST `/{task_id}/stop-repeating` | assignee; creator; manager | yes | task email (task_notification_service) | unchanged (task PR #439) |
| `tasks.py` | POST `/{task_id}/confirm-urgent` | assignee; creator; manager | yes | task email (task_notification_service) | unchanged (task PR #439) |
| `tasks.py` | POST `/{task_id}/complete` | assignee; creator; manager | yes | task email (task_notification_service) | unchanged (task PR #439) |
| `tasks.py` | POST `/{task_id}/comments` | assignee; creator; manager | yes | task email (task_notification_service) | unchanged (task PR #439) |
| `tenants.py` | PATCH `/me/locale` | admin | no | - | not needed |
| `tenant_ai_config.py` | PATCH `/` | admin | no | - | not needed |
| `thunder.py` | POST `/test-chat` | admin | no | - | not needed |
| `thunder.py` | POST `/test-chat/reset` | admin | no | - | not needed |
| `thunder.py` | POST `/pause` | admin | no | - | not needed |
| `thunder.py` | POST `/resume` | admin | no | - | not needed |
| `tickets.py` | POST `/` | requester; assignee | no | - | follow-up: ticket family |
| `tickets.py` | POST `/admin/routing` | requester; assignee | no | - | follow-up: ticket family |
| `tickets.py` | PATCH `/admin/sla-policies/{priority}` | requester; assignee | no | - | follow-up: ticket family |
| `timesheets.py` | POST `/weekly-draft` | employee | no | - | not needed (system weekly draft; nag job mails missing ones) |
| `timesheets.py` | PUT `/{timesheet_id}/entries` | employee (actor) | no | - | not needed (own hours) |
| `timesheets.py` | POST `/{timesheet_id}/submit` | approver | yes | staff mail (queue_staff_email) | unchanged |
| `timesheets.py` | POST `/{timesheet_id}/approve` | employee; client approver | yes | staff mail (queue_staff_email) | unchanged |
| `timesheets.py` | POST `/{timesheet_id}/reject` | employee | yes | staff mail (queue_staff_email) | unchanged |
| `timesheets.py` | POST `/{timesheet_id}/reopen` | employee; manager; BU head | no | - | **NEW** action_emails.timesheets.notify_reopened |
| `timesheets.py` | POST `/{timesheet_id}/scan-anomalies` | system | no | - | not needed |
| `timesheets.py` | POST `/{timesheet_id}/disputes` | employee; manager; approver; client team | no | - | **NEW** action_emails.timesheets.notify_dispute_raised |
| `timesheets.py` | POST `/disputes/{dispute_id}/resolve` | raiser; employee; manager; client team | no | - | **NEW** action_emails.timesheets.notify_dispute_resolved |
| `timesheet_approvals.py` | POST `/{timesheet_id}/approve` | approver; employee; client approver | yes | staff mail (queue_staff_email) | unchanged |
| `timesheet_approvals.py` | POST `/{timesheet_id}/reject` | approver; employee; client approver | yes | staff mail (queue_staff_email) | unchanged |
| `timesheet_approvals.py` | POST `/{timesheet_id}/client-request` | approver; employee; client approver | yes | staff mail (queue_staff_email) | unchanged |
| `timesheet_approvals.py` | POST `/{timesheet_id}/client-evidence` | approver; employee; client approver | yes | staff mail (queue_staff_email) | unchanged |
| `users.py` | POST `/assignments/create` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | POST `/users/create` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | POST `/users/create-with-roles` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | PUT `/users/{user_id}` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | DELETE `/users/{user_id}` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | PUT `/users/me/change-password` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | PUT `/users/me/whatsapp` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users.py` | PUT `/admin/users/{user_id}/reset-password` | the user; admin | yes (account emails) | create_user_with_roles handler | unchanged |
| `users_access_control.py` | POST `/delivery-centers` | admin only | no | - | not needed (config) |
| `users_access_control.py` | PUT `/delivery-centers/{dc_id}` | admin only | no | - | not needed (config) |
| `users_access_control.py` | DELETE `/delivery-centers/{dc_id}` | admin only | no | - | not needed (config) |
| `webhooks.py` | POST `/sendgrid` | system | no | - | not needed (inbound) |
| `webhooks.py` | POST `/mailgun` | system | no | - | not needed (inbound) |
| `webhooks.py` | POST `/twilio-sms` | system | no | - | not needed (inbound) |
| `webhooks.py` | POST `/twilio-whatsapp` | system | no | - | not needed (inbound) |
| `whatsapp_webhook.py` | POST `/whatsapp` | system | no | - | not needed (inbound) |
| `work_orders.py` | POST `/` | account manager; finance; employee | partly (expiry task) | task email (task_notification_service) | follow-up: work order family |
| `work_orders.py` | PATCH `/{work_order_id}` | account manager; finance; employee | partly (expiry task) | task email (task_notification_service) | follow-up: work order family |
| `work_orders.py` | POST `/{work_order_id}/end` | account manager; finance; employee | partly (expiry task) | task email (task_notification_service) | follow-up: work order family |
| `work_orders.py` | POST `/{work_order_id}/pause` | account manager; finance; employee | partly (expiry task) | task email (task_notification_service) | follow-up: work order family |
| `work_orders.py` | POST `/{work_order_id}/resume` | account manager; finance; employee | partly (expiry task) | task email (task_notification_service) | follow-up: work order family |
| `candidates/create_queue_first.py` | POST `/create` | auto-assigned recruiter | no | - | **NEW** action_emails.candidates.notify_recruiter_assigned (recruiter_assignment_service) |
| `candidates/crud.py` | PUT `/{candidate_id}/education` | recruiter (usually the actor) | no | - | not needed (profile sections edited by staff) |
| `candidates/crud.py` | PUT `/{candidate_id}/experience` | recruiter (usually the actor) | no | - | not needed (profile sections edited by staff) |
| `candidates/crud.py` | PUT `/{candidate_id}/skills` | recruiter (usually the actor) | no | - | not needed (profile sections edited by staff) |
| `candidates/crud.py` | PUT `/{candidate_id}/certifications` | recruiter (usually the actor) | no | - | not needed (profile sections edited by staff) |
| `candidates/crud.py` | PUT `/hr/update_candidate/{candidate_id}` | new recruiter | no | - | **NEW** action_emails.candidates.notify_recruiter_assigned |
| `candidates/crud.py` | PATCH `/{candidate_id}/thunder-config` | recruiter (usually the actor) | no | - | not needed (profile sections edited by staff) |
| `candidates/crud.py` | DELETE `/{candidate_id}` | recruiter | no | - | follow-up |
