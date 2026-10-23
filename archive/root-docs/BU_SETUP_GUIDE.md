# Business Unit Setup Guide

## Quick Start - How to Add Business Units

### Step 1: Navigate to Business Units Management
1. Click **Admin** in the left sidebar
2. Look for **Business Units** (we're adding this menu item now)
3. Or go directly to: `http://localhost:3000/admin/business-units`

### Step 2: Create Your First Business Unit
Click **"Add Business Unit"** button and fill in:
- **Name**: e.g., "North America", "Europe", "APAC"
- **Code**: e.g., "NA", "EU", "APAC" (short identifier)
- **Description**: e.g., "North American operations"

### Step 3: Assign Business Units to Users
Two ways to assign:

#### A) When Creating a New User
1. Click **Users & Access Control** → **Add User**
2. Fill user details
3. Select **Business Unit** from dropdown
4. Click **Create User**

#### B) When Editing an Existing User
1. Click **Users & Access Control** → Click Edit icon on user row
2. Scroll to **Business Unit** field (we're adding this now)
3. Select new Business Unit
4. Click **Update User**

## Smart BU Assignment for Candidates

### Business Unit Auto-Assignment Rules

When a candidate is **submitted to a job**, their BU is automatically set to:
1. **Job's Business Unit** (if job has BU assigned)
2. **Primary BU** (persists until candidate no longer active on that job)

### Multi-BU Tracking Logic

**Scenario 1:** Candidate assigned to BU-1, then submitted to BU-2 job
- ✅ Auto-updates candidate BU to BU-2
- ✅ Visual indicator shows "BU changed: BU-1 → BU-2"

**Scenario 2:** Candidate has multiple active jobs (different BUs)
- ✅ Shows PRIMARY BU (most recent job's BU)
- ✅ Displays: "Active on X jobs across Y BUs"

**Scenario 3:** Candidate manually assigned to BU-X, but job is in BU-Y
- ✅ Keeps manual assignment (manual override takes precedence)
- ⚠️ Shows warning: "Manually set to BU-X (Job is in BU-Y)"

**Scenario 4:** Candidate no longer active on any jobs
- ✅ BU assignment persists (for context in future jobs)
- ℹ️ Shows "No active jobs"

## Where BU Assignment Appears

### Candidates Section
- **Candidate Details** → **Users & BU Details** panel
  - Edit to change Recruiter and Business Unit
  - Shows current BU with context

### Users Section
- **Users & Access Control** → **Edit User**
  - Assign or change user's primary Business Unit
  - (We're adding this field to edit modal now)

### Jobs Section
- **Job Details** → BU assignment 
  - Used for auto-assigning candidate BU on submission

## Current Implementation Status

✅ **Done:**
- Business Units management screen created
- Route added: `/admin/business-units`
- Business Unit field in "Create User" modal

🚧 **In Progress:**
- Business Unit field in "Edit User" modal
- Dropdown data mapping (recruiters & BUs)
- Candidate BU auto-assignment from job

📝 **Next:**
- Add Business Units menu item to Admin sidebar
- Test full BU workflow end-to-end

## Testing Checklist

- [ ] Create 2-3 Business Units (NA, EU, APAC)
- [ ] Create users and assign to different BUs
- [ ] Create jobs and assign BUs
- [ ] Submit candidate to job and verify BU auto-assignment
- [ ] Edit existing candidate and change BU manually
- [ ] Verify Recruiter dropdown populated with "Recruiter" role users
- [ ] Verify candidate BU context shows in details panel
