"""
Relation Building Agent - Persona Extraction & Relationship Intelligence

Reports to: Flash Orchestration Engine

Purpose:
1. Extract candidate persona from SLM-parsed resume data
2. Build relationship intelligence profile from interactions
3. Classify candidate type and engagement potential
4. Store persona facts in candidate memory
5. Report relationship status to Flash for autonomous system coordination

Persona Classification:
- Career Level: Entry (0-2 yrs), Mid (2-5 yrs), Senior (5-10 yrs), Lead (10+ yrs)
- Skill Depth: Specialist (deep in 1-2 areas), Generalist (broad 3+ areas), Master (leading expert)
- Motivation Type: Growth-seeker, Stability-seeker, Compensation-driven, Impact-driven, Leadership-driven
- Risk Factors: Flight risk, Negotiation difficulty, Geographic constraint, Skill mismatch
- Engagement Readiness: High (actively seeking), Medium (open), Low (passive), Negative (needs nurturing)

Each autonomous system (Thunder, Interview Scheduler, Offer Generator, etc.) uses persona
to personalize its interactions and decisions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.agent_logging import log_agent_execution
from app.core.logging import logger
from app.models.candidate import Candidate
from app.services.resume_parser_slm import ResumeSLM
from app.services.candidate_memory_service import upsert_fact, get_memory
from app.services.performance_store_service import write_performance_event


class RelationBuildingAgent:
    """
    Relation Building Agent - Extracts and maintains candidate personas.

    Reports to Flash Orchestration Engine.

    Architecture:
    1. Extract: Parse SLM resume data into structured resume
    2. Analyze: Derive persona from resume + interaction history
    3. Store: Persist persona facts in candidate memory
    4. Report: Provide persona-aware insights to downstream systems
    5. Coordinate: Report relationship status to Flash for optimization
    """

    # Career level definitions (by years of experience)
    CAREER_LEVELS = {
        "entry": (0, 2),
        "mid": (2, 5),
        "senior": (5, 10),
        "lead": (10, 20),
        "principal": (20, float("inf")),
    }

    # Motivation signals (mapped from resume/interaction data)
    MOTIVATOR_KEYWORDS = {
        "growth": ["grow", "develop", "learn", "mentor", "training", "advancement", "skill", "challenge"],
        "stability": ["long-term", "established", "team", "culture", "benefits", "remote", "flexible"],
        "compensation": ["market", "salary", "equity", "bonus", "package", "competitive"],
        "impact": ["mission", "impact", "meaningful", "contribute", "lead", "drive", "transform"],
        "leadership": ["lead", "manage", "direct", "team", "organization", "strategy"],
    }

    # Risk signals (flags that might impact hiring)
    RISK_KEYWORDS = {
        "flight_risk": ["high growth", "early stage", "startup", "ambitious", "seeking challenge"],
        "negotiation_difficulty": ["very selective", "high bar", "demanding", "perfectionist"],
        "geographic_constraint": ["local only", "remote only", "relocation rejected", "visa"],
        "skill_gap": ["transitioning", "career change", "learning", "junior in field"],
    }

    @staticmethod
    @log_agent_execution("Relation Building Agent", "extract_candidate_persona")
    async def extract_candidate_persona(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        resume_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract persona from candidate's resume and interaction history.

        Steps:
        1. Fetch candidate + resume from database
        2. Parse resume using SLM
        3. Analyze career trajectory, skills, motivations, constraints
        4. Classify candidate persona type
        5. Store facts in candidate memory
        6. Return persona profile for downstream systems

        Args:
            candidate_id: Candidate UUID
            tenant_id: Tenant context
            db: Database session
            resume_text: Optional override resume text (for testing)

        Returns:
            {
                "candidate_id": str,
                "persona": {
                    "career_level": "senior",
                    "skill_depth": "specialist",
                    "motivation_primary": "growth",
                    "motivators": ["growth", "impact"],
                    "constraints": ["geographic_constraint"],
                    "risk_factors": ["flight_risk"],
                    "engagement_readiness": "high",
                },
                "profile": {
                    "years_experience": 7,
                    "skill_count": 12,
                    "companies_worked": 3,
                    "job_stability": 0.85,
                    "skill_areas": [...],
                },
                "relationship_status": "RECEPTIVE",
                "recommended_engagement": "proactive_outreach",
                "memory_facts_stored": 15,
            }
        """
        try:
            # 1. FETCH CANDIDATE
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                return {
                    "status": "error",
                    "message": f"Candidate {candidate_id} not found",
                    "candidate_id": candidate_id,
                }

            # 2. PARSE RESUME
            if not resume_text:
                resume_text = candidate.resume_text or ""

            if not resume_text:
                return {
                    "status": "error",
                    "message": f"No resume text available for candidate {candidate_id}",
                    "candidate_id": candidate_id,
                }

            parsed_resume = ResumeSLM.parse_resume(resume_text)

            # 3. ANALYZE PERSONA
            persona = RelationBuildingAgent._classify_persona(parsed_resume, resume_text)
            profile = RelationBuildingAgent._build_candidate_profile(parsed_resume)
            relationship_status = RelationBuildingAgent._assess_relationship_status(persona, profile)
            engagement_strategy = RelationBuildingAgent._recommend_engagement(persona, relationship_status)

            # 4. STORE FACTS IN MEMORY
            facts_stored = RelationBuildingAgent._store_persona_facts(
                candidate_id=candidate_id,
                tenant_id=tenant_id,
                db=db,
                persona=persona,
                profile=profile,
            )

            # 5. WRITE PERFORMANCE EVENT
            write_performance_event(
                db,
                event_type="RELATION_BUILDING_PERSONA_EXTRACTED",
                tenant_id=tenant_id,
                event_data={
                    "candidate_id": candidate_id,
                    "career_level": persona["career_level"],
                    "engagement_readiness": persona["engagement_readiness"],
                    "facts_stored": facts_stored,
                },
            )

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "candidate_name": candidate.name or parsed_resume.get("full_name"),
                "persona": persona,
                "profile": profile,
                "relationship_status": relationship_status,
                "recommended_engagement": engagement_strategy,
                "memory_facts_stored": facts_stored,
            }

        except Exception as e:
            logger.error(f"Relation Building Agent error for {candidate_id}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "candidate_id": candidate_id,
            }

    @staticmethod
    def _classify_persona(parsed_resume: Dict, resume_text: str) -> Dict[str, Any]:
        """
        Classify candidate persona from resume data.

        Analyzes:
        - Career progression (years, roles, companies)
        - Skill depth vs breadth
        - Motivation indicators
        - Constraints and risk factors
        """
        years_exp = parsed_resume.get("years_experience", 0)
        skills = parsed_resume.get("skills", [])
        work_history = parsed_resume.get("work_history", [])
        current_title = parsed_resume.get("current_title", "").lower()

        # CAREER LEVEL
        career_level = "entry"
        for level, (min_yrs, max_yrs) in RelationBuildingAgent.CAREER_LEVELS.items():
            if min_yrs <= years_exp < max_yrs:
                career_level = level
                break

        # SKILL DEPTH
        skill_count = len(set(skills))  # Unique skills
        if skill_count > 15:
            skill_depth = "generalist"
        elif skill_count > 8:
            skill_depth = "specialist"
        else:
            skill_depth = "focused"

        # MOTIVATION (from resume text analysis)
        resume_lower = resume_text.lower()
        motivation_scores = {}
        for motive, keywords in RelationBuildingAgent.MOTIVATOR_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in resume_lower)
            if score > 0:
                motivation_scores[motive] = score

        primary_motivator = max(motivation_scores.items(), key=lambda x: x[1])[0] if motivation_scores else "growth"
        all_motivators = [m for m, score in motivation_scores.items() if score > 0]

        # CONSTRAINTS & RISKS
        constraints = []
        risk_factors = []

        for risk_type, keywords in RelationBuildingAgent.RISK_KEYWORDS.items():
            if any(kw in resume_lower for kw in keywords):
                if "constraint" in risk_type:
                    constraints.append(risk_type)
                else:
                    risk_factors.append(risk_type)

        # Check for seniority risk factors
        if any(title in current_title for title in ["manager", "director", "vp", "lead"]):
            risk_factors.append("leadership_commitment")  # Less likely to go IC

        # ENGAGEMENT READINESS (based on signals)
        engagement_readiness = "medium"

        # High: Recently updated resume, many skills, growth trajectory
        if skill_count >= 10 and len(work_history) >= 3:
            if "growth" in all_motivators or "impact" in all_motivators:
                engagement_readiness = "high"

        # Low: Few skills, long tenure at one company, stability-focused
        if skill_count <= 5 and "stability" in all_motivators:
            engagement_readiness = "low"

        # Negative indicators
        if len(risk_factors) >= 3 or "negotiation_difficulty" in risk_factors:
            engagement_readiness = "low"

        return {
            "career_level": career_level,
            "years_experience": years_exp,
            "skill_depth": skill_depth,
            "skill_count": skill_count,
            "motivation_primary": primary_motivator,
            "motivators": all_motivators,
            "constraints": constraints,
            "risk_factors": risk_factors,
            "engagement_readiness": engagement_readiness,
        }

    @staticmethod
    def _build_candidate_profile(parsed_resume: Dict) -> Dict[str, Any]:
        """
        Build comprehensive candidate profile from parsed resume.
        """
        work_history = parsed_resume.get("work_history", [])
        education = parsed_resume.get("education", [])
        skills = parsed_resume.get("skills", [])

        # Calculate job stability (avg tenure per role)
        if work_history:
            total_months = sum(job.get("duration_months", 0) for job in work_history)
            avg_tenure = total_months / len(work_history) if work_history else 0
            job_stability = min(avg_tenure / 24, 1.0)  # Max 2 years = stable
        else:
            job_stability = 0.5

        return {
            "years_experience": parsed_resume.get("years_experience", 0),
            "companies_worked": len(set(job.get("company") for job in work_history)),
            "skill_count": len(set(skills)),
            "skill_areas": skills[:10],  # Top 10 skills
            "education_level": "bachelors" if any("bachelor" in str(e).lower() for e in education) else "other",
            "job_stability": job_stability,
            "has_certifications": bool(parsed_resume.get("certifications")),
            "languages": parsed_resume.get("languages", []),
            "current_title": parsed_resume.get("current_title"),
            "current_employer": parsed_resume.get("current_employer"),
        }

    @staticmethod
    def _assess_relationship_status(persona: Dict, profile: Dict) -> str:
        """
        Assess relationship status for Flash reporting.

        States:
        - RECEPTIVE: High likelihood to engage positively
        - INTERESTED: Medium likelihood, needs right approach
        - HESITANT: Low likelihood, needs significant value prop
        - RESISTANT: Very low, needs escalation or different approach
        """
        engagement = persona["engagement_readiness"]
        risk_count = len(persona["risk_factors"])
        constraint_count = len(persona["constraints"])
        skill_depth = persona["skill_depth"]

        # High engagement + few risks = RECEPTIVE
        if engagement == "high" and risk_count <= 1:
            return "RECEPTIVE"

        # Medium engagement + balanced profile = INTERESTED
        if engagement == "medium" and risk_count <= 2:
            return "INTERESTED"

        # Low engagement or many risks = HESITANT
        if engagement == "low" or risk_count >= 3:
            return "HESITANT"

        # Default
        return "INTERESTED"

    @staticmethod
    def _recommend_engagement(persona: Dict, relationship_status: str) -> str:
        """
        Recommend engagement strategy based on persona and relationship status.

        Strategies:
        - proactive_outreach: Initiate contact, highlight growth opportunities
        - patient_nurture: Maintain presence, build relationship over time
        - value_prop_focused: Lead with specific opportunity/compensation
        - escalate_to_partner: Partner/hiring manager should lead conversation
        """
        if relationship_status == "RECEPTIVE":
            if "growth" in persona["motivators"]:
                return "proactive_outreach_with_growth_focus"
            elif "leadership" in persona["motivators"]:
                return "proactive_outreach_with_leadership_focus"
            else:
                return "proactive_outreach"

        elif relationship_status == "INTERESTED":
            if persona["constraints"]:
                return "value_prop_with_constraint_solutions"
            else:
                return "patient_nurture_with_value_prop"

        elif relationship_status == "HESITANT":
            if "negotiation_difficulty" in persona["risk_factors"]:
                return "escalate_to_partner"
            else:
                return "value_prop_focused_with_patience"

        else:  # RESISTANT
            return "escalate_to_partner"

    @staticmethod
    def _store_persona_facts(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        persona: Dict,
        profile: Dict,
    ) -> int:
        """
        Store persona facts in candidate memory for downstream systems.

        Returns: Count of facts stored
        """
        facts_count = 0

        try:
            # Career level
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="career_level",
                fact_value=persona["career_level"],
                confidence=0.95,
            )
            facts_count += 1

            # Motivators
            for motivator in persona["motivators"]:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="MOTIVATOR",
                    fact_key=f"motivator_{motivator}",
                    fact_value="true",
                    confidence=0.8,
                )
                facts_count += 1

            # Constraints
            for constraint in persona["constraints"]:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="CONSTRAINT",
                    fact_key=constraint,
                    fact_value="true",
                    confidence=0.85,
                )
                facts_count += 1

            # Risk factors
            for risk in persona["risk_factors"]:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key=f"risk_{risk}",
                    fact_value="true",
                    confidence=0.75,
                )
                facts_count += 1

            # Skill count and depth
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="SKILL",
                fact_key="skill_depth",
                fact_value=persona["skill_depth"],
                confidence=0.9,
            )
            facts_count += 1

            # Engagement readiness
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="engagement_readiness",
                fact_value=persona["engagement_readiness"],
                confidence=0.8,
            )
            facts_count += 1

            # Job stability
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="job_stability",
                fact_value=str(profile["job_stability"]),
                confidence=0.85,
            )
            facts_count += 1

            db.commit()

        except Exception as e:
            logger.error(f"Error storing persona facts for {candidate_id}: {str(e)}")
            db.rollback()

        return facts_count

    @staticmethod
    async def report_to_flash(
        candidate_id: str,
        tenant_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Report candidate relationship status to Flash Orchestration Engine.

        Flash uses this to:
        - Assess talent pool quality
        - Identify high-potential candidates
        - Coordinate hiring strategy across systems
        - Flag engagement challenges early
        """
        # Extract persona
        persona_result = await RelationBuildingAgent.extract_candidate_persona(
            candidate_id, tenant_id, db
        )

        if persona_result["status"] != "success":
            return persona_result

        # Prepare report for Flash
        persona = persona_result["persona"]
        status = persona_result["relationship_status"]

        return {
            "status": "success",
            "report_type": "CANDIDATE_RELATIONSHIP_STATUS",
            "candidate_id": candidate_id,
            "candidate_name": persona_result.get("candidate_name"),
            "relationship_status": status,
            "career_level": persona["career_level"],
            "engagement_readiness": persona["engagement_readiness"],
            "primary_motivator": persona["motivation_primary"],
            "risk_factors": persona["risk_factors"],
            "constraints": persona["constraints"],
            "recommended_action": persona_result["recommended_engagement"],
            "persona": persona,
        }
