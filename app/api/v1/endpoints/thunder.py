"""
Thunder Pre-Screening API Endpoints
Questia chatbot-based candidate intake flow
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from uuid import uuid4
import logging
from typing import Optional, List

from app.models import ThunderSession, ThunderSessionStatus, Candidate, Jobs, HiringManagerValidation
from app.services.thunder_service import ThunderService
from app.services.ai_recruiter_integration_service import AIRecruiterIntegrationService
from app.core.database import get_db
from app.schemas.thunder_schemas import (
    ThunderSessionCreate,
    ThunderSessionResponse,
    ThunderAnswerRequest,
    ThunderAnswerResponse,
    ThunderSubmitResponse,
)

router = APIRouter(prefix="/thunder", tags=["Thunder Pre-Screening"])
logger = logging.getLogger(__name__)

thunder_service = ThunderService()
ai_recruiter_service = AIRecruiterIntegrationService()


@router.post("/sessions", response_model=ThunderSessionResponse)
async def create_or_resume_session(req: ThunderSessionCreate, db=None):
    """
    Start new Thunder session or resume existing one.
    Returns session state with current question(s) and form state.
    """
    try:
        db = db or next(get_db())

        # Check if candidate has existing session (resume flow)
        existing = db.query(ThunderSession).filter(
            ThunderSession.candidate_email == req.candidate_email,
            ThunderSession.status.in_([ThunderSessionStatus.STARTED, ThunderSessionStatus.IN_PROGRESS, ThunderSessionStatus.PAUSED])
        ).first()

        if existing:
            # Resume session
            existing.status = ThunderSessionStatus.IN_PROGRESS
            existing.last_activity_at = datetime.utcnow()
            db.commit()
            return ThunderSessionResponse.from_orm(existing)

        # Create new session
        session = await thunder_service.create_session(
            candidate_email=req.candidate_email,
            device_type=req.device_type,
            utm_source=req.utm_source,
            db=db
        )

        return ThunderSessionResponse.from_orm(session)

    except Exception as e:
        logger.error(f"Error creating Thunder session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.get("/sessions/{session_id}", response_model=ThunderSessionResponse)
async def get_session(session_id: str, db=None):
    """
    Get current session state including form responses, resume, progress.
    """
    try:
        db = db or next(get_db())
        session = db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        session.last_activity_at = datetime.utcnow()
        db.commit()

        return ThunderSessionResponse.from_orm(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session")


@router.post("/sessions/{session_id}/answer", response_model=ThunderAnswerResponse)
async def submit_answer(session_id: str, req: ThunderAnswerRequest, db=None):
    """
    Submit answer to current question.
    Returns next question or completion status.
    """
    try:
        db = db or next(get_db())
        session = db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Save response
        response = await thunder_service.save_response(
            session=session,
            question=req.question,
            response=req.response,
            time_taken_seconds=req.time_taken_seconds,
            db=db
        )

        # Check for conditional branching (e.g., work auth questions for non-US jobs)
        next_question = await thunder_service.get_next_question(
            session=session,
            current_question=req.question,
            db=db
        )

        return ThunderAnswerResponse(
            status="ok",
            next_question=next_question,
            session_id=session_id,
            completion_percentage=session.completion_percentage
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving answer for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save answer")


@router.post("/sessions/{session_id}/upload-resume")
async def upload_resume(session_id: str, file: UploadFile = File(...), db=None):
    """
    Upload and parse resume.
    Triggers resume parsing agent, stores URL and parsed data.
    """
    try:
        db = db or next(get_db())
        session = db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Upload to S3 and parse
        resume_url, parsed_data = await thunder_service.upload_and_parse_resume(
            session=session,
            file=file,
            db=db
        )

        session.resume_url = resume_url
        session.resume_parsed_data = parsed_data
        session.resume_parsed = True
        session.resume_parse_status = "SUCCESS"
        session.last_activity_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "resume_url": resume_url,
            "parsed_data": parsed_data,
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume for session {session_id}: {str(e)}")
        # Store error but don't block candidate
        session.resume_parse_status = "ERROR"
        session.last_error = str(e)
        session.error_count = (session.error_count or 0) + 1
        db.commit()

        raise HTTPException(status_code=400, detail="Resume parsing failed, please continue or retry")


@router.post("/sessions/{session_id}/submit", response_model=ThunderSubmitResponse)
async def submit_application(session_id: str, db=None):
    """
    Submit Thunder application.
    Finalizes session, creates candidate record, triggers AI Recruiter handoff.
    """
    try:
        db = db or next(get_db())
        session = db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Mark session as submitted
        session.status = ThunderSessionStatus.COMPLETED
        session.submitted = True
        session.submitted_at = datetime.utcnow()

        # Create or update candidate record
        candidate = await thunder_service.finalize_candidate(
            session=session,
            db=db
        )

        # Trigger AI Recruiter job matching (async)
        job_matches = await ai_recruiter_service.match_candidate_to_jobs(
            candidate_id=candidate.candidateID,
            resume_data=session.resume_parsed_data,
            candidate_data=session.candidate_data,
            db=db
        )

        session.job_matches = job_matches
        session.handoff_to_ai_recruiter_at = datetime.utcnow()
        db.commit()

        return ThunderSubmitResponse(
            status="submitted",
            candidate_id=candidate.candidateID,
            handoff_status="queued_for_ai_recruiter",
            job_matches=[
                {
                    "job_id": m["job_id"],
                    "title": m["title"],
                    "match_score": m["score"]
                }
                for m in job_matches[:5]  # Top 5 matches
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting application for session {session_id}: {str(e)}")
        session.status = ThunderSessionStatus.ERROR
        session.last_error = str(e)
        session.error_count = (session.error_count or 0) + 1
        db.commit()

        raise HTTPException(status_code=500, detail="Failed to submit application")


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str, db=None):
    """
    Pause session (candidate closes browser, can resume later).
    """
    try:
        db = db or next(get_db())
        session = db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        session.status = ThunderSessionStatus.PAUSED
        session.paused_at = datetime.utcnow()
        db.commit()

        return {"status": "paused", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to pause session")


@router.get("/sessions/{session_id}/progress")
async def get_progress(session_id: str, db=None):
    """
    Get session progress (completion %, current question, etc).
    """
    try:
        db = db or next(get_db())
        session = db.query(ThunderSession).filter(ThunderSession.id == session_id).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session_id,
            "status": session.status.value if session.status else None,
            "completion_percentage": session.completion_percentage,
            "last_question_reached": session.last_question_reached,
            "questions_answered": session.questions_answered,
            "resume_uploaded": session.resume_url is not None,
            "time_elapsed_minutes": (
                (datetime.utcnow() - session.created_at).total_seconds() / 60
                if session.created_at else 0
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching progress for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch progress")
