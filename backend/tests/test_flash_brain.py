"""Flash's brain layer (spec A, CEO decision 1): the Claude tool loop through the official SDK
(fake client, no network), the small model's JSON parsing, degradation tiers and their offline
notes, PromptExecutionLog rows written outside the caller's transaction, and the data rule --
an email, a phone number or pay never reaches any model."""
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.core.config import settings
from app.services.flash_brain import llm
from app.services.flash_brain.llm import BrainUnavailable, Brains, LargeBrain, SmallBrain, ToolDefinition
from app.services.flash_brain.redaction import redact_payload, redact_text
from app.services.flash_brain.router import route_intent

INTENTS = {"bench_availability": "who is on the bench", "my_tasks": "the asker's tasks"}

EMAIL = "priya.s@example.com"
PHONE = "+91 98765 43210"
SALARY = "18 LPA"
SECRETS = (EMAIL, "98765", "43210", "18 LPA", "150000", "85/hr", "drive.example.com", "resume.pdf", "32%")

FIND = ToolDefinition("find_candidates", "Find candidates for a role",
                      {"type": "object", "additionalProperties": False, "required": ["query"],
                       "properties": {"query": {"type": "string"}}})
STATUS = ToolDefinition("candidate_status", "Where a candidate is in hiring",
                        {"type": "object", "additionalProperties": False, "required": ["name"],
                         "properties": {"name": {"type": "string"}}})


# ---------------------------------------------------------------------------- fakes

def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool(id_, name, args):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def _response(stop, *content):
    return SimpleNamespace(stop_reason=stop, content=list(content),
                           usage=SimpleNamespace(input_tokens=11, output_tokens=7))


class FakeAnthropic:
    """Stands in for anthropic.Anthropic: scripted responses (or exceptions), every request kept."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=lambda o: o.__dict__)))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _large(client, logs=None, rounds=8, fallbacks=True):
    return LargeBrain(client=client, model="claude-opus-5-5", effort="medium", max_tokens=16000,
                      max_tool_rounds=rounds, fallbacks=fallbacks,
                      log_writer=(logs.append if logs is not None else lambda row: None))


def _small_reply(content, status=200):
    return SimpleNamespace(status_code=status, json=lambda: {"message": {"content": content}})


def _small(replies, logs=None, sent=None):
    replies = list(replies)

    def post(url, json=None, timeout=None):
        if sent is not None:
            sent.append({"url": url, "json": json, "timeout": timeout})
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return SmallBrain(base_url="http://ollama:11434/", model="qwen", timeout_s=15, post=post,
                      log_writer=(logs.append if logs is not None else lambda row: None))


# ---------------------------------------------------------------------------- tool loop

def test_parallel_tool_calls_come_back_in_one_user_message_with_errors_flagged():
    client = FakeAnthropic(
        _response("tool_use", _text("Looking."), _tool("t1", "find_candidates", {"query": "rails"}),
                  _tool("t2", "candidate_status", {"name": "Priya"})),
        _response("end_turn", _text("Priya is at L1.")))
    calls = []

    def execute(name, args):
        calls.append((name, args))
        return {"error": "You don't have permission to view candidates."} if name == "candidate_status" \
            else {"text": "1 match", "results": [{"name": "Priya S", "skills": ["Ruby on Rails"]}]}

    result = _large(client).run_tools(system="sys", history=[], user_message="find rails devs and Priya's status",
                                      tools=[FIND, STATUS], execute=execute, tenant_id=1)

    assert result.text == "Priya is at L1." and result.rounds == 1 and not result.refused
    assert calls == [("find_candidates", {"query": "rails"}), ("candidate_status", {"name": "Priya"})]
    second = client.requests[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    results = second[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert results[1]["is_error"] is True and "is_error" not in results[0]
    first = client.requests[0]
    assert all(t["strict"] is True for t in first["tools"])
    assert first["output_config"] == {"effort": "medium"} and "thinking" not in first
    assert first["betas"] == ["server-side-fallback-2026-07-01"] and first["fallbacks"] == "default"
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "tool_choice" not in first


def test_invalid_tool_input_is_returned_as_an_error_and_never_executed():
    client = FakeAnthropic(_response("tool_use", _tool("t1", "find_candidates", {"q": 1})),
                           _response("end_turn", _text("ok")))
    executed = []
    result = _large(client).run_tools(system="s", history=[], user_message="x", tools=[FIND],
                                      execute=lambda n, a: executed.append(n) or {}, tenant_id=1)
    assert executed == [] and result.trace[0]["error"]
    assert client.requests[1]["messages"][-1]["content"][0]["is_error"] is True


def test_the_round_limit_holds_by_withholding_tools_on_the_last_round():
    loops = [_response("tool_use", _tool(f"t{i}", "find_candidates", {"query": "x"})) for i in range(2)]
    client = FakeAnthropic(*loops, _response("end_turn", _text("Here is what I found.")))
    result = _large(client, rounds=2).run_tools(system="s", history=[], user_message="x", tools=[FIND],
                                                execute=lambda n, a: {"text": "none"}, tenant_id=1)
    assert result.rounds == 2 and result.text == "Here is what I found."
    assert client.requests[2]["tool_choice"] == {"type": "none"}
    stubborn = FakeAnthropic(*loops, _response("tool_use", _tool("t9", "find_candidates", {"query": "x"})))
    assert _large(stubborn, rounds=2).run_tools(system="s", history=[], user_message="x", tools=[FIND],
                                                execute=lambda n, a: {"text": "none"}, tenant_id=1).refused


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_refusal_or_truncation_tells_the_caller_to_fall_back(stop):
    result = _large(FakeAnthropic(_response(stop))).run_tools(system="s", history=[], user_message="x", tools=[FIND],
                                                              execute=lambda n, a: {}, tenant_id=1)
    assert result.refused and result.stop_reason == stop


def _status_error(cls, code):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize("error", [
    anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
    anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
    _status_error(anthropic.RateLimitError, 429),
    _status_error(anthropic.InternalServerError, 500),
    _status_error(anthropic.BadRequestError, 400),
    _status_error(anthropic.AuthenticationError, 401),
])
def test_api_failures_degrade_the_turn_and_are_logged(error):
    logs = []
    with pytest.raises(BrainUnavailable):
        _large(FakeAnthropic(error), logs).run_tools(system="s", history=[], user_message="x", tools=[FIND],
                                                     execute=lambda n, a: {}, tenant_id=1)
    assert len(logs) == 1 and logs[0].success is False and logs[0].error_message


def test_history_is_plain_text_and_fallbacks_can_be_switched_off():
    client = FakeAnthropic(_response("end_turn", _text("done")))
    _large(client, fallbacks=False).run_tools(
        system="s", tools=[], execute=lambda n, a: {}, tenant_id=1, user_message="and now?",
        history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
                 {"role": "event", "content": "Mission started"}])
    sent = client.requests[0]
    assert sent["messages"] == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
                                {"role": "user", "content": "and now?"}]
    assert "betas" not in sent and "fallbacks" not in sent and "tools" not in sent


def test_large_extract_json_uses_structured_output():
    client = FakeAnthropic(_response("end_turn", _text('{"intent": "my_tasks", "query": ""}')))
    data = _large(client).extract_json(purpose="intent", system="s", user="what's on my plate",
                                       schema={"type": "object", "required": ["intent", "query"],
                                               "properties": {"intent": {"type": "string"}, "query": {"type": "string"}}},
                                       tenant_id=1)
    assert data == {"intent": "my_tasks", "query": ""}
    assert client.requests[0]["output_config"]["format"]["type"] == "json_schema"
    with pytest.raises(BrainUnavailable):
        _large(FakeAnthropic(_response("refusal"))).extract_json(purpose="p", system="s", user="u",
                                                                  schema={"type": "object"}, tenant_id=1)


# ---------------------------------------------------------------------------- small brain

def test_small_brain_posts_an_ollama_chat_with_a_json_schema_format():
    sent = []
    schema = {"type": "object", "required": ["intent", "query"],
              "properties": {"intent": {"type": "string"}, "query": {"type": "string"}}}
    data = _small([_small_reply('{"intent": "my_tasks", "query": ""}')], sent=sent).extract_json(
        purpose="intent", system="s", user="u", schema=schema, tenant_id=1)
    assert data["intent"] == "my_tasks"
    assert sent[0]["url"] == "http://ollama:11434/api/chat" and sent[0]["timeout"] == 15
    body = sent[0]["json"]
    assert body["format"] == schema and body["stream"] is False and body["options"] == {"temperature": 0}


@pytest.mark.parametrize("reply", [_small_reply("not json"), _small_reply('{"intent": "x"}'), _small_reply("[1]"),
                                   _small_reply("", 200), _small_reply("{}", 503), None])
def test_small_brain_bad_output_is_unavailable(reply):
    import requests

    reply = reply or requests.ConnectionError("refused")
    logs = []
    with pytest.raises(BrainUnavailable):
        _small([reply], logs).extract_json(purpose="intent", system="s", user="u", tenant_id=1,
                                           schema={"type": "object", "required": ["intent", "query"]})
    assert logs[0].success is False


def test_router_falls_back_from_small_to_large_then_to_nothing():
    good_large = _large(FakeAnthropic(_response("end_turn", _text('{"intent": "bench_availability", "query": "kafka"}'))))
    brains = Brains(small=_small([_small_reply("garbage")]), large=good_large)
    assert route_intent(brains, "spare kafka person?", intents=INTENTS, tenant_id=1) == \
        {"intent": "bench_availability", "query": "kafka", "routed_by": "large"}
    assert route_intent(Brains(), "anything", intents=INTENTS, tenant_id=1) is None
    unknown = Brains(small=_small([_small_reply('{"intent": "unknown", "query": ""}')]))
    assert route_intent(unknown, "write a poem", intents=INTENTS, tenant_id=1) is None


# ---------------------------------------------------------------------------- tiers

@pytest.mark.parametrize("small,large,status,offline", [
    (True, True, "full", []),
    (False, True, "large_only", ["parsing model is offline because FLASH_SMALL_LLM_BASE_URL is not set"]),
    (True, False, "small_only", ["planning brain (Claude) is offline because ANTHROPIC_API_KEY is not set"]),
    (False, False, "rules", ["ANTHROPIC_API_KEY is not set", "FLASH_SMALL_LLM_BASE_URL is not set",
                             "ask for each detail explicitly"]),
])
def test_brain_status_and_offline_note_for_every_combination(monkeypatch, small, large, status, offline):
    monkeypatch.setattr(settings, "FLASH_AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test" if large else "")
    monkeypatch.setattr(settings, "FLASH_SMALL_LLM_BASE_URL", "http://ollama:11434" if small else "")
    monkeypatch.setattr(settings, "FLASH_SMALL_LLM_MODEL", "qwen")
    brains = llm.get_brains()
    assert brains.status() == status
    note = brains.offline_note()
    if not offline:
        assert note is None
    else:
        assert note.startswith("Heads-up: ") and all(part in note for part in offline)


def test_kill_switch_means_rules_only(monkeypatch):
    monkeypatch.setattr(settings, "FLASH_AGENT_ENABLED", False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    brains = llm.get_brains()
    assert brains.status() == "rules" and "FLASH_AGENT_ENABLED is false" in brains.offline_note()
    assert Brains(large=object()).without("large", "Claude timed out").status() == "rules"


# ---------------------------------------------------------------------------- logging

def test_every_call_logs_one_row_without_committing_the_callers_session(db, monkeypatch):
    from app.models.prompt_execution_log import PromptExecutionLog
    from app.services import prompt_framework_service

    written = []
    monkeypatch.setattr(prompt_framework_service, "_write_log", written.append)
    monkeypatch.setattr(db, "commit", lambda: pytest.fail("the caller's session must not be committed"))
    brain = LargeBrain(client=FakeAnthropic(_response("end_turn", _text(f"Mail {EMAIL}"))), model="claude-opus-5-5",
                       effort="medium", max_tokens=16000, max_tool_rounds=8, fallbacks=True)
    brain.run_tools(system="s", history=[], user_message="x", tools=[], execute=lambda n, a: {}, tenant_id=7)
    assert len(written) == 1 and not db.new
    row = written[0]
    assert isinstance(row, PromptExecutionLog) and row.tenant_id == "7" and row.prompt_type == "flash_agent"
    assert row.model == "claude-opus-5-5" and (row.input_tokens, row.output_tokens) == (11, 7) and row.success
    assert EMAIL not in row.response_preview


# ---------------------------------------------------------------------------- the data rule

SENSITIVE_RESULT = {
    "text": f"Priya S (Ruby on Rails, 6 years). Call {PHONE} or mail {EMAIL}. Expects {SALARY}; "
            f"current salary 150000; bill rate 85/hr; margin 32%; CV at https://drive.example.com/cv.pdf",
    "results": [{"name": "Priya S", "skills": ["Ruby on Rails"], "experience_months": 72,
                 "email": EMAIL, "phone": PHONE, "salary": 150000, "bill_rate": "85/hr",
                 "resume_url": "https://drive.example.com/resume.pdf", "documents": [{"content": "Aadhaar 1234"}]}],
}


def _assert_clean(sent):
    blob = json.dumps(sent)
    leaked = [s for s in SECRETS if s in blob]
    assert not leaked, f"reached the model: {leaked}"
    return blob


def test_contact_details_and_pay_never_reach_claude():
    client = FakeAnthropic(_response("tool_use", _tool("t1", "find_candidates", {"query": "rails"})),
                           _response("end_turn", _text("Found Priya S.")))
    _large(client).run_tools(
        system="s", tools=[FIND], execute=lambda n, a: SENSITIVE_RESULT, tenant_id=1,
        history=[{"role": "assistant", "content": f"Reach her at {EMAIL} / {PHONE}"}],
        user_message=f"find rails devs like the one at {EMAIL}, budget 150000")
    blob = _assert_clean(client.requests)
    assert "Priya S" in blob and "Ruby on Rails" in blob and "72" in blob  # work data still flows


def test_contact_details_and_pay_never_reach_the_small_model():
    sent = []
    brain = _small([_small_reply('{"intent": "my_tasks", "query": ""}')], sent=sent)
    route_intent(Brains(small=brain), f"what about {EMAIL} at {PHONE}, salary {SALARY}?", intents=INTENTS,
                 history=[{"question": "status of Priya", "reply": SENSITIVE_RESULT["text"]}], tenant_id=1)
    blob = _assert_clean(sent)
    assert "Priya" in blob


def test_redaction_keeps_work_data_and_drops_unknown_keys():
    clean = redact_payload(SENSITIVE_RESULT)
    person = clean["results"][0]
    assert person == {"name": "Priya S", "skills": ["Ruby on Rails"], "experience_months": 72}
    assert "[phone removed]" in clean["text"] and "[email removed]" in clean["text"]
    assert redact_text("JOB-1b9d6bcd-bbfd-11ee-8c90-0242ac120002 on 2026-10-21 10:00, L1 score 80") == \
        "JOB-1b9d6bcd-bbfd-11ee-8c90-0242ac120002 on 2026-10-21 10:00, L1 score 80"
    assert redact_text("revenue $1,200,000 and 12k INR") .count("[amount removed]") == 2
