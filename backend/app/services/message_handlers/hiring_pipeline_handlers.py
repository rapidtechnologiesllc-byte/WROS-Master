"""Message Handlers: hiring_pipeline_evaluate, hiring_stage_action, hiring_convert_to_bench

hiring_pipeline_evaluate  {candidate_id, trigger, ref}
    A fact about the candidate changed (verdict, offer answer, document, BGV, submission...):
    re-derive the pipeline stage, commit, then queue the new stage's entry action.
hiring_convert_to_bench   {pipeline_id}
    BGV cleared and the joining date has come: create the employee (BENCH) and their
    system login, and email the set-password link. Skips if no longer ready.
hiring_stage_action       {pipeline_id, stage}
    Run the stage's entry action (task, email, conversion) once; skipped when the pipeline
    has moved on since it was queued.

All are idempotent: evaluation is derived from facts and the action's queue task id is
deterministic (hp-act:{pipeline}:{stage}). Compensation: none needed; a failed run is
retried by the queue and re-reads the facts.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 40


class HiringPipelineEvaluateHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        from app.services.hiring_pipeline_service import evaluate_and_act

        payload = message.payload or {}
        candidate_id = payload.get("candidate_id")
        if not candidate_id:
            raise ValueError(f"Message {message.id} missing candidate_id")
        pipeline = evaluate_and_act(db, candidate_id, payload.get("trigger") or "event", payload.get("ref"))
        return {"status": "evaluated", "candidate_id": candidate_id, "stage": pipeline.stage,
                "blockers": pipeline.blockers or []}


class HiringStageActionHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        from app.services.hiring_pipeline_service import STAGE_ACTIONS, run_stage_action

        payload = message.payload or {}
        pipeline_id, stage = payload.get("pipeline_id"), payload.get("stage")
        if not pipeline_id or stage not in STAGE_ACTIONS:
            raise ValueError(f"Message {message.id} has no pipeline_id or an unknown stage {stage!r}")
        outcome = run_stage_action(db, int(pipeline_id), stage)
        return {"status": "done", "pipeline_id": pipeline_id, "stage": stage, "outcome": outcome}


class HiringConvertToBenchHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        from app.services.hiring_pipeline_service import convert_to_bench

        pipeline_id = (message.payload or {}).get("pipeline_id")
        if not pipeline_id:
            raise ValueError(f"Message {message.id} missing pipeline_id")
        return {"status": "done", "pipeline_id": pipeline_id, "outcome": convert_to_bench(db, int(pipeline_id))}
