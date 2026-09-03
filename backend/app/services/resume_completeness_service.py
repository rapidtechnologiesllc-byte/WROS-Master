"""
import logging
S-030/HRMS-0430 -- Resume Completeness Score.

BR-01: distinct from profile completeness (get_missing_fields()) --
this measures the QUALITY of the parsed resume document itself, never
combined with the "did Thunder collect the 10 required fields" score.

Real architecture: candidate_resume_parsed already exists (S-028) with
work_history/education/skills/certifications JSON columns and
total_experience_months -- exactly the scoring inputs this story needs,
no adaptation required here. resume_completeness_score/score_calculated_at
were added directly to that table (migration 0eb7ca2cdb11) plus a
denormalized resume_completeness_score on Candidate, per the spec's
own Step 2/data mapping.

BR-02 (must run AFTER skill extraction, or skills score 0): enforced
by call order in resume_parsing_service.parse_resume() -- this
function is called only after extract_and_tag_skills() has already
updated candidate_resume_parsed.skills for this parse.
"""
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed

MIN_EXPERIENCE_MONTHS_FOR_BONUS = 60  # 5 years, matches HRMS-P601's own threshold

def _score_contact_info(parsed: CandidateResumeParsed) -> int:
    has_name = bool(parsed.full_name)
    has_contact = bool(parsed.email or parsed.phone)
    return 10 if (has_name and has_contact) else 0

def _score_work_history(parsed: CandidateResumeParsed) -> int:
    entries = parsed.work_history or []
    if len(entries) >= 2:
        return 20
    if len(entries) >= 1:
        return 10
    return 0

def _score_work_descriptions(parsed: CandidateResumeParsed) -> int:
    entries = parsed.work_history or []
    with_description = sum(1 for e in entries if isinstance(e, dict) and str(e.get("description") or "").strip())
    return min(with_description, 3) * 5  # max 15

def _score_education(parsed: CandidateResumeParsed) -> int:
    return 10 if (parsed.education or []) else 0

def _score_skills(parsed: CandidateResumeParsed) -> int:
    count = len(parsed.skills or [])
    if count >= 10:
        return 15
    if count >= 5:
        return 10
    if count >= 1:
        return 5
    return 0

def _score_certifications(parsed: CandidateResumeParsed) -> int:
    return 10 if (parsed.certifications or []) else 0

def _score_experience_bonus(parsed: CandidateResumeParsed) -> int:
    months = parsed.total_experience_months or 0
    return 10 if months >= MIN_EXPERIENCE_MONTHS_FOR_BONUS else 0

def calculate_resume_completeness(parsed: Optional[CandidateResumeParsed]) -> int:
    """Step 1's scoring criteria. Returns 0 for a missing/empty record."""
    if parsed is None:
        return 0
    score = (
        _score_contact_info(parsed)
        + _score_work_history(parsed)
        + _score_work_descriptions(parsed)
        + _score_education(parsed)
        + _score_skills(parsed)
        + _score_certifications(parsed)
        + _score_experience_bonus(parsed)
    )
    return min(score, 100)

def update_resume_completeness_score(db: Session, candidate: Candidate, tenant_id: str) -> Dict:
    """Step 2. Loads candidate_resume_parsed, scores it, stores the
    result on both tables (BR: denormalized for fast reads)."""
    parsed = db.query(CandidateResumeParsed).filter(CandidateResumeParsed.candidate_id == candidate.candidateID, CandidateResumeParsed.tenant_id == tenant_id).first()
    score = calculate_resume_completeness(parsed)

    if parsed is not None:
        parsed.resume_completeness_score = score
        parsed.score_calculated_at = datetime.utcnow()
        db.add(parsed)

    candidate.resume_completeness_score = score
    db.add(candidate)
    db.commit()
    return {"resume_completeness_score": score}
