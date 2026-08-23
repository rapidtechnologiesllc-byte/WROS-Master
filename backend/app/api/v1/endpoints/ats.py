"""
ATS (Applicant Tracking System) Endpoints
==========================================

Endpoints
---------
GET  /ats/scores/all                – list all ATS scores (HR/Admin only)
GET  /ats/scores/job/{job_id}       – scores for a specific job
GET  /ats/scores/candidate/{cid}    – all scores for a specific candidate
GET  /ats/scores/{score_id}         – full detail for one score record
POST /ats/rescore                   – re-run ATS scoring for any candidate+job
"""

import json
import asyncio
from typing import List
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_resource_permission
from app.models.ats import ATSScore
from app.models.candidate import Candidate, CandidateEducationForm, CandidateExperienceForm
from app.models.user import Jobs
from app.schemas.ats import (
    ATSScoreResponse,
    ATSScoreBreakdown,
    AllATSScoresResponse,
    CandidateATSListItem,
    ATSRescoringRequest,
)
from app.tools.ats_scorer import run_ats_scoring

router = APIRouter(prefix="/ats", tags=["ats"])

# Thread pool for running the synchronous LLM pipeline from async endpoints
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ats_scorer")


# ---------------------------------------------------------------------------
# Internal helper — build full ATSScoreResponse from an ATSScore ORM row
# ---------------------------------------------------------------------------

def _build_response(score: ATSScore, db: Session) -> ATSScoreResponse:
    return ATSScoreResponse(
        ats_score_id=score.id,
        candidate_id=score.candidate_id,
        job_id=score.job_id,
        overall_score=score.overall_score,
        breakdown=ATSScoreBreakdown(
            skills_score=score.skills_score,
            experience_score=score.experience_score,
            education_score=score.education_score,
            location_score=score.location_score,
            culture_fit_score=score.culture_fit_score,
        ),
        profile_summary=score.profile_summary,
        strengths=json.loads(score.strengths) if score.strengths else [],
        weaknesses=json.loads(score.weaknesses) if score.weaknesses else [],
        recommendation=score.recommendation or "Review",
        score_rationale=score.score_rationale,
        ats_verdict=score.ats_verdict,
        scored_at=score.scored_at,
    )


# ---------------------------------------------------------------------------
# GET /ats/scores/all  — list every ATS score
# ---------------------------------------------------------------------------

@router.get(
    "/scores/all",
    response_model=AllATSScoresResponse,
    summary="List all ATS scores across every job and candidate",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def list_all_ats_scores(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    scores = db.query(ATSScore).order_by(ATSScore.overall_score.desc()).all()

    items = []
    for s in scores:
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == s.candidate_id
        ).first()
        job = db.query(Jobs).filter(Jobs.jobID == s.job_id).first() if s.job_id else None

        name = None
        if candidate:
            parts = [
                candidate.candidateFirstName,
                candidate.candidateMiddleName,
                candidate.candidateLastName,
            ]
            name = " ".join(filter(None, parts)) or None

        items.append(
            CandidateATSListItem(
                ats_score_id=s.id,
                candidate_id=s.candidate_id,
                candidate_name=name,
                candidate_email=candidate.candidateEmail if candidate else None,
                job_id=s.job_id,
                job_title=job.jobTitle if job else None,
                overall_score=s.overall_score,
                recommendation=s.recommendation,
                ats_verdict=s.ats_verdict,
                scored_at=s.scored_at,
            )
        )

    return AllATSScoresResponse(total=len(items), scores=items)


# ---------------------------------------------------------------------------
# GET /ats/scores/job/{job_id}  — all scores for one job
# ---------------------------------------------------------------------------

@router.get(
    "/scores/job/{job_id}",
    response_model=AllATSScoresResponse,
    summary="ATS scores for all applicants on a specific job",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def list_scores_for_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    scores = (
        db.query(ATSScore)
        .filter(ATSScore.job_id == job_id)
        .order_by(ATSScore.overall_score.desc())
        .all()
    )

    items = []
    for s in scores:
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == s.candidate_id
        ).first()
        parts = (
            [
                candidate.candidateFirstName,
                candidate.candidateMiddleName,
                candidate.candidateLastName,
            ]
            if candidate
            else []
        )
        name = " ".join(filter(None, parts)) or None

        items.append(
            CandidateATSListItem(
                ats_score_id=s.id,
                candidate_id=s.candidate_id,
                candidate_name=name,
                candidate_email=candidate.candidateEmail if candidate else None,
                job_id=s.job_id,
                job_title=job.jobTitle,
                overall_score=s.overall_score,
                recommendation=s.recommendation,
                ats_verdict=s.ats_verdict,
                scored_at=s.scored_at,
            )
        )

    return AllATSScoresResponse(total=len(items), scores=items)


# ---------------------------------------------------------------------------
# GET /ats/scores/candidate/{candidate_id}  — all scores for one candidate
# ---------------------------------------------------------------------------

@router.get(
    "/scores/candidate/{candidate_id}",
    response_model=AllATSScoresResponse,
    summary="All ATS scores recorded for a specific candidate",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def list_scores_for_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    scores = (
        db.query(ATSScore)
        .filter(ATSScore.candidate_id == candidate_id)
        .order_by(ATSScore.scored_at.desc())
        .all()
    )

    parts = [
        candidate.candidateFirstName,
        candidate.candidateMiddleName,
        candidate.candidateLastName,
    ]
    name = " ".join(filter(None, parts)) or None

    items = []
    for s in scores:
        job = db.query(Jobs).filter(Jobs.jobID == s.job_id).first() if s.job_id else None
        items.append(
            CandidateATSListItem(
                ats_score_id=s.id,
                candidate_id=s.candidate_id,
                candidate_name=name,
                candidate_email=candidate.candidateEmail,
                job_id=s.job_id,
                job_title=job.jobTitle if job else None,
                overall_score=s.overall_score,
                recommendation=s.recommendation,
                ats_verdict=s.ats_verdict,
                scored_at=s.scored_at,
            )
        )

    return AllATSScoresResponse(total=len(items), scores=items)


# ---------------------------------------------------------------------------
# GET /ats/scores/{score_id}  — single full-detail score
# ---------------------------------------------------------------------------

@router.get(
    "/scores/{score_id}",
    response_model=ATSScoreResponse,
    summary="Full ATS score detail for a single record",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_ats_score(
    score_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    score = db.query(ATSScore).filter(ATSScore.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail=f"ATS score record {score_id} not found")
    return _build_response(score, db)


# ---------------------------------------------------------------------------
# POST /ats/rescore  — manually re-trigger scoring
# ---------------------------------------------------------------------------

@router.post(
    "/rescore",
    response_model=ATSScoreResponse,
    summary="Re-run ATS scoring for a specific candidate + job",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
)
async def rescore_candidate(
    request: ATSRescoringRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Re-runs the full Gemini-powered ATS pipeline for a candidate+job pair.
    Creates a new ``ats_scores`` row and returns the full result.
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == request.candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = db.query(Jobs).filter(Jobs.jobID == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    score_record = await _run_and_persist_ats(candidate, job, db)
    return _build_response(score_record, db)


# ---------------------------------------------------------------------------
# Internal — run ATS in thread + persist result  (used by this router AND
# by the job-application endpoint in create_job.py)
# ---------------------------------------------------------------------------

async def _run_and_persist_ats(
    candidate: Candidate,
    job: Jobs,
    db: Session,
) -> ATSScore:
    """
    Run the ATS scoring pipeline asynchronously (offloads blocking LLM calls
    to a thread pool) and persist the result to ``ats_scores``.

    Returns the newly created ``ATSScore`` ORM object.
    """
    # Fetch related education / experience rows
    edu_rows = (
        db.query(CandidateEducationForm)
        .filter(CandidateEducationForm.candidateID == candidate.candidateID)
        .all()
    )
    exp_rows = (
        db.query(CandidateExperienceForm)
        .filter(CandidateExperienceForm.candidateID == candidate.candidateID)
        .all()
    )

    edu_dicts = [
        {
            "education_institute": r.education_institute,
            "degree": r.degree,
            "field_of_study": r.field_of_study,
            "starting_year": r.starting_year,
            "year_of_passing": r.year_of_passing,
        }
        for r in edu_rows
    ]
    exp_dicts = [
        {
            "company_name": r.company_name,
            "job_title": r.job_title,
            "start_date": str(r.start_date) if r.start_date else None,
            "end_date": str(r.end_date) if r.end_date else "Present",
            "year_of_experience": r.year_of_experience,
        }
        for r in exp_rows
    ]

    name_parts = [
        candidate.candidateFirstName,
        candidate.candidateMiddleName,
        candidate.candidateLastName,
    ]
    candidate_name = " ".join(filter(None, name_parts)) or "Unknown"

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        lambda: run_ats_scoring(
            job_title=job.jobTitle,
            job_description=job.jobDescription,
            job_skills=job.jobSkills,
            job_experience=job.jobExperience,
            job_location=job.jobLocation,
            candidate_name=candidate_name,
            candidate_experience=candidate.candidateExperience or "0",
            candidate_skills=candidate.candidateSkills or "",
            candidate_location=candidate.candidateCurrentLocation or "",
            education_records=edu_dicts,
            experience_records=exp_dicts,
        ),
    )

    # Persist
    score_row = ATSScore(
        candidate_id=candidate.candidateID,
        job_id=job.jobID,
        overall_score=result["overall_score"],
        skills_score=result["skills_score"],
        experience_score=result["experience_score"],
        education_score=result["education_score"],
        location_score=result["location_score"],
        culture_fit_score=result["culture_fit_score"],
        profile_summary=result["profile_summary"],
        strengths=json.dumps(result["strengths"]),
        weaknesses=json.dumps(result["weaknesses"]),
        recommendation=result["recommendation"],
        score_rationale=result["score_rationale"],
        ats_verdict=result["ats_verdict"],
    )
    db.add(score_row)
    db.commit()
    db.refresh(score_row)
    return score_row


async def run_ats_scoring_in_background(candidate_id: str, job_id: str) -> None:
    """BackgroundTask entry point for the public job-application endpoint
    (app.api.v1.endpoints.create_job). Must not receive the request's own
    `Depends(get_db)` session -- it's closed as soon as the HTTP response
    is sent, before a BackgroundTask necessarily gets its turn. Same
    SessionLocal()-per-background-task convention as
    app.services.ai_conversation_service.run_auto_assign_ai_agent_in_background()
    and app.api.v1.endpoints.bulk_engagement._run_worker_in_background()."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not candidate or not job:
            return
        await _run_and_persist_ats(candidate, job, db)
    finally:
        db.close()
