"""Flash Interview Analysis endpoints â€” AI-powered interview assessment."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
import logging
from app.services.flash_transcript_service import FlashTranscriptService

router = APIRouter(prefix="/flash/interviews", tags=["Flash Interview Analysis"])


@router.get("/{interview_id}/analysis", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_flash_interview_analysis(
    interview_id: str,
    use_mock: bool = Query(False, description="Use mock transcript for testing (local only)"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get Flash's AI-powered analysis of an interview transcript from Office 365.

    Flash reads the actual Teams meeting transcript and provides:
    - Technical competency score (0-100)
    - Communication clarity score (0-100)
    - Problem-solving approach score (0-100)
    - Cultural fit with BlitzenX score (0-100)
    - HIRE | NO_HIRE | MAYBE recommendation
    - Confidence percentage (0-100)
    - Strengths and concerns
    - Next steps recommendation

    Parameters:
    - use_mock: For local testing only. Uses generated mock transcript instead of Office 365.

    Permissions: candidate.view (Recruiter, HR, BU Head, Finance, CEO)
    """
    try:
        # Get Flash decision (reads from Office 365 or uses mock for local testing)
        decision = FlashTranscriptService.get_flash_decision(db, interview_id, use_mock=use_mock)

        if "error" in decision:
            raise HTTPException(status_code=404, detail=decision.get("error"))

        return {
            "status": "success",
            "data": decision
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{interview_id}/comparison", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_flash_panel_comparison(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Side-by-side comparison: Panel feedback vs Flash analysis.

    Useful for:
    - Identifying where panel and AI agree/disagree
    - Flagging high-confidence divergences
    - Supporting hiring decision with multiple perspectives

    Permissions: candidate.view
    """
    try:
        comparison = compare_panel_vs_flash(db, interview_id)
        if "error" in comparison:
            raise HTTPException(status_code=404, detail=comparison["error"])
        return {"status": "success", "data": comparison}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{interview_id}/coaching-email", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def send_coaching_email_to_panel_member(
    interview_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Send coaching email to a panel member with Flash's assessment insights.

    Includes:
    - Hiring manager's personalized coaching feedback
    - Flash's assessment (technical, communication, problem-solving, culture fit scores)
    - Comparison context showing where Flash and panel member agree/disagree
    - Suggested focus areas for future interviews

    Permissions: candidate.manage (Hiring Manager, BU Head, CEO)
    """
    try:
        from app.services.email_service import EmailService

        panel_member_name = payload.get("panel_member_name", "Panel Member")
        panel_member_email = payload.get("panel_member_email")
        coaching_message = payload.get("coaching_message", "")
        candidate_name = payload.get("candidate_name", "Candidate")
        flash_analysis = payload.get("flash_analysis", {})

        if not panel_member_email:
            raise HTTPException(status_code=400, detail="Panel member email is required")

        # Build coaching email
        subject = f"Interview Coaching: {candidate_name} - Flash & Panel Insights"

        body = f"""
Hi {panel_member_name},

Thank you for your thorough feedback on {candidate_name}'s interview. To support your growth as an interviewer, here's how Flash's AI analysis compares with your assessment:

---

FLASH AI ASSESSMENT:
Technical: {flash_analysis.get('technical_score', 'N/A')}/100
Communication: {flash_analysis.get('communication_score', 'N/A')}/100
Problem-Solving: {flash_analysis.get('problem_solving_score', 'N/A')}/100
Culture Fit: {flash_analysis.get('culture_fit_score', 'N/A')}/100

Recommendation: {flash_analysis.get('recommendation', 'N/A')} ({flash_analysis.get('confidence_pct', 0)}% confidence)

Rationale: {flash_analysis.get('rationale', 'N/A')}

Strengths identified by Flash:
{chr(10).join(['- ' + s for s in flash_analysis.get('strengths', [])])}

Concerns identified by Flash:
{chr(10).join(['- ' + c for c in flash_analysis.get('concerns', [])])}

Next Steps: {flash_analysis.get('next_steps', 'N/A')}

---

COACHING FEEDBACK FROM HIRING MANAGER:

{coaching_message}

---

This feedback is designed to help you refine your interview assessment skills. Areas where you and Flash diverge may indicate:

1. Context You Have: You may have seen something in person that the transcript didn't fully capture
2. Blind Spots: Flash's detailed analysis may have caught something worth noticing in future interviews
3. Growth Areas: Consider reviewing transcripts of interviews where you and Flash strongly disagreed

Looking forward to seeing your continued growth as an interviewer.

Best regards,
BlitzenX Hiring System

---
Interview ID: {interview_id}
Candidate: {candidate_name}
"""

        # Send email
        EmailService.send_email(
            to_email=panel_member_email,
            subject=subject,
            body=body,
            is_html=False
        )

        # Log event
        from app.models.candidate_ai import ConversationEvent
        from datetime import datetime

        db.add(ConversationEvent(
            conversation_id=None,
            event_type="COACHING_EMAIL_SENT",
            triggered_by="hiring_manager",
            event_data={
                "interview_id": interview_id,
                "panel_member_email": panel_member_email,
                "panel_member_name": panel_member_name,
                "candidate_name": candidate_name,
                "coaching_sent_by": current_user.email if hasattr(current_user, 'email') else "system",
                "timestamp": datetime.utcnow().isoformat()
            }
        ))
        db.commit()

        return {
            "status": "success",
            "message": f"Coaching email sent to {panel_member_name}",
            "recipient": panel_member_email
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
