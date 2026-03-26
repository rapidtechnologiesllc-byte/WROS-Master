from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime, date


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
    permission_role: Optional[str] = None
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
    no_of_positions: Optional[int] = None
    salary_range: Optional[str] = None
    recuriter_id: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    business_unit: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

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
    no_of_positions: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    hiring_manager_id: Optional[str] = None
    recuriter_id: Optional[str] = None
    business_unit: Optional[int] = None
    salary_range: Optional[str] = None

class AllJobsResponse(BaseModel):
    total_jobs: int
    jobs: list[JobResponse]

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

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class HrMeResponse(BaseModel):
    user_id: str
    user_name: Optional[str]
    user_email: str
    user_role: str
    permission_role: Optional[str] = None
    role_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    created_at: datetime
    access_token: str
    token_type: str = "bearer"

# LinkedIn Job Posting Schemas
class LinkedInPostRequest(BaseModel):
    job_id: str

class LinkedInPostResponse(BaseModel):
    status: str
    message: str
    linkedin_post_id: str
    posted_at: datetime
    job_details: JobResponse

# Offer Letter Schemas
class OfferLetterCreateRequest(BaseModel):
    candidate_id: str
    job_id: Optional[str] = None
    hiring_manager_id: str
    reporting_manager_id: str
    position: str
    salary: str
    joining_date: date

class OfferLetterUpdateRequest(BaseModel):
    job_id: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    reporting_manager_id: Optional[str] = None
    position: Optional[str] = None
    salary: Optional[str] = None
    joining_date: Optional[date] = None

class OfferLetterResponse(BaseModel):
    id: int
    candidate_id: str
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_id: str | None = None
    hiring_manager_id: str
    reporting_manager_id: str
    position: str
    salary: str
    joining_date: date
    offer_status: str
    candidate_response: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    created_by: str
    cancelled_at: datetime | None = None
    cancelled_by: str | None = None

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
