"""
import logging
Flash Interview Transcript Service

Reads interview transcripts from Office 365 Teams meetings and sends to Claude LLM
for AI-powered hire/no-hire decision with confidence scoring.

Production: Real transcripts from Office 365
Local: Mock transcripts for testing
"""

import logging
import json
import requests
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from anthropic import Anthropic

from app.models.interview_pipeline import SubmissionInterview
from app.models.candidate_ai import ConversationEvent
from app.core.logging import logger
from app.core.graph_auth import GraphServiceAuth

logger = logging.getLogger(__name__)

class FlashTranscriptService:
    """Reads and analyzes interview transcripts using Claude LLM."""

    CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

    @staticmethod
    def get_transcript_from_office365(interview_id: str, meeting_id: str) -> Optional[str]:
        """
        Fetch interview transcript from Office 365 Teams meeting.

        In production: Calls Microsoft Graph to get transcription
        In local: Returns mock transcript for testing
        """
        try:
            token = GraphServiceAuth.get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Microsoft Graph: Get meeting transcript
            graph_url = f"https://graph.microsoft.com/v1.0/me/events/{meeting_id}/getTranscript"
            response = requests.get(graph_url, headers=headers, timeout=10)

            if response.status_code == 200:
                transcript_data = response.json()
                transcript_text = transcript_data.get("content", "")
                logger.info(f"[Flash] Retrieved transcript for interview {interview_id}")
                return transcript_text
            else:
                logger.warning(f"[Flash] Failed to get transcript from Office365: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"[Flash] Error fetching transcript: {str(e)}")
            raise ValueError("Operation failed")

    @staticmethod
    def get_mock_transcript(candidate_name: str, role: str) -> str:
        """
        Generate mock interview transcript for local testing.
        Production code skips this.
        """
        return f"""
INTERVIEW TRANSCRIPT - LOCAL TESTING

Candidate: {candidate_name}
Role: {role}
Date: {datetime.now().strftime('%Y-%m-%d')}

---START TRANSCRIPT---

Interviewer (Sarah): Hi {candidate_name}, thanks for joining us today. We're excited to learn more about your background.

Candidate: Thanks for having me! I'm looking forward to our conversation.

Interviewer: Can you walk us through your most recent project and your role in it?

Candidate: Absolutely. In my last role, I led a team of 4 engineers building a real-time analytics platform. We used Python, PostgreSQL, and React. The key challenge was optimizing query performance for 50M+ records daily. I designed a partitioning strategy that reduced query time from 45 seconds to 2 seconds.

Interviewer: That's impressive. How did you approach the technical problem-solving?

Candidate: I started by profiling the queries to identify bottlenecks. Then I researched database optimization strategies, tested hypotheses in a sandbox, and implemented the solution in phases to minimize risk. The whole process took about 3 weeks.

Interviewer: How do you handle working with teammates who have different technical perspectives?

Candidate: I believe in collaborative problem-solving. When there's disagreement, I ask questions to understand their perspective, share my reasoning, and we usually find a good middle ground. Strong teams value diverse viewpoints.

Interviewer: One more - tell us about a time you failed and what you learned.

Candidate: Early in my career, I shipped a feature without proper testing. It had a bug that affected 20% of users. I learned the importance of testing discipline and now I'm diligent about QA. It was humbling but made me a better engineer.

Interviewer: Thanks {candidate_name}. We'll be in touch.

---END TRANSCRIPT---
"""

    @staticmethod
    def analyze_transcript_with_claude(transcript: str, candidate_name: str, role: str) -> dict:
        """
        Send transcript to Claude LLM for hire/no-hire decision.

        Claude evaluates:
        - Technical competency (0-100)
        - Communication clarity (0-100)
        - Problem-solving approach (0-100)
        - Cultural fit with BlitzenX (0-100)

        Returns: HIRE | NO_HIRE | MAYBE with confidence 0-100
        """
        try:
            client = Anthropic()

            prompt = f"""You are Flash, an expert AI hiring interviewer for BlitzenX (a Guidewire staffing specialist firm).

Analyze this interview transcript for candidate: {candidate_name} applying for: {role}

TRANSCRIPT:
{transcript}

Evaluate across 4 dimensions (0-100 for each):
1. Technical Competency: Does the candidate have the technical depth needed for {role}?
2. Communication: Can they articulate ideas clearly? Client-facing capability?
3. Problem-Solving: How do they approach complex problems? Analytical rigor?
4. Cultural Fit: Do they align with BlitzenX values (speed, agility, accountability, learning)?

DECISION LOGIC:
- If all dimensions >=75: HIRE with 85-95% confidence
- If any dimension <40: NO_HIRE with 70-95% confidence
- Otherwise: MAYBE with 40-60% confidence

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "recommendation": "HIRE" | "NO_HIRE" | "MAYBE",
  "confidence_pct": <0-100>,
  "technical_score": <0-100>,
  "communication_score": <0-100>,
  "problem_solving_score": <0-100>,
  "culture_fit_score": <0-100>,
  "strengths": ["strength1", "strength2", "strength3"],
  "concerns": ["concern1", "concern2"],
  "rationale": "One sentence explaining the decision",
  "next_steps": "Interview with hiring manager" | "Request additional references" | "Send offer" | "Reject and thank you"
}}"""

            response = client.messages.create(
                model=self.CLAUDE_MODEL,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            try:
                decision = json.loads(response_text)
                logger.info(f"[Flash] Analysis complete for {candidate_name}: {decision['recommendation']} ({decision['confidence_pct']}%)")
                return decision
            except json.JSONDecodeError as e:
                logger.error(f"[Flash] Invalid JSON response: {response_text}")
                return {
                    "error": "Invalid JSON from Claude",
                    "recommendation": "MAYBE",
                    "confidence_pct": 0,
                    "raw_response": response_text
                }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"[Flash] Claude analysis failed: {str(e)}")
            return {
                "error": str(e),
                "recommendation": None,
                "confidence_pct": 0
            }

    @staticmethod
    def get_flash_decision(db: Session, interview_id: str, use_mock: bool = False) -> dict:
        """
        Get Flash's hire/no-hire decision for an interview.

        Args:
            db: Database session
            interview_id: Interview ID
            use_mock: If True, use mock transcript (local testing)

        Returns:
            Flash decision with recommendation, scores, and rationale
        """
        interview = db.query(SubmissionInterview).filter(
            SubmissionInterview.id == interview_id
        ).first()

        if not interview:
            return {"error": f"Interview {interview_id} not found"}

        # Get candidate name
        candidate = interview.submission.candidate if interview.submission else None
        candidate_name = f"{candidate.candidateFirstName} {candidate.candidateLastName}" if candidate else "Candidate"
        role = interview.level or "Software Engineer"

        # Get transcript
        if use_mock:
            transcript = FlashTranscriptService.get_mock_transcript(candidate_name, role)
            logger.info(f"[Flash] Using MOCK transcript for {interview_id} (local testing)")
        else:
            # Try to get real transcript from Office 365
            meeting_id = getattr(interview, 'teams_meeting_id', None)
            if meeting_id:
                transcript = FlashTranscriptService.get_transcript_from_office365(interview_id, meeting_id)
            else:
                transcript = None

            if not transcript:
                logger.warning(f"[Flash] No transcript available for {interview_id}, returning no decision")
                return {"error": "No transcript available in Office 365"}

        # Analyze with Claude
        decision = FlashTranscriptService.analyze_transcript_with_claude(transcript, candidate_name, role)

        # Log decision event
        if "error" not in decision:
            db.add(ConversationEvent(
                conversation_id=None,
                event_type="FLASH_INTERVIEW_DECISION",
                triggered_by="flash_agent",
                event_data={
                    "interview_id": interview_id,
                    "candidate_name": candidate_name,
                    "recommendation": decision.get("recommendation"),
                    "confidence_pct": decision.get("confidence_pct"),
                    "technical_score": decision.get("technical_score"),
                    "communication_score": decision.get("communication_score"),
                    "problem_solving_score": decision.get("problem_solving_score"),
                    "culture_fit_score": decision.get("culture_fit_score"),
                    "strengths": decision.get("strengths", []),
                    "concerns": decision.get("concerns", []),
                    "rationale": decision.get("rationale"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            ))
            db.commit()

        return decision
