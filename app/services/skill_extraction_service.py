"""
S-029/HRMS-0429 -- Skill Extraction & Tagging from Resume.

Real architecture adaptations:
- No `candidates.skills` JSONB column -- the real Candidate model only
  has `candidateSkills` (Text). Cascades a comma-joined string of the
  candidate's full current canonical-skill set (not just the newly
  extracted batch, so a second resume parse or manual addition is
  reflected too) -- same adaptation S-028 already made for skills.
- No event bus -- wired as a direct function call from
  resume_parsing_service.parse_resume() right after skills are known
  (a fresh function added this same session, not an established
  pipeline with its own regression suite to protect -- low risk to
  wire in directly, unlike S-025's decision not to touch
  process_candidate_reply()).
- No candidate_missing_fields table / markFieldReceived() -- writing
  candidateSkills directly is the complete real equivalent.
- "ON CONFLICT ... DO NOTHING" (don't overwrite existing tags) is a
  query-then-skip pattern here (SQL Server, not Postgres), same as
  every other spec'd upsert this round.
"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.constants.skill_synonyms import SKILL_SYNONYM_REVERSE_INDEX
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_skill_tag import CandidateSkillTag


def normalize_skills(raw_skills: List[str]) -> List[Dict]:
    """
    Step 3. Returns a deduplicated list of {canonical, raw, confidence}.
    BR-01: canonical is the only thing used for matching. BR-03:
    unknown skills are preserved as their own canonical (confidence=0.8),
    never discarded.
    """
    seen_canonical = set()
    result = []
    for raw in raw_skills or []:
        raw_str = str(raw).strip()
        if not raw_str:
            continue
        canonical = SKILL_SYNONYM_REVERSE_INDEX.get(raw_str.lower())
        if canonical is not None:
            confidence = 1.0
        else:
            canonical = raw_str  # BR-03: keep as-is, not discarded
            confidence = 0.8

        if canonical in seen_canonical:
            continue  # dedupe: two raw skills normalizing to the same canonical
        seen_canonical.add(canonical)
        result.append({"canonical": canonical, "raw": raw_str, "confidence": confidence})
    return result


def _log_event(db: Session, conversation: Optional[CandidateConversation], event_type: str, event_data: Dict) -> None:
    if conversation is None:
        return
    db.add(ConversationEvent(conversation_id=conversation.id, event_type=event_type, event_data=event_data, triggered_by="system"))
    db.flush()


def extract_and_tag_skills(
    db: Session,
    candidate: Candidate,
    tenant_id: str,
    raw_skills: List[str],
    *,
    conversation: Optional[CandidateConversation] = None,
    source: str = "RESUME",
) -> Dict:
    """Step 4. Never raises. Returns {skills_count, canonical_skills}."""
    normalized = normalize_skills(raw_skills)

    for item in normalized:
        existing = (
            db.query(CandidateSkillTag)
            .filter(
                CandidateSkillTag.tenant_id == tenant_id, CandidateSkillTag.candidate_id == candidate.candidateID,
                CandidateSkillTag.skill_canonical == item["canonical"],
            )
            .first()
        )
        if existing:
            continue  # "DO NOTHING" -- don't overwrite an existing tag

        db.add(CandidateSkillTag(
            tenant_id=tenant_id, candidate_id=candidate.candidateID,
            skill_canonical=item["canonical"], skill_raw=item["raw"], source=source, confidence=item["confidence"],
        ))
        if item["confidence"] < 1.0:  # BR-03
            _log_event(db, conversation, "SKILL_NOT_IN_SYNONYM_LIBRARY", {"raw": item["raw"], "canonical": item["canonical"]})

    db.flush()

    all_tags = (
        db.query(CandidateSkillTag)
        .filter(CandidateSkillTag.tenant_id == tenant_id, CandidateSkillTag.candidate_id == candidate.candidateID)
        .order_by(CandidateSkillTag.skill_canonical.asc())
        .all()
    )
    canonical_skills = [t.skill_canonical for t in all_tags]
    if canonical_skills:
        candidate.candidateSkills = ", ".join(canonical_skills)
        db.add(candidate)

    _log_event(db, conversation, "candidate.skills_extracted", {"skills_count": len(canonical_skills), "canonical_skills": canonical_skills})
    db.commit()

    # S-037/HRMS-0437 BR-03: recalculate technical fit for every job this
    # candidate is linked to. Never raises -- see
    # technical_scoring_service.recalculate_for_candidate()'s own docstring.
    from app.services.technical_scoring_service import recalculate_for_candidate
    recalculate_for_candidate(db, candidate, tenant_id)

    return {"skills_count": len(canonical_skills), "canonical_skills": canonical_skills}


def get_unknown_skill_suggestions(db: Session, tenant_id: str, since_days: int = 7) -> List[Dict]:
    """Step 5's real equivalent of GET /api/admin/skill-suggestions'
    data source -- distinct low-confidence tags added recently, for a
    Lead BA to review and fold into the synonym library."""
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(days=since_days)
    rows = (
        db.query(CandidateSkillTag)
        .filter(CandidateSkillTag.tenant_id == tenant_id, CandidateSkillTag.confidence < 1.0, CandidateSkillTag.added_at >= since)
        .order_by(CandidateSkillTag.added_at.desc())
        .all()
    )
    seen = {}
    for row in rows:
        seen.setdefault(row.skill_canonical, {"skill": row.skill_canonical, "candidate_ids": [], "first_seen": row.added_at})
        seen[row.skill_canonical]["candidate_ids"].append(row.candidate_id)
    return list(seen.values())
