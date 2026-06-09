# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime, date
from pydantic import Field

# Candidate schemas
class CandidateCreateRequest(BaseModel):
    # Required fields
    candidate_email: EmailStr
    
    # Role (optional, defaults to "Candidate")
    candidate_role: Optional[str] = "Candidate"
    # Employee type: "Intern" | "Full Time Employee" | "Guidewire"
    candidate_employee_type: Optional[str] = None
    candidate_job_title: Optional[str] = None
    # Name fields (optional)
    candidate_first_name: Optional[str] = None
    candidate_middle_name: Optional[str] = None
    candidate_last_name: Optional[str] = None
    
    # Contact and personal info (optional)
    candidate_mobile: Optional[str] = None
    candidate_gender: Optional[str] = None
    candidate_date_of_birth: Optional[date] = None
    
    # Professional info (optional)
    candidate_source: Optional[str] = None
    candidate_experience: Optional[str] = None
    candidate_skills: Optional[str] = None
    candidate_joining_date: Optional[date] = None
    
    # Salary info (optional)
    candidate_expected_salary: Optional[str] = None
    candidate_current_salary: Optional[str] = None
    
    # Location (optional)
    candidate_current_location: Optional[str] = None
    candidate_job_title: Optional[str] = None
    # Employee type: "Intern" | "Full Time Employee" | "Guidewire"
    candidate_employee_type: Optional[str] = None
    assigned_hr_manager_id: Optional[str] = None
    assigned_report_manager_id: Optional[str] = None

    # Optional pre-filled education and experience details
    education_records: Optional[List["EducationRecord"]] = None
    experience_records: Optional[List["ExperienceRecord"]] = None

class CandidateCreateResponse(BaseModel):
    candidate_id: str
    candidate_is_first_time: bool
    candidate_password: str

# GET candidate schemas
class CandidateEducationResponse(BaseModel):
    education_institute: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    starting_year: str | None = None
    year_of_passing: str | None = None
    percentage: str | None = None
    document_is_submitted: bool | None = None

class CandidateExperienceResponse(BaseModel):
    company_name: str | None = None
    job_title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    year_of_experience: str | None = None
    document_is_submitted: bool | None = None

class CandidateAadharResponse(BaseModel):
    aadhar: str | None = None
    name_in_aadhar: str | None = None
    enrollment_number: str | None = None
    aadhar_is_submitted: bool | None = None
    is_verified: bool | None = None

class CandidatePanResponse(BaseModel):
    pan: str | None = None
    name_in_pan: str | None = None
    father_name_in_pan: str | None = None
    pan_is_submitted: bool | None = None
    is_verified: bool | None = None

class CandidateInfoResponse(BaseModel):
    position: str | None = None
    department: str | None = None
    dob: date | None = None
    gender: str | None = None
    marital_status: str | None = None
    nationality: str | None = None
    current_address: str | None = None
    permanent_address: str | None = None
    submitted_at: date | None = None

class CandidateCompleteResponse(BaseModel):
    # ── Core identity ────────────────────────────────────────────────────────
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_mobile: str | None = None
    candidate_role: str | None = None
    candidate_job_title: str | None = None
    candidate_is_verified: bool | None = None
    candidate_created_at: datetime | None = None
    # ── Professional details ─────────────────────────────────────────────────
    candidate_gender: str | None = None
    candidate_date_of_birth: date | None = None
    candidate_source: str | None = None
    candidate_experience: str | None = None
    candidate_skills: str | None = None
    candidate_joining_date: date | None = None
    candidate_current_location: str | None = None
    candidate_current_salary: str | None = None
    candidate_expected_salary: str | None = None
    # ── Employee type ────────────────────────────────────────────────────────
    candidate_employee_type: str | None = None
    # ── Job assignment ───────────────────────────────────────────────────────
    job_id: str | None = None
    # ── Related records ──────────────────────────────────────────────────────
    personal_info: CandidateInfoResponse | None = None
    education: list[CandidateEducationResponse] = []
    experience: list[CandidateExperienceResponse] = []
    aadhar: CandidateAadharResponse | None = None
    pan: CandidatePanResponse | None = None
    status: str | None = None
    pipline_status: str | None = None

class AllCandidatesResponse(BaseModel):
    total_candidates: int
    candidates: list[CandidateCompleteResponse]







class candidateFormRequest(BaseModel):
    position: str | None = None
    department: str | None = None
    dob: date 
    gender: str
    marital_status: str 
    nationality: str 
    current_address: str 
    permanent_address: str 
    submitted_at: date

class candidateFormResponse(BaseModel):
    status: str = "Success"
    message: str = "Form submitted successfully"





class CandidateGetRequest(BaseModel):
    candidate_id: int

class CandidateGetResponse(BaseModel):
    candidate_id: int
    candidate_name: str
    candidate_email: EmailStr
    candidate_phone: str
    candidate_role: str
    candidate_joining_date: date
    candidate_is_verified: bool

class CandidateInfoForm(BaseModel):
    position: str | None = None
    department: str | None = None
    dob: date 
    gender: str
    marital_status: str 
    nationality: str 
    current_address: str 
    permanent_address: str 
    submitted_at: date

# Single education record (without candidate_id for use in lists)
class EducationRecord(BaseModel):
    education_institute: str
    degree: str
    field_of_study: str
    starting_year: str
    year_of_passing: str
    percentage: str
    submitted_at: date
    document_is_submitted: bool | None = None

# Bulk education submission request
class CandidateEducationForm(BaseModel):
    education_records: List[EducationRecord]  # List of education records

# Single experience record (without candidate_id for use in lists)
class ExperienceRecord(BaseModel):
    company_name: str
    job_title: str
    start_date: date
    end_date: date
    year_of_experience: str
    submitted_at: date
    document_is_submitted: bool | None = None

# Bulk experience submission request
class CandidateExperienceForm(BaseModel):
    experience_records: List[ExperienceRecord]  # List of experience records

class CandidateAadharForm(BaseModel):
    aadhar: str
    name_in_aadhar: str
    enrollment_number: str
    aadhar_is_submitted: bool | None = None
    submitted_at: date
    is_verified: bool | None = None

class CandidatePanForm(BaseModel):
    pan: str
    name_in_pan: str
    father_name_in_pan: str
    pan_is_submitted: bool | None = None
    submitted_at: date
    is_verified: bool | None = None   

class candidateFormResponse(BaseModel):
    status: str = "Success"
    message: str = "Form submitted successfully"

#PAN verfication 
class PANRecord(BaseModel):
    pan: str
    name: str
    fathername: Optional[str] = "" # Mandatory for DCT category
    dob: str  # Format: DD/MM/YYYY

class OnboardingRequest(BaseModel):
    records: List[PANRecord]

class DeleteResponse(BaseModel):
    status: str = "Success"
    message: str = "Candidate deleted successfully"

# Change password schemas
class ChangePasswordRequest(BaseModel):
    new_password: str
    confirm_password: str

class ChangePasswordResponse(BaseModel):
    status: str
    message: str


# ---------------------------------------------------------------------------
# Public Job Application schemas
# ---------------------------------------------------------------------------

class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    start_year: str
    end_year: str
    percentage: Optional[str] = None


class ExperienceEntry(BaseModel):
    company_name: str
    job_title: str
    start_date: date
    end_date: Optional[date] = None
    years_of_experience: Optional[str] = None


class JobApplicationResponse(BaseModel):
    status: str
    message: str
    candidate_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CandidateStatusUpdateRequest(BaseModel):
    status: Optional[str] = Field(
        default=None,
        description="Account status. Allowed values: 'Active', 'Inactive'",
    )
    pipeline_status: Optional[str] = Field(
        default=None,
        description=(
            "Hiring pipeline stage. Allowed values: "
            "'Applied', 'Screening', 'Interview', 'Pre-Boarding', 'Onboarded', 'Rejected'"
        ),
    )


class CandidateStatusResponse(BaseModel):
    candidate_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    status: Optional[str] = None
    pipeline_status: Optional[str] = None
    updated_at: Optional[datetime] = None


class AllCandidateStatusResponse(BaseModel):
    total: int
    candidates: List[CandidateStatusResponse]


class StatusActionResponse(BaseModel):
    status: str
    message: str
    data: CandidateStatusResponse

class ManagerApprovalRequest(BaseModel):
    action: str = Field(description="Action to take: 'Approve' or 'Reject'")
    comments: Optional[str] = None
