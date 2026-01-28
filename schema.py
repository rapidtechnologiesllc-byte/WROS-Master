# schema.py
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime, date


# login schemas

class SignupRequest(BaseModel):
    user_name: str
    user_email: EmailStr
    user_password: str
    user_role: str


class SignupResponse(BaseModel):
    response: str = "User created successfully"


class LoginRequest(BaseModel):
    UserEmail: EmailStr
    UserPassword: str

class LoginResponse(BaseModel):
    user_role: str
    user_name: str
    user_email: EmailStr
    is_first_time: bool
    access_token: str

class CandidateLoginRequest(BaseModel):
    candidate_email: EmailStr
    candidate_password: str

class CandidateLoginResponse(BaseModel):
    candidate_id: str
    candidate_role: str
    candidate_name: str
    candidate_email: EmailStr
    candidate_mobile: str
    is_first_time: bool
    access_token: str

# Candidate schemas
class CandidateCreateRequest(BaseModel):
    # Required fields
    candidate_email: EmailStr
    
    # Role (optional, defaults to "Candidate")
    candidate_role: Optional[str] = "Candidate"
    
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

    assigned_hr_manager_id: Optional[str] = None
    assigned_report_manager_id: Optional[str] = None

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

class CandidateCompleteResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_mobile: str | None = None
    candidate_role: str | None = None
    candidate_is_verified: bool | None = None
    candidate_created_at: datetime | None = None
    personal_info: CandidateInfoResponse | None = None
    education: list[CandidateEducationResponse] = []
    experience: list[CandidateExperienceResponse] = []
    aadhar: CandidateAadharResponse | None = None
    pan: CandidatePanResponse | None = None

class AllCandidatesResponse(BaseModel):
    total_candidates: int
    candidates: list[CandidateCompleteResponse]







class candidateFormRequest(BaseModel):
    candidate_id: str  # Changed from int to str to match candidateID in model
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
    candidate_id: int
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
    candidate_id: str
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
    candidate_id: str
    experience_records: List[ExperienceRecord]  # List of experience records

class CandidateAadharForm(BaseModel):
    candidate_id: str  # Changed from int to str to match candidateID
    aadhar: str
    name_in_aadhar: str
    enrollment_number: str
    aadhar_is_submitted: bool | None = None
    submitted_at: date
    is_verified: bool | None = None

class CandidatePanForm(BaseModel):
    candidate_id: str  # Changed from int to str to match candidateID
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


# ===== Interview and Assignment Management Schemas =====

# Candidate Assignment Schemas
class CandidateAssignmentCreate(BaseModel):
    candidate_id: str
    hiring_manager_id: Optional[str] = None
    reporting_manager_id: Optional[str] = None

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
    contact_person: str
    job_status: str
    no_of_positions: int
    start_date: date
    end_date: date

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
    company_type: str
    company_name: str
    contact_person: str
    job_status: str
    no_of_positions: int
    start_date: date
    end_date: date
    hiring_manager_id: str

class AllJobsResponse(BaseModel):
    total_jobs: int
    jobs: list[JobResponse]

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