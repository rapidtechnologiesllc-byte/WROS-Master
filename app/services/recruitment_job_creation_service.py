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

from typing import Dict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.0-flash")


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
            return None

    def _validate_response_structure(self, data: Dict) -> None:
        """Validate that the response has required fields."""
        required_keys = {"job_title", "estimated_experience", "questions"}
        if not required_keys.issubset(set(data.keys())):
            raise ValueError(f"Missing required keys: {required_keys - set(data.keys())}")

        if not isinstance(data["questions"], list) or len(data["questions"]) == 0:
            raise ValueError("questions must be a non-empty list")

        for q in data["questions"]:
            required_q_keys = {"field", "question", "required", "type"}
            if not required_q_keys.issubset(set(q.keys())):
                raise ValueError(f"Question missing required keys: {required_q_keys - set(q.keys())}")

    def generate_clarifying_questions(self, one_liner: str) -> Dict:
        """
        Given a minimal job one-liner (e.g., "guidewire developer"),
        generate clarifying questions for missing pseudo-mandatory fields.

        Returns:
            {
                "job_title": "Guidewire Developer",
                "estimated_experience": "3-5 years",
                "questions": [
                    {
                        "field": "position_type",
                        "question": "Is this position Full-time or Contract?",
                        "options": ["Full time", "Contract"],
                        "required": true,
                        "type": "select"
                    },
                    ...
                ]
            }
        """
        prompt = f"""You are a job creation assistant helping recruiters post positions. Analyze this job requirement:

Job One-liner: "{one_liner}"

Identify the job title (no location or seniority), and estimated experience level.
Then generate 4 clarifying questions for the recruiter to create a complete job posting.

CRITICAL: Respond ONLY with valid JSON, no other text. Start with {{ and end with }}.

{{
    "job_title": "<extracted job title, no location/level modifier>",
    "estimated_experience": "<e.g., 3-5 years>",
    "questions": [
        {{
            "field": "position_type",
            "question": "Is this a Full-time or Contract position?",
            "options": ["Full time", "Contract"],
            "required": true,
            "type": "select"
        }},
        {{
            "field": "job_open_date",
            "question": "When should this job be posted?",
            "options": null,
            "required": true,
            "type": "date"
        }},
        {{
            "field": "pay_range",
            "question": "What is the salary/rate range (e.g., 100k-150k or $45-55/hr)?",
            "options": null,
            "required": true,
            "type": "text"
        }},
        {{
            "field": "contract_duration",
            "question": "For contracts, what is the expected duration?",
            "options": ["3 months", "6 months", "12 months", "18 months", "Permanent"],
            "required": false,
            "type": "select"
        }}
    ]
}}

Do not include any explanation, markdown, or extra text. JSON only."""

        response = llm.invoke(prompt)
        content = self._extract_content(response)

        result = self._parse_json_response(content)
        if result:
            return result

        raise ValueError(f"Failed to generate valid questions from LLM response: {content[:200]}")

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

        # Use existing job description generator for complete JD
        result = generate_job_description_with_state(
            job_title="",  # Will be inferred
            job_description_oneliner=one_liner,
            experience="",  # Will be inferred
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
            "contract_duration": contract_duration
        }


def get_recruitment_job_agent() -> RecruitmentJobCreationAgent:
    """Factory function to get the Recruitment Job Creation Agent."""
    return RecruitmentJobCreationAgent()
