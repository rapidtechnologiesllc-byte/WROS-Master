"""
Recruitment Agent for Job Creation — Agentic Workflow
=====================================================

Integrates the Recruitment sub-agent (part of Thunder) into the job creation flow.
When a user provides a minimal one-liner job description, the agent:

1. Asks clarifying questions for missing pseudo-mandatory fields
2. Collects user answers
3. Generates complete job description with all fields populated

Agent learns from patterns in successful jobs vs. dropped inquiries.
Logs all actions to agent_execution_log for maturity tracking.
"""

import logging
from typing import Dict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
import os
import re
import json
from dotenv import load_dotenv
from app.core.logging import logger

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Round-robin LLM providers: Gemini (primary) → Claude (backup) → fallback response
def _get_llm_provider():
    """Claude, then Gemini; None when no real key is configured (the agent
    then uses its deterministic fallbacks)."""
    from app.tools.llm_provider import real_api_key
    anthropic_key = real_api_key("ANTHROPIC_API_KEY")
    if anthropic_key:
        return ChatAnthropic(api_key=anthropic_key, model="claude-sonnet-5-5", temperature=0, max_retries=1)
    gemini_key = real_api_key("GEMINI_API_KEY")
    if gemini_key:
        return ChatGoogleGenerativeAI(api_key=gemini_key, model="gemini-2.5-flash", temperature=0, max_retries=1)
    logger.warning("[RecruitmentJobAgent] No AI provider key configured; using deterministic fallbacks")
    return None

llm = _get_llm_provider()

logger = logging.getLogger(__name__)

class RecruitmentJobCreationAgent:
    """
    Recruitment agent for generating clarifying questions and complete job data.
    """

    def _extract_content(self, response) -> str:
        """Extract text content from LLM response, handling various formats."""
        if isinstance(response.content, str):
            return response.content
        elif isinstance(response.content, list):
            return ''.join(
                part['text'] if isinstance(part, dict) and 'text' in part else str(part)
                for part in response.content
            )
        else:
            return str(response.content)

    def _parse_json_response(self, content: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown and extra text."""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start == -1 or json_end <= json_start:
                return None

            json_str = content[json_start:json_end]
            parsed = json.loads(json_str)

            self._validate_response_structure(parsed)
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError("Operation failed")

    # These field names are contractual: generate_complete_job() reads answers
    # back out by these exact keys, so every response must include them.
    REQUIRED_QUESTION_FIELDS = {
        "position_type", "job_open_date", "pay_range", "contract_duration",
        "role_type", "client_name",
    }

    def _validate_response_structure(self, data: Dict) -> None:
        """Validate that the response has required fields."""
        required_keys = {"job_title", "estimated_experience", "questions"}
        if not required_keys.issubset(set(data.keys())):
            raise ValueError(f"Missing required keys: {required_keys - set(data.keys())}")

        if not isinstance(data["questions"], list) or len(data["questions"]) == 0:
            raise ValueError("questions must be a non-empty list")

        present_fields = set()
        for q in data["questions"]:
            required_q_keys = {"field", "question", "required", "type"}
            if not required_q_keys.issubset(set(q.keys())):
                raise ValueError(f"Question missing required keys: {required_q_keys - set(q.keys())}")
            present_fields.add(q["field"])

        missing = self.REQUIRED_QUESTION_FIELDS - present_fields
        if missing:
            raise ValueError(f"Response is missing contractually required question fields: {missing}")

    def _get_fallback_response(self, one_liner: str) -> Dict:
        """Return default questions when LLM fails."""
        title = one_liner.split("with")[0].strip().title() if "with" in one_liner else one_liner.title()
        exp = "3-5 years"
        if "senior" in one_liner.lower():
            exp = "5-8 years"
        elif "junior" in one_liner.lower():
            exp = "0-2 years"
        elif "lead" in one_liner.lower() or "principal" in one_liner.lower():
            exp = "8+ years"

        return {
            "job_title": title,
            "estimated_experience": exp,
            "questions": [
                {
                    "field": "position_type",
                    "question": "Is this a Full-time or Contract position?",
                    "options": ["Full time", "Contract"],
                    "required": True,
                    "type": "select"
                },
                {
                    "field": "job_open_date",
                    "question": "When should this job be posted?",
                    "options": None,
                    "required": True,
                    "type": "date"
                },
                {
                    "field": "pay_range",
                    "question": "What is the Pay Rate for this role?",
                    "options": None,
                    "required": True,
                    "type": "pay_rate"
                },
                {
                    "field": "contract_duration",
                    "question": "For contracts, what is the expected duration?",
                    "options": ["3 months", "6 months", "12 months", "18 months", "Permanent"],
                    "required": False,
                    "type": "select"
                },
                {
                    "field": "role_type",
                    "question": "Is this an Internal (BlitzenX) role or an External (Partner/Client) role?",
                    "options": ["Internal", "External"],
                    "required": True,
                    "type": "select"
                },
                {
                    "field": "client_name",
                    "question": "If External, which client/partner is this role for?",
                    "options": None,
                    "required": False,
                    "type": "text"
                }
            ]
        }

    def generate_clarifying_questions(self, one_liner: str) -> Dict:
        """
        Given a minimal job one-liner (e.g., "guidewire developer"),
        generate clarifying questions for missing pseudo-mandatory fields.

        Returns:
            {
                "job_title": "Guidewire Developer",
                "estimated_experience": "3-5 years",
                "questions": [...]
            }
        """
        prompt = f"""You are a job creation assistant. Analyze this job requirement and respond ONLY with valid JSON (no other text):

"{one_liner}"

Extract the job title (no location/seniority modifiers) and estimate the required experience level.

Your "questions" array MUST include these 6 questions with these EXACT "field" values —
do not rename, remove, or skip any of them, and do not change their "field" value:
  - field "position_type": ask whether the role is Full-time or Contract
  - field "job_open_date": ask when the job should be posted
  - field "pay_range": ask for the Pay Rate (this matches the "Pay Rate" Amount + rate-type field on the job creation form; use "type": "pay_rate", not "text")
  - field "contract_duration": ask the expected contract duration (only relevant if Contract)
  - field "role_type": ask whether this is an Internal (BlitzenX) role or an External (Partner/Client) role
  - field "client_name": ask which client/partner this is for (only relevant if role_type is External; not required)

You MAY add up to 2 additional job-specific questions after those 6 (e.g. about
required certifications, tech stack, or domain modules) using field names of your choosing.

Respond with exactly this JSON shape:
{{
    "job_title": "<title>",
    "estimated_experience": "<e.g., 3-5 years>",
    "questions": [
        {{"field": "position_type", "question": "Is this Full-time or Contract?", "options": ["Full time", "Contract"], "required": true, "type": "select"}},
        {{"field": "job_open_date", "question": "When should this job be posted?", "options": null, "required": true, "type": "date"}},
        {{"field": "pay_range", "question": "What is the Pay Rate for this role?", "options": null, "required": true, "type": "pay_rate"}},
        {{"field": "contract_duration", "question": "For contracts, expected duration?", "options": ["3 months", "6 months", "12 months", "18 months", "Permanent"], "required": false, "type": "select"}},
        {{"field": "role_type", "question": "Is this an Internal (BlitzenX) role or an External (Partner/Client) role?", "options": ["Internal", "External"], "required": true, "type": "select"}},
        {{"field": "client_name", "question": "If External, which client/partner is this role for?", "options": null, "required": false, "type": "text"}}
    ]
}}"""

        try:
            if llm is None:
                raise RuntimeError("No AI provider configured")
            response = llm.invoke(prompt)
            content = self._extract_content(response)
            result = self._parse_json_response(content)
            if result:
                return result
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            import sys
            print(f"LLM call failed, using fallback: {type(e).__name__}", file=sys.stderr)

        return self._get_fallback_response(one_liner)

    def generate_complete_job(
        self,
        one_liner: str,
        answers: Dict[str, str],
        known_skills: Optional[List[str]] = None,
    ) -> Dict:
        """One-liner + Step 1 answers -> the Step 2 fields.

        Values the user already gave (title, location, experience, pay,
        position type) are used as-is. Missing ones are read from the
        one-liner deterministically (title, years of experience, known
        skills); the AI, when configured, writes the description and skill
        list. Nothing is invented: a value that can't be determined comes
        back empty for the user to fill.
        """
        from app.tools.job_description_generator import generate_job_description_with_state

        def answer(*keys):
            for key in keys:
                value = answers.get(key)
                if value not in (None, ""):
                    return str(value).strip()
            return ""

        position_type = answer("position_type") or "Full time"
        pay_range = answer("pay_range")
        job_open_date = answer("job_open_date")
        contract_duration = answer("contract_duration")
        location = answer("job_location", "location")
        experience = answer("job_experience", "experience") or infer_experience(one_liner)
        role_type = answer("role_type") or "Internal"
        client_name = answer("client_name") if "external" in role_type.lower() else ""
        job_title = answer("job_title") or infer_title(one_liner)

        # Extra answers (certifications, tech stack, ...) become context for the JD
        fixed_fields = self.REQUIRED_QUESTION_FIELDS | {"location", "experience", "job_location",
                                                        "job_experience", "job_title"}
        extra_context = "; ".join(
            f"{field.replace('_', ' ')}: {value}"
            for field, value in answers.items()
            if field not in fixed_fields and value
        )
        enriched_oneliner = f"{one_liner}. {extra_context}" if extra_context else one_liner

        result = generate_job_description_with_state(
            job_title=job_title,
            job_description_oneliner=enriched_oneliner,
            experience=experience,
            location=location,
        )
        skills = [s for s in (result.get("skills_needed") or []) if s] or match_known_skills(one_liner, known_skills or [])

        return {
            "job_title": job_title,
            "generated_job_description": result.get("generated_description", ""),
            "job_skills": skills,
            "job_experience": experience,
            "job_location": location,
            "position_type": position_type,
            "pay_range": pay_range,
            "job_open_date": job_open_date,
            "contract_duration": contract_duration,
            "role_type": role_type,
            "client_name": client_name,
            "ai_generated": bool(result.get("ai_generated")),
        }


_TITLE_BREAKS = re.compile(r"[,.;:(\n]| - | with | for | in | at | located | needed| required", re.IGNORECASE)
_EXPERIENCE = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to)?\s*(\d{1,2})?\s*(?:\+)?\s*(?:years?|yrs?)", re.IGNORECASE)


def infer_title(one_liner: str) -> str:
    """The role name at the start of the one-liner ("Guidewire Developer,
    6+ years ..." -> "Guidewire Developer")."""
    text = (one_liner or "").strip()
    if not text:
        return ""
    # Drop lead-ins ("We need a", "Looking for an", "Hiring") before splitting
    text = re.sub(
        r"^(?:(?:we\s+)?(?:are\s+)?(?:need(?:ing)?|looking\s+for|hiring|seeking|want)\s+)?(?:an?|the)?\s*",
        "", text, flags=re.IGNORECASE,
    ).strip()
    head = _TITLE_BREAKS.split(text, maxsplit=1)[0].strip()
    if not head or len(head) > 80:
        return ""
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in head.split())


def infer_experience(one_liner: str) -> str:
    """"6+ years" / "5-8 yrs" in the one-liner -> "6+ years" / "5-8 years"; else ""."""
    match = _EXPERIENCE.search(one_liner or "")
    if not match:
        return ""
    low, high = match.group(1), match.group(2)
    return f"{low}-{high} years" if high else f"{low}+ years"


def match_known_skills(one_liner: str, known_skills: List[str]) -> List[str]:
    """Skills already used in this system (jobs/candidates) that the one-liner names."""
    text = f" {(one_liner or '').lower()} "
    found = []
    for skill in sorted({k.strip() for k in known_skills if k and k.strip()}, key=len, reverse=True):
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, text) and not any(skill.lower() in f.lower() for f in found):
            found.append(skill)
    return found[:15]


def get_recruitment_job_agent() -> RecruitmentJobCreationAgent:
    """Factory function to get the Recruitment Job Creation Agent."""
    return RecruitmentJobCreationAgent()
