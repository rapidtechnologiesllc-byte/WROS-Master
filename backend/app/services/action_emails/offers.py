"""Offer emails: created, sent to the hiring manager for approval, approved or rejected by them,
released to the candidate, the candidate's answer, cancelled. The people on an offer: its hiring
manager, reporting manager, creator, the job's recruiter and the candidate's assigned recruiter.

These replace the direct EmailService sends the offer endpoints made before (a single Graph call,
no retry): every offer email now goes through the staff mail path."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.offer_letter import OfferLetter
from app.models.user import Jobs, Users
from app.services.action_emails.core import Team, add, after_commit, name_of, send

OFFERS_PATH = "/offers-listing"


def offer_team(db: Session, offer: OfferLetter) -> Team:
    team: Team = {}
    add(team, offer.hiring_manager_id, "Hiring Manager")
    add(team, offer.reporting_manager_id, "Reporting Manager")
    add(team, offer.created_by, "Created the offer")
    job = db.query(Jobs).filter(Jobs.jobID == offer.job_id).first() if offer.job_id else None
    if job is not None:
        add(team, job.recuriterID, "Recruiter")
    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    if candidate is not None:
        add(team, candidate.assigned_recruiter_id, "Candidate's Recruiter")
    return team


def _label(db: Session, offer: OfferLetter) -> str:
    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    name = (f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
            if candidate is not None else "") or offer.candidate_id
    return f"{name}, {offer.position}" if offer.position else name


def _facts(offer: OfferLetter) -> str:
    return f"Salary: {offer.salary}. Joining: {offer.joining_date}. Offer expires: {offer.offer_expire_date}."


def _send(db: Session, offer: OfferLetter, team: Team, *, actor_id: Optional[str], event: str, subject: str,
          opening: str, extra: Optional[str] = None) -> int:
    return send(db, team, actor_id=actor_id, key=f"offer-{event}-{offer.id}", subject=subject, opening=opening,
                details=[_facts(offer), extra], link_path=OFFERS_PATH, link_label="Open Offers")


@after_commit("offers")
def notify_offer_created(db: Session, offer: OfferLetter, *, actor: Users) -> int:
    label = _label(db, offer)
    return _send(db, offer, offer_team(db, offer), actor_id=actor.UserID, event="created",
                 subject=f"New offer: {label}", opening=f"{name_of(actor)} created an offer for {label}.")


@after_commit("offers")
def notify_offer_awaiting_approval(db: Session, offer: OfferLetter, *, actor: Users) -> int:
    """The generated letter waits for the hiring manager's approval."""
    label = _label(db, offer)
    return _send(db, offer, {offer.hiring_manager_id: ["Hiring Manager"]} if offer.hiring_manager_id else {},
                 actor_id=actor.UserID, event="awaiting-approval", subject=f"Approve the offer: {label}",
                 opening=f"{name_of(actor)} generated the offer letter for {label}; it is waiting for your approval.")


@after_commit("offers")
def notify_offer_decided(db: Session, offer: OfferLetter, *, actor: Users) -> int:
    """The hiring manager approved or rejected the offer (approval_status)."""
    label = _label(db, offer)
    decision = (offer.approval_status or "").lower()
    return _send(db, offer, offer_team(db, offer), actor_id=actor.UserID, event=f"decided-{decision}",
                 subject=f"Offer {decision}: {label}", opening=f"{name_of(actor)} {decision} the offer for {label}.",
                 extra=f"Notes: {offer.approval_notes}" if offer.approval_notes else None)


@after_commit("offers")
def notify_offer_released(db: Session, offer: OfferLetter, *, actor: Users) -> int:
    label = _label(db, offer)
    return _send(db, offer, offer_team(db, offer), actor_id=actor.UserID, event="released",
                 subject=f"Offer released: {label}",
                 opening=f"{name_of(actor)} released the offer to {label.split(',')[0]}.")


@after_commit("offers")
def notify_offer_answered(db: Session, offer: OfferLetter, *, message: Optional[str] = None) -> int:
    """The candidate accepted or declined (offer_status); the actor is the candidate, not staff."""
    label = _label(db, offer)
    answer = "accepted" if offer.offer_status == "Accepted" else "declined"
    return _send(db, offer, offer_team(db, offer), actor_id=None, event=f"answered-{answer}",
                 subject=f"Offer {answer}: {label}", opening=f"{label.split(',')[0]} {answer} the offer.",
                 extra=f"Their message: {message}" if message else None)


@after_commit("offers")
def notify_offer_cancelled(db: Session, offer: OfferLetter, *, actor: Users) -> int:
    label = _label(db, offer)
    return _send(db, offer, offer_team(db, offer), actor_id=actor.UserID, event="cancelled",
                 subject=f"Offer cancelled: {label}", opening=f"{name_of(actor)} cancelled the offer for {label}.")
