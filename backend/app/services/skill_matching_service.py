"""Skill Matching Service - Score candidate skills against job requirements by recency.

Spartan Pattern: This service reports health metrics to Flash (Alpha Wolf).
- Health metric: "Can I match candidates to jobs with these requirements?"
- Cascade detection: If match quality < 60%, escalate to Flash immediately
- Formation role: Position 3 (Interview/Offer) - depends on Thunder candidate quality + Flash job clarity
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.user import Jobs, Users
from app.models.candidate_job_score import CandidateJobScore

logger = logging.getLogger(__name__)

# Recency scoring thresholds (Spartan health metrics)
RECENCY_PENALTY_PER_DAY = 30 / 90  # 30 points deducted over 90 days
RECENCY_FLOOR = 70  # Minimum score for skills older than 90 days
PRIMARY_SKILL_BONUS = 10  # Extra points for primary skills
PHALANX_HEALTH_THRESHOLD = 60  # Formation integrity threshold

class SkillMatchingService:
    """Skill matching with recency scoring - reports health to Flash (Alpha Wolf)."""

    @staticmethod
    def score_candidate_skill_recency(
        candidate_id: str,
        job_id: str,
        db: Session
    ) -> Dict:
        """
        Score candidate skills by recency against job requirements.

        Returns health metrics for Spartan formation:
        - overall_recency_score: 0-100 (phalanx health for this match)
        - can_proceed: bool (can Flash proceed with this candidate?)
        - skill_details: List of individual skill scores
        - primary_skill_count: How many primary skills match
        - formation_feedback: Message for Flash about phalanx integrity
        """
        try:
            candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
            if not candidate:
                logger.error(f"[SkillMatching] Candidate {candidate_id} not found")
                return {
                    "overall_recency_score": 0,
                    "can_proceed": False,
                    "reason": "Candidate not found",
                    "formation_feedback": "FAIL: Candidate missing - cascade risk HIGH"
                }

            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                logger.error(f"[SkillMatching] Job {job_id} not found")
                return {
                    "overall_recency_score": 0,
                    "can_proceed": False,
                    "reason": "Job not found",
                    "formation_feedback": "FAIL: Job missing - cascade risk HIGH"
                }

            # Extract candidate skills (structured format from resume)
            candidate_skills = SkillMatchingService._parse_candidate_skills(candidate, db)

            # Extract job requirements (structured format from job creation)
            job_skills = SkillMatchingService._parse_job_skills(job, db)

            # Score each required skill against candidate's skills
            skill_scores = []
            primary_match_count = 0

            for job_skill in job_skills:
                score = SkillMatchingService._score_single_skill(
                    job_skill,
                    candidate_skills,
                    candidate.candidate_id
                )
                skill_scores.append(score)

                if score.get("matched") and job_skill.get("is_primary"):
                    primary_match_count += 1

            # Calculate overall recency score
            if skill_scores:
                overall_score = sum(s.get("score", 0) for s in skill_scores) / len(skill_scores)
            else:
                overall_score = 0

            # Spartan formation health check
            can_proceed = overall_score >= PHALANX_HEALTH_THRESHOLD

            if can_proceed:
                formation_feedback = f"OK: Recency match {overall_score:.0f}% - formation can proceed"
                logger.info(f"[SkillMatching] {candidate_id} → {job_id}: Score {overall_score:.0f}% ✓")
            else:
                formation_feedback = f"ALERT: Recency match {overall_score:.0f}% < {PHALANX_HEALTH_THRESHOLD}% - cascade risk MEDIUM"
                logger.warning(f"[SkillMatching] {candidate_id} → {job_id}: Score {overall_score:.0f}% - LOW MATCH")

            return {
                "overall_recency_score": round(overall_score),
                "can_proceed": can_proceed,
                "skill_details": skill_scores,
                "primary_skill_count": primary_match_count,
                "avg_days_since_used": SkillMatchingService._avg_days_since_used(skill_scores),
                "formation_feedback": formation_feedback
            }

        except Exception as e:
            logger.error(f"[SkillMatching] Error scoring {candidate_id} vs {job_id}: {str(e)}", exc_info=True)
            return {
                "overall_recency_score": 0,
                "can_proceed": False,
                "reason": str(e),
                "formation_feedback": "ERROR: Scoring failed - escalate to Flash"
            }

    @staticmethod
    def get_best_matches_by_recency(
        job_id: str,
        candidate_ids: List[str],
        db: Session
    ) -> List[Dict]:
        """
        Rank candidates by skill recency for a specific job.

        Returns sorted list with health metrics for Flash to make decisions.
        Spartan pattern: If no candidates meet threshold, report formation integrity CRITICAL.
        """
        matches = []

        for candidate_id in candidate_ids:
            result = SkillMatchingService.score_candidate_skill_recency(
                candidate_id,
                job_id,
                db
            )

            matches.append({
                "candidate_id": candidate_id,
                "recency_score": result.get("overall_recency_score", 0),
                "can_proceed": result.get("can_proceed", False),
                "primary_skill_count": result.get("primary_skill_count", 0),
                "avg_days_since_used": result.get("avg_days_since_used", 999),
                "formation_feedback": result.get("formation_feedback", "Unknown")
            })

        # Sort by recency score (descending), then by primary skill count
        matches.sort(
            key=lambda x: (-x["recency_score"], -x["primary_skill_count"]),
            reverse=False
        )

        # Spartan formation integrity check
        viable_count = sum(1 for m in matches if m["can_proceed"])
        if viable_count == 0:
            logger.error(f"[SkillMatching] Job {job_id}: NO viable candidates - PHALANX INTEGRITY CRITICAL")

        return matches

    @staticmethod
    def integrate_with_candidate_scoring(
        candidate_id: str,
        job_id: str,
        db: Session
    ) -> Optional[Dict]:
        """
        Integrate recency scoring into CandidateJobScore (same pattern as technical_scoring_service).

        Updates or creates score_breakdown with recency metrics.
        """
        try:
            # Get or create score record
            score_record = db.query(CandidateJobScore).filter(
                CandidateJobScore.candidate_id == candidate_id,
                CandidateJobScore.job_id == job_id
            ).first()

            if not score_record:
                logger.debug(f"[SkillMatching] No existing score for {candidate_id} → {job_id}, skipping integration")
                return None

            # Calculate recency score
            recency_result = SkillMatchingService.score_candidate_skill_recency(
                candidate_id,
                job_id,
                db
            )

            # Merge into score_breakdown (same pattern as technical_scoring_service)
            if score_record.score_breakdown is None:
                score_record.score_breakdown = {}

            score_record.score_breakdown["recency_score"] = recency_result.get("overall_recency_score")
            score_record.score_breakdown["primary_skill_count"] = recency_result.get("primary_skill_count")
            score_record.score_breakdown["avg_days_since_used"] = recency_result.get("avg_days_since_used")
            score_record.score_breakdown["formation_feedback"] = recency_result.get("formation_feedback")

            db.commit()
            logger.info(f"[SkillMatching] Integrated recency score for {candidate_id} → {job_id}")
            return recency_result

        except Exception as e:
            logger.error(f"[SkillMatching] Failed to integrate recency for {candidate_id} → {job_id}: {str(e)}", exc_info=True)
            db.rollback()
            return None

    # ─────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_candidate_skills(candidate: Candidate, db: Session) -> List[Dict]:
        """Extract structured skills from candidate."""
        try:
            # Try to get from candidate_skill_tags (structured format)
            if hasattr(candidate, 'skills') and candidate.skills:
                if isinstance(candidate.skills, list):
                    return candidate.skills

            # Fallback: return empty list (no skills found)
            return []
        except Exception as e:
            logger.warning(f"[SkillMatching] Failed to parse candidate skills: {e}")
            return []

    @staticmethod
    def _parse_job_skills(job: Jobs, db: Session) -> List[Dict]:
        """Extract structured skills from job."""
        try:
            if hasattr(job, 'required_skills_canonical') and job.required_skills_canonical:
                if isinstance(job.required_skills_canonical, list) and len(job.required_skills_canonical) > 0:
                    first_item = job.required_skills_canonical[0]

                    # Already structured format
                    if isinstance(first_item, dict) and "name" in first_item:
                        return job.required_skills_canonical

                    # Flat format - convert to structured
                    if isinstance(first_item, str):
                        return [
                            {
                                "name": skill,
                                "years_of_experience": None,
                                "last_used_date": None,
                                "is_primary": False
                            }
                            for skill in job.required_skills_canonical
                        ]

            return []
        except Exception as e:
            logger.warning(f"[SkillMatching] Failed to parse job skills: {e}")
            return []

    @staticmethod
    def _score_single_skill(
        job_skill: Dict,
        candidate_skills: List[Dict],
        candidate_id: str
    ) -> Dict:
        """Score a single job skill requirement against candidate's skills."""
        job_skill_name = job_skill.get("name", "").lower().strip()

        # Find matching candidate skill
        matched_skill = None
        for cand_skill in candidate_skills:
            if cand_skill.get("name", "").lower().strip() == job_skill_name:
                matched_skill = cand_skill
                break

        if not matched_skill:
            return {
                "job_skill": job_skill_name,
                "matched": False,
                "score": 0,
                "reason": "Skill not found in candidate profile"
            }

        # Calculate recency penalty
        last_used = matched_skill.get("last_used_date")
        days_since_used = 0

        if last_used:
            try:
                if isinstance(last_used, str):
                    last_used_date = datetime.fromisoformat(last_used.replace("Z", "+00:00")).date()
                else:
                    last_used_date = last_used if isinstance(last_used, date) else last_used.date()

                days_since_used = (datetime.now().date() - last_used_date).days
            except Exception:
                days_since_used = 999  # Unknown = assume old

        # Apply recency penalty
        base_score = 100
        penalty = min(30, days_since_used * RECENCY_PENALTY_PER_DAY)  # Max 30 point deduction
        score = max(RECENCY_FLOOR, base_score - penalty)

        # Apply primary skill bonus
        if matched_skill.get("is_primary"):
            score = min(100, score + PRIMARY_SKILL_BONUS)

        return {
            "job_skill": job_skill_name,
            "matched": True,
            "score": round(score),
            "days_since_used": days_since_used,
            "is_primary": matched_skill.get("is_primary", False),
            "reason": f"Last used {days_since_used} days ago"
        }

    @staticmethod
    def _avg_days_since_used(skill_scores: List[Dict]) -> float:
        """Calculate average days since skills were last used."""
        if not skill_scores:
            return 0

        matched_skills = [s for s in skill_scores if s.get("matched")]
        if not matched_skills:
            return 0

        total_days = sum(s.get("days_since_used", 0) for s in matched_skills)
        return round(total_days / len(matched_skills))
