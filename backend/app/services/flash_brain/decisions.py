"""Decisions waiting for a person (flash spec B): Flash surfaces them in the bubble ("N decisions
are waiting for you") as chips. A chip whose kind is a Flash workflow opens it in the bubble; any
other chip opens its link. Flash never takes these decisions itself.

Registry: PROVIDERS, each (db, user) -> [Decision]. A provider is added only when the service
function that records the decision exists.
"""
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import Users


@dataclass(frozen=True)
class Decision:
    kind: str
    ref: str
    text: str
    link: Optional[str] = None

    def as_dict(self) -> Dict:
        from app.services.flash_brain.workflows import WORKFLOWS

        return {**asdict(self), "workflow": self.kind in WORKFLOWS}


def core_cert_pending(db: Session, user: Users) -> List[Decision]:
    """PENDING Core certification requests this user may decide (BU Head or a leader of the BU)."""
    from app.core import authority
    from app.services import core_certification_service as service

    if not authority.has_permission(db, user, "workforce-overview.view"):
        return []
    rows = (service.visible_requests(db, user)
            .filter(service.CoreCertificationRequest.status == "PENDING")
            .order_by(service.CoreCertificationRequest.created_at).all())
    return [Decision(service.FLASH_WORKFLOW, request.id,
                     f"Approve Core certification: {employee.first_name} {employee.last_name}".strip(),
                     service.decision_link(request.id))
            for request, employee in rows if service.may_decide(db, request, user)]


def interview_needs_decision(db: Session, user: Users) -> List[Decision]:
    """Interview rounds whose feedback is mixed (NEEDS_DECISION) on jobs this user is the hiring
    manager of, within the interviews they may see."""
    from app.core import authority
    from app.models.candidate import Candidate
    from app.models.interview_verdict import InterviewRoundVerdict
    from app.models.user import InterviewPanel, Jobs
    from app.services.interview_scheduling_service import candidate_display_name, panel_scope

    if not authority.has_permission(db, user, "interviews.view"):
        return []
    rows = (db.query(InterviewRoundVerdict, InterviewPanel, Jobs, Candidate)
            .join(InterviewPanel, InterviewPanel.id == InterviewRoundVerdict.panel_id)
            .join(Jobs, Jobs.jobID == InterviewPanel.job_id)
            .join(Candidate, Candidate.candidateID == InterviewPanel.candidate_id)
            .filter(InterviewRoundVerdict.verdict == "NEEDS_DECISION", Jobs.hiringManagerID == user.UserID,
                    Jobs.tenant_id == user.tenant_id, panel_scope(db, user))
            .order_by(InterviewRoundVerdict.updated_at).all())
    return [Decision("interview_verdict", str(panel.id),
                     f"{candidate_display_name(candidate)}: {verdict.level} round for {job.jobTitle} -- feedback is "
                     "mixed, your decision is needed",
                     f"/candidates/{candidate.candidateID}?tab=interview")
            for verdict, panel, job, candidate in rows]


PROVIDERS = (core_cert_pending, interview_needs_decision)


def pending_decisions(db: Session, user: Users) -> List[Decision]:
    decisions: List[Decision] = []
    for provider in PROVIDERS:
        decisions.extend(provider(db, user))
    return decisions
