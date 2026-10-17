"""Flash workflows (flash spec B): a discussion that owns the conversation until it is done. It is
opened by a deep link (`?flash=kind:ref`, POST /flash/workflows/open) or by Flash itself; while it
is open every message goes to it, and the cancel words leave it.

A workflow re-checks the user's permission and the record's scope at every step (`_load`), and
delegates to the domain service -- no business rule is duplicated here.

Registry: WORKFLOWS[kind] -> object with open(ctx, ref) and step(ctx, text), each returning
{"reply": str, "done": bool, "state": dict | None}.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.flash_conversation import FlashConversation
from app.models.user import Users
from app.services import flash_conversation_service as conversations

logger = logging.getLogger(__name__)

CANCEL_HINT = "Type cancel to leave this discussion."


@dataclass
class WorkflowContext:
    db: Session
    user: Users
    conversation: FlashConversation

    @property
    def state(self) -> Dict:
        return dict(self.conversation.workflow_state or {})


def _words(text: str) -> str:
    return " ".join((text or "").strip().lower().rstrip(".!").split())


class CoreCertWorkflow:
    """Decide a Core certification request in the bubble: approve, close (no longer eligible) or
    reject through core_certification_service.reject_chat, whose state stays on the request."""

    kind = "core_cert"
    permission = "workforce-overview.view"
    APPROVE = {"approve", "approve it", "yes approve", "yes, approve", "approved"}
    REJECT = {"reject", "reject it", "no", "decline", "do not approve", "don't approve", "not approve"}
    CLOSE = {"close", "close it", "close the request", "yes close", "yes"}

    def _load(self, ctx: WorkflowContext, ref: Optional[str]):
        from app.core import authority
        from app.services import core_certification_service as service

        if not authority.has_permission(ctx.db, ctx.user, self.permission):
            raise HTTPException(status_code=403, detail="You don't have permission to see Core certification requests.")
        row = service.visible_request(ctx.db, ctx.user, ref or "")
        if row is None:
            raise HTTPException(status_code=404, detail="That Core certification request was not found.")
        return row

    @staticmethod
    def _name(employee) -> str:
        return f"{employee.first_name} {employee.last_name}".strip()

    def open(self, ctx: WorkflowContext, ref: str) -> Dict:
        from app.services import core_certification_service as service

        request, employee = self._load(ctx, ref)
        name = self._name(employee)
        if request.status != "PENDING":
            return {"reply": f"{name}'s Core certification request is already {request.status.lower()}.", "done": True}
        if not service.may_decide(ctx.db, request, ctx.user):
            return {"reply": (f"{name}'s Core certification is waiting on their BU Head. Only the BU Head or another "
                              "leader of that business unit can decide it."), "done": True}
        if request.chat_state:  # a rejection discussion was under way: pick it up
            turn = service.reject_chat(ctx.db, request, ctx.user, "")
            return {"reply": f"{turn['reply']} {CANCEL_HINT}", "done": turn["done"], "state": {"mode": "reject"}}
        check = service.eligibility(ctx.db, employee)
        if not check["eligible"]:
            return {"reply": (f"{name} no longer qualifies for Core certification: {' '.join(check['reasons'])} "
                              f"Close the request? Reply yes, or cancel to leave it pending."),
                    "done": False, "state": {"mode": "close"}}
        return {"reply": (f"{name} qualifies for Core certification: Buddy Program graduated and "
                          f"{check['billable_days']} approved billable Staff Aug days with no escalation. "
                          f"Approve or reject? {CANCEL_HINT}"),
                "done": False, "state": {"mode": "decide"}}

    def step(self, ctx: WorkflowContext, text: str) -> Dict:
        from app.services import core_certification_service as service

        request, employee = self._load(ctx, ctx.conversation.workflow_ref)
        name, said, mode = self._name(employee), _words(text), ctx.state.get("mode")
        try:
            if mode == "reject":
                turn = service.reject_chat(ctx.db, request, ctx.user, text)
                return {"reply": turn["reply"], "done": turn["done"], "state": {"mode": "reject"}}
            if said in service.CANCEL:
                return {"reply": f"Okay. {name}'s request stays pending.", "done": True}
            if mode == "close":
                if said in self.CLOSE:
                    service.close(ctx.db, request, ctx.user)
                    return {"reply": f"Closed: {name} no longer qualifies; a new request is raised when they do.",
                            "done": True}
                return {"reply": "Reply yes to close the request, or cancel to leave it pending.", "done": False,
                        "state": {"mode": "close"}}
            if said in self.APPROVE:
                service.approve(ctx.db, request, ctx.user)
                return {"reply": f"Approved: {name} is now Core-certified.", "done": True}
            if said in self.REJECT:
                turn = service.reject_chat(ctx.db, request, ctx.user, "")
                return {"reply": turn["reply"], "done": turn["done"], "state": {"mode": "reject"}}
            return {"reply": f"Reply approve or reject for {name}. {CANCEL_HINT}", "done": False,
                    "state": {"mode": "decide"}}
        except service.CertificationError as exc:
            return {"reply": str(exc), "done": True}


WORKFLOWS = {CoreCertWorkflow.kind: CoreCertWorkflow()}


def _apply(db: Session, conversation: FlashConversation, kind: str, ref: Optional[str], result: Dict) -> Dict:
    if result.get("done"):
        conversations.clear_workflow(db, conversation)
    else:
        conversations.set_workflow(db, conversation, kind, ref, result.get("state"))
    return result


def open_workflow(db: Session, user: Users, conversation: FlashConversation, kind: str, ref: str) -> Dict:
    """Validate the workflow's permission and scope, make it the active one, return its first prompt.
    Raises HTTPException (404 unknown kind or record, 403 no permission)."""
    workflow = WORKFLOWS.get(kind)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Flash has no '{kind}' discussion.")
    result = workflow.open(WorkflowContext(db, user, conversation), ref)
    return _apply(db, conversation, kind, ref, result)


def step_workflow(db: Session, user: Users, conversation: FlashConversation, text: str) -> Dict:
    """One message to the active workflow. A workflow the user may no longer see ends with the reason."""
    kind, ref = conversation.active_workflow, conversation.workflow_ref
    workflow = WORKFLOWS.get(kind)
    if workflow is None:
        logger.error(f"[Flash] conversation {conversation.id} had unknown workflow {kind!r}; cleared")
        return _apply(db, conversation, kind, ref, {"reply": "That discussion is no longer available.", "done": True})
    try:
        result = workflow.step(WorkflowContext(db, user, conversation), text)
    except HTTPException as exc:
        result = {"reply": str(exc.detail), "done": True}
    return _apply(db, conversation, kind, ref, result)
