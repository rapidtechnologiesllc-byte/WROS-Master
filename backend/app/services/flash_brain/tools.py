"""Flash's tools (flash spec C): what Flash may do for the person it is talking to.

Flash acts as that person. A tool is checked twice -- when it is offered (tools_for: a model is
only shown the tools the user may call) and again when it runs (execute) -- with the user's
role-template permissions (app.core.authority) and, for records, the existing scope helpers
called with the user. A denied tool returns {"error": "You don't have permission to ..."}, writes
nothing, and the reply says so plainly.

Every call is stored in the conversation as an `event` message. The payload keeps the full trace
for audit (tool, args, the whole outcome, ok, the raw "tool: text" line); the body is what the
person reads -- a one-line summary chosen per tool by its `summary` function ("Created job Rails
Developer for Acme"). A summary of None marks a purely internal step (a draft update, a client
lookup): the payload says `hidden` and the Flash bubble does not show it. A permission refusal is
always shown.

A tool marked `confirm` runs only after the user's explicit "yes" to the one-line question Flash
asked (the conversation's workflow state carries `confirm` / `confirmed`).

Autonomy boundary (CEO 2026-10-15): there is no tool that records an interview verdict, rejects
a candidate, hires, approves an offer, submits to a client or changes a candidate's status.
Flash reads those facts; people decide them. tests/test_flash_agent.py asserts the registry
holds none.

Finance (P&L, overdue invoices) is answered from the database only: those tools are never
offered to a language model (`model_visible=False`), so no finance figure reaches one.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.flash_conversation import FlashConversation
from app.models.user import Users
from app.services import flash_conversation_service as conversations

logger = logging.getLogger(__name__)

MAX_CLIENT_MATCHES = 5
EVENT_SUMMARY_CHARS = 300
# Words no tool name may contain: the decisions Flash never takes (asserted by a test)
FORBIDDEN_TOOL_WORDS = ("verdict", "reject", "hire", "offer", "submit", "submission", "approve", "candidate_status_change")


class ToolError(ValueError):
    """A tool could not do what was asked; the message is shown to the user (and the model)."""


@dataclass(frozen=True)
class FlashTool:
    name: str
    description: str
    input_schema: dict
    permission: Optional[str]  # "resource.action" (authority.has_permission); None = self-scoped
    handler: Callable[["ToolContext", dict], dict]  # returns {"text": str, ...data}
    denied: str  # completes "You don't have permission to ..."
    mutating: bool = False
    confirm: bool = False  # runs only after the user's explicit yes to Flash's question
    gate: Optional[Callable[[Session, Users], bool]] = None  # a rule on top of the permission
    model_visible: bool = True  # False: answered from the database only, never offered to a model
    # (args, outcome) -> the one line the person reads, or None for an internal step (not shown).
    # Required: register() refuses a tool without one.
    summary: Optional[Callable[[Dict, Dict], Optional[str]]] = None


@dataclass
class ToolContext:
    db: Session
    user: Users
    conversation: FlashConversation
    now: datetime
    brains: Any = None  # flash_brain.llm.Brains, for a tool that may draft text (job description)
    trace: List[Dict] = field(default_factory=list)  # every call made in this turn

    @property
    def state(self) -> Dict:
        return dict(self.conversation.workflow_state or {})

    def save_state(self, state: Dict) -> None:
        self.conversation.workflow_state = dict(state)
        self.db.flush()


def schema(properties: Dict[str, dict]) -> dict:
    """A strict tool schema: every property listed in `required` (optional ones are nullable) and
    no other property allowed -- what `strict: true` tool use requires."""
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties)}


def nullable(kind: str, **extra) -> dict:
    return {"type": [kind, "null"], **extra}


TOOLS: Dict[str, FlashTool] = {}


def register(tool: FlashTool) -> FlashTool:
    if tool.name in TOOLS:
        raise ValueError(f"Flash tool {tool.name!r} registered twice")
    if any(word in tool.name for word in FORBIDDEN_TOOL_WORDS):
        raise ValueError(f"Flash tool {tool.name!r} would take a decision Flash never takes")
    if tool.summary is None:
        raise ValueError(f"Flash tool {tool.name!r} has no summary: say what the person reads, or hide()")
    TOOLS[tool.name] = tool
    return tool


def allowed(db: Session, user: Users, tool: FlashTool) -> bool:
    from app.core import authority

    if tool.permission is not None and not authority.has_permission(db, user, tool.permission):
        return False
    return tool.gate is None or bool(tool.gate(db, user))


def tools_for(db: Session, user: Users, *, names: Optional[List[str]] = None) -> List[FlashTool]:
    """The tools a model may be offered for this user: permitted ones only, finance never."""
    _load_registry()
    pool = [TOOLS[n] for n in names] if names is not None else list(TOOLS.values())
    return [t for t in pool if t.model_visible and allowed(db, user, t)]


def _summary(outcome: Dict) -> str:
    text = outcome.get("error") or outcome.get("text") or "done"
    return str(text)[:EVENT_SUMMARY_CHARS]


def _one_line(text: str) -> str:
    line = " ".join(str(text).split())
    return line if len(line) <= EVENT_SUMMARY_CHARS else line[:EVENT_SUMMARY_CHARS - 1].rstrip() + "…"


# --------------------------------------------------------------------------- summaries

def hide(args: Dict, outcome: Dict) -> Optional[str]:
    """An internal step: kept in the audit trail, not shown in the bubble."""
    return None


def said(fn: Callable[[Dict, Dict], Optional[str]]) -> Callable[[Dict, Dict], Optional[str]]:
    """`fn` for a successful call; a failed one shows its (user-facing) error."""
    def summary(args: Dict, outcome: Dict) -> Optional[str]:
        return outcome["error"] if "error" in outcome else fn(args, outcome)
    return summary


def first_line(args: Dict, outcome: Dict) -> Optional[str]:
    """The tool's own text (or error), first line: for tools whose text is already a sentence for
    the person."""
    text = (outcome.get("error") or outcome.get("text") or "").strip()
    return text.splitlines()[0] if text else None


def _count(outcome: Dict, key: str) -> int:
    return len(outcome.get(key) or [])


def _for(value: Optional[str]) -> str:
    value = (value or "").strip()
    return f" for {value}" if value else ""


def _event_line(name: str, tool: Optional[FlashTool], args: Dict, outcome: Dict, refused: bool) -> Optional[str]:
    """What the person reads for this call, or None (not shown). Refusals are always shown; a
    call to no tool, or a confirmation not yet given, is Flash's own protocol and never shown."""
    if refused:
        return outcome["error"]
    if tool is None:
        return None
    line = tool.summary(args, outcome)
    return _one_line(line) if line else None


def execute(ctx: ToolContext, name: str, args: Optional[Dict] = None) -> Dict:
    """Run one tool as ctx.user. Permission and confirmation are re-checked here, whoever calls;
    a refusal or a domain error comes back as {"error": message}. The call is recorded as an
    event message."""
    _load_registry()
    args = dict(args or {})
    tool = TOOLS.get(name)
    refused, protocol = False, False
    if tool is None:
        outcome = {"error": f"Flash has no tool called {name}."}
        protocol = True
    elif not allowed(ctx.db, ctx.user, tool):
        outcome = {"error": f"You don't have permission to {tool.denied}."}
        refused = True
    elif tool.confirm and ctx.state.get("confirmed") != name:
        question = (ctx.state.get("confirm") or {}).get("question")
        outcome = {"error": "Not confirmed yet. " + (f"Ask the user: {question}" if question
                                                       else "Ask the user to confirm first.")}
        protocol = True
    else:
        try:
            outcome = tool.handler(ctx, args)
        except HTTPException as exc:
            outcome = {"error": exc.detail if isinstance(exc.detail, str) else str(exc.detail)}
        except ToolError as exc:
            outcome = {"error": str(exc)}
        if tool.confirm:
            state = ctx.state
            state.pop("confirmed", None)
            if "error" not in outcome:
                state.pop("confirm", None)
            ctx.save_state(state)
    if not isinstance(outcome, dict):
        raise TypeError(f"Flash tool {name} returned {type(outcome).__name__}, not a dict")
    trace_line = f"{name}: {_summary(outcome)}"
    line = None if protocol else _event_line(name, tool, args, outcome, refused)
    conversations.append(ctx.db, ctx.conversation, "event", line or trace_line,
                         {"tool": name, "args": jsonable_encoder(args), "outcome": jsonable_encoder(outcome),
                          "ok": "error" not in outcome, "hidden": line is None, "trace": trace_line})
    ctx.trace.append({"name": name, "args": args, "outcome": outcome})
    logger.info(f"[FlashTool] {ctx.user.UserID} {name} -> {'error' if 'error' in outcome else 'ok'}")
    return outcome


# --------------------------------------------------------------------------- read tools

def _find_candidates(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("Say which role or skills to search for.")
    results = flash_service.find_matching_candidates(ctx.db, query, tenant_id=ctx.user.tenant_id,
                                                     user_bu_id=ctx.user.business_unit_id)
    return {"text": flash_service._format_sourcing_reply(query, results),
            "results": [{k: r[k] for k in ("candidate_id", "name", "job_title", "skills", "score")} for r in results]}


def _candidate_status(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    name = (args.get("name") or "").strip()
    if not name:
        raise ToolError("Say whose status you want.")
    found = flash_service.get_candidate_status_summary(ctx.db, name, tenant_id=ctx.user.tenant_id,
                                                       user_bu_id=ctx.user.business_unit_id)
    return {"text": flash_service._format_status_reply(name, found["matches"]), "matches": found["matches"]}


def _bench(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    skills = (args.get("skills") or "").strip()
    results = flash_service.find_available_bench_employees(ctx.db, ctx.user, skills)
    return {"text": flash_service._format_bench_reply(skills, results), "results": results}


def _bench_cost(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    report = flash_service.get_bench_cost_answer(ctx.db, ctx.user)
    return {"text": flash_service.format_bench_cost_reply(report), "totals": report["totals"],
            "link": flash_service.BENCH_SCREEN_PATH}


def _bu_pnl(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    result = flash_service.get_finance_pnl_answer(ctx.db, ctx.user, (args.get("bu") or "").strip())
    return {"text": flash_service._format_finance_pnl_reply(result)}


def _overdue_invoices(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    return {"text": flash_service._format_ar_aging_reply(flash_service.get_ar_aging_answer(ctx.db, ctx.user))}


def _my_tasks(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    tasks = flash_service.get_my_tasks_answer(ctx.db, ctx.user)
    return {"text": flash_service._format_my_tasks_reply(tasks),
            "tasks": [{"id": t["id"], "title": t["title"], "priority": t["priority"], "status": t["status"]}
                      for t in tasks]}


def _my_timesheets(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    return {"text": flash_service._format_my_timesheets_reply(flash_service.get_my_timesheets_answer(ctx.db, ctx.user))}


def _pipeline_summary(ctx: ToolContext, args: Dict) -> Dict:
    from app.services import flash_service

    result = flash_service.get_pipeline_summary(ctx.db, ctx.user, (args.get("client") or "").strip())
    return {"text": flash_service._format_pipeline_summary(result), "total": result["total"]}


def _pending_decisions(ctx: ToolContext, args: Dict) -> Dict:
    from app.services.flash_brain.decisions import pending_decisions

    decisions = pending_decisions(ctx.db, ctx.user)
    if not decisions:
        return {"text": "Nothing is waiting for your decision.", "decisions": []}
    lines = [f"- {d.text}" for d in decisions]
    return {"text": f"{len(decisions)} decision(s) waiting for you:\n" + "\n".join(lines),
            "decisions": [{"kind": d.kind, "ref": d.ref, "text": d.text} for d in decisions]}


def _open_core_cert(ctx: ToolContext, args: Dict) -> Dict:
    from app.services.flash_brain.workflows import open_workflow

    result = open_workflow(ctx.db, ctx.user, ctx.conversation, "core_cert", str(args.get("request_id") or ""))
    return {"text": result["reply"]}


# --------------------------------------------------------------------------- clients

def search_clients(db: Session, user: Users, name: str) -> List:
    """Clients in the user's tenant and business units whose name contains `name` (any case), at
    most MAX_CLIENT_MATCHES. An exact name match alone wins over partial ones."""
    from app.core.data_scope import bu_filter
    from app.models.client import Client

    wanted = (name or "").strip().lower()
    if not wanted:
        return []
    rows = (db.query(Client)
            .filter(Client.tenant_id == user.tenant_id, bu_filter(db, user, Client.business_unit_id),
                    func.lower(Client.company_name).like(f"%{wanted}%"))
            .order_by(Client.company_name).limit(MAX_CLIENT_MATCHES).all())
    exact = [c for c in rows if (c.company_name or "").strip().lower() == wanted]
    return exact or rows


def visible_client(db: Session, user: Users, client_id: str):
    from app.core.data_scope import bu_filter
    from app.models.client import Client

    client = (db.query(Client)
              .filter(Client.id == client_id, Client.tenant_id == user.tenant_id,
                      bu_filter(db, user, Client.business_unit_id)).first())
    if client is None:
        raise ToolError("That client was not found.")
    return client


def _search_clients(ctx: ToolContext, args: Dict) -> Dict:
    name = (args.get("name") or "").strip()
    found = search_clients(ctx.db, ctx.user, name)
    if not found:
        return {"text": f"No client matches \"{name}\".", "clients": []}
    return {"text": f"{len(found)} client(s) match \"{name}\": " + ", ".join(c.company_name for c in found) + ".",
            "clients": [{"client_id": c.id, "client_name": c.company_name} for c in found]}


def _create_client(ctx: ToolContext, args: Dict) -> Dict:
    from app.core.data_scope import ensure_assignable
    from app.services import client_service
    from app.services.flash_brain import job_intake

    name = (args.get("company_name") or "").strip()
    if not name:
        raise ToolError("Say the client's company name.")
    ensure_assignable(ctx.db, ctx.user, ctx.user.business_unit_id, "client")
    try:
        client = client_service.create_client(ctx.db, company_name=name, created_by_user=ctx.user,
                                              country=args.get("country") or None)
    except (client_service.ClientValidationError, client_service.DuplicateClientError) as exc:
        raise ToolError(str(exc)) from exc
    job_intake.client_created(ctx, client)
    return {"text": f"Created client {client.company_name}.", "client_id": client.id,
            "client_name": client.company_name}


# --------------------------------------------------------------------------- registry

_LOADED = False


def _load_registry() -> None:
    """Tools from other modules (job intake, missions) register on first use."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    from app.services import flash_mission_service  # noqa: F401 -- registers the mission tools
    from app.services.flash_brain import job_intake  # noqa: F401 -- registers its tools


def _can_view_pnl(db: Session, user: Users) -> bool:
    from app.core.revenue_visibility_scope import can_view_pnl

    return can_view_pnl(db, user)


register(FlashTool(
    "find_candidates", "Search candidates by role or skills the user can see.",
    schema({"query": {"type": "string", "description": "Role or skills, e.g. 'Guidewire developer'"}}),
    "candidates.view", _find_candidates, "see candidates",
    summary=said(lambda a, o: f"Searched candidates{_for(a.get('query'))}: {_count(o, 'results')} found.")))
register(FlashTool(
    "candidate_status", "Where a named candidate is in hiring.",
    schema({"name": {"type": "string"}}), "candidates.view", _candidate_status, "see candidates",
    summary=said(lambda a, o: f"Looked up {a['name'].strip()}'s hiring status.")))  # the handler needs a name
register(FlashTool(
    "bench_availability", "Employees on the bench, optionally with given skills.",
    schema({"skills": {"type": "string", "description": "Skills, may be empty"}}),
    "employees.view", _bench, "see the bench",
    summary=said(lambda a, o: f"Checked the bench{_for(a.get('skills'))}: {_count(o, 'results')} available.")))
register(FlashTool(
    "bench_cost", "How much the bench is costing: people, bench days, bench loss, margin while allocated, net.",
    schema({}), "workforce-overview.view", _bench_cost, "see the bench", model_visible=False,
    summary=said(lambda a, o: "Checked what the bench is costing.")))
register(FlashTool(
    "bu_pnl", "A business unit's P&L.", schema({"bu": {"type": "string"}}), None, _bu_pnl,
    "see financial data", gate=_can_view_pnl, model_visible=False,
    summary=said(lambda a, o: f"Looked up the P&L{_for(a.get('bu'))}.")))
register(FlashTool(
    "overdue_invoices", "Overdue client invoices.", schema({}), None, _overdue_invoices,
    "see financial data", gate=_can_view_pnl, model_visible=False,
    summary=said(lambda a, o: "Looked up overdue invoices.")))
register(FlashTool("my_tasks", "The user's own tasks due today or overdue.", schema({}), None, _my_tasks,
                   "see these tasks", summary=said(lambda a, o: f"Checked your tasks: {_count(o, 'tasks')} due.")))
register(FlashTool("my_timesheets", "The user's own recent timesheets.", schema({}), None, _my_timesheets,
                   "see these timesheets", summary=said(lambda a, o: "Checked your timesheets.")))
register(FlashTool(
    "pipeline_summary", "How many candidates are at each hiring stage, optionally for one client.",
    schema({"client": {"type": "string", "description": "Client name, may be empty"}}),
    "candidates.view", _pipeline_summary, "see candidates",
    summary=said(lambda a, o: f"Checked the hiring pipeline{_for(a.get('client'))}.")))
register(FlashTool(
    "search_clients", "Find existing clients by name (use before creating a job or a client).",
    schema({"name": {"type": "string"}}), "clients.view", _search_clients, "see clients",
    summary=hide))  # a lookup on the way to a job or client; the reply says what was found
register(FlashTool(
    "create_client", "Create a new client attributed to the user's business unit. Only after the user "
    "said yes to Flash's question.",
    schema({"company_name": {"type": "string"}, "country": nullable("string")}),
    "clients.create", _create_client, "create clients", mutating=True, confirm=True,
    summary=said(lambda a, o: f"Created client {o['client_name']}.")))
register(FlashTool(
    "pending_decisions", "Decisions waiting for the user (approvals, mixed interview feedback).",
    schema({}), None, _pending_decisions, "see decisions",
    summary=said(lambda a, o: f"Checked your decisions: {_count(o, 'decisions')} waiting.")))
register(FlashTool(
    "open_core_cert", "Open a Core certification request for the user to decide in this chat.",
    schema({"request_id": {"type": "string"}}), "workforce-overview.view", _open_core_cert,
    "see Core certification requests", summary=said(lambda a, o: "Opened the Core certification request.")))
