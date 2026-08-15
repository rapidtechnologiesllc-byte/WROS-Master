-- WROS Complete Database Schema
-- PostgreSQL 18
-- Generated from 168 SQLAlchemy models
-- 2026-08-14

-- Drop existing tables (for clean install)
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

-- ============================================
-- PHASE 1: SECURITY FOUNDATION
-- ============================================


CREATE TABLE IF NOT EXISTS activity_feed_read_state (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	conversation_event_id INTEGER NOT NULL, 
	read_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_activity_feed_read_state_event UNIQUE (conversation_event_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(conversation_event_id) REFERENCES conversation_events (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS activity_timeline (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id VARCHAR(50) NOT NULL, 
	actor_type VARCHAR(20) DEFAULT 'USER' NOT NULL, 
	actor_id VARCHAR(50), 
	action VARCHAR(100) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(actor_id) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS agent_execution_log (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50), 
	agent_name VARCHAR(100) NOT NULL, 
	action_taken VARCHAR(200) NOT NULL, 
	action_data JSON, 
	execution_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	duration_ms INTEGER, 
	success BOOLEAN DEFAULT '1' NOT NULL, 
	error_message TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS approval_chains (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	from_position_id INTEGER NOT NULL, 
	to_position_id INTEGER NOT NULL, 
	workflow VARCHAR(100) NOT NULL, 
	auto_escalate BOOLEAN NOT NULL, 
	escalate_after_days INTEGER, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(from_position_id) REFERENCES org_positions (id), 
	FOREIGN KEY(to_position_id) REFERENCES org_positions (id)
)




CREATE TABLE IF NOT EXISTS ats_scores (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	job_id VARCHAR(50), 
	overall_score INTEGER NOT NULL, 
	skills_score INTEGER NOT NULL, 
	experience_score INTEGER NOT NULL, 
	education_score INTEGER NOT NULL, 
	location_score INTEGER NOT NULL, 
	culture_fit_score INTEGER NOT NULL, 
	profile_summary TEXT, 
	strengths TEXT, 
	weaknesses TEXT, 
	recommendation VARCHAR(20), 
	score_rationale TEXT, 
	ats_verdict TEXT, 
	scored_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID") ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS audit_log (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id VARCHAR(100) NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	user_id VARCHAR(50), 
	old_value TEXT, 
	new_value TEXT, 
	timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	ip_address VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS bank_transactions (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	transaction_date DATE NOT NULL, 
	amount_usd_cents INTEGER NOT NULL, 
	description TEXT NOT NULL, 
	matched_invoice_id VARCHAR(36), 
	reconciled BOOLEAN NOT NULL, 
	created_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(matched_invoice_id) REFERENCES invoices (id), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS bu_access (
	id SERIAL NOT NULL, 
	user_id VARCHAR(50) NOT NULL, 
	business_unit_id INTEGER NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bu_access_user_bu UNIQUE (user_id, business_unit_id), 
	FOREIGN KEY(user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id)
)




CREATE TABLE IF NOT EXISTS bu_revenue_targets (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	business_unit_id INTEGER NOT NULL, 
	target_period VARCHAR(6) NOT NULL, 
	fiscal_year INTEGER NOT NULL, 
	target_amount_usd_cents INTEGER NOT NULL, 
	created_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	CONSTRAINT bu_target_period CHECK (target_period IN ('Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'ANNUAL')), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS buddy_kpi_scores (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	buddy_record_id VARCHAR(36) NOT NULL, 
	kpi_number INTEGER NOT NULL, 
	kpi_category VARCHAR(10) NOT NULL, 
	kpi_name VARCHAR(200) NOT NULL, 
	score INTEGER NOT NULL, 
	scored_by VARCHAR(50) NOT NULL, 
	scored_date DATE NOT NULL, 
	week_number INTEGER NOT NULL, 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(buddy_record_id) REFERENCES buddy_program_records (id), 
	FOREIGN KEY(scored_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS buddy_program_records (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	buddy_engineer_user_id VARCHAR(50) NOT NULL, 
	program_start_date DATE NOT NULL, 
	expected_end_date DATE NOT NULL, 
	actual_end_date DATE, 
	status VARCHAR(20) NOT NULL, 
	extension_count INTEGER NOT NULL, 
	extension_reason TEXT, 
	bu_head_decision_notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(buddy_engineer_user_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS bulk_engagement_errors (
	id SERIAL NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	reason TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES bulk_engagement_jobs (id) ON DELETE CASCADE, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS bulk_engagement_jobs (
	id VARCHAR(36) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	recruiter_id VARCHAR(50) NOT NULL, 
	candidate_ids JSON NOT NULL, 
	total_count INTEGER NOT NULL, 
	queued_count INTEGER NOT NULL, 
	success_count INTEGER NOT NULL, 
	failed_count INTEGER NOT NULL, 
	skipped_count INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(recruiter_id) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS business_units (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id INTEGER, 
	bu_code VARCHAR(50), 
	parent_bu_id INTEGER, 
	bu_head_employee_id VARCHAR(36), 
	hr_manager_employee_id VARCHAR(36), 
	continent VARCHAR(50), 
	region VARCHAR(60), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(parent_bu_id) REFERENCES business_units (id), 
	FOREIGN KEY(bu_head_employee_id) REFERENCES employees (id), 
	FOREIGN KEY(hr_manager_employee_id) REFERENCES employees (id)
)




CREATE TABLE IF NOT EXISTS campaign_touchpoints (
	id SERIAL NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	touchpoint_number INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	message_type VARCHAR(50) NOT NULL, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	message_event_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(campaign_id) REFERENCES outreach_campaigns (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(message_event_id) REFERENCES conversation_events (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_aadhar_forms (
	"formID" SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	aadhar VARCHAR(12), 
	name_in_aadhar VARCHAR(100), 
	enrollment_number VARCHAR(20), 
	aadhar_is_submitted BOOLEAN, 
	"submittedAt" DATE, 
	is_verified BOOLEAN, 
	document_id INTEGER, 
	"formCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"formUpdatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY ("formID"), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(document_id) REFERENCES candidate_documents (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_abandonment_scores (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	abandonment_score INTEGER NOT NULL, 
	score_components JSON, 
	is_flagged BOOLEAN DEFAULT '0' NOT NULL, 
	calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_abandonment_scores UNIQUE (tenant_id, candidate_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_ai_assignments (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	ai_agent_name VARCHAR(100) NOT NULL, 
	ai_agent_persona VARCHAR(100), 
	assigned_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	assigned_by VARCHAR(50), 
	is_active BOOLEAN DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(assigned_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS candidate_assignments (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	hiring_manager_id VARCHAR(50), 
	reporting_manager_id VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(hiring_manager_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(reporting_manager_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS candidate_availability_slots (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	slot_date DATE NOT NULL, 
	slot_start_time TIME WITHOUT TIME ZONE NOT NULL, 
	slot_end_time TIME WITHOUT TIME ZONE NOT NULL, 
	timezone VARCHAR(50) NOT NULL, 
	is_confirmed BOOLEAN DEFAULT '0' NOT NULL, 
	slot_source VARCHAR(20) DEFAULT 'CANDIDATE_MESSAGE' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_checklist_items (
	id SERIAL NOT NULL, 
	checklist_id INTEGER NOT NULL, 
	template_item_id INTEGER, 
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	item_type VARCHAR(10) NOT NULL, 
	order_index INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	due_date TIMESTAMP WITHOUT TIME ZONE, 
	activated_at TIMESTAMP WITHOUT TIME ZONE, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(checklist_id) REFERENCES candidate_checklists (id) ON DELETE CASCADE, 
	FOREIGN KEY(template_item_id) REFERENCES checklist_template_items (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_checklists (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	template_id INTEGER, 
	template_name VARCHAR(255), 
	assigned_by_user_id VARCHAR(50), 
	assigned_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	status VARCHAR(20) NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(template_id) REFERENCES checklist_templates (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_by_user_id) REFERENCES users ("UserID") ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_conversations (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	status VARCHAR(50) DEFAULT 'open' NOT NULL, 
	ai_agent_name VARCHAR(100), 
	channel_preference VARCHAR(50) DEFAULT 'email', 
	summary TEXT, 
	summary_generated_at TIMESTAMP WITHOUT TIME ZONE, 
	next_action VARCHAR(200), 
	owner_type VARCHAR(50) DEFAULT 'ai_agent', 
	owner_id VARCHAR(100), 
	escalation_state VARCHAR(50) DEFAULT 'none', 
	is_thunder_paused BOOLEAN DEFAULT '0' NOT NULL, 
	thunder_paused_at TIMESTAMP WITHOUT TIME ZONE, 
	thunder_resume_at TIMESTAMP WITHOUT TIME ZONE, 
	thunder_paused_by VARCHAR(50), 
	offer_faq_active BOOLEAN DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(thunder_paused_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS candidate_desire_profiles (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	top_desire_category VARCHAR(30), 
	top_desire_score FLOAT, 
	desire_ranking JSON, 
	primary_fear VARCHAR(30), 
	primary_fear_score FLOAT, 
	engagement_level VARCHAR(10), 
	has_competing_offer BOOLEAN NOT NULL, 
	decision_urgency VARCHAR(10), 
	narrative_summary TEXT, 
	narrative_updated_at TIMESTAMP WITHOUT TIME ZONE, 
	talking_points JSON, 
	profile_updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_desire_profile_per_candidate UNIQUE (candidate_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_desire_signals (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	signal_source VARCHAR(30) NOT NULL, 
	signal_data JSON NOT NULL, 
	desire_category VARCHAR(30), 
	desire_direction VARCHAR(20), 
	desire_strength FLOAT, 
	extracted_insight TEXT, 
	processed BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	processed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_documents (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	document_type VARCHAR(50) NOT NULL, 
	original_filename VARCHAR(255) NOT NULL, 
	stored_filename VARCHAR(255) NOT NULL, 
	file_size INTEGER NOT NULL, 
	file_extension VARCHAR(10) NOT NULL, 
	mime_type VARCHAR(100), 
	sharepoint_url TEXT, 
	sharepoint_file_id VARCHAR(255), 
	sharepoint_folder_path VARCHAR(500), 
	is_virus_scanned BOOLEAN, 
	virus_scan_result VARCHAR(50), 
	is_verified VARCHAR(20), 
	verified_by VARCHAR(50), 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	version INTEGER, 
	is_latest BOOLEAN, 
	replaced_by INTEGER, 
	uploaded_by VARCHAR(50) NOT NULL, 
	uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	is_deleted BOOLEAN, 
	notes TEXT, 
	tags VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(verified_by) REFERENCES users ("UserID"), 
	FOREIGN KEY(replaced_by) REFERENCES candidate_documents (id)
)




CREATE TABLE IF NOT EXISTS candidate_drop_risk (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	drop_risk_score INTEGER NOT NULL, 
	risk_level VARCHAR(8) NOT NULL, 
	risk_signals JSON, 
	is_flagged BOOLEAN NOT NULL, 
	calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_drop_risk UNIQUE (tenant_id, candidate_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	CONSTRAINT candidate_drop_risk_level CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
)




CREATE TABLE IF NOT EXISTS candidate_education_forms (
	"formID" SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	education_institute VARCHAR(255), 
	degree VARCHAR(255), 
	field_of_study VARCHAR(255), 
	starting_year VARCHAR(50), 
	year_of_passing VARCHAR(50), 
	percentage VARCHAR(10), 
	"submittedAt" DATE, 
	document_is_submitted BOOLEAN, 
	document_id INTEGER, 
	"formCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"formUpdatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY ("formID"), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(document_id) REFERENCES candidate_documents (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_engagement_metrics (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	response_rate NUMERIC(5, 2) NOT NULL, 
	avg_response_time_minutes INTEGER, 
	total_messages_exchanged INTEGER NOT NULL, 
	days_to_qualification INTEGER, 
	avg_sentiment_score NUMERIC(3, 2), 
	last_inbound_at TIMESTAMP WITHOUT TIME ZONE, 
	metrics_calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_engagement_metrics UNIQUE (tenant_id, candidate_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_experience_forms (
	"formID" SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	company_name VARCHAR(255), 
	job_title VARCHAR(255), 
	start_date DATE, 
	end_date DATE, 
	year_of_experience VARCHAR(50), 
	document_is_submitted BOOLEAN, 
	"submittedAt" DATE, 
	document_id INTEGER, 
	"formCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"formUpdatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY ("formID"), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(document_id) REFERENCES candidate_documents (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_field_skips (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	field_name VARCHAR(100) NOT NULL, 
	skipped_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_forms (
	"formID" SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	position VARCHAR(255), 
	department VARCHAR(100), 
	dob DATE, 
	gender VARCHAR(10), 
	marital_status VARCHAR(10), 
	nationality VARCHAR(10), 
	current_address TEXT, 
	permanent_address TEXT, 
	"submittedAt" DATE, 
	"formCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"formUpdatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY ("formID"), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID")
)




CREATE TABLE IF NOT EXISTS candidate_ghosting_status (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	ghosted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ghosting_reason VARCHAR(200) DEFAULT 'No response after 3 follow-up messages' NOT NULL, 
	reactivation_scheduled_at TIMESTAMP WITHOUT TIME ZONE, 
	is_reactivated BOOLEAN DEFAULT '0' NOT NULL, 
	reactivated_at TIMESTAMP WITHOUT TIME ZONE, 
	reactivation_attempt_count INTEGER DEFAULT '0' NOT NULL, 
	last_reactivation_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_ghosting_status UNIQUE (tenant_id, candidate_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_history (
	id SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	note TEXT, 
	performed_by_id VARCHAR(50), 
	performed_by_name VARCHAR(200), 
	job_id VARCHAR(50), 
	interview_id INTEGER, 
	offer_letter_id INTEGER, 
	event_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	"createdAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_job_applications (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	job_id VARCHAR(50) NOT NULL, 
	application_status VARCHAR(50), 
	applied_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_job_flags (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	job_id VARCHAR(50) NOT NULL, 
	flag_type VARCHAR(50) NOT NULL, 
	message TEXT NOT NULL, 
	severity VARCHAR(20) DEFAULT 'MEDIUM' NOT NULL, 
	is_resolved BOOLEAN DEFAULT '0' NOT NULL, 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_job_scores (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	job_id VARCHAR(50) NOT NULL, 
	technical_score INTEGER, 
	compensation_score INTEGER, 
	availability_score INTEGER, 
	overall_score INTEGER, 
	score_breakdown JSON, 
	calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_job_score UNIQUE (tenant_id, candidate_id, job_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_joining_scores (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	offer_id INTEGER NOT NULL, 
	readiness_score INTEGER NOT NULL, 
	score_breakdown JSON, 
	calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_joining_score UNIQUE (tenant_id, candidate_id, offer_id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(offer_id) REFERENCES offer_letters (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_memory (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	summary TEXT, 
	last_updated TIMESTAMP WITHOUT TIME ZONE, 
	version INTEGER DEFAULT '1' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_memory_facts (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	fact_category VARCHAR(50) NOT NULL, 
	fact_key VARCHAR(100) NOT NULL, 
	fact_value TEXT NOT NULL, 
	confidence FLOAT DEFAULT '1.0' NOT NULL, 
	source_message_id INTEGER, 
	extracted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	is_active BOOLEAN DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(source_message_id) REFERENCES conversation_events (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_no_response_log (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	last_outbound_message_id INTEGER, 
	detection_type VARCHAR(20) NOT NULL, 
	detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	follow_up_scheduled_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE, 
	FOREIGN KEY(last_outbound_message_id) REFERENCES conversation_events (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_opportunity_watches (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	candidate_id VARCHAR(50) NOT NULL, 
	reason VARCHAR(30) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	matched_job_id VARCHAR(50), 
	matched_at TIMESTAMP WITHOUT TIME ZONE, 
	nudged_at TIMESTAMP WITHOUT TIME ZONE, 
	started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(matched_job_id) REFERENCES jobs ("jobID")
)




CREATE TABLE IF NOT EXISTS candidate_ownership (
	id SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	pool_status VARCHAR(20) DEFAULT 'Org Pool' NOT NULL, 
	owned_by_bu_id INTEGER, 
	owned_by_bu_name VARCHAR(100), 
	ownership_reason VARCHAR(200), 
	bu_owned_since TIMESTAMP WITHOUT TIME ZONE, 
	bu_ownership_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(owned_by_bu_id) REFERENCES business_units (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_pan_forms (
	"formID" SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	pan VARCHAR(10), 
	name_in_pan VARCHAR(100), 
	father_name_in_pan VARCHAR(100), 
	pan_is_submitted BOOLEAN, 
	"submittedAt" DATE, 
	is_verified BOOLEAN, 
	document_id INTEGER, 
	"formCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"formUpdatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY ("formID"), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(document_id) REFERENCES candidate_documents (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_resume_parsed (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	raw_text TEXT, 
	full_name VARCHAR(200), 
	email VARCHAR(300), 
	phone VARCHAR(50), 
	current_title VARCHAR(200), 
	current_employer VARCHAR(200), 
	work_history JSON, 
	education JSON, 
	skills JSON, 
	certifications JSON, 
	languages JSON, 
	total_experience_months INTEGER, 
	total_experience_years FLOAT, 
	parsed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	parser_version VARCHAR(20) DEFAULT '1.0' NOT NULL, 
	resume_completeness_score INTEGER, 
	score_calculated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_sentiment_log (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER, 
	message_event_id INTEGER, 
	sentiment VARCHAR(20) DEFAULT 'NEUTRAL' NOT NULL, 
	confidence FLOAT DEFAULT '0.0' NOT NULL, 
	analyzed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE, 
	FOREIGN KEY(message_event_id) REFERENCES conversation_events (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS candidate_skill_tags (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	skill_canonical VARCHAR(100) NOT NULL, 
	skill_raw VARCHAR(200), 
	source VARCHAR(20) DEFAULT 'RESUME' NOT NULL, 
	confidence FLOAT DEFAULT '1.0' NOT NULL, 
	added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_candidate_skill_tag UNIQUE (tenant_id, candidate_id, skill_canonical), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_sla_breaches (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	sla_type VARCHAR(50) NOT NULL, 
	breached_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	is_resolved BOOLEAN DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS candidate_status (
	id SERIAL NOT NULL, 
	"candidateID" VARCHAR(50) NOT NULL, 
	"piplineStatus" VARCHAR(50), 
	status VARCHAR(50), 
	"createdAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"updatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY("candidateID") REFERENCES candidates ("candidateID")
)




CREATE TABLE IF NOT EXISTS candidates (
	"candidateID" VARCHAR(50) NOT NULL, 
	"candidateRole" VARCHAR(50), 
	"candidateEmployeeType" VARCHAR(50), 
	"candidateJobTitle" VARCHAR(50), 
	"candidateFirstName" VARCHAR(150), 
	"candidateMiddleName" VARCHAR(150), 
	"candidateLastName" VARCHAR(150), 
	"candidateEmail" VARCHAR(200) NOT NULL, 
	"candidateMobile" VARCHAR(20), 
	linkedin_url VARCHAR(500), 
	"candidateGender" VARCHAR(10), 
	"candidateDateOfBirth" DATE, 
	"candidateSource" VARCHAR(50), 
	"candidateExperience" VARCHAR(50), 
	"candidateSkills" TEXT, 
	"candidateJoiningDate" DATE, 
	"candidateExpectedSalary" VARCHAR(50), 
	"candidateCurrentSalary" VARCHAR(50), 
	"candidateCurrentLocation" VARCHAR(200), 
	"candidatePassword" VARCHAR(200) NOT NULL, 
	"candidateTempPassword" VARCHAR(200), 
	"candidateIsVerified" BOOLEAN, 
	"candidateCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	total_experience_months INTEGER, 
	resume_completeness_score INTEGER, 
	employment_type VARCHAR(11) DEFAULT 'UNKNOWN' NOT NULL, 
	timezone VARCHAR(64) DEFAULT 'Asia/Kolkata' NOT NULL, 
	source_channel VARCHAR(9) DEFAULT 'DIRECT' NOT NULL, 
	vendor_id VARCHAR(36), 
	tenant_id INTEGER DEFAULT '1' NOT NULL, 
	job_id VARCHAR(50), 
	business_unit_id INTEGER, 
	email_2fa_opted_in BOOLEAN, 
	email_otp_code_hash VARCHAR(64), 
	email_otp_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	do_not_contact BOOLEAN DEFAULT '0' NOT NULL, 
	thunder_assigned_at TIMESTAMP WITHOUT TIME ZONE, 
	thunder_channel_user_id VARCHAR(100), 
	overall_desire_score INTEGER, 
	consent_given BOOLEAN, 
	employment_type_confirmed BOOLEAN DEFAULT '0', 
	PRIMARY KEY ("candidateID"), 
	CONSTRAINT chk_candidate_experience_5yr_floor CHECK ((total_experience_months IS NULL OR total_experience_months >= 60)), 
	CONSTRAINT candidate_employment_type CHECK (employment_type IN ('W2_FULLTIME', 'C2C', '1099', 'UNKNOWN')), 
	CONSTRAINT candidate_source_channel CHECK (source_channel IN ('DIRECT', 'SUBVENDOR')), 
	FOREIGN KEY(vendor_id) REFERENCES sub_vendor_accounts (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID"), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id)
)




CREATE TABLE IF NOT EXISTS checklist_template_items (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	item_type VARCHAR(10) NOT NULL, 
	order_index INTEGER NOT NULL, 
	due_days_offset INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(template_id) REFERENCES checklist_templates (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS checklist_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	created_by_user_id VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users ("UserID") ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS clarification_qa (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	request_id VARCHAR(36) NOT NULL, 
	sub_vendor_id VARCHAR(36) NOT NULL, 
	question VARCHAR(2000) NOT NULL, 
	asked_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	answer VARCHAR(2000), 
	answered_by VARCHAR(50), 
	answered_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(request_id) REFERENCES sub_vendor_requests (id), 
	FOREIGN KEY(sub_vendor_id) REFERENCES sub_vendor_accounts (id), 
	FOREIGN KEY(answered_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS client_contacts (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	client_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	title VARCHAR(200), 
	email VARCHAR(300) NOT NULL, 
	phone VARCHAR(50), 
	role_type VARCHAR(18) NOT NULL, 
	is_primary BOOLEAN NOT NULL, 
	linkedin_url TEXT, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_client_contact_email_per_client UNIQUE (client_id, email), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	CONSTRAINT contact_role_type CHECK (role_type IN ('HIRING_MANAGER', 'TECHNICAL_PANEL', 'PROCUREMENT', 'ACCOUNTS', 'PRIMARY', 'TIMESHEET_APPROVER'))
)




CREATE TABLE IF NOT EXISTS client_history (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	client_id VARCHAR(36) NOT NULL, 
	change_type VARCHAR(15) NOT NULL, 
	old_value TEXT, 
	new_value TEXT, 
	changed_by VARCHAR(50), 
	changed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	CONSTRAINT client_change_type CHECK (change_type IN ('STATUS', 'ACCOUNT_MANAGER', 'TIER', 'CONTRACT_TERMS'))
)




CREATE TABLE IF NOT EXISTS clients (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	business_unit_id INTEGER, 
	company_name VARCHAR(300) NOT NULL, 
	company_short_name VARCHAR(50), 
	industry VARCHAR(100), 
	country VARCHAR(100), 
	client_type VARCHAR(6) NOT NULL, 
	line_type VARCHAR(10), 
	website VARCHAR(300), 
	tier VARCHAR(8) NOT NULL, 
	status VARCHAR(13) NOT NULL, 
	account_manager_id VARCHAR(36), 
	client_owner_id VARCHAR(36), 
	account_manager_employee_id VARCHAR(36), 
	billing_address TEXT, 
	billing_currency VARCHAR(3) NOT NULL, 
	payment_terms_days INTEGER NOT NULL, 
	credit_limit_usd_cents INTEGER, 
	tax_id_client VARCHAR(100), 
	contract_start_date DATE, 
	contract_end_date DATE, 
	contract_url TEXT, 
	markup_rate_pct NUMERIC(5, 2), 
	nda_signed BOOLEAN NOT NULL, 
	nda_url TEXT, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	created_by VARCHAR(50), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_client_company_name_per_tenant UNIQUE (tenant_id, company_name), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	CONSTRAINT client_type CHECK (client_type IN ('DIRECT', 'MSP', 'VMS')), 
	CONSTRAINT client_line_type CHECK (line_type IN ('CORE', 'SPECIALITY')), 
	CONSTRAINT client_tier CHECK (tier IN ('PLATINUM', 'GOLD', 'SILVER', 'STANDARD')), 
	CONSTRAINT client_status CHECK (status IN ('QUALIFICATION', 'PROSPECT', 'PROPOSAL', 'NEGOTIATION', 'CONTRACT', 'ACTIVE', 'LOST')), 
	FOREIGN KEY(account_manager_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(client_owner_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(account_manager_employee_id) REFERENCES employees (id), 
	CONSTRAINT billing_currency CHECK (billing_currency IN ('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD'))
)




CREATE TABLE IF NOT EXISTS conflict_rules (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	rule_name VARCHAR(80) NOT NULL, 
	entity_type_a VARCHAR(50) NOT NULL, 
	action_type_a VARCHAR(50) NOT NULL, 
	entity_type_b VARCHAR(50) NOT NULL, 
	action_type_b VARCHAR(50) NOT NULL, 
	collision_window_minutes INTEGER NOT NULL, 
	resolution_action VARCHAR(20) NOT NULL, 
	delay_minutes INTEGER, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS consent_records (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	subject_type VARCHAR(50) NOT NULL, 
	subject_id VARCHAR(50) NOT NULL, 
	consent_type VARCHAR(100) NOT NULL, 
	consent_given BOOLEAN NOT NULL, 
	captured_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	captured_by VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS conversation_events (
	id SERIAL NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	event_data JSON, 
	triggered_by VARCHAR(50) DEFAULT 'ai_agent' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS cost_rate_configs (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	business_unit_id INTEGER, 
	statutory_pct NUMERIC(5, 2) NOT NULL, 
	overhead_pct NUMERIC(5, 2) NOT NULL, 
	effective_date DATE DEFAULT CURRENT_DATE NOT NULL, 
	created_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS data_scope_permissions (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	module VARCHAR(100) NOT NULL, 
	scope_type VARCHAR(50) NOT NULL, 
	filter_rule TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_data_scope_per_role_module UNIQUE (role_id, module), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
)




CREATE TABLE IF NOT EXISTS demand_gap_scores (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	demand_id VARCHAR(36) NOT NULL, 
	bench_match_count INTEGER NOT NULL, 
	bench_first_check_passed BOOLEAN NOT NULL, 
	gap_severity VARCHAR(20) NOT NULL, 
	rationale TEXT, 
	llm_parse_failed BOOLEAN NOT NULL, 
	days_open INTEGER NOT NULL, 
	scored_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id)
)




CREATE TABLE IF NOT EXISTS demand_history (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	demand_id VARCHAR(36) NOT NULL, 
	change_type VARCHAR(9) NOT NULL, 
	old_value TEXT, 
	new_value TEXT, 
	reason TEXT, 
	changed_by VARCHAR(50), 
	changed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	CONSTRAINT demand_change_type CHECK (change_type IN ('STATUS', 'RECRUITER', 'URGENCY', 'HEADCOUNT'))
)




CREATE TABLE IF NOT EXISTS demand_interview_panels (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	demand_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	interview_level VARCHAR(2) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	assigned_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	assigned_by VARCHAR(50), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_panel_member_per_demand_level UNIQUE (tenant_id, demand_id, interview_level, employee_id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	CONSTRAINT panel_interview_level CHECK (interview_level IN ('L1', 'L2')), 
	FOREIGN KEY(assigned_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS demands (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	client_id VARCHAR(36) NOT NULL, 
	job_title VARCHAR(300) NOT NULL, 
	job_description TEXT, 
	required_skills TEXT NOT NULL, 
	nice_to_have_skills TEXT, 
	min_experience_years NUMERIC(4, 1) NOT NULL, 
	max_experience_years NUMERIC(4, 1), 
	work_location VARCHAR(6) NOT NULL, 
	job_location VARCHAR(200), 
	domain VARCHAR(100), 
	employment_type VARCHAR(11) NOT NULL, 
	interview_type_required VARCHAR(9) NOT NULL, 
	headcount INTEGER NOT NULL, 
	positions_filled INTEGER NOT NULL, 
	billing_rate_usd_cents INTEGER, 
	budget_min_usd_cents INTEGER, 
	budget_max_usd_cents INTEGER, 
	required_start_date DATE, 
	urgency VARCHAR(9) NOT NULL, 
	status VARCHAR(11) NOT NULL, 
	sourcing_enabled BOOLEAN NOT NULL, 
	bench_first_checked BOOLEAN NOT NULL, 
	assigned_recruiter_employee_id VARCHAR(36), 
	assigned_bu_id INTEGER, 
	client_owner_id VARCHAR(36), 
	delivery_engine VARCHAR(10) NOT NULL, 
	confirmation_status VARCHAR(9) NOT NULL, 
	sow_reference VARCHAR(200), 
	sow_received_date DATE, 
	opportunity_id VARCHAR(36), 
	project_id VARCHAR(36), 
	source_type VARCHAR(11) NOT NULL, 
	duration_hours INTEGER, 
	revenue_potential_usd_cents INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	created_by VARCHAR(50), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	closed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	CONSTRAINT demand_work_location CHECK (work_location IN ('REMOTE', 'ONSITE', 'HYBRID')), 
	CONSTRAINT demand_employment_type CHECK (employment_type IN ('W2_FULLTIME')), 
	CONSTRAINT demand_interview_type CHECK (interview_type_required IN ('L1_ONLY', 'L1_AND_L2')), 
	CONSTRAINT demand_urgency CHECK (urgency IN ('IMMEDIATE', 'HIGH', 'NORMAL', 'FLEXIBLE')), 
	CONSTRAINT demand_status CHECK (status IN ('DRAFT', 'OPEN', 'IN_PROGRESS', 'FILLED', 'CANCELLED', 'ON_HOLD')), 
	FOREIGN KEY(assigned_recruiter_employee_id) REFERENCES employees (id), 
	FOREIGN KEY(assigned_bu_id) REFERENCES business_units (id), 
	FOREIGN KEY(client_owner_id) REFERENCES users ("UserID"), 
	CONSTRAINT demand_delivery_engine CHECK (delivery_engine IN ('SPECIALITY', 'CORE')), 
	CONSTRAINT demand_confirmation_status CHECK (confirmation_status IN ('POTENTIAL', 'CONFIRMED', 'CANCELLED')), 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	CONSTRAINT demand_source_type CHECK (source_type IN ('DIRECT', 'OPPORTUNITY'))
)




CREATE TABLE IF NOT EXISTS departments (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	business_unit_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	hiring_manager_id VARCHAR(36), 
	cost_center_code VARCHAR(50), 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(hiring_manager_id) REFERENCES org_nodes (id)
)




CREATE TABLE IF NOT EXISTS detailed_permissions (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	category VARCHAR(50), 
	layer VARCHAR(50), 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_permission_name_per_tenant UNIQUE (tenant_id, name), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS detailed_role_permissions (
	id SERIAL NOT NULL, 
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(permission_id) REFERENCES detailed_permissions (id)
)




CREATE TABLE IF NOT EXISTS employee_allocations (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	demand_id VARCHAR(36) NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	role VARCHAR(200), 
	status VARCHAR(11) NOT NULL, 
	utilization_pct NUMERIC(5, 2), 
	start_date DATE NOT NULL, 
	end_date DATE, 
	client_reporting_manager_contact_id VARCHAR(36), 
	timesheet_approver_email VARCHAR(300), 
	billing_rate_usd_cents INTEGER, 
	si_partner VARCHAR(12), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	CONSTRAINT employee_allocation_status CHECK (status IN ('ACTIVE', 'ENDED', 'CORE_PULLED')), 
	FOREIGN KEY(client_reporting_manager_contact_id) REFERENCES client_contacts (id), 
	CONSTRAINT employee_allocation_si_partner CHECK (si_partner IN ('PWC', 'EY', 'CASTLEBAY', 'ZENSAR', 'LTI_MINDTREE', 'OTHER'))
)




CREATE TABLE IF NOT EXISTS employee_concern_intakes (
	id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	message_text TEXT NOT NULL, 
	category VARCHAR(15), 
	resolution_text TEXT, 
	created_task_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(created_task_id) REFERENCES tasks (id)
)




CREATE TABLE IF NOT EXISTS employee_documents (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	document_type VARCHAR(13) NOT NULL, 
	document_url TEXT NOT NULL, 
	uploaded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	verified_by VARCHAR(50), 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	CONSTRAINT employee_document_type CHECK (document_type IN ('OFFER_LETTER', 'CONTRACT', 'ID_PROOF', 'ADDRESS_PROOF', 'PAN', 'TAX_FORM', 'VISA', 'NDA', 'OTHER'))
)




CREATE TABLE IF NOT EXISTS employee_employment_history (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	change_type VARCHAR(12) NOT NULL, 
	old_value TEXT, 
	new_value TEXT, 
	effective_date DATE NOT NULL, 
	reason TEXT, 
	changed_by VARCHAR(50), 
	changed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	CONSTRAINT employment_change_type CHECK (change_type IN ('TITLE', 'SALARY', 'BILLING_RATE', 'STATUS', 'BU', 'MANAGER', 'LOCATION'))
)




CREATE TABLE IF NOT EXISTS employee_engine_history (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	from_engine VARCHAR(10), 
	to_engine VARCHAR(10) NOT NULL, 
	changed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	changed_by VARCHAR(50), 
	approval_reference VARCHAR(200), 
	reason TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	CONSTRAINT engine_history_from CHECK (from_engine IN ('SPECIALITY', 'CORE')), 
	CONSTRAINT engine_history_to CHECK (to_engine IN ('SPECIALITY', 'CORE'))
)




CREATE TABLE IF NOT EXISTS employee_feedback_cycles (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	quarter_label VARCHAR(20) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	closed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS employee_feedback_responses (
	id SERIAL NOT NULL, 
	cycle_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	response_text TEXT NOT NULL, 
	is_flagged BOOLEAN NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(cycle_id) REFERENCES employee_feedback_cycles (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
)




CREATE TABLE IF NOT EXISTS employee_milestones (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	project_id VARCHAR(36), 
	employee_id VARCHAR(36), 
	milestone_type VARCHAR(8) NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	description TEXT, 
	target_date DATE NOT NULL, 
	completed_date DATE, 
	status VARCHAR(11) NOT NULL, 
	completion_notes TEXT, 
	set_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	CONSTRAINT employee_milestone_type CHECK (milestone_type IN ('PERSONAL', 'PROJECT', 'ORG')), 
	CONSTRAINT employee_milestone_status CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE', 'CANCELLED', 'EXTENDED'))
)




CREATE TABLE IF NOT EXISTS employee_performance_events (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	business_unit_id INTEGER, 
	event_type VARCHAR(50) NOT NULL, 
	event_data TEXT, 
	occurred_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id)
)




CREATE TABLE IF NOT EXISTS employees (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	candidate_id VARCHAR(50), 
	employee_number VARCHAR(50), 
	tenant_employee_id VARCHAR(100), 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	legal_name VARCHAR(300), 
	email VARCHAR(300) NOT NULL, 
	personal_email VARCHAR(300), 
	phone VARCHAR(50), 
	date_of_birth DATE, 
	gender VARCHAR(50), 
	nationality VARCHAR(100), 
	current_address TEXT, 
	permanent_address TEXT, 
	emergency_contact_name VARCHAR(200), 
	emergency_contact_phone VARCHAR(50), 
	joining_date DATE NOT NULL, 
	confirmation_date DATE, 
	exit_date DATE, 
	employment_type VARCHAR(10) NOT NULL, 
	status VARCHAR(19) NOT NULL, 
	bu_id INTEGER, 
	manager_id VARCHAR(36), 
	org_node_id VARCHAR(36), 
	current_title VARCHAR(200), 
	current_skills TEXT, 
	total_experience_months INTEGER, 
	blitzenx_experience_months INTEGER NOT NULL, 
	base_salary_usd_cents INTEGER, 
	billing_rate_usd_cents INTEGER, 
	billing_classification VARCHAR(12) NOT NULL, 
	work_location VARCHAR(6) NOT NULL, 
	visa_status VARCHAR(100), 
	pan_number VARCHAR(50), 
	tax_id VARCHAR(100), 
	bank_account_number_encrypted TEXT, 
	bank_routing_encrypted TEXT, 
	wros_user_id VARCHAR(50), 
	delivery_engine VARCHAR(10) NOT NULL, 
	engine_entry_date DATE NOT NULL, 
	core_eligible_from DATE, 
	core_certified BOOLEAN NOT NULL, 
	core_certified_date DATE, 
	buddy_program_status VARCHAR(11) NOT NULL, 
	buddy_program_start_date DATE, 
	buddy_program_graduation_date DATE, 
	htd_track BOOLEAN NOT NULL, 
	htd_start_date DATE, 
	htd_phase VARCHAR(23), 
	reporting_manager_user_id VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	created_by VARCHAR(50), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_employee_number_per_tenant UNIQUE (tenant_id, employee_number), 
	CONSTRAINT ck_core_requires_certification CHECK (delivery_engine != 'CORE' OR core_certified = true), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	UNIQUE (candidate_id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	CONSTRAINT employment_type CHECK (employment_type IN ('PERMANENT', 'CONTRACT', 'FIXED_TERM', 'INTERN')), 
	CONSTRAINT employee_status CHECK (status IN ('PRE_JOINING', 'ACTIVE', 'ON_LEAVE', 'BENCH', 'ALLOCATED', 'NOTICE_PERIOD', 'EXITED', 'SPECIALITY_READY', 'PERFORMANCE_MANAGED')), 
	FOREIGN KEY(bu_id) REFERENCES business_units (id), 
	FOREIGN KEY(manager_id) REFERENCES employees (id), 
	FOREIGN KEY(org_node_id) REFERENCES org_nodes (id), 
	CONSTRAINT billing_classification CHECK (billing_classification IN ('BENCH', 'ALLOCATED', 'NON_BILLABLE')), 
	CONSTRAINT work_location CHECK (work_location IN ('REMOTE', 'ONSITE', 'HYBRID')), 
	FOREIGN KEY(wros_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT delivery_engine CHECK (delivery_engine IN ('SPECIALITY', 'CORE')), 
	CONSTRAINT buddy_program_status CHECK (buddy_program_status IN ('NOT_STARTED', 'IN_PROGRESS', 'GRADUATED', 'EXTENDED', 'EXITED')), 
	CONSTRAINT htd_phase CHECK (htd_phase IN ('INDUCTION', 'SHADOW_DELIVERY', 'CONTROLLED_OWNERSHIP', 'CORE_ELIGIBILITY_REVIEW', 'COMPLETED', 'EXITED')), 
	FOREIGN KEY(reporting_manager_user_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS error_log (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	error_type VARCHAR(200) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	message TEXT NOT NULL, 
	stack_trace TEXT, 
	request_context TEXT, 
	integration_name VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS event_log (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50), 
	event_type VARCHAR(100) NOT NULL, 
	event_version VARCHAR(10) DEFAULT 'v1' NOT NULL, 
	payload JSON, 
	emitted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS expense_records (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	business_unit_id INTEGER, 
	logged_by_user_id VARCHAR(50) NOT NULL, 
	purpose VARCHAR(15) NOT NULL, 
	client_id VARCHAR(36), 
	conference_name VARCHAR(200), 
	investment_label VARCHAR(200), 
	expense_category VARCHAR(13) NOT NULL, 
	travel_type VARCHAR(16), 
	trip_label VARCHAR(200), 
	amount_usd_cents INTEGER NOT NULL, 
	location VARCHAR(200), 
	description TEXT, 
	receipt_ref VARCHAR(300) NOT NULL, 
	expense_date DATE NOT NULL, 
	manager_approval_status VARCHAR(8) NOT NULL, 
	manager_approved_by VARCHAR(50), 
	manager_approved_at TIMESTAMP WITHOUT TIME ZONE, 
	payment_status VARCHAR(10) NOT NULL, 
	approved_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(logged_by_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT expense_purpose CHECK (purpose IN ('CLIENT_CURRENT', 'CLIENT_PROSPECT', 'CONFERENCE', 'INVESTMENT', 'OTHER')), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	CONSTRAINT expense_category CHECK (expense_category IN ('TRAVEL', 'MEALS', 'LODGING', 'ENTERTAINMENT', 'OTHER')), 
	CONSTRAINT expense_travel_type CHECK (travel_type IN ('AIRFARE', 'GROUND_TRANSPORT', 'HOTEL', 'MEALS', 'OTHER')), 
	CONSTRAINT expense_manager_approval_status CHECK (manager_approval_status IN ('PENDING', 'APPROVED', 'REJECTED')), 
	FOREIGN KEY(manager_approved_by) REFERENCES users ("UserID"), 
	CONSTRAINT expense_payment_status CHECK (payment_status IN ('PENDING', 'APPROVED', 'REIMBURSED')), 
	FOREIGN KEY(approved_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS field_permissions (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	table_name VARCHAR(100) NOT NULL, 
	field_name VARCHAR(100) NOT NULL, 
	access_level VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_field_permission UNIQUE (role_id, table_name, field_name), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
)




CREATE TABLE IF NOT EXISTS file_uploads (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id VARCHAR(50) NOT NULL, 
	file_category VARCHAR(50) DEFAULT 'GENERIC' NOT NULL, 
	original_filename VARCHAR(255) NOT NULL, 
	unique_filename VARCHAR(255) NOT NULL, 
	file_size INTEGER NOT NULL, 
	file_extension VARCHAR(20), 
	sharepoint_url VARCHAR(1000), 
	scan_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, 
	uploaded_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS follow_up_schedule (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, 
	follow_up_number INTEGER NOT NULL, 
	triggered_by_message_id INTEGER, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE, 
	FOREIGN KEY(triggered_by_message_id) REFERENCES conversation_events (id) ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS hiring_manager_validations (
	id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	job_id VARCHAR(36) NOT NULL, 
	hiring_manager_id VARCHAR(36) NOT NULL, 
	status VARCHAR(9) DEFAULT 'PENDING' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	responded_at TIMESTAMP WITHOUT TIME ZONE, 
	email_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	email_reminder_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	notification_viewed_at TIMESTAMP WITHOUT TIME ZONE, 
	response_time_hours INTEGER, 
	responses JSON, 
	decision_comment TEXT, 
	decision_score INTEGER, 
	interview_scheduled_at TIMESTAMP WITHOUT TIME ZONE, 
	interview_id VARCHAR(50), 
	next_candidate_tried BOOLEAN DEFAULT '0' NOT NULL, 
	escalated_to_user_id VARCHAR(36), 
	escalated_at TIMESTAMP WITHOUT TIME ZONE, 
	escalation_reason VARCHAR(200), 
	created_by VARCHAR(36), 
	last_updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(job_id) REFERENCES demands (id), 
	FOREIGN KEY(hiring_manager_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(interview_id) REFERENCES interviews ("interviewID"), 
	FOREIGN KEY(escalated_to_user_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS hm_validation_responses (
	id VARCHAR(36) NOT NULL, 
	validation_id VARCHAR(36) NOT NULL, 
	question_id VARCHAR(100) NOT NULL, 
	question_text TEXT NOT NULL, 
	question_type VARCHAR(50) NOT NULL, 
	response_value TEXT, 
	response_json JSON, 
	response_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	time_to_respond_seconds INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(validation_id) REFERENCES hiring_manager_validations (id)
)




CREATE TABLE IF NOT EXISTS hr_assignments (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	hr1_id VARCHAR(50), 
	hr2_id VARCHAR(50), 
	assigned_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(hr1_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(hr2_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(assigned_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS htd_intake_status (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	is_paused BOOLEAN NOT NULL, 
	paused_at TIMESTAMP WITHOUT TIME ZONE, 
	pause_reason TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS htd_monthly_metrics (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	month_start DATE NOT NULL, 
	cohort_size INTEGER NOT NULL, 
	converted INTEGER NOT NULL, 
	conversion_rate NUMERIC(5, 4), 
	calculated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS htd_pause_log (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	action VARCHAR(7) NOT NULL, 
	reason TEXT, 
	audit_findings TEXT, 
	corrective_actions TEXT, 
	resumed_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT htd_pause_log_action CHECK (action IN ('PAUSED', 'RESUMED'))
)




CREATE TABLE IF NOT EXISTS htd_phase_gates (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	phase VARCHAR(30) NOT NULL, 
	gate_owner_role VARCHAR(30) NOT NULL, 
	gate_owner_user_id VARCHAR(50) NOT NULL, 
	gate_decision VARCHAR(10) NOT NULL, 
	gate_notes TEXT NOT NULL, 
	decided_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(gate_owner_user_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS intercompany_settlements (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	from_entity VARCHAR(50) NOT NULL, 
	to_entity VARCHAR(50) NOT NULL, 
	amount_usd_cents INTEGER NOT NULL, 
	settlement_date DATE NOT NULL, 
	reason TEXT NOT NULL, 
	created_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS internal_notes (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	content TEXT NOT NULL, 
	category VARCHAR(100), 
	created_by_id VARCHAR(50) NOT NULL, 
	created_by_name VARCHAR(200), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS interview_feedback (
	id SERIAL NOT NULL, 
	interview_id INTEGER, 
	interviewer_id VARCHAR(50), 
	technical_score INTEGER, 
	communication_score INTEGER, 
	problem_solving_score INTEGER, 
	culture_fit_score INTEGER, 
	comments TEXT, 
	recommendation VARCHAR(20), 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(interview_id) REFERENCES interviews (id), 
	FOREIGN KEY(interviewer_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS interview_panels (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50), 
	job_id VARCHAR(50), 
	round_name VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID")
)




CREATE TABLE IF NOT EXISTS interview_rehire_reviews (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	round_name VARCHAR(50) NOT NULL, 
	job_id VARCHAR(50), 
	requested_by VARCHAR(50), 
	justification TEXT NOT NULL, 
	past_no_hire_panel_ids JSON, 
	status VARCHAR(19) NOT NULL, 
	ai_decision VARCHAR(8), 
	ai_reasoning TEXT, 
	ai_confidence NUMERIC(3, 2), 
	decided_by VARCHAR(50), 
	decided_at TIMESTAMP WITHOUT TIME ZONE, 
	decision_note TEXT, 
	resulting_panel_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID"), 
	FOREIGN KEY(requested_by) REFERENCES users ("UserID"), 
	CONSTRAINT rehire_review_status CHECK (status IN ('PENDING_HM_APPROVAL', 'AI_CLEARED', 'APPROVED', 'REJECTED')), 
	CONSTRAINT rehire_review_ai_decision CHECK (ai_decision IN ('CLEAR', 'ESCALATE')), 
	FOREIGN KEY(decided_by) REFERENCES users ("UserID"), 
	FOREIGN KEY(resulting_panel_id) REFERENCES interview_panels (id)
)




CREATE TABLE IF NOT EXISTS interview_reminders (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	interview_id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	reminder_type VARCHAR(10) NOT NULL, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(9) NOT NULL, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(interview_id) REFERENCES submission_interviews (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	CONSTRAINT interview_reminder_type CHECK (reminder_type IN ('24H_BEFORE', '1H_BEFORE')), 
	CONSTRAINT interview_reminder_status CHECK (status IN ('PENDING', 'SENT', 'CANCELLED'))
)




CREATE TABLE IF NOT EXISTS interviews (
	id SERIAL NOT NULL, 
	"interviewID" VARCHAR(50) NOT NULL, 
	panel_id INTEGER, 
	candidate_id VARCHAR(50), 
	start_time TIMESTAMP WITHOUT TIME ZONE, 
	end_time TIMESTAMP WITHOUT TIME ZONE, 
	meeting_link TEXT, 
	outlook_event_id TEXT, 
	status VARCHAR(50), 
	feedback_status VARCHAR(50) DEFAULT 'Pending' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(panel_id) REFERENCES interview_panels (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID")
)




CREATE TABLE IF NOT EXISTS invoice_line_items (
	id VARCHAR(36) NOT NULL, 
	invoice_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	timesheet_id VARCHAR(36) NOT NULL, 
	hours NUMERIC(6, 2) NOT NULL, 
	rate_usd_cents INTEGER NOT NULL, 
	amount_usd_cents INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(timesheet_id) REFERENCES timesheets (id)
)




CREATE TABLE IF NOT EXISTS invoices (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	opportunity_id VARCHAR(36), 
	project_id VARCHAR(36) NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	business_unit_id INTEGER, 
	billing_period_start DATE NOT NULL, 
	billing_period_end DATE NOT NULL, 
	status VARCHAR(8) NOT NULL, 
	total_usd_cents INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	approved_by VARCHAR(50), 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	paid_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	CONSTRAINT invoice_status CHECK (status IN ('DRAFT', 'APPROVED', 'SENT', 'PAID')), 
	CONSTRAINT invoice_currency CHECK (currency IN ('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD')), 
	FOREIGN KEY(approved_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS job_title_roles (
	id SERIAL NOT NULL, 
	job_title_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_job_title_role UNIQUE (job_title_id, role_id), 
	FOREIGN KEY(job_title_id) REFERENCES job_titles (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
)




CREATE TABLE IF NOT EXISTS job_titles (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_job_title_name_per_tenant UNIQUE (tenant_id, name), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)




CREATE TABLE IF NOT EXISTS jobs (
	"jobID" VARCHAR(50) NOT NULL, 
	"jobTitle" VARCHAR(200) NOT NULL, 
	"jobDescription" TEXT NOT NULL, 
	"jobSkills" TEXT NOT NULL, 
	"jobExperience" VARCHAR(50) NOT NULL, 
	"jobLocation" VARCHAR(50) NOT NULL, 
	"salaryRange" VARCHAR(50), 
	"jobCreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	"companyType" VARCHAR(50), 
	"companyName" VARCHAR(50), 
	"contactPerson" VARCHAR(50), 
	"jobStatus" VARCHAR(50), 
	"noOfPositions" INTEGER, 
	"startDate" DATE, 
	"endDate" DATE, 
	"recuriterID" VARCHAR(50), 
	"hiringManagerID" VARCHAR(50), 
	business_unit_id INTEGER, 
	department_id INTEGER, 
	tenant_id INTEGER, 
	required_skills_canonical JSON, 
	min_experience_years INTEGER, 
	domain VARCHAR(100), 
	certifications_preferred JSON, 
	budget_min INTEGER, 
	budget_max INTEGER, 
	urgency VARCHAR(9), 
	hm_validation_questions JSON, 
	hm_validation_required BOOLEAN DEFAULT '0' NOT NULL, 
	hm_validation_timeout_hours INTEGER DEFAULT '24' NOT NULL, 
	auto_schedule_after_approval BOOLEAN DEFAULT '1' NOT NULL, 
	hm_auto_reject_threshold INTEGER, 
	PRIMARY KEY ("jobID"), 
	FOREIGN KEY("contactPerson") REFERENCES users ("UserID"), 
	FOREIGN KEY("recuriterID") REFERENCES users ("UserID"), 
	FOREIGN KEY("hiringManagerID") REFERENCES users ("UserID"), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT job_urgency CHECK (urgency IN ('IMMEDIATE', 'HIGH', 'NORMAL', 'FLEXIBLE'))
)




CREATE TABLE IF NOT EXISTS message_templates (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	template_key VARCHAR(17) NOT NULL, 
	template_name VARCHAR(200) NOT NULL, 
	channel VARCHAR(8) NOT NULL, 
	language VARCHAR(10) DEFAULT 'en' NOT NULL, 
	subject VARCHAR(500), 
	body TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	is_active BOOLEAN DEFAULT '0' NOT NULL, 
	created_by VARCHAR(50), 
	approved_by VARCHAR(50), 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_message_template_version UNIQUE (tenant_id, template_key, version, channel), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID"), 
	CONSTRAINT message_template_key CHECK (template_key IN ('GREETING_WHATSAPP', 'GREETING_EMAIL')), 
	CONSTRAINT message_template_channel CHECK (channel IN ('WHATSAPP', 'EMAIL', 'PORTAL', 'ANY'))
)




CREATE TABLE IF NOT EXISTS motivation_content_library (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	desire_category VARCHAR(30) NOT NULL, 
	content_items JSON NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_by VARCHAR(50), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_motivation_content_per_tenant_category UNIQUE (tenant_id, desire_category), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(updated_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS motivation_outcomes (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	trigger_type VARCHAR(30) NOT NULL, 
	message_sent TEXT NOT NULL, 
	desire_category_targeted VARCHAR(30), 
	sent_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	response_within_24h BOOLEAN, 
	engagement_before VARCHAR(10), 
	engagement_after VARCHAR(10), 
	offer_accepted BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS newsletter_subscribers (
	id SERIAL NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	name VARCHAR(100), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)




CREATE TABLE IF NOT EXISTS newsletters (
	id VARCHAR(50) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	content TEXT NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	created_by VARCHAR(50) NOT NULL, 
	scheduled_for TIMESTAMP WITHOUT TIME ZONE, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS notifications (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	recipient_id VARCHAR(50) NOT NULL, 
	channel VARCHAR(8) NOT NULL, 
	fallback_channel VARCHAR(8), 
	priority_tier VARCHAR(2) NOT NULL, 
	message TEXT NOT NULL, 
	delivery_status VARCHAR(13) NOT NULL, 
	scheduled_release_at TIMESTAMP WITHOUT TIME ZONE, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	read_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(recipient_id) REFERENCES users ("UserID"), 
	CONSTRAINT notification_channel CHECK (channel IN ('IN_APP', 'EMAIL', 'WHATSAPP', 'SMS')), 
	CONSTRAINT notification_fallback_channel CHECK (fallback_channel IN ('IN_APP', 'EMAIL', 'WHATSAPP', 'SMS')), 
	CONSTRAINT notification_priority_tier CHECK (priority_tier IN ('P0', 'P1', 'P2')), 
	CONSTRAINT notification_delivery_status CHECK (delivery_status IN ('PENDING', 'SENT', 'FALLBACK_SENT', 'FAILED'))
)




CREATE TABLE IF NOT EXISTS offer_faq_entries (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	topic VARCHAR(50) NOT NULL, 
	answer_text TEXT NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_offer_faq_entry UNIQUE (tenant_id, topic), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS offer_letters (
	id SERIAL NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	job_id VARCHAR(50), 
	hiring_manager_id VARCHAR(50), 
	reporting_manager_id VARCHAR(50), 
	position VARCHAR(200) NOT NULL, 
	salary VARCHAR(50) NOT NULL, 
	joining_date DATE NOT NULL, 
	offer_expire_date DATE NOT NULL, 
	offer_status VARCHAR(30) NOT NULL, 
	candidate_response TEXT, 
	responded_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	created_by VARCHAR(50), 
	cancelled_at TIMESTAMP WITHOUT TIME ZONE, 
	cancelled_by VARCHAR(50), 
	sharepoint_url TEXT, 
	download_url TEXT, 
	sharepoint_path TEXT, 
	approval_status VARCHAR(30), 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	approved_by VARCHAR(50), 
	approval_notes TEXT, 
	released_at TIMESTAMP WITHOUT TIME ZONE, 
	released_by VARCHAR(50), 
	hm_signature_path TEXT, 
	candidate_signature_path TEXT, 
	signed_offer_path TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(job_id) REFERENCES jobs ("jobID"), 
	FOREIGN KEY(hiring_manager_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(reporting_manager_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID"), 
	FOREIGN KEY(cancelled_by) REFERENCES users ("UserID"), 
	FOREIGN KEY(approved_by) REFERENCES users ("UserID"), 
	FOREIGN KEY(released_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS opportunities (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	client_id VARCHAR(36) NOT NULL, 
	client_owner_id VARCHAR(36), 
	account_manager_id VARCHAR(36), 
	business_unit_id INTEGER, 
	stage VARCHAR(13) NOT NULL, 
	engagement_type VARCHAR(18) NOT NULL, 
	service VARCHAR(40), 
	module VARCHAR(34), 
	client_type VARCHAR(16), 
	pricing_model VARCHAR(37), 
	revenue_value_usd_cents INTEGER NOT NULL, 
	revenue_value_native INTEGER, 
	currency VARCHAR(3) NOT NULL, 
	probability_pct INTEGER NOT NULL, 
	expected_close_date DATE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(client_owner_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(account_manager_id) REFERENCES employees (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	CONSTRAINT opportunity_stage CHECK (stage IN ('QUALIFICATION', 'PROSPECT', 'PROPOSAL', 'NEGOTIATION', 'CONTRACT', 'ACTIVE', 'LOST')), 
	CONSTRAINT opportunity_engagement_type CHECK (engagement_type IN ('STAFF_AUGMENTATION', 'PROJECT_BASED')), 
	CONSTRAINT opportunity_service CHECK (service IN ('Consulting & Advisory', 'System Integration', 'System Implementation & Managed Services', 'QA & Testing', 'Data Migration', 'Cloud Migration', 'Analytics and Insights', 'Digital Experiences', 'Staff Augmentation', 'Others')), 
	CONSTRAINT opportunity_module CHECK (module IN ('PolicyCenter', 'ClaimsCenter', 'BillingCenter', 'InsuranceSuite', 'InsuranceNow', 'PricingCenter', 'UnderwritingCenter', 'Jutro Digital', 'Data and Analytics', 'ProNavigator', 'Guidewire Marketplace accelerators', 'Others')), 
	CONSTRAINT opportunity_client_type CHECK (client_type IN ('Personal lines', 'Commercial lines', 'Specialty lines', 'Others')), 
	CONSTRAINT opportunity_pricing_model CHECK (pricing_model IN ('FTE-based', 'Transaction-based', 'Per policy', 'Outcome based/profit and risk sharing', 'Rebadge of Carrier FTEs', 'Monetization of Carrier Assets', 'Time and Material (T&M)', 'Fixed Bid', 'As-a-Service/Managed service', 'Service-as-a-software', 'Others')), 
	CONSTRAINT opportunity_currency CHECK (currency IN ('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD'))
)




CREATE TABLE IF NOT EXISTS orchestration_events (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	agent_id VARCHAR(50) NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id VARCHAR(50) NOT NULL, 
	action_type VARCHAR(50) NOT NULL, 
	risk_tier VARCHAR(20), 
	proposed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	matched_rule_id VARCHAR(36), 
	resolution_action VARCHAR(20), 
	llm_classified BOOLEAN NOT NULL, 
	llm_call_failed BOOLEAN NOT NULL, 
	severity VARCHAR(20), 
	escalated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(matched_rule_id) REFERENCES conflict_rules (id)
)




CREATE TABLE IF NOT EXISTS org_nodes (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	position_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	parent_id VARCHAR(36), 
	department_id VARCHAR(36), 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(position_id) REFERENCES org_positions (id), 
	FOREIGN KEY(parent_id) REFERENCES org_nodes (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
)




CREATE TABLE IF NOT EXISTS org_positions (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	rank INTEGER NOT NULL, 
	description TEXT, 
	approves_to_rank INTEGER, 
	approves_workflows VARCHAR(500), 
	rbac_role_name VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)




CREATE TABLE IF NOT EXISTS outreach_campaigns (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	campaign_type VARCHAR(50) DEFAULT 'STANDARD_OUTREACH' NOT NULL, 
	status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	stop_reason VARCHAR(200), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(conversation_id) REFERENCES candidate_conversations (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS outreach_sequences (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	candidate_id VARCHAR(50) NOT NULL, 
	demand_id VARCHAR(36), 
	message_text TEXT, 
	primary_channel VARCHAR(20) NOT NULL, 
	fallback_sequence TEXT, 
	status VARCHAR(30) NOT NULL, 
	touch_count INTEGER NOT NULL, 
	consent_given_snapshot BOOLEAN, 
	sent_via VARCHAR(50), 
	last_touch_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	blocked_reason TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(demand_id) REFERENCES demands (id)
)




CREATE TABLE IF NOT EXISTS panel_members (
	id SERIAL NOT NULL, 
	panel_id INTEGER, 
	interviewer_id VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(panel_id) REFERENCES interview_panels (id), 
	FOREIGN KEY(interviewer_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS partner_bu_assignments (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	partner_org_node_id VARCHAR(36) NOT NULL, 
	business_unit_id VARCHAR(36) NOT NULL, 
	core_revenue_share_pct INTEGER, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(partner_org_node_id) REFERENCES org_nodes (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id)
)




CREATE TABLE IF NOT EXISTS partner_goals (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	partner_user_id VARCHAR(50) NOT NULL, 
	target_period VARCHAR(6) NOT NULL, 
	fiscal_year INTEGER NOT NULL, 
	target_amount_usd_cents INTEGER NOT NULL, 
	created_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(partner_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT partner_target_period CHECK (target_period IN ('Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'ANNUAL')), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS partner_incentive_events (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	rule_id VARCHAR(36) NOT NULL, 
	partner_user_id VARCHAR(50) NOT NULL, 
	client_id VARCHAR(36), 
	amount_usd_cents INTEGER NOT NULL, 
	status VARCHAR(7) NOT NULL, 
	triggered_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	paid_at TIMESTAMP WITHOUT TIME ZONE, 
	period_year INTEGER, 
	period_month INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_partner_incentive_events_rule_client UNIQUE (rule_id, client_id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(rule_id) REFERENCES partner_incentive_rules (id), 
	FOREIGN KEY(partner_user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	CONSTRAINT incentive_event_status CHECK (status IN ('PENDING', 'PAID'))
)




CREATE TABLE IF NOT EXISTS partner_incentive_rules (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	partner_user_id VARCHAR(50) NOT NULL, 
	incentive_type VARCHAR(16) NOT NULL, 
	amount_usd_cents INTEGER, 
	revenue_share_pct NUMERIC(5, 2), 
	trigger_description TEXT, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(partner_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT incentive_type CHECK (incentive_type IN ('NEW_LOGO_BONUS', 'REVENUE_SHARE', 'DEPLOYMENT_BONUS', 'OTHER'))
)




CREATE TABLE IF NOT EXISTS partner_intent_profiles (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	partner_user_id VARCHAR(50) NOT NULL, 
	demand_count INTEGER NOT NULL, 
	core_demand_pct NUMERIC(5, 2), 
	specialty_demand_pct NUMERIC(5, 2), 
	avg_experience_level NUMERIC(4, 1), 
	experience_level_std_dev NUMERIC(4, 2), 
	typical_billing_range_min_usd_cents INTEGER, 
	typical_billing_range_max_usd_cents INTEGER, 
	typical_skills TEXT, 
	last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(partner_user_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS permissions (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)




CREATE TABLE IF NOT EXISTS pipeline_leakage_flags (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	pattern_type VARCHAR(22) NOT NULL, 
	business_unit_id INTEGER, 
	opportunity_id VARCHAR(36), 
	demand_id VARCHAR(36), 
	revenue_leakage_flag_id VARCHAR(36), 
	sub_vendor_request_id VARCHAR(36), 
	estimated_impact_usd_cents INTEGER, 
	detail TEXT, 
	detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	resolution_note TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT leakage_pattern_type CHECK (pattern_type IN ('STALLED_OPPORTUNITY', 'UNFILLED_DEMAND', 'UNBILLED_TIME', 'SUBVENDOR_COST_OVERRUN')), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	FOREIGN KEY(revenue_leakage_flag_id) REFERENCES revenue_leakage_time_layer (id), 
	FOREIGN KEY(sub_vendor_request_id) REFERENCES sub_vendor_requests (id)
)




CREATE TABLE IF NOT EXISTS preboarding_documents (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	offer_id INTEGER NOT NULL, 
	document_type VARCHAR(100) NOT NULL, 
	document_label VARCHAR(200) NOT NULL, 
	status VARCHAR(9) DEFAULT 'PENDING' NOT NULL, 
	document_url TEXT, 
	received_at TIMESTAMP WITHOUT TIME ZONE, 
	reminder_count INTEGER DEFAULT '0' NOT NULL, 
	last_reminded_at TIMESTAMP WITHOUT TIME ZONE, 
	is_mandatory BOOLEAN DEFAULT '1' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_preboarding_document UNIQUE (tenant_id, candidate_id, offer_id, document_type), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(offer_id) REFERENCES offer_letters (id) ON DELETE CASCADE, 
	CONSTRAINT preboarding_document_status CHECK (status IN ('PENDING', 'RECEIVED', 'VERIFIED', 'WAIVED', 'CANCELLED'))
)




CREATE TABLE IF NOT EXISTS preboarding_touchpoints (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	offer_id INTEGER NOT NULL, 
	touchpoint_type VARCHAR(20) NOT NULL, 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	FOREIGN KEY(offer_id) REFERENCES offer_letters (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS project_milestones (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	project_id VARCHAR(36) NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	description TEXT, 
	due_date DATE NOT NULL, 
	owner_employee_id VARCHAR(36), 
	is_complete VARCHAR(8) NOT NULL, 
	completion_date DATE, 
	delay_days INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(owner_employee_id) REFERENCES employees (id), 
	CONSTRAINT project_milestone_completion CHECK (is_complete IN ('PENDING', 'COMPLETE'))
)




CREATE TABLE IF NOT EXISTS projects (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	client_id VARCHAR(36) NOT NULL, 
	opportunity_id VARCHAR(36), 
	client_owner_id VARCHAR(36), 
	name VARCHAR(300) NOT NULL, 
	status VARCHAR(9) NOT NULL, 
	billing_type VARCHAR(18) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	continent VARCHAR(50), 
	allow_weekend_billing BOOLEAN NOT NULL, 
	delivery_engine VARCHAR(10) DEFAULT 'SPECIALITY' NOT NULL, 
	si_partner VARCHAR(12), 
	end_client VARCHAR(300), 
	client_partner VARCHAR(300), 
	business_type VARCHAR(16), 
	start_date DATE, 
	end_date DATE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	created_by VARCHAR(50), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id), 
	FOREIGN KEY(client_owner_id) REFERENCES users ("UserID"), 
	CONSTRAINT project_status CHECK (status IN ('PLANNING', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CLOSED')), 
	CONSTRAINT project_billing_type CHECK (billing_type IN ('TIME_AND_MATERIALS', 'FIXED_BID')), 
	CONSTRAINT project_currency CHECK (currency IN ('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD')), 
	CONSTRAINT project_delivery_engine CHECK (delivery_engine IN ('SPECIALITY', 'CORE')), 
	CONSTRAINT project_si_partner CHECK (si_partner IN ('PWC', 'EY', 'CASTLEBAY', 'ZENSAR', 'LTI_MINDTREE', 'OTHER')), 
	CONSTRAINT project_business_type CHECK (business_type IN ('T_AND_M', 'MANAGED_SERVICES', 'PROJECT', 'POD', 'PILOT'))
)




CREATE TABLE IF NOT EXISTS prompt_execution_log (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50), 
	prompt_type VARCHAR(50) NOT NULL, 
	template_version VARCHAR(20) NOT NULL, 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	latency_ms INTEGER, 
	response_preview VARCHAR(200), 
	model VARCHAR(50), 
	success BOOLEAN NOT NULL, 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE SET NULL
)




CREATE TABLE IF NOT EXISTS recognition_message_drafts (
	id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	occasion VARCHAR(30) NOT NULL, 
	draft_text TEXT NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	approved_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(approved_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS reconciliation_alerts (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	timesheet_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	billable_hours NUMERIC(6, 2) NOT NULL, 
	gap_detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	status VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(timesheet_id) REFERENCES timesheets (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	CONSTRAINT reconciliation_alert_status CHECK (status IN ('UNRESOLVED', 'RESOLVED'))
)




CREATE TABLE IF NOT EXISTS recruiter_intervention_queue (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	queue_reason VARCHAR(18) NOT NULL, 
	reason_detail TEXT, 
	priority INTEGER NOT NULL, 
	status VARCHAR(11) NOT NULL, 
	assigned_to_user_id VARCHAR(50), 
	added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	resolved_by VARCHAR(50), 
	resolution_note TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID") ON DELETE CASCADE, 
	CONSTRAINT intervention_queue_reason CHECK (queue_reason IN ('ESCALATION', 'HIGH_DROP_RISK', 'CRITICAL_DROP_RISK', 'SLA_BREACH', 'HIGH_ABANDONMENT', 'NO_SHOW', 'OFFER_COUNTER', 'DOCUMENT_OVERDUE')), 
	CONSTRAINT intervention_queue_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED')), 
	FOREIGN KEY(assigned_to_user_id) REFERENCES users ("UserID") ON DELETE NO ACTION, 
	FOREIGN KEY(resolved_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS reserve_fund_entries (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	business_unit_id INTEGER, 
	entry_type VARCHAR(12) NOT NULL, 
	amount_usd_cents INTEGER NOT NULL, 
	period_year INTEGER NOT NULL, 
	period_month INTEGER NOT NULL, 
	created_by VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	CONSTRAINT reserve_fund_entry_type CHECK (entry_type IN ('CONTRIBUTION', 'WITHDRAWAL')), 
	FOREIGN KEY(created_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS revenue_leakage_time_layer (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	project_id VARCHAR(36) NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	approved_hours NUMERIC(8, 2) NOT NULL, 
	invoiced_hours NUMERIC(8, 2) NOT NULL, 
	unbilled_hours NUMERIC(8, 2) NOT NULL, 
	partial_billing_reason TEXT, 
	detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
)




CREATE TABLE IF NOT EXISTS revenues (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	invoice_id VARCHAR(36) NOT NULL, 
	opportunity_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	client_id VARCHAR(36) NOT NULL, 
	business_unit_id INTEGER, 
	client_owner_id VARCHAR(36), 
	revenue_usd_cents INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	service VARCHAR(100), 
	module VARCHAR(100), 
	client_type VARCHAR(100), 
	pricing_model VARCHAR(100), 
	business_type VARCHAR(10), 
	partner_id VARCHAR(36), 
	partner_revenue_share_pct INTEGER, 
	partner_revenue_share_usd_cents INTEGER, 
	cost_usd_cents INTEGER, 
	gross_margin_usd_cents INTEGER, 
	gross_margin_pct INTEGER, 
	source VARCHAR(17) NOT NULL, 
	recognized_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	FOREIGN KEY(opportunity_id) REFERENCES opportunities (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(client_owner_id) REFERENCES users ("UserID"), 
	CONSTRAINT revenue_currency CHECK (currency IN ('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD')), 
	CONSTRAINT revenue_business_type CHECK (business_type IN ('CORE', 'SPECIALITY')), 
	CONSTRAINT revenue_source CHECK (source IN ('INVOICE', 'MANUAL_ADJUSTMENT', 'CORRECTION'))
)




CREATE TABLE IF NOT EXISTS role_attributes (
	id SERIAL NOT NULL, 
	role_id INTEGER NOT NULL, 
	attribute_name VARCHAR(100) NOT NULL, 
	attribute_value BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_attribute UNIQUE (role_id, attribute_name), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS role_permissions (
	id SERIAL NOT NULL, 
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS role_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	role_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
)




CREATE TABLE IF NOT EXISTS roles (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)




CREATE TABLE IF NOT EXISTS sourcing_alerts (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	demand_id VARCHAR(36) NOT NULL, 
	gap_score_id VARCHAR(36), 
	severity VARCHAR(20) NOT NULL, 
	rationale TEXT, 
	bench_first_check_passed BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	acknowledged_at TIMESTAMP WITHOUT TIME ZONE, 
	acknowledged_by VARCHAR(50), 
	sourced_at TIMESTAMP WITHOUT TIME ZONE, 
	consecutive_search_failures INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	FOREIGN KEY(gap_score_id) REFERENCES demand_gap_scores (id), 
	FOREIGN KEY(acknowledged_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS sourcing_search_runs (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	sourcing_alert_id VARCHAR(36) NOT NULL, 
	boolean_query TEXT, 
	alt_queries TEXT, 
	search_rationale TEXT, 
	estimated_result_volume INTEGER, 
	manual_query_override TEXT, 
	status VARCHAR(20) NOT NULL, 
	staged_candidate_count INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(sourcing_alert_id) REFERENCES sourcing_alerts (id)
)




CREATE TABLE IF NOT EXISTS staged_candidates (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	search_run_id VARCHAR(36) NOT NULL, 
	linkedin_profile_url VARCHAR(500), 
	email VARCHAR(200), 
	mobile VARCHAR(20), 
	full_name VARCHAR(300), 
	raw_profile_data TEXT, 
	dedup_status VARCHAR(30) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	promoted_to_candidate_id VARCHAR(50), 
	promoted_by VARCHAR(50), 
	promoted_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(search_run_id) REFERENCES sourcing_search_runs (id), 
	FOREIGN KEY(promoted_to_candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(promoted_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS sub_vendor_accounts (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	company_name VARCHAR(300) NOT NULL, 
	tax_id VARCHAR(100), 
	contact_email VARCHAR(300) NOT NULL, 
	contact_phone VARCHAR(50), 
	status VARCHAR(16) NOT NULL, 
	compliance_status VARCHAR(18) NOT NULL, 
	approved_by VARCHAR(50), 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT subvendor_status CHECK (status IN ('PENDING_APPROVAL', 'APPROVED', 'SUSPENDED', 'REJECTED')), 
	CONSTRAINT subvendor_compliance_status CHECK (compliance_status IN ('GOOD_STANDING', 'UNDER_REVIEW', 'SUSPENSION_PENDING', 'SUSPENDED')), 
	FOREIGN KEY(approved_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS sub_vendor_dedup_rejections (
	id VARCHAR(36) NOT NULL, 
	submission_id VARCHAR(36) NOT NULL, 
	matched_candidate_id VARCHAR(50), 
	occurred_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(submission_id) REFERENCES sub_vendor_submissions (id), 
	FOREIGN KEY(matched_candidate_id) REFERENCES candidates ("candidateID")
)




CREATE TABLE IF NOT EXISTS sub_vendor_requests (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	demand_id VARCHAR(36) NOT NULL, 
	sub_vendor_id VARCHAR(36) NOT NULL, 
	assigned_by VARCHAR(50), 
	assigned_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	deadline TIMESTAMP WITHOUT TIME ZONE, 
	max_candidates INTEGER, 
	status VARCHAR(6) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	FOREIGN KEY(sub_vendor_id) REFERENCES sub_vendor_accounts (id), 
	FOREIGN KEY(assigned_by) REFERENCES users ("UserID"), 
	CONSTRAINT subvendor_request_status CHECK (status IN ('OPEN', 'CLOSED'))
)




CREATE TABLE IF NOT EXISTS sub_vendor_submissions (
	id VARCHAR(36) NOT NULL, 
	request_id VARCHAR(36) NOT NULL, 
	sub_vendor_id VARCHAR(36) NOT NULL, 
	candidate_name VARCHAR(300) NOT NULL, 
	candidate_email VARCHAR(300) NOT NULL, 
	candidate_phone VARCHAR(50), 
	current_employer VARCHAR(300), 
	total_experience_years NUMERIC(4, 1), 
	expected_salary VARCHAR(50), 
	notice_period VARCHAR(100), 
	resume_url TEXT, 
	employment_type VARCHAR(11) NOT NULL, 
	status VARCHAR(19) NOT NULL, 
	feedback_note TEXT, 
	created_candidate_id VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES sub_vendor_requests (id), 
	FOREIGN KEY(sub_vendor_id) REFERENCES sub_vendor_accounts (id), 
	CONSTRAINT subvendor_submission_employment_type CHECK (employment_type IN ('W2_FULLTIME', 'C2C', '1099', 'UNKNOWN')), 
	CONSTRAINT subvendor_submission_status CHECK (status IN ('PENDING_REVIEW', 'ACCEPTED', 'REJECTED', 'MORE_INFO_REQUESTED')), 
	FOREIGN KEY(created_candidate_id) REFERENCES candidates ("candidateID")
)




CREATE TABLE IF NOT EXISTS sub_vendor_users (
	id VARCHAR(36) NOT NULL, 
	sub_vendor_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	email VARCHAR(300) NOT NULL, 
	password_hash VARCHAR(300) NOT NULL, 
	role VARCHAR(9) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(sub_vendor_id) REFERENCES sub_vendor_accounts (id), 
	CONSTRAINT subvendor_user_role CHECK (role IN ('ADMIN', 'SUBMITTER'))
)




CREATE TABLE IF NOT EXISTS sub_vendor_violations (
	id VARCHAR(36) NOT NULL, 
	sub_vendor_id VARCHAR(36) NOT NULL, 
	submission_id VARCHAR(36), 
	violation_type VARCHAR(16) NOT NULL, 
	employment_type VARCHAR(20), 
	occurred_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	is_cleared BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sub_vendor_id) REFERENCES sub_vendor_accounts (id), 
	FOREIGN KEY(submission_id) REFERENCES sub_vendor_submissions (id), 
	CONSTRAINT subvendor_violation_type CHECK (violation_type IN ('C2C_NOT_ACCEPTED'))
)




CREATE TABLE IF NOT EXISTS submission_interviews (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	submission_id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	level VARCHAR(2) NOT NULL, 
	panel_id VARCHAR(36), 
	scheduled_at TIMESTAMP WITHOUT TIME ZONE, 
	outcome VARCHAR(7) NOT NULL, 
	outcome_set_at TIMESTAMP WITHOUT TIME ZONE, 
	scheduled_via_graph_event_id VARCHAR(200), 
	confirmed_at TIMESTAMP WITHOUT TIME ZONE, 
	reschedule_count INTEGER DEFAULT '0' NOT NULL, 
	rescheduled_from_interview_id VARCHAR(36), 
	superseded_at TIMESTAMP WITHOUT TIME ZONE, 
	no_show_check_in_at TIMESTAMP WITHOUT TIME ZONE, 
	no_show_confirmed_at TIMESTAMP WITHOUT TIME ZONE, 
	no_show_reschedule_offer_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	no_show_no_response_at TIMESTAMP WITHOUT TIME ZONE, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(submission_id) REFERENCES submissions (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	CONSTRAINT submission_interview_level CHECK (level IN ('L1', 'L2')), 
	FOREIGN KEY(panel_id) REFERENCES demand_interview_panels (id), 
	CONSTRAINT submission_interview_outcome CHECK (outcome IN ('PENDING', 'PASS', 'FAIL')), 
	FOREIGN KEY(rescheduled_from_interview_id) REFERENCES submission_interviews (id)
)




CREATE TABLE IF NOT EXISTS submission_violations (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	recruiter_user_id VARCHAR(50), 
	candidate_id VARCHAR(50) NOT NULL, 
	violation_type VARCHAR(21) NOT NULL, 
	attempted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	candidate_status_at_time VARCHAR(100), 
	blocked_message TEXT, 
	is_cleared BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(recruiter_user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	CONSTRAINT submission_violation_type CHECK (violation_type IN ('NO_MARKET_PROFILE', 'EXPERIENCE_INELIGIBLE', 'C2C_NOT_ACCEPTED'))
)




CREATE TABLE IF NOT EXISTS submissions (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	demand_id VARCHAR(36) NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(50) NOT NULL, 
	submitted_by_user_id VARCHAR(50), 
	submitted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	status VARCHAR(26) NOT NULL, 
	client_feedback TEXT, 
	client_response_at TIMESTAMP WITHOUT TIME ZONE, 
	submission_rank INTEGER, 
	submitted_as_resume_url TEXT, 
	source VARCHAR(9) NOT NULL, 
	subvendor_id VARCHAR(36), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_submission_per_demand_candidate UNIQUE (tenant_id, demand_id, candidate_id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(demand_id) REFERENCES demands (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(submitted_by_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT submission_status CHECK (status IN ('SUBMITTED', 'SHORTLISTED', 'CLIENT_INTERVIEW_REQUESTED', 'REJECTED_BY_CLIENT', 'OFFER_EXTENDED', 'PLACED', 'WITHDRAWN')), 
	CONSTRAINT submission_source CHECK (source IN ('INTERNAL', 'SUBVENDOR')), 
	FOREIGN KEY(subvendor_id) REFERENCES sub_vendor_accounts (id)
)




CREATE TABLE IF NOT EXISTS system_config (
	id SERIAL NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	business_unit_id INTEGER, 
	config_category VARCHAR(20) NOT NULL, 
	config_key VARCHAR(100) NOT NULL, 
	config_value JSON NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_by VARCHAR(50), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_system_config_scope_key UNIQUE (tenant_id, business_unit_id, config_key), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(updated_by) REFERENCES users ("UserID") ON DELETE NO ACTION
)




CREATE TABLE IF NOT EXISTS task_capacity_alerts (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(50) NOT NULL, 
	department_id INTEGER, 
	open_task_count INTEGER NOT NULL, 
	reason TEXT NOT NULL, 
	is_resolved BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
)




CREATE TABLE IF NOT EXISTS task_reassignment_requests (
	id VARCHAR(36) NOT NULL, 
	task_id INTEGER NOT NULL, 
	from_user_id VARCHAR(50) NOT NULL, 
	suggested_to_user_id VARCHAR(50), 
	reason VARCHAR(200) NOT NULL, 
	status VARCHAR(8) NOT NULL, 
	approved_by_user_id VARCHAR(50), 
	final_to_user_id VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(task_id) REFERENCES tasks (id), 
	FOREIGN KEY(from_user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(suggested_to_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT task_reassignment_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')), 
	FOREIGN KEY(approved_by_user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(final_to_user_id) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS tasks (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	title VARCHAR(300) NOT NULL, 
	description TEXT, 
	task_type VARCHAR(7) NOT NULL, 
	category VARCHAR(100), 
	subcategory VARCHAR(100), 
	priority VARCHAR(6) NOT NULL, 
	priority_challenged BOOLEAN NOT NULL, 
	priority_challenge_note TEXT, 
	status VARCHAR(11) NOT NULL, 
	department_id INTEGER, 
	business_unit_id INTEGER, 
	assigned_to_user_id VARCHAR(50), 
	created_by_user_id VARCHAR(50), 
	parent_task_id INTEGER, 
	candidate_id VARCHAR(50), 
	document_id INTEGER, 
	interview_id INTEGER, 
	expense_id VARCHAR(36), 
	invoice_id VARCHAR(36), 
	due_date TIMESTAMP WITHOUT TIME ZONE, 
	is_external BOOLEAN NOT NULL, 
	visibility_scope VARCHAR(27) NOT NULL, 
	is_escalated BOOLEAN NOT NULL, 
	escalated_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_task_urgent_has_validation_attempt CHECK (priority NOT IN ('URGENT') OR priority_challenge_note IS NOT NULL OR priority_challenged = 0), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT task_type CHECK (task_type IN ('GENERAL', 'TICKET')), 
	CONSTRAINT task_priority CHECK (priority IN ('URGENT', 'HIGH', 'MEDIUM', 'LOW')), 
	CONSTRAINT task_status CHECK (status IN ('NEW', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED')), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(assigned_to_user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(created_by_user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(parent_task_id) REFERENCES tasks (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID"), 
	FOREIGN KEY(document_id) REFERENCES candidate_documents (id), 
	FOREIGN KEY(interview_id) REFERENCES interviews (id), 
	FOREIGN KEY(expense_id) REFERENCES expense_records (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	CONSTRAINT task_visibility_scope CHECK (visibility_scope IN ('ASSIGNEE_MANAGER_DEPARTMENT', 'ORG_WIDE'))
)




CREATE TABLE IF NOT EXISTS tenants (
	id SERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	is_active BOOLEAN NOT NULL, 
	default_timezone VARCHAR(50) DEFAULT 'UTC' NOT NULL, 
	default_date_format VARCHAR(10) DEFAULT 'MM/DD/YYYY' NOT NULL, 
	default_currency VARCHAR(3) DEFAULT 'USD' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT tenant_date_format CHECK (default_date_format IN ('MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD')), 
	CONSTRAINT tenant_default_currency CHECK (default_currency IN ('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD'))
)




CREATE TABLE IF NOT EXISTS thunder_sessions (
	id VARCHAR(36) NOT NULL, 
	candidate_id VARCHAR(50), 
	candidate_email VARCHAR(200) NOT NULL, 
	status VARCHAR(11) DEFAULT 'STARTED' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	paused_at TIMESTAMP WITHOUT TIME ZONE, 
	resumed_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	last_activity_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	device_type VARCHAR(50), 
	browser VARCHAR(100), 
	ip_address VARCHAR(45), 
	session_id_client VARCHAR(100), 
	last_question_reached VARCHAR(10), 
	questions_answered INTEGER DEFAULT '0' NOT NULL, 
	questions_total INTEGER DEFAULT '12' NOT NULL, 
	completion_percentage INTEGER DEFAULT '0' NOT NULL, 
	form_state JSON, 
	form_responses JSON, 
	resume_url VARCHAR(500), 
	resume_uploaded_at TIMESTAMP WITHOUT TIME ZONE, 
	resume_parsed BOOLEAN DEFAULT '0' NOT NULL, 
	resume_parse_status VARCHAR(50), 
	resume_parsed_data JSON, 
	candidate_data JSON, 
	candidate_location VARCHAR(200), 
	job_matches JSON, 
	selected_job_id VARCHAR(50), 
	screening_responses JSON, 
	last_error VARCHAR(500), 
	error_count INTEGER DEFAULT '0' NOT NULL, 
	retry_batch_id VARCHAR(36), 
	submitted BOOLEAN DEFAULT '0' NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	handoff_to_ai_recruiter_at TIMESTAMP WITHOUT TIME ZONE, 
	utm_source VARCHAR(100), 
	utm_campaign VARCHAR(100), 
	notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates ("candidateID")
)




CREATE TABLE IF NOT EXISTS ticket_category_routes (
	id SERIAL NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	subcategory VARCHAR(100), 
	department_id INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ticket_category_route UNIQUE (category, subcategory), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
)




CREATE TABLE IF NOT EXISTS ticket_details (
	task_id INTEGER NOT NULL, 
	impact VARCHAR(30) NOT NULL, 
	urgency VARCHAR(15) NOT NULL, 
	response_due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	resolution_due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	first_response_at TIMESTAMP WITHOUT TIME ZONE, 
	response_breached BOOLEAN NOT NULL, 
	resolution_breached BOOLEAN NOT NULL, 
	PRIMARY KEY (task_id), 
	FOREIGN KEY(task_id) REFERENCES tasks (id)
)




CREATE TABLE IF NOT EXISTS ticket_sla_policies (
	priority VARCHAR(10) NOT NULL, 
	response_minutes INTEGER NOT NULL, 
	resolution_minutes INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (priority)
)




CREATE TABLE IF NOT EXISTS timesheet_anomaly_flags (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	timesheet_entry_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	anomaly_type VARCHAR(17) NOT NULL, 
	detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(timesheet_entry_id) REFERENCES timesheet_entries (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	CONSTRAINT timesheet_anomaly_type CHECK (anomaly_type IN ('WEEKEND', 'OVER_12H', 'COMPLETED_PROJECT', 'DUPLICATE', 'UNLINKED_TASK'))
)




CREATE TABLE IF NOT EXISTS timesheet_disputes (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	timesheet_id VARCHAR(36) NOT NULL, 
	raised_by VARCHAR(8) NOT NULL, 
	raised_by_user_id VARCHAR(50), 
	disputed_date TIMESTAMP WITHOUT TIME ZONE, 
	disputed_hours NUMERIC(4, 2), 
	original_hours NUMERIC(6, 2) NOT NULL, 
	reason TEXT NOT NULL, 
	status VARCHAR(18) NOT NULL, 
	resolved_by VARCHAR(50), 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	resolution_notes TEXT, 
	adjusted_hours NUMERIC(6, 2), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(timesheet_id) REFERENCES timesheets (id), 
	CONSTRAINT timesheet_dispute_raised_by CHECK (raised_by IN ('RM', 'EMPLOYEE', 'CLIENT')), 
	FOREIGN KEY(raised_by_user_id) REFERENCES users ("UserID"), 
	CONSTRAINT timesheet_dispute_status CHECK (status IN ('OPEN', 'UNDER_REVIEW', 'RESOLVED_ADJUSTED', 'RESOLVED_CONFIRMED', 'CANCELLED')), 
	FOREIGN KEY(resolved_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS timesheet_entries (
	id VARCHAR(36) NOT NULL, 
	timesheet_id VARCHAR(36) NOT NULL, 
	entry_date DATE NOT NULL, 
	hours NUMERIC(4, 2) NOT NULL, 
	entry_type VARCHAR(12) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_timesheet_entry_per_day UNIQUE (timesheet_id, entry_date), 
	CONSTRAINT ck_timesheet_entry_hours_range CHECK (hours >= 0 AND hours <= 24), 
	FOREIGN KEY(timesheet_id) REFERENCES timesheets (id), 
	CONSTRAINT timesheet_entry_type CHECK (entry_type IN ('BILLABLE', 'NON_BILLABLE', 'LEAVE', 'HOLIDAY'))
)




CREATE TABLE IF NOT EXISTS timesheet_nag_logs (
	id SERIAL NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	week_starting_date DATE NOT NULL, 
	escalation_level INTEGER NOT NULL, 
	last_nagged_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	resolved BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_timesheet_nag_employee_week UNIQUE (employee_id, week_starting_date), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
)




CREATE TABLE IF NOT EXISTS timesheets (
	id VARCHAR(36) NOT NULL, 
	tenant_id INTEGER, 
	employee_id VARCHAR(36) NOT NULL, 
	business_unit_id INTEGER, 
	allocation_id VARCHAR(36), 
	task_id INTEGER, 
	week_starting_date DATE NOT NULL, 
	total_hours NUMERIC(6, 2) NOT NULL, 
	billable_hours NUMERIC(6, 2) NOT NULL, 
	non_billable_hours NUMERIC(6, 2) NOT NULL, 
	status VARCHAR(9) NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	approved_by VARCHAR(50), 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	rejection_reason TEXT, 
	client_approver_email VARCHAR(300), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_timesheet_per_employee_allocation_week UNIQUE (tenant_id, employee_id, allocation_id, week_starting_date), 
	CONSTRAINT uq_timesheet_per_employee_task_week UNIQUE (tenant_id, employee_id, task_id, week_starting_date), 
	CONSTRAINT ck_timesheet_allocation_or_task CHECK ((allocation_id IS NOT NULL) OR (task_id IS NOT NULL)), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(allocation_id) REFERENCES employee_allocations (id), 
	FOREIGN KEY(task_id) REFERENCES tasks (id), 
	CONSTRAINT timesheet_status CHECK (status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'DISPUTED')), 
	FOREIGN KEY(approved_by) REFERENCES users ("UserID")
)




CREATE TABLE IF NOT EXISTS user_roles (
	id VARCHAR(255) NOT NULL, 
	user_id VARCHAR(50) NOT NULL, 
	role_id INTEGER NOT NULL, 
	business_unit_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users ("UserID"), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id)
)




CREATE TABLE IF NOT EXISTS users (
	"UserID" VARCHAR(50) NOT NULL, 
	"UserRole" VARCHAR(50) NOT NULL, 
	"UserName" VARCHAR(150), 
	"UserEmail" VARCHAR(200) NOT NULL, 
	"UserPassword" VARCHAR(200) NOT NULL, 
	"CreatedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	role_id INTEGER, 
	business_unit_id INTEGER, 
	department_id INTEGER, 
	tenant_id INTEGER, 
	mfa_enabled BOOLEAN NOT NULL, 
	mfa_secret VARCHAR(64), 
	mfa_backup_codes TEXT, 
	email_otp_code_hash VARCHAR(64), 
	email_otp_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	msgraph_mail_last_synced_at TIMESTAMP WITHOUT TIME ZONE, 
	timezone VARCHAR(64) DEFAULT 'Asia/Kolkata' NOT NULL, 
	whatsapp_number VARCHAR(20), 
	ai_agent_name VARCHAR(100), 
	ai_agent_persona TEXT, 
	digest_enabled BOOLEAN DEFAULT '1' NOT NULL, 
	thunder_enabled BOOLEAN DEFAULT '1' NOT NULL, 
	terminated_at TIMESTAMP WITHOUT TIME ZONE, 
	terminated_by_user_id VARCHAR(50), 
	PRIMARY KEY ("UserID"), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	UNIQUE (whatsapp_number), 
	FOREIGN KEY(terminated_by_user_id) REFERENCES users ("UserID")
)



-- ============================================
-- CREATE INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_activity_feed_read_state_tenant_id ON activity_feed_read_state(tenant_id);
CREATE INDEX IF NOT EXISTS idx_activity_timeline_tenant_id ON activity_timeline(tenant_id);
CREATE INDEX IF NOT EXISTS idx_activity_timeline_created_at ON activity_timeline(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_execution_log_tenant_id ON agent_execution_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_approval_chains_tenant_id ON approval_chains(tenant_id);
CREATE INDEX IF NOT EXISTS idx_approval_chains_created_at ON approval_chains(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_id ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_tenant_id ON bank_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_created_at ON bank_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_bu_revenue_targets_tenant_id ON bu_revenue_targets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bu_revenue_targets_created_at ON bu_revenue_targets(created_at);
CREATE INDEX IF NOT EXISTS idx_buddy_kpi_scores_tenant_id ON buddy_kpi_scores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_buddy_program_records_tenant_id ON buddy_program_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_buddy_program_records_created_at ON buddy_program_records(created_at);
CREATE INDEX IF NOT EXISTS idx_bulk_engagement_errors_created_at ON bulk_engagement_errors(created_at);
CREATE INDEX IF NOT EXISTS idx_bulk_engagement_jobs_tenant_id ON bulk_engagement_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bulk_engagement_jobs_created_at ON bulk_engagement_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_business_units_tenant_id ON business_units(tenant_id);
CREATE INDEX IF NOT EXISTS idx_business_units_created_at ON business_units(created_at);
CREATE INDEX IF NOT EXISTS idx_campaign_touchpoints_tenant_id ON campaign_touchpoints(tenant_id);
CREATE INDEX IF NOT EXISTS idx_campaign_touchpoints_created_at ON campaign_touchpoints(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_abandonment_scores_tenant_id ON candidate_abandonment_scores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_ai_assignments_tenant_id ON candidate_ai_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_assignments_created_at ON candidate_assignments(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_availability_slots_tenant_id ON candidate_availability_slots(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_availability_slots_created_at ON candidate_availability_slots(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_conversations_tenant_id ON candidate_conversations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_conversations_created_at ON candidate_conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_desire_profiles_tenant_id ON candidate_desire_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_desire_profiles_created_at ON candidate_desire_profiles(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_desire_signals_tenant_id ON candidate_desire_signals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_desire_signals_created_at ON candidate_desire_signals(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_drop_risk_tenant_id ON candidate_drop_risk(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_engagement_metrics_tenant_id ON candidate_engagement_metrics(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_field_skips_tenant_id ON candidate_field_skips(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_ghosting_status_tenant_id ON candidate_ghosting_status(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_ghosting_status_created_at ON candidate_ghosting_status(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_job_flags_tenant_id ON candidate_job_flags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_job_flags_created_at ON candidate_job_flags(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_job_scores_tenant_id ON candidate_job_scores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_joining_scores_tenant_id ON candidate_joining_scores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_memory_tenant_id ON candidate_memory(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_memory_created_at ON candidate_memory(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_memory_facts_tenant_id ON candidate_memory_facts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_no_response_log_tenant_id ON candidate_no_response_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_opportunity_watches_tenant_id ON candidate_opportunity_watches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_ownership_created_at ON candidate_ownership(created_at);
CREATE INDEX IF NOT EXISTS idx_candidate_resume_parsed_tenant_id ON candidate_resume_parsed(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_sentiment_log_tenant_id ON candidate_sentiment_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_skill_tags_tenant_id ON candidate_skill_tags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_sla_breaches_tenant_id ON candidate_sla_breaches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_sla_breaches_created_at ON candidate_sla_breaches(created_at);
CREATE INDEX IF NOT EXISTS idx_candidates_tenant_id ON candidates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_checklist_template_items_created_at ON checklist_template_items(created_at);
CREATE INDEX IF NOT EXISTS idx_checklist_templates_created_at ON checklist_templates(created_at);
CREATE INDEX IF NOT EXISTS idx_clarification_qa_tenant_id ON clarification_qa(tenant_id);
CREATE INDEX IF NOT EXISTS idx_client_contacts_tenant_id ON client_contacts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_client_contacts_created_at ON client_contacts(created_at);
CREATE INDEX IF NOT EXISTS idx_client_history_tenant_id ON client_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_clients_tenant_id ON clients(tenant_id);
CREATE INDEX IF NOT EXISTS idx_clients_created_at ON clients(created_at);
CREATE INDEX IF NOT EXISTS idx_conflict_rules_tenant_id ON conflict_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conflict_rules_created_at ON conflict_rules(created_at);
CREATE INDEX IF NOT EXISTS idx_consent_records_tenant_id ON consent_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversation_events_created_at ON conversation_events(created_at);
CREATE INDEX IF NOT EXISTS idx_cost_rate_configs_tenant_id ON cost_rate_configs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cost_rate_configs_created_at ON cost_rate_configs(created_at);
CREATE INDEX IF NOT EXISTS idx_data_scope_permissions_tenant_id ON data_scope_permissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_scope_permissions_created_at ON data_scope_permissions(created_at);
CREATE INDEX IF NOT EXISTS idx_demand_gap_scores_tenant_id ON demand_gap_scores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_demand_history_tenant_id ON demand_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_demand_interview_panels_tenant_id ON demand_interview_panels(tenant_id);
CREATE INDEX IF NOT EXISTS idx_demands_tenant_id ON demands(tenant_id);
CREATE INDEX IF NOT EXISTS idx_demands_created_at ON demands(created_at);
CREATE INDEX IF NOT EXISTS idx_departments_tenant_id ON departments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_departments_created_at ON departments(created_at);
CREATE INDEX IF NOT EXISTS idx_detailed_permissions_tenant_id ON detailed_permissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_detailed_permissions_created_at ON detailed_permissions(created_at);
CREATE INDEX IF NOT EXISTS idx_detailed_role_permissions_created_at ON detailed_role_permissions(created_at);
CREATE INDEX IF NOT EXISTS idx_employee_allocations_tenant_id ON employee_allocations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employee_allocations_created_at ON employee_allocations(created_at);
CREATE INDEX IF NOT EXISTS idx_employee_concern_intakes_created_at ON employee_concern_intakes(created_at);
CREATE INDEX IF NOT EXISTS idx_employee_documents_tenant_id ON employee_documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employee_employment_history_tenant_id ON employee_employment_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employee_engine_history_tenant_id ON employee_engine_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employee_feedback_cycles_tenant_id ON employee_feedback_cycles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employee_milestones_tenant_id ON employee_milestones(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employee_milestones_created_at ON employee_milestones(created_at);
CREATE INDEX IF NOT EXISTS idx_employee_performance_events_tenant_id ON employee_performance_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employees_tenant_id ON employees(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employees_created_at ON employees(created_at);
CREATE INDEX IF NOT EXISTS idx_error_log_tenant_id ON error_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_error_log_created_at ON error_log(created_at);
CREATE INDEX IF NOT EXISTS idx_event_log_tenant_id ON event_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_expense_records_tenant_id ON expense_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_expense_records_created_at ON expense_records(created_at);
CREATE INDEX IF NOT EXISTS idx_field_permissions_tenant_id ON field_permissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_field_permissions_created_at ON field_permissions(created_at);
CREATE INDEX IF NOT EXISTS idx_file_uploads_tenant_id ON file_uploads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_file_uploads_created_at ON file_uploads(created_at);
CREATE INDEX IF NOT EXISTS idx_follow_up_schedule_tenant_id ON follow_up_schedule(tenant_id);
CREATE INDEX IF NOT EXISTS idx_follow_up_schedule_created_at ON follow_up_schedule(created_at);
CREATE INDEX IF NOT EXISTS idx_hiring_manager_validations_created_at ON hiring_manager_validations(created_at);
CREATE INDEX IF NOT EXISTS idx_hm_validation_responses_created_at ON hm_validation_responses(created_at);
CREATE INDEX IF NOT EXISTS idx_hr_assignments_created_at ON hr_assignments(created_at);
CREATE INDEX IF NOT EXISTS idx_htd_intake_status_tenant_id ON htd_intake_status(tenant_id);
CREATE INDEX IF NOT EXISTS idx_htd_monthly_metrics_tenant_id ON htd_monthly_metrics(tenant_id);
CREATE INDEX IF NOT EXISTS idx_htd_pause_log_tenant_id ON htd_pause_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_htd_pause_log_created_at ON htd_pause_log(created_at);
CREATE INDEX IF NOT EXISTS idx_htd_phase_gates_tenant_id ON htd_phase_gates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_htd_phase_gates_created_at ON htd_phase_gates(created_at);
CREATE INDEX IF NOT EXISTS idx_intercompany_settlements_tenant_id ON intercompany_settlements(tenant_id);
CREATE INDEX IF NOT EXISTS idx_intercompany_settlements_created_at ON intercompany_settlements(created_at);
CREATE INDEX IF NOT EXISTS idx_internal_notes_created_at ON internal_notes(created_at);
CREATE INDEX IF NOT EXISTS idx_interview_panels_created_at ON interview_panels(created_at);
CREATE INDEX IF NOT EXISTS idx_interview_rehire_reviews_created_at ON interview_rehire_reviews(created_at);
CREATE INDEX IF NOT EXISTS idx_interview_reminders_tenant_id ON interview_reminders(tenant_id);
CREATE INDEX IF NOT EXISTS idx_interview_reminders_created_at ON interview_reminders(created_at);
CREATE INDEX IF NOT EXISTS idx_invoices_tenant_id ON invoices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);
CREATE INDEX IF NOT EXISTS idx_job_title_roles_created_at ON job_title_roles(created_at);
CREATE INDEX IF NOT EXISTS idx_job_titles_tenant_id ON job_titles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_job_titles_created_at ON job_titles(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_id ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_message_templates_tenant_id ON message_templates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_message_templates_created_at ON message_templates(created_at);
CREATE INDEX IF NOT EXISTS idx_motivation_content_library_tenant_id ON motivation_content_library(tenant_id);
CREATE INDEX IF NOT EXISTS idx_motivation_outcomes_tenant_id ON motivation_outcomes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_newsletter_subscribers_created_at ON newsletter_subscribers(created_at);
CREATE INDEX IF NOT EXISTS idx_newsletters_created_at ON newsletters(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_id ON notifications(tenant_id);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);
CREATE INDEX IF NOT EXISTS idx_offer_faq_entries_tenant_id ON offer_faq_entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_offer_letters_created_at ON offer_letters(created_at);
CREATE INDEX IF NOT EXISTS idx_opportunities_tenant_id ON opportunities(tenant_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_created_at ON opportunities(created_at);
CREATE INDEX IF NOT EXISTS idx_orchestration_events_tenant_id ON orchestration_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_events_created_at ON orchestration_events(created_at);
CREATE INDEX IF NOT EXISTS idx_org_nodes_tenant_id ON org_nodes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_org_nodes_created_at ON org_nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_org_positions_created_at ON org_positions(created_at);
CREATE INDEX IF NOT EXISTS idx_outreach_campaigns_tenant_id ON outreach_campaigns(tenant_id);
CREATE INDEX IF NOT EXISTS idx_outreach_campaigns_created_at ON outreach_campaigns(created_at);
CREATE INDEX IF NOT EXISTS idx_outreach_sequences_tenant_id ON outreach_sequences(tenant_id);
CREATE INDEX IF NOT EXISTS idx_outreach_sequences_created_at ON outreach_sequences(created_at);
CREATE INDEX IF NOT EXISTS idx_partner_bu_assignments_tenant_id ON partner_bu_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_partner_bu_assignments_created_at ON partner_bu_assignments(created_at);
CREATE INDEX IF NOT EXISTS idx_partner_goals_tenant_id ON partner_goals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_partner_goals_created_at ON partner_goals(created_at);
CREATE INDEX IF NOT EXISTS idx_partner_incentive_events_tenant_id ON partner_incentive_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_partner_incentive_rules_tenant_id ON partner_incentive_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_partner_incentive_rules_created_at ON partner_incentive_rules(created_at);
CREATE INDEX IF NOT EXISTS idx_partner_intent_profiles_tenant_id ON partner_intent_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_permissions_created_at ON permissions(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_leakage_flags_tenant_id ON pipeline_leakage_flags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_preboarding_documents_tenant_id ON preboarding_documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_preboarding_documents_created_at ON preboarding_documents(created_at);
CREATE INDEX IF NOT EXISTS idx_preboarding_touchpoints_tenant_id ON preboarding_touchpoints(tenant_id);
CREATE INDEX IF NOT EXISTS idx_preboarding_touchpoints_created_at ON preboarding_touchpoints(created_at);
CREATE INDEX IF NOT EXISTS idx_project_milestones_tenant_id ON project_milestones(tenant_id);
CREATE INDEX IF NOT EXISTS idx_project_milestones_created_at ON project_milestones(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_tenant_id ON projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_prompt_execution_log_tenant_id ON prompt_execution_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_prompt_execution_log_created_at ON prompt_execution_log(created_at);
CREATE INDEX IF NOT EXISTS idx_recognition_message_drafts_created_at ON recognition_message_drafts(created_at);
CREATE INDEX IF NOT EXISTS idx_reconciliation_alerts_tenant_id ON reconciliation_alerts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_intervention_queue_tenant_id ON recruiter_intervention_queue(tenant_id);
CREATE INDEX IF NOT EXISTS idx_reserve_fund_entries_tenant_id ON reserve_fund_entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_reserve_fund_entries_created_at ON reserve_fund_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_revenue_leakage_time_layer_tenant_id ON revenue_leakage_time_layer(tenant_id);
CREATE INDEX IF NOT EXISTS idx_revenues_tenant_id ON revenues(tenant_id);
CREATE INDEX IF NOT EXISTS idx_revenues_created_at ON revenues(created_at);
CREATE INDEX IF NOT EXISTS idx_role_attributes_created_at ON role_attributes(created_at);
CREATE INDEX IF NOT EXISTS idx_role_templates_created_at ON role_templates(created_at);
CREATE INDEX IF NOT EXISTS idx_roles_created_at ON roles(created_at);
CREATE INDEX IF NOT EXISTS idx_sourcing_alerts_tenant_id ON sourcing_alerts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sourcing_alerts_created_at ON sourcing_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_sourcing_search_runs_tenant_id ON sourcing_search_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sourcing_search_runs_created_at ON sourcing_search_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_staged_candidates_tenant_id ON staged_candidates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_staged_candidates_created_at ON staged_candidates(created_at);
CREATE INDEX IF NOT EXISTS idx_sub_vendor_accounts_tenant_id ON sub_vendor_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sub_vendor_accounts_created_at ON sub_vendor_accounts(created_at);
CREATE INDEX IF NOT EXISTS idx_sub_vendor_requests_tenant_id ON sub_vendor_requests(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sub_vendor_submissions_created_at ON sub_vendor_submissions(created_at);
CREATE INDEX IF NOT EXISTS idx_sub_vendor_users_created_at ON sub_vendor_users(created_at);
CREATE INDEX IF NOT EXISTS idx_submission_interviews_tenant_id ON submission_interviews(tenant_id);
CREATE INDEX IF NOT EXISTS idx_submission_interviews_created_at ON submission_interviews(created_at);
CREATE INDEX IF NOT EXISTS idx_submission_violations_tenant_id ON submission_violations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_submissions_tenant_id ON submissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON submissions(created_at);
CREATE INDEX IF NOT EXISTS idx_system_config_tenant_id ON system_config(tenant_id);
CREATE INDEX IF NOT EXISTS idx_task_capacity_alerts_created_at ON task_capacity_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_task_reassignment_requests_created_at ON task_reassignment_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_tenant_id ON tasks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tenants_created_at ON tenants(created_at);
CREATE INDEX IF NOT EXISTS idx_thunder_sessions_created_at ON thunder_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_ticket_category_routes_created_at ON ticket_category_routes(created_at);
CREATE INDEX IF NOT EXISTS idx_timesheet_anomaly_flags_tenant_id ON timesheet_anomaly_flags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_timesheet_disputes_tenant_id ON timesheet_disputes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_timesheet_disputes_created_at ON timesheet_disputes(created_at);
CREATE INDEX IF NOT EXISTS idx_timesheet_entries_created_at ON timesheet_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_timesheet_nag_logs_tenant_id ON timesheet_nag_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_timesheets_tenant_id ON timesheets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_timesheets_created_at ON timesheets(created_at);
CREATE INDEX IF NOT EXISTS idx_user_roles_created_at ON user_roles(created_at);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);

-- ============================================
-- SCHEMA GENERATION COMPLETE
-- Total tables: 168
-- ============================================
