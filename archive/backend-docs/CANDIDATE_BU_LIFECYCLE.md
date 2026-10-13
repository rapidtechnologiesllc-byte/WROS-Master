# Candidate Business Unit (BU) Assignment Lifecycle

**Purpose:** Define when/how candidate BU changes throughout their recruiting journey.

---

## Overview

Candidates flow between **ORG-WIDE** (NULL BU) and **BU-ASSIGNED** states based on their job application status.

```
┌─────────────────┐
│  ORG-WIDE       │
│  (BU_ID = NULL) │  ← New candidates start here
└────────┬────────┘
         │
         │ Candidate submitted to Job
         ▼
┌─────────────────────────┐
│  BU-ASSIGNED            │
│  (BU_ID = Job.BU_ID)    │  ← Locked to job's BU
└────────┬────────────────┘
         │
    ┌────┴────────────────────────┐
    │                             │
    ▼                             ▼
┌──────────────────┐     ┌──────────────────┐
│ INTERVIEW STAGE  │     │ OFFER STAGE      │
│ (BU_ID set)      │     │ (BU_ID set)      │
└────┬─────────────┘     └────┬─────────────┘
     │                         │
    ┌┴──────────────┬──────────┴┐
    │               │           │
    ▼               ▼           ▼
┌─────────┐   ┌──────────┐  ┌─────────────┐
│REJECTED │   │DECLINED  │  │ONBOARDING   │
│(back to │   │(back to  │  │(stays in BU)│
│NULL)    │   │NULL)     │  │             │
└─────────┘   └──────────┘  └──────┬──────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │ HIRED/EMPLOYEE   │
                           │ (stays in BU)    │
                           └──────────────────┘
```

---

## Detailed Transitions

### 1. **CREATED STATE** (Entry Point)
**BU Assignment:** `NULL` (org-wide)

**Why:** New candidates are unassigned until linked to a job.

**Candidates visible to:** All HR users (not filtered by BU)

**Database state:**
```sql
INSERT INTO candidates (id, candidate_name, email, business_unit_id, status)
VALUES ('uuid', 'Jane Doe', 'jane@example.com', NULL, 'Created');
```

---

### 2. **SUBMITTED TO JOB** (Transition Point)
**Action:** Candidate submitted to a specific job
**Endpoint:** `PUT /jobs/{job_id}/assign-candidate/{candidate_id}`
**New BU Assignment:** `candidate.business_unit_id = job.business_unit_id`

**Why:** Lock candidate to job's BU for isolation/tracking

**Logic:**
```python
def assign_candidate_to_job(db: Session, candidate_id: str, job_id: str, current_user: Users):
    """
    Assign candidate to job and lock to job's BU.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    job = db.query(Job).filter(Job.id == job_id).first()

    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidate or job not found")

    # ✅ ASSIGN CANDIDATE TO JOB'S BU
    # This is the key step: lock candidate to this BU
    old_bu = candidate.business_unit_id
    candidate.business_unit_id = job.business_unit_id  # Assign to job's BU
    candidate.status = "Submitted"  # or "Applied", depending on terminology

    db.commit()
    db.refresh(candidate)

    logger.info(
        f"Candidate {candidate_id} assigned to job {job_id}. "
        f"BU changed from {old_bu} (org-wide) to {job.business_unit_id} (job's BU)"
    )
    return candidate
```

**Database state:**
```sql
UPDATE candidates 
SET business_unit_id = 1,  -- Job's BU
    status = 'Submitted'
WHERE id = 'uuid';
```

**Candidates visible to:** Only HR users in that BU

---

### 3. **INTERVIEW STAGE**
**BU Assignment:** `UNCHANGED` (stays on job's BU)

**Why:** Candidate is being actively evaluated, keep locked to BU

**Database state:**
```sql
UPDATE candidates
SET status = 'Interview'
WHERE id = 'uuid';
-- business_unit_id stays the same
```

---

### 4. **OFFER STAGE**
**BU Assignment:** `UNCHANGED` (stays on job's BU)

**Why:** Candidate has passed interviews, moving toward hire

**Database state:**
```sql
UPDATE candidates
SET status = 'Offer'
WHERE id = 'uuid';
-- business_unit_id stays the same
```

---

### 5. **REJECTED IN INTERVIEW** (Reversal Point)
**Action:** Interviewer rejects candidate
**Endpoint:** `POST /interviews/{interview_id}/reject`
**New BU Assignment:** `candidate.business_unit_id = NULL` (revert to org-wide)

**Why:** Candidate is no longer attached to this job's BU - they're back in the org pool for other BUs to use

**Logic:**
```python
def reject_candidate(db: Session, interview_id: str, current_user: Users):
    """
    Reject candidate from interview and revert to org-wide (NULL BU).
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()

    # ✅ REVERT TO ORG-WIDE
    old_bu = candidate.business_unit_id
    candidate.business_unit_id = None  # Back to org-wide
    candidate.status = "Rejected"

    interview.status = "Rejected"
    interview.feedback = "..."  # Interviewer's feedback

    db.commit()
    db.refresh(candidate)

    logger.info(
        f"Candidate {candidate.id} rejected. "
        f"BU reverted from {old_bu} to NULL (org-wide)"
    )
    return candidate
```

**Database state:**
```sql
UPDATE candidates
SET business_unit_id = NULL,  -- Back to org-wide
    status = 'Rejected'
WHERE id = 'uuid';
```

**Candidates visible to:** All HR users again (not filtered by BU)

---

### 6. **DECLINED OFFER** (Reversal Point)
**Action:** Candidate declines offer
**Endpoint:** `POST /offers/{offer_id}/decline`
**New BU Assignment:** `candidate.business_unit_id = NULL` (revert to org-wide)

**Why:** Candidate said no - they're back in the org pool

**Logic:**
```python
def decline_offer(db: Session, offer_id: str, current_user: Users):
    """
    Candidate declines offer and revert to org-wide (NULL BU).
    """
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    candidate = db.query(Candidate).filter(Candidate.id == offer.candidate_id).first()

    # ✅ REVERT TO ORG-WIDE
    old_bu = candidate.business_unit_id
    candidate.business_unit_id = None  # Back to org-wide
    candidate.status = "Declined"

    offer.status = "Declined"
    offer.declined_at = datetime.utcnow()

    db.commit()
    db.refresh(candidate)

    logger.info(
        f"Candidate {candidate.id} declined offer. "
        f"BU reverted from {old_bu} to NULL (org-wide)"
    )
    return candidate
```

**Database state:**
```sql
UPDATE candidates
SET business_unit_id = NULL,  -- Back to org-wide
    status = 'Declined'
WHERE id = 'uuid';
```

**Candidates visible to:** All HR users again

---

### 7. **ONBOARDING STATE**
**BU Assignment:** `UNCHANGED` (stays on job's BU)

**Why:** Candidate is moving to employee, keep BU assignment

**Database state:**
```sql
UPDATE candidates
SET status = 'Onboarding'  -- or 'Joined'
WHERE id = 'uuid';
-- business_unit_id stays assigned
```

---

### 8. **CONVERT TO EMPLOYEE** (Final Transition)
**Action:** Employee onboarding complete
**Endpoint:** `POST /employees/convert-from-candidate`
**New state:** Candidate → Employee (new Users record)
**BU Assignment:** `employees.business_unit_id = candidate.business_unit_id` (preserve)

**Why:** Employee inherits the BU assignment from the candidate

**Logic:**
```python
def convert_candidate_to_employee(db: Session, candidate_id: str, current_user: Users):
    """
    Convert candidate to employee and preserve BU assignment.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

    if not candidate or not candidate.business_unit_id:
        raise HTTPException(
            status_code=400,
            detail="Candidate must be assigned to a BU before converting to employee"
        )

    # Create employee with SAME BU as candidate
    employee = Users(
        UserID=str(uuid.uuid4()),
        UserName=candidate.candidate_name,
        UserEmail=candidate.candidate_email,
        business_unit_id=candidate.business_unit_id,  # ✅ Preserve BU
        tenant_id=candidate.tenant_id or current_user.tenant_id,
        # ... other fields
    )

    db.add(employee)
    db.commit()
    db.refresh(employee)

    # Mark candidate as converted
    candidate.status = "Converted to Employee"
    candidate.candidate_employee_user_id = employee.UserID

    db.commit()

    logger.info(
        f"Candidate {candidate.id} converted to employee {employee.UserID}. "
        f"BU assignment preserved: {candidate.business_unit_id}"
    )
    return employee
```

**Database state:**
```sql
-- New employee inherits candidate's BU
INSERT INTO users (UserID, UserName, UserEmail, business_unit_id, tenant_id, ...)
VALUES ('emp-uuid', 'Jane Doe', 'jane@example.com', 1, 1, ...);

-- Link candidate to employee for audit trail
UPDATE candidates
SET candidate_employee_user_id = 'emp-uuid',
    status = 'Converted to Employee'
WHERE id = 'uuid';
```

---

### 9. **DIDN'T JOIN** (Reversal Point)
**Action:** Candidate was supposed to join but didn't show up
**Endpoint:** `POST /candidates/{id}/mark-no-show` or similar
**New BU Assignment:** `candidate.business_unit_id = NULL` (revert to org-wide)

**Why:** Candidate never became an employee - back to org pool

**Logic:**
```python
def mark_candidate_no_show(db: Session, candidate_id: str, current_user: Users):
    """
    Mark candidate as no-show (didn't join) and revert to org-wide.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

    # ✅ REVERT TO ORG-WIDE
    old_bu = candidate.business_unit_id
    candidate.business_unit_id = None  # Back to org-wide
    candidate.status = "No Show"

    db.commit()
    db.refresh(candidate)

    logger.info(
        f"Candidate {candidate.id} marked as no-show. "
        f"BU reverted from {old_bu} to NULL (org-wide)"
    )
    return candidate
```

---

## Summary: BU Assignment State Machine

| State | BU Assignment | Visible To | Next Possible States |
|-------|---|---|---|
| **Created** | NULL (org-wide) | All HR users | Submitted |
| **Submitted** | job.BU_ID | BU HR users | Interview, Rejected |
| **Interview** | job.BU_ID | BU HR users | Offer, Rejected |
| **Offer** | job.BU_ID | BU HR users | Onboarding, Declined |
| **Rejected** | NULL (org-wide) | All HR users | Submitted (can retry) |
| **Declined** | NULL (org-wide) | All HR users | Submitted (can retry) |
| **Onboarding** | job.BU_ID | BU HR users | Joined, No Show |
| **Joined** | job.BU_ID | BU HR users | → Employee (convert) |
| **No Show** | NULL (org-wide) | All HR users | Submitted (can retry) |
| **Employee** | employee.BU_ID | BU HR users | (Employee lifecycle) |

---

## Implementation Checklist

### Create/Update Endpoints

- [ ] **Create Candidate**
  - [ ] Default: `business_unit_id = NULL`
  - [ ] Endpoint: `POST /candidates`
  
- [ ] **Assign Candidate to Job**
  - [ ] Set: `candidate.business_unit_id = job.business_unit_id`
  - [ ] Endpoint: `PUT /jobs/{job_id}/assign-candidate/{candidate_id}`
  
- [ ] **Reject Candidate**
  - [ ] Set: `candidate.business_unit_id = NULL`
  - [ ] Endpoint: `POST /interviews/{interview_id}/reject`
  
- [ ] **Decline Offer**
  - [ ] Set: `candidate.business_unit_id = NULL`
  - [ ] Endpoint: `POST /offers/{offer_id}/decline`
  
- [ ] **Mark No-Show**
  - [ ] Set: `candidate.business_unit_id = NULL`
  - [ ] Endpoint: `POST /candidates/{id}/mark-no-show`
  
- [ ] **Convert to Employee**
  - [ ] Preserve: `employee.business_unit_id = candidate.business_unit_id`
  - [ ] Endpoint: `POST /employees/convert-from-candidate`

### Frontend Updates

- [ ] Show candidate BU in details view (NULL = "Org-wide")
- [ ] Show BU change history in candidate timeline
- [ ] Warn recruiters when they try to submit candidate without a BU

### Testing

- [ ] Test: Create candidate → BU is NULL ✓
- [ ] Test: Submit to Job → BU becomes job's BU ✓
- [ ] Test: Reject interview → BU reverts to NULL ✓
- [ ] Test: Decline offer → BU reverts to NULL ✓
- [ ] Test: Convert to employee → preserves BU ✓
- [ ] Test: New candidate visible to all BUs ✓
- [ ] Test: Submitted candidate visible only to job's BU ✓
- [ ] Test: Rejected candidate visible to all BUs again ✓

---

## Why This Matters

**Without BU Assignment:**
- Recruiter A submits candidate to Job X
- Recruiter B in different BU could see and reuse same candidate
- Candidate gets duplicate interviews
- Confusion about who "owns" the candidate

**With BU Assignment:**
- Recruiter A submits candidate to Job X (BU locked)
- Recruiter B in different BU CANNOT see this candidate (filtered by BU)
- Recruiter B can submit SAME PERSON to Job Y in their own BU (creates new candidate record)
- Clear ownership and tracking per BU
- If candidate rejects or doesn't join → back to org-wide pool for anyone to use

---

## Code Example: Full Candidate Flow

```python
# 1. Create candidate (org-wide)
candidate = Candidate(
    id=str(uuid.uuid4()),
    candidate_name="Jane Doe",
    candidate_email="jane@example.com",
    business_unit_id=None,  # ✅ Start org-wide
    status="Created",
    tenant_id=1
)
db.add(candidate)
db.commit()

# 2. Submit to job (lock to job's BU)
job = db.query(Job).filter(Job.id == job_id).first()  # job.business_unit_id = 1
candidate.business_unit_id = job.business_unit_id  # ✅ Set to 1
candidate.status = "Submitted"
db.commit()

# 3a. If rejected (revert to org-wide)
candidate.business_unit_id = None  # ✅ Back to NULL
candidate.status = "Rejected"
db.commit()

# 3b. If accepted and moves to offer (stay on BU)
candidate.status = "Offer"
db.commit()  # business_unit_id still = 1

# 4. Convert to employee (preserve BU)
employee = Users(
    UserID=str(uuid.uuid4()),
    UserName=candidate.candidate_name,
    UserEmail=candidate.candidate_email,
    business_unit_id=candidate.business_unit_id,  # ✅ Preserve = 1
    tenant_id=1
)
db.add(employee)
db.commit()

candidate.status = "Converted to Employee"
candidate.candidate_employee_user_id = employee.UserID
db.commit()
```

---

## Notes

- **Default on creation**: Always `NULL` (org-wide)
- **Lock on job submission**: Set to `job.business_unit_id`
- **Unlock on rejection/decline/no-show**: Revert to `NULL`
- **Preserve on employee conversion**: Keep the BU assignment
- **Visibility**: Candidates with `NULL` BU visible to all; with BU_ID visible only to that BU
- **Org-wide candidates**: Those without a BU are freely available to any BU to use
