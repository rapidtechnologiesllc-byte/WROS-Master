"""
R-07 -- "createCandidateSafe() is the only path to create a candidate.
No direct inserts, anywhere, ever." This rule was already listed as an
established non-negotiable in CLAUDE.md, but the function itself was
never actually built anywhere in this codebase -- confirmed by grep
(zero hits for `createCandidateSafe` in app/) while researching the
Sub-Vendor Portal requirements, which assume it exists as a prerequisite
for dozens of stories across the corpus, not just that epic.

Two real, pre-existing direct-insert call sites bypassed this rule
before this module existed: app/api/v1/endpoints/create_job.py's public
job-application endpoint and app/api/v1/endpoints/onboarding.py's HR
candidate-creation endpoint. Both are retrofitted to call
create_candidate_safe() instead of constructing `Candidate(...)`
directly -- the whole point of building this is that no call site keeps
bypassing it, not just adding an unused "safe" alternative.

Both existing call sites' own dedup (app.core.database.check_candidate)
matched on email only -- exactly the gap the Development & Review
Standard names as its own worked example: "A duplicate check exists but
only matches one field (e.g., email), missing phone/LinkedIn." Fixed
here: email, phone, and LinkedIn URL are each checked independently, so
a duplicate caught only by phone (or only by LinkedIn) is still caught.
"""
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.candidate import Candidate
from app.utils.uniq_id_generator import candidate_id_generator, generate_password


class DuplicateCandidateError(Exception):
    """Raised instead of creating a second record for the same person.
    Callers decide how to translate this into their own response shape
    (e.g. a 200 "already applied" vs. a 400 error) -- this service layer
    has one behavior (refuse), not an opinion on HTTP semantics."""

    def __init__(self, existing: Candidate, matched_on: str):
        self.existing = existing
        self.matched_on = matched_on
        super().__init__(f"Candidate already exists (matched on {matched_on}): {existing.candidateID}")


def find_duplicate_candidate(
    db: Session, *, email: Optional[str] = None, mobile: Optional[str] = None,
    linkedin_url: Optional[str] = None,
) -> Tuple[Optional[Candidate], Optional[str]]:
    """
    R-07: each identifying field is checked independently -- a match on
    ANY of the three is a duplicate, checked in this order (email,
    phone, LinkedIn) so the reported `matched_on` is deterministic when
    more than one would match.
    """
    if email:
        hit = db.query(Candidate).filter(Candidate.candidateEmail == email).first()
        if hit:
            return hit, "email"

    if mobile:
        hit = db.query(Candidate).filter(Candidate.candidateMobile == mobile).first()
        if hit:
            return hit, "phone"

    if linkedin_url:
        hit = db.query(Candidate).filter(Candidate.linkedin_url == linkedin_url).first()
        if hit:
            return hit, "linkedin"

    return None, None


def create_candidate_safe(
    db: Session,
    *,
    email: str,
    mobile: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    candidate_id: Optional[str] = None,
    plain_password: Optional[str] = None,
    **fields,
) -> Candidate:
    """
    R-07: the only sanctioned path to create a candidate. Runs dedup
    first (fail closed -- raises rather than creating a second record);
    only inserts once no field matches an existing candidate.

    `fields` accepts any other Candidate column by name (candidateRole,
    candidateFirstName, etc.) so this can back every existing candidate-
    creation call site without those call sites needing to change their
    own field mapping, only the creation call itself.
    """
    existing, matched_on = find_duplicate_candidate(db, email=email, mobile=mobile, linkedin_url=linkedin_url)
    if existing:
        raise DuplicateCandidateError(existing, matched_on)

    candidate_id = candidate_id or candidate_id_generator()
    plain_password = plain_password or generate_password()

    candidate = Candidate(
        candidateID=candidate_id,
        candidateEmail=email,
        candidateMobile=mobile,
        linkedin_url=linkedin_url,
        candidatePassword=get_password_hash(plain_password),
        candidateTempPassword=plain_password,
        candidateIsVerified=False,
        **fields,
    )
    db.add(candidate)
    return candidate
