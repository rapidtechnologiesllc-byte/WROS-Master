"""Creating a job by talking to Flash (flash spec C, "job intake"; CEO 2026-10-15).

"I need a Rails developer for my new client Acme" opens the `job_intake` workflow. Its draft
lives in the conversation's workflow_state, so it survives reloads and works the same at every
brain tier:

- large brain (Claude): offered search_clients / create_client / update_job_draft / create_job
  and asked to fill only what is missing;
- small brain only: one JSON extraction per message, then Flash asks the next missing detail;
- no brain: regular expressions (RULES below), then the same explicit questions.

Every tier writes through the same tools (tools.execute: permission re-checked, every call an
event message), so the job that comes out is the same.

Required: client, title, at least one skill, minimum years, and where (location or remote).
company_type defaults to settings.FLASH_JOB_DEFAULT_COMPANY_TYPE ("Full time") and positions to
settings.FLASH_JOB_DEFAULT_POSITIONS (1). The client is resolved with search_clients: one match is
used, several -> Flash asks which, none -> Flash offers to create it (users holding
clients.create, after a yes). Before creating, Flash asks one line -- "Create Rails Developer for
Acme? yes/no" -- because the job publishes at once and outreach starts. create_job goes through
job_creation_service.submit_job, the one job-creation path.
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.services import flash_conversation_service as conversations
from app.services.flash_brain.llm import BrainUnavailable, Brains
from app.services.flash_brain.tools import (
    FlashTool,
    ToolContext,
    ToolError,
    execute,
    hide,
    nullable,
    register,
    said,
    schema,
    search_clients,
    tools_for,
    visible_client,
)

logger = logging.getLogger(__name__)

KIND = "job_intake"
PERMISSION = "jobs.create"
INTAKE_TOOLS = ["search_clients", "create_client", "update_job_draft", "create_job"]
REQUIRED = ("title", "skills", "min_experience_years", "where")
QUESTIONS = {
    "client": "Which client is this job for?",
    "title": "What's the job title?",
    "skills": "Which skills are required? (comma-separated)",
    "min_experience_years": "How many years of experience does the role need?",
    "where": "Where is the role -- remote, or which city?",
}
WORK_LOCATIONS = ("REMOTE", "ONSITE", "HYBRID")
CANCEL = {"cancel", "stop", "never mind", "nevermind", "drop it"}
_YES = re.compile(r"^\s*(yes|y|yep|yeah|yup|sure|ok|okay|confirm|confirmed|go ahead|do it|create it|please do)\b",
                  re.IGNORECASE)
_NO = re.compile(r"^\s*(no|n|nope|not yet|don't|do not|wait)\b", re.IGNORECASE)

DRAFT_SCHEMA = schema({
    "title": nullable("string", description="Job title, e.g. 'Rails Developer'"),
    "description": nullable("string"),
    "skills": {"type": ["array", "null"], "items": {"type": "string"}, "description": "Required skills"},
    "min_experience_years": nullable("number", description="Minimum years of experience"),
    "location": nullable("string", description="City or country of the role"),
    "work_location": {"type": ["string", "null"], "enum": [*WORK_LOCATIONS, None]},
    "company_type": nullable("string", description="Full time, Contract, ..."),
    "client_name": nullable("string", description="The client's company name as the user said it"),
    "client_id": nullable("string", description="A client id returned by search_clients"),
    "positions": nullable("integer", description="Number of openings"),
})

INTAKE_SYSTEM = (
    "You are Flash, BlitzenX's internal staffing assistant, creating a job with the user. "
    "Call update_job_draft with every job detail the user gives (client, title, skills, minimum years, "
    "location or remote, positions). Its result says what is still missing and what to ask next: ask only "
    "for that, one short question at a time, never for anything already given. Use search_clients to find "
    "the client. create_client and create_job only run after the user answered yes to the exact question "
    "update_job_draft gave you; ask that question word for word and wait. Never invent ids. Keep replies "
    "to one or two sentences.")


# --------------------------------------------------------------------------- draft

def is_yes(text: str) -> bool:
    return bool(_YES.match(text or ""))


def is_no(text: str) -> bool:
    return bool(_NO.match(text or ""))


def _words(text: str) -> str:
    return " ".join((text or "").strip().lower().rstrip(".!").split())


def _years(value) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def missing_slots(draft: Dict) -> List[str]:
    missing = []
    if not draft.get("client_id"):
        missing.append("client")
    if not draft.get("title"):
        missing.append("title")
    if not draft.get("skills"):
        missing.append("skills")
    if draft.get("min_experience_years") is None:
        missing.append("min_experience_years")
    if not draft.get("location") and not draft.get("work_location"):
        missing.append("where")
    return missing


def _where(draft: Dict) -> str:
    if draft.get("work_location") == "REMOTE":
        return "remote"
    place = draft.get("location") or ""
    mode = (draft.get("work_location") or "").lower()
    return f"{mode} in {place}".strip() if mode and place else (place or mode)


def confirm_question(draft: Dict) -> str:
    positions = draft.get("positions") or settings.FLASH_JOB_DEFAULT_POSITIONS
    return (f"Create {draft['title']} for {draft['client_name']} ({', '.join(draft['skills'])}; "
            f"{_years(draft['min_experience_years'])}+ years; {_where(draft)}; {positions} "
            f"position{'s' if positions != 1 else ''}; "
            f"{draft.get('company_type') or settings.FLASH_JOB_DEFAULT_COMPANY_TYPE})? yes/no")


def next_prompt(ctx: ToolContext, state: Dict) -> str:
    """What Flash asks next; records it in `state` (asking / confirm). Does not save."""
    from app.core import authority

    draft = state.setdefault("draft", {})
    state.pop("confirm", None)
    state["asking"] = None
    choices = state.get("client_choices") or []
    if choices:
        state["asking"] = "client_choice"
        names = [c["client_name"] for c in choices]
        return "Which client do you mean: " + ", ".join(names[:-1]) + f" or {names[-1]}?"
    if not draft.get("client_id"):
        name = draft.get("client_name")
        if name and state.get("client_missing") == name:
            if authority.has_permission(ctx.db, ctx.user, "clients.create"):
                question = f"{name} isn't a client yet. Create it (attributed to your business unit)? yes/no"
                state["confirm"] = {"action": "create_client", "question": question, "args": {"company_name": name}}
                return question
            state["asking"] = "client"
            return f"{name} isn't a client yet, and you can't create clients. Which existing client is this for?"
        state["asking"] = "client"
        return QUESTIONS["client"]
    for slot in REQUIRED:
        if slot in missing_slots(draft):
            state["asking"] = slot
            return QUESTIONS[slot]
    question = confirm_question(draft)
    state["confirm"] = {"action": "create_job", "question": question, "args": {}}
    return question


def _ensure_open(ctx: ToolContext, state: Dict) -> None:
    if ctx.conversation.active_workflow != KIND:
        conversations.set_workflow(ctx.db, ctx.conversation, KIND, None, state)


def _clean_skills(values) -> List[str]:
    from app.services.skill_extraction_service import normalize_skills

    if isinstance(values, str):
        values = re.split(r",|;|\band\b|/", values)
    return [n["canonical"] for n in normalize_skills([str(v).strip() for v in values or [] if str(v).strip()])]


def _update_draft(ctx: ToolContext, args: Dict) -> Dict:
    state = ctx.state
    draft = dict(state.get("draft") or {})
    for key in ("title", "description", "location", "company_type"):
        value = (args.get(key) or "").strip() if isinstance(args.get(key), str) else None
        if value:
            draft[key] = value
    if args.get("skills"):
        skills = _clean_skills(args["skills"])
        if skills:
            draft["skills"] = skills
    if args.get("min_experience_years") is not None:
        years = float(args["min_experience_years"])
        if years < 0 or years > 50:
            raise ToolError("Minimum years must be between 0 and 50.")
        draft["min_experience_years"] = years
    if args.get("positions") is not None:
        positions = int(args["positions"])
        if positions < 1:
            raise ToolError("A job needs at least one position.")
        draft["positions"] = positions
    if args.get("work_location"):
        mode = str(args["work_location"]).upper()
        if mode not in WORK_LOCATIONS:
            raise ToolError(f"Work location must be one of {', '.join(WORK_LOCATIONS)}.")
        draft["work_location"] = mode

    if args.get("client_id"):
        client = visible_client(ctx.db, ctx.user, args["client_id"])
        draft.update(client_id=client.id, client_name=client.company_name)
        state["client_choices"], state["client_missing"] = [], None
    elif args.get("client_name") and (args["client_name"].strip().lower() != (draft.get("client_name") or "").lower()
                                      or not draft.get("client_id")):
        name = args["client_name"].strip()
        found = search_clients(ctx.db, ctx.user, name)
        state["client_choices"], state["client_missing"] = [], None
        if len(found) == 1:
            draft.update(client_id=found[0].id, client_name=found[0].company_name)
        else:
            draft.update(client_id=None, client_name=name)
            if found:
                state["client_choices"] = [{"client_id": c.id, "client_name": c.company_name} for c in found]
            else:
                state["client_missing"] = name

    state["draft"] = draft
    _ensure_open(ctx, state)
    prompt = next_prompt(ctx, state)
    ctx.save_state(state)
    missing = missing_slots(draft)
    known = ", ".join(f"{k}={v}" for k, v in _visible_draft(draft).items())
    return {"text": f"Draft: {known or 'empty'}. Next, ask the user: {prompt}", "missing": missing}


def _visible_draft(draft: Dict) -> Dict:
    return {k: draft[k] for k in ("client_name", "title", "skills", "min_experience_years", "location",
                                  "work_location", "positions", "company_type") if draft.get(k) not in (None, "", [])}


def client_created(ctx: ToolContext, client) -> None:
    """create_client ran: an open job draft now points at the new client."""
    if ctx.conversation.active_workflow != KIND:
        return
    state = ctx.state
    state.setdefault("draft", {}).update(client_id=client.id, client_name=client.company_name)
    state["client_choices"], state["client_missing"] = [], None
    next_prompt(ctx, state)
    ctx.save_state(state)


def _description(ctx: ToolContext, draft: Dict) -> str:
    """The job description: the user's own, else drafted by Claude when it is up, else a template."""
    if draft.get("description"):
        return draft["description"]
    template = (f"{draft['title']} for {draft['client_name']}. Required: {', '.join(draft['skills'])}; "
                f"{_years(draft['min_experience_years'])}+ years.")
    brains = ctx.brains
    if brains is not None and brains.large is not None:
        try:
            drafted = brains.large.extract_json(
                purpose="job_description", tenant_id=ctx.user.tenant_id,
                system="Write a concise, factual job description (3-6 sentences) from these facts only. "
                       "Do not invent pay, benefits or contact details.",
                user=template + (f" Work: {_where(draft)}." if _where(draft) else ""),
                schema=schema({"description": {"type": "string"}}))
            if drafted["description"].strip():
                return drafted["description"].strip()
        except BrainUnavailable as exc:
            logger.warning(f"[FlashIntake] description falls back to the template: {exc}")
    return template


def build_request(ctx: ToolContext, draft: Dict, client):
    from app.schemas.user import JobCreateRequest, SkillRequirement

    work_location = draft.get("work_location") or ("REMOTE" if (draft.get("location") or "").lower() == "remote"
                                                   else "ONSITE")
    location = draft.get("location") or ("Remote" if work_location == "REMOTE" else "")
    return JobCreateRequest(
        job_title=draft["title"], job_description=_description(ctx, draft), job_skills=", ".join(draft["skills"]),
        structured_skills=[SkillRequirement(name=s, is_primary=i == 0) for i, s in enumerate(draft["skills"])],
        job_experience=f"{_years(draft['min_experience_years'])}+ years",
        min_experience_years=draft["min_experience_years"], job_location=location, work_location=work_location,
        company_type=draft.get("company_type") or settings.FLASH_JOB_DEFAULT_COMPANY_TYPE,
        company_name=client.company_name, job_status="active",
        no_of_positions=draft.get("positions") or settings.FLASH_JOB_DEFAULT_POSITIONS,
        client_id=client.id, business_unit=client.business_unit_id)


def _create_job(ctx: ToolContext, args: Dict) -> Dict:
    from app.services.job_creation_service import submit_job

    state = ctx.state
    draft = state.get("draft") or {}
    missing = missing_slots(draft)
    if missing:
        raise ToolError("The job still needs: " + ", ".join(missing) + ".")
    client = visible_client(ctx.db, ctx.user, draft["client_id"])
    request = build_request(ctx, draft, client)
    job_id = submit_job(ctx.db, ctx.user, request)
    reply = f"Job {job_id} for {client.company_name} is queued."
    mission_id = start_mission_for(ctx, job_id, request.no_of_positions)
    if mission_id:
        reply += " I'll start sourcing within a few minutes and report back here."
    state.update(done=True, job_id=job_id, mission_id=mission_id)
    ctx.save_state(state)
    return {"text": reply, "job_id": job_id, "mission_id": mission_id, "job_title": request.job_title,
            "client_name": client.company_name}


def start_mission_for(ctx: ToolContext, job_id: str, positions: int) -> Optional[str]:
    """Flash keeps working the job (flash_mission_service) when missions are switched on and the
    user's role template grants flash-missions.create; otherwise the job is simply created."""
    from app.core import authority
    from app.services.flash_mission_service import start_mission

    if not settings.FLASH_MISSIONS_ENABLED or not authority.has_permission(ctx.db, ctx.user, "flash-missions.create"):
        return None
    return start_mission(ctx.db, ctx.user, job_id, positions, conversation_id=ctx.conversation.id).id


register(FlashTool(
    "update_job_draft", "Record job details the user gave (only the ones given; others null). Returns what "
    "is still missing and the exact next question to ask.", DRAFT_SCHEMA, PERMISSION, _update_draft,
    "create jobs", summary=hide))  # an internal step: Flash's reply asks the next question
register(FlashTool(
    "create_job", "Create the drafted job. Only after the user answered yes to the confirmation question.",
    schema({}), PERMISSION, _create_job, "create jobs", mutating=True, confirm=True,
    summary=said(lambda a, o: f"Created job {o['job_title']} for {o['client_name']}"
                              + ("; Flash is working it." if o.get("mission_id") else "."))))


# --------------------------------------------------------------------------- rules tier

_TITLE = re.compile(r"\b((?:senior|junior|lead|principal|staff)\s+)?(\w[\w+#.]*)\s+"
                    r"(developer|engineer|architect|analyst|tester|consultant)s?\b", re.IGNORECASE)
_TITLE_SKIP = {"a", "an", "the", "new", "one", "two", "some", "need", "our", "my"}
_CLIENT = re.compile(r"\bclient\s+(?:is\s+|called\s+|named\s+)?([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})")
_FOR_CLIENT = re.compile(r"\bfor\s+(?:the\s+)?([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})")
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_BARE_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*\+?\s*$")
_POSITIONS = re.compile(r"\b(\d+)\s+(?:positions?|openings?|roles?|people|hires|heads?|seats?)\b", re.IGNORECASE)
_MODE = re.compile(r"\b(remote|on[\s-]?site|hybrid)\b", re.IGNORECASE)
_PLACE = re.compile(r"\b(?:in|at|based in|located in|from)\s+([A-Z][\w-]*(?:,?\s+[A-Z][\w-]*){0,2})")
_COMPANY_TYPE = re.compile(r"\b(full[\s-]?time|part[\s-]?time|contract)\b", re.IGNORECASE)
_COMPANY_TYPES = {"fulltime": "Full time", "parttime": "Part time", "contract": "Contract"}


def rules_fields(text: str, state: Dict) -> Dict:
    """Job details found in `text` by pattern; an answer to the question Flash just asked counts
    as that detail."""
    fields: Dict = {}
    asking = state.get("asking")
    raw = (text or "").strip()
    if asking == "client_choice":
        choices = state.get("client_choices") or []
        index = re.match(r"^\s*(\d+)\b", raw)
        picked = [c for c in choices if c["client_name"].lower() in raw.lower()]
        if index and 1 <= int(index.group(1)) <= len(choices):
            picked = [choices[int(index.group(1)) - 1]]
        if len(picked) == 1:
            fields["client_id"] = picked[0]["client_id"]
        return fields
    fields = _pattern_fields(raw, asking)
    # A plain answer to the question Flash just asked is that detail ("Ruby on Rails", "Acme")
    if asking == "skills":
        fields["skills"] = _clean_skills(raw)
    elif asking == "client" and "client_name" not in fields and not fields:
        fields["client_name"] = raw.rstrip(".")
    elif asking == "title" and "title" not in fields and not fields:
        fields["title"] = raw.rstrip(".")
    return fields


def _pattern_fields(raw: str, asking: Optional[str]) -> Dict:
    from app.constants.skill_synonyms import SKILL_SYNONYM_REVERSE_INDEX

    fields: Dict = {}
    title = _TITLE.search(raw)
    if title and title.group(2).lower() not in _TITLE_SKIP:
        seniority = (title.group(1) or "").strip().capitalize()
        word = title.group(2)
        word = word if any(ch.isupper() for ch in word) else word.capitalize()
        fields["title"] = " ".join(p for p in (seniority, word, title.group(3).capitalize()) if p)
    client = _CLIENT.search(raw) or _FOR_CLIENT.search(raw)
    if client:
        fields["client_name"] = client.group(1).strip()
    lowered = f" {raw.lower()} "
    skills = []
    for synonym, canonical in SKILL_SYNONYM_REVERSE_INDEX.items():
        if re.search(rf"(?<![\w.+#]){re.escape(synonym)}(?![\w+#])", lowered) and canonical not in skills:
            skills.append(canonical)
    if skills:
        fields["skills"] = skills
    years = _YEARS.search(raw) or (_BARE_NUMBER.match(raw) if asking == "min_experience_years" else None)
    if years:
        fields["min_experience_years"] = float(years.group(1))
    positions = _POSITIONS.search(raw)
    if positions:
        fields["positions"] = int(positions.group(1))
    mode = _MODE.search(raw)
    if mode:
        fields["work_location"] = {"remote": "REMOTE", "hybrid": "HYBRID"}.get(mode.group(1).lower(), "ONSITE")
    place = _PLACE.search(raw)
    if place and place.group(1) != fields.get("client_name"):
        fields["location"] = place.group(1).strip()
    elif asking == "where" and not mode:
        fields["location"] = raw.rstrip(".")
    company_type = _COMPANY_TYPE.search(raw)
    if company_type:
        fields["company_type"] = _COMPANY_TYPES[re.sub(r"[\s-]", "", company_type.group(1).lower())]
    return fields


def small_fields(brains: Brains, ctx: ToolContext, text: str, state: Dict) -> Optional[Dict]:
    """One extraction by the small model; None when it is offline or fails."""
    if brains.small is None:
        return None
    asked = QUESTIONS.get(state.get("asking") or "", "")
    try:
        data = brains.small.extract_json(
            purpose="intake", tenant_id=ctx.user.tenant_id, schema=DRAFT_SCHEMA,
            system="Extract job details from the user's answer. Use null for anything not stated. Never guess.",
            user=(f"Flash asked: {asked}\n" if asked else "") + f"User said: {text}")
    except BrainUnavailable as exc:
        logger.warning(f"[FlashIntake] small model could not extract: {exc}")
        return None
    return {k: v for k, v in data.items() if v not in (None, "", [])}


# --------------------------------------------------------------------------- workflow

class JobIntakeWorkflow:
    kind = KIND
    uses_brains = True

    def _require(self, ctx) -> None:
        from app.core import authority

        if not authority.has_permission(ctx.db, ctx.user, PERMISSION):
            raise HTTPException(status_code=403, detail="You don't have permission to create jobs.")

    @staticmethod
    def _tool_context(ctx) -> ToolContext:
        return ToolContext(ctx.db, ctx.user, ctx.conversation, ctx.now or datetime.utcnow(), brains=ctx.brains)

    def open(self, ctx, ref: Optional[str]) -> Dict:
        self._require(ctx)
        tool_ctx = self._tool_context(ctx)
        state = {"draft": {}}
        prompt = next_prompt(tool_ctx, state)
        return {"reply": f"Let's set up the job. {prompt} Type cancel to stop.", "done": False, "state": state}

    def step(self, ctx, text: str) -> Dict:
        self._require(ctx)
        tool_ctx = self._tool_context(ctx)
        if _words(text) in CANCEL:
            return {"reply": "Okay, I've dropped the job draft; nothing was created.", "done": True}
        state = tool_ctx.state
        pending = state.get("confirm")
        if pending and is_yes(text):
            state["confirmed"] = pending["action"]
        else:
            state.pop("confirmed", None)
        tool_ctx.save_state(state)

        brains = ctx.brains or Brains()
        reply = None
        if brains.large is not None:
            reply, brains = self._large_step(ctx, tool_ctx, text, brains)
            ctx.brains = brains
        if reply is None:
            reply = self._deterministic_step(tool_ctx, text, brains)
        state = tool_ctx.state
        return {"reply": reply, "done": bool(state.get("done")), "state": state,
                "job_id": state.get("job_id"), "mission_id": state.get("mission_id")}

    def _large_step(self, ctx, tool_ctx: ToolContext, text: str, brains: Brains):
        tools = tools_for(tool_ctx.db, tool_ctx.user, names=INTAKE_TOOLS)
        draft = _visible_draft(tool_ctx.state.get("draft") or {})
        message = f"{text}\n\n[Job draft so far: {json.dumps(draft, default=str)}]"
        try:
            result = brains.large.run_tools(system=INTAKE_SYSTEM, history=ctx.history or [], user_message=message,
                                            tools=tools, execute=lambda name, args: execute(tool_ctx, name, args),
                                            tenant_id=tool_ctx.user.tenant_id, purpose="intake")
        except BrainUnavailable as exc:
            logger.warning(f"[FlashIntake] Claude unavailable, continuing without it: {exc}")
            return self._after_partial(tool_ctx), brains.without("large", str(exc))
        if result.refused or not result.text:
            return self._after_partial(tool_ctx), brains.without("large", f"Claude stopped ({result.stop_reason})")
        return result.text, brains

    @staticmethod
    def _after_partial(tool_ctx: ToolContext) -> Optional[str]:
        """Claude stopped after running tools: say what they did instead of re-applying the message."""
        if not tool_ctx.trace:
            return None
        last = tool_ctx.trace[-1]["outcome"]
        if tool_ctx.state.get("done"):
            return last.get("text")
        state = tool_ctx.state
        prompt = next_prompt(tool_ctx, state)
        tool_ctx.save_state(state)
        return prompt

    def _deterministic_step(self, tool_ctx: ToolContext, text: str, brains: Brains) -> str:
        state = tool_ctx.state
        confirmed = state.get("confirmed")
        if confirmed in ("create_client", "create_job"):
            outcome = execute(tool_ctx, confirmed, (state.get("confirm") or {}).get("args") or {})
            if "error" in outcome:
                return outcome["error"]
            if confirmed == "create_client":
                return f"{outcome['text']} {self._prompt(tool_ctx)}"
            return outcome["text"]
        if state.get("confirm") and is_no(text):
            state.pop("confirm", None)
            state["asking"] = None
            tool_ctx.save_state(state)
            return "Okay, nothing was created. Tell me what to change, or type cancel to drop the draft."
        fields = small_fields(brains, tool_ctx, text, state)
        if fields is None or (state.get("asking") == "client_choice" and "client_id" not in fields):
            fields = {**rules_fields(text, state), **(fields or {})}
        if not fields:
            return f"I didn't catch that. {self._prompt(tool_ctx)}"
        outcome = execute(tool_ctx, "update_job_draft", fields)
        if "error" in outcome:
            return outcome["error"]
        return self._prompt(tool_ctx)

    @staticmethod
    def _prompt(tool_ctx: ToolContext) -> str:
        state = tool_ctx.state
        prompt = next_prompt(tool_ctx, state)
        tool_ctx.save_state(state)
        return prompt
