"""
ATS (Applicant Tracking System) Scorer
=======================================
Uses a LangGraph multi-node pipeline powered by Google Gemini to evaluate a
candidate's profile against a job description and produce:

  - An overall ATS score (0–100)
  - Sub-scores for 5 dimensions: Skills, Experience, Education, Location, Culture-Fit
  - A resume summary extracted from the raw profile text
  - Strengths / weaknesses / hiring recommendation

The pipeline runs in a single synchronous call; async usage wraps with
`asyncio.get_event_loop().run_in_executor(...)`.
"""

import logging
import json
import os
import re
from typing import List, Optional, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM initialisation (re-uses the same key as job_description_generator)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_llm = None

# Only attempt to initialize LLM if API key is provided
if GEMINI_API_KEY:
    try:
        _llm = ChatGoogleGenerativeAI(
            api_key=GEMINI_API_KEY,
            model="gemini-flash-lite-latest",          # fast, cheap, sufficient for scoring
            temperature=0.2,                    # low temp → consistent scores
        )
    except Exception as e:
        logger.error(f"Error initializing LLM: {str(e)}", exc_info=True)
        # If Google credentials not available, LLM will be None
        # ATS scoring will return stub response
        import sys
        print(f"[WARNING] ATS Scorer: LLM initialization failed: {e}", file=sys.stderr)
else:
    import sys
    print("[WARNING] ATS Scorer: GEMINI_API_KEY not set, using stub responses", file=sys.stderr)

def _invoke_llm(prompt: str) -> str:
    """Invoke the LLM and normalise the response to a plain string."""
    if _llm is None:
        # Return stub response if LLM not available (e.g., Google credentials missing)
        return '{"score": 50, "message": "ATS scoring unavailable - Google credentials not configured"}'

    response = _llm.invoke(prompt)
    if isinstance(response.content, str):
        return response.content
    if isinstance(response.content, list):
        return "".join(
            part["text"] if isinstance(part, dict) and "text" in part else str(part)
            for part in response.content
        )
    return str(response.content)

def _extract_json(text: str) -> dict:
    """
    Robustly extract the first JSON object from an LLM response that may
    include markdown fences or extra prose.
    """
    # Strip ```json … ``` fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Fallback: grab first { … }
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        text = brace.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("Operation failed")

# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class ATSState(TypedDict):
    # Inputs
    job_title: str
    job_description: str
    job_skills: str            # comma-separated or free text from the Jobs row
    job_experience: str        # e.g. "3–5 years"
    job_location: str

    candidate_name: str
    candidate_experience: str  # years
    candidate_skills: str      # free text / comma-separated
    candidate_location: str
    education_summary: str     # formatted string built from education records
    experience_summary: str    # formatted string built from experience records

    # Outputs (filled by nodes)
    profile_summary: str
    skills_score: int          # 0–25
    experience_score: int      # 0–25
    education_score: int       # 0–20
    location_score: int        # 0–15
    culture_fit_score: int     # 0–15
    overall_score: int         # 0–100
    strengths: List[str]
    weaknesses: List[str]
    recommendation: str        # "Shortlist" | "Review" | "Reject"
    score_rationale: str
    ats_verdict: str           # one-liner verdict for display

# ---------------------------------------------------------------------------
# Node 1 — Profile summariser
# ---------------------------------------------------------------------------

def _node_summarise_profile(state: ATSState) -> ATSState:
    """Convert raw candidate fields into a coherent textual profile."""
    prompt = f"""
You are an HR assistant. Summarise the following candidate profile in 3–4 concise sentences,
highlighting their key skills, experience, and education. Be factual and neutral.

Name: {state['candidate_name']}
Years of Experience: {state['candidate_experience']}
Skills: {state['candidate_skills']}
Current Location: {state['candidate_location']}

Education:
{state['education_summary'] or 'Not provided'}

Work Experience:
{state['experience_summary'] or 'Not provided'}

Return ONLY the summary paragraph, no extra text.
"""
    state["profile_summary"] = _invoke_llm(prompt).strip()
    return state

# ---------------------------------------------------------------------------
# Node 2 — Skills & Experience scorer
# ---------------------------------------------------------------------------

def _node_score_skills_experience(state: ATSState) -> ATSState:
    """Score skills (0–25) and experience (0–25) dimensions."""
    prompt = f"""
You are an expert ATS (Applicant Tracking System). Score the candidate on two dimensions.

JOB REQUIREMENTS
----------------
Job Title      : {state['job_title']}
Required Skills: {state['job_skills']}
Experience     : {state['job_experience']}

CANDIDATE PROFILE
-----------------
Skills         : {state['candidate_skills']}
Experience     : {state['candidate_experience']} years
Work History   :
{state['experience_summary'] or 'Not provided'}

Scoring guide
  skills_score    — out of 25. Award 25 if skills match ≥ 90 % of required skills.
  experience_score — out of 25. Award 25 if years match or exceed required experience.

Return ONLY a JSON object with exactly these keys:
{{
  "skills_score": <int 0-25>,
  "experience_score": <int 0-25>,
  "skills_rationale": "<one sentence>",
  "experience_rationale": "<one sentence>"
}}
"""
    raw = _invoke_llm(prompt)
    data = _extract_json(raw)

    state["skills_score"] = min(25, max(0, int(data.get("skills_score", 0))))
    state["experience_score"] = min(25, max(0, int(data.get("experience_score", 0))))
    return state

# ---------------------------------------------------------------------------
# Node 3 — Education & Location scorer
# ---------------------------------------------------------------------------

def _node_score_education_location(state: ATSState) -> ATSState:
    """Score education (0–20) and location (0–15) dimensions."""
    prompt = f"""
You are an expert ATS. Score the candidate on two dimensions.

JOB REQUIREMENTS
----------------
Job Title   : {state['job_title']}
Location    : {state['job_location']}
Description : {state['job_description'][:500]}

CANDIDATE PROFILE
-----------------
Education:
{state['education_summary'] or 'Not provided'}

Location: {state['candidate_location']}

Scoring guide
  education_score — out of 20.
    20 = Degree in a directly relevant field from a recognised institution.
    10 = Relevant degree or equivalent certification.
     0 = No education info or no apparent relevance.
  location_score — out of 15.
    15 = Candidate is in the same city/region as the job.
    10 = Same country / open to relocation stated.
     5 = Different region with remote-work potential.
     0 = No location data.

Return ONLY a JSON object with exactly these keys:
{{
  "education_score": <int 0-20>,
  "location_score": <int 0-15>,
  "education_rationale": "<one sentence>",
  "location_rationale": "<one sentence>"
}}
"""
    raw = _invoke_llm(prompt)
    data = _extract_json(raw)

    state["education_score"] = min(20, max(0, int(data.get("education_score", 0))))
    state["location_score"] = min(15, max(0, int(data.get("location_score", 0))))
    return state

# ---------------------------------------------------------------------------
# Node 4 — Culture-fit & Final verdict
# ---------------------------------------------------------------------------

def _node_score_culture_verdict(state: ATSState) -> ATSState:
    """Score culture-fit (0–15) and produce final verdict, strengths, weaknesses."""
    prompt = f"""
You are a senior recruiter. Evaluate culture and overall fit.

JOB DESCRIPTION (first 800 chars):
{state['job_description'][:800]}

CANDIDATE PROFILE SUMMARY:
{state['profile_summary']}

Partial scores already computed:
  Skills     : {state['skills_score']} / 25
  Experience : {state['experience_score']} / 25
  Education  : {state['education_score']} / 20
  Location   : {state['location_score']} / 15

Culture-fit scoring (out of 15):
  Consider: job-hopping patterns, progression, career alignment, soft skills inferred from profile.

Rules
  recommendation must be one of: "Shortlist", "Review", "Reject"
    Shortlist → overall_score ≥ 70
    Review    → overall_score 45–69
    Reject    → overall_score < 45

  overall_score = skills_score + experience_score + education_score
                + location_score + culture_fit_score   (max 100)

Return ONLY a JSON object with exactly these keys:
{{
  "culture_fit_score": <int 0-15>,
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"],
  "recommendation": "Shortlist|Review|Reject",
  "score_rationale": "<2–3 sentence overall rationale>",
  "ats_verdict": "<one punchy sentence for display>"
}}
"""
    raw = _invoke_llm(prompt)
    data = _extract_json(raw)

    culture = min(15, max(0, int(data.get("culture_fit_score", 0))))
    state["culture_fit_score"] = culture
    state["overall_score"] = min(
        100,
        state["skills_score"]
        + state["experience_score"]
        + state["education_score"]
        + state["location_score"]
        + culture,
    )
    state["strengths"] = data.get("strengths", [])
    state["weaknesses"] = data.get("weaknesses", [])
    state["recommendation"] = data.get("recommendation", "Review")
    state["score_rationale"] = data.get("score_rationale", "")
    state["ats_verdict"] = data.get("ats_verdict", "")
    return state

# ---------------------------------------------------------------------------
# Build & cache the compiled graph
# ---------------------------------------------------------------------------

def _build_ats_graph():
    g = StateGraph(ATSState)
    g.add_node("summarise_profile", _node_summarise_profile)
    g.add_node("score_skills_experience", _node_score_skills_experience)
    g.add_node("score_education_location", _node_score_education_location)
    g.add_node("score_culture_verdict", _node_score_culture_verdict)

    g.set_entry_point("summarise_profile")
    g.add_edge("summarise_profile", "score_skills_experience")
    g.add_edge("score_skills_experience", "score_education_location")
    g.add_edge("score_education_location", "score_culture_verdict")
    g.add_edge("score_culture_verdict", END)
    return g.compile()

_ATS_GRAPH = _build_ats_graph()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ats_scoring(
    *,
    job_title: str,
    job_description: str,
    job_skills: str,
    job_experience: str,
    job_location: str,
    candidate_name: str,
    candidate_experience: str,
    candidate_skills: str,
    candidate_location: str,
    education_records: Optional[List[dict]] = None,
    experience_records: Optional[List[dict]] = None,
) -> dict:
    """
    Run the full ATS scoring pipeline and return a result dictionary.

    Parameters
    ----------
    All job fields come from the ``Jobs`` ORM row.
    Candidate fields come from the ``Candidate`` ORM row.
    education_records / experience_records are lists of dicts with keys
      matching CandidateEducationForm / CandidateExperienceForm columns.

    Returns
    -------
    dict with keys:
        overall_score, skills_score, experience_score, education_score,
        location_score, culture_fit_score, profile_summary,
        strengths, weaknesses, recommendation, score_rationale, ats_verdict
    """
    # Format education into a readable string
    edu_lines = []
    for e in (education_records or []):
        edu_lines.append(
            f"  • {e.get('degree', 'N/A')} in {e.get('field_of_study', 'N/A')} "
            f"from {e.get('education_institute', 'N/A')} "
            f"({e.get('starting_year', '?')}–{e.get('year_of_passing', '?')})"
        )
    education_summary = "\n".join(edu_lines) or "Not provided"

    # Format experience into a readable string
    exp_lines = []
    for x in (experience_records or []):
        exp_lines.append(
            f"  • {x.get('job_title', 'N/A')} at {x.get('company_name', 'N/A')} "
            f"({x.get('start_date', '?')} → {x.get('end_date', 'Present')}, "
            f"{x.get('year_of_experience', '?')} yrs)"
        )
    experience_summary = "\n".join(exp_lines) or "Not provided"

    initial_state: ATSState = {
        "job_title": job_title or "",
        "job_description": job_description or "",
        "job_skills": job_skills or "",
        "job_experience": job_experience or "",
        "job_location": job_location or "",
        "candidate_name": candidate_name or "Unknown",
        "candidate_experience": candidate_experience or "0",
        "candidate_skills": candidate_skills or "Not provided",
        "candidate_location": candidate_location or "Not provided",
        "education_summary": education_summary,
        "experience_summary": experience_summary,
        # outputs (initialised empty)
        "profile_summary": "",
        "skills_score": 0,
        "experience_score": 0,
        "education_score": 0,
        "location_score": 0,
        "culture_fit_score": 0,
        "overall_score": 0,
        "strengths": [],
        "weaknesses": [],
        "recommendation": "Review",
        "score_rationale": "",
        "ats_verdict": "",
    }

    final_state = _ATS_GRAPH.invoke(initial_state)
    return {
        "overall_score": final_state["overall_score"],
        "skills_score": final_state["skills_score"],
        "experience_score": final_state["experience_score"],
        "education_score": final_state["education_score"],
        "location_score": final_state["location_score"],
        "culture_fit_score": final_state["culture_fit_score"],
        "profile_summary": final_state["profile_summary"],
        "strengths": final_state["strengths"],
        "weaknesses": final_state["weaknesses"],
        "recommendation": final_state["recommendation"],
        "score_rationale": final_state["score_rationale"],
        "ats_verdict": final_state["ats_verdict"],
    }
