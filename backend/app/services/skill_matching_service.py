"""Skill Matching Service - Score candidate skills against job requirements by recency.

Spartan Pattern: This service reports health metrics to Flash (Alpha Wolf).
- Health metric: "Can I match candidates to jobs with these requirements?"
- Cascade detection: If match quality < 60%, escalate to Flash immediately
- Formation role: Position 3 (Interview/Offer) - depends on Thunder candidate quality + Flash job clarity
"""
from datetime import date
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings

from app.models.candidate import Candidate
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs, _skills_list
from app.models.candidate_job_score import CandidateJobScore
from app.services.skill_extraction_service import normalize_skills

logger = logging.getLogger(__name__)

# Recency scoring thresholds (Spartan health metrics)
RECENCY_PENALTY_PER_DAY = 30 / 90  # 30 points deducted over 90 days
RECENCY_FLOOR = 70  # Minimum score for skills older than 90 days
PRIMARY_SKILL_BONUS = 10  # Extra points for primary skills
# A skill found only in the candidate's free-text skills line, not as a tagged skill record
TEXT_ONLY_MATCH_SCORE = 80

class SkillMatchingService:
    """Skill matching with recency scoring - reports health to Flash (Alpha Wolf).

    One skill schema on both sides (app.schemas.user.SkillRequirement): name (canonical, via
    skill_extraction_service.normalize_skills), years_of_experience, last_used_date, is_primary.
    The job side is Jobs.required_skills_canonical, else its skills text; the candidate side is
    their CandidateSkillTag rows plus their candidateSkills text."""

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
        - can_proceed: bool (score at least FLASH_MATCH_MIN_SCORE and no required skill missing)
        - skill_details: List of individual skill scores
        - primary_skill_count: How many primary skills match
        - formation_feedback: Message for Flash about phalanx integrity

        Raises:
            ValueError: the candidate or the job does not exist
        """
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        result = SkillMatchingService.score_skills(
            SkillMatchingService.job_skills(job),
            SkillMatchingService.candidate_skills(db, candidate),
            mode=job.job_skills_boolean_mode or "AND",
        )
        if result["can_proceed"]:
            formation_feedback = f"OK: Recency match {result['score']}% - formation can proceed"
            logger.info(f"[SkillMatching] {candidate_id} → {job_id}: Score {result['score']}% ✓")
        else:
            formation_feedback = (f"ALERT: Recency match {result['score']}% (needs {settings.FLASH_MATCH_MIN_SCORE}%, "
                                  f"missing {', '.join(result['missing_mandatory']) or 'none'}) - cascade risk MEDIUM")
            logger.warning(f"[SkillMatching] {candidate_id} → {job_id}: Score {result['score']}% - LOW MATCH")

        return {
            "overall_recency_score": result["score"],
            "can_proceed": result["can_proceed"],
            "skill_details": result["skill_details"],
            "primary_skill_count": result["primary_skill_count"],
            "missing_mandatory": result["missing_mandatory"],
            "avg_days_since_used": SkillMatchingService._avg_days_since_used(result["skill_details"]),
            "formation_feedback": formation_feedback
        }

    @staticmethod
    def score_skills(job_skills: List[Dict], candidate_skills: List[Dict], *, mode: str = "AND") -> Dict:
        """Score a candidate's skills against a job's. Each job skill scores 0 (missing) to 100
        (tagged, recently used); the overall score is their average. A skill is required when it
        is primary, or in AND mode unless it is explicitly optional (mandatory: false)."""
        by_name = {}
        for skill in candidate_skills:
            key = skill["name"].lower()
            # a tagged skill record beats the same skill found only in free text
            if key not in by_name or (by_name[key].get("source") == "text" and skill.get("source") != "text"):
                by_name[key] = skill

        details, missing, primary_matches = [], [], 0
        for job_skill in job_skills:
            detail = SkillMatchingService._score_single_skill(job_skill, by_name.get(job_skill["name"].lower()))
            details.append(detail)
            required = job_skill.get("is_primary") or ((mode or "AND").upper() != "OR" and job_skill.get("mandatory", True) is not False)
            if not detail["matched"] and required:
                missing.append(job_skill["name"])
            if detail["matched"] and job_skill.get("is_primary"):
                primary_matches += 1
        score = round(sum(d["score"] for d in details) / len(details)) if details else 0
        return {
            "score": score,
            "matched": [d["job_skill"] for d in details if d["matched"]],
            "missing_mandatory": missing,
            "primary_skill_count": primary_matches,
            "skill_details": details,
            "can_proceed": bool(details) and score >= settings.FLASH_MATCH_MIN_SCORE and not missing,
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
                "recency_score": result["overall_recency_score"],
                "can_proceed": result["can_proceed"],
                "primary_skill_count": result["primary_skill_count"],
                "avg_days_since_used": result["avg_days_since_used"],
                "formation_feedback": result["formation_feedback"]
            })

        # Sort by recency score (descending), then by primary skill count
        matches.sort(key=lambda x: (-x["recency_score"], -x["primary_skill_count"]))

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

        Updates the existing score_breakdown with recency metrics; None when the candidate has
        no score for this job yet. Raises on failure (after rolling back).
        """
        score_record = db.query(CandidateJobScore).filter(
            CandidateJobScore.candidate_id == candidate_id,
            CandidateJobScore.job_id == job_id
        ).first()

        if not score_record:
            logger.debug(f"[SkillMatching] No existing score for {candidate_id} → {job_id}, skipping integration")
            return None

        try:
            recency_result = SkillMatchingService.score_candidate_skill_recency(candidate_id, job_id, db)
            breakdown = dict(score_record.score_breakdown or {})
            breakdown["recency_score"] = recency_result.get("overall_recency_score")
            breakdown["primary_skill_count"] = recency_result.get("primary_skill_count")
            breakdown["avg_days_since_used"] = recency_result.get("avg_days_since_used")
            breakdown["formation_feedback"] = recency_result.get("formation_feedback")
            score_record.score_breakdown = breakdown
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[SkillMatching] Failed to integrate recency for {candidate_id} → {job_id}: {e}", exc_info=True)
            raise
        logger.info(f"[SkillMatching] Integrated recency score for {candidate_id} → {job_id}")
        return recency_result

    # ─────────────────────────────────────────────────────────────────────
    # SKILL SOURCES
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def candidate_skills(db: Session, candidate: Candidate, tags: Optional[List[CandidateSkillTag]] = None) -> List[Dict]:
        """The candidate's skills, canonical names: their CandidateSkillTag rows (source "tag")
        plus their candidateSkills text (source "text"). `tags` lets a caller that already
        loaded the rows for many candidates pass them in."""
        if tags is None:
            tags = db.query(CandidateSkillTag).filter(
                CandidateSkillTag.tenant_id == str(candidate.tenant_id),
                CandidateSkillTag.candidate_id == candidate.candidateID,
            ).all()
        skills = [{"name": n["canonical"], "years_of_experience": None, "last_used_date": None,
                   "is_primary": False, "source": "tag"}
                  for n in normalize_skills([t.skill_canonical for t in tags])]
        text = [s for s in (candidate.candidateSkills or "").split(",") if s.strip()]
        skills += [{"name": n["canonical"], "years_of_experience": None, "last_used_date": None,
                    "is_primary": False, "source": "text"}
                   for n in normalize_skills(text)]
        return skills

    @staticmethod
    def job_skills(job: Jobs) -> List[Dict]:
        """The job's required skills in the one schema, names normalised: its structured
        required_skills_canonical (dicts or plain names), else its skills text."""
        raw = job.required_skills_canonical or [{"name": name} for name in _skills_list(job)]
        skills, seen = [], set()
        for item in raw:
            entry = dict(item) if isinstance(item, dict) else {"name": item}
            if not isinstance(entry.get("name"), str) or not entry["name"].strip():
                raise ValueError(f"Job {job.jobID}: skill without a name in required_skills_canonical: {item!r}")
            canonical = normalize_skills([entry["name"]])[0]["canonical"]
            if canonical.lower() in seen:
                continue
            seen.add(canonical.lower())
            skills.append({
                "name": canonical,
                "years_of_experience": entry.get("years_of_experience", entry.get("years")),
                "last_used_date": entry.get("last_used_date"),
                "is_primary": bool(entry.get("is_primary")),
                "mandatory": entry.get("mandatory", True),
            })
        return skills

    # ─────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _score_single_skill(job_skill: Dict, matched_skill: Optional[Dict]) -> Dict:
        """Score a single job skill requirement against the candidate's matching skill (or None)."""
        job_skill_name = job_skill["name"]

        if not matched_skill:
            return {
                "job_skill": job_skill_name,
                "matched": False,
                "score": 0,
                "reason": "Skill not found in candidate profile"
            }

        if matched_skill.get("source") == "text":
            return {
                "job_skill": job_skill_name,
                "matched": True,
                "score": TEXT_ONLY_MATCH_SCORE,
                "days_since_used": 0,
                "is_primary": False,
                "reason": "Listed in the candidate's skills text only"
            }

        # Calculate recency penalty
        last_used = matched_skill.get("last_used_date")
        days_since_used = 0

        if last_used:
            if isinstance(last_used, str):
                last_used_date = datetime.fromisoformat(last_used.replace("Z", "+00:00")).date()
            else:
                last_used_date = last_used if isinstance(last_used, date) else last_used.date()
            days_since_used = (datetime.now().date() - last_used_date).days

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
            "reason": f"Last used {days_since_used} days ago" if last_used else "Tagged skill"
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
