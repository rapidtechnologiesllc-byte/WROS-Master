"""
Guidewire candidate indicator, 2026-08-05. Avinash's own framing:
"our bread and butter comes from Guidewire SI work. We nourish and take
care of these candidates well to be able to convert them." A simple
derived boolean, computed on read (no new persisted column) -- reuses
the real skill-canonicalization infra already built for S-029/HRMS-0429
(app.constants.skill_synonyms, whose "Guidewire" cluster is the spec's
own worked example) rather than inventing a second, parallel string-match
import logging
rule.

Two real sources, checked in order of authority:
1. CandidateSkillTag rows (structured, resume-parsed or manually tagged)
   with skill_canonical == "Guidewire" -- the authoritative source when
   it exists.
2. Raw candidateSkills free text, split the same way
   technical_scoring_service._ensure_job_requirements_parsed() splits
   job.jobSkills, then matched through the same
   SKILL_SYNONYM_REVERSE_INDEX -- covers candidates who haven't had a
   resume parsed yet but do have skills typed in.
3. The candidate's linked job (job title/skills/domain mentioning
   Guidewire) -- covers a freshly-created candidate with no skills
   entered yet but already assigned to a Guidewire requisition.
"""
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.constants.skill_synonyms import SKILL_SYNONYM_REVERSE_INDEX
from app.models.candidate import Candidate
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs

GUIDEWIRE_CANONICAL_SKILL = "Guidewire"

def is_guidewire_candidate(db: Session, candidate: Candidate) -> bool:
    tag = (
        db.query(CandidateSkillTag)
        .filter(
            CandidateSkillTag.candidate_id == candidate.candidateID,
            CandidateSkillTag.skill_canonical == GUIDEWIRE_CANONICAL_SKILL,
        )
        .first()
    )
    if tag is not None:
        return True

    raw_skills = [s.strip() for s in re.split(r"[,;]", candidate.candidateSkills or "") if s.strip()]
    for raw in raw_skills:
        if SKILL_SYNONYM_REVERSE_INDEX.get(raw.lower()) == GUIDEWIRE_CANONICAL_SKILL:
            return True

    if candidate.job_id:
        job: Optional[Jobs] = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job:
            job_text = " ".join(filter(None, [job.jobTitle, job.jobSkills, job.domain])).lower()
            if "guidewire" in job_text:
                return True

    return False
