"""
Career Site API Endpoints - Public job listings and applications

Endpoints for careers.blitzenx.com (port 3001):
- GET /api/v1/careers/jobs - List public jobs
- GET /api/v1/careers/jobs/{id} - Job details
- POST /api/v1/careers/applications - Submit application
- POST /api/v1/careers/analyze-resume - Thunder resume analysis
- POST /api/v1/careers/clarifications/generate - Generate Q&A for gaps
- POST /api/v1/careers/clarifications/{app_id}/answer - Submit clarification answer
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.career import (
    CareerJob, CareerApplication, CareerResumeAnalysis, CareerClarification, CareerConversation
)
from pydantic import BaseModel
from typing import Optional, List
import re
import json
from anthropic import Anthropic
from app.core.config import settings

router = APIRouter(prefix="/careers", tags=["careers"])


def call_claude(prompt: str) -> str:
    """Call Claude API for resume analysis and clarifications"""
    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text if message.content else ""
    except Exception as e:
        return f"Error calling Claude: {str(e)}"


# ============ SCHEMAS ============

class SkillRequirement(BaseModel):
    skill: str
    years_required: int
    level: Optional[str] = None


class JobDetail(BaseModel):
    id: str
    title: str
    description: str
    skills_required: Optional[List[SkillRequirement]] = None
    experience_years_required: Optional[int] = None
    location: str
    salary_range_min_usd_cents: Optional[int] = None
    salary_range_max_usd_cents: Optional[int] = None


class ResumeAnalysisRequest(BaseModel):
    resume_text: str
    job_id: str
    candidate_email: str
    candidate_name: Optional[str] = None
    candidate_experience_years: Optional[int] = None


class ResumeAnalysisResponse(BaseModel):
    overall_fit_score: float
    skills_matched: List[dict]
    experience_gap: Optional[dict]
    ai_assessment: str
    gaps_identified: List[dict]
    has_critical_gaps: bool
    tags: List[str]


class ApplicationSubmit(BaseModel):
    career_job_id: str
    candidate_email: str
    candidate_name: str
    candidate_phone: Optional[str] = None
    experience_years: Optional[int] = None
    authorized_to_work: Optional[bool] = None
    resume_text: str
    analysis: Optional[dict] = None
    clarifications: Optional[dict] = None
    conversation_responses: Optional[dict] = None


class ClarificationGenerateRequest(BaseModel):
    gaps: List[dict]
    resume_text: str
    job_id: str


class ClarificationResponse(BaseModel):
    gap_type: str
    gap_description: str
    ai_question: str


class ConversationResponseRequest(BaseModel):
    candidate_email: str
    job_id: str
    responses: dict  # {0: "answer", 1: "answer", 2: "answer", 3: "answer", 4: "answer"}
    candidate_name: Optional[str] = None


# ============ ENDPOINTS ============

@router.get("/applications/by-email/{email}")
def get_candidate_applications(email: str, db: Session = Depends(get_db)):
    """
    Get all applications for a candidate by email (for dashboard)

    Returns application history with status, fit scores, and job details.
    """
    applications = db.query(CareerApplication).filter(
        CareerApplication.candidate_email == email.lower()
    ).order_by(CareerApplication.created_at.desc()).all()

    result = []
    for app in applications:
        # Get analysis if available
        analysis = db.query(CareerResumeAnalysis).filter(
            CareerResumeAnalysis.career_application_id == app.id
        ).first()

        result.append({
            "id": app.id,
            "job_id": app.career_job_id,
            "job_title": f"Job {app.career_job_id}",
            "applied_date": app.created_at.strftime('%Y-%m-%d') if app.created_at else None,
            "status": app.status.lower() if app.status else "applied",
            "fit_score": analysis.overall_fit_score if analysis else 0,
            "last_update": app.updated_at.strftime('%Y-%m-%d') if app.updated_at else None,
        })

    return {"applications": result, "count": len(result)}


@router.get("/jobs", response_model=List[JobDetail])
def list_jobs(db: Session = Depends(get_db)):
    """List all published jobs"""
    jobs = db.query(CareerJob).filter(
        CareerJob.is_published == True,
        CareerJob.is_active == True
    ).all()

    return [JobDetail(
        id=job.id,
        title=job.title,
        description=job.description,
        skills_required=job.skills_required,
        experience_years_required=job.experience_years_required,
        location=job.location or "",
        salary_range_min_usd_cents=job.salary_range_min_usd_cents,
        salary_range_max_usd_cents=job.salary_range_max_usd_cents
    ) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job details by ID"""
    job = db.query(CareerJob).filter(CareerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobDetail(
        id=job.id,
        title=job.title,
        description=job.description,
        skills_required=job.skills_required,
        experience_years_required=job.experience_years_required,
        location=job.location or "",
        salary_range_min_usd_cents=job.salary_range_min_usd_cents,
        salary_range_max_usd_cents=job.salary_range_max_usd_cents
    )


@router.post("/conversations/save")
def save_conversation_responses(
    request: ConversationResponseRequest,
    db: Session = Depends(get_db)
):
    """
    Save relationship-building conversation responses from candidate

    Stores all Q&A from the pre-resume conversation stage.
    """
    # Save conversation responses
    for question_idx, response_text in request.responses.items():
        conversation = CareerConversation(
            candidate_email=request.candidate_email.lower(),
            question_index=int(question_idx),
            question_text=f"Question {int(question_idx) + 1}",
            candidate_response=response_text,
            conversation_summary=request.responses
        )
        db.add(conversation)

    db.commit()

    return {
        "success": True,
        "message": f"Saved {len(request.responses)} conversation responses for {request.candidate_email}",
        "responses_count": len(request.responses)
    }


@router.post("/analyze-resume", response_model=ResumeAnalysisResponse)
def analyze_resume(request: ResumeAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze candidate's resume against job requirements using Thunder AI

    Extracts skills, experience, and compares against JD.
    Returns gaps that need clarification.
    """
    job = db.query(CareerJob).filter(CareerJob.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create analysis prompt
    analysis_prompt = f"""You are a resume analyst. Analyze this candidate's resume against the job requirements and respond ONLY with valid JSON.

JOB REQUIREMENTS:
Title: {job.title}
Description: {job.description}
Required Skills: {job.skills_required or []}
Years of Experience Required: {job.experience_years_required or 'Not specified'}

CANDIDATE RESUME:
{request.resume_text}

CANDIDATE INFO:
Name: {request.candidate_name}
Email: {request.candidate_email}
Years of Experience: {request.candidate_experience_years}

Provide analysis as JSON with EXACTLY these keys (no other text):
{{
  "overall_fit_score": <number 0-100>,
  "skills_matched": [
    {{"skill": "name", "required_years": <number>, "actual_years": <number>, "match": <boolean>}}
  ],
  "experience_gap": {{"required": <number>, "actual": <number>, "gap": <number>}} or null,
  "gaps_identified": [
    {{"gap_type": "experience|skill|certification", "gap_description": "description"}}
  ],
  "has_critical_gaps": <boolean>,
  "tags": ["tag1", "tag2"]
}}"""

    # Call Claude for analysis
    response = call_claude(analysis_prompt)

    try:
        # Parse Claude's response (should be JSON)
        if response.strip().startswith('{'):
            analysis = json.loads(response)
        else:
            # Extract JSON from response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                analysis = json.loads(match.group())
            else:
                raise ValueError("No JSON found in response")
    except Exception as e:
        # Fallback if parsing fails
        analysis = {
            "overall_fit_score": 60,
            "skills_matched": [],
            "experience_gap": None,
            "gaps_identified": [{"gap_type": "analysis", "gap_description": "Unable to complete full analysis"}],
            "has_critical_gaps": False,
            "tags": ["needs_review"]
        }

    # Store analysis in database
    resume_analysis = CareerResumeAnalysis(
        career_job_id=job.id,
        candidate_email=request.candidate_email,
        overall_fit_score=analysis.get('overall_fit_score', 50),
        skills_matched=analysis.get('skills_matched', []),
        experience_gap=analysis.get('experience_gap'),
        ai_assessment=response,
        gaps_identified=analysis.get('gaps_identified', []),
        has_critical_gaps=analysis.get('has_critical_gaps', False),
        tags=analysis.get('tags', [])
    )
    db.add(resume_analysis)
    db.commit()

    return ResumeAnalysisResponse(**analysis)


@router.post("/clarifications/generate")
def generate_clarifications(
    request: ClarificationGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate clarification questions for identified gaps

    For each gap (e.g., "needs 5 years Java, has 2"), create a question
    to understand candidate's capabilities better.
    """
    job = db.query(CareerJob).filter(CareerJob.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    gaps_text = "\n".join([f"- {gap.get('gap_description', str(gap))}" for gap in request.gaps])

    clarification_prompt = f"""You are a recruiter generating follow-up questions for candidates. For each gap below, create a thoughtful clarification question. Respond ONLY with valid JSON array.

IDENTIFIED GAPS:
{gaps_text}

For each gap, generate a question. Return as JSON array:
[
  {{"gap_type": "experience|skill|certification", "gap_description": "description", "ai_question": "friendly question"}},
  ...
]
Only JSON, no other text."""

    response = call_claude(clarification_prompt)

    try:
        # Parse Claude's response
        if '[' in response:
            # Find JSON array in response
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                clarifications_data = json.loads(match.group())
            else:
                clarifications_data = []
        else:
            clarifications_data = []
    except:
        clarifications_data = []

    # Create clarification questions based on gaps
    clarifications = []
    for idx, gap in enumerate(request.gaps):
        # Use Claude's generated question if available, otherwise fallback
        generated_q = clarifications_data[idx] if idx < len(clarifications_data) else {}

        q = ClarificationResponse(
            gap_type=generated_q.get('gap_type', gap.get('gap_type', 'experience')),
            gap_description=generated_q.get('gap_description', gap.get('gap_description', str(gap))),
            ai_question=generated_q.get('ai_question', f"Can you tell us more about: {gap.get('gap_description', 'this aspect of your background')}?")
        )
        clarifications.append(q)

    return {"clarifications": clarifications}


@router.post("/applications")
async def submit_application(
    application: ApplicationSubmit,
    db: Session = Depends(get_db)
):
    """
    Submit a complete application (screening + resume + clarifications)

    Creates application record, links to job, stores analysis and responses.
    Also creates candidate in main WROS system so they appear in "All Candidates".
    Sends notification to recruiter.
    """
    from app.services.candidate_service import create_candidate_safe, DuplicateCandidateError

    job = db.query(CareerJob).filter(CareerJob.id == application.career_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create or get candidate in main WROS system (R-07)
    try:
        candidate = create_candidate_safe(
            db,
            email=application.candidate_email,
            mobile=application.candidate_phone,
            candidateFirstName=application.candidate_name.split()[0] if application.candidate_name else "",
            candidateLastName=" ".join(application.candidate_name.split()[1:]) if application.candidate_name and len(application.candidate_name.split()) > 1 else "",
            candidateSource="DIRECT",
            candidateRole="Candidate",
        )
        db.commit()
    except DuplicateCandidateError:
        # Candidate already exists, continue with application
        pass

    # Create application record
    app = CareerApplication(
        career_job_id=application.career_job_id,
        candidate_email=application.candidate_email,
        candidate_name=application.candidate_name,
        candidate_phone=application.candidate_phone,
        resume_text=application.resume_text,
        status="PENDING"
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    # Store resume analysis if provided
    if application.analysis:
        analysis = CareerResumeAnalysis(
            career_application_id=app.id,
            career_job_id=application.career_job_id,
            overall_fit_score=application.analysis.get('overall_fit_score', 0),
            skills_matched=application.analysis.get('skills_matched', []),
            experience_gap=application.analysis.get('experience_gap'),
            gaps_identified=application.analysis.get('gaps_identified', []),
            has_critical_gaps=application.analysis.get('has_critical_gaps', False),
            tags=application.analysis.get('tags', [])
        )
        db.add(analysis)
        db.commit()

    # Store clarification responses if provided
    if application.clarifications:
        for clarification_id, response in application.clarifications.items():
            # Create clarification record with response
            clarification = CareerClarification(
                career_application_id=app.id,
                career_resume_analysis_id=None,  # Would be set if we tracked analysis records separately
                gap_type="clarification",
                ai_question="Clarification response",
                candidate_response=response,
                status="ANSWERED"
            )
            db.add(clarification)
        db.commit()

    # TODO: Send notification to recruiter
    # TODO: Trigger back-end matching workflow

    return {
        "success": True,
        "application_id": app.id,
        "message": f"Application received for {job.title}. We'll review and get back to you soon!"
    }


@router.get("/applications/by-email/{email}")
def get_applications_by_email(email: str, db: Session = Depends(get_db)):
    """
    Get all applications for a candidate by email

    Returns applications with their current status and next steps.
    Recruiter is fetched from the job's linked Demand record.
    """
    from app.models.demand import Demand
    from app.models.employee import Employee

    applications = db.query(CareerApplication).filter(
        CareerApplication.candidate_email == email
    ).order_by(CareerApplication.created_at.desc()).all()

    # Map applications to response format
    response_apps = []
    for app in applications:
        job = db.query(CareerJob).filter(CareerJob.id == app.career_job_id).first()

        # Default to Thunder AI recruiter for all career site applications
        recruiter_name = "⚡ Thunder AI"

        # Determine status and next step
        status = app.status or 'applied'
        next_step_map = {
            'applied': 'Awaiting recruiter review',
            'screening': 'Scheduled for technical screening',
            'interview': 'Interview in progress',
            'offer': 'Offer extended - awaiting response',
            'rejected': 'Thank you for your interest'
        }

        response_apps.append({
            'id': app.id,
            'job_id': app.career_job_id,
            'job_title': job.title if job else 'Job Title',
            'job_location': job.location if job else 'Location TBD',
            'candidate_email': app.candidate_email,
            'candidate_name': app.candidate_name,
            'status': status,
            'fit_score': int(app.overall_fit_score or 60),
            'applied_date': app.created_at.isoformat() if app.created_at else '',
            'updated_at': app.updated_at.isoformat() if app.updated_at else '',
            'next_step': next_step_map.get(status, 'In process'),
            'recruiter_name': recruiter_name,
            'interview_date': None  # Can be extended with interview scheduling
        })

    return {
        'applications': response_apps,
        'count': len(response_apps)
    }


@router.post("/applications/{app_id}/clarifications/{clarification_id}/answer")
def submit_clarification_answer(
    app_id: str,
    clarification_id: str,
    answer: str,
    db: Session = Depends(get_db)
):
    """
    Submit answer to a clarification question
    """
    clarification = db.query(CareerClarification).filter(
        CareerClarification.id == clarification_id,
        CareerClarification.career_application_id == app_id
    ).first()

    if not clarification:
        raise HTTPException(status_code=404, detail="Clarification not found")

    # Store answer
    clarification.candidate_response = answer
    clarification.status = "ANSWERED"
    from datetime import datetime
    clarification.answered_at = datetime.utcnow()

    # Use Claude to assess if answer adequately addresses the gap
    assessment_prompt = f"""Assess if this answer adequately addresses the gap. Respond with ONLY: YES or NO followed by brief explanation.

Gap: {clarification.gap_description}
Question: {clarification.ai_question}
Answer: {answer}

Format: YES/NO - explanation"""

    assessment_response = call_claude(assessment_prompt)
    clarification.response_assessment = assessment_response
    clarification.satisfies_gap = "YES" in assessment_response.upper()
    clarification.status = "ASSESSED"
    clarification.assessed_at = datetime.utcnow()

    db.add(clarification)
    db.commit()

    return {
        "success": True,
        "satisfies_gap": clarification.satisfies_gap,
        "assessment": clarification.response_assessment
    }
