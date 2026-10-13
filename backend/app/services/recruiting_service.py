"""Start recruiting for a job the moment it goes live, however it went live (created
active, approved after pending, created in a Flash chat):

start_recruiting(job, reason)  -> queues
    flash_recruiter            nudges candidates watching for a matching opportunity, then
                               re-runs every 4 hours while the job is active
    source_candidates_for_job  ranks the active candidate pool (location + skill recency)
                               and reports the top matches (candidate_sourcing_complete)
handle_sourcing_complete       -> the report becomes a task for the job's recruiter: the top
                               matches to screen, or "no viable candidates" to widen the search
Queue ids are unique per run, so a re-run never collides with an earlier one.
"""
import logging
import uuid
from typing import Any, Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def start_recruiting(job, reason: str) -> None:
    """Call after the job is committed."""
    from app.services.message_queue_service import MessageQueueService

    run = uuid.uuid4().hex[:12]
    common = {"job_id": job.jobID, "job_title": job.jobTitle, "job_skills": job.jobSkills or "",
              "no_of_positions": getattr(job, "noOfPositions", None), "hiring_manager_id": job.hiringManagerID,
              "business_unit_id": getattr(job, "business_unit_id", None), "reason": reason}
    MessageQueueService.enqueue(task_name="flash_recruiter", task_id=f"recruit:{job.jobID}:{run}", data=common)
    MessageQueueService.enqueue(task_name="source_candidates_for_job", task_id=f"source:{job.jobID}:{run}",
                                data={"job_id": job.jobID, "reason": reason})
    logger.info(f"[Recruiting] started for job {job.jobID} ({reason})")


def handle_sourcing_complete(message: Any, db: Session) -> Dict[str, Any]:
    from app.models.candidate import Candidate
    from app.models.user import Jobs
    from app.services.task_service import create_task

    report = message.payload or {}
    job = db.query(Jobs).filter(Jobs.jobID == report.get("job_id")).first()
    if job is None:
        raise ValueError(f"Message {message.id}: job {report.get('job_id')!r} not found")
    viable = [m for m in report.get("top_matches") or [] if m.get("can_proceed")]
    names = {c.candidateID: " ".join(p for p in [c.candidateFirstName, c.candidateLastName] if p) or c.candidateID
             for c in db.query(Candidate).filter(Candidate.candidateID.in_([m["candidate_id"] for m in viable])).all()}
    if viable:
        title = f"Screen top matches for {job.jobTitle}"
        lines = [f"- {names.get(m['candidate_id'], m['candidate_id'])}: {m.get('recency_score', 0)}% skill recency"
                 for m in viable]
        description = (f"Flash ranked {report.get('candidates_available', 0)} candidates in the area for "
                       f"{job.jobTitle} ({job.jobID}). Best matches:\n" + "\n".join(lines))
    else:
        title = f"No viable candidates yet for {job.jobTitle}"
        description = (f"{report.get('formation_feedback', '')} Searched {report.get('candidates_available', 0)} "
                       f"candidates in {job.jobLocation or 'the job location'}. Widen the location or skills, or "
                       f"source new candidates.")
    task = create_task(db, title=title, description=description, priority="HIGH" if not viable else "MEDIUM",
                       tenant_id=getattr(job, "tenant_id", None), category="RECRUITING",
                       assigned_to_user_id=job.recuriterID or job.hiringManagerID,
                       visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT")
    return {"status": "success", "job_id": job.jobID, "task_id": task.id, "viable_matches": len(viable)}
