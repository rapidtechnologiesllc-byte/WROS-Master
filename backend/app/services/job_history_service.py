"""What has happened on a job (CEO 2026-11-05: "Job doesnt have a history tab ... it has to be interlinked and
autonomous"). Nobody logs anything: the timeline is read from the records the work already leaves behind, so the job,
its client, opportunity, candidates, interviews, offers, placements, sub-vendors and Flash's search stay one story.
Each event links to the record it came from.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_history import CandidateHistory
from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.offer import Offer
from app.models.opportunity import Opportunity
from app.models.submission import Submission
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest
from app.models.user import Interview, InterviewPanel, Jobs, Users

CLOSED_INTERVIEW_STATUSES = ("Cancelled",)
ACCEPTED_OFFER_STATUSES = ("ACCEPTED", "SIGNED")


def _name(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "A candidate"
    return " ".join(p for p in (candidate.candidateFirstName, candidate.candidateLastName) if p) or candidate.candidateEmail


def _user(db: Session, user_id: Optional[str]) -> Optional[str]:
    user = db.get(Users, user_id) if user_id else None
    return (user.UserName or user.UserEmail) if user is not None else None


def _event(at, kind: str, title: str, *, detail: Optional[str] = None, actor: Optional[str] = None,
           link: Optional[str] = None) -> Optional[Dict]:
    if at is None:
        return None
    return {"at": at.isoformat() if isinstance(at, datetime) else str(at), "kind": kind, "title": title, "detail": detail,
            "actor": actor, "link": link}


def job_history(db: Session, job: Jobs) -> List[Dict]:
    """Every event on the job, newest first."""
    candidates: Dict[str, Optional[Candidate]] = {}

    def person(candidate_id: str) -> Candidate:
        if candidate_id not in candidates:
            candidates[candidate_id] = db.get(Candidate, candidate_id)
        return candidates[candidate_id]

    def candidate_link(candidate_id: str) -> str:
        return f"/candidates/{candidate_id}"

    client = db.get(Client, job.client_id) if job.client_id else None
    opportunity = db.get(Opportunity, job.opportunity_id) if job.opportunity_id else None
    origin = f" from the {client.company_name} opportunity" if opportunity is not None and client is not None else ""
    events = [_event(job.jobCreatedAt, "JOB", f"Job created{origin}", actor=_user(db, job.created_by),
                     detail=f"{job.jobTitle}, {job.noOfPositions or 1} position(s). Hiring manager: {_user(db, job.hiringManagerID) or 'not set'}.",
                     link="/opportunity-pipeline" if opportunity is not None else None)]

    logged = set()
    for row in db.query(CandidateHistory).filter(CandidateHistory.job_id == job.jobID).all():
        logged.add((row.candidateID, row.event_type))
        events.append(_event(row.event_at, "CANDIDATE", f"{_name(person(row.candidateID))}: {row.event_type}", detail=row.note,
                             actor=row.performed_by_name, link=candidate_link(row.candidateID)))
    for row in db.query(CandidateJobApplication).filter(CandidateJobApplication.job_id == job.jobID).all():
        if (row.candidate_id, "Applied") not in logged:
            events.append(_event(row.applied_at, "CANDIDATE", f"{_name(person(row.candidate_id))} submitted to this job",
                                 detail=f"Status: {row.application_status}", link=candidate_link(row.candidate_id)))
    for row in db.query(Submission).filter(Submission.demand_id == job.jobID).all():
        events.append(_event(row.submitted_at or row.created_at, "SUBMISSION",
                             f"{_name(person(row.candidate_id))} submitted to the client", detail=f"Status: {row.status}",
                             actor=_user(db, row.submitted_by_user_id), link=candidate_link(row.candidate_id)))
    rows = (db.query(Interview, InterviewPanel).join(InterviewPanel, InterviewPanel.id == Interview.panel_id)
            .filter(InterviewPanel.job_id == job.jobID).all())
    for interview, panel in rows:
        events.append(_event(interview.start_time, "INTERVIEW",
                             f"{panel.round_name or 'Interview'} with {_name(person(interview.candidate_id))}",
                             detail=f"Status: {interview.status}", link=f"{candidate_link(interview.candidate_id)}?tab=interview"))
    for row in db.query(Offer).filter(Offer.job_id == job.jobID).all():
        events.append(_event(row.sent_at or row.created_at, "OFFER", f"Offer for {_name(person(row.candidate_id))}",
                             detail=f"Status: {row.status}", actor=_user(db, row.created_by_user_id),
                             link=candidate_link(row.candidate_id)))
    for row in db.query(EmployeeAllocation).filter(EmployeeAllocation.demand_id == job.jobID).all():
        events.append(_event(row.created_at, "PLACEMENT", f"Allocation: {row.role or job.jobTitle}", detail=f"Status: {row.status}",
                             link=f"/employees/{row.employee_id}"))
    requests = (db.query(SubVendorRequest, SubVendorAccount).join(SubVendorAccount, SubVendorAccount.id == SubVendorRequest.sub_vendor_id)
                .filter(SubVendorRequest.demand_id == job.jobID).all())
    for request, vendor in requests:
        events.append(_event(request.notified_at, "SUB_VENDOR", f"Role sent to {vendor.company_name}", link="/sub-vendors?view=roles"))
    from app.models.flash_mission import FlashMission

    mission = db.query(FlashMission).filter(FlashMission.job_id == job.jobID).first()
    if mission is not None:
        events.append(_event(mission.created_at, "FLASH", "Flash started the search", detail=f"State: {mission.state}"))
    events = [e for e in events if e is not None]
    return sorted(events, key=lambda e: e["at"], reverse=True)


def job_summary(db: Session, job: Jobs) -> Dict:
    """The job's figures from its own records; None when there is nothing to measure yet."""
    now = datetime.utcnow()
    upcoming = (db.query(Interview).join(InterviewPanel, InterviewPanel.id == Interview.panel_id)
                .filter(InterviewPanel.job_id == job.jobID, Interview.start_time > now,
                        Interview.status.notin_(CLOSED_INTERVIEW_STATUSES)).count())
    offers = db.query(Offer).filter(Offer.job_id == job.jobID).all()
    decided = [o for o in offers if o.accepted_at or o.rejected_at]
    accepted = [o for o in decided if o.accepted_at]
    starts = [o.accepted_at for o in accepted]
    days = (min(starts) - job.jobCreatedAt).days if starts and job.jobCreatedAt else None
    return {"upcoming_interviews": upcoming, "days_to_first_accepted_offer": days,
            "offer_acceptance_pct": round(len(accepted) * 100 / len(decided)) if decided else None,
            "positions_filled": job.positions_filled or 0, "positions": job.noOfPositions or 1}
