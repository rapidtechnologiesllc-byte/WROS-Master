# Duplicate Candidate Tracking - Complete Architecture

**Status:** Requirement Documentation  
**Date:** 2026-09-01  
**User Priority:** CRITICAL - Thunder needs this to analyze genuine interest patterns

---

## Feature Overview

When a candidate applies to multiple jobs, we need to:
1. ✅ Allow duplicate candidates (not reject)
2. ✅ Track all job applications for that candidate
3. ✅ Store & deduplicate resume versions intelligently
4. ✅ Show candidate history with all applications
5. ✅ Display dashboard in candidate details with all jobs

---

## Database Schema Changes

### 1. CandidateJobApplication Table (NEW)
Tracks each job application separately, allowing same candidate to apply multiple times.

```sql
CREATE TABLE candidate_job_application (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id VARCHAR(50) NOT NULL,
    job_id VARCHAR(50) NOT NULL,
    application_date TIMESTAMP DEFAULT now(),
    status VARCHAR(50) DEFAULT 'PENDING',  -- PENDING, VIEWED, SHORTLISTED, REJECTED, OFFERED
    resume_version_id UUID,  -- FK to candidate_resume_version
    applied_from VARCHAR(50),  -- 'portal', 'bulk_upload', 'recruiter', 'thunder'
    source_metadata JSONB,  -- Extra context (recruiter_id, campaign_id, etc)
    
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidateID) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(jobID) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES candidate_resume_version(id) ON DELETE SET NULL,
    
    INDEX idx_candidate_applications (candidate_id),
    INDEX idx_job_applications (job_id),
    INDEX idx_application_date (application_date)
);
```

### 2. CandidateResumeVersion Table (NEW)
Stores resume versions with deduplication by content hash.

```sql
CREATE TABLE candidate_resume_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id VARCHAR(50) NOT NULL,
    file_content BYTEA NOT NULL,  -- PDF/DOCX binary
    file_name VARCHAR(255),
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 of file_content
    version_number INT,  -- 1, 2, 3...
    uploaded_at TIMESTAMP DEFAULT now(),
    uploaded_by VARCHAR(50),  -- UserID of person who uploaded
    application_count INT DEFAULT 1,  -- How many applications use this version
    
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidateID) ON DELETE CASCADE,
    
    UNIQUE(candidate_id, content_hash),  -- Prevent duplicate content
    INDEX idx_candidate_resumes (candidate_id),
    INDEX idx_content_hash (content_hash)
);
```

### 3. Alter Existing Tables

**Add to `candidates` table:**
```sql
ALTER TABLE candidates ADD COLUMN (
    total_applications INT DEFAULT 0,  -- Denormalized for quick querying
    latest_application_date TIMESTAMP,
    latest_resume_version_id UUID
);
```

**Add to `candidate_status` table:**
```sql
ALTER TABLE candidate_status ADD COLUMN (
    applications JSONB  -- Array of job_ids this candidate applied to
);
```

---

## API Endpoints

### 1. Get All Applications for a Candidate
**GET** `/api/v1/candidates/{candidate_id}/applications`

```python
Response {
  "candidate_id": "CAN-xxx",
  "candidate_name": "Jane Doe",
  "total_applications": 3,
  "applications": [
    {
      "application_id": "APP-uuid-1",
      "job_id": "JOB-xxx",
      "job_title": "Senior Backend Engineer",
      "company": "TechCorp",
      "application_date": "2026-08-15T10:30:00Z",
      "status": "SHORTLISTED",
      "resume_version": 2,
      "days_ago": 17
    },
    {
      "application_id": "APP-uuid-2",
      "job_id": "JOB-yyy",
      "job_title": "Backend Lead",
      "company": "TechCorp",
      "application_date": "2026-08-18T14:20:00Z",
      "status": "PENDING",
      "resume_version": 2,  # Same version as above (merged)
      "days_ago": 14
    },
    {
      "application_id": "APP-uuid-3",
      "job_id": "JOB-zzz",
      "job_title": "Principal Engineer",
      "company": "OtherCorp",
      "application_date": "2026-08-25T09:15:00Z",
      "status": "REJECTED",
      "resume_version": 3,  # Different resume
      "days_ago": 7
    }
  ],
  "resume_versions": [
    {
      "version_id": "RESUME-v2-uuid",
      "version_number": 2,
      "uploaded_at": "2026-08-15T10:30:00Z",
      "application_count": 2,  # Used in 2 applications
      "is_current": true
    },
    {
      "version_id": "RESUME-v3-uuid",
      "version_number": 3,
      "uploaded_at": "2026-08-25T09:15:00Z",
      "application_count": 1,
      "is_current": false
    }
  ],
  "interest_analysis": {
    "total_jobs": 3,
    "time_span_days": 10,
    "avg_days_between_applications": 5,
    "similarity": [
      "Backend roles (2/3)",
      "All Senior+ level (3/3)",
      "Tech companies (100%)"
    ],
    "assessment": "GENUINE_INTEREST"  # or RANDOM_APPLYING, OPPORTUNISTIC
  }
}
```

### 2. Get Resume Version with Download
**GET** `/api/v1/candidates/{candidate_id}/resume-versions/{version_id}`

Returns binary PDF/DOCX file for download.

### 3. Get Resume Comparison
**GET** `/api/v1/candidates/{candidate_id}/resume-versions/compare?v1={v1_id}&v2={v2_id}`

```python
Response {
  "version_1": { "version_number": 2, "uploaded_at": "..." },
  "version_2": { "version_number": 3, "uploaded_at": "..." },
  "are_identical": false,
  "differences": {
    "skills_added": ["Kubernetes", "GraphQL"],
    "skills_removed": [],
    "experience_updated": true,
    "education_added": true,
    "summary_changed": false
  },
  "recommendation": "KEEP_BOTH"  # or MERGE
}
```

### 4. Create Candidate Job Application (When Duplicate Detected)
**POST** `/api/v1/candidates/{candidate_id}/apply-to-job`

```python
Request {
  "candidate_id": "CAN-xxx",
  "job_id": "JOB-yyy",
  "resume_version_id": "RESUME-v2-uuid",  # Optional, use latest if null
  "applied_from": "recruiter"
}

Response {
  "application_id": "APP-uuid",
  "candidate_id": "CAN-xxx",
  "job_id": "JOB-yyy",
  "status": "success",
  "is_duplicate_candidate": true,
  "message": "Jane Doe is applying to another job (3 total applications)"
}
```

---

## Frontend Components

### 1. Candidate History Screen (EXISTING - ENHANCED)
**Location:** `CandidateDetailsScreen.js`

Add new section: **"Application History"**

```
┌─────────────────────────────────────────┐
│  Candidate: Jane Doe                    │
│  Email: jane@example.com                │
│  Total Applications: 3                  │
└─────────────────────────────────────────┘

APPLICATION HISTORY
┌──────────────────────────────────────────────────┐
│ Job Title          | Date       | Status | Days │
├──────────────────────────────────────────────────┤
│ Senior Backend Eng | Aug 15     | ✓ Shrt | 17d  │
│ Backend Lead       | Aug 18     | ⏳ Pend | 14d  │
│ Principal Engineer | Aug 25     | ✗ Rej  | 7d   │
└──────────────────────────────────────────────────┘

RESUME VERSIONS
┌──────────────────────────────────────────────────┐
│ Version | Uploaded   | Used in | Download | ...  │
├──────────────────────────────────────────────────┤
│ v2      | Aug 15     | 2 jobs  | ⬇️      | 📄   │
│ v3      | Aug 25     | 1 job   | ⬇️      | 📄   │
└──────────────────────────────────────────────────┘
```

**Features:**
- Click job title → open job details
- Click "Used in" → show which applications use this resume
- Download icon → download specific resume version
- "Compare" → show diff between v2 and v3
- "Merge" button if v2 and v3 identical → deduplicates

### 2. Candidate Details Left Sidebar (NEW)
**Location:** `CandidateDetailsScreen.js` - Left menu

```
CANDIDATE: Jane Doe
──────────────────

📊 Profile (current)
  └─ Basic Info
  └─ Professional
  └─ Identity
  └─ Notes

📋 Applications (3)
  ├─ Senior Backend Eng (Aug 15) ✓
  ├─ Backend Lead (Aug 18) ⏳
  └─ Principal Engineer (Aug 25) ✗

📄 Resumes (2 versions)
  ├─ Version 2 (Aug 15) - Current
  └─ Version 3 (Aug 25)

📧 Messages (7)
⭐ Starred (1)
🔔 Notifications
```

**Clicking "Applications (3)"** shows timeline view:
- Left: All 3 applications (clickable)
- Main: Selected application details + resume version used

### 3. Application Timeline Component (NEW)
**Shows:** "Jane applied to 3 jobs in the last 10 days"

Visual timeline:
```
Aug 15  Aug 18  Aug 21  Aug 24  Aug 27
  |       |       |       |       |
  ●       ●               ●
  |       |_______________|
  |       Backend roles
  |
  Senior Backend Eng
  
  ● = Application
  Assessment: Genuinely interested (similar roles, consistent timeline)
```

---

## Duplicate Resume Deduplication Logic

### Algorithm: Smart Resume Versioning

```python
def handle_duplicate_candidate_application(candidate_id, job_id, new_resume_file):
    """
    1. Compute SHA-256 hash of new resume
    2. Check if exact match exists for this candidate
    3. If match: link to existing version (no duplicate storage)
    4. If no match: create new version with incremented version_number
    5. Create application record linking to resume version
    """
    
    # Step 1: Hash the new resume
    new_resume_hash = sha256(new_resume_file.content).hexdigest()
    
    # Step 2: Check existing versions
    existing_version = db.query(CandidateResumeVersion).filter(
        CandidateResumeVersion.candidate_id == candidate_id,
        CandidateResumeVersion.content_hash == new_resume_hash
    ).first()
    
    if existing_version:
        # CASE 1: Exact match found - reuse this version
        resume_version_id = existing_version.id
        existing_version.application_count += 1
        logger.info(f"Resume deduped: using version {existing_version.version_number}")
    else:
        # CASE 2: New unique resume - create new version
        next_version = (
            db.query(func.max(CandidateResumeVersion.version_number))
            .filter(CandidateResumeVersion.candidate_id == candidate_id)
            .scalar() or 0
        ) + 1
        
        new_version = CandidateResumeVersion(
            candidate_id=candidate_id,
            file_content=new_resume_file.content,
            content_hash=new_resume_hash,
            version_number=next_version,
            application_count=1
        )
        db.add(new_version)
        db.flush()
        resume_version_id = new_version.id
        logger.info(f"New resume version created: {next_version}")
    
    # Step 3: Create application record
    application = CandidateJobApplication(
        candidate_id=candidate_id,
        job_id=job_id,
        resume_version_id=resume_version_id,
        applied_from='recruiter'
    )
    db.add(application)
    db.commit()
    
    return {
        "application_id": application.id,
        "resume_version": resume_version_id,
        "version_number": (
            existing_version.version_number 
            if existing_version 
            else next_version
        ),
        "is_new_version": not existing_version
    }
```

**Examples:**

| Step | Resume | Hash | Action | Result |
|------|--------|------|--------|--------|
| 1 | v1.pdf | abc123 | Create | v1 created |
| 2 | v1.pdf (same) | abc123 | Detect dup | Use v1 (count: 2) |
| 3 | v2.pdf (updated) | def456 | Create | v2 created |
| 4 | v2.pdf (same as step 3) | def456 | Detect dup | Use v2 (count: 2) |
| 5 | v1.pdf (reverted) | abc123 | Detect dup | Use v1 (count: 3) |

**Result: 2 stored resumes (v1, v2), 5 applications, zero duplicate storage**

---

## Thunder Integration: Interest Analysis

When Thunder sees a duplicate candidate application:

```python
def analyze_candidate_interest(candidate_id):
    """
    Analyze application pattern to score genuine interest.
    Thunder uses this to decide: is this person worth pursuing?
    """
    
    applications = get_candidate_applications(candidate_id)
    
    # Metrics
    total_apps = len(applications)
    days_spanned = (applications[-1].date - applications[0].date).days
    avg_days_between = days_spanned / (total_apps - 1) if total_apps > 1 else 0
    
    # Job similarity analysis
    jobs = [get_job(app.job_id) for app in applications]
    job_titles = [j.job_title for j in jobs]
    job_levels = [extract_level(j.job_title) for j in jobs]  # Senior, Lead, Principal
    companies = [j.company for j in jobs]
    
    # Scoring
    if total_apps == 1:
        assessment = "SINGLE_APPLICATION"
        score = 0.5
    elif all_same_level(job_levels) and similar_roles(job_titles):
        assessment = "GENUINE_INTEREST"  # Applied to related roles
        score = 0.9
        reasoning = "All applications are for similar roles at same level"
    elif days_spanned < 7 and total_apps > 5:
        assessment = "RANDOM_APPLYING"  # Too many, too fast
        score = 0.2
        reasoning = f"Submitted {total_apps} applications in {days_spanned} days"
    else:
        assessment = "OPPORTUNISTIC"  # Mixed interest
        score = 0.5
        reasoning = "Applications span different roles/levels"
    
    return {
        "candidate_id": candidate_id,
        "total_applications": total_apps,
        "assessment": assessment,
        "confidence_score": score,
        "reasoning": reasoning,
        "recommendation": (
            "PURSUE_AGGRESSIVELY" if score > 0.7
            else "PURSUE_ACTIVELY" if score > 0.5
            else "LOW_PRIORITY"
        )
    }
```

---

## Implementation Roadmap

### Phase 1: Database & Backend (Week 1)
- [ ] Create `candidate_job_application` table
- [ ] Create `candidate_resume_version` table  
- [ ] Add `total_applications`, `latest_application_date` to `candidates`
- [ ] Implement `create_candidate_job_application()` service
- [ ] Implement resume deduplication logic (SHA-256 hashing)
- [ ] Create GET `/candidates/{id}/applications` endpoint
- [ ] Create GET `/candidates/{id}/resume-versions/{id}` endpoint

### Phase 2: Frontend - History Screen (Week 2)
- [ ] Add "Application History" section to CandidateDetailsScreen
- [ ] Display timeline of all applications
- [ ] Add resume versions table
- [ ] Implement resume download
- [ ] Add resume comparison UI
- [ ] Show interest analysis (genuine vs random)

### Phase 3: Frontend - Left Sidebar (Week 2)
- [ ] Add "Applications (N)" menu item to left sidebar
- [ ] Clickable application list
- [ ] Show application status badges
- [ ] Link applications to corresponding jobs

### Phase 4: Thunder Integration (Week 3)
- [ ] Implement `analyze_candidate_interest()` function
- [ ] Call interest scoring in Thunder workflow
- [ ] Use score to adjust Thunder engagement strategy
- [ ] Log assessment to candidate record

### Phase 5: Testing & Deployment (Week 3)
- [ ] Test duplicate detection with same resume
- [ ] Test resume versioning with different resumes
- [ ] Test resume deduplication (v2=v4, keep only 1)
- [ ] End-to-end: apply 5 times, verify all tracked
- [ ] Verify interest analysis scoring

---

## Key Benefits

| Before | After |
|--------|-------|
| Same person applies 2x → 400 Error | Same person applies 2x → Tracked as 2 applications ✅ |
| Can't see application pattern | Thunder sees: applied to 3 similar roles ✅ |
| No resume versioning | Multiple resumes deduplicated, all stored ✅ |
| Unknown candidate intent | Interest score: 0.9 (genuine) vs 0.2 (random) ✅ |

---

## Success Metrics

- ✅ Zero duplicate rejection errors
- ✅ All candidate applications tracked
- ✅ Resume storage reduced by 40% (deduplication)
- ✅ Thunder can score: "Jane is 90% likely interested"
- ✅ Recruiter can see: "Jane applied to 3 backend roles in 10 days"
