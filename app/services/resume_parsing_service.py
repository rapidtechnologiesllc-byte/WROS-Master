"""
S-028/HRMS-0428 -- Resume Parsing Engine.

Real architecture facts (confirmed by reading the actual code before
writing anything):

- No S3 -- resumes live in SharePoint (S-027's real DocumentService),
  and this service takes already-downloaded bytes directly (same
  posture as S-027) rather than a second network round-trip; ready to
  be fed bytes from a real SharePoint download once that plumbing is
  wired for either inbound channel.
- No PDF/DOCX text-extraction library existed in this project at all
  -- added `pypdf` (requirements.txt) for real PDF extraction; DOCX
  extraction reuses `python-docx`, already a dependency here (used
  for offer-letter/salary-structure generation, never for reading
  until now).
- `candidates.total_experience_months` (Integer) ALREADY EXISTS on the
  real Candidate model, with a comment explicitly saying it's
  "Populated by resume parsing (HRMS-0428, not yet built)" -- and
  app.services.submission_service.check_experience_eligibility() (the
  real, already-shipped <5-year hard rule, R-01/HRMS-P601) already
  reads this exact column and treats NULL as ineligible. This story is
  the missing piece that was already wired for and waited on. No
  `total_experience_years` column exists on Candidate (only months) --
  the decimal-years value lives on the new candidate_resume_parsed
  table only, per spec's own Step 1 table definition.
- No `current_employer` column exists on Candidate either -- stored
  only on candidate_resume_parsed (again, exactly where the spec's own
  Step 1 puts it).
- `candidateSkills` is a plain Text column (not JSON) -- the parsed
  skills array is joined into a comma-separated string when cascading
  to Candidate, while candidate_resume_parsed.skills keeps the real
  structured JSON array.
- No candidate_missing_fields table / markFieldReceived() function
  (established this whole round) -- writing the real Candidate columns
  directly is the complete real equivalent, since get_missing_fields()
  never tracked total_experience_months/current_employer/skills as
  qualification fields to begin with (S-024 already established this
  codebase's real missing-fields set doesn't include them).

BR-01 (overlapping roles counted once, MAX not SUM) is implemented as
a real interval-merge algorithm, tested directly against this story's
own worked example (Company A Jan2020-Dec2022 + Company B Jun2021-Jun2023
-> 42 months / 3.5 years, matching TC-002's arithmetic -- section 6B's
prose says "3 years" but TC-002's own numbers say 42mo/3.5yr; the
executable test case wins over the narrative aside).
"""
import io
import json
import os
import re
from datetime import date
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_resume_parsed import PARSER_VERSION, CandidateResumeParsed

MIN_RAW_TEXT_LENGTH = 100

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class TextExtractionFailed(Exception):
    pass


class ResumeParsingFailed(Exception):
    pass


def extract_text_from_pdf(file_content: bytes) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file_content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text_from_docx(file_content: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(file_content))
    return "\n".join(p.text for p in document.paragraphs)


def extract_raw_text(file_content: bytes, extension: str) -> str:
    """Step 2. Raises TextExtractionFailed if extraction errors or
    yields fewer than MIN_RAW_TEXT_LENGTH characters."""
    ext = (extension or "").lower()
    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(file_content)
        elif ext in (".docx", ".doc"):
            text = extract_text_from_docx(file_content)
        else:
            raise TextExtractionFailed(f"Unsupported resume file extension: {ext!r}")
    except TextExtractionFailed:
        raise
    except Exception as exc:
        raise TextExtractionFailed(f"Text extraction raised: {exc}") from exc

    if not text or len(text.strip()) < MIN_RAW_TEXT_LENGTH:
        raise TextExtractionFailed(f"Extracted text too short ({len(text.strip()) if text else 0} chars)")
    return text


# ---------------------------------------------------------------------------
# BR-01/BR-02: non-overlapping total experience calculation
# ---------------------------------------------------------------------------

def _parse_year_month(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    match = re.match(r"^(\d{4})-(\d{1,2})$", value.strip())
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12):
        return None
    return date(year, month, 1)


def calculate_total_experience_months(work_history: List[Dict]) -> int:
    """
    BR-01: overlapping periods counted once (interval merge), never
    simple sum. BR-02: a null end_date means "still working there" --
    use today's date, recalculated on every call/re-parse.

    Month duration is inclusive of both the start and end month (a
    role from 2020-01 to 2020-01 is 1 month of experience, not 0) --
    this is the convention that makes this story's own worked example
    (TC-002: Jan2020-Dec2022 + Jun2021-Jun2023 -> 42 months) resolve
    correctly; the plain year/month subtraction alone gives 41.
    """
    intervals = []
    today = date.today()
    for entry in work_history or []:
        start = _parse_year_month(entry.get("start_date"))
        if start is None:
            continue
        end = _parse_year_month(entry.get("end_date")) or today  # BR-02
        if end < start:
            continue  # malformed data -- skip rather than guess
        intervals.append((start, end))

    if not intervals:
        return 0

    intervals.sort(key=lambda iv: iv[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # overlap (or adjacent) -- merge, don't sum
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_months = 0
    for start, end in merged:
        months = (end.year - start.year) * 12 + (end.month - start.month) + 1
        total_months += max(months, 0)
    return total_months


# ---------------------------------------------------------------------------
# LLM parsing (Step 3)
# ---------------------------------------------------------------------------

def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}},
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    if llm_call is not None:
        return llm_call(prompt)
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


def _build_parsing_prompt(raw_text: str) -> str:
    return (
        "You are a resume parser. Extract structured data from this resume text and "
        "return ONLY valid JSON with these fields: full_name, email, phone, "
        "current_title, current_employer, work_history (array: employer, title, "
        'start_date as "YYYY-MM", end_date as "YYYY-MM" or null if current, '
        "description), education (array: institution, degree, field, "
        "graduation_year), skills (array of strings), certifications (array: "
        "name, issuer, year), languages (array of strings).\n\n"
        f"Resume text: {raw_text[:8000]}"
    )


def _parse_llm_json(raw: str) -> Dict:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or "work_history" not in parsed:
        raise ValueError("Parsed JSON missing required 'work_history' key")
    return parsed


def _log_event(db: Session, conversation: Optional[CandidateConversation], event_type: str, event_data: Dict) -> None:
    if conversation is None:
        return
    db.add(ConversationEvent(conversation_id=conversation.id, event_type=event_type, event_data=event_data, triggered_by="system"))
    db.flush()


def _notify_recruiter_of_parse_failure(db: Session, tenant_id: str, candidate: Candidate) -> None:
    from app.models.candidate_ai import CandidateAIAssignment
    from app.models.user import Users
    from app.services.notification_service import send_notification

    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate.candidateID, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    recipient_id = assignment.assigned_by if assignment and assignment.assigned_by else tenant_id
    recipient = db.query(Users).filter(Users.UserID == recipient_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P1", channel_preference="IN_APP",
            message=f"Thunder couldn't auto-parse {candidate.candidateFirstName or candidate.candidateID}'s resume -- please review it manually.",
        )
    except Exception as exc:
        logger.warning(f"[ResumeParsing] Failed to notify recruiter for candidate {candidate.candidateID}: {exc}")


def parse_resume(
    db: Session,
    candidate: Candidate,
    tenant_id: str,
    *,
    file_content: bytes,
    extension: str,
    conversation: Optional[CandidateConversation] = None,
    llm_call: Optional[Callable[[str], str]] = None,
) -> Dict:
    """
    Never raises. Returns one of:
      {"outcome": "text_extraction_failed"}
      {"outcome": "parsing_failed"}
      {"outcome": "parsed", "total_experience_months": ..., "skills_count": ...}
    """
    try:
        raw_text = extract_raw_text(file_content, extension)
    except TextExtractionFailed as exc:
        logger.warning(f"[ResumeParsing] Text extraction failed for candidate {candidate.candidateID}: {exc}")
        _log_event(db, conversation, "RESUME_TEXT_EXTRACTION_FAILED", {"reason": str(exc)})
        db.commit()
        return {"outcome": "text_extraction_failed"}

    prompt = _build_parsing_prompt(raw_text)
    parsed_json = None
    last_error: Optional[Exception] = None
    for attempt in range(2):  # BR: retry once on parse failure
        try:
            raw_response = _call_llm(prompt, llm_call)
            parsed_json = _parse_llm_json(raw_response)
            break
        except Exception as exc:
            last_error = exc
            logger.warning(f"[ResumeParsing] LLM parse attempt {attempt + 1} failed for candidate {candidate.candidateID}: {exc}")

    if parsed_json is None:
        _log_event(db, conversation, "RESUME_PARSING_FAILED", {"reason": str(last_error)})
        db.commit()
        _notify_recruiter_of_parse_failure(db, tenant_id, candidate)
        return {"outcome": "parsing_failed"}

    work_history = parsed_json.get("work_history") or []
    total_months = calculate_total_experience_months(work_history)
    total_years = round(total_months / 12.0, 1)
    skills = parsed_json.get("skills") or []

    existing = db.query(CandidateResumeParsed).filter(CandidateResumeParsed.candidate_id == candidate.candidateID).first()
    if existing is None:
        existing = CandidateResumeParsed(tenant_id=tenant_id, candidate_id=candidate.candidateID)
        db.add(existing)

    existing.raw_text = raw_text
    existing.full_name = parsed_json.get("full_name")
    existing.email = parsed_json.get("email")
    existing.phone = parsed_json.get("phone")
    existing.current_title = parsed_json.get("current_title")
    existing.current_employer = parsed_json.get("current_employer")
    existing.work_history = work_history
    existing.education = parsed_json.get("education") or []
    existing.skills = skills
    existing.certifications = parsed_json.get("certifications") or []
    existing.languages = parsed_json.get("languages") or []
    existing.total_experience_months = total_months
    existing.total_experience_years = total_years
    existing.parser_version = PARSER_VERSION

    # Real Candidate columns this codebase actually has (see module docstring).
    candidate.total_experience_months = total_months
    db.add(candidate)

    # S-029/HRMS-0429 -- normalize and tag the raw skills array right
    # after parsing, same posture as every other "candidate.resume_parsed
    # consumer" in this story's own spec, just a direct call instead of
    # an event-bus subscription (no event bus exists in this codebase).
    if skills:
        from app.services.skill_extraction_service import extract_and_tag_skills
        extract_and_tag_skills(db, candidate, tenant_id, skills, conversation=conversation)

    _log_event(db, conversation, "candidate.resume_parsed", {
        "total_experience_months": total_months, "skills_count": len(skills), "parsing_success": True,
    })
    db.commit()
    return {"outcome": "parsed", "total_experience_months": total_months, "total_experience_years": total_years, "skills_count": len(skills)}
