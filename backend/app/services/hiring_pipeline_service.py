"""The hiring pipeline: one state machine for the CEO's hiring order.

    SCREEN -> L1 -> L2 -> OFFER -> ACCEPTED -> ONBOARDING -> BGV -> BENCH
           -> SUBMITTED -> CLIENT_SELECTED -> CLIENT_ONBOARDING -> ALLOCATED

A stage is never set by hand: evaluate() walks the facts in order (screen decision,
interview verdicts, offer, onboarding documents and checklists, BGV, employee, submission,
client onboarding, allocation) and the candidate is in the furthest stage whose entry facts
hold. The first unmet fact is the blocker, written in plain words. Re-running evaluate()
changes nothing unless a fact changed, so it is safe to call from anywhere, any number of
times: domain events call notify() (queued), and an hourly sweep catches anything missed.

Entering a stage can trigger an action (a task, an email, a conversion). Each action runs at
most once per pipeline and stage (deterministic queue task id), so retries never repeat it.

Candidates who were already employees before the pipeline existed are "grandfathered": the
gates before BENCH are treated as met, so their current work is never blocked.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.background_verification import BackgroundVerification
from app.models.candidate import Candidate, CandidateStatus
from app.models.client_onboarding import ClientOnboarding
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.hiring_pipeline import STAGES, HiringPipeline, HiringPipelineEvent
from app.models.offer_letter import OfferLetter
from app.models.submission import Submission

logger = logging.getLogger(__name__)

EVALUATE_TASK = "hiring_pipeline_evaluate"
STAGE_ACTION_TASK = "hiring_stage_action"
BENCH_TASK = "hiring_convert_to_bench"
ACTIVE_SUBMISSION = ("SUBMITTED", "SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED")
SWEEP_STALE_AFTER = timedelta(hours=1)
SWEEP_BACKFILL_LIMIT = 200


class PipelineGateBlocked(Exception):
    def __init__(self, stage: str, required: str, blockers: List[str]):
        self.stage, self.required, self.blockers = stage, required, blockers
        super().__init__(f"Candidate is at {stage}; {required} requires: " + "; ".join(blockers or ["earlier steps"]))


def stage_index(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else -1


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------

def _latest_offer(db: Session, candidate_id: str, job_id: Optional[str]) -> Optional[OfferLetter]:
    query = db.query(OfferLetter).filter(OfferLetter.candidate_id == candidate_id,
                                         OfferLetter.offer_status != "Cancelled")
    if job_id:
        scoped = query.filter(OfferLetter.job_id == job_id).order_by(OfferLetter.id.desc()).first()
        if scoped is not None:
            return scoped
    return query.order_by(OfferLetter.id.desc()).first()


def onboarding_complete(db: Session, candidate_id: str, offer: OfferLetter) -> Tuple[bool, List[str]]:
    """Every mandatory pre-joining document for this offer is VERIFIED or WAIVED, and every
    checklist assigned since the offer was accepted is completed."""
    from app.models.checklist import CandidateChecklist
    from app.models.preboarding_document import PreboardingDocument

    docs = db.query(PreboardingDocument).filter(PreboardingDocument.candidate_id == candidate_id,
                                                PreboardingDocument.offer_id == offer.id,
                                                PreboardingDocument.status != "CANCELLED").all()
    blockers = []
    if not docs:
        blockers.append("pre-joining document collection has not started")
    outstanding = [d.document_label for d in docs if d.is_mandatory and d.status not in ("VERIFIED", "WAIVED")]
    if outstanding:
        blockers.append("documents not verified: " + ", ".join(sorted(outstanding)))
    since = offer.responded_at or offer.created_at
    checklists = db.query(CandidateChecklist).filter(CandidateChecklist.candidate_id == candidate_id)
    if since is not None:
        checklists = checklists.filter(CandidateChecklist.assigned_at >= since)
    open_lists = [c.template_name or f"checklist {c.id}" for c in checklists.all() if c.status != "completed"]
    if open_lists:
        blockers.append("checklists not completed: " + ", ".join(open_lists))
    return not blockers, blockers


def bgv_status(db: Session, candidate_id: str) -> Optional[str]:
    """Best BGV outcome on record for the candidate (a pass carries over between offers)."""
    rows = db.query(BackgroundVerification).filter(BackgroundVerification.candidate_id == candidate_id).all()
    statuses = {r.status for r in rows}
    for status in ("PASSED", "WAIVED", "FAILED", "IN_PROGRESS", "NOT_STARTED"):
        if status in statuses:
            return status
    return None


def _employee(db: Session, candidate_id: str) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.candidate_id == candidate_id,
                                     Employee.status != "EXITED").order_by(Employee.created_at.desc()).first()


def _submissions(db: Session, candidate_id: str) -> List[Submission]:
    return db.query(Submission).filter(Submission.candidate_id == candidate_id).order_by(Submission.submitted_at).all()


def _screen_required(db: Session, candidate: Optional[Candidate]) -> bool:
    """Recruiter screening is always a step, but candidates Thunder (AI) engaged skip it."""
    if candidate is None:
        return True
    status = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate.candidateID).first()
    return not (candidate.thunder_enabled and status is not None and status.thunder_assigned_at is not None)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _walk(db: Session, pipeline: HiringPipeline) -> Tuple[str, List[str], Dict]:
    """(stage, blockers, refs). stage is REJECTED when a gate failed for good."""
    from app.services.interview_verdict_service import candidate_verdicts

    cid, refs = pipeline.candidate_id, {}
    employee = _employee(db, cid)
    if employee is not None:
        refs["employee_id"] = employee.id
    reached = "SCREEN"

    if not pipeline.grandfathered:
        verdicts = [v for _, v in candidate_verdicts(db, cid)]
        levels = {}
        for v in verdicts:  # latest round per level wins
            levels[v.level] = v.verdict
        # SCREEN -> L1
        if pipeline.screen_decision == "FAIL" or levels.get("SCREEN") == "FAIL":
            return "REJECTED", ["recruiter screen failed"], refs
        screened = (not pipeline.screen_required or pipeline.screen_decision in ("PASS", "SKIP")
                    or levels.get("SCREEN") == "PASS" or "L1" in levels or "L2" in levels)
        if not screened:
            return reached, ["recruiter screen pending"], refs
        # CEO decision 2026-10-10: nobody under 5 years' experience is interviewed, offered or
        # moved on -- checked at every stage, so a rounds-first or corrected record is still caught
        from app.services.submission_service import check_experience_eligibility

        candidate = db.query(Candidate).filter(Candidate.candidateID == cid).first()
        if candidate is not None:
            experience = check_experience_eligibility(candidate)
            if not experience["is_eligible"]:
                return reached, [f"not eligible (5-year rule): {experience['message']}"], refs
        reached = "L1"
        # L1 -> L2 -> OFFER
        for level, nxt in (("L1", "L2"), ("L2", "OFFER")):
            verdict = levels.get(level)
            if verdict == "FAIL":
                return "REJECTED", [f"{level} interview: No Hire"], refs
            if verdict != "PASS":
                label = "technical" if level == "L1" else "management"
                waiting = {None: "not scheduled", "PENDING": "in progress",
                           "NEEDS_DECISION": "mixed feedback, hiring manager to decide"}.get(verdict, verdict)
                return reached, [f"{level} ({label}) interview {waiting}"], refs
            reached = nxt
        # OFFER -> ACCEPTED -> ONBOARDING
        offer = _latest_offer(db, cid, pipeline.job_id)
        if offer is not None:
            refs["offer_letter_id"] = offer.id
        if offer is None:
            return reached, ["no offer created yet"], refs
        if offer.offer_status == "Rejected":
            return "REJECTED", ["candidate declined the offer"], refs
        if offer.offer_status != "Accepted":
            return reached, [f"offer is {offer.offer_status}; waiting for the candidate to accept"], refs
        reached = "ONBOARDING"
        bgv = bgv_status(db, cid)
        if bgv == "FAILED":  # can come back from the vendor before every document is verified
            return "REJECTED", ["background verification failed"], refs
        # ONBOARDING -> BGV
        done, blockers = onboarding_complete(db, cid, offer)
        if not done:
            return reached, blockers, refs
        reached = "BGV"
        # BGV -> BENCH
        if bgv not in ("PASSED", "WAIVED"):
            return reached, [f"background verification {(bgv or 'not started').replace('_', ' ').lower()}"], refs
        if employee is None:
            joining = offer.joining_date
            when = f"on the joining date {joining.isoformat()}" if joining and joining > date.today() else "now"
            return reached, [f"BGV cleared; joins the bench {when}"], refs
    elif employee is None:
        return "BENCH", ["grandfathered candidate has no employee record"], refs

    reached = "BENCH"
    # BENCH -> SUBMITTED -> CLIENT_SELECTED -> CLIENT_ONBOARDING -> ALLOCATED
    submissions = _submissions(db, cid)
    placed = [s for s in submissions if s.status == "PLACED"]
    selected = [s for s in submissions if s.status == "OFFER_EXTENDED"]
    active = [s for s in submissions if s.status in ACTIVE_SUBMISSION]
    if placed:
        sub = placed[-1]
        refs["submission_id"] = sub.id
        allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == employee.id,
                                                         EmployeeAllocation.status == "ACTIVE").first()
        if allocation is not None:
            return "ALLOCATED", [], refs
        return "CLIENT_ONBOARDING", ["placed but no active project allocation yet"], refs
    if selected:
        sub = selected[-1]
        refs["submission_id"] = sub.id
        onboarding = db.query(ClientOnboarding).filter(ClientOnboarding.submission_id == sub.id).first()
        if onboarding is None:
            return "CLIENT_SELECTED", ["client onboarding not started"], refs
        if onboarding.status == "START_CONFIRMED" and onboarding.confirmed_start_date:
            return "CLIENT_ONBOARDING", [f"starts at the client on {onboarding.confirmed_start_date.isoformat()}"], refs
        return "CLIENT_ONBOARDING", ["waiting for the client to confirm a start date"], refs
    if active:
        refs["submission_id"] = active[-1].id
        return "SUBMITTED", [f"client reviewing submission ({active[-1].status.replace('_', ' ').lower()})"], refs
    if pipeline.grandfathered and bgv_status(db, cid) not in ("PASSED", "WAIVED"):
        # CEO decision 2026-10-10: employees from before the pipeline need a BGV too
        return "BENCH", ["background verification required before any client submission"], refs
    return "BENCH", ["on the bench, not yet submitted to a client"], refs


def evaluate(db: Session, pipeline: HiringPipeline, *, trigger: str = "evaluate", ref: Optional[str] = None,
             actor: str = "system") -> HiringPipeline:
    """Re-derive the stage from facts; record a transition event when it changes. Flushes,
    does not commit. Call queue_stage_actions(pipeline) after the caller commits."""
    if pipeline.closed_at is not None:
        return pipeline
    stage, blockers, refs = _walk(db, pipeline)
    for key, value in refs.items():
        setattr(pipeline, key, value)
    pipeline.blockers = blockers
    pipeline.last_evaluated_at = datetime.utcnow()
    if stage != pipeline.stage:
        db.add(HiringPipelineEvent(pipeline_id=pipeline.id, from_stage=pipeline.stage, to_stage=stage,
                                   trigger=trigger, ref=ref, actor=actor, note="; ".join(blockers) or None))
        logger.info(f"[Pipeline] {pipeline.candidate_id}: {pipeline.stage} -> {stage} ({trigger})")
        pipeline.stage, pipeline.stage_entered_at = stage, datetime.utcnow()
    if stage in ("REJECTED", "ALLOCATED"):
        pipeline.closed_at = datetime.utcnow()
    db.flush()
    return pipeline


def get_or_create_pipeline(db: Session, candidate_id: str, job_id: Optional[str] = None, *,
                           created_by: str = "system", reopen: bool = False) -> HiringPipeline:
    """The candidate's open pipeline; else their latest closed one (a rejection stays a
    rejection); a new one only when none exists or reopen=True (rehire after a rejection)."""
    pipeline = db.query(HiringPipeline).filter(HiringPipeline.candidate_id == candidate_id,
                                               HiringPipeline.closed_at.is_(None)).first()
    if pipeline is not None:
        return pipeline
    latest = db.query(HiringPipeline).filter(HiringPipeline.candidate_id == candidate_id) \
        .order_by(HiringPipeline.id.desc()).first()
    if latest is not None and not (reopen and latest.stage in ("REJECTED", "WITHDRAWN")):
        return latest
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise ValueError(f"Candidate {candidate_id} not found")
    employee = _employee(db, candidate_id)
    pipeline = HiringPipeline(candidate_id=candidate_id, job_id=job_id or candidate.job_id,
                              tenant_id=candidate.tenant_id, stage="SCREEN",
                              screen_required=_screen_required(db, candidate),
                              grandfathered=employee is not None, backfilled=created_by == "backfill")
    db.add(pipeline)
    db.flush()
    db.add(HiringPipelineEvent(pipeline_id=pipeline.id, from_stage=None, to_stage="SCREEN", trigger="created",
                               actor=created_by, note="grandfathered: already an employee" if employee else None))
    if employee is not None:  # they still need a BGV before a client: give HR a record to work
        from app.services.bgv_service import ensure_bgv

        ensure_bgv(db, candidate_id, None, candidate.tenant_id)
    return evaluate(db, pipeline, trigger="created", actor=created_by)


def record_screen_decision(db: Session, candidate_id: str, decision: str, user_id: str,
                           notes: Optional[str] = None) -> HiringPipeline:
    if decision not in ("PASS", "SKIP", "FAIL"):
        raise ValueError("Screen decision must be PASS, SKIP or FAIL.")
    pipeline = get_or_create_pipeline(db, candidate_id)
    pipeline.screen_decision, pipeline.screen_decided_by = decision, user_id
    return evaluate(db, pipeline, trigger="screen", ref=decision, actor=user_id)


def assert_gate(db: Session, candidate_id: str, required_stage: str) -> HiringPipeline:
    """Raise PipelineGateBlocked unless the candidate has reached required_stage."""
    pipeline = evaluate(db, get_or_create_pipeline(db, candidate_id), trigger="gate", ref=required_stage)
    if pipeline.stage in ("REJECTED", "WITHDRAWN") or stage_index(pipeline.stage) < stage_index(required_stage):
        raise PipelineGateBlocked(pipeline.stage, required_stage, pipeline.blockers or [])
    return pipeline


def snapshot(db: Session, pipeline: HiringPipeline) -> Dict:
    events = db.query(HiringPipelineEvent).filter(HiringPipelineEvent.pipeline_id == pipeline.id) \
        .order_by(HiringPipelineEvent.id).all()
    return {
        "pipeline_id": pipeline.id, "candidate_id": pipeline.candidate_id, "job_id": pipeline.job_id,
        "stage": pipeline.stage, "stage_entered_at": pipeline.stage_entered_at, "blockers": pipeline.blockers or [],
        "screen_required": pipeline.screen_required, "screen_decision": pipeline.screen_decision,
        "grandfathered": pipeline.grandfathered, "offer_letter_id": pipeline.offer_letter_id,
        "employee_id": pipeline.employee_id, "submission_id": pipeline.submission_id,
        "closed_at": pipeline.closed_at,
        "events": [{"from_stage": e.from_stage, "to_stage": e.to_stage, "trigger": e.trigger, "ref": e.ref,
                    "actor": e.actor, "note": e.note, "at": e.created_at} for e in events],
    }


# ---------------------------------------------------------------------------
# Queue: notify after a fact changed; run each stage's action once
# ---------------------------------------------------------------------------

def notify(candidate_id: str, trigger: str, ref, tenant_id: Optional[int] = None) -> bool:
    """Call after commit. Queues a re-evaluation; the same (trigger, ref) is queued once."""
    from app.services.thunder_mail.cadence_service import enqueue_once

    return enqueue_once(EVALUATE_TASK, f"hp:{candidate_id}:{trigger}:{ref}",
                        {"candidate_id": candidate_id, "trigger": trigger, "ref": str(ref)}, tenant_id)


def queue_stage_actions(pipeline: HiringPipeline, db: Optional[Session] = None) -> int:
    """Call after commit. Queues the entry action of the current stage (once per stage), and
    the bench conversion once BGV is cleared and the joining date has come."""
    from app.services.thunder_mail.cadence_service import enqueue_once

    queued = 0
    if pipeline.stage in STAGE_ACTIONS:
        queued += int(enqueue_once(STAGE_ACTION_TASK, f"hp-act:{pipeline.id}:{pipeline.stage}",
                                   {"pipeline_id": pipeline.id, "stage": pipeline.stage}, pipeline.tenant_id))
    if db is not None and ready_for_bench(db, pipeline)[0]:
        queued += int(_queue_bench(pipeline))
    return queued


# ---------------------------------------------------------------------------
# BENCH: BGV cleared + joining date -> employee and system login
# ---------------------------------------------------------------------------

def _queue_bench(pipeline: HiringPipeline) -> bool:
    """Once per pipeline per day: a conversion blocked today (e.g. no business unit) is
    retried by tomorrow's sweep after someone fixes it."""
    from app.services.thunder_mail.cadence_service import enqueue_once

    return enqueue_once(BENCH_TASK, f"hp-bench:{pipeline.id}:{date.today().isoformat()}",
                        {"pipeline_id": pipeline.id}, pipeline.tenant_id)


def _bgv_cleared(db: Session, pipeline: HiringPipeline) -> bool:
    return bgv_status(db, pipeline.candidate_id) in ("PASSED", "WAIVED")


def ready_for_bench(db: Session, pipeline: HiringPipeline, today: Optional[date] = None) -> Tuple[bool, str]:
    if pipeline.closed_at is not None or pipeline.stage != "BGV":
        return False, f"pipeline is at {pipeline.stage}"
    if not _bgv_cleared(db, pipeline):
        return False, "background verification not cleared"
    if _employee(db, pipeline.candidate_id) is not None:
        return False, "already an employee"
    offer = db.query(OfferLetter).filter(OfferLetter.id == pipeline.offer_letter_id).first()
    if offer is None or offer.joining_date is None:
        return False, "accepted offer has no joining date"
    if offer.joining_date > (today or date.today()):
        return False, f"joining date {offer.joining_date.isoformat()} not reached"
    return True, "ready"


def assert_cleared_for_employment(db: Session, candidate_id: str) -> HiringPipeline:
    """Manual conversion: allowed only once BGV is cleared (any joining date)."""
    pipeline = evaluate(db, get_or_create_pipeline(db, candidate_id), trigger="gate", ref="convert")
    if pipeline.grandfathered or pipeline.stage == "BGV" and _bgv_cleared(db, pipeline):
        return pipeline
    raise PipelineGateBlocked(pipeline.stage, "employment", pipeline.blockers or [])


def convert_to_bench(db: Session, pipeline_id: int) -> str:
    """Queued on the joining date: the candidate becomes a BENCH employee with a system login
    (Employee role; a set-password link is emailed). Commits."""
    from app.services.account_activation_service import queue_account_email
    from app.services.employee_conversion_service import EmployeeConversionService

    pipeline = db.query(HiringPipeline).filter(HiringPipeline.id == pipeline_id).with_for_update().first()
    if pipeline is None:
        raise ValueError(f"Hiring pipeline {pipeline_id} not found")
    ready, reason = ready_for_bench(db, pipeline)
    if not ready:
        return f"skipped: {reason}"
    candidate = db.query(Candidate).filter(Candidate.candidateID == pipeline.candidate_id).first()
    offer = db.query(OfferLetter).filter(OfferLetter.id == pipeline.offer_letter_id).first()
    try:
        user, employee = EmployeeConversionService.convert_candidate_to_employee(
            db, candidate, joining_date=offer.joining_date, tenant_id=candidate.tenant_id, changed_by="system",
            job_title=offer.position)
    except ValueError as exc:  # e.g. no business unit on the job or candidate
        db.rollback()
        pipeline = db.query(HiringPipeline).filter(HiringPipeline.id == pipeline_id).first()
        pipeline.blockers = [f"cannot create the employee: {exc}"]
        db.commit()
        return f"blocked: {exc}"
    evaluate(db, pipeline, trigger="bench", ref=employee.id)
    db.commit()
    queue_account_email(user, "ACTIVATE")
    logger.info(f"[Pipeline] {pipeline.candidate_id} joined the bench as {employee.id}")
    return f"employee {employee.id} created on the bench; login email queued"


def _recruiter_task(db: Session, pipeline: HiringPipeline, title: str, description: str, category: str) -> None:
    from app.services.task_service import create_task

    candidate = db.query(Candidate).filter(Candidate.candidateID == pipeline.candidate_id).first()
    name = " ".join(p for p in [getattr(candidate, "candidateFirstName", None),
                                getattr(candidate, "candidateLastName", None)] if p) or pipeline.candidate_id
    task = create_task(db, title=title.format(name=name), description=description.format(name=name),
                       priority="HIGH", tenant_id=pipeline.tenant_id, category=category,
                       assigned_to_user_id=getattr(candidate, "assigned_recruiter_id", None),
                       visibility_scope="ORG_WIDE" if not getattr(candidate, "assigned_recruiter_id", None)
                       else "ASSIGNEE_MANAGER_DEPARTMENT")
    task.candidate_id = pipeline.candidate_id
    db.add(task)


def _action_screen(db: Session, pipeline: HiringPipeline) -> str:
    if not pipeline.screen_required:
        return "skipped: Thunder-engaged candidate"
    _recruiter_task(db, pipeline, "Screen candidate: {name}",
                    "Screen {name}, then record PASS, SKIP or FAIL in the hiring pipeline. Scheduling the L1 "
                    "(technical) interview also counts as passing the screen.", "HIRING_SCREEN")
    return "recruiter screen task created"


def _action_schedule(level: str):
    def action(db: Session, pipeline: HiringPipeline) -> str:
        from app.services.interview_verdict_service import candidate_verdicts

        # Fact-based: a round at this level already exists for this job (or with no job set),
        # scheduled from the screens or by Flash -> nobody needs to be asked to schedule it
        if any(verdict.level == level and panel.job_id in (pipeline.job_id, None)
               for panel, verdict in candidate_verdicts(db, pipeline.candidate_id)):
            return f"{level} round already exists: no scheduling task"
        label = "technical" if level == "L1" else "management"
        _recruiter_task(db, pipeline, f"Schedule {level} ({label}) interview: {{name}}",
                        f"{{name}} is ready for the {level} ({label}) round. Create the interview panel with "
                        f"level {level}; the verdict from interviewer feedback moves them on automatically.",
                        "INTERVIEW_SCHEDULING")
        return f"{level} scheduling task created"
    return action


def _action_offer(db: Session, pipeline: HiringPipeline) -> str:
    _recruiter_task(db, pipeline, "Create offer: {name}",
                    "{name} passed L1 and L2. Create, approve and release the offer letter.", "OFFER")
    return "offer task created"


def _action_onboarding(db: Session, pipeline: HiringPipeline) -> str:
    from app.services.hiring_onboarding_service import start_onboarding

    return start_onboarding(db, pipeline)


def _action_bgv(db: Session, pipeline: HiringPipeline) -> str:
    """Documents are verified: start BGV (consent is one of the documents) and hand it to HR,
    who runs it with the vendor and records the verdict (or the vendor's webhook does)."""
    from app.services.bgv_service import ensure_bgv, start_if_consented
    from app.services.task_service import create_task

    offer = db.query(OfferLetter).filter(OfferLetter.id == pipeline.offer_letter_id).first()
    bgv = ensure_bgv(db, pipeline.candidate_id, pipeline.offer_letter_id, pipeline.tenant_id)
    start_if_consented(db, bgv)
    if bgv.status in ("PASSED", "WAIVED"):
        db.commit()
        return f"BGV already {bgv.status}"
    task = create_task(db, title=f"Run background verification: {pipeline.candidate_id}",
                       description=(f"Pre-joining documents are verified. Run background verification "
                                    f"(BGV #{bgv.id}) and record PASSED or FAILED in BGV."),
                       priority="HIGH", tenant_id=pipeline.tenant_id, category="BGV",
                       assigned_to_user_id=getattr(offer, "created_by", None),
                       visibility_scope="ORG_WIDE" if not getattr(offer, "created_by", None) else "ASSIGNEE_MANAGER_DEPARTMENT")
    task.candidate_id = pipeline.candidate_id
    db.add(task)
    return f"BGV #{bgv.id} {bgv.status.lower()}; HR task created"


STAGE_ACTIONS: Dict[str, Callable[[Session, HiringPipeline], str]] = {
    "SCREEN": _action_screen,
    "L1": _action_schedule("L1"),
    "L2": _action_schedule("L2"),
    "OFFER": _action_offer,
    "ONBOARDING": _action_onboarding,
    "BGV": _action_bgv,
}


def run_stage_action(db: Session, pipeline_id: int, stage: str) -> str:
    """Runs the action only if the pipeline is still in that stage; commits."""
    pipeline = db.query(HiringPipeline).filter(HiringPipeline.id == pipeline_id).with_for_update().first()
    if pipeline is None:
        raise ValueError(f"Hiring pipeline {pipeline_id} not found")
    if pipeline.stage != stage:
        return f"stale: pipeline is now {pipeline.stage}"
    outcome = STAGE_ACTIONS[stage](db, pipeline)
    db.add(HiringPipelineEvent(pipeline_id=pipeline.id, from_stage=stage, to_stage=stage, trigger="action",
                               actor="system", note=outcome))
    db.commit()
    return outcome


def evaluate_and_act(db: Session, candidate_id: str, trigger: str, ref: Optional[str] = None,
                     actor: str = "system") -> HiringPipeline:
    """Evaluate, commit, then queue the stage's entry action. A new interview round for a
    rejected candidate (it passed the rehire guard) opens a new pipeline."""
    pipeline = get_or_create_pipeline(db, candidate_id, reopen=trigger == "panel_created")
    evaluate(db, pipeline, trigger=trigger, ref=ref, actor=actor)
    db.commit()
    queue_stage_actions(pipeline, db)
    return pipeline


# ---------------------------------------------------------------------------
# Scheduled sweep
# ---------------------------------------------------------------------------

def run_pipeline_sweep(db: Session) -> Dict:
    """Hourly: re-evaluate open pipelines not evaluated in the last hour (time-based facts,
    e.g. a joining date arriving), and backfill pipelines for candidates in active hiring."""
    cutoff = datetime.utcnow() - SWEEP_STALE_AFTER
    stale = db.query(HiringPipeline).filter(HiringPipeline.closed_at.is_(None)).filter(
        (HiringPipeline.last_evaluated_at.is_(None)) | (HiringPipeline.last_evaluated_at < cutoff)).all()
    changed = []
    for pipeline in stale:
        before = pipeline.stage
        evaluate(db, pipeline, trigger="sweep")
        if pipeline.stage != before:
            changed.append(pipeline)
    db.commit()
    for pipeline in changed:  # only real progress triggers an action; backfill just records state
        queue_stage_actions(pipeline)
    for pipeline in stale:  # joining dates arrive without any event
        if ready_for_bench(db, pipeline)[0]:
            _queue_bench(pipeline)

    open_ids = {r[0] for r in db.query(HiringPipeline.candidate_id).filter(HiringPipeline.closed_at.is_(None)).all()}
    candidates = [r[0] for r in db.query(CandidateStatus.candidateID).filter(
        CandidateStatus.piplineStatus.notin_(["Rejected", "Withdrawn", "Archived"])).all() if r[0] not in open_ids]
    # employees from before the pipeline: their pipeline (and BGV record) up front, so HR can
    # clear BGV before anyone tries to submit them to a client
    candidates = [r[0] for r in db.query(Employee.candidate_id).filter(
        Employee.candidate_id.isnot(None), Employee.status != "EXITED").all() if r[0] not in open_ids] + candidates
    candidates = list(dict.fromkeys(candidates))
    backfilled = 0
    for candidate_id in candidates[:SWEEP_BACKFILL_LIMIT]:
        if db.query(HiringPipeline.id).filter(HiringPipeline.candidate_id == candidate_id).first():
            continue  # a closed pipeline exists: rejected/allocated candidates aren't reopened by the sweep
        try:
            get_or_create_pipeline(db, candidate_id, created_by="backfill")
            db.commit()
            backfilled += 1
        except Exception as exc:
            db.rollback()
            logger.error(f"[Pipeline] backfill failed for {candidate_id}: {exc}", exc_info=True)
    result = {"re_evaluated": len(stale), "stage_changes": len(changed), "backfilled": backfilled}
    logger.info(f"[Pipeline] sweep {result}")
    return result
