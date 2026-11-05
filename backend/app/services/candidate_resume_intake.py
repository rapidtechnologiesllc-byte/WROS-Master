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
    from app.models.candidate_resume_parsed import PARSER_VERSION, CandidateResumeParsed
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
    row.parser_version = PARSER_VERSION
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


def _same(a: Any, b: Any) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def refresh_from_resume(db: Session, row) -> List[str]:
    """Read a resume on file again with the current parser. What the older parser wrote goes (a row is the parser's only
    if it still reads exactly as parsed); what a person typed stays; what was missed is added. Flushes."""
    from app.services.candidate_service import experience_years

    candidate = db.get(Candidate, row.candidate_id)
    old = {"jobs": [j for j in row.work_history or [] if isinstance(j, dict)],
           "education": [e for e in row.education or [] if isinstance(e, dict)],
           "skills": [str(s) for s in row.skills or []], "certifications": [c for c in row.certifications or [] if isinstance(c, dict)]}
    cid = row.candidate_id
    if candidate is None:
        return []
    parsed = save_parsed_resume(db, candidate, row.raw_text, row.total_experience_years)

    forms = db.query(CandidateExperienceForm).filter(CandidateExperienceForm.candidateID == cid).all()
    for form in forms:
        if any(_same(form.company_name, j.get("employer")) and _same(form.job_title, j.get("title")) for j in old["jobs"]):
            db.delete(form)
    schools = db.query(CandidateEducationForm).filter(CandidateEducationForm.candidateID == cid).all()
    for form in schools:
        if any(_same(form.education_institute, e.get("institution")) and _same(form.degree, e.get("degree")) for e in old["education"]):
            db.delete(form)
    skills = db.query(CandidateProfileSkill).filter(CandidateProfileSkill.candidate_id == cid).all()
    for skill in skills:
        if any(_same(skill.name, s) for s in old["skills"]):
            db.delete(skill)
    certifications = db.query(CandidateCertification).filter(CandidateCertification.candidate_id == cid).all()
    for certificate in certifications:
        if any(_same(certificate.name, c.get("name")) for c in old["certifications"]):
            db.delete(certificate)
    db.flush()

    added: List[str] = []
    present = db.query(CandidateExperienceForm).filter(CandidateExperienceForm.candidateID == cid).all()
    for job in parsed.get("work_history") or []:
        if isinstance(job, dict) and (job.get("employer") or job.get("title")) and not any(
                _same(p.company_name, job.get("employer")) and _same(p.job_title, job.get("title")) for p in present):
            start, end = _month(job.get("start_date")), _month(job.get("end_date"))
            db.add(CandidateExperienceForm(candidateID=cid, company_name=job.get("employer"), job_title=job.get("title"), start_date=start,
                                           end_date=end, year_of_experience=experience_years(start, end), responsibilities=job.get("description")))
            added.append("Experience")
    present = db.query(CandidateEducationForm).filter(CandidateEducationForm.candidateID == cid).all()
    for entry in parsed.get("education") or []:
        if isinstance(entry, dict) and (entry.get("institution") or entry.get("degree")) and not any(
                _same(p.education_institute, entry.get("institution")) and _same(p.degree, entry.get("degree")) for p in present):
            db.add(CandidateEducationForm(candidateID=cid, education_institute=entry.get("institution"), degree=entry.get("degree"),
                                          field_of_study=entry.get("field"),
                                          year_of_passing=str(entry["graduation_year"]) if entry.get("graduation_year") else None))
            added.append("Education")
    present = db.query(CandidateProfileSkill).filter(CandidateProfileSkill.candidate_id == cid).all()
    has_primary = any(p.is_primary for p in present)
    for name in parsed.get("skills") or []:
        name = str(name).strip()
        if name and not any(_same(p.name, name) for p in present):
            db.add(CandidateProfileSkill(candidate_id=cid, name=name[:255], is_primary=not has_primary))
            has_primary = True
            added.append("Skills")
    if ", ".join(old["skills"]) == (candidate.candidateSkills or "") and parsed.get("skills"):
        candidate.candidateSkills = ", ".join(str(s) for s in parsed["skills"])
    present = db.query(CandidateCertification).filter(CandidateCertification.candidate_id == cid).all()
    for certificate in parsed.get("certifications") or []:
        if isinstance(certificate, dict) and certificate.get("name") and not any(_same(p.name, certificate["name"]) for p in present):
            db.add(CandidateCertification(candidate_id=cid, name=str(certificate["name"])[:255], organization=certificate.get("issuer")))
            added.append("Certifications")
    db.flush()
    return sorted(set(added))


def run_resume_refresh_job(db: Session, limit: int = 200) -> Dict[str, int]:
    """Every resume read by an older parser is read again (existing candidates get what new ones get). Commits per
    candidate; a resume that fails stays on the older version and is retried, and the others carry on."""
    from app.models.candidate_resume_parsed import PARSER_VERSION, CandidateResumeParsed

    ids = [r[0] for r in db.query(CandidateResumeParsed.id).filter(CandidateResumeParsed.parser_version != PARSER_VERSION,
                                                                   CandidateResumeParsed.raw_text.isnot(None)).limit(limit).all()]
    refreshed = failed = 0
    for row_id in ids:
        try:
            refresh_from_resume(db, db.get(CandidateResumeParsed, row_id))
            db.commit()
            refreshed += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            logger.error(f"[ResumeIntake] resume row {row_id} could not be read again: {exc}", exc_info=True)
    if refreshed or failed:
        logger.info(f"[ResumeIntake] resumes read again: {refreshed} refreshed, {failed} failed")
    return {"refreshed": refreshed, "failed": failed}


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
