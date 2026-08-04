"""
Ready-for-opportunity workflow. Avinash's real design (2026-08-04
backlog capture, [[wros_ready_for_opportunity_workflow]] in memory): a
candidate who isn't a fit right now shouldn't just be `closed` -- keep
watching for a future job that fits, nudge only when a real match
appears, never on a recurring schedule ("that doesn't mean we reach
out daily or weekly... only when we know we can convert the
candidate").

Trigger for entering the watch: the ONE real, live "conversation
closed with nothing more to offer" path that exists in this codebase
today is offer_decision_service._handle_decline() -- a declined offer
IS a real "no current fit, worth watching for the next one" moment.
Other theoretical closure paths (e.g. qualification completing with no
open job at all) aren't wired here because they don't have a live
trigger of their own yet in this codebase (qualification_conversation_service.
run_qualification_turn() itself isn't called from any live inbound
path -- a pre-existing, already-flagged gap, not something this story
fixes as a side effect).

Trigger for the nudge: an actual new-job-posted event (scan_new_job_for_matches(),
called as a background task right after a job is published), never a
scheduled poll -- per Avinash's explicit constraint.

Match check is a real, honest v1: keyword overlap between the
candidate's own skills/title text and the new job's skills/title text
(same technique internal_ask_thunder_service.find_matching_candidates()
already uses for the same class of problem), not the full S-037-040
scoring pipeline -- that pipeline is Submission-scoped (built against
an existing application to a specific job) and doesn't cleanly apply
to "does this candidate, who never applied to this NEW job, look like
a fit" without first creating a real Submission, which is itself a
bigger decision (does a match auto-create a Submission, or just
notify?) intentionally left to the human/candidate response, not
assumed here.
"""
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.candidate_opportunity_watch import CandidateOpportunityWatch
from app.models.user import Jobs

MATCH_KEYWORD_MIN_OVERLAP = 2  # at least 2 shared meaningful terms to count as a plausible match

_STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "of", "in", "on", "to", "years",
    "year", "experience", "role", "roles", "required", "preferred", "must", "have",
    "strong", "good", "excellent", "knowledge", "skills", "ability",
}


def _keywords(text: Optional[str]) -> set:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+.#]*", text or "")
    return {t.lower() for t in tokens if len(t) > 1 and t.lower() not in _STOPWORDS}


def start_watching(db: Session, candidate: Candidate, *, reason: str, tenant_id=None) -> CandidateOpportunityWatch:
    """Idempotent -- a candidate already being actively watched doesn't
    get a duplicate row."""
    existing = db.query(CandidateOpportunityWatch).filter(
        CandidateOpportunityWatch.candidate_id == candidate.candidateID,
        CandidateOpportunityWatch.is_active.is_(True),
    ).first()
    if existing:
        return existing

    watch = CandidateOpportunityWatch(
        candidate_id=candidate.candidateID, reason=reason, tenant_id=tenant_id or candidate.tenant_id,
    )
    db.add(watch)
    db.flush()
    return watch


def _is_plausible_match(candidate: Candidate, job: Jobs) -> bool:
    candidate_terms = _keywords(candidate.candidateSkills) | _keywords(candidate.candidateJobTitle)
    job_terms = _keywords(job.jobSkills) | _keywords(job.jobTitle)
    return len(candidate_terms & job_terms) >= MATCH_KEYWORD_MIN_OVERLAP


def scan_new_job_for_matches(db: Session, job: Jobs, *, now: Optional[datetime] = None) -> List[CandidateOpportunityWatch]:
    """Called as a background task right after a job is published --
    never a scheduled scan. Nudges every actively-watched candidate who
    plausibly matches, then deactivates their watch (they're back in an
    active pursuit, not just being watched anymore)."""
    from app.services.thunder_service import (
        ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message,
    )

    now = now or datetime.utcnow()
    active_watches = db.query(CandidateOpportunityWatch).filter(CandidateOpportunityWatch.is_active.is_(True)).all()

    matched = []
    for watch in active_watches:
        candidate = db.query(Candidate).filter(Candidate.candidateID == watch.candidate_id).first()
        if not candidate or not _is_plausible_match(candidate, job):
            continue

        conversation = (
            db.query(CandidateConversation)
            .filter(CandidateConversation.candidate_id == candidate.candidateID)
            .order_by(CandidateConversation.id.desc())
            .first()
        )
        if not conversation:
            continue  # no conversation to nudge through -- leave the watch active, try again on the next new job

        watch.matched_job_id = job.jobID
        watch.matched_at = now
        watch.is_active = False
        db.add(watch)

        try:
            send_thunder_message(
                db, conversation, candidate,
                f"Hi {candidate.candidateFirstName or ''}, a new role just opened that looks like a great fit for "
                f"your background -- {job.jobTitle}. Want us to submit your profile?",
                sender_type="ai_agent", auto_generated=True,
            )
            watch.nudged_at = now
            db.add(watch)
        except (ConsentNotGiven, DuplicateMessageSuppressed, ConversationOwnedByHuman, ThunderPausedError):
            # Real, expected outcomes (same catch-tuple every other
            # send site already tolerates) -- the match is still
            # recorded even if the nudge itself couldn't go out this
            # instant (e.g. a recruiter currently owns the conversation).
            pass

        matched.append(watch)

    db.commit()
    return matched
