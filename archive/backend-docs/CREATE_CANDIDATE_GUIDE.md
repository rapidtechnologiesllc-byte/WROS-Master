# Create Candidate - Complete Implementation Guide

**Status:** ✅ Ready to test  
**Integration Level:** Phase 2-4 compliant  
**Last Updated:** 2026-08-16

---

## Overview

The "Create Candidate" workflow enables HR users to add new candidates to the system with:
- Multi-field form validation
- Resume upload and parsing
- Automatic Thunder AI agent assignment
- Permission-based access control
- Email notifications

---

## Permission Requirements

### Required Permissions
```
recruitment.view  - Ability to access recruitment section
candidate.create  - Ability to create new candidates
```

### Role Mapping
**Who can create candidates:**
- ✅ Super User (admin.manage implies candidate.*)
- ✅ Admin (admin.manage)
- ✅ Recruiter/Senior Recruiter (recruitment.manage)
- ✅ HR Manager (candidate.create)
- ❌ Finance, Partner, BU Head (no candidate.create permission)

---

## Frontend Form Structure

### File
`src/screens/CandidateCreate.js`

### Form Sections

#### 1. Basic Information
Required fields:
- **First Name** - Text input
- **Last Name** - Text input (required)
- **Email** - Email input (required, must be unique)
- **Mobile** - Phone with country code selector
  - Country codes: +91, +1, +44, +61, +971, +65, +49, +63
  - Mobile is stored with country code (e.g., +919876543210)
- **Gender** - Dropdown (Male, Female, Other, Prefer not to say)
- **Date of Birth** - Date picker
- **Current Location** - City, State, Country cascade select (required)

#### 2. Professional Information
Optional fields:
- **Job Title** - Text input
- **Experience** - Number input (years)
- **Source** - Dropdown (LinkedIn, Referral, Direct, etc.)
- **Current Salary** - Number input
- **Expected Salary** - Number input
- **Joining Date** - Date picker

#### 3. Attachments
- **Resume Upload** - Accept .pdf, .doc, .docx
  - Auto-extract education, experience, skills
  - Auto-populate relevant form fields

#### 4. Education (Auto-populated from Resume)
- Institution Name
- Degree
- Field of Study
- Start Date
- End Date
- Percentage

#### 5. Experience (Auto-populated from Resume)
- Company Name
- Job Title
- Start Date
- End Date

#### 6. Skills (Auto-populated from Resume)
- Skill Name
- Years of Experience
- Last Used Date
- Primary Skill (checkbox)

#### 7. Send Login Email
- Checkbox: Send login credentials email to candidate

---

## Backend Endpoint

### POST `/candidates/create`

**Authentication:** Required (HR or Admin user)

**Request Body:**
```json
{
  "candidate_first_name": "John",
  "candidate_middle_name": "",
  "candidate_last_name": "Doe",
  "candidate_email": "john.doe@example.com",
  "candidate_mobile": "+919876543210",
  "candidate_gender": "Male",
  "candidate_date_of_birth": "1990-05-15",
  "candidate_current_location": "Bangalore, Karnataka, India",
  "candidate_job_title": "Software Engineer",
  "candidate_experience": 5,
  "candidate_source": "LinkedIn",
  "candidate_current_salary": 80000,
  "candidate_expected_salary": 100000,
  "candidate_joining_date": "2026-09-01",
  "candidate_skills": "Python, JavaScript, React",
  "send_login_email": true,
  "education_records": [
    {
      "education_institute": "IIT Bangalore",
      "degree": "B.Tech",
      "field_of_study": "Computer Science",
      "starting_year": 2014,
      "year_of_passing": 2018,
      "percentage": 8.5
    }
  ],
  "experience_records": [
    {
      "company_name": "Tech Company A",
      "job_title": "Software Engineer",
      "start_date": "2018-06-01",
      "end_date": "2021-05-31",
      "year_of_experience": 3
    }
  ]
}
```

**Response:**
```json
{
  "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_first_time": true,
  "generated_password": "TempPassword123!",
  "message": "Candidate created successfully"
}
```

**Error Cases:**
- `400 Bad Request` - Duplicate email, missing location, validation error
- `401 Unauthorized` - Not authenticated or no recruitment.view permission
- `403 Forbidden` - No candidate.create permission
- `500 Server Error` - Database or resume parsing error

---

## Key Features

### 1. Email Uniqueness Check
- Every candidate email must be unique
- System checks against all existing candidates
- Returns 400 error if duplicate found

### 2. Resume Parsing & Auto-Population
**Process:**
1. User uploads resume (PDF/DOC/DOCX)
2. System extracts text from resume
3. AI infers fields using Gemini API:
   - Job title
   - Skills
   - Experience (years)
   - Education details
   - Company history
4. Auto-populate form fields
5. User can edit before saving

**Fallback:** If parsing fails, form shows error but doesn't block creation

### 3. Thunder AI Agent Auto-Assignment
**Timing:** Immediately after candidate created
**What happens:**
- Candidate assigned to Thunder AI recruiter
- Thunder begins autonomous candidate intake conversation
- Candidate receives WhatsApp notification (via Thunder)
- No manual recruiter action needed

**Implementation:**
- Endpoint calls `assign_ai_agent(candidate_id, tenant_id)`
- Uses background task queue for async processing
- Logs assignment in activity feed

### 4. Login Email Notification
**When:** If "Send Login Email" checkbox checked
**Content:**
- Candidate email address
- Temporary password
- Login portal URL
- Thunder AI recruiter introduction

**Delivery:** Background task via SMTP

### 5. Candidate Status Initialization
**On Creation:**
- Status: "Active"
- Pipeline Stage: "Applied"
- Created timestamp recorded
- Available for Thunder matching

---

## Data Validation Rules

| Field | Rule | Error Message |
|-------|------|---------------|
| Email | Must be unique, valid format | "Email already exists" or "Invalid email" |
| Mobile | Format with country code | "+919876543210" or "+1-234-567-8900" |
| Location | City, State, Country required | "Location is mandatory" |
| First Name | Optional, max 50 chars | "Name too long" |
| Last Name | Optional, max 50 chars | "Name too long" |
| Experience | Optional, number 0-70 | "Experience must be 0-70 years" |
| Joining Date | Optional, YYYY-MM-DD format | "Invalid date format" |
| Skills | Optional, comma-separated | Auto-split on submit |

---

## Integration with Phase 2-4 Features

### Phase 2: Candidate Isolation
**Feature:** Candidates locked to Business Unit on submission
**Impact on Create:**
- Candidate created as "unassociated" (no BU set yet)
- Visible to all HR users during intake
- Lock happens on job submission (not creation)
- Related feature: `CandidateIsolationService`

### Phase 3: Audit Logging
**What's logged:**
- Candidate creation timestamp
- Creator user ID
- Fields created
- Resume uploaded (yes/no)

**Query:** Check `audit_log` table with entity_type="candidate"

### Phase 4: Admin UI
**Related feature:** Role template management
**Connection:** Recruiters have "recruitment.manage" permission
- Enables "recruitment.view" + "candidate.create"
- Set via Admin UI role templates
- No changes needed to Create Candidate workflow

### Thunder AI Agent Assignment
**Automatic on creation:**
- Candidate enters Thunder autonomous queue
- Thunder starts intake conversation
- No manual assignment needed
- Related feature: Thunder autonomous system

---

## User Workflow (Step-by-Step)

### 1. Navigate to Create Candidate
```
Navigation → Recruitment → Add Candidate
```
(Only visible if user has recruitment.view permission)

### 2. Fill Basic Information
- Enter required fields: Last Name, Email, Location
- Enter optional fields: First Name, Mobile, Gender, DOB
- System validates in real-time

### 3. Upload Resume (Optional)
- Click "Upload Resume"
- Select PDF/DOC/DOCX file
- System parses and auto-fills:
  - Job title
  - Experience years
  - Skills
  - Education
- User reviews and can edit

### 4. Add Professional Information
- Job Title (if not auto-filled)
- Experience years
- Source (where you found them)
- Current salary
- Expected salary
- Joining date

### 5. Add Education (Optional)
- Can be auto-populated from resume
- Manually add if resume didn't extract
- Institute, degree, field of study, dates

### 6. Add Experience (Optional)
- Can be auto-populated from resume
- Manually add if resume didn't extract
- Company, title, dates

### 7. Add Skills (Optional)
- Can be auto-populated from resume
- Set primary skill (checkbox)
- Years of experience per skill

### 8. Review & Submit
- Review all entered data
- Check "Send Login Email" if needed
- Click "Create Candidate"
- System:
  - Creates candidate account
  - Generates temporary password
  - Assigns to Thunder AI
  - Sends email (if checked)
  - Shows success message with candidate ID

### 9. Next Steps
- Candidate enters Thunder intake queue
- Recruiter can start Thunder conversation
- Candidate can log in and complete profile
- Candidate available for job submissions

---

## Error Handling

### Common Errors

**1. Duplicate Email**
```
Error: Account already exists with email john@example.com
Action: User must use different email or search for existing candidate
```

**2. Missing Location**
```
Error: Location (City, State, Country) is mandatory
Action: User must select location from cascade dropdown
```

**3. Invalid Email Format**
```
Error: Invalid email format
Action: User must enter valid email (e.g., user@domain.com)
```

**4. Resume Parse Failure**
```
Warning: Could not parse resume (showing UI toast)
Action: User can continue with manual entry or re-upload
```

**5. Duplicate Mobile Number**
```
Error: Mobile number already registered
Action: User can enter different number or skip field
```

---

## Testing Checklist

### Unit Tests (Backend)
- [ ] Valid candidate creation with all fields
- [ ] Valid candidate creation with minimal fields
- [ ] Duplicate email rejection
- [ ] Invalid email format rejection
- [ ] Missing location rejection
- [ ] Resume parsing success
- [ ] Resume parsing failure (graceful)
- [ ] Thunder agent assignment
- [ ] Email notification sent
- [ ] Candidate status initialized

### Integration Tests (Frontend + Backend)
- [ ] Form submit calls correct endpoint
- [ ] Permission check blocks unauthorized users
- [ ] Resume upload and auto-fill works
- [ ] Form validation shows error messages
- [ ] Success message shows candidate ID
- [ ] Redirect to candidate details after creation
- [ ] Thunder assignment verified in activity feed
- [ ] Login email received by candidate

### E2E Tests (Full Workflow)
- [ ] HR creates candidate with resume
- [ ] Candidate receives login email
- [ ] Candidate logs in with generated password
- [ ] Thunder starts autonomous conversation
- [ ] Recruiter can see candidate in Thunder queue
- [ ] Candidate can update profile before submission
- [ ] Candidate visible for job matching

### Edge Cases
- [ ] Very long names (100+ chars)
- [ ] Special characters in names (ñ, é, etc.)
- [ ] Non-standard phone numbers
- [ ] Very old DOB (70+ years)
- [ ] Future joining date (after today)
- [ ] Resume with no extractable data
- [ ] Bulk creation (multiple in succession)

---

## Performance Notes

### Database Queries
- Email uniqueness check: Indexed on candidate_email
- Candidate creation: Single insert + status + personal_info
- Education/Experience: Bulk insert (batch)
- Total queries per creation: 4-6

### Resume Parsing
- Extraction: 1-3 seconds (file size dependent)
- AI inference: 2-5 seconds (Gemini API call)
- Total: 3-8 seconds
- Timeout: 30 seconds (if exceeds, user shown warning)

### Background Tasks
- Email sending: 2-5 seconds (SMTP)
- Thunder assignment: 1-2 seconds (database + messaging)
- Activity log: <100ms

---

## Security & Compliance

### Data Protection
- ✅ Passwords hashed with bcrypt
- ✅ Temporary password is secure random
- ✅ Email delivery over TLS
- ✅ Candidate data encrypted in transit

### Access Control
- ✅ Permission required (recruitment.view + candidate.create)
- ✅ Tenant scoped (can't create for other tenants)
- ✅ Audit logged (who created, when)

### Privacy
- ✅ GDPR compliant (can request deletion)
- ✅ Data retention policy enforced
- ✅ Resume stored in secure storage (Azure Blob)

---

## Troubleshooting

### Resume Won't Upload
- Check file format (must be PDF/DOC/DOCX)
- Check file size (should be < 10MB)
- Try uploading a different resume

### Auto-fill Not Working
- Resume might not have standard format
- Manual entry of fields is always available
- Try uploading a simpler resume

### No Email Sent
- Check "Send Login Email" checkbox
- Verify SMTP is configured on server
- Check email logs in admin panel

### Candidate Not in Thunder Queue
- Check if Thunder feature is enabled
- Verify Thunder service status
- Check activity log for assignment errors

### Thunder Not Responding
- Candidate might not have WhatsApp
- Check if candidate's mobile includes country code
- Verify Thunder service is running

---

## Success Criteria

✅ Candidate created successfully when:
1. All required fields provided and valid
2. Email is unique in system
3. Location selected from cascade dropdown
4. Candidate record created in database
5. Candidate status set to "Active"
6. Thunder AI agent assigned
7. Login email sent (if requested)
8. Activity log entry created
9. User sees success message with candidate ID

---

## Related Features

- **Thunder AI Recruiter** - Auto-assignment and intake
- **Candidate Isolation** - BU locking on submission
- **Resume Parsing** - Extract education/experience/skills
- **Permission-Based Access** - RBAC for who can create
- **Email Notifications** - Send login credentials
- **Activity Feed** - Log all candidate events
- **Candidate Portal** - Self-service profile completion

---

## Quick Start for Developers

### Running Locally
```bash
# Backend
cd OnboardingModule-Backend
export DATABASE_URL="postgresql://postgres:123@localhost:5432/wros_dev"
python -m uvicorn app.main:app --reload

# Frontend
cd OnboardingModule-Frontend
npm start
```

### Testing API Directly
```bash
# Create candidate
curl -X POST http://localhost:8000/candidates/create \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_email": "test@example.com",
    "candidate_last_name": "Test",
    "candidate_current_location": "Bangalore, Karnataka, India"
  }'
```

### Check Candidate Created
```bash
# Backend logs show:
# [INFO] Candidate created: 550e8400-e29b-41d4-a716-446655440000
# [INFO] Thunder assignment: success
# [INFO] Email sent to: test@example.com
```

---

**Status: Ready for testing**  
**Last Updated: 2026-08-16**
