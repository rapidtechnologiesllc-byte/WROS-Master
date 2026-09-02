"""
import logging
S-031/HRMS-0431 -- AI Prompt Framework.

Foundational story, same posture as S-021/S-024 for their own
consumers: HRMS-0432 Context Builder (this story's own "designed
together" dependency) and HRMS-0434 AI Response Generation don't exist
as separately-named things in this codebase. Their real equivalent
already exists and predates this story --
thunder_service.build_candidate_context()/generate_thunder_reply_with_fallback()
already do candidate-context assembly and LLM calling informally, for
WhatsApp/web_chat/email replies. This framework is NOT retrofitted
into those already-shipped, already-tested call sites this round --
that would mean touching ~7 existing services (thunder_service,
ai_conversation_service, facts_extraction_service,
conversation_summary_service, qualification_engine_service,
response_parser_service, resume_parsing_service), each with its own
regression suite, this late before launch. Built here as a real,
complete, standalone module ready for that migration as a deliberate
future decision, not made unilaterally now.

Real architecture:
- LLM is Gemini (GEMINI_API_KEY), not the spec's Anthropic
  claude-sonnet-4-6 -- same adaptation every LLM-calling story this
  round has made.
- {{thunder_name}} (BR-04) is populated from
  ai_conversation_service.resolve_thunder_config() (S-011's real
  per-tenant Thunder identity), never hardcoded.
- {{candidate_summary}}/{{known_facts}} come from
  candidate_memory_service.get_memory() (S-021), {{missing_fields}}
  from ai_conversation_service.get_missing_fields() -- both already
  real and tested.
- prompt_execution_log is a genuinely new table (see its model
  docstring) -- BR-03's "every call logged, no exceptions" is enforced
  by call_llm() always writing a row, success or failure, before
  returning or raising.
"""
import os
import re
import time
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.constants.prompt_templates import PROMPT_TEMPLATES
from app.core.logging import logger
from app.models.prompt_execution_log import PromptExecutionLog

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_MODEL_NAME = "gemini-2.0-flash"
RETRY_DELAY_SECONDS = 3

logger = logging.getLogger(__name__)

class UnknownPromptType(Exception):
    pass


class LLMCallFailedError(Exception):
    pass


def _format_known_facts(facts: List[Dict]) -> str:
    if not facts:
        return "(none yet)"
    return ", ".join(f"{f.get('key')}={f.get('value')}" for f in facts)


def _format_conversation_history(messages: List[Dict], limit: int = 10) -> str:
    if not messages:
        return "(no messages yet)"
    recent = messages[-limit:]
    lines = []
    for m in recent:
        sender = m.get("sender") or m.get("sender_type") or "Unknown"
        body = m.get("body") or m.get("message_body") or ""
        lines.append(f"[{sender}]: {body}")
    return "\n".join(lines)


def _format_missing_fields(missing_fields: List[Dict]) -> str:
    if not missing_fields:
        return "(none -- profile complete)"
    return ", ".join(m.get("label", m.get("field", "")) for m in missing_fields)


def _placeholder_values(candidate_context: Dict, additional_params: Optional[Dict]) -> Dict[str, str]:
    additional_params = additional_params or {}
    memory = candidate_context.get("memory") or {}
    return {
        "thunder_name": candidate_context.get("thunder_name") or "Thunder",
        "candidate_name": candidate_context.get("name") or "there",
        "candidate_summary": memory.get("summary") or "",
        "known_facts": _format_known_facts(memory.get("facts") or []),
        "conversation_history": _format_conversation_history(candidate_context.get("recent_messages") or []),
        "next_question": additional_params.get("question", ""),
        "missing_fields": _format_missing_fields(candidate_context.get("missing_fields") or []),
    }


def build_prompt(prompt_type: str, candidate_context: Dict, additional_params: Optional[Dict] = None) -> Dict:
    """
    Step 2. Returns {system_prompt, user_prompt, prompt_type,
    template_version, max_tokens, temperature, built_at}. Logs a
    warning (PROMPT_MISSING_CONTEXT-equivalent) for any
    required_context_field missing from candidate_context, but still
    builds with whatever is available -- never blocks Thunder from
    responding over a missing optional field.
    """
    template = PROMPT_TEMPLATES.get(prompt_type)
    if template is None:
        raise UnknownPromptType(f"No prompt template registered for prompt_type={prompt_type!r}")

    for field in template["required_context_fields"]:
        if not candidate_context.get(field):
            logger.warning(f"[PromptFramework] PROMPT_MISSING_CONTEXT: required field {field!r} missing for prompt_type={prompt_type!r}")

    values = _placeholder_values(candidate_context, additional_params)

    def _replace(text: str) -> str:
        for key, value in values.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text

    system_prompt = _replace(template["system_prompt"])
    user_prompt = _replace(template["user_prompt_template"])

    from datetime import datetime
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_type": prompt_type,
        "template_version": template["version"],
        "max_tokens": template["max_tokens"],
        "temperature": template["temperature"],
        "built_at": datetime.utcnow(),
    }


def _default_llm_call(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        },
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


def call_llm(
    db: Session,
    tenant_id: str,
    candidate_id: Optional[str],
    prompt_type: str,
    template_version: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    *,
    llm_call: Optional[Callable[[str, str, int, float], str]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> str:
    """
    Step 3. BR-03: always logs, success or failure. Retries once after
    RETRY_DELAY_SECONDS on failure; raises LLMCallFailedError if both
    attempts fail. max_tokens is never overridden upward by a caller --
    build_prompt() is the only source of it, this function just enforces
    the value it's given.
    """
    last_error: Optional[Exception] = None
    for attempt in range(2):
        start = time.monotonic()
        try:
            if llm_call is not None:
                response = llm_call(system_prompt, user_prompt, max_tokens, temperature)
            else:
                api_key = os.getenv("GEMINI_API_KEY", "")
                if not api_key:
                    raise RuntimeError("GEMINI_API_KEY not set")
                response = _default_llm_call(system_prompt, user_prompt, max_tokens, temperature, api_key)
            latency_ms = int((time.monotonic() - start) * 1000)

            db.add(PromptExecutionLog(
                tenant_id=tenant_id, candidate_id=candidate_id, prompt_type=prompt_type, template_version=template_version,
                input_tokens=len(system_prompt.split()) + len(user_prompt.split()), output_tokens=len(response.split()),
                latency_ms=latency_ms, response_preview=response[:200], model=GEMINI_MODEL_NAME, success=True,
            ))
            db.commit()
            return response
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            last_error = exc
            latency_ms = int((time.monotonic() - start) * 1000)
            db.add(PromptExecutionLog(
                tenant_id=tenant_id, candidate_id=candidate_id, prompt_type=prompt_type, template_version=template_version,
                input_tokens=None, output_tokens=None, latency_ms=latency_ms, response_preview=None,
                model=GEMINI_MODEL_NAME, success=False, error_message=str(exc),
            ))
            db.commit()
            logger.warning(f"[PromptFramework] callLLM attempt {attempt + 1} failed for prompt_type={prompt_type!r}: {exc}")
            if attempt == 0:
                sleep_fn(RETRY_DELAY_SECONDS)

    raise LLMCallFailedError(f"LLM call failed twice for prompt_type={prompt_type!r}: {last_error}")


def get_prompt_templates() -> List[Dict]:
    """Step 5's real GET /api/admin/prompt-templates data source."""
    return [
        {"id": t["id"], "prompt_type": t["prompt_type"], "version": t["version"], "max_tokens": t["max_tokens"], "temperature": t["temperature"]}
        for t in PROMPT_TEMPLATES.values()
    ]
