"""
Thunder Security Service - Strict Information Access Control
============================================================
Implements information firewall between Thunder (public AI recruiter)
and internal systems (Flash, HR data, confidential info).

Rules enforced:
- Thunder answers ONLY from public/candidate-specific data
- Flash NEVER communicates externally
- No internal HR info exposed
- No salary/rate/cost info exposed
- Only open jobs + candidate's own status shared
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.candidate import Candidate
from app.models.user import Jobs
from app.core.logging import logger


class InformationCategory(Enum):
    """What information Thunder is allowed to access"""
    OPEN_JOBS = "public_open_jobs"  # Public job listings
    CANDIDATE_OWN_STATUS = "candidate_own_status"  # Only their own application status
    CANDIDATE_OWN_DATA = "candidate_own_data"  # Only their own profile
    INTERNAL_HR = "internal_hr"  # BLOCKED - HR data, salaries, costs
    FLASH_COMMUNICATIONS = "flash_communications"  # BLOCKED - Flash-only
    SYSTEM_DATA = "system_data"  # BLOCKED - System internals, configs


class ThunderSecurityManager:
    """
    Enforces strict information access for Thunder.
    Acts as a gatekeeper between Thunder queries and database.
    """

    # BLOCKED CATEGORIES - Thunder CANNOT access these
    BLOCKED_CATEGORIES = {
        InformationCategory.INTERNAL_HR,
        InformationCategory.FLASH_COMMUNICATIONS,
        InformationCategory.SYSTEM_DATA,
    }

    # ALLOWED CATEGORIES - Thunder CAN access these
    ALLOWED_CATEGORIES = {
        InformationCategory.OPEN_JOBS,
        InformationCategory.CANDIDATE_OWN_STATUS,
        InformationCategory.CANDIDATE_OWN_DATA,
    }

    def __init__(self, db: Session):
        self.db = db
        self.audit_log = []

    def get_public_jobs(self) -> List[Dict]:
        """
        ALLOWED: Return only publicly-listed open jobs
        No: salary ranges, cost rates, internal notes, HR comments
        """
        logger.info("[THUNDER-SECURITY] Fetching public open jobs")

        jobs = self.db.query(Jobs).filter(
            and_(
                Jobs.jobStatus.in_(["active", "public"]),
                # Only return job info candidates should see
            )
        ).all()

        public_jobs = []
        for job in jobs:
            public_jobs.append({
                "job_id": job.jobID,
                "title": job.jobTitle,
                "description": job.jobDescription,
                "skills": job.jobSkills,
                "experience_required": job.jobExperience,
                "location": job.jobLocation,
                # BLOCKED: salary, cost, rate, internal notes
            })

        self._audit_access(
            category=InformationCategory.OPEN_JOBS,
            resource_count=len(public_jobs),
            allowed=True,
        )

        return public_jobs

    def get_candidate_own_status(self, candidate_id: str) -> Dict:
        """
        ALLOWED: Return ONLY this candidate's own application status
        Only information the candidate already knows about their own application
        """
        logger.info(f"[THUNDER-SECURITY] Fetching candidate's own status: {candidate_id}")

        candidate = self.db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            logger.warning(f"[THUNDER-SECURITY] Candidate not found: {candidate_id}")
            return {"error": "Candidate not found"}

        # ONLY their own status - nothing about other candidates
        status_info = {
            "candidate_id": candidate.candidateID,
            "name": f"{candidate.candidateFirstName} {candidate.candidateLastName}",
            "email": candidate.candidateEmail,
            "phone": candidate.candidateMobile,
            "applied_for_job": candidate.candidateRole,
            "application_date": str(candidate.candidateCreatedAt) if candidate.candidateCreatedAt else None,
            "status": "Active",
            # BLOCKED: salary expectations, internal notes, other candidates' data
        }

        self._audit_access(
            category=InformationCategory.CANDIDATE_OWN_STATUS,
            resource_id=candidate_id,
            allowed=True,
        )

        return status_info

    def validate_claude_request(self, candidate_id: str, query: str) -> Dict[str, Any]:
        """
        SECURITY GATE: Validates that Claude's response will only use allowed data
        Checks if the query asks for blocked information
        """
        logger.info(f"[THUNDER-SECURITY] Validating Claude request from candidate: {candidate_id}")

        # Scan for forbidden keywords
        forbidden_keywords = [
            "salary", "cost", "rate", "budget", "confidential", "internal",
            "other candidates", "employee", "hr", "human resources",
            "pay", "compensation", "margin", "profit", "secret", "private",
            "flash", "agentic", "system", "database", "config", "admin",
        ]

        query_lower = query.lower()
        blocked_terms = [kw for kw in forbidden_keywords if kw in query_lower]

        if blocked_terms:
            logger.warning(
                f"[THUNDER-SECURITY] BLOCKED - Forbidden terms detected: {blocked_terms}"
            )
            return {
                "allowed": False,
                "reason": "Your question asks for information I'm not allowed to share.",
                "error": "Information access denied",
                "blocked_terms": blocked_terms,
            }

        # Allowed - Claude can respond using only public + candidate's own data
        return {
            "allowed": True,
            "allowed_sources": [
                InformationCategory.OPEN_JOBS.value,
                InformationCategory.CANDIDATE_OWN_STATUS.value,
            ],
            "blocked_sources": [
                InformationCategory.INTERNAL_HR.value,
                InformationCategory.FLASH_COMMUNICATIONS.value,
                InformationCategory.SYSTEM_DATA.value,
            ],
        }

    def ensure_flash_internal_only(self, message_source: str) -> bool:
        """
        SECURITY GATE: Ensures Flash AI messages stay INTERNAL
        Flash should NEVER communicate with candidates or external systems
        """
        logger.info(f"[FLASH-SECURITY] Checking if message should go external: {message_source}")

        # Flash is for HR/internal use only
        internal_only_contexts = [
            "flash_", "internal_", "hr_", "admin_", "staff_"
        ]

        if any(context in message_source.lower() for context in internal_only_contexts):
            logger.warning(
                f"[FLASH-SECURITY] BLOCKED - Flash tried to communicate externally: {message_source}"
            )
            return False  # Block external communication

        return True  # Allow only if not Flash-internal

    def _audit_access(
        self,
        category: InformationCategory,
        resource_id: Optional[str] = None,
        resource_count: int = 0,
        allowed: bool = True,
    ):
        """Log all data access for audit trail"""
        log_entry = {
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            "category": category.value,
            "resource_id": resource_id,
            "resource_count": resource_count,
            "allowed": allowed,
        }
        self.audit_log.append(log_entry)
        logger.info(f"[AUDIT] Data access: {log_entry}")


class ThunderClaudeIntegration:
    """
    Integrates Claude AI with Thunder in STRICT MODE
    - Claude answers ONLY from allowed database information
    - No access to confidential data
    - Responses validated before sending to candidates
    """

    def __init__(self, db: Session, claude_client):
        self.db = db
        self.claude = claude_client
        self.security = ThunderSecurityManager(db)

    def answer_candidate_question(
        self,
        candidate_id: str,
        question: str,
    ) -> Dict[str, str]:
        """
        Thunder uses Claude to answer candidate questions
        STRICT MODE: Only from public jobs + their own status
        """
        logger.info(f"[THUNDER] Candidate {candidate_id} asks: {question}")

        # Step 1: Security validation
        security_check = self.security.validate_claude_request(candidate_id, question)
        if not security_check["allowed"]:
            logger.warning(f"[THUNDER] Security blocked request: {security_check['reason']}")
            return {
                "answer": "I can only help with questions about open jobs or your application status. What would you like to know?",
                "status": "blocked",
            }

        # Step 2: Gather allowed data
        public_jobs = self.security.get_public_jobs()
        candidate_status = self.security.get_candidate_own_status(candidate_id)

        # Step 3: Build Claude prompt with STRICT boundaries
        system_prompt = """
You are Thunder, a recruitment AI assistant.

STRICT RULES - YOU MUST FOLLOW:
1. ONLY answer from the job listings and this candidate's own application status provided below
2. NEVER mention: salaries, costs, rates, internal notes, other candidates, HR information
3. NEVER access or mention: Flash AI, system internals, database structure, configs
4. If asked about something not in the allowed data, say: "I don't have that information"
5. Always be professional and helpful within these boundaries

ALLOWED DATA:
- Open job listings (titles, descriptions, skills, locations)
- This candidate's own application status and personal info
- General company information about BlitzenX

BLOCKED DATA:
- Salary ranges, compensation, cost rates
- Internal HR notes or candidate ratings
- Other candidates' information
- System/technical information
- Flash AI activities or capabilities
"""

        context_data = f"""
OPEN JOBS:
{self._format_jobs_for_claude(public_jobs)}

CANDIDATE'S STATUS:
{self._format_status_for_claude(candidate_status)}
"""

        # Step 4: Call Claude with strict parameters
        try:
            response = self.claude.messages.create(
                model="claude-opus-5",
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"{context_data}\n\nCandidate Question: {question}"
                    }
                ],
            )

            answer = response.content[0].text

            # Step 5: Validate response before sending
            if self._response_contains_blocked_info(answer):
                logger.warning(f"[THUNDER] Claude response contained blocked info, sanitizing")
                answer = "I can only help with information about open jobs and your application. Please ask about those instead."

            return {
                "answer": answer,
                "status": "success",
                "source": "claude-strict-mode",
            }

        except Exception as e:
            logger.error(f"[THUNDER] Claude error: {e}")
            return {
                "answer": "I'm having trouble answering that right now. Please try again later.",
                "status": "error",
            }

    def _format_jobs_for_claude(self, jobs: List[Dict]) -> str:
        """Format public jobs for Claude context"""
        if not jobs:
            return "No open jobs available at this time."

        formatted = "Available open positions:\n"
        for job in jobs:
            formatted += f"\n- {job['title']} ({job['location']})\n"
            formatted += f"  Required skills: {job['skills']}\n"
            formatted += f"  Experience needed: {job['experience_required']}\n"

        return formatted

    def _format_status_for_claude(self, status: Dict) -> str:
        """Format candidate's own status for Claude context"""
        if "error" in status:
            return "Candidate information not found."

        return f"""
Your Application:
- Position applied for: {status.get('applied_for_job', 'N/A')}
- Application date: {status.get('application_date', 'N/A')}
- Current status: {status.get('status', 'N/A')}
"""

    def _response_contains_blocked_info(self, response: str) -> bool:
        """Scan Claude's response for accidentally leaked blocked info"""
        blocked_keywords = [
            "salary", "cost", "rate", "budget", "pay", "compensation",
            "confidential", "internal", "admin", "system", "database",
            "flash", "secret", "private", "margin", "profit"
        ]

        response_lower = response.lower()
        for keyword in blocked_keywords:
            if keyword in response_lower:
                return True

        return False


def ensure_flash_stays_internal(message_context: str) -> bool:
    """
    CRITICAL GATE: Prevents Flash (internal AI) from communicating externally
    All Flash communications must be confined to internal systems only
    """
    if "flash" in message_context.lower():
        if "candidate" in message_context.lower() or "external" in message_context.lower():
            logger.critical(
                f"[SECURITY] BLOCKED - Flash tried external communication: {message_context}"
            )
            return False

    return True
