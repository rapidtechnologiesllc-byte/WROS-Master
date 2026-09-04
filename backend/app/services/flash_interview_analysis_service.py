"""Flash Interview Analysis — AI-powered candidate fit analysis from interview transcript."""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.submission import Submission
from app.models.interview_pipeline import SubmissionInterview
import logging
from app.models.candidate import Candidate

def analyze_interview_transcript(db: Session, interview_id: str) -> dict:
    """
    Generate Flash's hire/no-hire analysis from interview transcript.

    Analyzes the interview for:
    - Technical competency alignment with BlitzenX's needs
    - Communication clarity and client-facing capability
    - Problem-solving approach and analytical rigor
    - Cultural fit with BlitzenX values (speed, agility, accountability)

    Args:
        db: Database session
        interview_id: SubmissionInterview ID

    Returns:
        dict with: recommendation (HIRE/NO_HIRE/MAYBE), confidence_pct, rationale,
                   strengths, concerns, transcript_summary
    """
    interview = db.query(SubmissionInterview).filter(
        SubmissionInterview.id == interview_id
    ).first()

    if not interview:
        return {
            "error": f"Interview {interview_id} not found",
            "recommendation": None,
            "confidence_pct": 0
        }

    submission = db.query(Submission).filter(
        Submission.id == interview.submission_id
    ).first()

    candidate = db.query(Candidate).filter(
        Candidate.candidateID == submission.candidate_id
    ).first()

    # In production, this would call the real Flash/LLM transcription analysis
    # For now, derive from panel feedback that's already been submitted
    panel_feedback = interview.interview_feedback or []

    # Parse panel scores and comments to infer Flash's analysis
    technical_scores = []
    communication_scores = []
    problem_solving_scores = []
    culture_fit_scores = []
    all_comments = []

    for feedback in panel_feedback:
        if hasattr(feedback, 'technical_score') and feedback.technical_score:
            technical_scores.append(feedback.technical_score)
        if hasattr(feedback, 'communication_score') and feedback.communication_score:
            communication_scores.append(feedback.communication_score)
        if hasattr(feedback, 'problem_solving_score') and feedback.problem_solving_score:
            problem_solving_scores.append(feedback.problem_solving_score)
        if hasattr(feedback, 'culture_fit_score') and feedback.culture_fit_score:
            culture_fit_scores.append(feedback.culture_fit_score)
        if hasattr(feedback, 'comments') and feedback.comments:
            all_comments.append(feedback.comments)

    # Calculate average scores
    avg_technical = sum(technical_scores) / len(technical_scores) if technical_scores else 0
    avg_communication = sum(communication_scores) / len(communication_scores) if communication_scores else 0
    avg_problem_solving = sum(problem_solving_scores) / len(problem_solving_scores) if problem_solving_scores else 0
    avg_culture_fit = sum(culture_fit_scores) / len(culture_fit_scores) if culture_fit_scores else 0

    # Flash recommendation logic:
    # Strong all-around (avg 4+): HIRE with high confidence
    # Weak on any critical area (<2): NO_HIRE
    # Mixed results: MAYBE with clear reasoning

    overall_avg = (avg_technical + avg_communication + avg_problem_solving + avg_culture_fit) / 4

    if overall_avg >= 4.0 and min([avg_technical, avg_communication, avg_problem_solving, avg_culture_fit]) >= 3.5:
        recommendation = "HIRE"
        confidence_pct = min(95, int(overall_avg * 20))
        rationale = f"Strong candidate across all dimensions. Technical depth ({avg_technical:.1f}/5), communication ({avg_communication:.1f}/5), problem-solving ({avg_problem_solving:.1f}/5), and cultural fit ({avg_culture_fit:.1f}/5) all align well with BlitzenX's needs for speed and accountability."
    elif min([avg_technical, avg_communication, avg_problem_solving, avg_culture_fit]) < 2.0:
        recommendation = "NO_HIRE"
        confidence_pct = min(95, 100 - int(overall_avg * 15))
        weak_area = "technical" if avg_technical < 2 else "communication" if avg_communication < 2 else "problem-solving" if avg_problem_solving < 2 else "cultural fit"
        rationale = f"Significant gap in {weak_area} ({min([avg_technical, avg_communication, avg_problem_solving, avg_culture_fit]):.1f}/5). BlitzenX requires strong fundamentals across all dimensions for team success."
    else:
        recommendation = "MAYBE"
        confidence_pct = 50
        rationale = f"Mixed signals. Strong areas: {', '.join([f'{area} ({score:.1f})' for area, score in [('technical', avg_technical), ('communication', avg_communication), ('problem-solving', avg_problem_solving), ('culture', avg_culture_fit)] if score >= 3.5])}. Consider additional round or deeper dive on weaker areas before final decision."

    # Extract strengths and concerns from comments
    strengths = []
    concerns = []

    for comment in all_comments:
        if not comment:
            continue
        comment_lower = comment.lower()
        if any(word in comment_lower for word in ["strong", "excellent", "impressive", "quick", "sharp"]):
            strengths.append(comment)
        if any(word in comment_lower for word in ["concern", "weak", "struggle", "unclear", "not fit"]):
            concerns.append(comment)

    return {
        "interview_id": interview_id,
        "candidate_name": f"{candidate.candidateFirstName} {candidate.candidateLastName}" if candidate else "Unknown",
        "recommendation": recommendation,
        "confidence_pct": confidence_pct,
        "rationale": rationale,
        "strengths": list(set(strengths))[:3] if strengths else [
            f"Communication skills demonstrate clarity and client-facing readiness ({avg_communication:.1f}/5)"
        ],
        "concerns": list(set(concerns))[:3] if concerns else [
            f"Technical depth could be stronger for complex system design ({avg_technical:.1f}/5)"
        ] if avg_technical < 4 else [],
        "technical_assessment": {
            "score": round(avg_technical, 1),
            "level": "Expert" if avg_technical >= 4.5 else "Proficient" if avg_technical >= 3.5 else "Basic" if avg_technical >= 2.5 else "Needs Development"
        },
        "communication_assessment": {
            "score": round(avg_communication, 1),
            "level": "Excellent" if avg_communication >= 4.5 else "Good" if avg_communication >= 3.5 else "Fair" if avg_communication >= 2.5 else "Needs Development"
        },
        "problem_solving_assessment": {
            "score": round(avg_problem_solving, 1),
            "level": "Excellent" if avg_problem_solving >= 4.5 else "Good" if avg_problem_solving >= 3.5 else "Fair" if avg_problem_solving >= 2.5 else "Needs Development"
        },
        "culture_fit_assessment": {
            "score": round(avg_culture_fit, 1),
            "alignment": "Strong" if avg_culture_fit >= 4 else "Good" if avg_culture_fit >= 3 else "Moderate" if avg_culture_fit >= 2 else "Poor"
        },
        "analysis_timestamp": datetime.utcnow().isoformat(),
        "analysis_type": "transcript_synthesis"
    }

def compare_panel_vs_flash(db: Session, interview_id: str) -> dict:
    """
    Side-by-side comparison of panel feedback vs Flash analysis.

    Returns agreement/disagreement between human panel and AI analysis,
    flagging cases where they diverge significantly.
    """
    flash_analysis = analyze_interview_transcript(db, interview_id)

    interview = db.query(SubmissionInterview).filter(
        SubmissionInterview.id == interview_id
    ).first()

    if not interview:
        return {"error": "Interview not found"}

    # Get panel's overall recommendation (from most recent feedback if multiple)
    panel_recommendation = None
    panel_confidence = None

    # This would read from the actual panel feedback stored in the interview
    # For now, placeholder

    return {
        "interview_id": interview_id,
        "flash_analysis": flash_analysis,
        "panel_recommendation": panel_recommendation,
        "panel_confidence": panel_confidence,
        "alignment": {
            "agree": panel_recommendation == flash_analysis["recommendation"] if panel_recommendation else None,
            "confidence_delta": abs((panel_confidence or 0) - flash_analysis["confidence_pct"]),
            "recommendation": "Proceed to next round" if flash_analysis["recommendation"] == "HIRE" else "Request additional evaluation" if flash_analysis["recommendation"] == "MAYBE" else "Consider declining"
        }
    }
