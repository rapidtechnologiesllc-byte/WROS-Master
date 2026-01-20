# Database Schema Documentation

## Overview
This document describes the database schema for the Onboarding Module Backend application.

**Database Type**: Microsoft SQL Server (Azure SQL Database compatible)  
**ORM**: SQLAlchemy 2.0+  
**Migration Tool**: Alembic

---

## Tables

### 1. users
System users (HR, Admin, Interviewers)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| UserID | String(50) | PRIMARY KEY, INDEX | Unique user identifier |
| UserRole | String(50) | NOT NULL | User role (HR, Admin, Interviewer) |
| UserName | String(150) | NULLABLE | Full name of user |
| UserEmail | String(200) | UNIQUE, NOT NULL, INDEX | Email address (used for login) |
| UserPassword | String(200) | NOT NULL | Bcrypt hashed password |
| CreatedAt | DateTime | DEFAULT now() | Account creation timestamp |

**Indexes**: UserID (PK), UserEmail (UNIQUE)

---

### 2. candidates
Candidate information

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| candidateID | String(50) | PRIMARY KEY, INDEX | Unique candidate identifier |
| candidateRole | String(50) | DEFAULT 'Candidate' | Role designation |
| candidateFirstName | String(150) | NULLABLE | First name |
| candidateMiddleName | String(150) | NULLABLE | Middle name |
| candidateLastName | String(150) | NULLABLE | Last name |
| candidateEmail | String(200) | UNIQUE, NOT NULL, INDEX | Email address |
| candidateMobile | String(20) | NULLABLE | Mobile number |
| candidateGender | String(10) | NULLABLE | Gender |
| candidateDateOfBirth | Date | NULLABLE | Date of birth |
| candidateSource | String(50) | NULLABLE | Recruitment source |
| candidateExperience | String(50) | NULLABLE | Years of experience |
| candidateSkills | Text | NULLABLE | Comma-separated skills |
| candidateJoiningDate | Date | NULLABLE | Expected/actual joining date |
| candidateExpectedSalary | String(50) | NULLABLE | Expected salary |
| candidateCurrentSalary | String(50) | NULLABLE | Current salary |
| candidateCurrentLocation | String(200) | NULLABLE | Current location |
| candidatePassword | String(200) | NOT NULL | Bcrypt hashed password |
| candidateIsVerified | Boolean | NULLABLE | Email verification status |
| candidateCreatedAt | DateTime | DEFAULT now() | Registration timestamp |

**Indexes**: candidateID (PK), candidateEmail (UNIQUE)

---

### 3. candidate_assignments
Assignment of candidates to managers

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTOINCREMENT | Assignment ID |
| candidate_id | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| hiring_manager_id | String(50) | FOREIGN KEY → users.UserID | Hiring manager |
| reporting_manager_id | String(50) | FOREIGN KEY → users.UserID | Reporting manager |
| created_at | DateTime | DEFAULT now() | Assignment timestamp |

**Foreign Keys**:
- candidate_id → candidates.candidateID
- hiring_manager_id → users.UserID
- reporting_manager_id → users.UserID

---

### 4. interview_panels
Interview panel configuration

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTOINCREMENT | Panel ID |
| candidate_id | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| round_name | String(50) | | Round name (HR, Tech, Manager) |
| created_at | DateTime | DEFAULT now() | Panel creation timestamp |

**Foreign Keys**:
- candidate_id → candidates.candidateID

---

### 5. panel_members
Interviewers assigned to panels

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTOINCREMENT | Member ID |
| panel_id | Integer | FOREIGN KEY → interview_panels.id | Panel reference |
| interviewer_id | String(50) | FOREIGN KEY → users.UserID | Interviewer reference |

**Foreign Keys**:
- panel_id → interview_panels.id
- interviewer_id → users.UserID

---

### 6. interviews
Scheduled interviews

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTOINCREMENT | Interview ID |
| panel_id | Integer | FOREIGN KEY → interview_panels.id | Panel reference |
| candidate_id | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| start_time | DateTime | | Interview start time |
| end_time | DateTime | | Interview end time |
| meeting_link | Text | | Online meeting link |
| outlook_event_id | Text | | Outlook calendar event ID |
| status | String(50) | | Status (Scheduled, Completed, Cancelled) |

**Foreign Keys**:
- panel_id → interview_panels.id
- candidate_id → candidates.candidateID

---

### 7. interview_feedback
Feedback from interviewers

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PRIMARY KEY, AUTOINCREMENT | Feedback ID |
| interview_id | Integer | FOREIGN KEY → interviews.id | Interview reference |
| interviewer_id | String(50) | FOREIGN KEY → users.UserID | Interviewer reference |
| technical_score | Integer | | Technical skills score (1-10) |
| communication_score | Integer | | Communication score (1-10) |
| problem_solving_score | Integer | | Problem solving score (1-10) |
| culture_fit_score | Integer | | Culture fit score (1-10) |
| comments | Text | | Detailed feedback comments |
| recommendation | String(20) | | Recommendation (Hire/Hold/Reject) |
| submitted_at | DateTime | DEFAULT now() | Feedback submission time |

**Foreign Keys**:
- interview_id → interviews.id
- interviewer_id → users.UserID

---

### 8. candidate_forms
Candidate personal information form

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| formID | Integer | PRIMARY KEY, AUTOINCREMENT | Form ID |
| candidateID | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| position | String(255) | NULLABLE | Applied position |
| department | String(100) | NULLABLE | Department |
| dob | Date | NULLABLE | Date of birth |
| gender | String(10) | NULLABLE | Gender |
| marital_status | String(10) | NULLABLE | Marital status |
| nationality | String(10) | NULLABLE | Nationality |
| current_address | Text | NULLABLE | Current address |
| permanent_address | Text | NULLABLE | Permanent address |
| submittedAt | Date | NULLABLE | Submission date |
| formCreatedAt | DateTime | DEFAULT now() | Form creation time |
| formUpdatedAt | DateTime | DEFAULT now(), ON UPDATE now() | Last update time |

**Foreign Keys**:
- candidateID → candidates.candidateID

---

### 9. candidate_education_forms
Candidate education details

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| formID | Integer | PRIMARY KEY, AUTOINCREMENT | Form ID |
| candidateID | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| education_institute | String(255) | NULLABLE | Institute name |
| degree | String(255) | NULLABLE | Degree name |
| field_of_study | String(255) | NULLABLE | Field of study |
| starting_year | String(4) | NULLABLE | Start year |
| year_of_passing | String(4) | NULLABLE | Passing year |
| percentage | String(10) | NULLABLE | Percentage/CGPA |
| submittedAt | Date | NULLABLE | Submission date |
| document_is_submitted | Boolean | NULLABLE | Document submission status |
| formCreatedAt | DateTime | DEFAULT now() | Form creation time |
| formUpdatedAt | DateTime | DEFAULT now(), ON UPDATE now() | Last update time |

**Foreign Keys**:
- candidateID → candidates.candidateID

---

### 10. candidate_experience_forms
Candidate work experience

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| formID | Integer | PRIMARY KEY, AUTOINCREMENT | Form ID |
| candidateID | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| company_name | String(255) | NULLABLE | Company name |
| job_title | String(255) | NULLABLE | Job title |
| start_date | Date | NULLABLE | Employment start date |
| end_date | Date | NULLABLE | Employment end date |
| year_of_experience | String(4) | NULLABLE | Years of experience |
| document_is_submitted | Boolean | NULLABLE | Document submission status |
| submittedAt | Date | NULLABLE | Submission date |
| formCreatedAt | DateTime | DEFAULT now() | Form creation time |
| formUpdatedAt | DateTime | DEFAULT now(), ON UPDATE now() | Last update time |

**Foreign Keys**:
- candidateID → candidates.candidateID

---

### 11. candidate_aadhar_forms
Candidate Aadhar verification

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| formID | Integer | PRIMARY KEY, AUTOINCREMENT | Form ID |
| candidateID | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| aadhar | String(12) | NULLABLE | Aadhar number |
| name_in_aadhar | String(100) | NULLABLE | Name as per Aadhar |
| enrollment_number | String(20) | NULLABLE | Enrollment number |
| aadhar_is_submitted | Boolean | NULLABLE | Aadhar submission status |
| submittedAt | Date | NULLABLE | Submission date |
| is_verified | Boolean | NULLABLE | Verification status |
| formCreatedAt | DateTime | DEFAULT now() | Form creation time |
| formUpdatedAt | DateTime | DEFAULT now(), ON UPDATE now() | Last update time |

**Foreign Keys**:
- candidateID → candidates.candidateID

---

### 12. candidate_pan_forms
Candidate PAN verification

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| formID | Integer | PRIMARY KEY, AUTOINCREMENT | Form ID |
| candidateID | String(50) | FOREIGN KEY → candidates.candidateID | Candidate reference |
| pan | String(10) | NULLABLE | PAN number |
| name_in_pan | String(100) | NULLABLE | Name as per PAN |
| father_name_in_pan | String(100) | NULLABLE | Father's name as per PAN |
| pan_is_submitted | Boolean | NULLABLE | PAN submission status |
| submittedAt | Date | NULLABLE | Submission date |
| is_verified | Boolean | NULLABLE | Verification status |
| formCreatedAt | DateTime | DEFAULT now() | Form creation time |
| formUpdatedAt | DateTime | DEFAULT now(), ON UPDATE now() | Last update time |

**Foreign Keys**:
- candidateID → candidates.candidateID

---

## Database Relationships

```
users (1) ----< (N) candidate_assignments (hiring_manager)
users (1) ----< (N) candidate_assignments (reporting_manager)
users (1) ----< (N) panel_members
users (1) ----< (N) interview_feedback

candidates (1) ----< (N) candidate_assignments
candidates (1) ----< (N) interview_panels
candidates (1) ----< (N) interviews
candidates (1) ----< (N) candidate_forms
candidates (1) ----< (N) candidate_education_forms
candidates (1) ----< (N) candidate_experience_forms
candidates (1) ----< (N) candidate_aadhar_forms
candidates (1) ----< (N) candidate_pan_forms

interview_panels (1) ----< (N) panel_members
interview_panels (1) ----< (N) interviews

interviews (1) ----< (N) interview_feedback
```

---

## Initial Data Requirements

### Required Initial Users
At least one admin user should be created:

```sql
INSERT INTO users (UserID, UserRole, UserName, UserEmail, UserPassword, CreatedAt)
VALUES (
    'admin-001',
    'Admin',
    'System Administrator',
    'admin@company.com',
    '$2b$12$...',  -- Bcrypt hash of password
    GETDATE()
);
```

### Password Hashing
All passwords must be hashed using bcrypt with cost factor 12:

```python
import bcrypt
password = "your-password"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
```

---

## Database Maintenance

### Recommended Indexes
The following indexes are automatically created by SQLAlchemy:
- Primary keys on all tables
- Unique indexes on email fields
- Foreign key indexes

### Backup Strategy
- **Daily**: Automated backups (Azure SQL Database default)
- **Retention**: 7-35 days (configurable)
- **Point-in-time restore**: Available for last 7-35 days

### Performance Optimization
- Connection pooling configured (pool_size=5, max_overflow=10)
- Prepared statements used via SQLAlchemy ORM
- Indexes on frequently queried columns (email, IDs)

---

## Migration Commands

```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current version
alembic current
```

---

**Last Updated**: 2026-01-19
