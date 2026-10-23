"""Flash's language models (CEO 2026-10-15: hybrid).

- LargeBrain: Claude through the official `anthropic` SDK -- planning and tool use (a manual
  tool-use loop: strict tools, all tool results of a round in one user message, errors returned
  as is_error) and JSON extraction (output_config.format json_schema).
- SmallBrain: a self-hosted Ollama-compatible model (POST {base}/api/chat with a JSON-schema
  `format`) -- parsing and classification.

Either may be missing; `Brains.status()` says which tier Flash runs at ("full", "large_only",
"small_only", "rules") and `offline_note()` names what is offline and which setting turns it on.
A model that fails during a call raises BrainUnavailable and the caller degrades to the next tier.

Data rule: everything sent to a model -- the user's words, earlier turns, tool results -- passes
through flash_brain.redaction inside these classes, so no caller can send contact details, pay,
documents or finance figures. Every call (success or failure) writes one PromptExecutionLog row
through its own session (never the caller's).
"""
import json
import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Sequence

import jsonschema
import requests

from app.core.config import settings
from app.services.flash_brain.redaction import redact_payload, redact_text

logger = logging.getLogger(__name__)

# Server-side refusal fallback ("default" picks the fallback model by refusal category)
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PREVIEW_CHARS = 200


class BrainUnavailable(RuntimeError):
    """The model could not give a usable answer (offline, timeout, refusal, bad output)."""


@dataclass(frozen=True)
class ToolDefinition:
    """What the large model is told about a tool (FlashTool carries the same three fields)."""
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolLoopResult:
    text: str = ""
    trace: List[Dict[str, Any]] = field(default_factory=list)  # {"name", "args", "result" | "error"}
    refused: bool = False
    stop_reason: Optional[str] = None
    rounds: int = 0


def log_llm_call(*, tenant_id, prompt_type: str, model: str, input_tokens: Optional[int],
                 output_tokens: Optional[int], latency_ms: int, preview: Optional[str], success: bool,
                 error: Optional[str] = None, writer: Optional[Callable] = None) -> None:
    """One PromptExecutionLog row per model call, written through its own session (default) so it
    never commits the caller's work. Tests pass `writer` to keep the row in their transaction."""
    from app.models.prompt_execution_log import PromptExecutionLog
    from app.services.prompt_framework_service import _write_log

    (writer or _write_log)(PromptExecutionLog(
        tenant_id=str(tenant_id), candidate_id=None, prompt_type=prompt_type, template_version="flash-v1",
        input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms,
        response_preview=(redact_text(preview)[:PREVIEW_CHARS] if preview else None), model=model,
        success=success, error_message=error))


def _check_required(data: Any, schema: dict, who: str) -> dict:
    if not isinstance(data, dict):
        raise BrainUnavailable(f"{who} returned {type(data).__name__}, not a JSON object")
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise BrainUnavailable(f"{who} returned JSON that does not match the schema: {exc.message}") from exc
    return data


class SmallBrain:
    """Ollama-compatible chat model used for parsing and classification."""

    def __init__(self, *, base_url: str, model: str, timeout_s: float, log_writer: Optional[Callable] = None,
                 post: Callable = requests.post):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.log_writer = log_writer
        self._post = post

    def extract_json(self, *, purpose: str, system: str, user: str, schema: dict, tenant_id) -> dict:
        body = {"model": self.model, "stream": False, "format": schema, "options": {"temperature": 0},
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": redact_text(user)}]}
        start = time.monotonic()
        content, error = None, None
        try:
            response = self._post(f"{self.base_url}/api/chat", json=body, timeout=self.timeout_s)
            if response.status_code != 200:
                raise BrainUnavailable(f"small model answered HTTP {response.status_code}")
            content = (response.json().get("message") or {}).get("content")
            if not content:
                raise BrainUnavailable("small model returned no content")
            try:
                data = json.loads(content)
            except ValueError as exc:
                raise BrainUnavailable(f"small model returned invalid JSON: {exc}") from exc
            return _check_required(data, schema, "small model")
        except requests.RequestException as exc:
            error = f"small model unreachable: {exc}"
            raise BrainUnavailable(error) from exc
        except BrainUnavailable as exc:
            error = str(exc)
            raise
        finally:
            log_llm_call(tenant_id=tenant_id, prompt_type=f"flash_{purpose}", model=self.model,
                         input_tokens=None, output_tokens=None,
                         latency_ms=int((time.monotonic() - start) * 1000), preview=content,
                         success=error is None, error=error, writer=self.log_writer)


class LargeBrain:
    """Claude via the official `anthropic` SDK (Messages API)."""

    def __init__(self, *, client, model: str, effort: str, max_tokens: int, max_tool_rounds: int,
                 fallbacks: bool, log_writer: Optional[Callable] = None):
        self.client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.max_tool_rounds = max_tool_rounds
        self.fallbacks = fallbacks
        self.log_writer = log_writer

    # ------------------------------------------------------------------ one request
    def _create(self, *, purpose: str, tenant_id, system: str, messages: list, tools: Optional[list] = None,
                output_format: Optional[dict] = None, tool_choice: Optional[dict] = None):
        import anthropic

        output_config: Dict[str, Any] = {"effort": self.effort}
        if output_format is not None:
            output_config["format"] = output_format
        params: Dict[str, Any] = dict(
            model=self.model, max_tokens=self.max_tokens, messages=messages, output_config=output_config,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}])
        if tools:
            params["tools"] = tools
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        start = time.monotonic()
        response, error = None, None
        try:
            if self.fallbacks:
                response = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
            else:
                response = self.client.messages.create(**params)
            return response
        except anthropic.BadRequestError as exc:
            error = f"Claude rejected the request (400): {exc.message}"
            logger.error(f"[FlashBrain] {error}", exc_info=True)
            raise BrainUnavailable(error) from exc
        except anthropic.RateLimitError as exc:
            error = "Claude is rate limited"
            raise BrainUnavailable(error) from exc
        except anthropic.APIStatusError as exc:
            error = f"Claude answered HTTP {exc.status_code}"
            if exc.status_code < 500:
                logger.error(f"[FlashBrain] {error}: {exc.message}", exc_info=True)
            raise BrainUnavailable(error) from exc
        except anthropic.APITimeoutError as exc:
            error = "Claude timed out"
            raise BrainUnavailable(error) from exc
        except anthropic.APIConnectionError as exc:
            error = "Claude is unreachable"
            raise BrainUnavailable(error) from exc
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            usage = getattr(response, "usage", None)
            stop = getattr(response, "stop_reason", None)
            if error is None and stop in ("refusal", "max_tokens"):
                error = f"stop_reason={stop}"
            log_llm_call(tenant_id=tenant_id, prompt_type=f"flash_{purpose}", model=self.model,
                         input_tokens=getattr(usage, "input_tokens", None),
                         output_tokens=getattr(usage, "output_tokens", None),
                         latency_ms=int((time.monotonic() - start) * 1000),
                         preview=_text_of(response) if response is not None else None,
                         success=error is None, error=error, writer=self.log_writer)

    # ------------------------------------------------------------------ JSON extraction
    def extract_json(self, *, purpose: str, system: str, user: str, schema: dict, tenant_id) -> dict:
        response = self._create(purpose=purpose, tenant_id=tenant_id, system=system,
                                messages=[{"role": "user", "content": redact_text(user)}],
                                output_format={"type": "json_schema", "schema": schema})
        if response.stop_reason != "end_turn":
            raise BrainUnavailable(f"Claude stopped with {response.stop_reason}")
        try:
            data = json.loads(_text_of(response))
        except ValueError as exc:
            raise BrainUnavailable(f"Claude returned invalid JSON: {exc}") from exc
        return _check_required(data, schema, "Claude")

    # ------------------------------------------------------------------ tool loop
    def run_tools(self, *, system: str, history: Sequence[dict], user_message: str, tools: Sequence,
                  execute: Callable[[str, dict], dict], tenant_id, purpose: str = "agent") -> ToolLoopResult:
        """Manual tool-use loop. `history` is plain text turns ({"role": "user"|"assistant",
        "content": str}) -- stored tool and thinking blocks are never replayed, so history stays
        append-only. Within this turn the full assistant content (thinking included) is sent back.
        A refusal or max_tokens returns ToolLoopResult(refused=True): the caller falls back to rules."""
        definitions = [{"name": t.name, "description": t.description, "input_schema": t.input_schema, "strict": True}
                       for t in tools]
        schemas = {t.name: t.input_schema for t in tools}
        messages: List[dict] = [{"role": turn["role"], "content": redact_text(turn["content"])}
                                for turn in history if turn.get("content") and turn.get("role") in ("user", "assistant")]
        messages.append({"role": "user", "content": redact_text(user_message)})
        result = ToolLoopResult()
        while True:
            last_round = result.rounds >= self.max_tool_rounds
            response = self._create(purpose=purpose, tenant_id=tenant_id, system=system, messages=messages,
                                    tools=definitions or None,
                                    tool_choice={"type": "none"} if (last_round and definitions) else None)
            result.stop_reason = response.stop_reason
            if response.stop_reason in ("refusal", "max_tokens"):
                result.refused = True
                return result
            if response.stop_reason not in ("tool_use", "pause_turn"):
                result.text = _text_of(response)
                return result
            if last_round:  # the model was told to stop calling tools and did not
                result.refused = True
                return result
            result.rounds += 1
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [self._run_one(block, schemas, execute, result)
                            for block in response.content if block.type == "tool_use"]
            messages.append({"role": "user", "content": tool_results})

    @staticmethod
    def _run_one(block, schemas: dict, execute: Callable, result: ToolLoopResult) -> dict:
        args = block.input
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = None
        try:
            if block.name not in schemas:
                raise ValueError(f"unknown tool {block.name}")
            if not isinstance(args, dict):
                raise ValueError("tool input is not a JSON object")
            jsonschema.validate(args, schemas[block.name])
        except (ValueError, jsonschema.ValidationError) as exc:
            message = getattr(exc, "message", None) or str(exc)
            result.trace.append({"name": block.name, "args": args, "error": message})
            return {"type": "tool_result", "tool_use_id": block.id, "is_error": True, "content": f"Invalid input: {message}"}
        outcome = execute(block.name, args)
        if not isinstance(outcome, dict):
            raise TypeError(f"tool {block.name} returned {type(outcome).__name__}, not a dict")
        result.trace.append({"name": block.name, "args": args, **({"error": outcome["error"]} if "error" in outcome
                                                                     else {"result": outcome})})
        visible = json.dumps(redact_payload(outcome), default=str)
        return {"type": "tool_result", "tool_use_id": block.id, "content": visible,
                **({"is_error": True} if "error" in outcome else {})}


def _text_of(response) -> str:
    return "".join(getattr(block, "text", "") for block in (getattr(response, "content", None) or [])
                   if getattr(block, "type", None) == "text").strip()


# ---------------------------------------------------------------------- tiers

@dataclass(frozen=True)
class Brains:
    small: Optional[SmallBrain] = None
    large: Optional[LargeBrain] = None
    small_offline_reason: Optional[str] = None  # why `small` is None, naming the setting
    large_offline_reason: Optional[str] = None

    def status(self) -> str:
        if self.small and self.large:
            return "full"
        if self.large:
            return "large_only"
        if self.small:
            return "small_only"
        return "rules"

    def offline_note(self) -> Optional[str]:
        parts = []
        if self.large is None:
            parts.append(f"my planning brain (Claude) is offline because {self.large_offline_reason or 'it is not configured'}")
        if self.small is None:
            parts.append(f"my parsing model is offline because {self.small_offline_reason or 'it is not configured'}")
        if not parts:
            return None
        tail = " I'll ask for each detail explicitly." if self.large is None else ""
        return "Heads-up: " + "; ".join(parts) + "." + tail

    def without(self, which: str, reason: str) -> "Brains":
        """The same tiers with one brain taken offline for the rest of the turn (it just failed)."""
        if which == "large":
            return replace(self, large=None, large_offline_reason=reason)
        return replace(self, small=None, small_offline_reason=reason)


_clients: Dict[tuple, Any] = {}


def _anthropic_client(api_key: str, timeout_s: float):
    import anthropic

    key = (api_key, timeout_s)
    if key not in _clients:
        _clients[key] = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=1)
    return _clients[key]


def get_brains() -> Brains:
    """The configured tiers (FastAPI dependency and the default for services; tests override)."""
    if not settings.FLASH_AGENT_ENABLED:
        reason = "FLASH_AGENT_ENABLED is false"
        return Brains(small_offline_reason=reason, large_offline_reason=reason)
    large, large_reason = None, None
    if not settings.ANTHROPIC_API_KEY:
        large_reason = "ANTHROPIC_API_KEY is not set"
    elif not settings.FLASH_LARGE_LLM_MODEL:
        large_reason = "FLASH_LARGE_LLM_MODEL is not set"
    else:
        large = LargeBrain(client=_anthropic_client(settings.ANTHROPIC_API_KEY, settings.FLASH_LARGE_LLM_TIMEOUT_S),
                           model=settings.FLASH_LARGE_LLM_MODEL, effort=settings.FLASH_LARGE_LLM_EFFORT,
                           max_tokens=settings.FLASH_LARGE_LLM_MAX_TOKENS,
                           max_tool_rounds=settings.FLASH_LARGE_LLM_MAX_TOOL_ROUNDS,
                           fallbacks=settings.FLASH_LARGE_LLM_FALLBACKS_ENABLED)
    small, small_reason = None, None
    if not settings.FLASH_SMALL_LLM_BASE_URL:
        small_reason = "FLASH_SMALL_LLM_BASE_URL is not set"
    elif not settings.FLASH_SMALL_LLM_MODEL:
        small_reason = "FLASH_SMALL_LLM_MODEL is not set"
    else:
        small = SmallBrain(base_url=settings.FLASH_SMALL_LLM_BASE_URL, model=settings.FLASH_SMALL_LLM_MODEL,
                           timeout_s=settings.FLASH_SMALL_LLM_TIMEOUT_S)
    return Brains(small=small, large=large, small_offline_reason=small_reason, large_offline_reason=large_reason)
