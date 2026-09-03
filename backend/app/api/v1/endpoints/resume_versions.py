"""
import logging
Resume Versioning API - List, view, and compare candidate resume versions

Endpoints:
- GET /candidates/{id}/resume-versions - List all resume versions for a candidate
- GET /candidates/{id}/resume-versions/{version_id} - Get specific resume version
- GET /candidates/{id}/resume-comparison - Compare two resume versions with analysis
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.schemas.candidate import CandidateResponse
from app.services.resume_comparison_service import ResumeComparisonService, ResumeChangeAnalysis
from app.services.resume_search_service import ResumeSearchService

router = APIRouter(prefix="/candidates", tags=["resume-versions"])

logger = logging.getLogger(__name__)

class ResumeVersionResponse:
    """Response format for resume version"""
    def __init__(self, resume: CandidateResumeParsed):
        self.id = resume.id
        self.candidate_id = resume.candidate_id
        self.parsed_at = resume.parsed_at.isoformat() if resume.parsed_at else None
        self.version_number = resume.id  # Use ID as version number for now
        self.full_name = resume.full_name
        self.email = resume.email
        self.phone = resume.phone
        self.current_title = resume.current_title
        self.current_employer = resume.current_employer
        self.work_history = resume.work_history
        self.education = resume.education
        self.skills = resume.skills
        self.certifications = resume.certifications
        self.languages = resume.languages
        self.total_experience_months = resume.total_experience_months
        self.total_experience_years = resume.total_experience_years
        self.resume_completeness_score = resume.resume_completeness_score
        self.parser_version = resume.parser_version

    def dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "parsed_at": self.parsed_at,
            "version_number": self.version_number,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "current_title": self.current_title,
            "current_employer": self.current_employer,
            "work_history": self.work_history,
            "education": self.education,
            "skills": self.skills,
            "certifications": self.certifications,
            "languages": self.languages,
            "total_experience_months": self.total_experience_months,
            "total_experience_years": self.total_experience_years,
            "resume_completeness_score": self.resume_completeness_score,
            "parser_version": self.parser_version,
        }


@router.get(
    "/{candidate_id}/resume-versions",
    response_model=List[dict],
    dependencies=[Depends(require_resource_permission("resume_versions", "view"))]
)
def list_resume_versions(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> List[dict]:
    """
    Get all resume versions for a candidate, sorted by date (newest first).

    Returns list of resume versions with:
    - Parsed date
    - Extracted fields (name, skills, experience)
    - Completeness score
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    versions = ResumeComparisonService.get_resume_versions(db, candidate_id)

    if not versions:
        return []

    return [ResumeVersionResponse(v).dict() for v in versions]


@router.get(
    "/{candidate_id}/resume-versions/{version_id}",
    response_model=dict,
    dependencies=[Depends(require_resource_permission("resume_versions", "view"))]
)
def get_resume_version(
    candidate_id: str,
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Get a specific resume version with full details.

    Includes:
    - All parsed fields
    - Raw resume text
    - Completion score
    - Parse timestamp
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    resume = db.query(CandidateResumeParsed).filter(
        CandidateResumeParsed.candidate_id == candidate_id,
        CandidateResumeParsed.id == version_id
    ).first()

    if not resume:
        raise HTTPException(status_code=404, detail=f"Resume version {version_id} not found")

    response = ResumeVersionResponse(resume).dict()
    response["raw_text"] = resume.raw_text  # Include raw text for full transparency

    return response


@router.get(
    "/{candidate_id}/resume-comparison",
    response_model=dict,
    dependencies=[Depends(require_resource_permission("resume_versions", "view"))]
)
def compare_resume_versions(
    candidate_id: str,
    version1_id: Optional[int] = Query(None, description="First version ID (older)"),
    version2_id: Optional[int] = Query(None, description="Second version ID (newer)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Compare two resume versions and analyze changes.

    Returns:
    - List of skills added
    - Experience changes
    - Title changes
    - Detected inconsistencies
    - Suspicion score and risk level
    - Recommendation for recruiter/Thunder

    If version IDs not specified, compares the two most recent versions.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    versions = ResumeComparisonService.get_resume_versions(db, candidate_id)

    if len(versions) < 2:
        return {
            "status": "insufficient_versions",
            "message": "At least 2 resume versions required for comparison",
            "versions_available": len(versions)
        }

    # Determine which versions to compare
    if version1_id and version2_id:
        old_version = db.query(CandidateResumeParsed).filter(
            CandidateResumeParsed.id == version1_id,
            CandidateResumeParsed.candidate_id == candidate_id
        ).first()
        new_version = db.query(CandidateResumeParsed).filter(
            CandidateResumeParsed.id == version2_id,
            CandidateResumeParsed.candidate_id == candidate_id
        ).first()

        if not old_version or not new_version:
            raise HTTPException(status_code=404, detail="One or both resume versions not found")
    else:
        # Default: compare two most recent
        old_version = versions[1]
        new_version = versions[0]

    # Perform comparison analysis
    analysis = ResumeChangeAnalysis(old_version, new_version)
    summary = analysis.get_summary()

    return {
        "status": "compared",
        "candidate_id": candidate_id,
        "old_version": {
            "id": old_version.id,
            "parsed_at": old_version.parsed_at.isoformat() if old_version.parsed_at else None,
            "skills_count": len(old_version.skills or []),
            "experience_years": old_version.total_experience_years,
            "jobs_count": len(old_version.work_history or []),
        },
        "new_version": {
            "id": new_version.id,
            "parsed_at": new_version.parsed_at.isoformat() if new_version.parsed_at else None,
            "skills_count": len(new_version.skills or []),
            "experience_years": new_version.total_experience_years,
            "jobs_count": len(new_version.work_history or []),
        },
        "analysis": summary,
    }


@router.post(
    "/{candidate_id}/resume-search",
    dependencies=[Depends(require_resource_permission("resume_versions", "create"))]
)
def search_candidate_resume(
    candidate_id: str,
    query: str = Query(..., min_length=1, description="Search query (skills, companies, roles)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Full-text search within a candidate's resume.

    Searches across:
    - Skills
    - Job titles and companies
    - Education and certifications
    - Raw resume text

    Returns: Matching sections and snippet context
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    # Get latest resume version
    latest_resume = db.query(CandidateResumeParsed).filter(
        CandidateResumeParsed.candidate_id == candidate_id
    ).order_by(CandidateResumeParsed.parsed_at.desc()).first()

    if not latest_resume:
        raise HTTPException(status_code=404, detail="No resume found for candidate")

    results = {
        "query": query,
        "candidate_id": candidate_id,
        "matches": {
            "skills": [],
            "jobs": [],
            "education": [],
            "certifications": [],
            "raw_text": []
        }
    }

    query_lower = query.lower()

    # Search skills
    if latest_resume.skills:
        matching_skills = [s for s in latest_resume.skills if query_lower in s.lower()]
        results["matches"]["skills"] = matching_skills

    # Search work history
    if latest_resume.work_history:
        for job in latest_resume.work_history:
            job_text = f"{job.get('employer')} - {job.get('title')} - {job.get('description')}".lower()
            if query_lower in job_text:
                results["matches"]["jobs"].append({
                    "employer": job.get("employer"),
                    "title": job.get("title"),
                    "description": job.get("description")[:200] if job.get("description") else None,
                    "dates": f"{job.get('start_date')} to {job.get('end_date', 'Present')}"
                })

    # Search education
    if latest_resume.education:
        for edu in latest_resume.education:
            edu_text = f"{edu.get('institution')} {edu.get('degree')} {edu.get('field')}".lower()
            if query_lower in edu_text:
                results["matches"]["education"].append(edu)

    # Search certifications
    if latest_resume.certifications:
        for cert in latest_resume.certifications:
            cert_text = f"{cert.get('name')} {cert.get('issuer')}".lower()
            if query_lower in cert_text:
                results["matches"]["certifications"].append(cert)

    # Search raw text
    if latest_resume.raw_text and query_lower in latest_resume.raw_text.lower():
        # Find context around match
        idx = latest_resume.raw_text.lower().find(query_lower)
        start = max(0, idx - 100)
        end = min(len(latest_resume.raw_text), idx + len(query) + 100)
        context = latest_resume.raw_text[start:end]
        results["matches"]["raw_text"] = [{
            "snippet": f"...{context}...",
            "position": idx
        }]

    results["total_matches"] = sum(len(v) if isinstance(v, list) else 1 for v in results["matches"].values())

    return results
