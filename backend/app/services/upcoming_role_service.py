"""Roles a client is about to need, raised on an opportunity before the contract is signed (CEO
2026-11-02: "Recruitment should start working on it as it takes 60-90 days to hire ... it has to
open job on its own").

An upcoming role is a real job (a jobs row through demand_service.create_demand, the one creation
path): confirmation_status POTENTIAL and source_type OPPORTUNITY say it is not sold yet, demand
status OPEN lets recruiting start now (recruiting_service.start_recruiting, called by the endpoint
after the commit). The UpcomingRole row beside it carries how candidates hear the client described
(never its name), the expected start and likelihood, and whether Thunder emails the matches itself
(role_outreach_service). When the contract is signed the same job simply goes on being staffed.
"""
import json
import logging
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_update import UpcomingRole
from app.models.demand import EMPLOYMENT_TYPES, WORK_LOCATIONS
from app.models.opportunity import Opportunity
from app.models.user import Users

logger = logging.getLogger(__name__)


class UpcomingRoleError(ValueError):
    pass


def _skills(raw) -> List[str]:
    items = raw if isinstance(raw, list) else str(raw or "").split(",")
    seen, skills = set(), []
    for item in items:
        name = str(item).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            skills.append(name)
    return skills


def create_upcoming_role(db: Session, opportunity: Opportunity, *, actor: Users, title: str, description: str,
                         skills, client_description: str, positions: int = 1, location: str = "",
                         work_location: str = "REMOTE", employment_type: str = "FULLTIME",
                         min_experience_years: Optional[float] = None, target_start: Optional[date] = None,
                         likelihood_pct: Optional[int] = None, auto_outreach: bool = True,
                         client_update_id: Optional[int] = None):
    """Open the job and its UpcomingRole row. Does not commit; the caller commits, then starts
    recruiting (recruiting_service.start_recruiting) on the returned job."""
    from app.services.bu_leadership import head_for_client
    from app.services.demand_service import create_demand

    title, description = (title or "").strip(), (description or "").strip()
    client_description = (client_description or "").strip()
    skill_list = _skills(skills)
    if not title:
        raise UpcomingRoleError("Name the role, e.g. BillingCenter Developer.")
    if not description:
        raise UpcomingRoleError("Describe the work: candidates are matched and written to from it.")
    if not skill_list:
        raise UpcomingRoleError("List the skills the role needs.")
    if not client_description:
        raise UpcomingRoleError("Say how candidates may hear the client described, e.g. 'a mid-size P&C "
                                "carrier'. The client's name is never shared.")
    if positions < 1:
        raise UpcomingRoleError("At least one position.")
    work_location = (work_location or "REMOTE").upper()
    if work_location not in WORK_LOCATIONS:
        raise UpcomingRoleError(f"Work location must be one of {', '.join(WORK_LOCATIONS)}.")
    if work_location != "REMOTE" and not (location or "").strip():
        raise UpcomingRoleError("An onsite or hybrid role needs its location.")
    employment_type = (employment_type or "FULLTIME").upper()
    if employment_type not in EMPLOYMENT_TYPES:
        raise UpcomingRoleError(f"Employment type must be one of {', '.join(EMPLOYMENT_TYPES)}.")
    if likelihood_pct is not None and not 0 <= likelihood_pct <= 100:
        raise UpcomingRoleError("Likelihood is a percentage from 0 to 100.")
    if min_experience_years is not None and min_experience_years < 0:
        raise UpcomingRoleError("Experience cannot be negative.")

    client = db.query(Client).filter(Client.id == opportunity.client_id).first()
    if client is None or client.business_unit_id is None:
        raise UpcomingRoleError("The client has no business unit: assign one so the role has an owner.")
    for word in filter(None, (client.company_name, client.company_short_name)):
        if word.lower() in client_description.lower():
            raise UpcomingRoleError("The description candidates see must not name the client.")
    hiring_manager = head_for_client(db, client.business_unit_id, client.id) or opportunity.client_owner_id

    job = create_demand(
        db, tenant_id=actor.tenant_id, client_id=client.id, opportunity_id=opportunity.id,
        job_title=title, job_description=description, jobSkills=", ".join(skill_list),
        required_skills=json.dumps(skill_list), required_skills_canonical=[{"name": s} for s in skill_list],
        jobExperience=f"{min_experience_years:g}+ years" if min_experience_years is not None else "Not specified",
        min_experience_years=min_experience_years, job_location=(location or "").strip() or "Remote",
        work_location=work_location, employment_type=employment_type, headcount=positions,
        required_start_date=target_start, status="OPEN", confirmation_status="POTENTIAL",
        source_type="OPPORTUNITY", business_unit_id=client.business_unit_id, hiringManagerID=hiring_manager,
        created_by=actor.UserID,
    )
    db.flush()
    db.add(UpcomingRole(
        job_id=job.jobID, tenant_id=actor.tenant_id, opportunity_id=opportunity.id,
        client_update_id=client_update_id, client_description=client_description, target_start=target_start,
        likelihood_pct=likelihood_pct, auto_outreach=auto_outreach, created_by=actor.UserID,
    ))
    logger.info(f"[UpcomingRole] {opportunity.id}: opened job {job.jobID} {title!r} x{positions} "
                f"(auto outreach {'on' if auto_outreach else 'off'})")
    return job
