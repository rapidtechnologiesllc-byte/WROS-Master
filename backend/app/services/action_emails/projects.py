"""Project emails: created, a new project manager, a status change, a milestone added or completed.
The people on a project: its project manager, its creator and the client's team; a milestone adds
its owner (employee login)."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project, ProjectMilestone
from app.models.user import Users
from app.services.action_emails.core import Team, add, after_commit, client_team, employee_login, merge, name_of, send

PROJECTS_PATH = "/projects"


def project_team(db: Session, project: Project) -> Team:
    team: Team = {}
    add(team, project.manager_user_id, "Project Manager")
    add(team, project.created_by, "Created it")
    merge(team, client_team(db, project.client_id))
    return team


def _label(db: Session, project: Project) -> str:
    client = db.get(Client, project.client_id)
    return f"{project.name} ({client.company_name})" if client is not None else project.name


def _send(db: Session, project: Project, team: Team, *, actor: Users, key: str, subject: str, opening: str,
          details=None) -> int:
    return send(db, team, actor_id=actor.UserID, key=key, subject=subject, opening=opening, details=details,
                link_path=PROJECTS_PATH, link_label="Open Projects")


@after_commit("projects")
def notify_project_created(db: Session, project: Project, *, actor: Users) -> int:
    label = _label(db, project)
    return _send(db, project, project_team(db, project), actor=actor, key=f"project-created-{project.id}",
                 subject=f"New project: {label}", opening=f"{name_of(actor)} created the project {label}.",
                 details=[f"Status: {project.status}. Billing: {project.billing_type}, {project.currency}."])


@after_commit("projects")
def notify_project_manager_changed(db: Session, project: Project, *, actor: Users,
                                   previous_manager: Optional[str]) -> int:
    if not project.manager_user_id or project.manager_user_id == previous_manager:
        return 0
    label = _label(db, project)
    return _send(db, project, {project.manager_user_id: ["Project Manager"]}, actor=actor,
                 key=f"project-manager-{project.id}", subject=f"You manage the project {label}",
                 opening=f"{name_of(actor)} made you the project manager of {label}.")


@after_commit("projects")
def notify_project_status(db: Session, project: Project, *, actor: Users) -> int:
    label = _label(db, project)
    return _send(db, project, project_team(db, project), actor=actor,
                 key=f"project-status-{project.id}-{project.status}", subject=f"Project {project.status.lower()}: {label}",
                 opening=f"{name_of(actor)} moved the project {label} to {project.status}.")


def _milestone_team(db: Session, project: Project, milestone: ProjectMilestone) -> Team:
    team = project_team(db, project)
    add(team, employee_login(db, milestone.owner_employee_id), "Milestone Owner")
    return team


@after_commit("projects")
def notify_milestone_created(db: Session, project: Project, milestone: ProjectMilestone, *, actor: Users) -> int:
    label = _label(db, project)
    return _send(db, project, _milestone_team(db, project, milestone), actor=actor,
                 key=f"project-milestone-created-{milestone.id}", subject=f"New milestone on {label}: {milestone.title}",
                 opening=f"{name_of(actor)} added the milestone {milestone.title} to {label}.",
                 details=[f"Due: {milestone.due_date}.", milestone.description])


@after_commit("projects")
def notify_milestone_completed(db: Session, project: Project, milestone: ProjectMilestone, *, actor: Users) -> int:
    label = _label(db, project)
    late = f" ({milestone.delay_days} day(s) late)" if milestone.delay_days else ""
    return _send(db, project, _milestone_team(db, project, milestone), actor=actor,
                 key=f"project-milestone-completed-{milestone.id}",
                 subject=f"Milestone done on {label}: {milestone.title}",
                 opening=f"{name_of(actor)} completed the milestone {milestone.title} on {label}{late}.")
