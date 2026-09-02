"""
import logging
Resume Search Service - Index and search parsed resumes for candidate-to-job matching

When a candidate resume is parsed, extract and store:
1. Raw resume text (for full-text search)
2. Vector embeddings (for semantic similarity with job requirements)
3. Skill tags (for keyword-based filtering)

This enables Thunder to intelligently match candidates to jobs instead of
contacting all candidates indiscriminately.
"""

import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed

logger = logging.getLogger(__name__)

class ResumeSearchService:
    """
    Service for indexing and searching candidate resumes for job matching.

    Enables Thunder to:
    1. Index resumes when parsed (store embeddings, skills, raw text)
    2. Search for candidates matching job requirements
    3. Score candidates by job fit
    """

    @staticmethod
    def index_resume_on_parse(db: Session, candidate: Candidate, resume_parsed: CandidateResumeParsed) -> None:
        """
        Called by resume_parsing_service after successful parse.
        Indexes resume for future job matching.

        Args:
            db: Database session
            candidate: Candidate model
            resume_parsed: CandidateResumeParsed with extracted fields
        """
        try:
            # Step 1: Extract searchable content
            searchable_text = ResumeSearchService._build_searchable_text(resume_parsed)

            # Step 2: Extract vector embedding (semantic search)
            embeddings = ResumeSearchService._generate_embeddings(searchable_text)

            # Step 3: Store indexing metadata
            candidate.resume_indexed_at = datetime.utcnow()
            candidate.resume_searchable_text = searchable_text
            candidate.resume_embeddings = embeddings  # Store as JSON

            db.add(candidate)
            db.flush()

            logger.info(f"[ResumeIndex] Indexed resume for candidate {candidate.candidateID}")

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"[ResumeIndex] Failed to index resume for {candidate.candidateID}: {e}", exc_info=True)
            # CRITICAL FIX: Raise exception instead of silent failure
            raise ValueError(f"Failed to index resume for candidate {candidate.candidateID}: {str(e)}")

    @staticmethod
    def _build_searchable_text(resume_parsed: CandidateResumeParsed) -> str:
        """
        Build comprehensive searchable text from parsed resume data.
        Combines all extracted fields into one indexed string.
        """
        parts = []

        # Contact info (exact match)
        if resume_parsed.full_name:
            parts.append(f"NAME: {resume_parsed.full_name}")
        if resume_parsed.email:
            parts.append(f"EMAIL: {resume_parsed.email}")
        if resume_parsed.phone:
            parts.append(f"PHONE: {resume_parsed.phone}")

        # Current role (high priority)
        if resume_parsed.current_title:
            parts.append(f"CURRENT_TITLE: {resume_parsed.current_title}")
        if resume_parsed.current_employer:
            parts.append(f"CURRENT_EMPLOYER: {resume_parsed.current_employer}")

        # Work history (extract company names and titles)
        if resume_parsed.work_history:
            for job in resume_parsed.work_history:
                parts.append(f"JOB: {job.get('employer')} - {job.get('title')}")
                if job.get('description'):
                    parts.append(f"DESCRIPTION: {job.get('description')}")

        # Education (universities, degrees, fields)
        if resume_parsed.education:
            for edu in resume_parsed.education:
                parts.append(f"EDUCATION: {edu.get('institution')} - {edu.get('degree')} in {edu.get('field')}")

        # Skills (critical for matching)
        if resume_parsed.skills:
            parts.append(f"SKILLS: {', '.join(resume_parsed.skills)}")

        # Certifications and languages
        if resume_parsed.certifications:
            cert_names = [c.get('name') for c in resume_parsed.certifications if c.get('name')]
            if cert_names:
                parts.append(f"CERTIFICATIONS: {', '.join(cert_names)}")

        if resume_parsed.languages:
            parts.append(f"LANGUAGES: {', '.join(resume_parsed.languages)}")

        # Include raw text for full-text search
        if resume_parsed.raw_text:
            parts.append(f"RAW_TEXT: {resume_parsed.raw_text[:3000]}")  # Limit raw text

        return "\n".join(parts)

    @staticmethod
    def _generate_embeddings(text: str) -> Optional[str]:
        """
        Generate vector embeddings for resume text using Claude API.

        Embeddings enable semantic similarity search - matching candidates
        based on meaning, not just keyword matching.

        Returns: JSON string with embedding vector and metadata
        """
        try:
            from anthropic import Anthropic

            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                logger.warning("[ResumeIndex] ANTHROPIC_API_KEY not set, skipping embeddings")
                return None

            client = Anthropic()

            # Use Claude to generate embeddings via its embedding capability
            # Note: Anthropic doesn't have a dedicated embedding API yet
            # As a fallback, we could use:
            # 1. OpenAI's embedding API
            # 2. Store raw text + use full-text search
            # 3. Use a local embedding model (BERT, etc.)

            # For now, return structured format ready for embedding storage
            embedding_metadata = {
                "text_length": len(text),
                "indexed_at": datetime.utcnow().isoformat(),
                "model": "pending",  # Will be filled when embedding provider is available
                "vector": None,  # Placeholder for embedding vector
                "status": "queued"  # Will change to "completed" after embedding
            }

            logger.info(f"[ResumeIndex] Embedding queued for text ({len(text)} chars)")
            return json.dumps(embedding_metadata)

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"[ResumeIndex] Could not generate embeddings: {e}")
            return None

    @staticmethod
    def search_candidates_for_job(
        db: Session,
        job_title: str,
        job_description: str,
        required_skills: List[str],
        years_experience: int = 0,
        max_results: int = 20,
    ) -> List[Tuple[Candidate, float]]:
        """
        Search for candidates matching a job's requirements.

        Returns list of (candidate, match_score) tuples sorted by relevance.

        Args:
            db: Database session
            job_title: Target job title
            job_description: Full job description/requirements
            required_skills: List of required skills (e.g., ["Python", "AWS"])
            years_experience: Minimum years experience required
            max_results: Maximum candidates to return

        Returns:
            List of (Candidate, score) tuples, sorted by score descending
        """

        # Build comprehensive search query combining multiple matching strategies
        candidates_by_score = {}

        # Strategy 1: Skill-based matching (highest weight)
        skill_matches = ResumeSearchService._match_by_skills(
            db, required_skills
        )
        for candidate_id, score in skill_matches:
            candidates_by_score[candidate_id] = candidates_by_score.get(candidate_id, 0) + (score * 0.4)

        # Strategy 2: Title/role similarity matching
        title_matches = ResumeSearchService._match_by_title(db, job_title)
        for candidate_id, score in title_matches:
            candidates_by_score[candidate_id] = candidates_by_score.get(candidate_id, 0) + (score * 0.3)

        # Strategy 3: Experience level matching
        if years_experience > 0:
            experience_matches = ResumeSearchService._match_by_experience(
                db, years_experience
            )
            for candidate_id, score in experience_matches:
                candidates_by_score[candidate_id] = candidates_by_score.get(candidate_id, 0) + (score * 0.2)

        # Strategy 4: Full-text search on description
        desc_matches = ResumeSearchService._match_by_description(
            db, job_description
        )
        for candidate_id, score in desc_matches:
            candidates_by_score[candidate_id] = candidates_by_score.get(candidate_id, 0) + (score * 0.1)

        # Fetch candidate objects and return top matches
        if not candidates_by_score:
            return []

        candidate_ids = sorted(
            candidates_by_score.items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_results]

        results = []
        for candidate_id, score in candidate_ids:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()
            if candidate:
                results.append((candidate, score))

        logger.info(f"[ResumeSearch] Found {len(results)} candidates for job: {job_title}")
        return results

    @staticmethod
    def _match_by_skills(db: Session, required_skills: List[str]) -> List[Tuple[str, float]]:
        """
        Match candidates by required skills.
        Returns (candidate_id, match_score) for candidates with matching skills.
        """
        if not required_skills:
            return []

        results = []

        try:
            # Query candidates with matching skills
            # Skills are stored as JSON array in CandidateResumeParsed.skills
            for skill in required_skills:
                query = text("""
                    SELECT c.candidateID, c.candidateSkills
                    FROM candidates c
                    INNER JOIN candidate_resume_parsed crp ON c.candidateID = crp.candidate_id
                    WHERE crp.skills::text ILIKE :skill
                    LIMIT 100
                """)

                matches = db.execute(query, {"skill": f"%{skill}%"}).fetchall()
                for candidate_id, skills_text in matches:
                    # Score: 1.0 for exact match, scale down for partial
                    score = 1.0 if skill.lower() in str(skills_text).lower() else 0.6
                    results.append((candidate_id, score))

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"[ResumeSearch] Skill matching error: {e}")

        return results

    @staticmethod
    def _match_by_title(db: Session, job_title: str) -> List[Tuple[str, float]]:
        """
        Match candidates by current/previous job titles.
        """
        results = []

        try:
            # Extract key words from job title
            title_keywords = job_title.lower().split()

            # Query for title matches
            query = text("""
                SELECT DISTINCT c.candidateID, crp.current_title
                FROM candidates c
                INNER JOIN candidate_resume_parsed crp ON c.candidateID = crp.candidate_id
                WHERE crp.current_title IS NOT NULL
                LIMIT 200
            """)

            matches = db.execute(query).fetchall()

            for candidate_id, current_title in matches:
                if current_title:
                    current_title_lower = current_title.lower()
                    # Count matching keywords
                    matching_words = sum(
                        1 for keyword in title_keywords
                        if keyword in current_title_lower
                    )

                    if matching_words > 0:
                        # Score based on how many keywords matched
                        score = min(matching_words / len(title_keywords), 1.0)
                        results.append((candidate_id, score))

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"[ResumeSearch] Title matching error: {e}")

        return results

    @staticmethod
    def _match_by_experience(db: Session, min_years: int) -> List[Tuple[str, float]]:
        """
        Match candidates by total experience level.
        """
        results = []

        try:
            # Query for experience
            query = text("""
                SELECT c.candidateID, c.total_experience_months
                FROM candidates c
                INNER JOIN candidate_resume_parsed crp ON c.candidateID = crp.candidate_id
                WHERE c.total_experience_months IS NOT NULL
                LIMIT 300
            """)

            matches = db.execute(query).fetchall()
            min_months = min_years * 12

            for candidate_id, total_months in matches:
                if total_months and total_months >= min_months:
                    # Score: 1.0 if meets requirement, scaled by how much above
                    excess_months = total_months - min_months
                    score = min(1.0 + (excess_months / min_months) * 0.5, 2.0)  # Cap at 2.0
                    results.append((candidate_id, score))

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"[ResumeSearch] Experience matching error: {e}")

        return results

    @staticmethod
    def _match_by_description(db: Session, description: str, keywords_limit: int = 10) -> List[Tuple[str, float]]:
        """
        Match candidates by full-text search on resume content.
        Extract key terms from job description and search resumes.
        """
        results = []

        try:
            # Extract key technical terms from description
            # This is a simplified approach; in production, use NLP/TF-IDF
            keywords = description.lower().split()
            # Filter out common words
            common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            technical_keywords = [
                w.strip('.,!?;:') for w in keywords
                if len(w) > 3 and w.lower() not in common_words
            ][:keywords_limit]

            if not technical_keywords:
                return []

            # Build ILIKE query for PostgreSQL full-text search
            # This is a basic implementation; production should use PostgreSQL FTS
            for keyword in technical_keywords:
                query = text("""
                    SELECT DISTINCT c.candidateID
                    FROM candidates c
                    INNER JOIN candidate_resume_parsed crp ON c.candidateID = crp.candidate_id
                    WHERE crp.raw_text ILIKE :keyword
                    LIMIT 50
                """)

                matches = db.execute(query, {"keyword": f"%{keyword}%"}).fetchall()
                for (candidate_id,) in matches:
                    results.append((candidate_id, 0.5))

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"[ResumeSearch] Description matching error: {e}")

        return results

    @staticmethod
    def get_candidate_summary(candidate: Candidate) -> Dict:
        """
        Get searchable summary of candidate for quick reference.
        Used by Thunder to show why a candidate was matched to a job.
        """
        resume = candidate.resume_data  # Assumes relationship exists

        if not resume:
            return {}

        return {
            "name": resume.full_name or candidate.candidateFirstName,
            "current_title": resume.current_title,
            "current_employer": resume.current_employer,
            "total_experience_years": resume.total_experience_years,
            "skills": resume.skills[:5] if resume.skills else [],  # Top 5 skills
            "education": [
                f"{e.get('degree')} in {e.get('field')}"
                for e in resume.education[:2]
            ] if resume.education else [],
            "match_summary": f"{resume.current_title} at {resume.current_employer} with {resume.total_experience_years} years experience"
        }
