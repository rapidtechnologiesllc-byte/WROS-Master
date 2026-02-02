from langchain_google_genai import ChatGoogleGenerativeAI
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize the LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-3-flash-preview")


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
    
    # Define the flow
    workflow.set_entry_point("generate_description")
    workflow.add_edge("generate_description", "extract_skills")
    workflow.add_edge("extract_skills", END)
    
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
    
    # Create and run the workflow
    app = create_job_description_workflow()
    final_state = app.invoke(initial_state)
    
    return final_state


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