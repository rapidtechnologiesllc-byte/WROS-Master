#!/usr/bin/env python3
from sqlalchemy import text
from app.core.database import engine

create_tables_sql = """
-- Career Jobs
CREATE TABLE IF NOT EXISTS career_jobs (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id INTEGER NULL,
    opportunity_id VARCHAR(36) NULL,
    demand_id VARCHAR(36) NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    skills_required JSONB NULL,
    experience_years_required INTEGER NULL,
    location VARCHAR(200) NULL,
    salary_range_min_usd_cents INTEGER NULL,
    salary_range_max_usd_cents INTEGER NULL,
    is_published BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP NULL,
    closed_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS ix_career_jobs_tenant_id ON career_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS ix_career_jobs_is_published ON career_jobs(is_published);
CREATE INDEX IF NOT EXISTS ix_career_jobs_is_active ON career_jobs(is_active);
CREATE INDEX IF NOT EXISTS ix_career_jobs_title ON career_jobs(title);

-- Career Applications
CREATE TABLE IF NOT EXISTS career_applications (
    id VARCHAR(36) PRIMARY KEY,
    career_job_id VARCHAR(36) NOT NULL REFERENCES career_jobs(id),
    candidate_email VARCHAR(300) NOT NULL,
    candidate_name VARCHAR(200) NULL,
    candidate_phone VARCHAR(50) NULL,
    resume_file_path VARCHAR(500) NULL,
    resume_text TEXT NULL,
    resume_uploaded_at TIMESTAMP NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_career_applications_job_id ON career_applications(career_job_id);
CREATE INDEX IF NOT EXISTS ix_career_applications_email ON career_applications(candidate_email);
CREATE INDEX IF NOT EXISTS ix_career_applications_status ON career_applications(status);

-- Career Resume Analysis
CREATE TABLE IF NOT EXISTS career_resume_analysis (
    id VARCHAR(36) PRIMARY KEY,
    career_application_id VARCHAR(36) NOT NULL REFERENCES career_applications(id),
    career_job_id VARCHAR(36) NOT NULL REFERENCES career_jobs(id),
    overall_fit_score FLOAT NULL,
    skills_matched JSONB NULL,
    experience_gap JSONB NULL,
    ai_assessment TEXT NULL,
    gaps_identified JSONB NULL,
    has_critical_gaps BOOLEAN DEFAULT FALSE,
    tags JSONB DEFAULT '[]'::jsonb,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_career_resume_analysis_app_id ON career_resume_analysis(career_application_id);
CREATE INDEX IF NOT EXISTS ix_career_resume_analysis_job_id ON career_resume_analysis(career_job_id);

-- Career Conversations
CREATE TABLE IF NOT EXISTS career_conversations (
    id VARCHAR(36) PRIMARY KEY,
    career_application_id VARCHAR(36) NULL REFERENCES career_applications(id),
    candidate_email VARCHAR(300) NOT NULL,
    question_index INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    candidate_response TEXT NULL,
    conversation_summary JSONB NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_career_conversations_app_id ON career_conversations(career_application_id);
CREATE INDEX IF NOT EXISTS ix_career_conversations_email ON career_conversations(candidate_email);

-- Career Clarifications
CREATE TABLE IF NOT EXISTS career_clarifications (
    id VARCHAR(36) PRIMARY KEY,
    career_application_id VARCHAR(36) NOT NULL REFERENCES career_applications(id),
    career_resume_analysis_id VARCHAR(36) NOT NULL REFERENCES career_resume_analysis(id),
    gap_type VARCHAR(100) NOT NULL,
    gap_description TEXT NULL,
    ai_question TEXT NOT NULL,
    suggested_answers JSONB NULL,
    candidate_response TEXT NULL,
    response_received_at TIMESTAMP NULL,
    response_assessment TEXT NULL,
    satisfies_gap BOOLEAN NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    answered_at TIMESTAMP NULL,
    assessed_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS ix_career_clarifications_app_id ON career_clarifications(career_application_id);
CREATE INDEX IF NOT EXISTS ix_career_clarifications_analysis_id ON career_clarifications(career_resume_analysis_id);
CREATE INDEX IF NOT EXISTS ix_career_clarifications_status ON career_clarifications(status);
"""

try:
    with engine.connect() as conn:
        conn.execute(text(create_tables_sql))
        conn.commit()
    print("Career tables created successfully")
except Exception as e:
    print(f"Error: {e}")
