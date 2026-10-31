"""Emails to the internal team of a client when work on it starts (CEO 2026-10-30: "i added a client,
i added an opportunity nothing triggered email to the internal team who is involved on that").

The team of a client is its Client Owner, its account manager and the head of its business unit in
its contracting company (bu_leadership.head_for_client). An opportunity adds its own Client Owner
and its Account Manager (Opportunity.owner_employee_id, the employee's login). Each person gets one email listing every role
they hold; the person who did it is not emailed about their own action.

Sent through the staff mail path (staff_mail_service.queue_staff_email) after the caller's commit,
with a deterministic key per record and person, so a retry never mails twice. A failure to queue
never undoes the client or opportunity: it is logged with the stack and the record stays."""
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.user import Users

logger = logging.getLogger(__name__)

CLIENT_MANAGEMENT_PATH = "/client-management"
OPPORTUNITY_PIPELINE_PATH = "/opportunity-pipeline"


def _add(team: Dict[str, List[str]], user_id: Optional[str], role: str) -> None:
    if user_id and role not in team.setdefault(user_id, []):
        team[user_id].append(role)


def client_team(db: Session, client: Client) -> Dict[str, List[str]]:
    """user_id -> the roles that person holds on the client, in a stable order."""
    from app.services.bu_leadership import head_for_client

    team: Dict[str, List[str]] = {}
    _add(team, client.client_owner_user_id, "Client Owner")
    _add(team, client.account_manager_user_id, "Account Manager")
    if client.business_unit_id is not None:
        _add(team, head_for_client(db, client.business_unit_id, client.id), "BU Head")
    return team


def _queue_team(db: Session, team: Dict[str, List[str]], *, actor_id: Optional[str], key: str,
                subject: str, opening: str, details: List[str], link_path: str, link_label: str) -> int:
    """Queue one email per team member except the actor; returns how many were queued."""
    from app.services.staff_mail_service import queue_staff_email

    queued = 0
    for user_id, roles in team.items():
        if user_id == actor_id:
            continue
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is None or user.terminated_at is not None:
            logger.warning(f"[ClientTeamEmail] {key}: team member {user_id} is unknown or terminated; not emailed")
            continue
        try:
            if queue_staff_email(
                user, key=f"{key}-{user_id}", subject=subject[:250], link_path=link_path, link_label=link_label,
                paragraphs=[opening, f"You are on it as: {', '.join(roles)}.", *details],
            ):
                queued += 1
        except Exception as exc:
            logger.error(f"[ClientTeamEmail] {key}: email to {user_id} not queued: {exc}", exc_info=True)
    logger.info(f"[ClientTeamEmail] {key}: {queued} email(s) queued for {len(team)} team member(s)")
    return queued


def _name(db: Session, user_id: Optional[str]) -> Optional[str]:
    user = db.query(Users).filter(Users.UserID == user_id).first() if user_id else None
    return (user.UserName or user.UserEmail) if user else None


def _team_lines(db: Session, team: Dict[str, List[str]]) -> List[str]:
    return [f"{', '.join(roles)}: {_name(db, user_id) or user_id}" for user_id, roles in team.items()]


def notify_client_created(db: Session, client: Client, *, actor: Users) -> int:
    """Queue the new-client email for a committed client. Never raises (the client already exists)."""
    try:
        team = client_team(db, client)
        by = actor.UserName or actor.UserEmail
        return _queue_team(
            db, team, actor_id=actor.UserID, key=f"client-created-{client.id}",
            subject=f"New client: {client.company_name}",
            opening=f"{by} added the client {client.company_name}.",
            details=["Team: " + "; ".join(_team_lines(db, team)) + "."],
            link_path=CLIENT_MANAGEMENT_PATH, link_label="Open Client Management",
        )
    except Exception as exc:
        logger.error(f"[ClientTeamEmail] new-client email for {client.id} not queued: {exc}", exc_info=True)
        return 0


def notify_client_owner_assigned(db: Session, client: Client, *, actor: Users) -> int:
    """Queue the email to a client's newly assigned Client Owner. Never raises."""
    try:
        team = {client.client_owner_user_id: ["Client Owner"]} if client.client_owner_user_id else {}
        return _queue_team(
            db, team, actor_id=actor.UserID,
            key=f"client-owner-{client.id}-{client.client_owner_user_id}",
            subject=f"You are now the Client Owner of {client.company_name}",
            opening=f"{actor.UserName or actor.UserEmail} made you the Client Owner of {client.company_name}.",
            details=[], link_path=CLIENT_MANAGEMENT_PATH, link_label="Open Client Management",
        )
    except Exception as exc:
        logger.error(f"[ClientTeamEmail] client-owner email for {client.id} not queued: {exc}", exc_info=True)
        return 0


def notify_opportunity_created(db: Session, opportunity, *, actor: Users) -> int:
    """Queue the new-opportunity email for a committed opportunity to the client's team plus the
    opportunity's own Client Owner and Account Manager. Never raises (the opportunity exists)."""
    from app.models.employee import Employee
    from app.models.opportunity import OpportunityProfile

    try:
        client = db.query(Client).filter(Client.id == opportunity.client_id).first()
        if client is None:
            raise ValueError(f"Opportunity {opportunity.id} has unknown client {opportunity.client_id}")
        team: Dict[str, List[str]] = {}
        _add(team, opportunity.client_owner_id, "Client Owner (opportunity)")
        owner = db.query(Employee).filter(Employee.id == opportunity.owner_employee_id).first() \
            if opportunity.owner_employee_id else None
        if owner is not None:
            _add(team, owner.wros_user_id, "Account Manager (opportunity)")
        for user_id, roles in client_team(db, client).items():
            for role in roles:
                _add(team, user_id, role)
        profile = db.query(OpportunityProfile).filter(OpportunityProfile.opportunity_id == opportunity.id).first()
        value = f"${opportunity.revenue_value_usd_cents / 100:,.0f}" if opportunity.revenue_value_usd_cents else None
        facts = [f"Stage: {opportunity.stage}"]
        if profile is not None and profile.service:
            facts.append(f"Service: {profile.service}")
        if value:
            facts.append(f"Value: {value}")
        if opportunity.expected_close_date:
            facts.append(f"Expected close: {opportunity.expected_close_date:%Y-%m-%d}")
        by = actor.UserName or actor.UserEmail
        return _queue_team(
            db, team, actor_id=actor.UserID, key=f"opportunity-created-{opportunity.id}",
            subject=f"New opportunity: {client.company_name}",
            opening=f"{by} added an opportunity for {client.company_name}.",
            details=[". ".join(facts) + ".", "Team: " + "; ".join(_team_lines(db, team)) + "."],
            link_path=OPPORTUNITY_PIPELINE_PATH, link_label="Open the pipeline",
        )
    except Exception as exc:
        logger.error(f"[ClientTeamEmail] new-opportunity email for {opportunity.id} not queued: {exc}",
                     exc_info=True)
        return 0
