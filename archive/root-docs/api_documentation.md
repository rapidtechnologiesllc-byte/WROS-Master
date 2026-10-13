# Onboarding Module API Documentation

This document lists all the registered **API v1 endpoints**, their paths, HTTP methods, and functionality descriptions.

## Table of Contents

- [Ats Endpoints](#ats-endpoints)
- [Auth Endpoints](#auth-endpoints)
- [Candidate History Endpoints](#candidate-history-endpoints)
- [Candidate Ownership Endpoints](#candidate-ownership-endpoints)
- [Candidate Status Endpoints](#candidate-status-endpoints)
- [Candidates Endpoints](#candidates-endpoints)
- [Checklists Endpoints](#checklists-endpoints)
- [Create Job Endpoints](#create-job-endpoints)
- [Email Endpoints](#email-endpoints)
- [Internal Endpoints](#internal-endpoints)
- [Interviews Endpoints](#interviews-endpoints)
- [Msgraph Endpoints](#msgraph-endpoints)
- [Newsletter Endpoints](#newsletter-endpoints)
- [Offer Letters Endpoints](#offer-letters-endpoints)
- [Onboarding Endpoints](#onboarding-endpoints)
- [Preonboarding Endpoints](#preonboarding-endpoints)
- [Rbac Endpoints](#rbac-endpoints)
- [Users Endpoints](#users-endpoints)

---

## Ats Endpoints
**Source File**: `app/api/v1/endpoints/ats.py`  
**Base Prefix**: `/api/v1/ats`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/ats/scores/all` | List all ATS scores across every job and candidate | `list_all_ats_scores()` |
| `GET` | `/api/v1/ats/scores/job/{job_id}` | ATS scores for all applicants on a specific job | `list_scores_for_job()` |
| `GET` | `/api/v1/ats/scores/candidate/{candidate_id}` | All ATS scores recorded for a specific candidate | `list_scores_for_candidate()` |
| `GET` | `/api/v1/ats/scores/{score_id}` | Full ATS score detail for a single record | `get_ats_score()` |

### Detailed Functionality

#### `GET` /api/v1/ats/scores/all

**Summary**: List all ATS scores across every job and candidate

*No detailed description available.*

#### `GET` /api/v1/ats/scores/job/{job_id}

**Summary**: ATS scores for all applicants on a specific job

*No detailed description available.*

#### `GET` /api/v1/ats/scores/candidate/{candidate_id}

**Summary**: All ATS scores recorded for a specific candidate

*No detailed description available.*

#### `GET` /api/v1/ats/scores/{score_id}

**Summary**: Full ATS score detail for a single record

*No detailed description available.*


---

## Auth Endpoints
**Source File**: `app/api/v1/endpoints/auth.py`  
**Base Prefix**: `/api/v1/auth`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/v1/signup` | Create a new user account | `signup()` |
| `POST` | `/api/v1/auth/login` | Unified login endpoint. | `unified_login()` |

### Detailed Functionality

#### `POST` /api/v1/auth/v1/signup

**Summary**: Create a new user account

```text
Create a new user account

Args:
    request: SignupRequest containing user details
    db: Database session
    
Returns:
    SignupResponse with success message
    
Raises:
    HTTPException: If user with email already exists
```

#### `POST` /api/v1/auth/login

**Summary**: Unified login endpoint.

```text
Unified login endpoint.

Accepts a single email + password and automatically determines whether
the credentials belong to a **User** (HR / Admin / etc.) or a **Candidate**.
The response includes an `entity_type` field ("user" or "candidate") so
the frontend can route accordingly.

Raises:
    HTTPException 401: If credentials do not match any user or candidate.
```


---

## Candidate History Endpoints
**Source File**: `app/api/v1/endpoints/candidate_history.py`  
**Base Prefix**: `/api/v1/history`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/history/{candidate_id}` | Log a new timeline event for a candidate | `create_candidate_history()` |
| `GET` | `/api/v1/history/{candidate_id}` | Get the full history / timeline for a candidate | `get_candidate_history()` |
| `GET` | `/api/v1/history/{candidate_id}/latest` | Get the N most recent history events for a candidate | `get_latest_candidate_history()` |

### Detailed Functionality

#### `POST` /api/v1/history/{candidate_id}

**Summary**: Log a new timeline event for a candidate

```text
Record a new event in the candidate's history / timeline.

**event_type** must be one of:
- `Applied` — candidate applied for a job
- `Screening` — HR screened the candidate
- `Interview Scheduled` — interview has been scheduled
- `Interview Completed` — interview was conducted
- `Offer Released` — offer letter was generated & sent
- `Offer Accepted` — candidate accepted the offer
- `Offer Rejected` — candidate rejected the offer
- `Pre-Onboarding` — pre-onboarding tasks started
- `Onboarded` — candidate has joined
- `Rejected` — candidate was rejected at any stage
- `Custom` — any other freeform event (describe it in `note`)

The `performed_by_id` / `performed_by_name` default to the calling user's
details if not explicitly supplied in the request body.
```

#### `GET` /api/v1/history/{candidate_id}

**Summary**: Get the full history / timeline for a candidate

```text
Returns the chronological timeline of events for a single candidate,
ordered newest-first.

**Optional query parameters:**
- `event_type` — filter to a specific event type
- `skip` / `limit` — standard pagination
```

#### `GET` /api/v1/history/{candidate_id}/latest

**Summary**: Get the N most recent history events for a candidate

```text
Convenience endpoint — returns the `n` most recent timeline events for a
candidate. Useful for dashboards that show a summary card.
```


---

## Candidate Ownership Endpoints
**Source File**: `app/api/v1/endpoints/candidate_ownership.py`  
**Base Prefix**: `/api/v1/candidate-pool`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/candidate-pool/` | List all candidates with their pool ownership status | `list_candidate_pool()` |
| `GET` | `/api/v1/candidate-pool/{candidate_id}` | Get pool ownership status for a specific candidate | `get_candidate_pool_status()` |
| `POST` | `/api/v1/candidate-pool/{candidate_id}/override` | Manually override candidate pool ownership (HR Admin) | `override_candidate_pool()` |

### Detailed Functionality

#### `GET` /api/v1/candidate-pool/

**Summary**: List all candidates with their pool ownership status

```text
Returns every candidate with their current pool ownership state.

**Filters:**
- `pool_status` — `'Org Pool'` or `'BU Owned'`
- `bu_id` — only show candidates owned by this specific Business Unit

Candidates who have **never been assigned** to any BU are implicitly in the
Org Pool (they may not have a `candidate_ownership` row yet).
```

#### `GET` /api/v1/candidate-pool/{candidate_id}

**Summary**: Get pool ownership status for a specific candidate

```text
Returns the current pool ownership state for a single candidate.

If the candidate has no ownership record (i.e. never been assigned to a BU),
they are implicitly in the **Org Pool**.
```

#### `POST` /api/v1/candidate-pool/{candidate_id}/override

**Summary**: Manually override candidate pool ownership (HR Admin)

```text
Manually change the pool ownership state for a candidate.

- Setting `pool_status = 'BU Owned'` requires a valid `bu_id`.
- Setting `pool_status = 'Org Pool'` clears all BU ownership data.
- Every override is logged to the candidate history audit trail.

**Required permission:** `candidate.edit`
```


---

## Candidate Status Endpoints
**Source File**: `app/api/v1/endpoints/candidate_status.py`  
**Base Prefix**: `/api/v1/status`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `PUT` | `/api/v1/status/{candidate_id}` | Update candidate account status and/or pipeline status | `update_candidate_status()` |
| `GET` | `/api/v1/status/all` | Get status summary for all candidates | `get_all_candidate_statuses()` |
| `GET` | `/api/v1/status/{candidate_id}` | Get status for a specific candidate | `get_candidate_status()` |

### Detailed Functionality

#### `PUT` /api/v1/status/{candidate_id}

**Summary**: Update candidate account status and/or pipeline status

```text
Update the `status` (Active / Inactive) and/or `pipeline_status`
(Applied → Screening → Interview → Pre-Boarding → Onboarded / Rejected)
for a candidate.

At least one of `status` or `pipeline_status` must be provided.
Both fields are optional in a single call — send only what you want to change.
```

#### `GET` /api/v1/status/all

**Summary**: Get status summary for all candidates

```text
Returns account status and pipeline status for every candidate.
Useful for pipeline dashboards and bulk status views.

**Optional filters (query params):**
- `status` — filter by account status (`Active` | `Inactive`)
- `pipeline_status` — filter by pipeline stage
  (`Applied` | `Screening` | `Interview` | `Pre-Onboarding` | `Onboarded` | `Hired` | `Rejected`)

Both filters are independent and can be combined.
```

#### `GET` /api/v1/status/{candidate_id}

**Summary**: Get status for a specific candidate

```text
Returns the current account status and pipeline status for a single candidate.
```


---

## Candidates Endpoints
**Source File**: `app/api/v1/endpoints/candidates.py`  
**Base Prefix**: `/api/v1/candidate`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/candidate/change_password` | Change candidate password after first login. | `change_password()` |
| `GET` | `/api/v1/candidate/my-info` | Get complete information for the authenticated candidate. | `get_my_info()` |
| `POST` | `/api/v1/candidate/candidate-form/` | Create or update candidate information form. | `candidate_info()` |
| `POST` | `/api/v1/candidate/education-form/` | Create or update candidate education forms (supports multiple records). | `candidate_education()` |
| `POST` | `/api/v1/candidate/experience-form/` | Create or update candidate experience forms (supports multiple records). | `candidate_experience()` |
| `POST` | `/api/v1/candidate/aadhar-form/` | Create or update candidate Aadhar form. | `candidate_aadhar()` |
| `POST` | `/api/v1/candidate/pan-form/` | Create or update candidate PAN form. | `candidate_pan()` |
| `POST` | `/api/v1/candidate/education/add` | Add a single education record for the authenticated candidate. | `add_education_record()` |
| `PUT` | `/api/v1/candidate/education/{education_id}` | Update a specific education record by ID. | `update_education_record()` |
| `DELETE` | `/api/v1/candidate/education/{education_id}` | Delete a specific education record by ID. | `delete_education_record()` |
| `GET` | `/api/v1/candidate/education/list` | Get all education records for the authenticated candidate with IDs. | `list_education_records()` |
| `POST` | `/api/v1/candidate/experience/add` | Add a single experience record for the authenticated candidate. | `add_experience_record()` |
| `PUT` | `/api/v1/candidate/experience/{experience_id}` | Update a specific experience record by ID. | `update_experience_record()` |
| `DELETE` | `/api/v1/candidate/experience/{experience_id}` | Delete a specific experience record by ID. | `delete_experience_record()` |
| `GET` | `/api/v1/candidate/experience/list` | Get all experience records for the authenticated candidate with IDs. | `list_experience_records()` |
| `GET` | `/api/v1/candidate/personal-info` | Get only the personal info form for the authenticated candidate. | `get_personal_info()` |
| `GET` | `/api/v1/candidate/aadhar` | Get only the Aadhar form for the authenticated candidate. | `get_aadhar_info()` |
| `GET` | `/api/v1/candidate/pan` | Get only the PAN form for the authenticated candidate. | `get_pan_info()` |
| `GET` | `/api/v1/candidate/onboarding-status` | Get onboarding completion status for the authenticated candidate. | `get_onboarding_status()` |

### Detailed Functionality

#### `POST` /api/v1/candidate/change_password

**Summary**: Change candidate password after first login.

```text
Change candidate password after first login.

Args:
    request: ChangePasswordRequest containing candidate_id, old_password, new_password, confirm_password
    db: Database session
    
Returns:
    ChangePasswordResponse with status and message
    
Raises:
    HTTPException: If candidate not found, old password incorrect, or validation fails
```

#### `GET` /api/v1/candidate/my-info

**Summary**: Get complete information for the authenticated candidate.

```text
Get complete information for the authenticated candidate.

Args:
    db: Database session
    user: Authenticated candidate user
    
Returns:
    CandidateCompleteResponse with all candidate information including:
    - Personal info (name, email, mobile, etc.)
    - Candidate info form (position, department, dob, etc.)
    - Education records
    - Experience records
    - Aadhar details
    - PAN details
    
Raises:
    HTTPException: If candidate not found
```

#### `POST` /api/v1/candidate/candidate-form/

**Summary**: Create or update candidate information form.

```text
Create or update candidate information form.

Args:
    request: candidateFormRequest containing candidate form details
    db: Database session
    
Returns:
    candidateFormResponse with status and message
    
Raises:
    HTTPException: If candidate not found or validation fails
```

#### `POST` /api/v1/candidate/education-form/

**Summary**: Create or update candidate education forms (supports multiple records).

```text
Create or update candidate education forms (supports multiple records).

Args:
    request: CandidateEducationForm containing candidate_id and list of education records
    db: Database session
    
Returns:
    candidateFormResponse with status and message
    
Raises:
    HTTPException: If candidate not found, empty list, or validation fails
```

#### `POST` /api/v1/candidate/experience-form/

**Summary**: Create or update candidate experience forms (supports multiple records).

```text
Create or update candidate experience forms (supports multiple records).

Args:
    request: CandidateExperienceForm containing candidate_id and list of experience records
    db: Database session
    
Returns:
    candidateFormResponse with status and message
    
Raises:
    HTTPException: If candidate not found, empty list, or validation fails
```

#### `POST` /api/v1/candidate/aadhar-form/

**Summary**: Create or update candidate Aadhar form.

```text
Create or update candidate Aadhar form.

Args:
    request: CandidateAadharForm containing Aadhar details
    db: Database session
    user: Authenticated candidate user
    
Returns:
    candidateFormResponse with status and message
    
Raises:
    HTTPException: If candidate not found or validation fails
```

#### `POST` /api/v1/candidate/pan-form/

**Summary**: Create or update candidate PAN form.

```text
Create or update candidate PAN form.

Args:
    request: CandidatePanForm containing PAN details
    db: Database session
    user: Authenticated candidate user
    
Returns:
    candidateFormResponse with status and message
    
Raises:
    HTTPException: If candidate not found or validation fails
```

#### `POST` /api/v1/candidate/education/add

**Summary**: Add a single education record for the authenticated candidate.

```text
Add a single education record for the authenticated candidate.

Args:
    request: EducationRecord containing education details
    db: Database session
    user: Authenticated candidate
    
Returns:
    candidateFormResponse with success message
```

#### `PUT` /api/v1/candidate/education/{education_id}

**Summary**: Update a specific education record by ID.

```text
Update a specific education record by ID.

Args:
    education_id: ID of the education record to update
    request: EducationRecord with updated details
    db: Database session
    user: Authenticated candidate
    
Returns:
    candidateFormResponse with success message
    
Raises:
    HTTPException: If record not found or doesn't belong to candidate
```

#### `DELETE` /api/v1/candidate/education/{education_id}

**Summary**: Delete a specific education record by ID.

```text
Delete a specific education record by ID.

Args:
    education_id: ID of the education record to delete
    db: Database session
    user: Authenticated candidate
    
Returns:
    candidateFormResponse with success message
    
Raises:
    HTTPException: If record not found or doesn't belong to candidate
```

#### `GET` /api/v1/candidate/education/list

**Summary**: Get all education records for the authenticated candidate with IDs.

```text
Get all education records for the authenticated candidate with IDs.

Returns:
    List of education records with formID included
```

#### `POST` /api/v1/candidate/experience/add

**Summary**: Add a single experience record for the authenticated candidate.

```text
Add a single experience record for the authenticated candidate.

Args:
    request: ExperienceRecord containing experience details
    db: Database session
    user: Authenticated candidate
    
Returns:
    candidateFormResponse with success message
```

#### `PUT` /api/v1/candidate/experience/{experience_id}

**Summary**: Update a specific experience record by ID.

```text
Update a specific experience record by ID.

Args:
    experience_id: ID of the experience record to update
    request: ExperienceRecord with updated details
    db: Database session
    user: Authenticated candidate
    
Returns:
    candidateFormResponse with success message
    
Raises:
    HTTPException: If record not found or doesn't belong to candidate
```

#### `DELETE` /api/v1/candidate/experience/{experience_id}

**Summary**: Delete a specific experience record by ID.

```text
Delete a specific experience record by ID.

Args:
    experience_id: ID of the experience record to delete
    db: Database session
    user: Authenticated candidate
    
Returns:
    candidateFormResponse with success message
    
Raises:
    HTTPException: If record not found or doesn't belong to candidate
```

#### `GET` /api/v1/candidate/experience/list

**Summary**: Get all experience records for the authenticated candidate with IDs.

```text
Get all experience records for the authenticated candidate with IDs.

Returns:
    List of experience records with formID included
```

#### `GET` /api/v1/candidate/personal-info

**Summary**: Get only the personal info form for the authenticated candidate.

```text
Get only the personal info form for the authenticated candidate.

Returns:
    CandidateInfoResponse with personal information
    
Raises:
    HTTPException: If personal info not found
```

#### `GET` /api/v1/candidate/aadhar

**Summary**: Get only the Aadhar form for the authenticated candidate.

```text
Get only the Aadhar form for the authenticated candidate.

Returns:
    CandidateAadharResponse with Aadhar information
    
Raises:
    HTTPException: If Aadhar info not found
```

#### `GET` /api/v1/candidate/pan

**Summary**: Get only the PAN form for the authenticated candidate.

```text
Get only the PAN form for the authenticated candidate.

Returns:
    CandidatePanResponse with PAN information
    
Raises:
    HTTPException: If PAN info not found
```

#### `GET` /api/v1/candidate/onboarding-status

**Summary**: Get onboarding completion status for the authenticated candidate.

```text
Get onboarding completion status for the authenticated candidate.

Returns:
    Detailed status including completion percentage and form-wise status
```


---

## Checklists Endpoints
**Source File**: `app/api/v1/endpoints/checklists.py`  
**Base Prefix**: `/api/v1/checklist`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/checklist/hr/templates` | Create a new checklist template | `create_template()` |
| `GET` | `/api/v1/checklist/hr/templates` | List all checklist templates | `list_templates()` |
| `GET` | `/api/v1/checklist/hr/templates/{template_id}` | Get a single template with all its items | `get_template()` |
| `PUT` | `/api/v1/checklist/hr/templates/{template_id}` | Update template name / description | `update_template()` |
| `DELETE` | `/api/v1/checklist/hr/templates/{template_id}` | Delete a template (cascade deletes its items) | `delete_template()` |
| `POST` | `/api/v1/checklist/hr/templates/{template_id}/items` | Add an item to a checklist template | `add_template_item()` |
| `PUT` | `/api/v1/checklist/hr/templates/{template_id}/items/{item_id}` | Update a template item | `update_template_item()` |
| `DELETE` | `/api/v1/checklist/hr/templates/{template_id}/items/{item_id}` | Delete a template item | `delete_template_item()` |
| `POST` | `/api/v1/checklist/hr/assign` | Assign a checklist template to a candidate | `assign_checklist()` |
| `GET` | `/api/v1/checklist/hr/candidate/{candidate_id}` | View all checklists for a specific candidate | `get_candidate_checklists()` |
| `PUT` | `/api/v1/checklist/hr/candidate-item/{item_id}/complete` | HR manually marks a checklist item as complete | `hr_complete_item()` |
| `GET` | `/api/v1/checklist/candidate/my-checklists` | Get the authenticated candidate's checklists | `get_my_checklists()` |
| `PUT` | `/api/v1/checklist/candidate/item/{item_id}/complete` | Candidate marks a checklist item as complete | `candidate_complete_item()` |

### Detailed Functionality

#### `POST` /api/v1/checklist/hr/templates

**Summary**: Create a new checklist template

```text
Create a reusable checklist template, optionally with initial items.
```

#### `GET` /api/v1/checklist/hr/templates

**Summary**: List all checklist templates

*No detailed description available.*

#### `GET` /api/v1/checklist/hr/templates/{template_id}

**Summary**: Get a single template with all its items

*No detailed description available.*

#### `PUT` /api/v1/checklist/hr/templates/{template_id}

**Summary**: Update template name / description

*No detailed description available.*

#### `DELETE` /api/v1/checklist/hr/templates/{template_id}

**Summary**: Delete a template (cascade deletes its items)

*No detailed description available.*

#### `POST` /api/v1/checklist/hr/templates/{template_id}/items

**Summary**: Add an item to a checklist template

*No detailed description available.*

#### `PUT` /api/v1/checklist/hr/templates/{template_id}/items/{item_id}

**Summary**: Update a template item

*No detailed description available.*

#### `DELETE` /api/v1/checklist/hr/templates/{template_id}/items/{item_id}

**Summary**: Delete a template item

*No detailed description available.*

#### `POST` /api/v1/checklist/hr/assign

**Summary**: Assign a checklist template to a candidate

```text
Copies all items from the template into a new CandidateChecklist.
- Todo items start as 'pending' (candidate can complete anytime).
- Queue items: only the first (lowest order_index) becomes 'active';
  all others remain 'pending' until triggered by the previous completion.
```

#### `GET` /api/v1/checklist/hr/candidate/{candidate_id}

**Summary**: View all checklists for a specific candidate

*No detailed description available.*

#### `PUT` /api/v1/checklist/hr/candidate-item/{item_id}/complete

**Summary**: HR manually marks a checklist item as complete

```text
HR can mark any todo or active queue item complete on behalf of a candidate.
Queue items automatically activate the next queue item.
```

#### `GET` /api/v1/checklist/candidate/my-checklists

**Summary**: Get the authenticated candidate's checklists

*No detailed description available.*

#### `PUT` /api/v1/checklist/candidate/item/{item_id}/complete

**Summary**: Candidate marks a checklist item as complete

```text
Candidate can complete:
- Any 'todo' item (status 'pending') on their checklist.
- A 'queue' item only if it is the currently 'active' queue item.

On queue-item completion, the next queue item is automatically activated.
```


---

## Create Job Endpoints
**Source File**: `app/api/v1/endpoints/create_job.py`  
**Base Prefix**: `/api/v1/jobs`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/jobs/generate_job_description` | Generate job description using AI. | `generate_job_description()` |
| `GET` | `/api/v1/jobs/all` | Get all jobs from the system. | `get_all_jobs()` |
| `GET` | `/api/v1/jobs/active-jobs` | Get all jobs with status 'active' or 'public'. | `get_active_jobs()` |
| `GET` | `/api/v1/jobs/filter` | Filter jobs by one or more columns. All parameters are optional and combined | `filter_jobs()` |
| `GET` | `/api/v1/jobs/my-jobs` | Get all jobs where the current authenticated user is assigned as: | `get_my_jobs()` |
| `POST` | `/api/v1/jobs/create_job` | Create a new job posting. | `create_job()` |
| `POST` | `/api/v1/jobs/{job_id}/approve` | Approve a pending job posting and make it live. | `approve_job()` |
| `PUT` | `/api/v1/jobs/update_job/{job_id}` | Update an existing job posting. | `update_job()` |
| `DELETE` | `/api/v1/jobs/delete_job/{job_id}` | Delete a job posting. | `delete_job()` |
| `POST` | `/api/v1/jobs/post-on-linkedin` | Post a created job to LinkedIn (Pseudo API - Mock Implementation). | `post_job_on_linkedin()` |
| `PUT` | `/api/v1/jobs/{job_id}/assign-candidate/{candidate_id}` | Assign or re-assign a candidate to a job | `assign_candidate_to_job()` |
| `PUT` | `/api/v1/jobs/unassign-candidate/{candidate_id}` | Remove a candidate's job assignment | `unassign_candidate_from_job()` |
| `GET` | `/api/v1/jobs/{job_id}/candidates` | Get all candidates assigned to a job | `get_candidates_by_job()` |
| `POST` | `/api/v1/jobs/{job_id}/applications/{candidate_id}` | Assign a candidate to a job (multi-job support) | `create_job_application()` |
| `DELETE` | `/api/v1/jobs/{job_id}/applications/{candidate_id}` | Remove a candidate from a job (multi-job) | `remove_job_application()` |
| `PUT` | `/api/v1/jobs/{job_id}/applications/{candidate_id}/status` | Update per-application status | `update_job_application_status()` |
| `GET` | `/api/v1/jobs/{job_id}/applications` | List all candidates assigned to a job (multi-job) | `get_job_applications()` |
| `GET` | `/api/v1/jobs/candidate-applications/{candidate_id}` | List all jobs a candidate is assigned to (multi-job) | `get_candidate_applications()` |
| `GET` | `/api/v1/jobs/{job_id}/statistics` | Get statistics for a job | `get_job_statistics()` |

### Detailed Functionality

#### `POST` /api/v1/jobs/generate_job_description

**Summary**: Generate job description using AI.

```text
Generate job description using AI.

Args:
    request: Job description generation request
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    Job description generation response
```

#### `GET` /api/v1/jobs/all

**Summary**: Get all jobs from the system.

```text
Get all jobs from the system.

Args:
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    AllJobsResponse with list of all jobs and total count
```

#### `GET` /api/v1/jobs/active-jobs

**Summary**: Get all jobs with status 'active' or 'public'.

```text
Get all jobs with status 'active' or 'public'.

Args:
    db: Database session
    user: Authenticated HR/Admin user

Returns:
    AllJobsResponse with list of active/public jobs and total count
```

#### `GET` /api/v1/jobs/filter

**Summary**: Filter jobs by one or more columns. All parameters are optional and combined

```text
Filter jobs by one or more columns. All parameters are optional and combined
with AND logic.

- **business_unit**: business_unit_id (integer)
- **department_id**: department_id (integer)
- **job_status**: e.g. active, pending_approval, draft
- **contact_person**: partial / exact match on contact_person field
- **company_type**: e.g. full time, contract, internship
- **company_name**: partial / exact match on company name
- **job_location**: partial / exact match on job location
```

#### `GET` /api/v1/jobs/my-jobs

**Summary**: Get all jobs where the current authenticated user is assigned as:

```text
Get all jobs where the current authenticated user is assigned as:
- **Recruiter** (`recuriterID`)
- **Hiring Manager** (`hiringManagerID`)
- **Contact Person** (`contactPerson`)

All three roles are checked with OR logic — a job appears once even if
the user matches more than one column.
```

#### `POST` /api/v1/jobs/create_job

**Summary**: Create a new job posting.

```text
Create a new job posting.

Job status is determined by the creator's role — it is NOT taken from the request body.
- Super User / BU Head / Hiring Manager → published immediately (status: active)
- All other roles (HR, HRBP, Recruiter, etc.) → saved as draft (status: pending_approval)

Args:
    request: JobCreateRequest containing job details
    db: Database session
    user: Authenticated HR/Admin user

Returns:
    JobCreateResponse with job_id and message indicating publish or pending state
```

#### `POST` /api/v1/jobs/{job_id}/approve

**Summary**: Approve a pending job posting and make it live.

```text
Approve a pending job posting and make it live.

Only users with the `job.approve` permission (Super User, BU Head) can call this.
Only jobs in `pending_approval` status can be approved.

Args:
    job_id: ID of the job to approve
    db: Database session
    user: Authenticated user with job.approve permission

Returns:
    JobApproveResponse confirming the job is now active

Raises:
    404: Job not found
    400: Job is not in pending_approval status
```

#### `PUT` /api/v1/jobs/update_job/{job_id}

**Summary**: Update an existing job posting.

```text
Update an existing job posting.

Args:
    job_id: ID of the job to update
    request: JobUpdateRequest containing fields to update
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    JobResponse with updated job details
    
Raises:
    HTTPException: If job not found
```

#### `DELETE` /api/v1/jobs/delete_job/{job_id}

**Summary**: Delete a job posting.

```text
Delete a job posting.

Args:
    job_id: ID of the job to delete
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If job not found
```

#### `POST` /api/v1/jobs/post-on-linkedin

**Summary**: Post a created job to LinkedIn (Pseudo API - Mock Implementation).

```text
Post a created job to LinkedIn (Pseudo API - Mock Implementation).

This is a pseudo/mock implementation since LinkedIn API access is not available yet.
It simulates posting a job to LinkedIn and returns a mock response.

Args:
    request: LinkedInPostRequest containing job_id
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    LinkedInPostResponse with status, message, mock LinkedIn post ID, and job details
    
Raises:
    HTTPException: If job not found
```

#### `PUT` /api/v1/jobs/{job_id}/assign-candidate/{candidate_id}

**Summary**: Assign or re-assign a candidate to a job

```text
Link a candidate to the given job (or switch them to a different job).
The operation is idempotent — assigning the same job twice is safe.
To move a candidate to another job, call this endpoint with the new job_id.
Raises 404 if either the job or candidate does not exist.
```

#### `PUT` /api/v1/jobs/unassign-candidate/{candidate_id}

**Summary**: Remove a candidate's job assignment

```text
Unlink a candidate from whichever job they are currently assigned to (sets job_id = NULL).
Raises 404 if the candidate does not exist.
```

#### `GET` /api/v1/jobs/{job_id}/candidates

**Summary**: Get all candidates assigned to a job

```text
Return every candidate whose job_id matches the given job.
Raises 404 if the job does not exist.
```

#### `POST` /api/v1/jobs/{job_id}/applications/{candidate_id}

**Summary**: Assign a candidate to a job (multi-job support)

```text
Assign a candidate to a job using the many-to-many junction table.
A candidate can be assigned to multiple jobs.

- Returns **409** if the candidate is already assigned to this job.
- Returns **404** if the job or candidate does not exist.
```

#### `DELETE` /api/v1/jobs/{job_id}/applications/{candidate_id}

**Summary**: Remove a candidate from a job (multi-job)

```text
Remove the assignment between a candidate and a job (many-to-many).
Returns **404** if the assignment does not exist.
```

#### `PUT` /api/v1/jobs/{job_id}/applications/{candidate_id}/status

**Summary**: Update per-application status

```text
Update the ``application_status`` of a specific candidate ↔ job assignment.
Valid values: ``Applied``, ``Shortlisted``, ``Interview``, ``Offered``, ``Rejected``, ``Hired``.
```

#### `GET` /api/v1/jobs/{job_id}/applications

**Summary**: List all candidates assigned to a job (multi-job)

```text
Return all candidates linked to this job via the many-to-many table.
Optionally filter by ``application_status``.
```

#### `GET` /api/v1/jobs/candidate-applications/{candidate_id}

**Summary**: List all jobs a candidate is assigned to (multi-job)

```text
Return every job a candidate is linked to via the many-to-many table.
```

#### `GET` /api/v1/jobs/{job_id}/statistics

**Summary**: Get statistics for a job

```text
Return aggregated application statistics for a specific job.

**Includes:**
- `total_applications` — total candidates assigned via the multi-job table
- `applied`, `shortlisted`, `interview`, `offered`, `hired`, `rejected` — named counts
- `status_breakdown` — full list of every status with its count (covers custom statuses)

Returns **404** if the job does not exist.
```


---

## Email Endpoints
**Source File**: `app/api/v1/endpoints/email.py`  
**Base Prefix**: `/api/v1/email`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/email/send` | Send a plain or HTML email from the HRMS service mailbox | `send_mail()` |
| `POST` | `/api/v1/email/notify` | Send a styled HRMS notification email | `send_notification()` |
| `POST` | `/api/v1/email/interview/invite/{interview_id}` | Send interview invite for an existing scheduled interview | `send_interview_invite_by_id()` |
| `POST` | `/api/v1/email/interview/invite/custom` | Send a custom ad-hoc interview invite (no interview_id needed) | `send_custom_interview_invite()` |

### Detailed Functionality

#### `POST` /api/v1/email/send

**Summary**: Send a plain or HTML email from the HRMS service mailbox

```text
Send an email from **helpdesk_hrms@blitzenx.com** to any recipient.
Supports plain text and HTML body. Optional CC list.
```

#### `POST` /api/v1/email/notify

**Summary**: Send a styled HRMS notification email

```text
Send a branded notification email with a heading and body message.
Uses the BlitzenX HRMS email template automatically.
```

#### `POST` /api/v1/email/interview/invite/{interview_id}

**Summary**: Send interview invite for an existing scheduled interview

```text
Fetches interview details from the DB (candidate, panel members, times)
and sends a full invite:
- Creates a Teams calendar event (organiser = helpdesk_hrms@blitzenx.com)
- Sends a branded HTML email to the **candidate** with interviewers in CC

Also stores the `outlook_event_id` and `meeting_link` back on the interview row.
```

#### `POST` /api/v1/email/interview/invite/custom

**Summary**: Send a custom ad-hoc interview invite (no interview_id needed)

```text
Ad-hoc interview invite when the interview hasn't been formally
entered into the system yet. Provide all details manually.
```


---

## Internal Endpoints
**Source File**: `app/api/v1/endpoints/internal.py`  
**Base Prefix**: `/api/v1/internal`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/internal/notes/{candidate_id}` | Get all internal HR notes for a candidate | `get_notes_by_candidate()` |
| `POST` | `/api/v1/internal/notes/{candidate_id}` | Add an internal HR note to a candidate | `create_note()` |

### Detailed Functionality

#### `GET` /api/v1/internal/notes/{candidate_id}

**Summary**: Get all internal HR notes for a candidate

```text
Returns all **internal HR notes** for the given candidate, ordered by
newest first.

Only HR / Admin users can access this endpoint. Notes are strictly
internal and **never** exposed to the candidate.

**Optional query params**:
- `category` — filter to notes matching a specific category tag.
```

#### `POST` /api/v1/internal/notes/{candidate_id}

**Summary**: Add an internal HR note to a candidate

```text
Creates a new **internal HR note** on a candidate.

- Notes are private and intended solely for the HR team's tracking.
- The `category` field is optional and defaults to `"General"`.
- The note is attributed to the authenticated HR / Admin user.

**Example categories**: `General`, `Background Check`,
`Salary Negotiation`, `Reference Check`, `Culture Fit`, `Offer Discussion`.
```


---

## Interviews Endpoints
**Source File**: `app/api/v1/endpoints/interviews.py`  
**Base Prefix**: `/api/v1/interviews`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/interviews/panels/create` | Create a new interview panel for a candidate. | `create_interview_panel()` |
| `GET` | `/api/v1/interviews/panels/{panel_id}` | Get details of a specific interview panel. | `get_interview_panel()` |
| `GET` | `/api/v1/interviews/panels` | Get all interview panels with optional filtering. | `get_all_interview_panels()` |
| `DELETE` | `/api/v1/interviews/panels/{panel_id}` | Delete an interview panel and all associated data. | `delete_interview_panel()` |
| `POST` | `/api/v1/interviews/panel-members/assign` | Assign an interviewer to an interview panel. | `assign_panel_member()` |
| `GET` | `/api/v1/interviews/panel-members/{panel_id}` | Get all members of a specific panel. | `get_panel_members()` |
| `DELETE` | `/api/v1/interviews/panel-members/{member_id}` | Remove an interviewer from a panel. | `remove_panel_member()` |
| `POST` | `/api/v1/interviews/create` | Create a new interview. | `create_interview()` |
| `GET` | `/api/v1/interviews/my-interviews` | Get my interviews | `get_my_interviews()` |
| `GET` | `/api/v1/interviews/{interview_id}` | Get details of a specific interview. | `get_interview()` |
| `GET` | `/api/v1/interviews` | Get all interviews with optional filtering. | `get_all_interviews()` |
| `PUT` | `/api/v1/interviews/{interview_id}` | Update an existing interview. | `update_interview()` |
| `DELETE` | `/api/v1/interviews/{interview_id}` | Delete an interview and all associated feedback. | `delete_interview()` |
| `POST` | `/api/v1/interviews/feedback/submit` | Submit interview feedback. | `submit_interview_feedback()` |
| `GET` | `/api/v1/interviews/feedback/interview/{interview_id}` | Get all feedback for a specific interview. | `get_feedback_by_interview()` |
| `GET` | `/api/v1/interviews/feedback/{feedback_id}` | Get specific feedback details. | `get_feedback_by_id()` |
| `PUT` | `/api/v1/interviews/feedback/{feedback_id}` | Update existing interview feedback. | `update_interview_feedback()` |
| `DELETE` | `/api/v1/interviews/feedback/{feedback_id}` | Delete interview feedback. | `delete_interview_feedback()` |
| `GET` | `/api/v1/interviews/statistics` | Get overall interview statistics. | `get_interview_statistics()` |
| `GET` | `/api/v1/interviews/candidate-history/{candidate_id}` | Get complete interview history for a candidate. | `get_candidate_interview_history()` |
| `GET` | `/api/v1/interviews/interviewer-workload/{interviewer_id}` | Get workload statistics for an interviewer. | `get_interviewer_workload()` |

### Detailed Functionality

#### `POST` /api/v1/interviews/panels/create

**Summary**: Create a new interview panel for a candidate.

```text
Create a new interview panel for a candidate.

Args:
    request: InterviewPanelCreate with candidate_id and round_name
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewPanelResponse with panel details
    
Raises:
    HTTPException: If candidate not found
```

#### `GET` /api/v1/interviews/panels/{panel_id}

**Summary**: Get details of a specific interview panel.

```text
Get details of a specific interview panel.

Args:
    panel_id: ID of the panel
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewPanelWithDetails including member and interview counts
    
Raises:
    HTTPException: If panel not found
```

#### `GET` /api/v1/interviews/panels

**Summary**: Get all interview panels with optional filtering.

```text
Get all interview panels with optional filtering.

Args:
    candidate_id: Optional filter by candidate ID
    round_name: Optional filter by round name
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    List of InterviewPanelWithDetails
```

#### `DELETE` /api/v1/interviews/panels/{panel_id}

**Summary**: Delete an interview panel and all associated data.

```text
Delete an interview panel and all associated data.

Args:
    panel_id: ID of the panel to delete
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If panel not found
```

#### `POST` /api/v1/interviews/panel-members/assign

**Summary**: Assign an interviewer to an interview panel.

```text
Assign an interviewer to an interview panel.

Args:
    request: PanelMemberCreate with panel_id and interviewer_id
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    PanelMemberResponse with assignment details
    
Raises:
    HTTPException: If panel or interviewer not found, or already assigned
```

#### `GET` /api/v1/interviews/panel-members/{panel_id}

**Summary**: Get all members of a specific panel.

```text
Get all members of a specific panel.

Args:
    panel_id: ID of the panel
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    List of PanelMemberWithDetails
    
Raises:
    HTTPException: If panel not found
```

#### `DELETE` /api/v1/interviews/panel-members/{member_id}

**Summary**: Remove an interviewer from a panel.

```text
Remove an interviewer from a panel.

Args:
    member_id: ID of the panel member to remove
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If panel member not found
```

#### `POST` /api/v1/interviews/create

**Summary**: Create a new interview.

```text
Create a new interview.

Args:
    request: InterviewCreate with interview details
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewResponse with interview details
    
Raises:
    HTTPException: If panel or candidate not found, or time validation fails
```

#### `GET` /api/v1/interviews/my-interviews

**Summary**: Get my interviews

```text
Get all interviews where the current user is a panel member.

- Lists every interview across all panels the user has been assigned to.
- If the interview is **Completed**, the user's own feedback for that
  interview is embedded in ``my_feedback`` (``None`` when not yet submitted).
- ``feedback_submitted`` is ``True`` when the user has already given feedback.
- ``pending_feedback`` in the summary counts completed interviews with no
  feedback from the user yet.

Args:
    status: Optional filter (Scheduled | Completed | Cancelled)
    db: Database session
    user: Authenticated HR/Admin user (must be a panel member)

Returns:
    MyInterviewsResponse with aggregated interview list
```

#### `GET` /api/v1/interviews/{interview_id}

**Summary**: Get details of a specific interview.

```text
Get details of a specific interview.

Args:
    interview_id: ID of the interview
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewDetailedResponse with complete interview details
    
Raises:
    HTTPException: If interview not found
```

#### `GET` /api/v1/interviews

**Summary**: Get all interviews with optional filtering.

```text
Get all interviews with optional filtering.

Args:
    candidate_id: Optional filter by candidate ID
    panel_id: Optional filter by panel ID
    status: Optional filter by status
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    List of InterviewDetailedResponse
```

#### `PUT` /api/v1/interviews/{interview_id}

**Summary**: Update an existing interview.

```text
Update an existing interview.

Args:
    interview_id: ID of the interview to update
    request: InterviewUpdate with fields to update
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewResponse with updated interview details
    
Raises:
    HTTPException: If interview not found or validation fails
```

#### `DELETE` /api/v1/interviews/{interview_id}

**Summary**: Delete an interview and all associated feedback.

```text
Delete an interview and all associated feedback.

Args:
    interview_id: ID of the interview to delete
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If interview not found
```

#### `POST` /api/v1/interviews/feedback/submit

**Summary**: Submit interview feedback.

```text
Submit interview feedback.

Args:
    request: InterviewFeedbackCreate with feedback details
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewFeedbackResponse with feedback details
    
Raises:
    HTTPException: If interview or interviewer not found, or validation fails
```

#### `GET` /api/v1/interviews/feedback/interview/{interview_id}

**Summary**: Get all feedback for a specific interview.

```text
Get all feedback for a specific interview.

Args:
    interview_id: ID of the interview
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    List of InterviewFeedbackWithDetails
    
Raises:
    HTTPException: If interview not found
```

#### `GET` /api/v1/interviews/feedback/{feedback_id}

**Summary**: Get specific feedback details.

```text
Get specific feedback details.

Args:
    feedback_id: ID of the feedback
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewFeedbackWithDetails
    
Raises:
    HTTPException: If feedback not found
```

#### `PUT` /api/v1/interviews/feedback/{feedback_id}

**Summary**: Update existing interview feedback.

```text
Update existing interview feedback.

Args:
    feedback_id: ID of the feedback to update
    request: InterviewFeedbackUpdate with fields to update
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewFeedbackResponse with updated feedback
    
Raises:
    HTTPException: If feedback not found or validation fails
```

#### `DELETE` /api/v1/interviews/feedback/{feedback_id}

**Summary**: Delete interview feedback.

```text
Delete interview feedback.

Args:
    feedback_id: ID of the feedback to delete
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If feedback not found
```

#### `GET` /api/v1/interviews/statistics

**Summary**: Get overall interview statistics.

```text
Get overall interview statistics.

Args:
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewStatistics with counts and averages
```

#### `GET` /api/v1/interviews/candidate-history/{candidate_id}

**Summary**: Get complete interview history for a candidate.

```text
Get complete interview history for a candidate.

Args:
    candidate_id: ID of the candidate
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    CandidateInterviewHistory with all interview details
    
Raises:
    HTTPException: If candidate not found
```

#### `GET` /api/v1/interviews/interviewer-workload/{interviewer_id}

**Summary**: Get workload statistics for an interviewer.

```text
Get workload statistics for an interviewer.

Args:
    interviewer_id: ID of the interviewer
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewerWorkload with statistics and upcoming interviews
    
Raises:
    HTTPException: If interviewer not found
```


---

## Msgraph Endpoints
**Source File**: `app/api/v1/endpoints/msgraph.py`  
**Base Prefix**: `/api/v1/msgraph`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/msgraph/auth/signin` | No description provided. | `signin()` |
| `GET` | `/api/v1/msgraph/auth/callback` | No description provided. | `callback()` |
| `GET` | `/api/v1/msgraph/me` | Return the current authenticated user's profile from the database. | `me()` |
| `POST` | `/api/v1/msgraph/mail/send` | No description provided. | `send_mail()` |
| `POST` | `/api/v1/msgraph/calendar/schedule` | No description provided. | `schedule_meeting()` |
| `GET` | `/api/v1/msgraph/calendar/meetings` | Get user's calendar meetings/events. | `get_my_meetings()` |
| `GET` | `/api/v1/msgraph/service/calendar/events/{user_email}` | Get calendar events for a specific user within a date range using service account. | `get_user_calendar_events()` |
| `POST` | `/api/v1/msgraph/service/calendar/schedule` | Schedule a meeting for a specific user using service account. | `schedule_meeting_for_user()` |
| `GET` | `/api/v1/msgraph/sharepoint/test-connection` | Test SharePoint connection and list available folders. | `test_sharepoint_connection()` |
| `GET` | `/api/v1/msgraph/sharepoint/list-drives` | List all drives available in the SharePoint site. | `list_sharepoint_drives()` |

### Detailed Functionality

#### `GET` /api/v1/msgraph/auth/signin

**Summary**: No description provided.

*No detailed description available.*

#### `GET` /api/v1/msgraph/auth/callback

**Summary**: No description provided.

*No detailed description available.*

#### `GET` /api/v1/msgraph/me

**Summary**: Return the current authenticated user's profile from the database.

```text
Return the current authenticated user's profile from the database.
Requires a valid JWT Bearer token (obtained from /auth/callback redirect).

Returns:
    User details
```

#### `POST` /api/v1/msgraph/mail/send

**Summary**: No description provided.

*No detailed description available.*

#### `POST` /api/v1/msgraph/calendar/schedule

**Summary**: No description provided.

*No detailed description available.*

#### `GET` /api/v1/msgraph/calendar/meetings

**Summary**: Get user's calendar meetings/events.

```text
Get user's calendar meetings/events.

Args:
    top: Number of events to return (default: 10, max: 100)
    skip: Number of events to skip for pagination (default: 0)

Returns:
    List of calendar events with details
```

#### `GET` /api/v1/msgraph/service/calendar/events/{user_email}

**Summary**: Get calendar events for a specific user within a date range using service account.

```text
Get calendar events for a specific user within a date range using service account.
Uses Application-level permissions (Calendars.ReadWrite).
No user sign-in required.

Args:
    user_email: Email address of the user whose calendar to read
    start_time: Start of date range in ISO format (e.g., "2026-02-03T00:00:00")
               If not provided, defaults to current date at 00:00:00
    end_time: End of date range in ISO format (e.g., "2026-02-10T23:59:59")
             If not provided, defaults to 7 days from start_time

Returns:
    List of calendar events for the specified user within the date range
```

#### `POST` /api/v1/msgraph/service/calendar/schedule

**Summary**: Schedule a meeting for a specific user using service account.

```text
Schedule a meeting for a specific user using service account.
Uses Application-level permissions (Calendars.ReadWrite, OnlineMeetings.ReadWrite.All).
No user sign-in required.

Args:
    organizer_email: Email of the user who will be the organizer
    subject: Meeting subject/title
    start_iso: Start time in ISO format (e.g., "2026-02-03T10:00:00")
    end_iso: End time in ISO format
    attendees: List of attendee email addresses
    timezone: Timezone (default: UTC)
    teams_online: Create as Teams online meeting (default: True)
    location: Physical location (optional)

Returns:
    Event ID and Teams join URL (if online meeting)
```

#### `GET` /api/v1/msgraph/sharepoint/test-connection

**Summary**: Test SharePoint connection and list available folders.

```text
Test SharePoint connection and list available folders.
Uses service account authentication.

Returns:
    Connection status and folder list
```

#### `GET` /api/v1/msgraph/sharepoint/list-drives

**Summary**: List all drives available in the SharePoint site.

```text
List all drives available in the SharePoint site.
Helps identify the correct Drive ID to use in .env file.

Returns:
    List of drives with their IDs and names
```


---

## Newsletter Endpoints
**Source File**: `app/api/v1/endpoints/newsletter.py`  
**Base Prefix**: `/api/v1/newsletters`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/newsletters/subscribe` | Subscribe an email to the newsletter | `subscribe_newsletter()` |
| `DELETE` | `/api/v1/newsletters/unsubscribe/{email}` | Unsubscribe an email from the newsletter | `unsubscribe_newsletter()` |
| `GET` | `/api/v1/newsletters/subscribers` | List all newsletter subscribers | `get_subscribers()` |
| `POST` | `/api/v1/newsletters/create` | Create a newsletter draft | `create_newsletter()` |
| `GET` | `/api/v1/newsletters/all` | List all newsletters (optionally filtered by status) | `get_newsletters()` |
| `GET` | `/api/v1/newsletters/dispatched` | List newsletters that have been scheduled or sent | `get_dispatched_newsletters()` |
| `PUT` | `/api/v1/newsletters/update/{newsletter_id}` | Update a newsletter draft | `update_newsletter()` |
| `POST` | `/api/v1/newsletters/schedule/{newsletter_id}` | Schedule a newsletter for future delivery | `schedule_newsletter()` |
| `POST` | `/api/v1/newsletters/send/{newsletter_id}` | Send a newsletter immediately | `send_newsletter_now()` |
| `DELETE` | `/api/v1/newsletters/delete/{newsletter_id}` | Delete a newsletter | `delete_newsletter()` |

### Detailed Functionality

#### `POST` /api/v1/newsletters/subscribe

**Summary**: Subscribe an email to the newsletter

```text
Subscribe an email address to the newsletter.
- If the email doesn't exist, a new subscriber is created.
- If the email exists but is inactive, it is reactivated.
- If the email is already active, the existing record is returned as-is.
```

#### `DELETE` /api/v1/newsletters/unsubscribe/{email}

**Summary**: Unsubscribe an email from the newsletter

```text
Deactivate an email address so it no longer receives newsletters.
Returns 404 if the subscriber does not exist.
```

#### `GET` /api/v1/newsletters/subscribers

**Summary**: List all newsletter subscribers

```text
Retrieve a paginated list of all newsletter subscribers.
```

#### `POST` /api/v1/newsletters/create

**Summary**: Create a newsletter draft

```text
Create a new newsletter in 'draft' status.
```

#### `GET` /api/v1/newsletters/all

**Summary**: List all newsletters (optionally filtered by status)

```text
Retrieve a paginated list of all newsletters, newest first.

Pass an optional `status` query param to filter:
- `draft` — unpublished drafts
- `scheduled` — queued for future delivery
- `sent` — already delivered
- `failed` — delivery failed
```

#### `GET` /api/v1/newsletters/dispatched

**Summary**: List newsletters that have been scheduled or sent

```text
Return only newsletters with status `scheduled` or `sent` — i.e. every
newsletter that an admin has dispatched (queued or already delivered).
Results are ordered newest-first.
```

#### `PUT` /api/v1/newsletters/update/{newsletter_id}

**Summary**: Update a newsletter draft

```text
Partially update fields on an existing newsletter. Returns 404 if not found.
```

#### `POST` /api/v1/newsletters/schedule/{newsletter_id}

**Summary**: Schedule a newsletter for future delivery

```text
Schedule an existing draft (or reschedule a previously scheduled) newsletter.
Returns 400 if the newsletter has already been sent.
```

#### `POST` /api/v1/newsletters/send/{newsletter_id}

**Summary**: Send a newsletter immediately

```text
Immediately send a newsletter to all active subscribers.
Returns 400 if the newsletter has already been sent.
```

#### `DELETE` /api/v1/newsletters/delete/{newsletter_id}

**Summary**: Delete a newsletter

```text
Permanently delete a newsletter and cancel any associated scheduled job.
Returns 404 if the newsletter does not exist.
```


---

## Offer Letters Endpoints
**Source File**: `app/api/v1/endpoints/offer_letters.py`  
**Base Prefix**: `/api/v1/offer-letter`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/offer-letter/templates` | List all offer-letter templates available in SharePoint | `list_offer_templates()` |
| `POST` | `/api/v1/offer-letter/respond` | Candidate responds to an offer letter (accept or reject). | `respond_to_offer()` |
| `GET` | `/api/v1/offer-letter/my-offers` | Get all offer letters for the authenticated candidate. | `get_my_offers()` |
| `POST` | `/api/v1/offer-letter/create` | Create a new offer letter for a candidate (HR/Recruiter only). | `create_offer_letter()` |
| `POST` | `/api/v1/offer-letter/cancel/{offer_id}` | Cancel an offer letter (HR/Recruiter only). | `cancel_offer_letter()` |
| `PUT` | `/api/v1/offer-letter/update/{offer_id}` | Update an offer letter (HR/Recruiter only). | `update_offer_letter()` |
| `GET` | `/api/v1/offer-letter/all` | Get all offer letters with optional filters (HR/Recruiter only). | `get_all_offers()` |
| `GET` | `/api/v1/offer-letter/{offer_id}` | Get a specific offer letter by ID (HR/Recruiter only). | `get_offer_by_id()` |
| `POST` | `/api/v1/offer-letter/generate/{offer_id}` | Generate a filled offer letter .docx from the SharePoint template | `generate_offer_letter_document()` |
| `POST` | `/api/v1/offer-letter/salary-structure` | Generate a salary-structure .docx for an employee | `generate_salary_structure()` |
| `POST` | `/api/v1/offer-letter/salary-structure/details` | Generate salary-structure details + downloadable .docx in a single response | `generate_salary_structure_with_details()` |
| `GET` | `/api/v1/offer-letter/salary-structure/preview/{offer_id}` | Preview salary breakdown for an existing offer letter | `preview_salary_structure()` |

### Detailed Functionality

#### `GET` /api/v1/offer-letter/templates

**Summary**: List all offer-letter templates available in SharePoint

```text
Returns all `.docx` (and other) template files stored in the SharePoint
templates folder (`SHAREPOINT_TEMPLATE_PATH` parent directory).

**Optional query param:**
- `folder` — drill into a sub-folder, e.g. `?folder=full-time`

**Required permission:** `offer.view`
```

#### `POST` /api/v1/offer-letter/respond

```text
Candidate responds to an offer letter (accept or reject).
```

#### `GET` /api/v1/offer-letter/my-offers

```text
Get all offer letters for the authenticated candidate.
```

#### `POST` /api/v1/offer-letter/create

```text
Create a new offer letter for a candidate (HR/Recruiter only).
```

#### `POST` /api/v1/offer-letter/cancel/{offer_id}

```text
Cancel an offer letter (HR/Recruiter only).
```

#### `PUT` /api/v1/offer-letter/update/{offer_id}

```text
Update an offer letter (HR/Recruiter only).
```

#### `GET` /api/v1/offer-letter/all

```text
Get all offer letters with optional filters (HR/Recruiter only).
```

#### `GET` /api/v1/offer-letter/{offer_id}

```text
Get a specific offer letter by ID (HR/Recruiter only).
```

#### `POST` /api/v1/offer-letter/generate/{offer_id}

**Summary**: Generate a filled offer letter .docx from the SharePoint template

```text
Auto-generate a filled `.docx` offer letter for the given offer.

1. Load offer + candidate + job details from the database.
2. Fetch the template `.docx` from SharePoint.
3. Replace all `{{placeholder}}` tokens and inject the salary table.
4. Upload the filled document back to SharePoint.
5. Return the SharePoint web URL and a pre-authenticated download link.

**Required permission:** `offer.manage`
```

#### `POST` /api/v1/offer-letter/salary-structure

**Summary**: Generate a salary-structure .docx for an employee

```text
Generate and **download** a professional salary-structure Word document.

Components auto-calculated from annual CTC:
- Basic = 50% CTC, HRA = 40% Basic
- Medical = ₹15 000, Transport = ₹19 200, Performance = ₹19 800 (all fixed)
- PT Deduction = ₹1 800 (fixed)

**Required permission:** `offer.manage`
```

#### `POST` /api/v1/offer-letter/salary-structure/details

**Summary**: Generate salary-structure details + downloadable .docx in a single response

```text
Generate the salary-structure Word document **and** return the full
salary breakdown as structured JSON in a single API call.

The `.docx` file is included in the response as a **base64-encoded string**
under `salary_structure.docx_base64`.  Decode it on the frontend to offer
the user a download without a second request.

**Salary components (auto-calculated from annual CTC):**
| Component | Rule |
|---|---|
| Basic | 50% of CTC |
| HRA | 40% of Basic |
| Medical | Fixed ₹15,000 p.a. |
| Transport | Fixed ₹19,200 p.a. |
| Deployment / Performance | Remaining after above 4, capped ₹60,000 |
| Fixed Allowance | Remainder after all above |
| EPF Employee & Employer | 12% of EPF base, capped ₹21,600 each |
| ESIC Employee | 0.75% of ESIC base (only if monthly base ≤ ₹21,000) |

**Required permission:** `offer.manage`
```

#### `GET` /api/v1/offer-letter/salary-structure/preview/{offer_id}

**Summary**: Preview salary breakdown for an existing offer letter

```text
Return the calculated salary breakdown (JSON) for an existing offer
without generating a file — useful for UI previews.

**Required permission:** `offer.view`
```


---

## Onboarding Endpoints
**Source File**: `app/api/v1/endpoints/onboarding.py`  
**Base Prefix**: `/api/v1/onboarding`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/onboarding/hr/create_candidate` | Create a new candidate account with comprehensive information. | `create_candidate()` |
| `GET` | `/api/v1/onboarding/hr/get_all_candidates` | Get all candidates with their complete information for HR/Admin. | `get_all_candidates()` |
| `GET` | `/api/v1/onboarding/hr/candidate/{candidate_id}` | Get full details of a single candidate by candidate ID. | `get_candidate_by_id()` |
| `GET` | `/api/v1/onboarding/hr/my-bu/candidates` | Get all candidates owned by the calling user's Business Unit | `get_candidates_by_my_bu()` |
| `PUT` | `/api/v1/onboarding/hr/update_candidate/{candidate_id}` | Update an existing candidate. | `update_candidate()` |
| `DELETE` | `/api/v1/onboarding/hr/delete_candidate/{candidate_id}` | Delete a candidate and all associated records. | `delete_candidate()` |
| `GET` | `/api/v1/onboarding/hr/candidate/{candidate_id}/contacts` | Get assigned managers and job contact person for a candidate | `get_candidate_contacts()` |

### Detailed Functionality

#### `POST` /api/v1/onboarding/hr/create_candidate

**Summary**: Create a new candidate account with comprehensive information.

```text
Create a new candidate account with comprehensive information.

Args:
    request: CandidateCreateRequest containing candidate details including:
            - Required: email, role
            - Optional: name fields, contact info, professional details, salary info, location
    db: Database session
    
Returns:
    CandidateCreateResponse with candidate_id, is_first_time flag, and generated password
    
Raises:
    HTTPException: If candidate with email already exists
```

#### `GET` /api/v1/onboarding/hr/get_all_candidates

**Summary**: Get all candidates with their complete information for HR/Admin.

```text
Get all candidates with their complete information for HR/Admin.

Returns:
    AllCandidatesResponse with list of all candidates and their forms
```

#### `GET` /api/v1/onboarding/hr/candidate/{candidate_id}

**Summary**: Get full details of a single candidate by candidate ID.

```text
Get full details of a single candidate by candidate ID.

Returns all profile data including personal info form, education,
experience, Aadhar, and PAN records.

Raises:
    HTTPException 404: If no candidate with the given ID exists.
```

#### `GET` /api/v1/onboarding/hr/my-bu/candidates

**Summary**: Get all candidates owned by the calling user's Business Unit

```text
Returns all candidates that are currently **owned by the calling user's
Business Unit** (pool_status = 'BU Owned').

- The BU is determined automatically from the logged-in user's
  `business_unit_id` — no parameter needed.
- Use `include_org_pool=true` to also fetch unassigned Org Pool candidates
  (useful for BU managers who want to pick new candidates).
- Optionally filter by `pipeline_status`.

**Requires:** `candidate.view` permission.
```

#### `PUT` /api/v1/onboarding/hr/update_candidate/{candidate_id}

**Summary**: Update an existing candidate.

```text
Update an existing candidate.

Args:
    candidate_id: ID of the candidate to update
    request: CandidateUpdateRequest containing fields to update
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    CandidateCreateResponse with updated candidate details
    
Raises:
    HTTPException: If candidate not found
```

#### `DELETE` /api/v1/onboarding/hr/delete_candidate/{candidate_id}

**Summary**: Delete a candidate and all associated records.

```text
Delete a candidate and all associated records.

Args:
    candidate_id: ID of the candidate to delete
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If candidate not found
```

#### `GET` /api/v1/onboarding/hr/candidate/{candidate_id}/contacts

**Summary**: Get assigned managers and job contact person for a candidate

```text
Returns the full contact details for everyone connected to a candidate:

**From CandidateAssignment (direct assignment):**
- `assigned_hiring_manager` — the HR user directly assigned to manage this candidate
- `assigned_reporting_manager` — the reporting manager directly assigned to the candidate

**From the candidate's linked Job (via `candidate.job_id`):**
- `job_contact_person` — the contact person recorded on the job posting
- `job_hiring_manager` — the hiring manager recorded on the job posting
- `job_recruiter` — the recruiter recorded on the job posting

All fields are `null` when the corresponding record does not exist.
```


---

## Preonboarding Endpoints
**Source File**: `app/api/v1/endpoints/preonboarding.py`  
**Base Prefix**: `/api/v1/preonboarding`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/preonboarding/hiring-manager/review` | Hiring Manager: list candidates with ≥2 completed interviews (ready for approval/rejection) | `get_hm_candidate_review()` |
| `POST` | `/api/v1/preonboarding/{candidate_id}/hiring-manager-approval` | Hiring Manager Approval for a candidate | `hiring_manager_approval()` |

### Detailed Functionality

#### `GET` /api/v1/preonboarding/hiring-manager/review

**Summary**: Hiring Manager: list candidates with ≥2 completed interviews (ready for approval/rejection)

```text
Returns the list of candidates who have completed **at least 2 interviews**
for jobs where the authenticated user is the **Hiring Manager**.

For each candidate every completed interview round is included together
with the full feedback from each panel member (scores, comments, recommendation).

Use the ``approval_endpoint`` field in each candidate entry to approve or
reject them via ``POST /preonboarding/{candidate_id}/hiring-manager-approval``.
```

#### `POST` /api/v1/preonboarding/{candidate_id}/hiring-manager-approval

**Summary**: Hiring Manager Approval for a candidate

```text
Process Hiring Manager Approval for a candidate.

The candidate must be in the 'Approval' pipeline stage.
The authenticated user must be the assigned hiring manager for the candidate
(or an administrator, depending on business rules).

If Approved -> Candidate moves to 'Pre-Onboarding'
If Rejected -> Candidate moves to 'Rejected' (and goes to Org Pool)
```


---

## Rbac Endpoints
**Source File**: `app/api/v1/endpoints/rbac.py`  
**Base Prefix**: `/api/v1/rbac`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/rbac/roles` | List all roles | `list_roles()` |
| `POST` | `/api/v1/rbac/roles` | Create a new role | `create_role()` |
| `GET` | `/api/v1/rbac/roles/{role_id}` | Get a role with its attributes and permissions | `get_role()` |
| `GET` | `/api/v1/rbac/permissions` | List all permissions | `list_permissions()` |
| `POST` | `/api/v1/rbac/permissions` | Create a new permission | `create_permission()` |
| `POST` | `/api/v1/rbac/roles/{role_id}/permissions` | Assign a permission to a role | `assign_permission_to_role()` |
| `DELETE` | `/api/v1/rbac/roles/{role_id}/permissions/{permission_id}` | Remove a permission from a role | `remove_permission_from_role()` |
| `POST` | `/api/v1/rbac/users/{user_id}/assign-role` | Assign a role to a user | `assign_role_to_user()` |
| `GET` | `/api/v1/rbac/users/{user_id}/permissions` | Get a user's effective permissions and attributes | `get_user_permissions()` |
| `POST` | `/api/v1/rbac/users/set-business-unit` | Assign a business unit to a user | `set_business_unit_for_user()` |
| `PUT` | `/api/v1/rbac/users/{user_id}/business-unit` | Update a user's business unit | `update_business_unit_for_user()` |
| `GET` | `/api/v1/rbac/users/{user_id}/business-unit` | Get the business unit assigned to a user | `get_user_business_unit()` |
| `POST` | `/api/v1/rbac/business-units` | Create a new business unit | `create_business_unit()` |
| `GET` | `/api/v1/rbac/business-units` | List all business units | `list_business_units()` |
| `DELETE` | `/api/v1/rbac/business-units/{business_unit_id}` | Delete a business unit | `delete_business_unit()` |
| `DELETE` | `/api/v1/rbac/roles/{role_id}` | Delete a role | `delete_role()` |
| `PUT` | `/api/v1/rbac/roles/{role_id}` | Update a role name/description | `update_role()` |
| `DELETE` | `/api/v1/rbac/permissions/{permission_id}` | Delete a permission | `delete_permission()` |
| `GET` | `/api/v1/rbac/users/{user_id}/role` | Get the RBAC role assigned to a user | `get_user_role()` |
| `DELETE` | `/api/v1/rbac/users/{user_id}/role` | Revoke the RBAC role from a user | `revoke_user_role()` |
| `GET` | `/api/v1/rbac/business-units/{business_unit_id}` | Get a single business unit by ID | `get_business_unit()` |
| `PUT` | `/api/v1/rbac/business-units/{business_unit_id}` | Update a business unit | `update_business_unit()` |
| `POST` | `/api/v1/rbac/departments` | Create a new department | `create_department()` |
| `GET` | `/api/v1/rbac/departments` | List all departments | `list_departments()` |
| `GET` | `/api/v1/rbac/departments/{department_id}` | Get a single department by ID | `get_department()` |
| `PUT` | `/api/v1/rbac/departments/{department_id}` | Update a department | `update_department()` |
| `DELETE` | `/api/v1/rbac/departments/{department_id}` | Delete a department | `delete_department()` |
| `POST` | `/api/v1/rbac/users/set-department` | Assign a department to a user | `set_department_for_user()` |
| `PUT` | `/api/v1/rbac/users/{user_id}/department` | Update a user's department | `update_department_for_user()` |
| `GET` | `/api/v1/rbac/users/{user_id}/department` | Get the department assigned to a user | `get_user_department()` |

### Detailed Functionality

#### `GET` /api/v1/rbac/roles

**Summary**: List all roles

```text
Return all defined RBAC roles (lightweight list).
```

#### `POST` /api/v1/rbac/roles

**Summary**: Create a new role

```text
Create a new RBAC role. Returns 409 if the role name already exists.
```

#### `GET` /api/v1/rbac/roles/{role_id}

**Summary**: Get a role with its attributes and permissions

```text
Retrieve a single role with its full attribute list and assigned permissions.
```

#### `GET` /api/v1/rbac/permissions

**Summary**: List all permissions

```text
Return all defined RBAC permissions.
```

#### `POST` /api/v1/rbac/permissions

**Summary**: Create a new permission

```text
Create a new named permission string. Returns 409 if it already exists.
```

#### `POST` /api/v1/rbac/roles/{role_id}/permissions

**Summary**: Assign a permission to a role

```text
Add a permission to a role. Idempotent — no error if already assigned.
```

#### `DELETE` /api/v1/rbac/roles/{role_id}/permissions/{permission_id}

**Summary**: Remove a permission from a role

```text
Remove a permission from a role. Returns 404 if the mapping doesn't exist.
```

#### `POST` /api/v1/rbac/users/{user_id}/assign-role

**Summary**: Assign a role to a user

```text
Assign an RBAC role to a user by their UserID.
Returns 404 if the user or role does not exist.
```

#### `GET` /api/v1/rbac/users/{user_id}/permissions

**Summary**: Get a user's effective permissions and attributes

```text
Inspect the full permission and attribute set for a user based on their assigned RBAC role.
Returns an empty summary if no role is assigned.
```

#### `POST` /api/v1/rbac/users/set-business-unit

**Summary**: Assign a business unit to a user

```text
Assign a business unit to a user by their UserID.
Returns 404 if the user or business unit does not exist.
```

#### `PUT` /api/v1/rbac/users/{user_id}/business-unit

**Summary**: Update a user's business unit

```text
Update a user's business unit by their UserID.
Returns 404 if the user or business unit does not exist.
```

#### `GET` /api/v1/rbac/users/{user_id}/business-unit

**Summary**: Get the business unit assigned to a user

```text
Retrieve the business unit assigned to a user by their UserID.
Returns 404 if the user does not exist or has no business unit assigned.
```

#### `POST` /api/v1/rbac/business-units

**Summary**: Create a new business unit

```text
Create a new business unit.
Returns 409 if the business unit name already exists.
```

#### `GET` /api/v1/rbac/business-units

**Summary**: List all business units

```text
Return all defined business units.
```

#### `DELETE` /api/v1/rbac/business-units/{business_unit_id}

**Summary**: Delete a business unit

```text
Delete a business unit by its ID. Returns 404 if not found.
```

#### `DELETE` /api/v1/rbac/roles/{role_id}

**Summary**: Delete a role

```text
Delete an RBAC role by ID. Returns 404 if not found.
```

#### `PUT` /api/v1/rbac/roles/{role_id}

**Summary**: Update a role name/description

```text
Update the name or description of a role. Returns 404 if not found.
```

#### `DELETE` /api/v1/rbac/permissions/{permission_id}

**Summary**: Delete a permission

```text
Delete a permission by ID. Returns 404 if not found.
```

#### `GET` /api/v1/rbac/users/{user_id}/role

**Summary**: Get the RBAC role assigned to a user

```text
Return the role currently assigned to a user. Returns 404 if no role is set.
```

#### `DELETE` /api/v1/rbac/users/{user_id}/role

**Summary**: Revoke the RBAC role from a user

```text
Remove the RBAC role assignment from a user.
```

#### `GET` /api/v1/rbac/business-units/{business_unit_id}

**Summary**: Get a single business unit by ID

```text
Retrieve a single business unit by its ID. Returns 404 if not found.
```

#### `PUT` /api/v1/rbac/business-units/{business_unit_id}

**Summary**: Update a business unit

```text
Update the name or description of a business unit. Returns 404 if not found.
```

#### `POST` /api/v1/rbac/departments

**Summary**: Create a new department

```text
Create a new department.
Returns **409** if a department with the same name already exists.
```

#### `GET` /api/v1/rbac/departments

**Summary**: List all departments

```text
Return all defined departments.
```

#### `GET` /api/v1/rbac/departments/{department_id}

**Summary**: Get a single department by ID

```text
Retrieve a single department by its ID. Returns **404** if not found.
```

#### `PUT` /api/v1/rbac/departments/{department_id}

**Summary**: Update a department

```text
Update the name or description of a department.
Returns **404** if not found. Returns **409** if the new name already exists.
```

#### `DELETE` /api/v1/rbac/departments/{department_id}

**Summary**: Delete a department

```text
Delete a department by its ID. Returns **404** if not found.
```

#### `POST` /api/v1/rbac/users/set-department

**Summary**: Assign a department to a user

```text
Assign a department to a user by their UserID.
Returns **404** if the user or department does not exist.
```

#### `PUT` /api/v1/rbac/users/{user_id}/department

**Summary**: Update a user's department

```text
Change the department assigned to a user.
Returns **404** if the user or department does not exist.
```

#### `GET` /api/v1/rbac/users/{user_id}/department

**Summary**: Get the department assigned to a user

```text
Retrieve the department assigned to the given user.
Returns **404** if the user does not exist or has no department assigned.
```


---

## Users Endpoints
**Source File**: `app/api/v1/endpoints/users.py`  
**Base Prefix**: `/api/v1/hr`

| Method | Endpoint Path | Summary / Description | Function |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/hr/me` | Get current HR/Admin user's profile with a fresh access token | `get_me()` |
| `GET` | `/api/v1/hr/users/all` | Get all users (HR, Admin, etc.) from the system. | `get_all_users()` |
| `GET` | `/api/v1/hr/users/search` | Search / filter users by name, permission role, or user role | `search_users()` |
| `POST` | `/api/v1/hr/assignments/create` | Create a candidate assignment with hiring and reporting managers. | `create_candidate_assignment()` |
| `POST` | `/api/v1/hr/interviews/create` | Create an interview with panel and candidate. | `create_interview()` |
| `POST` | `/api/v1/hr/panel-members/assign` | Assign an interviewer to an interview panel. | `assign_panel_member()` |
| `POST` | `/api/v1/hr/interviews/feedback` | Submit interview feedback with scores and recommendation. | `submit_interview_feedback()` |
| `GET` | `/api/v1/hr/assignments/candidates` | Get all candidates assigned to the logged-in user (as hiring or reporting manager). | `get_assigned_candidates()` |
| `GET` | `/api/v1/hr/interviews/assigned` | Get all interviews where the logged-in user is a panel member. | `get_assigned_interviews()` |
| `PUT` | `/api/v1/hr/update_interview/{interview_id}` | Update an existing interview. | `update_interview()` |
| `DELETE` | `/api/v1/hr/delete_interview/{interview_id}` | Delete an interview and all associated feedback. | `delete_interview()` |
| `POST` | `/api/v1/hr/users/create` | Create a new HR/Admin user | `create_user()` |
| `PUT` | `/api/v1/hr/users/{user_id}` | Update an HR/Admin user's profile or role | `update_user()` |
| `DELETE` | `/api/v1/hr/users/{user_id}` | Delete an HR/Admin user account | `delete_user()` |
| `PUT` | `/api/v1/hr/users/me/change-password` | Change current user's password | `change_password()` |
| `GET` | `/api/v1/hr/users/{user_id}` | Get a single user by ID | `get_user_by_id()` |
| `GET` | `/api/v1/hr/hiring_manager/assigned/candidate` | List candidates assigned to the authenticated hiring manager | `get_hiring_manager_assigned_candidates()` |

### Detailed Functionality

#### `GET` /api/v1/hr/me

**Summary**: Get current HR/Admin user's profile with a fresh access token

```text
Return the profile of the currently authenticated HR / Admin user
together with a fresh access token.

Useful for:
- Restoring session state after page reload
- Refreshing the token without a full re-login
- Fetching up-to-date role / business-unit information
```

#### `GET` /api/v1/hr/users/all

**Summary**: Get all users (HR, Admin, etc.) from the system.

```text
Get all users (HR, Admin, etc.) from the system.
Does not include candidates.

Args:
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    AllUsersResponse with list of all users and total count
```

#### `GET` /api/v1/hr/users/search

**Summary**: Search / filter users by name, permission role, or user role

```text
Search users with any combination of filters.  All filters are optional —
omit all of them to get a paginated list of every user.

**Filters:**
- `name` — partial, case-insensitive match on `UserName` **or** `UserEmail`
- `permission_role` — exact match on the RBAC `Role.name`
  (e.g. `'HR Manager'`, `'Recruiter'`, `'Admin'`)
- `user_role` — exact match on the legacy `UserRole` column
  (e.g. `'HR'`, `'Admin'`)

**Pagination:** use `skip` / `limit`.
```

#### `POST` /api/v1/hr/assignments/create

**Summary**: Create a candidate assignment with hiring and reporting managers.

```text
Create a candidate assignment with hiring and reporting managers.

Args:
    request: CandidateAssignmentCreate containing candidate_id and manager IDs
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    CandidateAssignmentResponse with assignment details
    
Raises:
    HTTPException: If candidate or managers not found
```

#### `POST` /api/v1/hr/interviews/create

**Summary**: Create an interview with panel and candidate.

```text
Create an interview with panel and candidate.

Args:
    request: InterviewCreate containing interview details
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewResponse with interview details
    
Raises:
    HTTPException: If panel or candidate not found
```

#### `POST` /api/v1/hr/panel-members/assign

**Summary**: Assign an interviewer to an interview panel.

```text
Assign an interviewer to an interview panel.

Args:
    request: PanelMemberCreate containing panel_id and interviewer_id
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    PanelMemberResponse with panel member details
    
Raises:
    HTTPException: If panel or interviewer not found
```

#### `POST` /api/v1/hr/interviews/feedback

**Summary**: Submit interview feedback with scores and recommendation.

```text
Submit interview feedback with scores and recommendation.

Args:
    request: InterviewFeedbackCreate containing feedback details
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewFeedbackResponse with feedback details
    
Raises:
    HTTPException: If interview or interviewer not found
```

#### `GET` /api/v1/hr/assignments/candidates

**Summary**: Get all candidates assigned to the logged-in user (as hiring or reporting manager).

```text
Get all candidates assigned to the logged-in user (as hiring or reporting manager).

Args:
    db: Database session
    user: Authenticated user
    
Returns:
    List of AssignedCandidateResponse with candidate details
```

#### `GET` /api/v1/hr/interviews/assigned

**Summary**: Get all interviews where the logged-in user is a panel member.

```text
Get all interviews where the logged-in user is a panel member.

Args:
    db: Database session
    user: Authenticated user
    
Returns:
    List of AssignedInterviewResponse with interview details
```

#### `PUT` /api/v1/hr/update_interview/{interview_id}

**Summary**: Update an existing interview.

```text
Update an existing interview.

Args:
    interview_id: ID of the interview to update
    request: InterviewUpdateRequest containing fields to update
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    InterviewResponse with updated interview details
    
Raises:
    HTTPException: If interview not found
```

#### `DELETE` /api/v1/hr/delete_interview/{interview_id}

**Summary**: Delete an interview and all associated feedback.

```text
Delete an interview and all associated feedback.

Args:
    interview_id: ID of the interview to delete
    db: Database session
    user: Authenticated HR/Admin user
    
Returns:
    DeleteResponse with success message
    
Raises:
    HTTPException: If interview not found
```

#### `POST` /api/v1/hr/users/create

**Summary**: Create a new HR/Admin user

```text
Create a new internal user (HR, Admin, etc.).
Requires permission: user.manage
```

#### `PUT` /api/v1/hr/users/{user_id}

**Summary**: Update an HR/Admin user's profile or role

```text
Update a user's name or role.
Requires permission: user.manage
```

#### `DELETE` /api/v1/hr/users/{user_id}

**Summary**: Delete an HR/Admin user account

```text
Delete an internal user account.
Before deleting, all FK references to this user across every table are
set to NULL so that no foreign-key constraint blocks the delete.
Requires permission: user.manage
```

#### `PUT` /api/v1/hr/users/me/change-password

**Summary**: Change current user's password

```text
Change the password of the currently logged-in user.
Requires the correct current password for verification.

Raises:
    400 if current password is wrong
    400 if new password is same as current
```

#### `GET` /api/v1/hr/users/{user_id}

**Summary**: Get a single user by ID

```text
Retrieve the full profile of a single internal user (HR, Admin, etc.)
by their User ID.

Args:
    user_id: The unique ID of the user to retrieve.
    db: Database session.
    current_user: Authenticated HR/Admin user (requires user.manage permission).

Returns:
    SingleUserResponse with all user details.

Raises:
    HTTPException 404: If the user is not found.
```

#### `GET` /api/v1/hr/hiring_manager/assigned/candidate

**Summary**: List candidates assigned to the authenticated hiring manager

```text
Retrieve all candidates that are directly assigned to the currently
authenticated user **as a hiring manager**.

Returns enriched candidate details including pipeline status so the
hiring manager can see the full picture at a glance.

Args:
    db: Database session.
    current_user: The authenticated hiring manager.

Returns:
    List of HiringManagerAssignedCandidateResponse.
```
