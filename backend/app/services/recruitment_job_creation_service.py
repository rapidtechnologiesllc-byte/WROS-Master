"""
Recruitment Agent for Job Creation — Agentic Workflow
import logging
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
import json
from dotenv import load_dotenv
from app.core.logging import logger

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Round-robin LLM providers: Gemini (primary) → Claude (backup) → fallback response
def _get_llm_provider():
    """Get LLM provider with round-robin fallback: Gemini → Claude → fallback responses."""
    # Try Gemini first (primary) - skip if dummy key
    if GEMINI_API_KEY and GEMINI_API_KEY not in ["AIzaSyDummy_For_Local_Dev", ""]:
        try:
            return ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-3-flash-preview", temperature=0, max_retries=1)
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            print(f"Gemini provider failed: {e}, trying Claude...", flush=True)

    # Fall back to Claude (backup) - skip if dummy key
            if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY not in ["sk-ant-d01-dummy-for-local-dev", ""]:
                pass
        try:
            return ChatAnthropic(api_key=ANTHROPIC_API_KEY, model="claude-opus-4-1", temperature=0, max_retries=1)
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            print(f"Claude provider failed: {e}, using fallback responses...", flush=True)

    # If all real providers fail/unavailable, return a dummy LLM that will always fail
    # and trigger the _get_fallback_response() in the agent
            return ChatGoogleGenerativeAI(api_key="dummy", model="gemini-3-flash-preview", temperature=0, max_retries=1)

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
        answers: Dict[str, str]
    ) -> Dict:
        """
        Given one-liner + user answers to clarifying questions,
        generate complete job data with all fields populated.

        Args:
            one_liner: Original job description (e.g., "guidewire developer")
            answers: Dict of field -> user answer
                {
                    "position_type": "Full time",
                    "job_open_date": "2026-08-15",
                    "pay_range": "100k-150k",
                    "contract_duration": "Permanent"
                }

        Returns:
            {
                "job_title": "Guidewire Developer",
                "job_description": "Full professional JD",
                "job_skills": ["Skill1", "Skill2", ...],
                "job_experience": "3-5 years",
                "job_location": "Remote",
                "position_type": "Full time",
                "pay_range": "100k-150k",
                "job_open_date": "2026-08-15",
                "contract_duration": "Permanent"
            }
        """
        from app.tools.job_description_generator import generate_job_description_with_state

        # Extract key info from answers
        position_type = answers.get("position_type", "Full time")
        pay_range = answers.get("pay_range", "Not specified")
        job_open_date = answers.get("job_open_date", "")
        contract_duration = answers.get("contract_duration", "")
        location = answers.get("location", "Remote")
        experience = answers.get("experience", "")
        role_type = answers.get("role_type", "Internal")
        client_name = answers.get("client_name", "") if "external" in role_type.lower() else ""

        # Any answers beyond the fixed contractual fields (e.g. certifications,
        # tech stack, domain modules from the LLM's follow-up questions) get
        # folded into the one-liner so the JD generator has that context too —
        # otherwise those answers would be silently discarded.
        fixed_fields = self.REQUIRED_QUESTION_FIELDS | {"location", "experience"}
        extra_context = "; ".join(
            f"{field.replace('_', ' ')}: {value}"
            for field, value in answers.items()
            if field not in fixed_fields and value
        )
        enriched_oneliner = f"{one_liner}. {extra_context}" if extra_context else one_liner

        # Use existing job description generator for complete JD
        result = generate_job_description_with_state(
            job_title="",  # Will be inferred
            job_description_oneliner=enriched_oneliner,
            experience=experience,  # Will be inferred if not provided
            location=location
        )

        return {
            "job_title": result.get("job_title", "Job Title"),
            "generated_job_description": result.get("generated_description", ""),
            "job_skills": result.get("skills_needed", []),
            "job_experience": result.get("experience", "3-5 years"),
            "job_location": result.get("location", "Remote"),
            "position_type": position_type,
            "pay_range": pay_range,
            "job_open_date": job_open_date,
            "contract_duration": contract_duration,
            "role_type": role_type,
            "client_name": client_name
        }

def get_recruitment_job_agent() -> RecruitmentJobCreationAgent:
    """Factory function to get the Recruitment Job Creation Agent."""
    return RecruitmentJobCreationAgent()
