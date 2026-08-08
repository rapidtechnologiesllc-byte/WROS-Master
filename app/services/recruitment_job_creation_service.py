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
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-3-flash-preview")


class RecruitmentJobCreationAgent:
    """
    Recruitment agent for generating clarifying questions and complete job data.
    """

    def generate_clarifying_questions(self, one_liner: str) -> Dict:
        """
        Given a minimal job one-liner (e.g., "guidewire developer"),
        generate clarifying questions for missing pseudo-mandatory fields.

        Returns:
            {
                "questions": [
                    {
                        "field": "position_type",
                        "question": "Is this position Full-time or Contract?",
                        "options": ["Full time", "Contract"],
                        "required": True
                    },
                    ...
                ],
                "identified_title": "Guidewire Developer",
                "estimated_experience": "3-5 years"
            }
        """
        prompt = f"""
        A hiring manager just entered this minimal job requirement one-liner:
        "{one_liner}"

        Based on this, identify:
        1. The likely job title (without location or seniority modifiers)
        2. Estimated required experience level (e.g., "3-5 years")
        3. What additional information is needed to create a complete, high-quality job posting

        Generate 3-4 clarifying questions to ask the user. Each question should have:
        - A clear field name
        - A natural language question
        - Available options (if applicable)
        - Whether it's required (True/False)

        For Position Type, ask if Full-time or Contract.
        For Job Open Date, ask when to post (date picker).
        For Pay Range, ask salary/rate range.
        For Duration, ask if permanent or contract length.

        Respond in this exact JSON format:
        {{
            "job_title": "Guidewire Developer",
            "estimated_experience": "3-5 years",
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
                    "question": "When should we post this job?",
                    "options": null,
                    "required": true,
                    "type": "date"
                }},
                {{
                    "field": "pay_range",
                    "question": "What is the salary/rate range for this role?",
                    "options": null,
                    "required": true,
                    "type": "text"
                }},
                {{
                    "field": "contract_duration",
                    "question": "If contract, what is the expected duration?",
                    "options": ["3 months", "6 months", "12 months", "Permanent"],
                    "required": false,
                    "type": "select"
                }}
            ]
        }}
        """

        response = llm.invoke(prompt)
        if isinstance(response.content, str):
            content = response.content
        elif isinstance(response.content, list):
            content = ''.join(
                part['text'] if isinstance(part, dict) and 'text' in part else str(part)
                for part in response.content
            )
        else:
            content = str(response.content)

        # Parse JSON response
        import json
        try:
            # Extract JSON from response (may have markdown formatting)
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback structure
        return {
            "job_title": "Job Title",
            "estimated_experience": "Unknown",
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
                    "question": "When should we post this job?",
                    "options": None,
                    "required": True,
                    "type": "date"
                },
                {
                    "field": "pay_range",
                    "question": "What is the salary/rate range?",
                    "options": None,
                    "required": True,
                    "type": "text"
                }
            ]
        }

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
