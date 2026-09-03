"""
HRMS-1105 (S-320) -- Candidate Ranking & Scoring Engine.

Real implementation: Calculate fit scores based on:
- Skills match (required vs candidate skills) — 40% weight
- Experience level (candidate years vs demand min/max) — 35% weight
- Location match (candidate location vs job location) — 15% weight
- Resume completeness (quality of resume) — 10% weight

Formula: weighted_sum of (component_score * component_weight)
Result: 0-100 scale fit score per candidate-job pair

Ranking: sort candidates by fit_score descending
Best Match: top candidate for job
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from decimal import Decimal
import logging

from app.models.candidate import Candidate
from app.models.demand import Demand
from app.core.logging import logger

logger = logging.getLogger(__name__)

class CandidateScoringService:
    """Score and rank candidates against job requirements (HRMS-1105 / S-320)."""

    # Scoring weights (sum must equal 100)
    SKILLS_WEIGHT = 40
    EXPERIENCE_WEIGHT = 35
    LOCATION_WEIGHT = 15
    RESUME_WEIGHT = 10

    def calculate_fit_score(self, db: Session, candidate_id: str, demand_id: str, tenant_id: int) -> dict:
        """
        Calculate how well a candidate matches a job demand.

        Args:
            db: Database session
            candidate_id: Candidate ID
            demand_id: Demand (job) ID
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Dict with fit_score (0-100), component scores, and recommendation

        Raises:
            ValueError: If candidate or demand not found
        """
        try:
            # Fetch candidate and demand
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
                Candidate.tenant_id == tenant_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found in tenant {tenant_id}")

            demand = db.query(Demand).filter(
                Demand.id == demand_id,
                Demand.tenant_id == tenant_id
            ).first()

            if not demand:
                raise ValueError(f"Demand {demand_id} not found in tenant {tenant_id}")

            # Calculate component scores
            skills_score = self._calculate_skills_match(candidate, demand)
            experience_score = self._calculate_experience_match(candidate, demand)
            location_score = self._calculate_location_match(candidate, demand)
            resume_score = self._calculate_resume_quality(candidate)

            # Calculate weighted fit score
            fit_score = int(
                (skills_score * self.SKILLS_WEIGHT +
                 experience_score * self.EXPERIENCE_WEIGHT +
                 location_score * self.LOCATION_WEIGHT +
                 resume_score * self.RESUME_WEIGHT) / 100
            )

            # Clamp to 0-100
            fit_score = max(0, min(100, fit_score))

            # Determine recommendation
            if fit_score >= 85:
                recommendation = "STRONG_MATCH"
            elif fit_score >= 70:
                recommendation = "GOOD_MATCH"
            elif fit_score >= 50:
                recommendation = "FAIR_MATCH"
            else:
                recommendation = "WEAK_MATCH"

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "demand_id": demand_id,
                "fit_score": fit_score,
                "components": {
                    "skills_match": skills_score,
                    "experience_level": experience_score,
                    "location_match": location_score,
                    "resume_completeness": resume_score
                },
                "weights": {
                    "skills": self.SKILLS_WEIGHT,
                    "experience": self.EXPERIENCE_WEIGHT,
                    "location": self.LOCATION_WEIGHT,
                    "resume": self.RESUME_WEIGHT
                },
                "recommendation": recommendation,
                "calculated_at": datetime.utcnow().isoformat()
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e),
                "candidate_id": candidate_id,
                "demand_id": demand_id
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error calculating fit score: {e}")
            return {
                "status": "error",
                "error": f"Internal server error: {str(e)}",
                "candidate_id": candidate_id,
                "demand_id": demand_id
            }

    def rank_candidates(self, db: Session, demand_id: str, tenant_id: int, limit: int = 50) -> dict:
        """
        Rank all candidates for a specific job demand.

        Args:
            db: Database session
            demand_id: Demand (job) ID
            tenant_id: Tenant ID for multi-tenancy
            limit: Maximum number of candidates to return (default 50)

        Returns:
            Dict with ranked candidates sorted by fit_score descending

        Raises:
            ValueError: If demand not found
        """
        try:
            # Verify demand exists
            demand = db.query(Demand).filter(
                Demand.id == demand_id,
                Demand.tenant_id == tenant_id
            ).first()

            if not demand:
                raise ValueError(f"Demand {demand_id} not found in tenant {tenant_id}")

            # Get all candidates in tenant (in real system, could filter by status, etc.)
            candidates = db.query(Candidate).filter(
                Candidate.tenant_id == tenant_id
            ).limit(limit).all()

            ranked_candidates = []

            for candidate in candidates:
                # Calculate fit score for each candidate
                fit_result = self.calculate_fit_score(db, candidate.candidateID, demand_id, tenant_id)

                if fit_result.get("status") == "success":
                    ranked_candidates.append({
                        "candidate_id": candidate.candidateID,
                        "candidate_name": f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip(),
                        "candidate_email": candidate.candidateEmail,
                        "candidate_job_title": candidate.candidateJobTitle,
                        "fit_score": fit_result["fit_score"],
                        "recommendation": fit_result["recommendation"],
                        "components": fit_result["components"]
                    })

            # Sort by fit_score descending
            ranked_candidates.sort(key=lambda x: x["fit_score"], reverse=True)

            # Add rank numbers
            for i, candidate in enumerate(ranked_candidates, 1):
                candidate["rank"] = i

            return {
                "status": "success",
                "demand_id": demand_id,
                "total_candidates_evaluated": len(ranked_candidates),
                "ranked_candidates": ranked_candidates,
                "ranked_at": datetime.utcnow().isoformat()
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e),
                "demand_id": demand_id
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error ranking candidates: {e}")
            return {
                "status": "error",
                "error": f"Internal server error: {str(e)}",
                "demand_id": demand_id
            }

    def identify_best_match(self, db: Session, demand_id: str, tenant_id: int) -> dict:
        """
        Identify the top candidate for a job demand.

        Args:
            db: Database session
            demand_id: Demand (job) ID
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Dict with best matching candidate and fit score

        Raises:
            ValueError: If demand not found or no candidates available
        """
        try:
            # Verify demand exists
            demand = db.query(Demand).filter(
                Demand.id == demand_id,
                Demand.tenant_id == tenant_id
            ).first()

            if not demand:
                raise ValueError(f"Demand {demand_id} not found in tenant {tenant_id}")

            # Get all candidates
            candidates = db.query(Candidate).filter(
                Candidate.tenant_id == tenant_id
            ).all()

            if not candidates:
                raise ValueError(f"No candidates found for demand {demand_id}")

            # Find best candidate
            best_candidate = None
            best_score = -1

            for candidate in candidates:
                fit_result = self.calculate_fit_score(db, candidate.candidateID, demand_id, tenant_id)

                if fit_result.get("status") == "success":
                    fit_score = fit_result["fit_score"]
                    if fit_score > best_score:
                        best_score = fit_score
                        best_candidate = {
                            "candidate_id": candidate.candidateID,
                            "candidate_name": f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip(),
                            "candidate_email": candidate.candidateEmail,
                            "candidate_job_title": candidate.candidateJobTitle,
                            "fit_score": fit_score,
                            "recommendation": fit_result["recommendation"],
                            "components": fit_result["components"]
                        }

            if not best_candidate:
                raise ValueError(f"Could not calculate fit scores for any candidate")

            # Determine if ready for interview
            ready_to_interview = best_candidate["fit_score"] >= 70

            return {
                "status": "success",
                "demand_id": demand_id,
                "best_match_candidate_id": best_candidate["candidate_id"],
                "best_match_candidate_name": best_candidate["candidate_name"],
                "best_match_candidate_email": best_candidate["candidate_email"],
                "fit_score": best_candidate["fit_score"],
                "recommendation": best_candidate["recommendation"],
                "components": best_candidate["components"],
                "ready_to_interview": ready_to_interview,
                "identified_at": datetime.utcnow().isoformat()
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e),
                "demand_id": demand_id
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error identifying best match: {e}")
            return {
                "status": "error",
                "error": f"Internal server error: {str(e)}",
                "demand_id": demand_id
            }

    # ============ Component Scoring Methods ============

    def _calculate_skills_match(self, candidate: Candidate, demand: Demand) -> int:
        """
        Calculate skills match score (0-100).

        Compares candidate skills against required and nice-to-have skills.
        Required skills match: 80% of score
        Nice-to-have skills match: 20% of score
        """
        if not candidate.candidateSkills or not demand.required_skills:
            return 0

        try:
            # Parse skills
            candidate_skills = self._parse_skills(candidate.candidateSkills)
            required_skills = self._parse_skills(demand.required_skills)
            nice_to_have = self._parse_skills(demand.nice_to_have_skills or "[]")

            if not required_skills:
                return 100  # No required skills = full match

            # Calculate required skills match
            required_matches = sum(1 for skill in required_skills if skill in candidate_skills)
            required_match_pct = (required_matches / len(required_skills)) * 100

            # Calculate nice-to-have match
            nice_match_pct = 0
            if nice_to_have:
                nice_matches = sum(1 for skill in nice_to_have if skill in candidate_skills)
                nice_match_pct = (nice_matches / len(nice_to_have)) * 100

            # Weighted combination
            skills_score = int((required_match_pct * 0.8) + (nice_match_pct * 0.2))
            return max(0, min(100, skills_score))
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Error calculating skills match: {e}")
            return 0

    def _calculate_experience_match(self, candidate: Candidate, demand: Demand) -> int:
        """
        Calculate experience level match score (0-100).

        Compares candidate total experience (months) against demand min/max.
        """
        if candidate.total_experience_months is None:
            return 0  # No experience data = no match

        try:
            candidate_years = candidate.total_experience_months / 12.0
            min_years = float(demand.min_experience_years or 0)
            max_years = float(demand.max_experience_years or 999)

            # Perfect match: candidate years within range
            if min_years <= candidate_years <= max_years:
                return 100

            # Below minimum
            if candidate_years < min_years:
                gap_years = min_years - candidate_years
                # 5% penalty per year below minimum
                penalty = min(50, gap_years * 5)
                return max(0, int(100 - penalty))

            # Above maximum
            if candidate_years > max_years:
                excess_years = candidate_years - max_years
                # 2% penalty per year above maximum (less harsh than below minimum)
                penalty = min(30, excess_years * 2)
                return max(0, int(100 - penalty))

            return 100
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Error calculating experience match: {e}")
            return 0

    def _calculate_location_match(self, candidate: Candidate, demand: Demand) -> int:
        """
        Calculate location match score (0-100).

        Returns 100 if locations match (case-insensitive), 0 otherwise.
        For remote jobs, returns 100 if candidate is anywhere.
        """
        try:
            # Remote job matches anyone
            if demand.work_location and demand.work_location.upper() == "REMOTE":
                return 100

            # If no candidate location, partial match (50%)
            if not candidate.candidateCurrentLocation:
                return 50

            if not demand.job_location:
                return 50

            # Exact location match
            candidate_loc = candidate.candidateCurrentLocation.lower().strip()
            demand_loc = demand.job_location.lower().strip()

            if candidate_loc == demand_loc:
                return 100

            # Partial match (city-level matching could be added here)
            # For now, just check if any part matches
            candidate_parts = candidate_loc.split(",")
            demand_parts = demand_loc.split(",")

            for c_part in candidate_parts:
                for d_part in demand_parts:
                    if c_part.strip() == d_part.strip():
                        return 75  # Partial location match

            return 0  # No location match
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Error calculating location match: {e}")
            return 50

    def _calculate_resume_quality(self, candidate: Candidate) -> int:
        """
        Calculate resume quality score (0-100).

        Uses resume_completeness_score if available, otherwise estimates.
        """
        if candidate.resume_completeness_score is not None:
            return max(0, min(100, candidate.resume_completeness_score))

        # Estimate based on available fields
        quality_score = 0
        field_count = 0

        if candidate.candidateFirstName and candidate.candidateLastName:
            quality_score += 20
            field_count += 1
        if candidate.candidateEmail:
            quality_score += 20
            field_count += 1
        if candidate.candidateMobile:
            quality_score += 15
            field_count += 1
        if candidate.candidateSkills:
            quality_score += 20
            field_count += 1
        if candidate.total_experience_months is not None:
            quality_score += 15
            field_count += 1
        if candidate.candidateCurrentLocation:
            quality_score += 10
            field_count += 1

        return max(0, min(100, quality_score))

    def _parse_skills(self, skills_json: str) -> list:
        """Parse skills from JSON string (or comma-separated string)."""
        if not skills_json:
            return []

        try:
            # Try JSON parse first
            if skills_json.startswith("["):
                parsed = json.loads(skills_json)
                return [s.lower().strip() for s in parsed if s]

            # Try comma-separated
            if "," in skills_json:
                return [s.lower().strip() for s in skills_json.split(",") if s.strip()]

            # Single skill
            return [skills_json.lower().strip()]
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Error parsing skills: {e}")
            # CRITICAL FIX: Raise error instead of returning empty list
            raise Exception(f"Failed to parse candidate skills: {str(e)}")
