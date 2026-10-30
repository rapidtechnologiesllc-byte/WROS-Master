"""A candidate's resume that arrived by email: stored like an HR upload, parsed, and used to fill the
profile sections that are still empty (Skills, Education, Experience, Certifications).

Used by the HRMS mailbox (a resume forwarded by staff) and by Thunder (a resume the candidate
attached to a reply). A section a recruiter or an earlier resume already filled is never touched:
only an empty section is filled, so nothing anyone entered is overwritten.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateEducationForm, CandidateExperienceForm
from app.models.candidate_profile_extras import CandidateCertification, CandidateProfileSkill
from app.models.document import CandidateDocument

logger = logging.getLogger(__name__)

RESUME_DOCUMENT_TYPE = "resume"


def has_resume(db: Session, candidate_id: str) -> bool:
    """A resume document is on file (what the profile's Resume section shows)."""
    return db.query(CandidateDocument.id).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.document_type == RESUME_DOCUMENT_TYPE,
        CandidateDocument.is_deleted.isnot(True),
    ).first() is not None


def save_parsed_resume(db: Session, candidate: Candidate, text: str,
                       total_experience_years: Any = None) -> Dict[str, Any]:
    """Parse the resume text into candidate_resume_parsed (one row per candidate, replaced) and
    return the parsed fields. Flushes; the caller commits."""
    from app.models.candidate_resume_parsed import CandidateResumeParsed
    from app.services.resume_completeness_service import calculate_resume_completeness
    from app.services.resume_parser_slm import ResumeSLM

    parsed = ResumeSLM.parse_resume(text)
    row = db.query(CandidateResumeParsed).filter_by(candidate_id=candidate.candidateID).first()
    if row is None:
        row = CandidateResumeParsed(candidate_id=candidate.candidateID, tenant_id=str(candidate.tenant_id))
        db.add(row)
    years = total_experience_years if isinstance(total_experience_years, (int, float)) else None
    row.raw_text, row.full_name, row.email, row.phone = text, parsed["full_name"], parsed["email"], parsed["phone"]
    row.current_title, row.current_employer = parsed["current_title"], parsed["current_employer"]
    row.work_history, row.education, row.skills = parsed["work_history"], parsed["education"], parsed["skills"]
    row.certifications, row.languages = parsed["certifications"], parsed["languages"]
    row.total_experience_years = years
    row.total_experience_months = round(years * 12) if years is not None else None
    row.parsed_at = datetime.utcnow()
    db.flush()
    score = calculate_resume_completeness(row)
    row.resume_completeness_score, row.score_calculated_at = score, datetime.utcnow()
    candidate.resume_completeness_score = score
    return parsed


def _month(value: Optional[str]) -> Optional[date]:
    """'YYYY-MM' (the parser's format) as the first of that month."""
    if not value:
        return None
    try:
        year, month = str(value)[:7].split("-")
        return date(int(year), int(month), 1)
    except ValueError:
        logger.warning(f"[ResumeIntake] ignoring unreadable resume date {value!r}")
        return None


def fill_empty_sections(db: Session, candidate: Candidate, parsed: Dict[str, Any]) -> List[str]:
    """Fill each empty profile section from the parsed resume. Returns the sections filled.
    Flushes; the caller commits."""
    from app.services.candidate_service import experience_years

    candidate_id = candidate.candidateID
    filled: List[str] = []

    education = [e for e in parsed.get("education") or [] if isinstance(e, dict) and (e.get("institution") or e.get("degree"))]
    if education and not db.query(CandidateEducationForm.formID).filter(
            CandidateEducationForm.candidateID == candidate_id).first():
        for entry in education:
            db.add(CandidateEducationForm(
                candidateID=candidate_id, education_institute=entry.get("institution"), degree=entry.get("degree"),
                field_of_study=entry.get("field"),
                year_of_passing=str(entry["graduation_year"]) if entry.get("graduation_year") else None,
            ))
        filled.append("Education")

    jobs = [j for j in parsed.get("work_history") or [] if isinstance(j, dict) and (j.get("employer") or j.get("title"))]
    if jobs and not db.query(CandidateExperienceForm.formID).filter(
            CandidateExperienceForm.candidateID == candidate_id).first():
        for job in jobs:
            start, end = _month(job.get("start_date")), _month(job.get("end_date"))
            db.add(CandidateExperienceForm(
                candidateID=candidate_id, company_name=job.get("employer"), job_title=job.get("title"),
                start_date=start, end_date=end, year_of_experience=experience_years(start, end),
                responsibilities=job.get("description"),
            ))
        filled.append("Experience")

    skills = [str(s).strip() for s in parsed.get("skills") or [] if str(s).strip()]
    if skills and not db.query(CandidateProfileSkill.id).filter(
            CandidateProfileSkill.candidate_id == candidate_id).first():
        for index, name in enumerate(skills):
            db.add(CandidateProfileSkill(candidate_id=candidate_id, name=name[:255], is_primary=index == 0))
        if not candidate.candidateSkills:
            candidate.candidateSkills = ", ".join(skills)
        filled.append("Skills")

    certifications = [c for c in parsed.get("certifications") or [] if isinstance(c, dict) and c.get("name")]
    if certifications and not db.query(CandidateCertification.id).filter(
            CandidateCertification.candidate_id == candidate_id).first():
        for cert in certifications:
            db.add(CandidateCertification(candidate_id=candidate_id, name=str(cert["name"])[:255],
                                          organization=cert.get("issuer")))
        filled.append("Certifications")

    db.flush()
    if filled:
        logger.info(f"[ResumeIntake] {candidate_id}: filled {filled} from the resume")
    return filled


def store_resume_document(db: Session, candidate: Candidate, name: str, content: bytes, uploaded_by: str,
                          uploaded_by_user_id: Optional[str], uploaded_by_name: str) -> Optional[CandidateDocument]:
    """Upload the resume like the HR resume upload does (SharePoint + candidate_documents) and
    commit. uploaded_by is the document's uploader (a user or candidate id); uploaded_by_user_id
    the staff user for the candidate's history (None when the candidate sent it). Returns None when document storage is not configured (the caller says so to a human);
    raises RuntimeError when Graph or SharePoint fails."""
    from fastapi import HTTPException

    from app.core.graph_auth import GraphServiceAuth, get_graph_token
    from app.services import document_service
    from app.services.candidate_activity_service import log_resume_uploaded
    from app.services.virus_scan_service import scan_document_content

    if not (GraphServiceAuth.is_configured() and document_service.SHAREPOINT_SITE_ID
            and document_service.SHAREPOINT_DRIVE_ID):
        return None
    service = document_service.DocumentService(db)
    filename = service.generate_unique_filename(name, candidate.candidateID, RESUME_DOCUMENT_TYPE)
    try:
        stored = service.upload_to_sharepoint(get_graph_token(), candidate.candidateID, RESUME_DOCUMENT_TYPE,
                                              content, filename)
    except HTTPException as exc:
        raise RuntimeError(f"Resume upload for {candidate.candidateID} failed: {exc.detail}") from exc
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    document = service.save_document_metadata(
        candidate_id=candidate.candidateID, document_type=RESUME_DOCUMENT_TYPE, original_filename=name,
        unique_filename=filename, file_size=len(content), file_extension=extension, sharepoint_data=stored,
        uploaded_by=uploaded_by)
    scan_document_content(document, content)
    log_resume_uploaded(db, candidate.candidateID, name, len(content) / (1024 * 1024),
                        uploaded_by_user_id=uploaded_by_user_id, uploaded_by_name=uploaded_by_name)
    db.commit()
    return document
