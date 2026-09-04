from pydantic import BaseModel, EmailStr, constr, Field
from typing import Optional, List
import logging
from datetime import datetime, date
from app.core.logging import logger

# Candidate Assignment Schemas
class CandidateAssignmentCreate(BaseModel):
    candidate_id: str
    hiring_manager_id: Optional[str] = None
    reporting_manager_id: Optional[str] = None
logger = logging.getLogger(__name__)

class CandidateAssignmentResponse(BaseModel):
    id: int
    candidate_id: str
    hiring_manager_id: str | None = None
    reporting_manager_id: str | None = None
    created_at: datetime

# Interview Panel Schemas
class InterviewPanelCreate(BaseModel):
    candidate_id: str
    round_name: str  # HR, Tech, Manager

class InterviewPanelResponse(BaseModel):
    id: int
    candidate_id: str
    round_name: str
    created_at: datetime

# Panel Member Schemas
class PanelMemberCreate(BaseModel):
    panel_id: int
    interviewer_id: str

class PanelMemberResponse(BaseModel):
    id: int
    panel_id: int
    interviewer_id: str

# Interview Schemas
class InterviewCreate(BaseModel):
    panel_id: int
    candidate_id: str
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: str = "Scheduled"  # Scheduled, Completed, Cancelled

class InterviewResponse(BaseModel):
    id: int
    panel_id: int
    candidate_id: str
    start_time: datetime
    end_time: datetime
    meeting_link: str | None = None
    outlook_event_id: str | None = None
    status: str

# Interview Feedback Schemas
class InterviewFeedbackCreate(BaseModel):
    interview_id: int
    interviewer_id: str
    technical_score: int
    communication_score: int
    problem_solving_score: int
    culture_fit_score: int
    comments: Optional[str] = None
    recommendation: str  # Hire / Hold / Reject

class InterviewFeedbackResponse(BaseModel):
    id: int
    interview_id: int
    interviewer_id: str
    technical_score: int
    communication_score: int
    problem_solving_score: int
    culture_fit_score: int
    comments: str | None = None
    recommendation: str
    submitted_at: datetime

# GET Response Schemas
class AssignedCandidateResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_mobile: str | None = None
    assignment_type: str  # "hiring_manager" or "reporting_manager"
    assigned_at: datetime

class AssignedInterviewResponse(BaseModel):
    interview_id: int
    candidate_id: str
    candidate_name: str
    panel_id: int
    round_name: str
    start_time: datetime
    end_time: datetime
    meeting_link: str | None = None
    status: str

# User Response Schema
class UserResponse(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    user_role: str
    job_title: Optional[str] = None
    role_template_id: Optional[int] = None
    permission_role: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    business_unit_id: Optional[int] = None
    business_unit_name: Optional[str] = None
    created_at: datetime

class AllUsersResponse(BaseModel):
    total_users: int
    users: list[UserResponse]

# Job Schemas
class JobCreateRequest(BaseModel):
    job_title: str
    job_description: str
    job_skills: str
    job_experience: str
    job_location: str
    company_type: str
    company_name: str
    # Optional: not a manually-entered field on the Create Job screen
    # (auto-populated from the selected business unit's HR assignment,
    # when one exists) -- must not block job creation when absent.
    contact_person: Optional[str] = None
    job_status: str
    no_of_positions: Optional[int] = None
    salary_range: Optional[str] = None
    recuriter_id: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    business_unit: Optional[int] = None
    department_id: Optional[int] = None
    start_date: Optional[date] = None

class JobCreateResponse(BaseModel):
    job_id: str
    response: str

class JobResponse(BaseModel):
    job_id: str
    job_title: str
    job_description: str
    job_skills: str
    job_experience: str
    job_location: str
    job_created_at: datetime
    company_type: Optional[str] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_person_name: Optional[str] = None
    job_status: Optional[str] = None
    no_of_positions: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    hiring_manager_id: Optional[str] = None
    hiring_manager_name: Optional[str] = None
    recuriter_id: Optional[str] = None
    business_unit: Optional[int] = None
    department_id: Optional[int] = None
    salary_range: Optional[str] = None
    required_skills_canonical: Optional[list] = None
    job_skills_boolean_mode: Optional[str] = None

class AllJobsResponse(BaseModel):
    total_jobs: int
    jobs: list[JobResponse]

# ── Candidate ↔ Job mapping schemas ──────────────────────────────────────────

class CandidateJobAssignRequest(BaseModel):
    """Body for PUT /{job_id}/assign-candidate/{candidate_id}"""
    job_id: Optional[str] = None  # allows re-assignment or removal (None = unlink)

class CandidateJobSummary(BaseModel):
    """Lightweight candidate info returned when listing candidates for a job."""
    candidate_id: str
    candidate_first_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    candidate_email: str
    candidate_mobile: Optional[str] = None
    candidate_experience: Optional[str] = None
    candidate_current_location: Optional[str] = None
    job_id: Optional[str] = None

class CandidatesByJobResponse(BaseModel):
    job_id: str
    job_title: str
    total_candidates: int
    candidates: list[CandidateJobSummary]

# ── Multi-Job Application schemas (many-to-many) ──────────────────────────────

class JobApplicationCreate(BaseModel):
    """Assign a candidate to a job (many-to-many)."""
    application_status: Optional[str] = "Applied"

class JobApplicationStatusUpdate(BaseModel):
    """Update the per-application status."""
    application_status: str

class JobApplicationEntry(BaseModel):
    """Single row in candidate_job_applications."""
    id: int
    candidate_id: str
    job_id: str
    job_title: Optional[str] = None
    application_status: Optional[str] = None
    applied_at: datetime

class CandidateJobsResponse(BaseModel):
    """All jobs a candidate is linked to."""
    candidate_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    total_jobs: int
    applications: List[JobApplicationEntry]

class JobCandidatesMultiResponse(BaseModel):
    """All candidates linked to a specific job (many-to-many)."""
    job_id: str
    job_title: str
    total_candidates: int
    applications: List[JobApplicationEntry]

# ── Job Statistics schema ─────────────────────────────────────────────────────

class ApplicationStatusCount(BaseModel):
    """Count of applications for a single status value."""
    status: str
    count: int

class JobStatisticsResponse(BaseModel):
    """Aggregated statistics for a single job posting."""
    job_id: str
    job_title: str
    job_status: str
    total_applications: int
    # Named convenience counts — most commonly needed at a glance
    applied: int
    shortlisted: int
    interview: int
    offered: int
    hired: int
    rejected: int
    # Full per-status breakdown (covers any custom statuses too)
    status_breakdown: List[ApplicationStatusCount]

class JobApproveResponse(BaseModel):
    job_id: str
    status: str
    message: str
    approved_by: str

class GenerateJobDescriptionRequest(BaseModel):
    job_title: str
    job_description: str
    job_experience: str
    job_location: str

class GenerateJobDescriptionResponse(BaseModel):
    job_title: str
    generated_job_description: str
    job_skills: list[str]
    job_experience: str
    job_location: str

# Agent-based Job Creation Schemas
class ClarifyingQuestion(BaseModel):
    field: str
    question: str
    options: Optional[list[str]] = None
    required: bool = True
    type: str = "text"  # text, select, date

class GenerateJobWithAgentRequest(BaseModel):
    job_description_oneliner: str

class GenerateJobWithAgentResponse(BaseModel):
    job_title: str
    estimated_experience: str
    questions: list[ClarifyingQuestion]

class GenerateJobCompleteRequest(BaseModel):
    job_description_oneliner: str
    answers: dict[str, str]  # field -> user answer

class GenerateJobCompleteResponse(BaseModel):
    job_title: str
    generated_job_description: str
    job_skills: list[str]
    job_experience: str
    job_location: str
    position_type: str
    pay_range: str
    job_open_date: Optional[str] = None
    contract_duration: Optional[str] = None
    role_type: Optional[str] = None
    client_name: Optional[str] = None

# Update Schemas
class JobUpdateRequest(BaseModel):
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    job_skills: Optional[str] = None
    job_experience: Optional[str] = None
    job_location: Optional[str] = None
    company_type: Optional[str] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    job_status: Optional[str] = None
    no_of_positions: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    salary_range: Optional[str] = None
    recuriter_id: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    business_unit: Optional[int] = None
    department_id: Optional[int] = None

class CandidateUpdateRequest(BaseModel):
    candidate_first_name: Optional[str] = None
    candidate_middle_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    candidate_mobile: Optional[str] = None
    candidate_gender: Optional[str] = None
    candidate_date_of_birth: Optional[date] = None
    candidate_source: Optional[str] = None
    candidate_experience: Optional[str] = None
    candidate_skills: Optional[str] = None
    candidate_joining_date: Optional[date] = None
    candidate_expected_salary: Optional[str] = None
    candidate_current_salary: Optional[str] = None
    candidate_current_location: Optional[str] = None
    candidate_job_title: Optional[str] = None
    # Employee type: "Intern" | "Full Time Employee" | "Guidewire"
    candidate_employee_type: Optional[str] = None
    assigned_hr_manager_id: Optional[str] = None
    assigned_report_manager_id: Optional[str] = None

class InterviewUpdateRequest(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_link: Optional[str] = None
    outlook_event_id: Optional[str] = None
    status: Optional[str] = None

class DeleteResponse(BaseModel):
    status: str = "Success"
    message: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class AdminResetPasswordRequest(BaseModel):
    """Admin-only password reset - no current password required"""
    new_password: str

class HrMeResponse(BaseModel):
    user_id: str
    user_name: Optional[str]
    user_email: str
    user_role: str
    job_title: Optional[str] = None
    permission_role: Optional[str] = None
    role_template_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    created_at: datetime
    access_token: str
    token_type: str = "bearer"
    digest_enabled: bool = True  # S-065/HRMS-0465

class DigestPreferenceRequest(BaseModel):
    digest_enabled: bool

class DigestPreferenceResponse(BaseModel):
    digest_enabled: bool

# LinkedIn Job Posting Schemas
class LinkedInPostRequest(BaseModel):
    job_id: str

class LinkedInPostResponse(BaseModel):
    status: str
    message: str
    # No real LinkedIn API integration exists yet -- always True today.
    # Added so any API consumer (not just this one screen's toast) can
    # tell honestly that nothing actually went live on LinkedIn, rather
    # than relying on parsing "(Mock)" out of the human-readable message.
    is_simulated: bool = True
    linkedin_post_id: str
    posted_at: datetime
    job_details: JobResponse

# Offer Letter Schemas
class OfferLetterCreateRequest(BaseModel):
    candidate_id: str
    job_id: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    reporting_manager_id: Optional[str] = None
    position: str
    salary: str
    joining_date: date
    offer_expire_date: date

class OfferLetterUpdateRequest(BaseModel):
    # ── Core offer fields ─────────────────────────────────────────────────────
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    reporting_manager_id: Optional[str] = None
    position: Optional[str] = None
    salary: Optional[str] = None
    joining_date: Optional[date] = None
    offer_expire_date: Optional[date] = None

    # ── Status overrides (HR manual control) ─────────────────────────────────
    offer_status: Optional[str] = None
    candidate_response: Optional[str] = None
    responded_at: Optional[datetime] = None

    # ── Document links (manual correction / re-generation) ───────────────────
    sharepoint_url: Optional[str] = None
    download_url: Optional[str] = None
    sharepoint_path: Optional[str] = None

    # ── Approval workflow fields ──────────────────────────────────────────────
    approval_status: Optional[str] = None
    approval_notes: Optional[str] = None

class OfferLetterResponse(BaseModel):
    id: int
    candidate_id: str
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_id: str | None = None
    hiring_manager_id: str | None = None
    reporting_manager_id: str | None = None
    position: str
    salary: str
    joining_date: date
    offer_expire_date: date
    offer_status: str
    candidate_response: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    created_by: str
    cancelled_at: datetime | None = None
    cancelled_by: str | None = None
    # Document links (populated after offer letter is generated)
    sharepoint_url: str | None = None
    download_url: str | None = None
    sharepoint_path: str | None = None
    # Approval workflow fields
    approval_status: str | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    approval_notes: str | None = None
    # Release tracking
    released_at: datetime | None = None
    released_by: str | None = None
    # Signature paths
    hm_signature_path: str | None = None
    candidate_signature_path: str | None = None
    signed_offer_path: str | None = None

class CreateUserWithRolesRequest(BaseModel):
    """
    Request schema for creating a new user with RBAC role template and org hierarchy.

    Required Fields:
    - user_name: User's display name (required)
    - user_email: User's email address (required, unique within tenant)
    - user_password: Initial password (required, min 8 chars)
    - role_template_id: RBAC role template ID (required)
    - hierarchy_level: Org hierarchy level 1-17 (required) - see ORG_HIERARCHY_LEVELS.md
    - specialization: Specialization domain (required) - Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis

    Optional Fields:
    - job_title: User's job position
    - business_unit_id: Primary business unit assignment
    - partner_id: Optional partner assignment
    - parent_node_id: Org hierarchy - who this person reports to (validated against hierarchy rules)

    ❌ DEPRECATED FIELDS (DO NOT USE):
    - user_role: Use role_template_id instead
    - password: Misspelling of user_password

    Schema Validation:
    - extra='forbid': Rejects unknown/deprecated fields with 422 error
    - validate_default: Validates defaults on assignment
    - hierarchy_level must be 1-17
    - specialization must be from approved list

    Example:
        {
            "user_name": "John Doe",
            "user_email": "john@example.com",
            "user_password": "SecurePassword123!",
            "job_title": "Senior Consultant",
            "role_template_id": 3,
            "business_unit_id": 1,
            "hierarchy_level": 5,
            "specialization": "Recruitment",
            "parent_node_id": "hiring-manager-uuid"
        }
    """
    user_name: str = Field(..., min_length=1, max_length=255, description="User's display name")
    user_email: str = Field(..., max_length=255, description="User's unique email within tenant")
    user_password: str = Field(..., min_length=8, max_length=255, description="Initial password (min 8 chars)")
    role_template_id: int = Field(..., gt=0, description="RBAC role template ID (e.g., 1=SuperUser, 3=Recruiter)")
    hierarchy_level: int = Field(..., ge=1, le=17, description="Org hierarchy level: 1 (Intern) to 17 (CEO) - MANDATORY")
    specialization: str = Field(..., min_length=1, max_length=100, description="Specialization domain (Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis) - MANDATORY")
    job_title: Optional[str] = Field(None, max_length=255, description="User's job position")
    partner_id: Optional[int] = Field(None, gt=0, description="Optional partner ID")
    business_unit_id: Optional[int] = Field(None, gt=0, description="Primary business unit ID")
    parent_node_id: Optional[str] = Field(None, description="Org hierarchy: who this person reports to (validated by org_hierarchy_validator)")

    class Config:
        extra = 'forbid'  # STRICT: Reject any unknown fields (catches deprecated fields)
        validate_default = True
        json_schema_extra = {
            "version": "1.0",
            "deprecated_fields": ["user_role (use role_template_id)", "password (use user_password)"],
            "notes": "Do NOT attempt to pass user_role or password fields - schema will reject with 422 error"
        }

class UpdateUserWithRolesRequest(BaseModel):
    """
    Request schema for updating user account with RBAC role template.

    THIS SCHEMA USES role_template_id FOR RBAC, NOT DEPRECATED user_role FIELD.

    Optional Fields (all optional, update only what's needed):
    - user_name: User's display name (max 255 chars)
    - user_email: User's email (max 255 chars)
    - job_title: User's job position (max 255 chars)
    - business_unit_id: Primary business unit (must be > 0)
    - role_template_id: RBAC role template ID (must be > 0)
    - partner_id: Partner assignment (must be > 0)
    - assigned_at: ISO 8601 timestamp for role assignment

    ❌ DEPRECATED FIELDS (DO NOT USE):
    - user_role: REMOVED - use role_template_id instead
    - user_password: Use password reset endpoint instead
    - UserID: Read-only, cannot be updated
    - CreatedAt: Audit field, immutable

    Schema Validation Rules:
    - extra='forbid': ANY deprecated field is REJECTED with HTTP 422
    - Field lengths: Enforced (user_name max 255, job_title max 255)
    - IDs: Must be positive integers (gt=0)
    - No empty strings allowed (min_length=1 for strings)

    Example Valid Request:
        {
            "job_title": "Senior Consultant",
            "role_template_id": 3,
            "business_unit_id": 1
        }

    Example Invalid Request (will be rejected):
        {
            "user_role": "Admin"  ← DEPRECATED, returns 422
        }

    Endpoint Behavior:
    - If tenant_id is NULL, auto-assigns current_user.tenant_id
    - Only provided fields are updated (partial update supported)
    - Response includes updated UserResponse with all fields
    """
    user_name: Optional[str] = Field(None, min_length=1, max_length=255, description="User's display name (1-255 chars)")
    user_email: Optional[str] = Field(None, max_length=255, description="User's email (unique within tenant)")
    job_title: Optional[str] = Field(None, max_length=255, description="User's job position/title")
    partner_id: Optional[int] = Field(None, gt=0, description="Partner ID (must be > 0)")
    business_unit_id: Optional[int] = Field(None, gt=0, description="Business unit ID (must be > 0)")
    role_template_id: Optional[int] = Field(None, gt=0, description="RBAC role template ID (must be > 0, e.g., 1=SuperUser, 3=Recruiter)")
    assigned_at: Optional[str] = Field(None, description="ISO 8601 timestamp for role assignment")

    class Config:
        extra = 'forbid'  # CRITICAL: Reject ANY unknown fields (catches typos, deprecated fields)
        validate_default = True  # Validate even None values
        json_schema_extra = {
            "version": "2.0",
            "critical_note": "Do NOT use deprecated user_role field - it will be rejected with HTTP 422",
            "deprecated_fields": [
                "user_role (REMOVED - use role_template_id instead)",
                "user_password (use POST /password-reset instead)",
                "UserID (read-only)",
                "CreatedAt (audit field, immutable)"
            ],
            "auto_fix": "If user has NULL tenant_id, endpoint auto-assigns current_user.tenant_id"
        }

class OfferAcceptanceRequest(BaseModel):
    offer_id: int
    action: str  # "accept" or "reject"
    response_message: Optional[str] = None

class OfferAcceptanceResponse(BaseModel):
    status: str
    message: str
    offer_id: int
    offer_status: str
    responded_at: datetime

class OfferCancelRequest(BaseModel):
    reason: Optional[str] = None

class AllOffersResponse(BaseModel):
    total_offers: int
    offers: list[OfferLetterResponse]

# ── Offer Approval (Hiring Manager) ──────────────────────────────────────────

class OfferApprovalResponse(BaseModel):
    status: str
    message: str
    offer_id: int
    approval_status: str
    approved_at: Optional[datetime] = None

# ── Offer Release (HR releases to candidate) ──────────────────────────────────

class OfferReleaseResponse(BaseModel):
    status: str
    message: str
    offer_id: int
    offer_status: str
    released_at: datetime

# ── Candidate Signature + Acceptance ─────────────────────────────────────────

class CandidateSignedAcceptanceResponse(BaseModel):
    status: str
    message: str
    offer_id: int
    offer_status: str
    signed_offer_path: Optional[str] = None

# ── User Section ─────────────────────────────────────────────────────────────

class SingleUserResponse(BaseModel):
    """Full profile of a single internal user."""
    user_id: str
    user_name: Optional[str]
    user_email: str
    user_role: str
    job_title: Optional[str] = None
    permission_role: Optional[str] = None
    role_template_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    created_at: datetime

# ── Hiring Manager Section ────────────────────────────────────────────────────

class HiringManagerAssignedCandidateResponse(BaseModel):
    """Candidate assigned to the authenticated hiring manager."""
    assignment_id: int
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_mobile: Optional[str] = None
    candidate_job_title: Optional[str] = None
    candidate_experience: Optional[str] = None
    candidate_current_location: Optional[str] = None
    candidate_joining_date: Optional[date] = None
    candidate_expected_salary: Optional[str] = None
    candidate_current_salary: Optional[str] = None
    candidate_is_verified: Optional[bool] = None
    pipeline_status: Optional[str] = None
    assigned_at: datetime
