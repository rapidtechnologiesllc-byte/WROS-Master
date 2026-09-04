from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import logging

from app.data.job_description_templates import JOB_DESCRIPTION_TEMPLATES
from app.tools.llm_provider import get_llm

load_dotenv()
logger = logging.getLogger(__name__)

# Define the state structure
class JobDescriptionState(TypedDict):
    """State for job description generation workflow"""
    job_title: str
    job_description_oneliner: str
    experience: str
    location: str
    generated_description: str
    skills_needed: List[str]

def generate_description_node(state: JobDescriptionState) -> JobDescriptionState:
    """
    Node to generate a comprehensive job description based on input parameters.
    Falls back to template if LLM fails.
    """
    try:
        llm, provider = get_llm()
        prompt = f"""
You are a professional job description writer. Create a comprehensive job description based on:
- Title: {state['job_title']}
- Summary: {state['job_description_oneliner']}
- Experience Level: {state['experience']}
- Location: {state['location']}

Generate a professional, detailed job description that:
1. Starts with an engaging summary
2. Lists key responsibilities (5-7 bullets)
3. Lists required qualifications (technical + soft skills)
4. Mentions company benefits or growth opportunities
5. Ends with application instructions

Keep tone professional but friendly."""
        result = llm.invoke(prompt)
        state['generated_description'] = result.content
        logger.info(f"Job description generated using {provider.value}")
    except Exception as e:
        logger.error(f"Failed to generate job description: {e}. Using template fallback.")
        # Return a professional template instead of error message
        state['generated_description'] = f"""Overview:
{state['job_description_oneliner']}

Roles & Responsibilities:
- Lead technical initiatives and contribute to team success
- Collaborate with cross-functional teams to deliver solutions
- Participate in code reviews and knowledge sharing
- Drive quality and best practices

Qualifications:
- {state['experience']} years of professional experience
- Strong problem-solving and communication skills
- Experience in building scalable solutions
- Located in or willing to work in {state['location']}"""

    return state

def extract_skills_node(state: JobDescriptionState) -> JobDescriptionState:
    """
    Node to extract required skills from generated description.
    """
    try:
        llm, provider = get_llm()
        prompt = f"""
From this job description, extract the top 10 required skills as a simple comma-separated list.

Job Description:
{state['generated_description']}

Return ONLY the skills, comma-separated, nothing else."""
        result = llm.invoke(prompt)
        skills_text = result.content.strip()
        state['skills_needed'] = [s.strip() for s in skills_text.split(',')]
        logger.info(f"Skills extracted using {provider.value}: {len(state['skills_needed'])} skills")
    except Exception as e:
        logger.error(f"Failed to extract skills: {e}")
        state['skills_needed'] = []
    
    return state

def generate_job_description_with_state(
    job_title: str,
    job_description_oneliner: str,
    experience: str,
    location: str
) -> dict:
    """
    Main entry point - generates job description using workflow.
    Returns dict with generated_description and skills_needed.
    """
    graph = StateGraph(JobDescriptionState)
    graph.add_node("generate", generate_description_node)
    graph.add_node("extract_skills", extract_skills_node)
    graph.add_edge("generate", "extract_skills")
    graph.add_edge("extract_skills", END)
    graph.set_entry_point("generate")

    runnable = graph.compile()

    result = runnable.invoke({
        "job_title": job_title,
        "job_description_oneliner": job_description_oneliner,
        "experience": experience,
        "location": location,
        "generated_description": "",
        "skills_needed": []
    })

    return {
        "generated_description": result.get("generated_description", ""),
        "skills_needed": result.get("skills_needed", [])
    }
