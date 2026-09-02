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
import re
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.candidate import Candidate
from app.utils.uniq_id_generator import candidate_id_generator, generate_password


class DuplicateCandidateError(Exception):
    """Raised when attempting to create a duplicate candidate.
    Used for logging/audit only - duplicates are now tracked as multiple applications.
    Allows Thunder to analyze: is person genuinely interested or randomly applying?"""

    def __init__(self, existing: Candidate, matched_on: str):
        self.existing = existing
        self.matched_on = matched_on
        super().__init__(f"Candidate matched existing record (on {matched_on}): {existing.candidateID}")


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
) -> Tuple[Candidate, bool]:
    """
    R-07: the only sanctioned path to create a candidate. Runs dedup check;
    if duplicate found by email/phone/LinkedIn, returns existing candidate
    so caller can track as a new job application instead of duplicate rejection.

    Enables Thunder to analyze application patterns: is this person genuinely
    interested (applying to related roles) or randomly applying (unrelated roles)?

    Returns: (Candidate object, is_new: bool)
      - is_new=True: newly created candidate
      - is_new=False: existing candidate (duplicate match), caller should create job application
    """
    existing, matched_on = find_duplicate_candidate(db, email=email, mobile=mobile, linkedin_url=linkedin_url)
    if existing:
        # Duplicate found - return existing candidate, let caller track as multiple application
        return existing, False

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
        associated_bu_id=None,  # BU lifecycle: New candidates are org-wide (NULL)
        **fields,
    )
    db.add(candidate)

    # S-012/HRMS-0412 -- Thunder's WhatsApp send path (send_thunder_
    # message) hard-requires a whatsapp_outreach ConsentRecord and fails
    # closed without one. A phone number given at application time is
    # this codebase's consent signal for WhatsApp outreach about THIS
    # application -- every candidate-creation call site funnels through
    # this one R-07-sanctioned function, so capturing it here (rather
    # than per-call-site) means Thunder's first-engagement message can
    # actually send for any real candidate, not just ones created
    # through the public web chat's explicit checkbox.
    if mobile:
        from app.models.consent import ConsentRecord
        db.add(ConsentRecord(
            subject_type="candidate", subject_id=candidate_id,
            consent_type="whatsapp_outreach", consent_given=True,
            captured_by="candidate_creation",
        ))

    return candidate, True  # Return (candidate, is_new=True) for new candidates


# ---------------------------------------------------------------------------
# R-01 (HRMS-P601) -- 5-year experience floor.
#
# REMOVED 2026-07-23 as a creation-time BLOCK, direct instruction from
# Avinash: "we should still gather all resumes not stop building our
# DB." A candidate below the floor (or not yet experience-verified) is
# now created exactly like any other candidate -- no BU Head override
# mechanism needed anymore since nothing blocks. The rule itself is
# still enforced for real at the point it actually matters --
# submission/matching to a role requiring 5+ years -- via
# app.services.submission_service.check_experience_eligibility(),
# unaffected by this change. parse_experience_to_months() below is kept:
# total_experience_months is still computed and stored at creation time
# so that submission-time gate has real data to check against.
# ---------------------------------------------------------------------------

_EXPERIENCE_YEARS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")


def parse_experience_to_months(raw: Optional[str]) -> Optional[int]:
    """
    Extracts the leading numeric year value from free text ("3.5",
    "5 years", "10+ yrs"). Returns None -- not 0 -- for non-numeric text
    ("Fresher", "Intern", blank), so the eligibility check correctly
    falls into the same "not verified" fail-closed state the field
    already specifies for NULL, rather than a fabricated zero.
    """
    if not raw:
        return None
    match = _EXPERIENCE_YEARS_PATTERN.search(raw)
    if not match:
        return None
    return round(float(match.group(1)) * 12)
