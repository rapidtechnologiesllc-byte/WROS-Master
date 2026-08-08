from langchain_google_genai import ChatGoogleGenerativeAI
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os

from app.data.job_description_templates import JOB_DESCRIPTION_TEMPLATES

# Load environment variables from .env file
load_dotenv()

# Initialize the LLM
# max_retries=1: fail fast instead of the default exponential backoff (which
# burns 30s+ and extra free-tier quota per call) so callers can fall back quickly.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-3-flash-preview", max_retries=1)


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
    
    Args:
        state: Current state containing job_title, job_description_oneliner, experience, location
        
    Returns:
        Updated state with generated_description
    """
    prompt = f"""
    Generate a comprehensive and professional job description based on the following information:
    
    Job Title: {state['job_title']}
    Brief Description: {state['job_description_oneliner']}
    Required Experience: {state['experience']}
    Location: {state['location']}
    
    Please create a detailed job description that includes:
    1. A compelling overview of the role
    2. Key responsibilities (5-7 bullet points)
    3. Required qualifications and experience
    4. Preferred qualifications (if applicable)
    5. What the candidate will achieve in this role
    
    Make it professional, engaging, and attractive to potential candidates.
    """
    
    response = llm.invoke(prompt)
    # Handle response.content being either a string or list (varies by model version)
    if isinstance(response.content, str):
        content = response.content
    elif isinstance(response.content, list):
        # Handle list of content parts (e.g., [{'text': '...'}, ...])
        content = ''.join(
            part['text'] if isinstance(part, dict) and 'text' in part else str(part)
            for part in response.content
        )
    else:
        content = str(response.content)
    state['generated_description'] = content
    
    return state


def extract_skills_node(state: JobDescriptionState) -> JobDescriptionState:
    """
    Node to extract required skills from the generated job description.

    Args:
        state: Current state containing generated_description

    Returns:
        Updated state with skills_needed list
    """
    prompt = f"""
    Analyze the following job description and extract a list of key technical and soft skills required for this role.

    Job Title: {state['job_title']}
    Job Description:
    {state['generated_description']}

    Please provide a concise list of 8-12 essential skills. Include both technical skills and soft skills.
    Format your response as a comma-separated list of skills only, without numbering or bullet points.
    Example: Python, JavaScript, Team Leadership, Communication, Problem Solving
    """

    response = llm.invoke(prompt)
    # Handle response.content being either a string or list (varies by model version)
    if isinstance(response.content, str):
        content = response.content
    elif isinstance(response.content, list):
        # Handle list of content parts (e.g., [{'text': '...'}, ...])
        content = ''.join(
            part['text'] if isinstance(part, dict) and 'text' in part else str(part)
            for part in response.content
        )
    else:
        content = str(response.content)
    # Parse the comma-separated skills into a list
    skills_text = content.strip()
    skills_list = [skill.strip() for skill in skills_text.split(',')]

    state['skills_needed'] = skills_list

    return state


def infer_metadata_node(state: JobDescriptionState) -> JobDescriptionState:
    """
    Node to infer job title and experience level from the one-liner when not provided.

    Args:
        state: Current state with generated_description

    Returns:
        Updated state with inferred job_title and experience
    """
    # Only infer if the values are empty
    if not state.get('job_title') or not state.get('experience'):
        prompt = f"""
        Based on this one-liner job description and the generated job description below, extract:
        1. The job title ONLY (without location, seniority level, or remote/on-site info). Examples: "Guidewire Developer", "Data Scientist", "Full Stack Engineer" (NOT "Remote Guidewire Developer" or "Senior Guidewire Developer")
        2. The experience level required in years (e.g., "3-5 years", "5+ years", "2 years", "Entry level")

        One-liner: {state['job_description_oneliner']}

        Generated Description:
        {state['generated_description']}

        Respond EXACTLY in this format with no extra text:
        JOB_TITLE: [title only, no location or seniority]
        EXPERIENCE: [years required]
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

        # Parse the response
        lines = content.strip().split('\n')
        for line in lines:
            if line.startswith('JOB_TITLE:') and not state.get('job_title'):
                title = line.replace('JOB_TITLE:', '').strip()
                # Clean up any remaining location/seniority keywords
                title = title.replace('Remote ', '').replace('On-site ', '').replace('Hybrid ', '').strip()
                state['job_title'] = title
            elif line.startswith('EXPERIENCE:') and not state.get('experience'):
                state['experience'] = line.replace('EXPERIENCE:', '').strip()

    return state


# Create the workflow graph
def create_job_description_workflow():
    """
    Creates and compiles the LangGraph workflow for job description generation.

    Returns:
        Compiled workflow graph
    """
    workflow = StateGraph(JobDescriptionState)

    # Add nodes to the graph
    workflow.add_node("generate_description", generate_description_node)
    workflow.add_node("extract_skills", extract_skills_node)
    workflow.add_node("infer_metadata", infer_metadata_node)

    # Define the flow
    workflow.set_entry_point("generate_description")
    workflow.add_edge("generate_description", "extract_skills")
    workflow.add_edge("extract_skills", "infer_metadata")
    workflow.add_edge("infer_metadata", END)

    # Compile the graph
    return workflow.compile()


def generate_job_description_with_state(
    job_title: str,
    job_description_oneliner: str,
    experience: str,
    location: str
) -> dict:
    """
    Main function to generate a complete job description with state management.
    
    Args:
        job_title: The title of the job position
        job_description_oneliner: A brief one-line description of the job
        experience: Required experience level (e.g., "3-5 years", "Entry level")
        location: Job location (e.g., "Remote", "New York, NY", "Hybrid - San Francisco")
        
    Returns:
        Dictionary containing:
            - job_title: Original job title
            - job_description_oneliner: Original brief description
            - experience: Required experience
            - location: Job location
            - generated_description: AI-generated comprehensive job description
            - skills_needed: List of extracted skills
    """
    # Initialize the state
    initial_state: JobDescriptionState = {
        "job_title": job_title,
        "job_description_oneliner": job_description_oneliner,
        "experience": experience,
        "location": location,
        "generated_description": "",
        "skills_needed": []
    }

    # Known-role templates take priority over the LLM entirely -- no quota
    # usage, no variance, and no dependency on Gemini being up. See
    # app/data/job_description_templates.py for how to add more roles.
    template = _find_template(job_title, job_description_oneliner)
    if template:
        return _apply_template(template, initial_state)

    # Create and run the workflow
    app = create_job_description_workflow()
    try:
        final_state = app.invoke(initial_state)
        return final_state
    except Exception:
        # LLM unavailable (quota exhausted, network, etc.) — degrade to a
        # usable draft rather than 500ing the whole job-creation flow.
        return _fallback_job_description(initial_state)


def _clean_title(raw: str) -> str:
    """Strip seniority/location modifiers and trailing experience clauses from a raw title guess."""
    import re
    title = re.split(r"\bwith\b|\d+[\s-]*(to|-)[\s-]*\d+\s*years?|\d+\+?\s*years?", raw, flags=re.IGNORECASE)[0]
    for word in ("Senior", "Junior", "Lead", "Principal", "Remote", "On-site", "Onsite", "Hybrid"):
        title = re.sub(rf"\b{word}\b", "", title, flags=re.IGNORECASE)
    return " ".join(title.split()).title() or raw.title()


def _find_template(job_title: str, job_description_oneliner: str):
    """Look up a known-role template by normalized title. See job_description_templates.py."""
    candidates = [job_title, _clean_title(job_description_oneliner) if job_description_oneliner else ""]
    for candidate in candidates:
        key = (candidate or "").strip().lower()
        if key in JOB_DESCRIPTION_TEMPLATES:
            return JOB_DESCRIPTION_TEMPLATES[key]
    return None


def _apply_template(template: dict, state: JobDescriptionState) -> dict:
    """Fill a known-role template's {location}/{experience} placeholders with the real values."""
    title = state.get("job_title") or _clean_title(state["job_description_oneliner"])
    experience = state.get("experience") or "3-5 years"
    location = state.get("location") or "Remote"

    description = template["description"].format(location=location, experience=experience)

    return {
        **state,
        "job_title": title,
        "experience": experience,
        "location": location,
        "generated_description": description,
        "skills_needed": list(template["skills"]),
    }


def _fallback_job_description(state: JobDescriptionState) -> dict:
    """Best-effort job description when the LLM is unavailable."""
    title = state.get("job_title") or _clean_title(state["job_description_oneliner"])
    experience = state.get("experience") or "3-5 years"
    location = state.get("location") or "Remote"

    description = (
        f"We are looking for an experienced {title} to join our team.\n\n"
        f"About the Role:\n{state['job_description_oneliner']}\n\n"
        "Key Responsibilities:\n"
        f"- Deliver high-quality {title} work aligned with project and client requirements\n"
        "- Collaborate with cross-functional teams to plan, execute, and deliver on schedule\n"
        "- Follow established engineering/domain best practices and coding or process standards\n"
        "- Communicate progress, risks, and blockers proactively to stakeholders\n"
        "- Participate in reviews, testing, and continuous improvement of deliverables\n\n"
        "Requirements:\n"
        f"- {experience} of relevant hands-on experience\n"
        f"- Based {location}, available to work with the assigned team's hours\n"
        "- Strong communication and problem-solving skills\n\n"
        "Note: This is a starter draft — refine the details above before publishing."
    )

    # No LLM available to extract skills from context, so fall back to the
    # job title's own words plus baseline professional skills — never an
    # empty list, since the form has no manual Skills input as a backstop.
    title_skills = [w for w in title.split() if len(w) > 2]
    skills = list(dict.fromkeys(title_skills + ["Communication", "Problem Solving", "Team Collaboration"]))

    return {
        **state,
        "job_title": title,
        "experience": experience,
        "location": location,
        "generated_description": description,
        "skills_needed": skills,
    }


# Legacy function for backward compatibility
def generate_job_description(job_title: str, job_description: str):
    """
    Legacy function for backward compatibility.
    Generates a simple job description without state management.
    
    Args:
        job_title: The job title
        job_description: Brief job description
        
    Returns:
        LLM response with generated job description
    """
    prompt = f"""
    Generate a job description for the following job title and job description:
    Job Title: {job_title}
    Job Description: {job_description}
    """
    return llm.invoke(prompt)


# Example usage
# if __name__ == "__main__":
#     # Test the job description generator
#     result = generate_job_description_with_state(
#         job_title="Agentic AI Developer",
#         job_description_oneliner="Build scalable agentic AI systems",
#         experience="2-3 years",
#         location="Chennai"
#     )
    
#     print("=" * 80)
#     print(f"JOB TITLE: {result['job_title']}")
#     print("=" * 80)
#     print(f"\nLOCATION: {result['location']}")
#     print(f"EXPERIENCE: {result['experience']}")
#     print(f"\nORIGINAL BRIEF: {result['job_description_oneliner']}")
#     print("\n" + "=" * 80)
#     print("GENERATED JOB DESCRIPTION:")
#     print("=" * 80)
#     print(result['generated_description'])
#     print("\n" + "=" * 80)
#     print("REQUIRED SKILLS:")
#     print("=" * 80)
#     for i, skill in enumerate(result['skills_needed'], 1):
#         print(f"{i}. {skill}")
#     print("=" * 80)